import tempfile
import unittest
from pathlib import Path

from webapp import create_app


class DesignPreviewTests(unittest.TestCase):
    def test_design_updater_includes_weather_effect_source(self):
        updater_path = Path(__file__).parents[1].joinpath('update-design-preview.sh')
        if not updater_path.exists():
            self.skipTest('Das Mac-Aktualisierungsskript wird nicht auf dem Pi installiert.')
        updater = updater_path.read_text(encoding='utf-8')
        self.assertIn('static/weather.js', updater)
        self.assertIn('static/grid-charge.js', updater)
        self.assertIn('grid_charging.py', updater)
        self.assertIn('tests/test_grid_charging.py', updater)
        self.assertIn('restart marstek-web marstek-battery', updater)

    def test_ipad_web_app_metadata_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = create_app({'database_path': Path(tmp) / 'measurements.db', 'shelly': {'poll_seconds': 5}}).test_client()
            page = client.get('/').get_data(as_text=True)
            manifest = client.get('/static/manifest.webmanifest')
            manifest_data = manifest.get_json()
        self.assertIn('apple-mobile-web-app-capable', page)
        self.assertIn('apple-touch-icon', page)
        self.assertIn('manifest.webmanifest', page)
        self.assertEqual(manifest.status_code, 200)
        self.assertEqual(manifest_data['display'], 'standalone')
        self.assertEqual(manifest_data['start_url'], '/')
        manifest.close()

    def test_system_status_keeps_last_success_during_short_failure(self):
        script = Path(__file__).parents[1].joinpath('static/system.js').read_text(encoding='utf-8')
        self.assertIn("lastSuccess = data", script)
        self.assertIn("render(lastSuccess)", script)
        self.assertIn("Aktualisierung verzögert", script)
        self.assertIn("failures < 3", script)

    def test_preview_is_separate_and_explains_its_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = create_app({
                'database_path': Path(tmp) / 'measurements.db',
                'shelly': {'poll_seconds': 5},
            }).test_client()
            response = client.get('/')

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn('EnergyPi · Monitor', page)
        self.assertIn('id="grid-charge-open"', page)
        self.assertIn('id="grid-charge-dialog"', page)
        self.assertIn('id="grid-charge-card-status"', page)
        self.assertIn('name="start_at"', page)
        self.assertIn('class="charge-open-button"', page)
        self.assertNotIn('id="grid-charge-open" class="metric-detail-link"', page)
        self.assertIn('data-step-field="energy_kwh"', page)
        self.assertIn('data-step-field="duration_hours"', page)
        self.assertIn('data-step-field="power_w"', page)
        self.assertIn('data-power="2500"', page)
        self.assertNotIn('id="grid-charge-confirm"', page)
        self.assertNotIn('<summary>Netzladevorschlag</summary>', page)
        grid_charge = Path(__file__).parents[1].joinpath('static/grid-charge.js').read_text(encoding='utf-8')
        self.assertIn('/api/grid-charge/preview', grid_charge)
        self.assertIn('voraussichtliches Ende', grid_charge)
        self.assertIn("active:'Laden aktiv'", grid_charge)
        self.assertIn('id="preferences-open"', page)
        self.assertIn('id="forecast-previous-day"', page)
        self.assertIn('id="forecast-next-day"', page)
        self.assertIn('id="tibber-previous-day"', page)
        self.assertIn('id="tibber-next-day"', page)
        self.assertIn('id="tibber-mini-chart"', page)
        self.assertIn('id="tibber-live-min"', page)
        self.assertIn('id="tibber-live-max"', page)
        self.assertIn('href="#tibber-prices"', page)
        self.assertIn('id="tibber-prices"', page)
        tibber = Path(__file__).parents[1].joinpath('static/tibber.js').read_text(encoding='utf-8')
        self.assertIn("if(el('tibber-date').value===today()){todayPayload=p", tibber)
        self.assertIn('(todayPayload?.points||[])', tibber)
        self.assertIn('renderLivePrice(todayPayload)', tibber)
        self.assertIn("p.complete?'Heutige Tagespreise vollständig'", tibber)
        self.assertIn('class="system-monitor-link"', page)
        self.assertIn('href="/design_alt"', page)
        legacy = client.get('/design_alt')
        self.assertEqual(legacy.status_code, 200)
        self.assertIn('Netzbezug & Einspeisung', legacy.get_data(as_text=True))
        self.assertIn('class="system-monitor-link"', legacy.get_data(as_text=True))
        system_script = Path(__file__).parents[1].joinpath('static/system.js').read_text(encoding='utf-8')
        self.assertIn('location.hostname}:8083', system_script)
        compatibility = client.get('/design-preview')
        self.assertEqual(compatibility.status_code, 200)
        self.assertLess(page.index('id="planning-area"'), page.index('id="system-area"'))
        self.assertIn('class="chartcard systemcard system-overview" open', page)
        self.assertIn('class="chartcard observation-card"', page)
        observation=page[page.index('class="chartcard observation-card"'):page.index('class="chartcard decisions-card"')]
        self.assertTrue(observation.startswith('class="chartcard observation-card"'))
        self.assertNotIn(' open',observation.split('>')[0])
        self.assertIn('<summary>',observation)
        decisions=page[page.index('class="chartcard decisions-card"'):page.index('</div></section>',page.index('class="chartcard decisions-card"'))]
        self.assertNotIn(' open',decisions.split('>')[0])
        self.assertIn('<summary>',decisions)
        self.assertIn('/static/autumn-leaves.js', page)
        self.assertIn('class="pv-sunshine"', page)
        self.assertIn('name="pv_sunshine_threshold_w"', page)
        self.assertIn('name="frost_temperature_c"', page)
        dashboard = Path(__file__).parents[1].joinpath('static/dashboard.js').read_text(encoding='utf-8')
        self.assertIn('sunshineThreshold-200', dashboard)
        self.assertIn("classList.toggle('sunshine-active'", dashboard)
        self.assertIn("classList.toggle('grid-import'", dashboard)
        self.assertIn("classList.toggle('grid-export'", dashboard)
        self.assertIn('id="grid-average-value"', page)
        self.assertIn('15-Minuten-Durchschnitt', page)
        self.assertIn('Zeitlich gemittelter Nettowert', page)
        self.assertIn('id="phase-open"', page)
        self.assertIn('id="phase-dialog"', page)
        self.assertIn('/static/phases.js', page)
        self.assertIn('id="live-energy-card"', page)
        self.assertIn('id="live-source-bar"', page)
        self.assertIn('id="live-target-bar"', page)
        self.assertIn('href="#energy-area"', page)
        design = Path(__file__).parents[1].joinpath('static/design-live.css').read_text(encoding='utf-8')
        self.assertIn('grid-template-columns:repeat(3,minmax(220px,1fr))', design)
        self.assertIn('#live-energy-effective{font-size:15px', design)
        self.assertIn('#grid-charge-form [hidden]{display:none!important}', design)
        self.assertIn('.touch-stepper{display:grid', design)
        self.assertIn('drawLiveFlows(liveFlowResult)', dashboard)
        self.assertIn('next.balance_day===localDay()', dashboard)
        overview=page[page.index('id="overview"'):page.index('id="battery"')]
        self.assertNotIn('class="phases"', overview)
        self.assertIn('updateGridAverage(s.average_15m)', dashboard)
        autumn = Path(__file__).parents[1].joinpath('static/autumn-leaves.js').read_text(encoding='utf-8')
        weather = Path(__file__).parents[1].joinpath('static/weather.js').read_text(encoding='utf-8')
        self.assertIn("classList.toggle('frost-active'", autumn)
        self.assertIn("new CustomEvent('energypi-weather'", weather)
        self.assertIn("valid:Boolean(p.sample&&!p.stale)", weather)
        self.assertNotIn('/static/autumn-leaves.js', legacy.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
