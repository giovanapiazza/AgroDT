"""Testes de importacao generica e associacao conservadora de bandas."""
import io
import unittest
import zipfile

import numpy as np
from PIL import Image

from image_importer import classify, find_pairs, extract_single_band, make_tiff, read_zip


def band(value=10):
    buf = io.BytesIO()
    Image.fromarray(np.full((20, 20), value, dtype=np.uint16)).save(buf, format="TIFF")
    return buf.getvalue()


class GenericImporterTests(unittest.TestCase):
    def test_sequoia(self):
        files = {
            "drone/IMG_260410_133001_0000_RED.TIF": band(),
            "drone/IMG_260410_133001_0000_NIR.TIF": band(),
            "drone/IMG_260410_133001_0000_REG.TIF": band(),
            "drone/IMG_260410_133001_0001_RED.TIF": band(),
            "drone/IMG_260410_133001_0001_NIR.TIF": band(),
        }
        pairs, warnings = find_pairs(files, "auto")
        self.assertEqual(len(pairs), 2)
        self.assertFalse(any("incompleto" in w for w in warnings))

    def test_sentinel_2(self):
        pairs, _ = find_pairs({"tile/B04.tif": band(), "tile/B08.tif": band()}, "sentinel2")
        self.assertEqual(len(pairs), 1)

    def test_micasense_manual_profile(self):
        pairs, _ = find_pairs({"IMG_0001_3.tif": band(), "IMG_0001_5.tif": band()}, "micasense_rededge")
        self.assertEqual(len(pairs), 1)
        auto, _ = find_pairs({"IMG_0001_3.tif": band(), "IMG_0001_5.tif": band()}, "auto")
        self.assertEqual(len(auto), 0)

    def test_folder_bands(self):
        pairs, _ = find_pairs({"RED/IMG_0001.tif": band(), "NIR/IMG_0001.tif": band()}, "auto")
        self.assertEqual(len(pairs), 1)

    def test_ambiguous_not_guessed(self):
        pairs, warnings = find_pairs({"IMG_001.tif": band(), "IMG_002.tif": band()}, "auto")
        self.assertEqual(len(pairs), 0)
        self.assertTrue(warnings)

    def test_rgb_not_assumed_red(self):
        self.assertEqual(classify("capture_RGB.JPG")[0], None)

    def test_zip_traversal(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("../escape_RED.tif", band())
        with self.assertRaises(ValueError):
            read_zip(archive.getvalue())

    def test_nan_mask_is_preserved(self):
        data = np.array([[0.2, float("nan")], [0.7, 0.9]], dtype=np.float32)
        payload = make_tiff(data)
        output = extract_single_band(payload, ".tif")
        self.assertTrue(np.isnan(output[0, 1]))
        self.assertAlmostEqual(float(output[1, 0]), 0.7, places=5)

    def test_array_conversion(self):
        payload = make_tiff(np.full((20, 20), 7, dtype=np.float32))
        self.assertAlmostEqual(float(extract_single_band(payload, ".tif").mean()), 7)


if __name__ == "__main__":
    unittest.main()
