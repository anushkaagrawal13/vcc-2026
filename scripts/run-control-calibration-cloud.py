"""Restore only K562, run a bounded CPU calibration, verify durable private backups.

Use system Python (boto3) in authenticated AWS CloudShell. No EC2 APIs or launches.
A parent process bounds the whole worker, including restore/test/export, to 45 min.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys

BUCKET='vcc-2026-artifacts-706098201643-us-east-2'
PREFIX='public/replogle_2022/006_k562_control_calibration'
EXPERIMENT='006_k562_control_calibration'
CONFIG='config/'+EXPERIMENT+'.yaml'
RAW='data/raw/replogle_2022/K562_essential_raw_singlecell_01.h5ad.gz'


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(8<<20),b''):h.update(chunk)
    return h.hexdigest()


def update(root):
    """Preserve identical untracked cloud reports before a fast-forward pull."""
    def git(*args):return subprocess.check_output(['git',*args],cwd=root)
    if git('remote','get-url','origin').decode().strip()!='https://github.com/anushkaagrawal13/vcc-2026.git':
        raise ValueError('Unexpected repository origin')
    if git('diff','--name-only') or git('diff','--cached','--name-only'):
        raise ValueError('Tracked edits present; refusing automatic update')
    subprocess.run(['git','fetch','origin','main'],cwd=root,check=True,timeout=120)
    untracked=set(git('ls-files','--others','--exclude-standard','-z').decode().split('\0'))
    incoming=set(git('ls-tree','-r','--name-only','-z','origin/main').decode().split('\0'))
    for name in sorted((untracked & incoming)-{''}):
        path=root/name
        if not name.startswith('results/') or path.read_bytes()!=git('show','origin/main:'+name):
            raise ValueError('Untracked collision differs from remote: '+name)
        destination=root/'work/006_preupdate'/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.exists():raise FileExistsError(destination)
        path.rename(destination)
    subprocess.run(['git','merge','--ff-only','origin/main'],cwd=root,check=True,timeout=120)


def worker(root, do_update):
    import boto3
    from botocore.config import Config
    s3=boto3.client('s3',region_name='us-east-2',config=Config(connect_timeout=10,read_timeout=60,retries={'max_attempts':3}))
    if do_update:update(root)
    out=root/'results'/EXPERIMENT;art=root/'data/processed'/EXPERIMENT
    if any(p.exists() and any(p.iterdir()) for p in [out,art]):
        raise FileExistsError('An experiment attempt already exists; inspect it before rerunning')
    python=root/'.venv/bin/python'
    if not python.is_file():raise FileNotFoundError('Cloud venv missing; run bash scripts/setup.sh first')
    manifest=json.loads((root/'results/001_replogle_pseudobulk/backup_manifest.json').read_text())
    record=next(r for r in manifest['files'] if r['path']==RAW)
    path=root/RAW
    reserve=1536*1024**2+(0 if path.exists() else record['bytes'])
    if shutil.disk_usage(root).free<reserve:
        raise RuntimeError(f'Need {reserve} bytes free before restore (includes 1.5 GiB headroom)')
    if not path.exists():
        path.parent.mkdir(parents=True,exist_ok=True)
        partial=path.with_suffix(path.suffix+'.partial')
        if partial.exists():raise FileExistsError('Partial download exists; inspect before retry')
        s3.download_file(BUCKET,'public/replogle_2022/001_replogle_pseudobulk/'+RAW,str(partial))
        if partial.stat().st_size!=record['bytes'] or digest(partial)!=record['sha256']:
            raise ValueError('Downloaded input checksum mismatch')
        partial.rename(path)
    if path.stat().st_size!=record['bytes'] or digest(path)!=record['sha256']:
        raise ValueError('Existing input checksum mismatch')
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',NUMBA_NUM_THREADS='1',POLARS_MAX_THREADS='1')
    # Check the packages this experiment uses against existing repository pins.
    check="import importlib.metadata as m,re,pathlib; pins=[s.split('==') for s in pathlib.Path('requirements.lock.txt').read_text().splitlines() if '==' in s]; wanted={'numpy','h5py','indexed-gzip','pyyaml','pandas','pyarrow','pytest','scipy'}; assert all(m.version(n)==v for n,v in pins if n.lower() in wanted), 'Pinned environment differs'"
    subprocess.run([str(python),'-c',check],cwd=root,env=env,check=True,timeout=60)
    subprocess.run([str(python),'-m','pytest','-q'],cwd=root,env=env,check=True,timeout=180)
    subprocess.run([str(python),'-m','src.control_calibration','--config',CONFIG],cwd=root,env=env,check=True,timeout=2100)
    files=[p for folder in [out,art] for p in folder.rglob('*') if p.is_file()]+[root/CONFIG,root/'requirements.lock.txt']
    report=dict(status='complete_backed_up',execution_environment='AWS CloudShell CPU; no EC2 launched',files=[])
    for p in files:
        h=digest(p);key=PREFIX+'/'+str(p.relative_to(root))
        s3.upload_file(str(p),BUCKET,key,ExtraArgs={'ServerSideEncryption':'AES256'})
        body=s3.get_object(Bucket=BUCKET,Key=key)['Body'];remote=hashlib.sha256()
        try:
            for chunk in iter(lambda:body.read(8<<20),b''):remote.update(chunk)
        finally:body.close()
        if remote.hexdigest()!=h:raise ValueError('Backup hash mismatch: '+key)
        report['files'].append(dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=h))
    report['completed_utc']=datetime.now(timezone.utc).isoformat()
    payload=json.dumps(report,indent=2).encode()
    s3.put_object(Bucket=BUCKET,Key=PREFIX+'/backup_manifest.json',Body=payload,ServerSideEncryption='AES256')
    if s3.get_object(Bucket=BUCKET,Key=PREFIX+'/backup_manifest.json')['Body'].read()!=payload:
        raise ValueError('Manifest read-back mismatch')
    (out/'backup_manifest.json').write_bytes(payload)
    print(json.dumps({'status':report['status'],'artifact_count':len(files),
                      'artifact_bytes':sum(x['bytes'] for x in report['files']),
                      'manifest_sha256':hashlib.sha256(payload).hexdigest()}),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--update',action='store_true');parser.add_argument('--worker',action='store_true')
    args=parser.parse_args();root=args.repo.resolve()
    if args.worker:
        worker(root,args.update);return
    # This lock guards concurrent runs even during input restoration.
    lock=root/'work/006_run.lock';lock.parent.mkdir(parents=True,exist_ok=True)
    import fcntl
    with lock.open('w') as lockfile:
        fcntl.flock(lockfile,fcntl.LOCK_EX|fcntl.LOCK_NB)
        logs=Path.home()/'.vcc-cloud';logs.mkdir(exist_ok=True)
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        log=logs/f'control-calibration-{stamp}.log'
        command=[sys.executable,str(Path(__file__).resolve()),'--repo',str(root),'--worker']
        if args.update:command.append('--update')
        with log.open('wb') as stream:
            process=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            try:code=process.wait(timeout=2700)
            except (subprocess.TimeoutExpired,KeyboardInterrupt):
                os.killpg(process.pid,signal.SIGTERM)
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid,signal.SIGKILL);process.wait()
                code=124
        print(log.read_text()[-12000:])
        # Log export is a separate short process so a network stall cannot leave a worker running.
        export="import boto3,sys; from botocore.config import Config; boto3.client('s3',region_name='us-east-2',config=Config(connect_timeout=5,read_timeout=15,retries={'max_attempts':1})).upload_file(sys.argv[1],sys.argv[2],sys.argv[3],ExtraArgs={'ServerSideEncryption':'AES256'})"
        try:subprocess.run([sys.executable,'-c',export,str(log),BUCKET,PREFIX+'/logs/'+log.name],check=True,timeout=60)
        except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
            print('Log export failed; local log retained:',log,type(exc).__name__)
        print('Exit',code,'Log',log,flush=True)
        raise SystemExit(code)


if __name__=='__main__':main()
