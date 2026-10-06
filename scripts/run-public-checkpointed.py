"""CloudShell supervisor: persist logs and verify each stage in S3 immediately."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone
import boto3

p=argparse.ArgumentParser()
p.add_argument('--bucket',required=True)
p.add_argument('--prefix',required=True)
a=p.parse_args()
root=Path(__file__).resolve().parents[1]
state_dir=Path.home()/'.vcc-cloud'
state_dir.mkdir(exist_ok=True)
s3=boto3.client('s3',region_name='us-east-2')
report={'status':'running','files':[],'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()}
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')

def publish_state(stage):
    report.update(stage=stage,updated_utc=datetime.now(timezone.utc).isoformat())
    raw=json.dumps(report,indent=2).encode()
    (state_dir/'public-run-state.json').write_bytes(raw)
    s3.put_object(Bucket=a.bucket,Key=a.prefix+'/run-state.json',Body=raw,ServerSideEncryption='AES256')

def run(command,stage):
    publish_state(stage)
    log=state_dir/('public-'+stage+'.log')
    with log.open('wb') as f:
        proc=subprocess.Popen(command,cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT)
        deadline=time.monotonic()+5400
        while proc.poll() is None:
            if time.monotonic()>deadline:
                proc.terminate();proc.wait(timeout=30);raise TimeoutError(stage)
            time.sleep(15)
            s3.upload_file(str(log),a.bucket,a.prefix+'/logs/'+log.name,ExtraArgs={'ServerSideEncryption':'AES256'})
    s3.upload_file(str(log),a.bucket,a.prefix+'/logs/'+log.name,ExtraArgs={'ServerSideEncryption':'AES256'})
    if proc.returncode:raise RuntimeError(f'{stage} failed with exit {proc.returncode}; see persisted log')

def backup(path):
    path=Path(path);relative=str(path.relative_to(root));key=a.prefix+'/'+relative
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(8<<20),b''):h.update(chunk)
    s3.upload_file(str(path),a.bucket,key,ExtraArgs={'ServerSideEncryption':'AES256'})
    remote=hashlib.sha256();body=s3.get_object(Bucket=a.bucket,Key=key)['Body']
    for chunk in iter(lambda:body.read(8<<20),b''):remote.update(chunk)
    body.close()
    if remote.hexdigest()!=h.hexdigest():raise ValueError('Backup mismatch '+relative)
    report['files']=[x for x in report['files'] if x['path']!=relative]+[dict(path=relative,bytes=path.stat().st_size,sha256=h.hexdigest())]
    publish_state('verified '+relative)

try:
    config='config/001_replogle_pseudobulk.yaml'
    for line in ['K562','RPE1']:
        code="from src.data.replogle import *; c=load_config('"+config+"'); s=next(s for s in c['sources'] if s['line']=='"+line+"'); download_one(s,ROOT/c['raw_dir']/(s['name']+'.gz'))"
        run(['.venv/bin/python','-c',code],line+'-download')
        pattern='K562*' if line=='K562' else 'rpe1*'
        for path in sorted((root/'data/raw/replogle_2022').glob(pattern)):
            if not path.name.endswith('.partial'):backup(path)
        run(['.venv/bin/python','-m','src.data.pseudobulk','--config',config,'--line',line],line+'-aggregate')
        for path in sorted((root/'data/processed/001_replogle_pseudobulk').glob(line+'*.parquet')):backup(path)
        backup(root/('results/001_replogle_pseudobulk/'+line+'_qc.json'))
    # Cohorts use metadata only; never inspect held-out expression for selection.
    code="""import pandas as pd,json
from pathlib import Path
p=Path('data/processed/001_replogle_pseudobulk');r=Path('results/001_replogle_pseudobulk')
a={line:set(pd.read_parquet(p/(line+'_matched_strata.parquet'),columns=['target_gene_id']).target_gene_id) for line in ['K562','RPE1']}
g={line:set(pd.read_parquet(p/(line+'_control_baseline.parquet'),columns=['output_gene_id']).output_gene_id) for line in ['K562','RPE1']}
c={'shared_target_ids':sorted(a['K562']&a['RPE1']),'RPE1_unseen_target_ids':sorted(a['RPE1']-a['K562']),'common_output_gene_ids':sorted(g['K562']&g['RPE1'])};c['counts']={k:len(v) for k,v in c.items()};(r/'cohorts.json').write_text(json.dumps(c,indent=2))
"""
    run(['.venv/bin/python','-c',code],'cohorts')
    backup(root/'results/001_replogle_pseudobulk/cohorts.json');backup(root/config)
    report.update(status='complete_backed_up',execution_environment='AWS CloudShell; no EC2 launched',verification='Every listed object read back and SHA-256 matched')
    publish_state('complete')
except Exception as exc:
    report.update(status='failed',error=str(exc));publish_state('failed');raise
