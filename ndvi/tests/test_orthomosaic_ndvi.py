"""Testes do NDVI georreferenciado calculado a partir de ortomosaicos multibanda."""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from orthomosaic_ndvi import (
    BandSelectionRequired, calculate_orthomosaic_ndvi, choose_bands
)

try:
    import rasterio
    from rasterio.transform import from_origin
except ImportError:
    rasterio = None


@unittest.skipUnless(rasterio, "Instale requirements-geo.txt para os testes GeoTIFF")
class OrthomosaicNDVITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder / "orthophoto.tif"

    def create(self, descriptions=("Green", "Red", "NIR", "Red Edge"), nodata=False):
        values = np.full((4, 24, 26), 100, dtype=np.float32)
        values[2] = 300
        if nodata:
            values[2, 0, 0] = -9999
        with rasterio.open(self.source, "w", driver="GTiff", count=4,
                           height=24, width=26, dtype="float32", nodata=-9999,
                           transform=from_origin(10, 20, .2, .2),
                           crs="EPSG:32722") as dst:
            for index, layer in enumerate(values, 1):
                dst.write(layer, index)
                if descriptions[index - 1]:
                    dst.set_band_description(index, descriptions[index - 1])

    def test_automatic_geotiff_and_heatmap(self):
        self.create()
        result = calculate_orthomosaic_ndvi(self.source, self.folder)
        self.assertAlmostEqual(result["mean_ndvi"], .5)
        self.assertEqual((result["red_band"], result["nir_band"]), (2, 3))
        self.assertTrue((self.folder / "ndvi_ortomosaico.png").is_file())
        with rasterio.open(self.folder / "ndvi_ortomosaico.tif") as src:
            self.assertEqual(src.crs.to_epsg(), 32722)
            self.assertAlmostEqual(float(src.read(1)[0, 1]), .5)

    def test_select_manually_when_metadata_absent(self):
        self.create((None, None, None, None))
        with self.assertRaises(BandSelectionRequired):
            calculate_orthomosaic_ndvi(self.source, self.folder)
        self.assertFalse((self.folder / "ndvi_ortomosaico.tif").exists())
        result = calculate_orthomosaic_ndvi(self.source, self.folder, 2, 3)
        self.assertEqual(result["selection_method"], "manual")

    def test_nodata_remains_invalid(self):
        self.create(nodata=True)
        result = calculate_orthomosaic_ndvi(self.source, self.folder)
        self.assertEqual(result["valid_pixels"], 24 * 26 - 1)
        with rasterio.open(self.folder / "ndvi_ortomosaico.tif") as src:
            self.assertEqual(float(src.read(1)[0, 0]), -9999)

    def test_invalid_indices(self):
        self.create()
        with self.assertRaises(ValueError):
            choose_bands(self.source, 2, 2)
        with self.assertRaises(ValueError):
            choose_bands(self.source, 10, 3)

    def test_rgb_only_not_ndvi(self):
        self.create(("Red", "Green", "Blue", "Alpha"))
        with self.assertRaises(BandSelectionRequired):
            choose_bands(self.source)


if __name__ == "__main__":
    unittest.main()
