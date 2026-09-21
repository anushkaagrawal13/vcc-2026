"""Conservative preflight for the official CLI's in-memory packaging path."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import h5py


def physical_memory_bytes():
    if sys.platform == 'darwin':
        return int(subprocess.check_output(['/usr/sbin/sysctl', '-n', 'hw.memsize'], text=True))
    return os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE')


def prep_resources(path, package=False):
    with h5py.File(path, 'r') as handle:
        matrix = handle['X']
        storage = sum(matrix[k].size * matrix[k].dtype.itemsize for k in ['data', 'indices', 'indptr'])
    # CLI validation/canonicalization/reordering may allocate additional copies.
    memory_needed = 3 * storage + 512 * 1024**2
    physical_memory = physical_memory_bytes()
    scratch_needed = storage + 2 * Path(path).stat().st_size if package else 0
    scratch_free = shutil.disk_usage(tempfile.gettempdir()).free
    return {'matrix_bytes': storage, 'estimated_memory_needed_bytes': memory_needed,
            'physical_memory_bytes': physical_memory,
            'estimated_scratch_needed_bytes': scratch_needed, 'scratch_free_bytes': scratch_free,
            'can_run': memory_needed < physical_memory * 0.8 and scratch_needed < scratch_free * 0.8}


def require_prep_resources(path, package=False):
    estimate = prep_resources(path, package)
    if not estimate['can_run']:
        gib = 1024**3
        raise RuntimeError(
            f"Official CLI preflight: estimated {estimate['estimated_memory_needed_bytes']/gib:.1f} GiB RAM "
            f"and {estimate['estimated_scratch_needed_bytes']/gib:.1f} GiB scratch; "
            f"host has {estimate['physical_memory_bytes']/gib:.1f} GiB total RAM and "
            f"{estimate['scratch_free_bytes']/gib:.1f} GiB free scratch. "
            'Run this config on a larger host; do not drop cells or genes to fit.')
    return estimate
