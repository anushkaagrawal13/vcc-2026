import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from src.run import stage


class RunnerTests(unittest.TestCase):
    def test_resume_rejects_changed_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, state_path = root / 'output', root / 'state.json'
            state, calls = {'stages': {}}, []
            def action():
                calls.append(1)
                artifact.write_text('complete')
            stage(state, state_path, 'example', [artifact], action)
            stage(state, state_path, 'example', [artifact], action)
            self.assertEqual(calls, [1])
            artifact.write_text('corrupted')
            with self.assertRaisesRegex(RuntimeError, 'missing/changed'):
                stage(state, state_path, 'example', [artifact], action)

    def test_failed_stage_is_not_checkpointed(self):
        with tempfile.TemporaryDirectory() as directory:
            state_path, state = Path(directory) / 'state.json', {'stages': {}}
            def fail():
                raise RuntimeError('interrupted')
            with self.assertRaisesRegex(RuntimeError, 'interrupted'):
                stage(state, state_path, 'example', [], fail)
            self.assertEqual(state['stages'], {})
            self.assertFalse(state_path.exists())

    def test_ec2_wrapper_arms_deadline_and_stops(self):
        for setup_exit in (0, 23):
            with self.subTest(setup_exit=setup_exit), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                scripts = root / 'scripts'
                scripts.mkdir()
                source = Path(__file__).resolve().parents[1] / 'scripts/run-on-ec2.sh'
                (scripts / 'run-on-ec2.sh').write_text(source.read_text())
                (scripts / 'setup.sh').write_text(f'#!/bin/bash\nexit {setup_exit}\n')
                binaries = root / 'bin'
                binaries.mkdir()
                log = root / 'sudo.log'
                # Never invoke real sudo/systemctl: every privileged call is mocked.
                for name, content in {
                    'uname': 'echo Linux',
                    'grep': 'exit 0',
                    'sudo': 'printf "%s\\n" "$*" >> "$SUDO_LOG"',
                }.items():
                    path = binaries / name
                    path.write_text('#!/bin/bash\n' + content + '\n')
                    path.chmod(0o755)
                venv = root / '.venv/bin'
                venv.mkdir(parents=True)
                python = venv / 'python'
                python.write_text('#!/bin/bash\nexit 0\n')
                python.chmod(0o755)
                env = dict(os.environ, PATH=f'{binaries}:' + os.environ['PATH'],
                           VCC_TOKEN='synthetic-not-a-token', SUDO_LOG=str(log))
                result = subprocess.run(['bash', str(scripts / 'run-on-ec2.sh')], env=env, timeout=10)
                self.assertEqual(result.returncode, setup_exit)
                calls = log.read_text().splitlines()
                self.assertIn('--on-active=8h', calls[1])
                self.assertEqual(calls[-1], '-n /usr/bin/systemctl poweroff')
