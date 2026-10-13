"""Audit GEO metadata without guessing controls or loading expression matrices."""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import yaml

ROOT=Path(__file__).resolve().parents[2]


def run(config):
    cfg=yaml.safe_load(Path(config).read_text());raw=ROOT/cfg['raw_dir'];out=ROOT/cfg['results_dir']
    raw.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
    panels=[];receipts=[]
    for source in cfg['sources']:
        decoded={}
        for suffix in ['cell_identities.csv.gz','barcodes.tsv.gz','genes.tsv.gz']:
            name=source['prefix']+'_'+suffix;p=raw/name
            url=f"https://ftp.ncbi.nlm.nih.gov/geo/samples/GSM2406nnn/{source['sample']}/suppl/{name}"
            if not p.exists():
                with urllib.request.urlopen(url,timeout=60) as response:p.write_bytes(response.read())
            b=p.read_bytes();receipts.append(dict(url=url,path=str(p.relative_to(ROOT)),bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
            decoded[suffix]=gzip.decompress(b).decode()
        rows=list(csv.DictReader(io.StringIO(decoded['cell_identities.csv.gz'])))
        barcodes=decoded['barcodes.tsv.gz'].splitlines();barset=set(barcodes)
        genes=[s.split('\t') for s in decoded['genes.tsv.gz'].splitlines()]
        nbc=Counter(r['cell BC'] for r in rows)
        good=[r for r in rows if r['good coverage'].upper()=='TRUE' and float(r['number of cells'])==1 and nbc[r['cell BC']]==1 and r['cell BC'] in barset]
        candidates=defaultdict(Counter)
        for r in good:
            if r['guide identity'] in cfg['candidate_upr_controls']:
                candidates[r['cell BC'].rsplit('-',1)[-1]][r['guide identity']]+=1
        panels.append(dict(**source,identity_rows=len(rows),expression_barcodes=len(barcodes),
                           unique_expression_barcodes=len(barset),genes=len(genes),unique_gene_ids=len({g[0] for g in genes}),
                           unique_gene_symbols=len({g[1] for g in genes}),guide_identities=dict(sorted(Counter(r['guide identity'] for r in rows).items())),
                           good_coverage=dict(Counter(r['good coverage'] for r in rows)),
                           number_of_cells=dict(Counter(r['number of cells'] for r in rows)),
                           identity_barcodes_absent_from_matrix=sum(r['cell BC'] not in barset for r in rows),
                           expression_barcodes_without_identity=len(barset-set(nbc)),duplicate_identity_barcodes=sum(v>1 for v in nbc.values()),
                           conservative_eligible_assignment_rows=len(good),
                           conservative_filter='good coverage TRUE, number of cells == 1, unique assignment barcode, barcode in expression matrix',
                           candidate_control_rows_by_gem={k:dict(v) for k,v in sorted(candidates.items())}))
    report=dict(status='metadata_audit_complete_pooling_blocked',assay_type=cfg['assay_type'],line=cfg['line'],
                panels=panels,sources=receipts,pooling_decision=cfg['pooling_decision'],
                blocking_items=['Primary guide-table confirmation of UPR non-targeting controls','UPR condition/time metadata confirmation','Expression matrix integer/count and matched-control QC before training'],
                notes=['Epistasis panel contains combinations and DMSO/tunicamycin/thapsigargin; excluded',
                       'Guide identity UMI count is guide capture support, not RNA library size',
                       'No Adamson cells have been pooled into Replogle models; Norman CRISPRa remains excluded'],
                primary_analysis='https://github.com/thomasmaxwellnorman/perturbseq_demo/blob/master/perturbseq_demo.ipynb')
    (out/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'panels':[{k:p[k] for k in ['panel','identity_rows','conservative_eligible_assignment_rows']} for p in panels]}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);run(p.parse_args().config)
