"""Conservative preflight for the official CLI's in-memory packaging path."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import h5py
from vcc.sizing import prep_peak_gib


def physical_memory_bytes():
    if sys.platform == 'darwin':
        return int(subprocess.check_output(['/usr/sbin/sysctl', '-n', 'hw.memsize'], text=True))
    return os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE')


def memory_limit_bytes():
    """Respect container limits as well as the physical host's memory."""
    limits = [physical_memory_bytes()]
    for name in ('/sys/fs/cgroup/memory.max',
                 '/sys/fs/cgroup/memory/memory.limit_in_bytes'):
        try:
            value = Path(name).read_text().strip()
            if value != 'max' and int(value) > 0:
                limits.append(int(value))
        except (OSError, ValueError):
            pass
    return min(limits)


def prep_resources(path, package=False):
    with h5py.File(path, 'r') as handle:
        matrix = handle['X']
        storage = sum(matrix[k].size * matrix[k].dtype.itemsize for k in ['data', 'indices', 'indptr'])
        nnz = matrix['data'].size
        casts = matrix['data'].dtype.name != 'float32'
    # CLI validation/canonicalization/reordering may allocate additional copies.
    memory_needed = max(3 * storage + 512 * 1024**2,
                        int(prep_peak_gib(nnz, casts=casts) * 1024**3))
    physical_memory = memory_limit_bytes()
    scratch_needed = storage + 2 * Path(path).stat().st_size if package else 0
    scratch_free = shutil.disk_usage(tempfile.gettempdir()).free
    return {'matrix_bytes': storage, 'estimated_memory_needed_bytes': memory_needed,
            'physical_memory_bytes': physical_memory_bytes(),
            'effective_memory_limit_bytes': physical_memory,
            'estimated_scratch_needed_bytes': scratch_needed, 'scratch_free_bytes': scratch_free,
            'can_run': memory_needed < physical_memory * 0.8 and scratch_needed < scratch_free * 0.8}


def require_prep_resources(path, package=False):
    estimate = prep_resources(path, package)
    if not estimate['can_run']:
        gib = 1024**3
        raise RuntimeError(
            f"Official CLI preflight: estimated {estimate['estimated_memory_needed_bytes']/gib:.1f} GiB RAM "
            f"and {estimate['estimated_scratch_needed_bytes']/gib:.1f} GiB scratch; "
            f"host has {estimate['effective_memory_limit_bytes']/gib:.1f} GiB effective RAM and "
            f"{estimate['scratch_free_bytes']/gib:.1f} GiB free scratch. "
            'Run this config on a larger host; do not drop cells or genes to fit.')
    return estimate
