"""Runtime monkeypatch for fdsreader 1.11.7 (data stage only).

fdsreader 1.11.7 strips ghost cells incorrectly for cell-centered 3D slices:
its ``SubSlice._load_data`` uses ``data[1:, 1:]``, which trims the ghost layer in
only the first two dimensions, so 3D slices come back one cell too large on the
third axis. ``patch_fdsreader_3d_cell_centered`` replaces the method at runtime
(the installed package is not modified on disk) with a version that strips the
ghost layer on all present axes and retries the read on transient I/O errors
(including silently short reads).

Only the data stage (re-extracting the reduced flow-field arrays and the
point-vs-path statistics from the FDS output tree) needs this; the committed
figure stage reads the cached npz files and never imports it. fdsreader 1.12.1
applies the same ghost-cell fix natively; an unpatched re-extraction with it
reproduces all fdsreader-derived outputs exactly.
"""
from __future__ import annotations

import numpy as np


def patch_fdsreader_3d_cell_centered() -> None:
    """Fix fdsreader 1.11.7 ghost-cell stripping for cell-centered 3D slices."""
    import os
    import time as _time

    import fdsreader.utils.fortran_data as fdtype
    from fdsreader.slcf.slice import SubSlice

    def _load_data(self, file_path: str, data_out: np.ndarray):
        n = self.dimension.size(cell_centered=False)
        dtype_data = fdtype.combine(fdtype.FLOAT, fdtype.new((("f", n),)))
        load_times = self.n_t == -1
        # The FDS output tree may live on a network share that intermittently
        # drops the session mid-read (OSError errno 22). Retry the whole slice
        # read with backoff -- the reopen also nudges the share to reconnect --
        # before giving up.
        for _attempt in range(8):
            try:
                if load_times:
                    self._parent_slice.n_t = (
                        os.stat(file_path).st_size - self._offset
                    ) // dtype_data.itemsize
                    self._parent_slice.times = np.empty(self.n_t)
                with open(file_path, "rb") as infile:
                    infile.seek(self._offset)
                    records = fdtype.read(infile, dtype_data, self.n_t)
                    # np.fromfile returns FEWER records, silently, when the share
                    # delivers a short read; the rest of data_out (np.empty) would
                    # then stay uninitialised. Treat that like a dropped session.
                    if len(records) != self.n_t:
                        raise OSError(f"short read: {len(records)} of {self.n_t} "
                                      f"frames from {os.path.basename(file_path)}")
                    for t, data in enumerate(records):
                        if load_times:
                            self.times[t] = data[0][0]
                        data = data[1].reshape(
                            self.dimension.shape(cell_centered=False), order="F"
                        )
                        if self.cell_centered:
                            data_out[t, :] = data[(slice(1, None),) * data.ndim]
                        else:
                            data_out[t, :] = data
                return
            except OSError:
                if _attempt == 7:
                    raise
                _time.sleep(min(30.0, 3.0 * (_attempt + 1)))

    SubSlice._load_data = _load_data
