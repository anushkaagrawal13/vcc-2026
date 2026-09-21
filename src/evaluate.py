"""Session 1: official upload validation/packaging, not a biological score.

Session 2 will call cell-eval2 with vcc2026 preset on PUBLIC held-out single cells,
adding real controls as required by its scoring contract. Raw metric diagnostics
and reference-scaled scores must be separate artifacts. Challenge ground truth
and its reference bundles are withheld; never manufacture a local official score.
"""
import argparse
import subprocess
import sys
from pathlib import Path

from src.config import load_config
from src.resources import require_prep_resources


def prep_command(cfg, package=False):
    p, s = cfg['paths'], cfg['schema']
    command = [str(Path(sys.executable).parent / 'vcc'), 'prep', str(p['prediction']),
               '-g', str(p['bundle'] / 'gene_names.csv'),
               '--perts', str(p['bundle'] / 'pert_counts.csv'),
               '--contexts', ','.join(s['contexts']),
               '--expected-gene-dim', str(s['n_genes']),
               '--cells-per-pert', str(s['cells_per_perturbation']),
               '--max-nnz', str(s['max_stored_entries']),
               '--max-counts-per-cell', str(s['max_counts_per_cell']),
               '-o', str(p['submission'])]
    if not package:
        command.append('--dry-run')
    return command


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--package', action='store_true')
    args = parser.parse_args()
    cfg = load_config(args.config)
    require_prep_resources(cfg['paths']['prediction'], args.package)
    subprocess.run(prep_command(cfg, args.package), check=True)
