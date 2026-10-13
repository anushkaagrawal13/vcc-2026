"""Versioned human STRING graph; exact Ensembl gene aliases, no symbol guessing."""
import gzip
import json
import urllib.request
from collections import defaultdict
from pathlib import Path
import numpy as np
from src.transfer import digest


def download(cfg, root):
    raw=root/cfg['raw_dir'];raw.mkdir(parents=True,exist_ok=True)
    receipts=[]
    for source in cfg['sources']:
        path=raw/source['name'];receipt=path.with_suffix(path.suffix+'.json')
        if path.exists():
            if not receipt.exists() or digest(path)!=json.loads(receipt.read_text())['sha256']:
                raise ValueError('Existing annotation archive lacks a matching receipt')
        else:
            tmp=path.with_suffix(path.suffix+'.partial')
            with urllib.request.urlopen(source['url'],timeout=120) as response, tmp.open('wb') as f:
                while chunk:=response.read(1<<20):f.write(chunk)
            if tmp.stat().st_size!=source['bytes']:raise ValueError('STRING source size changed')
            tmp.rename(path)
            record={**source,'sha256':digest(path),'license':'CC-BY-4.0','version':'12.0',
                    'checksum_type':'Computed SHA-256; no publisher hash supplied'}
            receipt.write_text(json.dumps(record,indent=2)+'\n')
        receipts.append(json.loads(receipt.read_text()))
    return receipts


def build_graph(raw, ids, threshold):
    wanted=set(ids); candidates=defaultdict(set)
    with gzip.open(raw/'9606.protein.aliases.v12.0.txt.gz','rt') as f:
        for line in f:
            if line.startswith('#'):continue
            fields=line.rstrip('\n').split('\t')
            if len(fields)>=3 and fields[1].startswith('ENSG') and len(fields[1])==15:
                candidates[fields[0]].add(fields[1])
    mapping={protein:next(iter(genes)) for protein,genes in candidates.items() if len(genes)==1 and next(iter(genes)) in wanted}
    index={gene:i for i,gene in enumerate(ids)}
    w=np.zeros((len(ids),len(ids)),dtype=np.float32)
    with gzip.open(raw/'9606.protein.links.v12.0.txt.gz','rt') as f:
        next(f)
        for line in f:
            p,q,score=line.split();score=int(score)
            if score<threshold or p not in mapping or q not in mapping:continue
            i,j=index[mapping[p]],index[mapping[q]]
            if i!=j:w[i,j]=w[j,i]=max(w[i,j],score/1000)
    return w,dict(targets=len(ids),mapped_targets=len(set(mapping.values())),
                  ambiguous_proteins_skipped=sum(len(g)>1 for g in candidates.values()),
                  undirected_edges=int(np.count_nonzero(w)//2),isolated_targets=int((w.sum(axis=1)==0).sum()),
                  score_threshold=threshold, self_edges_removed=True,
                  isoform_edge_reduction='maximum score per undirected gene pair')
