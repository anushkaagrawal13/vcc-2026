"""Bounded CloudShell experiment and verified durable export. Run with system Python."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone
import boto3

root=Path(__file__).resolve().parents[1]
bucket='vcc-2026-artifacts-706098201643-us-east-2'
prefix='public/replogle_2022/003_string_models'
s3=boto3.client('s3',region_name='us-east-2')
log=Path.home()/'.vcc-cloud/rich-run.log'
log.parent.mkdir(exist_ok=True)
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
try:
    with log.open('wb') as f:
        subprocess.run(['.venv/bin/python','-m','pytest','-q'],cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
        subprocess.run(['.venv/bin/python','-m','src.rich_transfer','--config','config/003_string_models.yaml'],cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=1800)
finally:
    s3.upload_file(str(log),bucket,prefix+'/logs/rich-run.log',ExtraArgs={'ServerSideEncryption':'AES256'})
files=list((root/'results/003_string_models').glob('*'))+list((root/'data/processed/003_string_models').glob('*'))+list((root/'data/raw/string_v12').glob('*.gz*'))+[root/'config/003_string_models.yaml']
report={'status':'complete_backed_up','files':[],'execution_environment':'AWS CloudShell; no EC2 launched'}
for p in files:
    h=hashlib.sha256(p.read_bytes()).hexdigest()
    key=prefix+'/'+str(p.relative_to(root))
    s3.upload_file(str(p),bucket,key,ExtraArgs={'ServerSideEncryption':'AES256'})
    body=s3.get_object(Bucket=bucket,Key=key)['Body']; remote=hashlib.sha256()
    for chunk in iter(lambda:body.read(8<<20),b''):remote.update(chunk)
    body.close()
    assert remote.hexdigest()==h, key
    report['files'].append({'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':h})
report['completed_utc']=datetime.now(timezone.utc).isoformat()
b=json.dumps(report,indent=2).encode()
(Path.home()/'.vcc-cloud/rich-backup.json').write_bytes(b)
s3.put_object(Bucket=bucket,Key=prefix+'/backup_manifest.json',Body=b,ServerSideEncryption='AES256')
print(json.dumps(report),flush=True)
