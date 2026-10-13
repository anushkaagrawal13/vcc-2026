"""Batch-balanced K562 control calibration; no perturbation labels or RPE1 inputs."""
import argparse
import json
from pathlib import Path
import time

import numpy as np
from src.count_adapter import MeanCalibratedTransport

ROOT = Path(__file__).resolve().parents[1]


def split_controls(batches, fit_per_batch, calibration_per_batch, audit_per_batch, seed):
    batches = np.asarray(batches).astype(str)
    sizes = [fit_per_batch, calibration_per_batch, audit_per_batch]
    if batches.ndim != 1 or not len(batches) or any(not isinstance(n, int) or n < 2 for n in sizes):
        raise ValueError('Invalid split sizes or batches')
    result = [[], [], []]
    rng = np.random.default_rng(seed)
    for batch in sorted(set(batches)):
        indices = rng.permutation(np.flatnonzero(batches == batch))
        if len(indices) < sum(sizes):
            raise ValueError('Insufficient controls in batch ' + batch)
        start = 0
        for dest, n in zip(result, sizes):
            dest.extend(indices[start:start+n]); start += n
    return [np.asarray(x, dtype=np.int64) for x in result]


def balanced_donors(batches, cells_per_batch, seed):
    batches = np.asarray(batches).astype(str)
    if batches.ndim != 1 or not len(batches) or not isinstance(cells_per_batch, int) or cells_per_batch < 1:
        raise ValueError('Invalid donor design')
    rng = np.random.default_rng(seed)
    donors = np.concatenate([rng.choice(np.flatnonzero(batches == b), cells_per_batch, replace=True)
                             for b in sorted(set(batches))])
    rng.shuffle(donors)
    return donors


def distribution_metrics(counts, libraries, reference, reference_libraries, normalization):
    def moments(x, d):
        x = np.asarray(x, dtype=float); d = np.asarray(d, dtype=float)
        if (x.ndim != 2 or d.shape != (len(x),) or len(x) < 2
                or not np.isfinite(x).all() or not np.isfinite(d).all()
                or np.any(x < 0) or np.any(d <= 0) or np.any(x.sum(1) > d)):
            raise ValueError('Invalid counts/depth')
        log = np.log1p(x * normalization / d[:, None])
        return log.mean(0), log.var(0, ddof=1), (x == 0).mean(0)
    a = moments(counts, libraries); b = moments(reference, reference_libraries)
    if a[0].shape != b[0].shape:
        raise ValueError('Gene axis mismatch')
    return dict(mean_log_rmse=float(np.sqrt(np.mean((a[0]-b[0])**2))),
                variance_log_rmse=float(np.sqrt(np.mean((a[1]-b[1])**2))),
                dropout_mae=float(np.abs(a[2]-b[2]).mean()))


def select_candidate(rows):
    if not rows or any(not np.isfinite(r['mean_log_rmse']) for r in rows):
        raise ValueError('Missing or nonfinite calibration scores')
    names = sorted(set(r['candidate'] for r in rows))
    seeds = {name: [r['seed'] for r in rows if r['candidate'] == name] for name in names}
    if any(len(v) != len(set(v)) or sorted(v) != sorted(seeds[names[0]]) for v in seeds.values()):
        raise ValueError('Unbalanced candidate seed comparison')
    scores = {n: float(np.mean([r['mean_log_rmse'] for r in rows if r['candidate'] == n])) for n in names}
    return min(names, key=lambda n: (scores[n], n != 'legacy', n)), scores


def evaluate_candidates(fit, fit_libraries, fit_batches, calibration, calibration_libraries,
                        cfg, artifact, output):
    """Selection takes calibration controls only. Audit data are not accepted."""
    model = MeanCalibratedTransport(fit, fit_libraries, cfg['normalization'])
    zero = np.zeros(fit.shape[1]); states = {}; histories = {}; rows = []
    donors = balanced_donors(fit_batches, cfg['mc_cells_per_batch'], cfg['mc_seed'])
    for candidate in cfg['candidates']:
        name = candidate['name']; iterations = candidate['iterations']
        if iterations:
            state = model.calibrate(zero, iterations, len(donors), cfg['mc_seed'], donors,
                                    cfg['learning_rate'], cfg['maximum_step'], cfg['maximum_offset'])
            states[name] = state; histories[name] = state['qc']
            np.savez_compressed(artifact/(name+'_calibration.npz'),
                                **{k: state[k] for k in ['offset','requested_delta']})
        for seed in cfg['evaluation_seeds']:
            draw = balanced_donors(fit_batches, cfg['evaluation_cells_per_batch'], seed)
            if iterations:
                x, d, qc = model.generate_calibrated(states[name], len(draw), seed, draw)
            else:
                x, d, qc = model.generate(zero, len(draw), seed, draw)
            np.savez_compressed(artifact/f'{name}_seed_{seed}.npz', counts=x, libraries=d, donor_indices=draw)
            rows.append(dict(candidate=name, seed=seed, generator_qc=qc,
                             **distribution_metrics(x, d, calibration, calibration_libraries, cfg['normalization'])))
    winner, scores = select_candidate(rows)
    frozen = dict(selected=winner, selection_metric='mean_log_rmse averaged over declared seeds; lower is better',
                  selection_scores=scores, calibration_rows=rows, fit_histories=histories,
                  note='No audit controls or perturbation outcomes accepted by selection function')
    (output/'frozen_selection.json').write_text(json.dumps(frozen, indent=2, allow_nan=False)+'\n')
    return frozen


def run(config):
    # Heavy dependencies stay out of the small numerical unit tests.
    import yaml
    from importlib.metadata import version
    from src.data.pseudobulk import open_h5, column
    from src.transfer import digest
    import subprocess
    started = time.monotonic(); cfg = yaml.safe_load(Path(config).read_text())
    out = ROOT/cfg['results_dir']; art = ROOT/cfg['artifact_dir']
    if out.exists() and any(out.iterdir()):
        raise FileExistsError('Refusing to overwrite prior results; inspect/archive the attempted run')
    if art.exists() and any(art.iterdir()):
        raise FileExistsError('Refusing to overwrite prior artifacts')
    manifest = json.loads((ROOT/cfg['input_manifest']).read_text())
    record = next(x for x in manifest['files'] if x['path'] == cfg['raw'])
    if digest(ROOT/cfg['raw']) != record['sha256']:
        raise ValueError('Raw archive checksum mismatch')
    print('Verified K562 archive; selecting control-only splits', flush=True)
    with open_h5(ROOT/cfg['raw']) as f:
        symbols = column(f['obs'], 'gene').astype(str)
        batches = column(f['obs'], 'gem_group').astype(str)
        libraries = column(f['obs'], 'UMI_count').astype(float)
        control = np.flatnonzero(symbols == 'non-targeting')
        fit, calibration, audit = [control[ix] for ix in split_controls(batches[control],
            cfg['fit_per_batch'], cfg['calibration_per_batch'], cfg['audit_per_batch'], cfg['seed'])]
        genes = column(f['var'], f['var'].attrs['_index']).astype(str)
        if len(set(genes)) != len(genes):
            raise ValueError('Duplicate gene IDs')
        nb = len(set(batches[control]))
        if nb != cfg['expected_batches']:
            raise ValueError('Batch count differs from predeclared design')
        def read(indices):
            order = np.argsort(indices)
            x = np.empty((len(indices),len(genes)), dtype=np.int32)
            for start in range(0,len(order),128):
                ix = order[start:start+128]; block = f['X'][indices[ix],:]
                if (not np.isfinite(block).all() or np.any(block < 0)
                        or np.any(block != np.floor(block)) or np.any(block.sum(1) > libraries[indices[ix]])):
                    raise ValueError('Invalid raw counts')
                x[ix] = block
            return x
        fit_x = read(fit); cal_x = read(calibration)
        art.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
        selection = dict(fit_indices=fit.tolist(),calibration_indices=calibration.tolist(),audit_indices=audit.tolist(),
                         n_genes=len(genes),n_batches=nb,config_sha256=digest(config),raw=record,
                         fit_per_batch=cfg['fit_per_batch'],calibration_per_batch=cfg['calibration_per_batch'],audit_per_batch=cfg['audit_per_batch'])
        (art/'cell_selection.json').write_text(json.dumps(selection,indent=2)+'\n')
        frozen = evaluate_candidates(fit_x,libraries[fit],batches[fit],cal_x,libraries[calibration],cfg,art,out)
        frozen_hash = digest(out/'frozen_selection.json')
        print('Frozen selection: '+frozen['selected']+'; now reading audit cells',flush=True)
        audit_x = read(audit)
    np.savez_compressed(art/'reference_splits.npz',fit=fit_x,calibration=cal_x,audit=audit_x,
                        fit_libraries=libraries[fit],calibration_libraries=libraries[calibration],
                        audit_libraries=libraries[audit],fit_batches=batches[fit],output_gene_ids=genes)
    rows = []
    # Audit all predeclared candidates for transparency; the saved choice cannot change.
    for candidate in cfg['candidates']:
        for seed in cfg['evaluation_seeds']:
            with np.load(art/f"{candidate['name']}_seed_{seed}.npz") as generated:
                rows.append(dict(candidate=candidate['name'],seed=seed,
                    **distribution_metrics(generated['counts'],generated['libraries'],audit_x,libraries[audit],cfg['normalization'])))
    if digest(out/'frozen_selection.json') != frozen_hash:
        raise ValueError('Selection changed during audit')
    import resource, sys
    report = dict(status='complete',scope='K562 control-only null calibration, not perturbation prediction or official VCC scoring',
                  config_sha256=digest(config),raw=record,selected=frozen['selected'],selection_scores=frozen['selection_scores'],
                  frozen_selection_sha256=frozen_hash,audit_rows=rows,
                  fit_calibration_split_noise=distribution_metrics(fit_x,libraries[fit],cal_x,libraries[calibration],cfg['normalization']),
                  fit_audit_split_noise=distribution_metrics(fit_x,libraries[fit],audit_x,libraries[audit],cfg['normalization']),
                  n_genes=len(genes),n_batches=nb,n_fit=len(fit),n_calibration=len(calibration),n_audit=len(audit),
                  source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  versions={p:version(p) for p in ['numpy','h5py','indexed-gzip']},elapsed_seconds=time.monotonic()-started,
                  peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),
                  limitations=['Synthetic control transport adds sampling noise; mean correction cannot guarantee correct dispersion',
                               'One K562 control split and three generated seeds do not establish generalization',
                               'Candidate selection is provisional until K562 perturbation-fold evaluation; no RPE1 retuning'])
    (out/'metrics.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':'complete','selected':frozen['selected'],'selection_scores':frozen['selection_scores']}),flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True)
    run(parser.parse_args().config)
