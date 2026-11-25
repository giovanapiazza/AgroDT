"""Testa preparacao de dois voos independentes com ZIPs locais (sem rede)."""
from contextlib import ExitStack
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import preparar_2_voos_zenodo as datasets


def tif(data):
    buffer = BytesIO()
    Image.fromarray(np.full((20, 20), data, dtype=np.uint16)).save(buffer, format="TIFF")
    return buffer.getvalue()


class TwoZenodoMissionsTests(unittest.TestCase):
    def test_independent_sources_and_manifests(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for mission in ("ADM3", "UFRGS"):
                base = folder / mission
                base.mkdir()
                for band in datasets.BANDS:
                    with ZipFile(base / (band + ".zip"), "w") as archive:
                        for n in range(1, 5):
                            archive.writestr(
                                f"raw/IMG_{mission}_{n:04d}_{band}.TIF", tif(10000 + n))
            for mission in ("ADM3", "UFRGS"):
                with ExitStack() as stack:
                    archives = datasets.open_sources(stack, mission, folder / mission)
                    dest = datasets.create_archive(archives, mission, 2, 3,
                                                   folder / (mission + ".zip"))
                with ZipFile(dest) as archive:
                    files = archive.namelist()
                    self.assertEqual(len([f for f in files if f.endswith(".TIF")]), 12)
                    manifest = json.loads(archive.read("ORIGEM_ZENODO.json"))
                    self.assertEqual(manifest["capture_count"], 3)
                    self.assertEqual(manifest["zenodo_record"],
                                     datasets.DATASETS[mission]["record"])
                    self.assertEqual(len(manifest["captures"]), 3)
            with ZipFile(folder / "ADM3.zip") as first, ZipFile(folder / "UFRGS.zip") as second:
                self.assertNotEqual(first.namelist(), second.namelist())

    def test_refuse_missing_captures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for band in datasets.BANDS:
                with ZipFile(root / (band + ".zip"), "w") as z:
                    z.writestr("IMG_0001_" + band + ".TIF", tif(10000))
            with ExitStack() as stack:
                archives = datasets.open_sources(stack, "ADM3", root)
                with self.assertRaises(ValueError):
                    datasets.create_archive(archives, "ADM3", 1, 30,
                                            root / "should_not_exist.zip")
                self.assertFalse((root / "should_not_exist.zip").exists())


if __name__ == "__main__":
    unittest.main()
