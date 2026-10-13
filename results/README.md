# Experiment record

Track metrics tables, small plots, configs and provenance in git; keep matrices in
gitignored `data/`. Never label synthetic tests or local schema checks as a
challenge score.

| Experiment | Data | Status | Official score |
|---|---|---|---|
| Synthetic schema fixture | 3 genes, 2 targets, A/B/C, 4 cells each | Official CLI packaging test passed | Not applicable |
| `000_zero_delta` | Official `vcc2026-val-1` controls | Submitted as `Axby4yc5z8rw49HHPjz7`; compute terminated and working disk deleted | −0.03350 (published) |
| K562 → RPE1 ridge | Public Replogle | Deferred until Session 1 completes | Not applicable |

For each real experiment commit its config, seed, git revision, input hashes,
package/scorer versions, raw/scaled metric distinction, per-context metrics,
cohort coverage, runtime and memory where measured. Official results also require
entry ID, partition, panel and anchor bundle identifiers.

On October 6, all 14 Linux rehearsal tests passed and the full EC2 pipeline
completed. It generated 360,000 cells across 18,533 genes, passed official CLI
validation, and produced a 3.86-GB `.vcc` package. The prediction SHA-256 exactly
matches the earlier Kaggle result. All nine exported files were verified against
their source SHA-256 hashes. See `first_cloud_batch_2026-10-06.json` and
`000_zero_delta_batch.json`. Upload succeeded with server MD5 verification;
`000_zero_delta_submission.json` records the published entry and all six metrics.
Overall: **−0.0334974**, rank **974** at retrieval.
EC2 termination and deletion of the attached 200 GiB disk were verified; the
private S3 backup is retained.

`000_zero_delta_status.json` records an earlier local disk failure, and
`000_zero_delta_validation.json` records the earlier Kaggle generation run;
these are historical evidence rather than the current batch status.

The verified preflight estimates **18.8 GiB free disk for generation alone**,
conservatively allowing for uncompressed sparse storage. Packaging needs additional
scratch and several copies of that matrix in RAM. The measured packaging
estimate was 57.0 GiB RAM and 26.1 GiB scratch. The successful host used 128 GiB
RAM and 200 GiB gp3; the full-panel runner requires at least 96 GiB effective RAM
and 100 GiB free disk before starting.

## Official null baseline (October 6)

| Metric | Raw | Reference-scaled |
|---|---:|---:|
| PDS | 0.498246 | −0.003927 |
| MSE | 1.027118 | 0.000000 |
| LFC NMAE | 1.008885 | −0.012605 |
| Direction fidelity | 0.465276 | −0.158275 |
| Direction reach | 0.059642 | −0.021876 |
| Significant-DE Jaccard | 0.028796 | −0.004302 |

These are the API's published aggregate values, not local estimates. The null
model has no target-specific biological signal. Its weakest scaled metric is
direction fidelity, supporting evaluation of count-distribution calibration as
well as mean deltas in later experiments. A negative overall score is compatible
with this baseline: the rubric's zero anchor is a mean-perturbation-response
model, not this control-only multinomial model.

## Replogle pseudobulks — completed October 6

Step 2 is complete. Both original raw-count sources passed their publisher MD5
checks; compressed originals preserve single-cell data for later DE evaluation.
Matched-control tidy tables were generated separately for K562 and RPE1.

| Line / role | Cells | Controls | Target groups | Output genes | Tidy rows | Aggregation seconds | Peak RSS GiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| K562 / train | 310,385 | 10,691 | 2,057 | 8,563 | 17,614,091 | 173.2 | 1.44 |
| RPE1 / held out | 247,914 | 11,485 | 2,393 | 8,749 | 20,936,357 | 132.4 | 1.53 |

Aggregation timing excludes download, Parquet writing and backup. Targets retain
at least 5 cells in K562 and 2 in RPE1; no extra cell-count filter was imposed.
The 48 K562 and 56 RPE1 gem groups each had at least 116 and 119 matched control
cells, respectively. Deltas use mean per-cell `log1p(10000 * count / total_UMI)`
and target-cell-weighted matched-gem controls; raw-count means/deltas are also
retained. Neither line is pooled with the other or with CRISPRa data.

Metadata-only evaluation cohorts contain **2,055 shared targets**, **335 unseen
RPE1 targets**, and **7,226 common output genes**. RPE1's NEDD8-MDP1 (51 cells),
PRSS50 (150), and RBM14-RBM4 (257) have missing source Ensembl IDs. They remain
separate `UNMAPPED:<symbol>` targets in the table and are excluded from the
Ensembl-ID overlap cohorts. Do not silently map or merge them during modeling.

All **14 artifacts / 5,811,970,524 bytes** are backed up under:

```text
s3://vcc-2026-artifacts-706098201643-us-east-2/public/replogle_2022/001_replogle_pseudobulk/
```

Every listed object was read back and SHA-256 verified. The final manifest was
retrieved from S3 after CloudShell reconnected, and both committed QC reports
match its hashes. See `001_replogle_pseudobulk/backup_manifest.json`, `status.json`,
`K562_qc.json`, `RPE1_qc.json`, and `cohort_summary.json`. The full cohort lists
are in the checksummed S3 artifact. Raw data and processed Parquets remain
excluded from git. Restore commands are in `docs/data-policy.md`.

**20 tests passed** in the pinned Linux environment, including missing-ID
preservation, unequal-batch control matching, chunk/gzip invariance and invalid
input rejection. This run used CloudShell; no EC2 instance or EBS disk was
created. S3 storage and requests remain billable. No model has been trained yet.

The initial interrupted attempt is preserved in
`001_replogle_pseudobulk/attempt1_status.json`. Its missing outputs prompted
per-source/per-line verified checkpoints. The successful rerun also caught and
fixed the three missing-ID targets before resuming from verified artifacts.

Next: restore the processed tables, freeze modeling choices on K562-only folds,
and evaluate one-feature ridge plus zero-delta/nearest-line baselines on the
separate shared-target and unseen-target RPE1 cohorts. These descriptive tables
are not a single-cell rubric score.

## K562 → RPE1 ridge transfer — October 12

**First cross-line estimate:** ridge MSE **0.0104594**, versus zero-delta
**0.0113142** (7.56% reduction) and training-mean **0.0104506** (7.63% reduction).
**Ridge does not beat the training-mean baseline.** These are public pseudobulk
diagnostics, not the official VCC rubric or a leaderboard score.

| Model | All mapped MSE | Shared-target MSE | Unseen-target MSE |
|---|---:|---:|---:|
| Zero delta | 0.0113142 | 0.0118283 | 0.0081605 |
| K562 mean response | 0.0104506 | 0.0109048 | 0.0076647 |
| One-feature ridge | 0.0104594 | 0.0109114 | 0.0076867 |
| Same-target K562 / mean fallback | 0.0114233 | 0.0120361 | 0.0076647 |

The evaluation includes 2,390 mapped RPE1 targets: 2,055 shared and 335 unseen,
over 7,226 common output genes. The same-target transfer comparator has only one
source line available; unseen targets explicitly fall back to the K562 mean.
The three unmapped targets are excluded from this gene-ID-based experiment.

Ridge alpha **10** was selected using five seeded K562-only target folds.
Each fold fits its own median imputer and standardizer. The target basal-expression
feature is missing for 189 K562 targets and 283 RPE1 targets; these are imputed
using training statistics, not dropped or treated as measured zero expression.
All settings and predictions were frozen before RPE1 outcomes were loaded.

**24 tests passed** in pinned Linux. Six inputs matched experiment 001 hashes.
The run took **95.6 seconds**, peaked at **1.64 GiB RSS**, and ran in CloudShell
without EC2. Six output artifacts (~133 MB) passed S3 SHA-256 read-back checks.
See `002_ridge_transfer/metrics.json`, `metrics.csv`, `backup_manifest.json`, and
`status.json`. Full fold/axis metadata, coefficients and predictions are retained
under `public/replogle_2022/002_ridge_transfer/` in the existing private S3 bucket.

Interpretation: a generic K562 response transfers better than this one-feature
model or unscaled same-target copying by MSE. This does not establish why, nor
prove that richer features will help. Do not tune on these RPE1 outcomes.

Next: predeclare K562-only model comparisons, add training-only biological
features and audit Adamson CRISPRi before pooling. Compare richer ridge and
LightGBM against the training-mean baseline; pursue single-cell count generation
and official metric calibration as a separate experiment. Any further RPE1
evaluation is repeated use of this holdout and must be disclosed.

## STRING priors + ridge / LightGBM — October 12

**K562-selected LightGBM is best overall among the predeclared families:** RPE1
MSE **0.0102680**, 1.75% below the mean-response baseline and 9.25% below zero
delta. However, it is **4.63% worse than the mean baseline on unseen targets**.
The gain is concentrated in shared targets; this is not uniform improvement in
zero-shot generalization. These remain repeated public pseudobulk diagnostics,
not the official single-cell rubric.

| Model | K562 CV MSE | RPE1 all MSE | Shared MSE | Unseen MSE |
|---|---:|---:|---:|---:|---:|
| Zero delta | — | 0.0113142 | 0.0118283 | 0.0081605 |
| K562 mean | 0.0035433 | 0.0104506 | 0.0109048 | 0.0076647 |
| Basal-only low-rank ridge | 0.0034536 | 0.0104343 | 0.0108746 | 0.0077336 |
| STRING low-rank ridge | 0.0030401 | 0.0103949 | 0.0107431 | 0.0082590 |
| STRING low-rank LightGBM | 0.0028579 | 0.0102680 | 0.0106346 | 0.0080193 |

Five K562-only folds selected alpha 1 for basal ridge, alpha 100 for STRING
ridge, and 15 leaves for LightGBM (60 rounds). LightGBM improved CV MSE 19.34%
over the mean baseline. All richer models predict 16 fold-local response
components and reconstruct gene-level deltas. The basal ablation includes a
missingness indicator and low-rank output; it is not identical to experiment 002.

STRING v12.0 maps 2,390 of 2,392 unique panel targets, with 48,627 undirected
gene pairs at combined score >=700 and 237 isolated targets. Twelve ambiguous
protein mappings were discarded. Neighbor response priors exclude self and
contain only training-fold labels; basis fitting, imputation and standardization
are also fold-local. Isolated targets use the training-mean response prior.
The single training-line expression mean duplicates K562 basal expression and
was not added as an independent feature. Adamson remains a separate data audit.

All settings and predictions were frozen before RPE1 outcomes were read.
The overall model is selected by K562 CV; do not choose a mean/LightGBM switch
per cohort from these RPE1 results. Further experiments need predeclared K562
selection and additional independent validation before claiming broad transfer.

**31 tests passed.** The initial full-prediction phase was killed after CV;
the successful recovery preserved selections and used chunked on-disk prediction
and evaluation. The resumed phase took 108.8 seconds with 1.19 GiB peak RSS.
No EC2 was launched. All **29 artifacts / 503,734,598 bytes** were backed up and
SHA-256 verified; the manifest was retrieved directly from S3 afterward.

Committed evidence: `003_string_models/metrics.json`, `metrics.csv`, and
`status.json`. Full frozen folds/axes, fitted models, predictions, graph and exact
STRING sources are under `public/replogle_2022/003_string_models/` in the existing
private S3 bucket. `status.json` pins the complete remote manifest by SHA-256.
See `docs/003-string-models.md` for the predeclared design and recovery details.

Next: audit Adamson CRISPRi condition/guide matching and expression scale; extend
training-only validation for targets without measured neighbors. Separately build
a count-generation adapter and evaluate dispersion/DE calibration using retained
single cells. Do not present mean-delta MSE improvements as a VCC score improvement.

## 004 and 005: provenance audit and raw-count rehearsal

Adamson metadata were audited separately; its UPR control identities and
conditions still require primary confirmation, so it remains excluded.
Experiment 005 successfully generated fresh counts and ran the official six
raw metrics on six predetermined RPE1 targets (three shared, three unseen).

| Raw metric | Zero delta | Training mean | LightGBM |
|---|---:|---:|---:|
| PDS cosine ↑ | 0.56667 | 0.53333 | 0.50000 |
| Expression error ↓ | 4.54529 | 4.93668 | 4.78661 |
| DE direction fidelity/yield ↑ | 0.70524 | 0.69566 | 0.69759 |
| DE direction reach ↑ | 0.14152 | 0.18818 | 0.07000 |
| DE Jaccard ↑ | 0.00226 | 0.00412 | 0.00291 |
| DE LFC NMAE ↓ | 0.94046 | 0.93999 | 0.95066 |

These are unscaled public-data diagnostics, not leaderboard scores. Small-panel
PDS and metric-specific DE gates limit interpretation. See
`docs/005-count-rehearsal.md`, exact per-target CSVs and cohort counts for details.
The approximate count adapter needs K562-only calibration before challenge use.

## 006: K562 control calibration — completed October 13

Calibration controls selected 16 correction iterations before audit expression
was read. Mean metrics across the three declared generation seeds:

| Generator | Audit mean-log RMSE ↓ | Audit variance-log RMSE ↓ | Audit dropout MAE ↓ |
|---|---:|---:|---:|
| Legacy | 0.057217 | 0.075210 | 0.101699 |
| 8 correction iterations | 0.047399 | 0.065858 | 0.070475 |
| **16 correction iterations (selected)** | **0.045400** | **0.058507** | **0.061400** |

The selected generator reduces these errors by 20.7%, 22.2% and 39.6%, respectively.
This is a K562 null-control diagnostic, not perturbation prediction or an official
VCC score. It used 576 fit, 192 calibration and 192 audit controls balanced across
48 gem groups and all 8,563 K562 genes. No RPE1 outcomes entered this experiment.

**41 pinned-environment tests passed.** The scientific command took 115.1 seconds
and about 419 MiB peak RSS. All **17 artifacts / 11,085,979 bytes** passed full S3
read-back SHA-256 verification. No EC2 was launched.

Exact evidence: [metrics](006_k562_control_calibration/metrics.json),
[frozen selection](006_k562_control_calibration/frozen_selection.json),
[backup manifest](006_k562_control_calibration/backup_manifest.json), and
[completion status](006_k562_control_calibration/status.json). The CSV is derived
from those exact reports. See the
[run report](../docs/006-k562-control-calibration.md) for the predeclared protocol.
Next: compare the fixed correction and legacy adapter on K562 perturbation folds
before freezing the final generator; no RPE1 retuning or new submission yet.
