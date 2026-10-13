"""CPU-only CloudShell rehearsal, 45-minute hard limit and verified S3 export."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone
import boto3

root=Path(__file__).resolve().parents[1]
bucket='vcc-2026-artifacts-706098201643-us-east-2'
prefix='public/replogle_2022/005_count_rehearsal'
s3=boto3.client('s3',region_name='us-east-2')
log=Path.home()/'.vcc-cloud/count-rehearsal.log';log.parent.mkdir(exist_ok=True)
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',NUMBA_NUM_THREADS='1',POLARS_MAX_THREADS='1')
try:
    with log.open('wb') as f:
        subprocess.run(['.venv/bin/python','-m','pytest','-q'],cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
        subprocess.run(['.venv/bin/python','-m','src.count_rehearsal','--config','config/005_count_rehearsal.yaml'],cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=2700)
finally:
    s3.upload_file(str(log),bucket,prefix+'/logs/run.log',ExtraArgs={'ServerSideEncryption':'AES256'})
files=[p for folder in ['results/005_count_rehearsal','data/processed/005_count_rehearsal'] for p in (root/folder).rglob('*') if p.is_file()]+[root/'config/005_count_rehearsal.yaml']
report=dict(status='complete_backed_up',execution_environment='AWS CloudShell; no EC2 launched',files=[])
for p in files:
    h=hashlib.sha256(p.read_bytes()).hexdigest();key=prefix+'/'+str(p.relative_to(root))
    s3.upload_file(str(p),bucket,key,ExtraArgs={'ServerSideEncryption':'AES256'})
    body=s3.get_object(Bucket=bucket,Key=key)['Body'];remote=hashlib.sha256()
    for chunk in iter(lambda:body.read(8<<20),b''):remote.update(chunk)
    body.close()
    if remote.hexdigest()!=h:raise ValueError('Backup checksum mismatch')
    report['files'].append(dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=h))
report['completed_utc']=datetime.now(timezone.utc).isoformat()
b=json.dumps(report,indent=2).encode();(Path.home()/'.vcc-cloud/count-backup.json').write_bytes(b)
s3.put_object(Bucket=bucket,Key=prefix+'/backup_manifest.json',Body=b,ServerSideEncryption='AES256')
print(json.dumps({'status':report['status'],'artifact_count':len(files),'bytes':sum(x['bytes'] for x in report['files']),'manifest_sha256':hashlib.sha256(b).hexdigest()}),flush=True)
