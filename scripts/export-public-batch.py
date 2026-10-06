"""Run with AWS's system Python (boto3), after the public batch completes.

No credential material is written. Every object is checked by streaming a
read-back SHA-256. Source single cells stay private in the project bucket.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone

import boto3

p = argparse.ArgumentParser()
p.add_argument('--bucket', required=True)
p.add_argument('--prefix', required=True)
p.add_argument('--wait-seconds', type=int, default=7200)
args = p.parse_args()
root = Path(__file__).resolve().parents[1]
reports = root / 'results/001_replogle_pseudobulk'
deadline = time.monotonic() + args.wait_seconds
while not (all((reports / (line + '_qc.json')).exists() for line in ['K562', 'RPE1']) and (reports / 'cohorts.json').exists()):
    if time.monotonic() >= deadline:
        raise TimeoutError('Public batch did not finish before export deadline')
    time.sleep(20)
s3 = boto3.client('s3', region_name='us-east-2')
files = []
for directory in ['data/raw/replogle_2022', 'data/processed/001_replogle_pseudobulk', 'results/001_replogle_pseudobulk']:
    files.extend(path for path in (root / directory).glob('*') if path.is_file() and not path.name.endswith('.partial'))
files.append(root / 'config/001_replogle_pseudobulk.yaml')
verified = []
for path in sorted(files):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8 << 20), b''):
            h.update(chunk)
    relative = str(path.relative_to(root))
    key = args.prefix.rstrip('/') + '/' + relative
    s3.upload_file(str(path), args.bucket, key, ExtraArgs={'ServerSideEncryption': 'AES256'})
    remote = hashlib.sha256()
    body = s3.get_object(Bucket=args.bucket, Key=key)['Body']
    for chunk in iter(lambda: body.read(8 << 20), b''):
        remote.update(chunk)
    body.close()
    if remote.hexdigest() != h.hexdigest():
        raise ValueError('Backup digest mismatch: ' + relative)
    verified.append({'path': relative, 'bytes': path.stat().st_size, 'sha256': h.hexdigest()})
    print(json.dumps({'verified': relative, 'bytes': path.stat().st_size}), flush=True)
record = {'status': 'complete_backed_up', 'source_commit': subprocess.check_output(['git','rev-parse','HEAD'], cwd=root, text=True).strip(),
          'completed_utc': datetime.now(timezone.utc).isoformat(), 'execution_environment': 'AWS CloudShell; no EC2 instance launched',
          'bucket': args.bucket, 'prefix': args.prefix, 'verification': 'every object read back and SHA-256 matched', 'files': verified}
output = reports / 'backup.json'
output.write_text(json.dumps(record, indent=2) + '\n')
s3.upload_file(str(output), args.bucket, args.prefix.rstrip('/') + '/results/001_replogle_pseudobulk/backup.json', ExtraArgs={'ServerSideEncryption':'AES256'})
print('BACKUP_COMPLETE', flush=True)
