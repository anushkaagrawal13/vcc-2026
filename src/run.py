"""Checkpointed, non-submitting baseline batch runner."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024**2), b''):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def fingerprints(paths):
    return {str(p): sha256(p) for p in paths}


def stage(state, state_path, name, outputs, action):
    """Skip only completed stages whose artifacts still match their hashes."""
    previous = state['stages'].get(name)
    if previous:
        if any(not p.is_file() for p in outputs) or fingerprints(outputs) != previous['sha256']:
            raise RuntimeError(f'{name}: saved artifact missing/changed; inspect before resuming')
        print(f'{name}: verified checkpoint', flush=True)
        return
    print(f'{name}: starting', flush=True)
    action()
    state['stages'][name] = {'sha256': fingerprints(outputs),
                             'completed_utc': datetime.now(timezone.utc).isoformat()}
    write_json(state_path, state)


def run(cfg):
    from src.data.download import download
    from src.evaluate import prep_command
    from src.predict import generate
    from src.resources import memory_limit_bytes, require_prep_resources
    os.chdir(ROOT)
    # Preserve one immutable source/config identity across resume attempts.
    commit = subprocess.check_output(['git', '-c', 'core.fsmonitor=false', 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-c', 'core.fsmonitor=false', 'status', '--porcelain', '--untracked-files=normal'], text=True)
    # Runtime reports under results/ are expected; source/config edits are not.
    if any(not line[3:].startswith('results/') for line in dirty.splitlines()):
        raise RuntimeError('Commit source/config changes and remove unrelated untracked files before running')
    paths = cfg['paths']
    paths['prediction'].parent.mkdir(parents=True, exist_ok=True)
    paths['report'].parent.mkdir(parents=True, exist_ok=True)
    scratch = paths['prediction'].parent / 'scratch'
    scratch.mkdir(exist_ok=True)
    os.environ['TMPDIR'] = str(scratch)
    import tempfile
    tempfile.tempdir = str(scratch)
    # Full-panel admission check before downloading/generating. Detailed check
    # against actual nnz is performed again before official packaging.
    full_panel = cfg['schema']['n_genes'] > 1000
    if full_panel and (memory_limit_bytes() < 96 * 1024**3 or shutil.disk_usage(scratch).free < 100 * 1024**3):
        raise RuntimeError('Full-panel batch requires >=96 GiB effective RAM and >=100 GiB free disk')
    state_path = paths['prediction'].parent / 'run-state.json'
    identity = {'commit': commit, 'config_sha256': sha256(cfg['_config_path'])}
    with (paths['prediction'].parent / '.run.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = json.loads(state_path.read_text()) if state_path.exists() else {**identity, 'stages': {}}
        if any(state[k] != v for k, v in identity.items()):
            raise RuntimeError('Checkpoint source/config differs; use a new experiment directory')
        subprocess.run([sys.executable, '-m', 'pip', 'check'], check=True)
        subprocess.run([sys.executable, '-m', 'pytest', '-q'], check=True)
        # Export exact host dependency versions; contains no authentication data.
        freeze = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True)
        (paths['report'].parent / f"{cfg['experiment']}_environment.txt").write_text(freeze)
        names = ['gene_names.csv', 'pert_counts.csv', 'manifest.json'] + [f'context_{c}.h5ad' for c in cfg['schema']['contexts']]
        inputs = [paths['bundle'] / name for name in names]
        stage(state, state_path, 'download', inputs, lambda: download(cfg))
        def prediction():
            if paths['prediction'].exists() or paths['report'].exists():
                raise RuntimeError('Uncheckpointed prediction/report exists; inspect it before retrying')
            generate(cfg)
        stage(state, state_path, 'predict', [paths['prediction'], paths['report']], prediction)
        def validate():
            estimate = require_prep_resources(paths['prediction'], package=True)
            subprocess.run(prep_command(cfg), check=True)
            write_json(paths['prediction'].parent / 'preflight.json', estimate)
        stage(state, state_path, 'validate', [paths['prediction'].parent / 'preflight.json'], validate)
        def package():
            if paths['submission'].exists():
                raise RuntimeError('Uncheckpointed package exists; inspect it before retrying')
            require_prep_resources(paths['prediction'], package=True)
            subprocess.run(prep_command(cfg, package=True), check=True)
        stage(state, state_path, 'package', [paths['submission']], package)
        summary = {**identity, 'status': 'packaged_not_submitted', 'official_score': None,
                   'submission_sha256': sha256(paths['submission']),
                   'stages': list(state['stages'])}
        write_json(paths['report'].parent / f"{cfg['experiment']}_batch.json", summary)
        print('Package ready. Submission is a separate, explicit action.', flush=True)


if __name__ == '__main__':
    from src.config import load_config
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='config/000_zero_delta.yaml')
    run(load_config(parser.parse_args().config))
