from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rttlayout2.export import export_layout
from rttlayout2.app import hud_metrics
from rttlayout2.model import CockpitFile


FIXTURES = Path(__file__).resolve().parent / "fixtures"
TEST_DIR = Path(__file__).resolve().parent
F15_PATH = FIXTURES / "F-15C" / "3dCkpit.dat"
F16_PATH = FIXTURES / "F-16CM-52" / "3dCkpit.dat"


class ModelTests(unittest.TestCase):
    def test_parse_f15_rtt_block(self):
        doc = CockpitFile.load(F15_PATH)
        self.assertEqual(doc.rtt_width, 1200)
        self.assertEqual(doc.rtt_height, 1200)
        self.assertGreaterEqual({s.name for s in doc.surfaces}, {"hud", "pfl", "ded", "rwr", "mfdleft", "mfdright"})
        self.assertEqual(next(s for s in doc.surfaces if s.name == "hud").rect(), (0, 0, 560, 560))

    def test_parse_f16_optional_hms(self):
        doc = CockpitFile.load(F16_PATH)
        self.assertEqual(doc.rtt_width, 600)
        self.assertEqual(doc.rtt_height, 600)
        self.assertEqual(next(s for s in doc.surfaces if s.name == "hms").rect(), (0, 314, 286, 600))

    def test_render_keeps_other_file_content_and_removes_old_block(self):
        doc = CockpitFile.load(F15_PATH)
        rendered = doc.render()
        self.assertIn("cockpitmodel", rendered)
        self.assertIn("// RTT definition line:", rendered)
        self.assertIn("boresighty 0.375;", rendered)
        self.assertEqual(rendered.count("mfdleft"), 1)

    def test_export_png(self):
        doc = CockpitFile.load(F15_PATH)
        with tempfile.TemporaryDirectory(dir=TEST_DIR) as tmp:
            out = Path(tmp) / "sample_export.png"
            export_layout(doc, out, 1600, 1600)
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 0)

    def test_export_rejects_out_of_bounds_surface(self):
        doc = CockpitFile.load(F15_PATH)
        doc.surfaces[0].left = -1
        with tempfile.TemporaryDirectory(dir=TEST_DIR) as tmp:
            out = Path(tmp) / "invalid_export.png"
            with self.assertRaises(ValueError):
                export_layout(doc, out)

    def test_hud_metrics_from_quad(self):
        doc = CockpitFile.load(F15_PATH)
        hud = next(s for s in doc.surfaces if s.name == "hud")
        metrics = hud_metrics(hud)
        self.assertAlmostEqual(metrics["tfov_h"], 20.000, places=3)
        self.assertAlmostEqual(metrics["tfov_v"], 20.100, places=3)
        self.assertAlmostEqual(metrics["deck_angle"], -4.126, places=3)


if __name__ == "__main__":
    unittest.main()
