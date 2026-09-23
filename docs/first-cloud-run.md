# First cloud run: prepare before paying

Status: scripts prepared; no EC2 launch or full-panel submission performed.
Do not skip the full null submission gate to start model development.

## Before launch

1. Commit/push the reviewed source and record the exact commit to check out.
2. Run `bash scripts/rehearse.sh`. This generates 24 synthetic cells and packages
   them through the official CLI; it does not upload or shut down the host.
3. Confirm Ohio quota, live price, credit balance and authorized spending limit.
   Proposed configuration: x86 Ubuntu, r6a.4xlarge (128 GiB / 16 vCPU), 200 GiB
   encrypted gp3, one instance. Configure instance-initiated shutdown to **Stop**.
   Use SSH restricted to the operator's IP, IMDSv2 required, no public notebook
   port, no Elastic IP, NAT gateway, extra monitoring or paid AMI software.
4. Configure a boot-time shutdown timer BEFORE launch (see cloud-init below).
   This covers unattended time before anyone starts the batch. Confirm timer
   activation after boot; do not cancel it just because a job is running.
5. Decide where to export results and packages. EBS retains them after Stop, but
   is not an independent backup and continues billing. Do not delete the volume
   until copies are downloaded and their SHA-256 digests verified.

## Boot configuration (EC2 user data)

This contains no token or private key. It schedules a stop at eight hours from
boot, on EVERY boot, before dependency setup. Instance shutdown behavior must be
Stop. Review and supply this user data as part of the approved launch configuration.

```yaml
#cloud-config
packages:
  - git
  - python3-venv
  - tmux
write_files:
  - path: /etc/systemd/system/vcc-boot-deadline.service
    content: |
      [Unit]
      Description=Stop the VCC host at the runtime deadline
      [Service]
      Type=oneshot
      ExecStart=/usr/bin/systemctl poweroff
  - path: /etc/systemd/system/vcc-boot-deadline.timer
    content: |
      [Unit]
      Description=Eight hour VCC runtime limit per boot
      [Timer]
      OnBootSec=8h
      Unit=vcc-boot-deadline.service
      [Install]
      WantedBy=timers.target
runcmd:
  - systemctl daemon-reload
  - systemctl enable --now vcc-boot-deadline.timer
```

A timer is a safeguard, not a billing cap. A setup failure before timer activation
still needs operator attention. Stop the instance manually if timer activation
cannot be verified. Billing alerts alone cannot guarantee a dollar limit.

## Run the approved batch

Clone `https://github.com/anushkaagrawal13/vcc-2026.git`, check out the reviewed
commit, and enter the repo. Verify `systemctl list-timers vcc-boot-deadline.timer`.
Start `tmux new -s vcc` so an SSH disconnect does not interrupt the job.

Inside tmux:

```bash
mkdir -p logs
read -rsp 'VCC token: ' VCC_TOKEN; echo
export VCC_TOKEN
bash scripts/run-on-ec2.sh config/000_zero_delta.yaml >logs/first-run.log 2>&1
```

Enter the token only into the host's private terminal prompt, never chat, Git,
user data, a command-line argument, or a notebook cell. Do not use shell tracing.
The token is inherited in process memory; it is not intentionally persisted.
Raw operational logs stay gitignored because the CLI may emit signed URLs.

The wrapper arms a second independent eight-hour timer, verifies this is an EC2
Linux machine, installs the environment, runs tests, and executes `src.run`.
It powers off on success or failure. Both timers must be checked before work;
the earlier timer wins. A stopped machine requires explicit restart to inspect
files remotely. Do not leave it running just to wait for a score.

The runner sets packaging scratch to the data disk, checks >=96 GiB effective
RAM and >=100 GiB free storage for the full panel before expensive work, then
checks official memory/scratch estimates against the generated artifact.

## Resume and review

`data/processed/000_zero_delta/run-state.json` records completed stages and hashes.
Rerun the same config at the same commit to resume. Missing or modified artifacts,
changed source/config, concurrent runs, and uncheckpointed prediction/package
files cause a stop for inspection. Interrupted generation is restarted from the
beginning; it does not resume within a matrix. No script deletes existing outputs
to force a retry. Checksums may take time on full-size files.

The setup script pins Python 3.12.2 and its uv bootstrap, installs the lockfile,
and runs `pip check`; the runner records the actual platform-specific dependency
set in `results/000_zero_delta_environment.txt`.

After successful packaging:

- Export the experiment config, `results/000_zero_delta*.json`, environment list,
  run state, preflight report and `.vcc` package. Verify SHA-256 on the destination.
- The status is **packaged_not_submitted**, not a leaderboard result. Review the
  package and submit exactly once with the official CLI:

  ```bash
  .venv/bin/vcc submit data/processed/000_zero_delta/prediction.vcc \
    -m '000_zero_delta: multinomial control null' --wait
  ```

- If upload times out, inspect the server's entry history before retrying. Never
  blindly retry a submission: quota is two scored submissions per UTC day.
- Save entry ID, panel/partition, anchors and all six metrics in `results/`, then
  commit sanitized summaries. Keep the token and signed URLs out of commits.
- Stop compute immediately; retain only necessary storage. After verified backup,
  remove redundant data/volumes with approval. Review costs before the next run.

## Later runs

Implement Replogle pseudobulk and one-feature ridge on small fixtures next, after
recording the full null score. Keep RPE1 responses out of tuning and feature
fitting. Batch large preprocessing on AWS; use cached pseudobulk tables and Kaggle
for small iterations. Adamson, additional features and LightGBM follow only after
that holdout works. No GPU instance is needed for the initial baseline.
