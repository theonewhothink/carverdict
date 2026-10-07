"""Preview branches must never run an in-build production deployment."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class BuildEntrypointTest(unittest.TestCase):
    def run_entrypoint(self, branch=None, preview=None, build_status=0):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work / 'scripts').mkdir()
            shutil.copy(root / 'build.sh', work / 'build.sh')
            (work / 'scripts/build_inner.sh').write_text(
                f'echo "preview=${{MOTORJURY_PREVIEW:-0}}"\nexit {build_status}\n')
            executable = work / 'npx'
            executable.write_text('#!/bin/sh\necho deployed > deployed\nexit 0\n')
            executable.chmod(0o755)
            environment = dict(os.environ, PATH=str(work) + os.pathsep + os.environ['PATH'])
            for name in ('WORKERS_CI_BRANCH', 'MOTORJURY_PREVIEW'):
                environment.pop(name, None)
            if branch is not None:
                environment['WORKERS_CI_BRANCH'] = branch
            if preview is not None:
                environment['MOTORJURY_PREVIEW'] = preview
            result = subprocess.run(['bash', 'build.sh'], cwd=work, env=environment,
                                    capture_output=True, text=True)
            return result.returncode, result.stdout, (work / 'deployed').exists()

    def test_cloudflare_feature_branch_stays_private(self):
        code, output, deployed = self.run_entrypoint(branch='codex/review', preview='0')
        self.assertEqual(code, 0)
        self.assertIn('preview=1', output)
        self.assertFalse(deployed)

    def test_main_build_deploys_only_after_success(self):
        code, output, deployed = self.run_entrypoint(branch='main')
        self.assertEqual(code, 0)
        self.assertIn('preview=0', output)
        self.assertTrue(deployed)
        code, _, deployed = self.run_entrypoint(branch='main', build_status=1)
        self.assertEqual(code, 1)
        self.assertFalse(deployed)

    def test_explicit_preview_does_not_deploy(self):
        code, _, deployed = self.run_entrypoint(branch='main', preview='1')
        self.assertEqual(code, 0)
        self.assertFalse(deployed)
