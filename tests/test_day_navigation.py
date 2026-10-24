import unittest
from pathlib import Path


class DayNavigationTests(unittest.TestCase):
    def test_relative_day_controls_are_wired(self):
        html = Path('templates/index.html').read_text()
        script = Path('static/dashboard.js').read_text()
        for element_id in ('previous-day', 'today', 'next-day', 'date'):
            self.assertIn(f'id="{element_id}"', html)
        controls = html[html.index('id="previous-day"'):html.index('id="date"')]
        self.assertLess(controls.index('previous-day'), controls.index('id="today"'))
        self.assertLess(controls.index('id="today"'), controls.index('next-day'))
        self.assertIn("$('previous-day').onclick=()=>shiftHistoryDay(-1)", script)
        self.assertIn("$('next-day').onclick=()=>shiftHistoryDay(1)", script)
        self.assertIn("$('date').value||localDay()", script)


if __name__ == '__main__':
    unittest.main()
