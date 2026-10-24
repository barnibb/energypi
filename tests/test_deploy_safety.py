import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class DeploySafetyTests(unittest.TestCase):
    def test_shell_scripts_are_valid(self):
        for name in ('deploy-to-pi.sh', 'deploy/install-on-pi.sh'):
            subprocess.run(['/bin/bash', '-n', str(ROOT / name)], check=True)

    def test_full_deploy_preserves_local_state(self):
        script = (ROOT / 'deploy-to-pi.sh').read_text()
        for name in ('config.toml', 'marstek.toml', 'forecast.toml',
                     'secrets.toml', 'deploy-local.env', 'data/'):
            self.assertIn("--exclude '" + name + "'", script)
        self.assertIn('energypi-code-', script)

    def test_installer_validates_configuration_before_restart(self):
        script = (ROOT / 'deploy/install-on-pi.sh').read_text()
        validation = script.index('for required in config.toml')
        tests = script.index('unittest discover')
        restart = script.index('systemctl restart')
        self.assertLess(validation, tests)
        self.assertLess(tests, restart)
        self.assertIn('active_services=()', script)
        self.assertIn('ENERGYPI_REMOTE_DIR', script)


if __name__ == '__main__':
    unittest.main()
