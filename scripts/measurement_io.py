"""Shared I/O and helpers for the LEM/SICK analysis scripts.

This module holds the loaders and small helpers that were previously copied
verbatim across several analysis scripts. The logic is unchanged from those copies; it is parameterised
here (base path, time window) instead of relying on module-level globals, so each
script keeps a thin one-line adapter that closes over its own configuration.

NOTE: input paths point at the external measurement archive in the caller; the
reduced CSVs this produces are what the reproduction package ships.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

SUB_PROCESSED = "1_Processed_data"
# committed per-test time series (export_timeseries.py): used in place of the
# measurement archive when that archive is not present
TIMESERIES_DIR = Path(__file__).resolve().parent.parent / "results" / "measurement" / "timeseries"


def get_processed_file(base_path: Path, folder_id: str,
                       sub: str = SUB_PROCESSED) -> Path | None:
    """Return the ``*_processed.csv`` for a run folder, or ``None`` if absent.
    Without the archive (``base_path`` missing) the committed time series of the
    run is returned instead; ``read_processed`` maps it back to the same columns."""
    folder_path = Path(base_path) / folder_id / sub
    if folder_path.exists():
        found = list(folder_path.glob("*_processed.csv"))
        return found[0] if found else None
    if not Path(base_path).exists():
        f = TIMESERIES_DIR / f"{folder_id}.csv"
        return f if f.exists() else None
    return None


def list_runs(base_path: Path) -> list[str]:
    """Run folders of the archive, or the runs of the committed time series."""
    if Path(base_path).exists():
        return sorted(p.name for p in Path(base_path).iterdir() if p.is_dir())
    return sorted(pd.read_csv(TIMESERIES_DIR / "runs.csv")["run"])


def _committed(file_path: Path) -> bool:
    return Path(file_path).parent.resolve() == TIMESERIES_DIR.resolve()


def read_processed(file_path: Path) -> pd.DataFrame:
    """A processed run record with the consolidation's column names, read from the
    archive or from the committed time series (renamed back via channels.csv)."""
    if not _committed(file_path):
        return pd.read_csv(file_path, comment="#")
    # the committed values are the shortest round-trip repr of the doubles the
    # archive reader obtains, so read them back exactly
    df = pd.read_csv(file_path, float_precision="round_trip")
    ch = pd.read_csv(TIMESERIES_DIR / "channels.csv")
    names = ch[ch["run"] == Path(file_path).stem].set_index("column")["source_column"]
    df = df.rename(columns=names.to_dict())
    df["Time Absolute"] = df["Time Absolute"].str.replace("T", " ", regex=False)
    return df


def read_header(file_path: Path) -> tuple[float, float]:
    """(Burning_Duration, Start_ventilation) of a run record, in s."""
    if _committed(file_path):
        r = pd.read_csv(TIMESERIES_DIR / "runs.csv").set_index("run").loc[Path(file_path).stem]
        return float(r["burning_duration_s"]), float(r["ventilation_start_s"])
    b_dur, v_start = np.nan, np.nan
    with open(file_path, "r") as f:
        for line in f:
            if "Burning_Duration:" in line:
                m = re.search(r"Burning_Duration:\s*([\d.]+)", line)
                if m:
                    b_dur = float(m.group(1))
            if "Start_ventilation:" in line:
                m = re.search(r"Start_ventilation:\s*([\d.]+)", line)
                if m:
                    v_start = float(m.group(1))
    return b_dur, v_start


def load_runs(base_path: Path, selection_list: list[str],
              t_start: float, t_end: float, sub: str = SUB_PROCESSED):
    """Load processed runs, baseline-corrected at t=0, clipped to [t_start, t_end].

    Returns ``(loaded_data, durations, vent_times)`` where ``loaded_data`` maps
    run id -> DataFrame. Sensor columns (Temp/Extinction/Mass) are zeroed at the
    sample nearest t=0; ``durations``/``vent_times`` come from the CSV header
    (Burning_Duration / Start_ventilation). Identical logic to the former
    per-script ``load_data``.
    """
    loaded_data, durations, vent_times = {}, {}, {}
    for folder_id in selection_list:
        file_path = get_processed_file(base_path, folder_id, sub)
        if not file_path:
            continue
        try:
            b_dur, v_start = read_header(file_path)
            df = read_processed(file_path)
            df = df[(df["Time (s)"] >= t_start) & (df["Time (s)"] <= t_end)]
            idx0 = (df["Time (s)"] - 0).abs().idxmin()
            sensor_cols = [c for c in df.columns
                           if any(w in c for w in ["Temp", "Extinction", "Mass"])]
            df[sensor_cols] = df[sensor_cols] - df.loc[idx0, sensor_cols]
            loaded_data[folder_id] = df
            durations[folder_id] = b_dur
            vent_times[folder_id] = v_start
            print(f"  loaded: {folder_id}")
        except Exception as e:  # noqa: BLE001 - report and continue, as before
            print(f"  failed: {folder_id}: {e}")
    return loaded_data, durations, vent_times


def ensemble_stats(all_data: dict, t_start: float, t_end: float):
    """Ensemble mean and Bessel-corrected SD on a 1 s common grid.

    Returns ``(mean_df, std_df)`` (or ``(None, None)`` if empty). Identical logic
    to the former per-script ``calculate_stats``.
    """
    if not all_data:
        return None, None
    common_time = np.arange(t_start, t_end + 1, 1)
    all_series = []
    for df in all_data.values():
        df_interp = pd.DataFrame({"Time (s)": common_time})
        for col in df.columns:
            if col != "Time (s)":
                vals = pd.to_numeric(df[col], errors="coerce").values
                df_interp[col] = np.interp(common_time, df["Time (s)"].values, vals,
                                           left=np.nan, right=np.nan)
        all_series.append(df_interp)
    concat_df = pd.concat(all_series)
    return (concat_df.groupby("Time (s)").mean().reset_index(),
            concat_df.groupby("Time (s)").std(ddof=1).reset_index())


def widmann_norm_factor(lam_nm: float, lam_lem_nm: float = 638.0) -> float:
    """Widmann wavelength-normalization factor K_m(lam_lem)/K_m(lam).

    With K_m proportional to lambda^-1.0088 (Widmann 2003), the factor that maps an
    extinction coefficient measured at ``lam_nm`` onto the LEM reference
    wavelength ``lam_lem_nm`` is ``(lam_lem_nm / lam_nm) ** -1.0088``.
    """
    return (lam_lem_nm / lam_nm) ** -1.0088
