import tempfile
import unittest
from pathlib import Path

from webapp import create_app


class EnergyFlowPreviewTests(unittest.TestCase):
    def test_preview_is_separate_from_main_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = create_app({'database_path': Path(tmp) / 'measurements.db', 'shelly': {'poll_seconds': 5}}).test_client()
            main = client.get('/').get_data(as_text=True)
            preview = client.get('/energiefluss-preview')
        self.assertEqual(preview.status_code, 200)
        page = preview.get_data(as_text=True)
        self.assertIn('id="energy-flow"', page)
        self.assertIn('BLAUES MODEL Y', page)
        self.assertIn('class="central-hub"', page)
        self.assertIn('id="flow-house"', page)
        self.assertIn('class="asset grid-asset"', page)
        self.assertIn('/static/energy-flow-preview.js', page)
        self.assertNotIn('id="energy-flow"', main)

    def test_preview_script_uses_existing_read_only_apis(self):
        script = Path(__file__).parents[1].joinpath('static/energy-flow-preview.js').read_text(encoding='utf-8')
        for endpoint in ('/api/status','/api/solaredge','/api/marstek','/api/charging'):
            self.assertIn(endpoint, script)
        self.assertNotIn("method:'POST'", script)


if __name__ == '__main__':
    unittest.main()
