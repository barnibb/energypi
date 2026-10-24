import subprocess
import unittest
from pathlib import Path


class MacBackupRunnerTests(unittest.TestCase):
    def test_runner_is_valid_and_keeps_mac_awake_with_one_retry(self):
        path = Path('mac-backup/run-backup.sh')
        if not path.exists():
            self.skipTest('Mac-spezifischer Runner ist auf dem Pi nicht installiert')
        subprocess.run(['/bin/bash', '-n', str(path)], check=True)
        script = path.read_text()
        self.assertIn('/usr/bin/caffeinate -i -w $$', script)
        self.assertIn('/usr/bin/ssh -C -i "$HOME/.ssh/marstek_backup_ed25519"', script)
        self.assertIn('-o IPQoS=throughput', script)
        self.assertIn('if [ "$attempt" -ge 2 ]', script)
        self.assertIn('rm -f "$partial"', script)
