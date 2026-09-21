# vcc-2026

CPU-first experiments for the 2026 Virtual Cell Challenge. Start with a real
schema round-trip; only then build public-data pseudobulk models.

## Start here

The repo is open in VS Code. A local `.venv` contains Python 3.12.2 and the
official `vcc-cli==0.2.1`; activate it before running CLI commands:

```bash
source .venv/bin/activate
vcc --version
make test
```

To recreate elsewhere, use `conda env create -f environment.yml`, activate
`vcc-2026`, and run Make with `PYTHON=python`. Alternatively create a Python
3.12.2 virtual environment and `pip install -r requirements.lock.txt`.
Every dependency, including transitive packages, is pinned. The environment was
tested on macOS; Linux/Kaggle installation remains to be verified.

## Session 1 workflow

```bash
vcc login                 # hidden API-key prompt; OS keychain, never git/chat
vcc whoami
make download            # official CLI download + checksum + allowlisted extraction
make predict             # config/000_zero_delta.yaml
make validate            # official vcc prep --dry-run, no score or upload
make package             # official vcc prep -> prediction.vcc
vcc submit data/processed/000_zero_delta/prediction.vcc \
  -m '000_zero_delta: multinomial control null' --wait
# Save returned entry id, partition, panel, anchors, and all six scores in results/.
```

`CONFIG=config/<experiment>.yaml` selects an experiment. Paths are always relative
to this repository. Predictions and reports are not overwritten: use a new
experiment/config for a new run. Downloads are resumable through the official CLI.

The baseline fits each context's pooled control gene probabilities and draws NEW
multinomial cells at 20,000 counts per cell. It predicts no perturbation response
in expectation on the normalized expression scale. It does not copy or relabel
experimental cells. Finite draws are not exactly zero delta, and multinomial
variance is an intentionally weak approximation of biological variation.

Only count-generation chunks are in memory; the output is streamed to a sparse
H5AD. The official packaging CLI can still require substantial memory and disk.
Raw data, processed matrices, secrets and environments are gitignored. Summaries,
plots, configurations and provenance in `results/` are versioned.

`make validate` and `make package` first estimate the official CLI's memory and
scratch requirements. They refuse an undersized host with a concrete estimate.
The current Mac has 8 GiB RAM and little free disk, so full official prep may
require a larger CPU machine even though streaming generation works locally.
Keep the full cell/gene panel when moving the run; do not shrink the experiment
to get a locally convenient but invalid submission.

Current run: the validation controls are downloaded and inspected; all 10 tests
pass. Full generation was stopped when disk space fell below 1 GiB, and its
incomplete output was removed. There is no real submission or leaderboard score
yet. Generation now estimates disk needs before writing. The redundant download
zip was removed after verifying the extracted raw files; `make download` can
retrieve it again if needed.

## Architecture and build gates

| Stage | Modules | Artifact / exit condition |
|---|---|---|
| 1. Contract | `src/data/download.py`, `src/schema.py` | Checksummed controls, manifest, exact gene/perturbation axes |
| 1. Null prediction | `src/models/baseline.py`, `src/predict.py` | Sparse raw-count H5AD, official `.vcc` package, first returned score |
| 2. Public data | `src/data/pseudobulk.py` | Tidy matched-control deltas plus preserved single cells |
| 2. First model | `src/features.py`, `src/models/ridge.py` | K562-trained / RPE1-held-out ridge on one feature |
| 3. Expansion | `src/models/gbm.py` | Adamson + remaining features + LightGBM, same validation split |
| 4. Freeze | configs + results | Ablations and final pipeline frozen by mid-October |

Later-stage modules intentionally contain design contracts, not working models.
Do not mistake them for implemented training or evaluation. Nearest-line remains
a planned Session 2 comparator. Notebooks are for exploration, never the pipeline.

## What the official schema changes

The submission is **single-cell raw counts**, not a delta CSV: 360,000 cells ×
18,533 ordered genes, with 400 cells for each of 300 targets in A/B/C. The model's
internal pseudobulk deltas therefore require a separate count-generation adapter.
Four scored metrics involve differential expression, so keeping only means loses
information needed to evaluate the complete rubric.

Validation responses are hidden. `make validate` checks format locally; it is
not a local leaderboard score. Public K562→RPE1 validation will use the official
`cell-eval2` vcc2026 preset against retained held-out cells. Report raw diagnostics
separately from any locally reference-scaled scores; neither is the hidden
challenge score. Zero-delta is also **not** the rubric's mean-perturbation-response
zero-score anchor.

## Next sessions

1. Finish the real null upload and record its returned score before modeling.
2. Download the smaller Replogle K562/RPE1 panels first (about 9.9/8.1 GB), inspect
   their count layers and guide/batch annotations, then pseudobulk with matched
   controls. Define the expression scale explicitly. Keep RPE1 perturbation
   outcomes out of feature fitting, priors, scaling and hyperparameter selection.
3. Fit ridge on K562 using target-gene baseline expression. Freeze choices on
   K562-only folds; report shared-target and unseen-target RPE1 cohorts, zero-delta
   and nearest-line comparators. This is a transfer estimate for that pair, not a
   guarantee for the three anonymous challenge contexts.
4. Add Adamson CRISPRi, training-line expression and training-only GO/STRING priors;
   compare LightGBM on exactly the same holdout. Exclude Norman 2019 CRISPRa unless
   implementing and validating a separate assay task.
5. Ablate and freeze by mid-October. Test data arrive October 22; the final deadline
   is November 5, 2026, 23:59 UTC. Only the last final submission counts for prizes.

Kaggle is optional for this CPU-first starting point. Account setup/phone
verification is still a user action. Later upload only processed public-data
tables as a Kaggle Dataset; use a thin notebook that imports this repository.

See [challenge notes](docs/challenge-contract.md), [data policy](docs/data-policy.md)
and [results](results/README.md).
