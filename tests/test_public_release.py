import subprocess
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]

@unittest.skipUnless((ROOT / '.git').is_dir(), 'Veröffentlichungsprüfung benötigt eine Git-Arbeitskopie')
class PublicReleaseTests(unittest.TestCase):
    def tracked_files(self):
        result = subprocess.run(
            ['git', 'ls-files', '-z'], check=True, capture_output=True
        )
        return [Path(name) for name in result.stdout.decode().split('\0') if name]

    def test_local_configuration_is_not_tracked(self):
        tracked = {str(path) for path in self.tracked_files()}
        self.assertNotIn('config.toml', tracked)
        self.assertNotIn('marstek.toml', tracked)
        self.assertNotIn('forecast.toml', tracked)
        self.assertNotIn('deploy-local.env', tracked)
        self.assertNotIn('secrets.toml', tracked)
        self.assertIn('config.example.toml', tracked)
        self.assertIn('marstek.example.toml', tracked)
        self.assertIn('forecast.example.toml', tracked)
        self.assertIn('deploy-local.example.env', tracked)

    def test_tracked_text_has_no_personal_network_values(self):
        forbidden_literals = [
            '192.168.178.' + '57',
            '192.168.178.' + '102',
            '192.168.178.' + '104',
        ]
        forbidden_patterns = [
            re.compile(r'/Users/[^/]+/Documents/Codex'),
            re.compile(r'de\.[^.]+\.marstek-backup'),
        ]
        findings = []
        for path in self.tracked_files():
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                continue
            for value in forbidden_literals:
                if value in text:
                    findings.append(f'{path}: {value}')
            for pattern in forbidden_patterns:
                if pattern.search(text):
                    findings.append(f'{path}: {pattern.pattern}')
        self.assertEqual(findings, [])


if __name__ == '__main__':
    unittest.main()
