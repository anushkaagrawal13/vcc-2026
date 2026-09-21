# Official contract review — 2026-09-21

Read end to end: [rules](https://virtualcellchallenge.org/rules) (revised September
16), [evaluation](https://virtualcellchallenge.org/evaluation),
[datasets](https://virtualcellchallenge.org/datasets), and the full
[rubric source](https://github.com/ArcInstitute/cell-eval2/blob/5e64833518a6603a0301cbe28185d49c30f4a986/docs/vcc2026_metrics/vcc2026-metrics.md)
that builds the official PDF. Source revision:
`5e64833518a6603a0301cbe28185d49c30f4a986`. The source repo currently reports
cell-eval2 0.16.0; the rubric's numerical examples describe 0.15.0 / rule version 3.
Record the actual scorer/rule/bundle stamps with every evaluation; do not infer
compatibility from example numbers.

## Observed input, not an invented schema

The authenticated validation bundle downloaded September 21 contains:

- `context_A.h5ad`, `context_B.h5ad`, `context_C.h5ad`;
- `gene_names.csv`: one column **with `gene_name` header**; preserve its order;
- `pert_counts.csv`: one `target_gene` column, 300 symbols;
- `manifest.json`: season 2026, partition `val`, panel `vcc2026-val-1`, contexts
  A/B/C, 18,533 genes, 400 predicted cells per perturbation;
- 18,400 control cells per context, with `context`, `target_gene`, `ntc_id` in obs.

The public CLI help says headerless genes, but CLI 0.2.1 accepts the actual header.
Use actual downloaded ordering, not the website's illustrative gene list.
The downloader records SHA-256 locally after the official CLI's transport
checksum verification. Prediction reports include the input hashes.

## Upload versus scorer

Upload one `.vcc` with all contexts, no control-labelled rows, exact perturbation
set, exactly 400 cells per target/context, exact gene order, finite nonnegative
integral `.X`, ≤1,000,000 counts per cell and ≤4,750,000,000 stored entries.
Sparse storage must omit explicit zeros. Test contexts will be D/E/F.

The platform adds held-out real controls before calling cell-eval2. Consequently
the **scorer** needs controls although the **upload** must not contain them.
Do not pass upload files directly into a local scorer and assume equivalence.

## Six metrics

| Metric | Important implementation boundary |
|---|---|
| `pds_cosine` | Rank effect similarity; exclude all panel target genes, average tied ranks |
| `expr_mse_unbiased_capped_norm` | Panel-wide ratio of sums, jackknife correction and prediction-spread cap |
| `de_wilcoxon_direction_fidelity_yield_raw` | Direction precision multiplied by call coverage |
| `de_wilcoxon_direction_reach_raw` | Deepest prefix reaching ≥0.9 directional purity |
| `de_wilcoxon_sig_jaccard` | Significant-set intersection / union |
| `de_wilcoxon_lfc_nmae` | Fold-change error on reference-significant genes; ≥10-gene gate |

The target's own gene is excluded throughout (all panel targets for PDS). DE uses
per-cell CPM, control mean >5 CPM filtering, per-perturbation BH FDR <0.05 and
Wilcoxon tests. Pseudobulk expression uses normalized group sums then log1p;
these are distinct transforms. Leave their implementation to the pinned official
scorer instead of reproducing selected formulas approximately.

Metrics scale between a context-specific mean-perturbation-response baseline and
a replicate anchor, then average equally over six metrics and three contexts.
Expression is clipped to [0,1]; NMAE has a -6 floor; other scaled metrics may be
negative or exceed 1. Validation/test scores are not directly comparable.

## Rules affecting workflow

Eligibility and personal/university/employer capacity are participant declarations.
Teams have 1–8 members; a person belongs to one team. Use data and software only
with applicable rights. Experimental results may train a model but may not be
copied into an entry or used to manually revise its predictions. Describe learned
and non-learned components and datasets in the method record. Do not share models,
results or strategies with other teams in ways that undermine the competition.

Two scored submissions per UTC day; one submission in flight. Uploads rejected
before scoring do not consume the scored quota. Leaderboard submission publishes
team/member/organization/model identity with scores. Only the last final entry
determines prize consideration. Rules may change with organizer notification.

Registration and CLI authentication are complete as observed September 21.
Discord membership and Kaggle account/phone verification are not verified.
[Official Discord invitation](https://discord.com/invite/f2aWGPXwej).

These are engineering notes; the linked full rules remain authoritative.
