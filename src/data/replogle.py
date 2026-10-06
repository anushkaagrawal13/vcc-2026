"""Pinned Replogle source downloads, losslessly compressed during transfer."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import urllib.request

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load_config(path):
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    cfg = yaml.safe_load(p.read_text())
    if cfg['assay_type'] != 'CRISPRi':
        raise ValueError('This adapter supports only Replogle CRISPRi.')
    cfg['_sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
    return cfg


def download_one(source, destination):
    """Hash original bytes, preserve them in gzip; never stage the dense original."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    receipt = destination.with_suffix(destination.suffix + '.json')
    if destination.exists():
        if not receipt.exists():
            raise ValueError('Archive without receipt: inspect before replacing')
        result = json.loads(receipt.read_text())
        if result['source'] != source:
            raise ValueError('Source differs from existing archive receipt')
        h = hashlib.sha256()
        with destination.open('rb') as f:
            for chunk in iter(lambda: f.read(8 << 20), b''):
                h.update(chunk)
        if h.hexdigest() != result['archive_sha256']:
            raise ValueError('Existing archive checksum mismatch')
        return result
    partial = destination.with_suffix(destination.suffix + '.partial')
    md5, sha, size = hashlib.md5(), hashlib.sha256(), 0
    with urllib.request.urlopen(source['url'], timeout=120) as response:
        with partial.open('wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, compresslevel=1, mtime=0) as out:
            while chunk := response.read(8 << 20):
                md5.update(chunk)
                sha.update(chunk)
                size += len(chunk)
                out.write(chunk)
                if size // (1 << 30) != (size - len(chunk)) // (1 << 30):
                    print(json.dumps({'event': 'download', 'line': source['line'], 'bytes': size}), flush=True)
    if size != source['bytes']:
        raise ValueError(f'Download size mismatch: {size}')
    if source.get('md5') and md5.hexdigest() != source['md5']:
        raise ValueError('Published source MD5 mismatch')
    os.replace(partial, destination)
    h = hashlib.sha256()
    with destination.open('rb') as f:
        for chunk in iter(lambda: f.read(8 << 20), b''):
            h.update(chunk)
    result = {'source': source, 'raw_bytes': size, 'raw_sha256': sha.hexdigest(),
              'raw_md5': md5.hexdigest(), 'published_md5_verified': bool(source.get('md5')),
              'archive_bytes': destination.stat().st_size, 'archive_sha256': h.hexdigest()}
    receipt.write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--config', required=True)
    args = p.parse_args()
    cfg = load_config(args.config)
    reports = []
    for source in cfg['sources']:
        reports.append(download_one(source, ROOT / cfg['raw_dir'] / (source['name'] + '.gz')))
    out = ROOT / cfg['results_dir']
    out.mkdir(parents=True, exist_ok=True)
    (out / 'downloads.json').write_text(json.dumps({'config_sha256': cfg['_sha256'], 'files': reports}, indent=2) + '\n')


if __name__ == '__main__':
    main()
