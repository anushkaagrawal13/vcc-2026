# vcc-2026

CPU-first experiments for the 2026 Virtual Cell Challenge. Start with a real
schema round-trip; only then build public-data pseudobulk models.

## Initial project plan

Build a reproducible, CPU-first pipeline that transfers CRISPRi responses across
cell lines. Establish a valid submission and an honest classical baseline before
spending time on more complex models. The primary scientific result is the
**Replogle K562 → RPE1 holdout**, with the leaderboard used as a sanity check.

### Week 0: contract and setup

- Read the official rules and 2026 scoring rubric end to end; record the schema,
  metrics, dates and submission limits in `docs/challenge-contract.md`.
- Register for the challenge, authenticate the VCC CLI, and download/checksum the
  validation files before designing model outputs.
- Join the challenge Discord for announcements (completion not yet verified).
- Set up GitHub, a pinned environment, and a phone-verified Kaggle account.
- Keep raw/processed data and credentials out of Git. Use one `config/*.yaml` per
  experiment; commit metrics, plots and provenance under `results/`.

### Build order and acceptance criteria

1. **Schema round-trip.** Generate the full zero-response count panel, validate
   and package it with the official CLI, submit it, and commit the returned score.
   Local format validation is not biological scoring: challenge responses are
   hidden. Finish this gate before implementing the modeling stages.
2. **Public-data pseudobulk.** Start with Replogle 2022. Compute mean expression
   deltas for each (cell line, perturbation) against matched non-targeting
   controls, preserving batch/guide provenance and documenting normalization.
   Save a tidy training table and retain held-out cells for DE evaluation.
3. **Three initial feature families.** Target-gene baseline expression in the
   destination line; target-gene mean expression across training lines; and
   GO/STRING neighbor-response priors calculated from training outcomes only.
   Begin with the first feature alone.
4. **Classical models.** Fit ridge per output gene, then LightGBM. Compare both
   with zero-delta and nearest-line baselines using identical splits and metrics.
   Add Adamson 2016 after the Replogle-only experiment works.
5. **Honest validation.** Train on K562 and evaluate on untouched RPE1. Select
   features and hyperparameters using K562-only folds. RPE1 baseline controls may
   inform destination-line features; RPE1 perturbation outcomes must not enter
   fitting, priors or tuning. Report shared-target and unseen-target cohorts,
   mean-response diagnostics and the official six-metric evaluation separately.
6. **Ablate and freeze.** Compare feature families, datasets and the count
   generator. Freeze the pipeline by mid-October. Reserve October 22–November 5
   for executing the finished pipeline on the test set and checking submissions.

**Assay policy:** Adamson 2016 and Replogle 2022 are CRISPRi. Norman 2019 is
CRISPRa and is excluded from the initial training set. Any later use requires an
explicit assay-type feature, a separate task and validation; never silently pool
activation and repression.

### Optional hybrid extension, after the classical baseline

Treat deep learning as a testable extension: add frozen gene/cell embeddings to
ridge or LightGBM, or fit a small residual model on top of the classical
prediction. Compare against the same untouched holdout and retain the extension
only if it improves the relevant metrics. Arc Virtual Cell Atlas is a candidate
source of representations or training data, subject to rule, license, assay and
leakage checks; using it is not yet an implemented or validated approach.

A separate count-generation adapter must turn predicted means into new raw-count
cells. After the multinomial null, evaluate a generator that also models
biological dispersion, since four rubric metrics depend on differential
expression. Improved mean predictions alone do not establish a better submission.

### First three working sessions

| Session | Deliverable |
|---|---|
| 1 | Registration/rubric review, scaffold, full zero-delta submission and recorded score |
| 2 | Replogle pseudobulk, one-feature ridge, K562 → RPE1 holdout and baseline comparisons |
| 3 | Adamson, remaining features, LightGBM and the first comparative results table |

These are ordered milestones, not claims that all three sessions are complete.

## Prepared cloud batch

See [the first-cloud-run checklist](docs/first-cloud-run.md) before launching.
`bash scripts/rehearse.sh` runs the synthetic round-trip and checkpoint tests.
On an approved EC2 host, `scripts/run-on-ec2.sh` sets a shutdown deadline, installs
the environment and runs the checkpointed download → generate → validate →
package batch. It stops on completion/failure; submission is a separate action.
No instance has been launched by these preparation steps.

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
The environment and lockfile pin the declared dependencies. Linux/Kaggle
installation has been verified with Python 3.12.2; platform-specific transitive
dependencies should be recorded when reproducing on another host.

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

## Current status and compute plan (September 22, 2026)

- Validation controls are downloaded, checksummed and inspected. The Kaggle
  environment passes **11 tests**; see `results/kaggle_setup.json`.
- Full-panel zero-delta generation now passes the real validation schema:
  360,000 cells, 18,533 genes, and 2,235,911,741 stored entries. The prediction
  checksum and input provenance are recorded in
  `results/000_zero_delta_validation.json`.
- Official packaging is still blocked on Kaggle: the measured peak estimate is
  61.2 GB (57.0 GiB), against a 30 GiB container memory limit. No `.vcc` package
  or submission was created. The controls bundle contains no perturbation
  ground truth, so it cannot produce a local biological score; the official
  score is returned by the challenge scorer after submission.
- AWS signup is complete. The requested Ohio standard On-Demand quota increase
  from 5 to **16 vCPUs is pending**. No project EC2 machine has been launched.
- Planned initial host: **128 GiB RAM, 200 GiB SSD, CPU only**, used intermittently
  for packaging and larger preprocessing jobs. Confirm the instance type, live
  regional price and spending limit before launching. Configure automatic stop
  and billing alerts; alerts are not a spending cap, and retained storage remains
  billable while compute is stopped.
- Keep Kaggle for lightweight experiments and optional GPU work. Notebooks clone
  the repo and call its modules; they do not contain the pipeline. Publish only
  permitted processed public-data tables as a Kaggle Dataset when ready.

The next concrete milestone is to package the validated null prediction on a
sufficiently large host, review it, and then submit it for the official score.
Reassess hosting
costs after measuring actual runtime and storage needs; this is an initial
project compute plan, not a commitment to an always-on server.

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

Kaggle account setup and phone verification are complete. Its tested notebook
is a thin setup/resource-check wrapper; full-panel packaging needs the larger
CPU host described above.

See [challenge notes](docs/challenge-contract.md), [data policy](docs/data-policy.md)
and [results](results/README.md).

## Prepared first cloud batch

See [the first-run runbook](docs/first-cloud-run.md) for the launch checklist,
boot-time shutdown timer, secure token entry, checkpoint recovery and artifact
export. Run `bash scripts/rehearse.sh` for the synthetic official-CLI round-trip.
`bash scripts/setup.sh` installs the pinned environment; `python -m src.run`
runs the checkpointed download/generate/validate/package pipeline.
The EC2-only `scripts/run-on-ec2.sh` adds automatic shutdown; never use it for
local rehearsal. Submission remains an explicit separate command.
