"""
Re-run the FireTest measurement consolidation WITHOUT the 1800 s time clip,
to capture the full post-ventilation record
(needed to read the true fouling plateau and to see late cleaning events).

Only changed from the original consolidation:
  - csv_x_max  1800 -> 3600   (extended T_END to expose the post-ventilation tail)
  - input read from the measurement root (MEAS_ROOT), OUTPUT written locally only
  - all heptane runs enabled (075 / 150 / 220)

SAFETY: never writes into the input tree. A guard aborts if an output path would
resolve inside it. Read-only w.r.t. the raw input tree.
"""
import pandas as pd
import numpy as np
import io
import re
import json
import warnings
from pathlib import Path

import paths as P

warnings.filterwarnings("ignore", category=RuntimeWarning)

# --- paths: read from the measurement root (env-overridable via paths.py),
# write locally --------------------------------------------------------------
INPUT_BASE = P.MEAS_ROOT
OUTPUT_BASE = Path(__file__).resolve().parent.parent / "data" / "reprocessed"
SUB_RAW, SUB_PROCESSED = "0_Raw_data", "1_Processed_data"
metadata_file = INPUT_BASE / "experiment_metadata.txt"

# all heptane runs (075 / 150 / 220)
versuche_dict = {
    "Heptane | 220 mm | 300 g | S1 | R1": "Hep_220_S1_R1",
    "Heptane | 220 mm | 300 g | S1 | R2": "Hep_220_S1_R2",
    "Heptane | 220 mm | 300 g | S1 | R3": "Hep_220_S1_R3",
    "Heptane | 220 mm | 300 g | S1 | R4": "Hep_220_S1_R4",
    "Heptane | 160 mm | 150 g | S1 | R1": "Hep_160_S1_R1",
    "Heptane | 160 mm | 150 g | S1 | R2": "Hep_160_S1_R2",
    "Heptane | 160 mm | 150 g | S1 | R3": "Hep_160_S1_R3",
    "Heptane | 160 mm | 75 g | S2 | R1": "Hep_160_S2_R1",
    "Heptane | 160 mm | 75 g | S2 | R2": "Hep_160_S2_R2",
    "Heptane | 160 mm | 75 g | S2 | R3": "Hep_160_S2_R3",
    "Heptane | 160 mm | 75 g | S3 | R1": "Hep_160_S3_R1",
    "Heptane | 160 mm | 75 g | S3 | R2": "Hep_160_S3_R2",
    "Heptane | 160 mm | 75 g | S4 | R1": "Hep_160_S4_R1",
    "Heptane | 160 mm | 75 g | S4 | R2": "Hep_160_S4_R2",
}

rm_threshold = 1.0
csv_x_min, csv_x_max = -60, 3600          # <-- un-clipped (was -60, 1800)
LEM_PATH_LENGTH_M, SICK_PATH_LENGTH_M = 0.81, 1.6

quantities_dict = {
    "Plume Impingement Temperature (°C)": "Temperaturstatistik 1 s/Temp. Decke über Brandherd/AVE/1s (°C)",
    "Mass (kg)": "Temperaturstatistik 1 s/Waage/AVE/1s (kg)",
    "Transm. LEM 1 (%)": "Transmission LEM1/LEM1/Transmission (%)",
    "Transm. LEM 2 (%)": "Transmission LEM2/LEM2/Transmission (%)",
    "Transm. LEM 3 (%)": "Transmission LEM3/LEM3/Transmission (%)",
    "Transm. LEM 4 (%)": "Transmission LEM4 APD/LEM4 APD/Transmission (%)",
    "Transm. SICK IR (%)": "Temperaturstatistik 1 s/SICK IR/AVE/1s (%)",
    "Smoke Detector 1 (V)": "Statistik 3/Rauchmelder 1/AVE/1s (V)",
    "Smoke Detector 2 (V)": "Statistik 3/Rauchmelder 2/AVE/1s (V)",
    "Smoke Detector 3 (V)": "Statistik 3/Rauchmelder 3/AVE/1s (V)",
    "Temp Tree 1_0.6 (°C)": "Temperaturstatistik 1 s/Messbaum 1_0 6/AVE/1s (°C)",
    "Temp Tree 1_1.2 (°C)": "Temperaturstatistik 1 s/Messbaum 1_1 2/AVE/1s (°C)",
    "Temp Tree 1_1.6 (°C)": "Temperaturstatistik 1 s/Messbaum 1_1 6/AVE/1s (°C)",
    "Temp Tree 1_1.8 (°C)": "Temperaturstatistik 1 s/Messbaum 1_1 8/AVE/1s (°C)",
    "Temp Tree 1_2.0 (°C)": "Temperaturstatistik 1 s/Messbaum 1_2 0/AVE/1s (°C)",
    "Temp Tree 1_2.2 (°C)": "Temperaturstatistik 1 s/Messbaum 1_2 2/AVE/1s (°C)",
    "Temp Tree 1_2.4 (°C)": "Temperaturstatistik 1 s/Messbaum 1_2 4/AVE/1s (°C)",
    "Temp Tree 1_2.5 (°C)": "Temperaturstatistik 1 s/Messbaum 1_2 5/AVE/1s (°C)",
    "Temp Tree 2_0.6 (°C)": "Temperaturstatistik 1 s/Messbaum 2_0 6/AVE/1s (°C)",
    "Temp Tree 2_1.2 (°C)": "Temperaturstatistik 1 s/Messbaum 2_1 2/AVE/1s (°C)",
    "Temp Tree 2_1.6 (°C)": "Temperaturstatistik 1 s/Messbaum 2_1 6/AVE/1s (°C)",
    "Temp Tree 2_1.8 (°C)": "Temperaturstatistik 1 s/Messbaum 2_1 8/AVE/1s (°C)",
    "Temp Tree 2_2.0 (°C)": "Temperaturstatistik 1 s/Messbaum 2_2 0/AVE/1s (°C)",
    "Temp Tree 2_2.2 (°C)": "Temperaturstatistik 1 s/Messbaum 2_2 2/AVE/1s (°C)",
    "Temp Tree 2_2.4 (°C)": "Temperaturstatistik 1 s/Messbaum 2_2 4/AVE/1s (°C)",
    "Temp Tree 2_2.5 (°C)": "Temperaturstatistik 1 s/Messbaum 2_2 5/AVE/1s (°C)",
}


# ---- functions copied verbatim from the notebook ---------------------------
def calculate_derived_metrics(df, label):
    factor_soot = (638 / 880) ** -1.0088
    is_sooty = any(x in label.lower() for x in ["isoprop", "hep", "poly", "pur"])
    for col in [c for c in df.columns if "Transm." in c]:
        L = SICK_PATH_LENGTH_M if "SICK" in col else LEM_PATH_LENGTH_M
        new_c = col.replace("Transm.", "Extinction").replace("(%)", "(1/m)")
        data_series = df[col].iloc[:, 0] if isinstance(df[col], pd.DataFrame) else df[col]
        df[new_c] = (-np.log((data_series / 100.0).clip(lower=1e-5)) / L).clip(lower=0)
        if "SICK" in col and is_sooty:
            df[new_c + "_corr"] = df[new_c] * factor_soot
    for col in [c for c in df.columns if "Smoke Detector" in c and "(V)" in c]:
        det_data = df[col].iloc[:, 0] if isinstance(df[col], pd.DataFrame) else df[col]
        df[col.replace("(V)", "(Binary)")] = (det_data > rm_threshold).astype(int)
    return df


def apply_dynamic_sensor_naming(df, config):
    if not config:
        return df
    rename_map = {}
    for pos, sensors in config.items():
        if sensors in [None, "none", "null"]:
            continue
        if isinstance(sensors, str):
            sensors = [sensors]
        for s_id in sensors:
            variants = [s_id.replace('_', ' '), s_id.replace('_', ''), s_id]
            for clean_id in variants:
                for col in df.columns:
                    if clean_id in col and col not in rename_map.values():
                        rename_map[col] = col.replace(clean_id, f"{s_id}_{pos}")
    return df.rename(columns=rename_map).loc[:, ~df.columns.duplicated()].copy()


def load_and_process(file_path, cols_map, trigger, start_abs=None):
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
    s_idx = next(i for i, l in enumerate(lines) if "Time (-)" in l)
    t0 = pd.to_datetime(start_abs) if start_abs is not None else None
    if t0 is None:
        for line in lines:
            parts = line.strip().split('\t')
            if len(parts) >= 4 and any(t in parts[3].lower() for t in trigger):
                t0 = pd.to_datetime(parts[2], format='%d.%m.%Y %H:%M:%S.%f', errors='coerce')
                break
    df = pd.read_csv(io.StringIO("".join(lines[s_idx + 1:])),
                     names=lines[s_idx].strip().split(','), sep=',', decimal='.')
    df['Time Absolute'] = pd.to_datetime(df[df.columns[0]], format='%d.%m.%Y %H:%M:%S.%f', errors='coerce')
    df = df.dropna(subset=['Time Absolute'])
    t0 = t0 if t0 else df['Time Absolute'].iloc[0]
    df['Time (s)'] = (df['Time Absolute'] - t0).dt.total_seconds().round(0).astype(int)
    rename_dict = {long: short for short, long in cols_map.items() if long in df.columns}
    return df[['Time (s)', 'Time Absolute'] + list(rename_dict.keys())].rename(columns=rename_dict)


def load_mb2_bottom(file_path):
    f_path = Path(file_path)
    if f_path.suffix.lower() == ".csv":
        df = pd.read_csv(f_path, sep=';', decimal=',', encoding='latin-1')
        df['Time Absolute'] = pd.to_datetime(df['Uhrzeit_korrigiert'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
        c_map = {'0 6': 'Temp Tree 2_0.6 (°C)', '1 2': 'Temp Tree 2_1.2 (°C)', '1 6': 'Temp Tree 2_1.6 (°C)', '1 8': 'Temp Tree 2_1.8 (°C)'}
        df.rename(columns={c: v for c in df.columns for k, v in c_map.items() if k in c}, inplace=True)
    else:
        df = pd.read_csv(f_path, sep='\t', decimal=',', header=None,
                         names=['Datum', 'Zeit', 'Temp Tree 2_0.6 (°C)', 'Temp Tree 2_1.2 (°C)',
                                'Temp Tree 2_1.6 (°C)', 'Temp Tree 2_1.8 (°C)'], encoding='latin-1')
        df['Time Absolute'] = pd.to_datetime(df['Datum'] + ' ' + df['Zeit'], format='%d.%m.%Y %H:%M:%S', errors='coerce')
    return df[[c for c in df.columns if "Temp Tree" in c or c == 'Time Absolute']]


def main():
    # safety: never write into the (read-only) input tree
    assert not OUTPUT_BASE.resolve().is_relative_to(INPUT_BASE.resolve()), \
        f"OUTPUT_BASE inside the input tree refused: {OUTPUT_BASE}"
    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

    if not metadata_file.exists():
        print(f"Metadata file {metadata_file} missing!")
        return

    meta_df = pd.read_csv(metadata_file, sep=';', encoding='utf-8')
    meta_df["Start_abs"] = pd.to_datetime(meta_df["Date"] + " " + meta_df["Start_time"], format="%Y-%m-%d %H:%M:%S", errors="coerce")

    def parse_cfg(val):
        try:
            return json.loads(str(val).replace('none', 'null'))
        except Exception:
            return {}
    meta_dict = {row["ID"]: {**row, "Sensor_Config": parse_cfg(row.get("Sensor_Config", "{}"))}
                 for _, row in meta_df.iterrows()}

    for label, folder in versuche_dict.items():
        p_raw = INPUT_BASE / folder / SUB_RAW
        if not p_raw.exists():
            print(f"(skip) raw missing: {p_raw}")
            continue
        meta = meta_dict.get(folder)
        start_abs = meta["Start_abs"] if meta else None
        files = list(p_raw.glob("Messung*.txt"))
        if not files:
            print(f"(skip) no Messung*.txt in {folder}")
            continue

        df = load_and_process(files[0], quantities_dict, ["zündung"], start_abs)
        if meta and meta["Sensor_Config"]:
            df = apply_dynamic_sensor_naming(df, meta["Sensor_Config"])

        f_mb2 = next(p_raw.glob("*final_manuell.csv"), next(p_raw.glob("25*.txt"), None))
        if f_mb2:
            try:
                df_mb2 = load_mb2_bottom(f_mb2).sort_values('Time Absolute')
                df = pd.merge_asof(df.sort_values('Time Absolute'), df_mb2, on='Time Absolute', direction='nearest', tolerance=pd.Timedelta('1s'))
                df = df.loc[:, ~df.columns.duplicated()].copy()
            except Exception as e:
                print(f"MB2 merge error in {folder}: {e}")

        if df is None:
            continue
        df = calculate_derived_metrics(df, label)

        prio = ['Time (s)', 'Time Absolute', 'Mass (kg)', 'Plume Impingement Temperature (°C)']
        trees = sorted([c for c in df.columns if "Temp Tree" in c])
        transms = sorted([c for c in df.columns if "Transm." in c])
        exts = sorted([c for c in df.columns if "Extinction" in c])
        detect = sorted([c for c in df.columns if "(Binary)" in c])
        to_exclude = [c for c in df.columns if "Smoke Detector" in c and "(V)" in c]
        rest = [c for c in df.columns if c not in (prio + trees + transms + exts + detect + to_exclude)]
        final_cols = [c for c in (prio + trees + transms + exts + detect + rest) if c in df.columns]
        df = df[final_cols]

        df = df[(df['Time (s)'] >= csv_x_min) & (df['Time (s)'] <= csv_x_max)]

        blacklist_config = {
            "Hep_160_S1_R3": ["Transm. SICK_F2_2.3 IR (%)", "Extinction SICK_F2_2.3 IR (1/m)", "Extinction SICK_F2_2.3 IR (1/m)_corr"],
            "Hep_220_S1_R1": ["Transm. LEM_4_F1_2.3 (%)", "Extinction LEM_4_F1_2.3 (1/m)", "Transm. SICK_F2_2.3 IR (%)", "Extinction SICK_F2_2.3 IR (1/m)", "Extinction SICK_F2_2.3 IR (1/m)_corr"],
            "Hep_220_S1_R2": ["Transm. SICK_F2_2.3 IR (%)", "Extinction SICK_F2_2.3 IR (1/m)", "Extinction SICK_F2_2.3 IR (1/m)_corr"],
            "Hep_220_S1_R3": ["Transm. SICK_F2_2.3 IR (%)", "Extinction SICK_F2_2.3 IR (1/m)", "Extinction SICK_F2_2.3 IR (1/m)_corr"],
            "Hep_220_S1_R4": ["Transm. LEM_4_F1_2.3 (%)", "Extinction LEM_4_F1_2.3 (1/m)", "Transm. SICK_F2_2.3 IR (%)", "Extinction SICK_F2_2.3 IR (1/m)", "Extinction SICK_F2_2.3 IR (1/m)_corr"],
        }
        if folder in blacklist_config:
            for col in blacklist_config[folder]:
                if col in df.columns:
                    df[col] = np.nan
                    ext_col = col.replace("Transm.", "Extinction").replace("(%)", "(1/m)")
                    if ext_col in df.columns:
                        df[ext_col] = np.nan

        p_proc = OUTPUT_BASE / folder / SUB_PROCESSED
        assert not p_proc.resolve().is_relative_to(INPUT_BASE.resolve()), \
            f"refusing write into the input tree: {p_proc}"
        p_proc.mkdir(parents=True, exist_ok=True)
        csv_path = p_proc / f"{folder}_processed.csv"
        with open(csv_path, 'w', encoding='utf-8-sig') as f:
            f.write(f"# Experiment: {label}\n")
            if meta:
                for key, value in meta.items():
                    if key not in ("Sensor_Config", "Start_abs"):
                        f.write(f"# {key}: {value}\n")
            f.write("# " + "-" * 50 + "\n")
            df.to_csv(f, index=False, lineterminator='\n')
        print(f"Exported (local): {folder}  ->  t in [{df['Time (s)'].min():.0f}, {df['Time (s)'].max():.0f}] s")


if __name__ == "__main__":
    main()
