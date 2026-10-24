import unittest
from controller import Controller


class ControllerTests(unittest.TestCase):
    def test_complete_cycle(self):
        c = Controller()
        for t in range(0, 180, 5):
            self.assertIsNone(c.update(3500, t))
        self.assertEqual(c.update(3500, 180), "WUERDE_SPERREN")
        self.assertIsNone(c.update(2500, 185))
        self.assertTrue(c.blocked)
        for t in range(190, 370, 5):
            self.assertIsNone(c.update(-500, t))
        self.assertEqual(c.update(-500, 370), "WUERDE_FREIGEBEN")

    def test_threshold_resets_timer(self):
        c = Controller()
        for t in range(0, 175, 5):
            c.update(3500, t)
        c.update(3000, 175)
        self.assertIsNone(c.since)
        self.assertIsNone(c.update(3500, 180))
        self.assertFalse(c.blocked)

    def test_missing_sample_and_gap(self):
        for invalid in (None, float("nan")):
            c = Controller(blocked=True)
            c.update(1000, 0)
            c.update(invalid, 5)
            self.assertIsNone(c.since)
            self.assertTrue(c.blocked)
        c = Controller()
        c.update(4000, 0)
        self.assertIsNone(c.update(4000, 200))
        self.assertEqual(c.since, 200)

    def test_exact_release_threshold(self):
        c = Controller(blocked=True)
        c.update(1000, 0)
        c.update(2000, 5)
        self.assertIsNone(c.since)
        self.assertTrue(c.blocked)

    def test_corrected_load_and_sustained_discharge_paths(self):
        c=Controller(block_w=1600,release_w=1000,hold_s=180,sustained_discharge_w=750,sustained_discharge_s=600)
        for t in range(0,180,5):self.assertIsNone(c.update(2390,t,800))
        self.assertEqual(c.update(2390,180,800),'WUERDE_SPERREN')
        self.assertTrue(c.blocked)
        c=Controller(block_w=3000,release_w=1000,hold_s=180,sustained_discharge_w=750,sustained_discharge_s=600)
        for t in range(0,600,5):self.assertIsNone(c.update(2390,t,800))
        self.assertEqual(c.update(2390,600,800),'WUERDE_SPERREN_DAUERLAST')

    def test_sustained_timer_resets_below_threshold_and_on_gap(self):
        c=Controller(block_w=3000,sustained_discharge_w=750,sustained_discharge_s=600)
        c.update(1500,0,800);c.update(1500,300,740)
        self.assertIsNone(c.sustained_since)
        c.update(1500,305,800);c.update(1500,500,800)
        self.assertEqual(c.sustained_since,500)


if __name__ == "__main__":
    unittest.main()
