"""Experiment paths are relative to the repository, never the caller's cwd."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_config(path):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    with path.open() as stream:
        cfg = yaml.safe_load(stream)
    if cfg['assay_type'] != 'CRISPRi':
        raise ValueError('This experiment supports CRISPRi only; do not pool CRISPRa.')
    if cfg['model'] != 'multinomial_control_null':
        raise ValueError('Only the Session 1 null model is implemented.')
    expected = {'validation': ['A', 'B', 'C'], 'test': ['D', 'E', 'F']}
    if cfg['schema']['contexts'] != expected[cfg['phase']]:
        raise ValueError('Context labels do not match the experiment phase.')
    cfg['paths'] = {key: ROOT / value for key, value in cfg['paths'].items()}
    cfg['_config_path'] = path
    return cfg
