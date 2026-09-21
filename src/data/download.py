"""Download the authenticated controls bundle using the official checksum-aware CLI."""
import argparse
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from src.config import load_config
from src.schema import sha256


def download(cfg):
    destination = cfg['paths']['bundle']
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / 'controls.zip'
    cli = Path(sys.executable).parent / 'vcc'
    subprocess.run([str(cli), 'datasets', 'download', 'controls', '--output', str(archive)], check=True)
    names = ['gene_names.csv', 'pert_counts.csv', 'manifest.json'] + [
        f'context_{c}.h5ad' for c in cfg['schema']['contexts']]
    # Fixed allowlist: never extract arbitrary archive paths.
    with zipfile.ZipFile(archive) as bundle:
        if any(bundle.namelist().count(name) != 1 for name in names):
            raise ValueError('Bundle does not contain exactly one copy of each required file.')
        for name in names:
            target = destination / name
            with bundle.open(name) as source, target.with_suffix(target.suffix + '.partial').open('wb') as sink:
                shutil.copyfileobj(source, sink)
            target.with_suffix(target.suffix + '.partial').replace(target)
    provenance = {name: sha256(destination / name) for name in ['controls.zip', *names]}
    (destination / 'checksums.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print(f'Verified download and extracted {len(names)} files into {destination}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    download(load_config(parser.parse_args().config))
