import unittest
from io import BytesIO

import numpy as np
from PIL import Image

from app import calculate_ndvi, detect_regions
from simular_drone import imagem_sintetica


class TestSimulacao(unittest.TestCase):
    def test_gera_par_valido_e_variavel(self):
        a = imagem_sintetica(1)
        b = imagem_sintetica(2)
        self.assertNotEqual(a[0], b[0])
        self.assertEqual(len(a), 2)
        red, nir = [np.array(Image.open(BytesIO(blob)), dtype=np.float32) for blob in a]
        self.assertEqual(red.shape, (120, 160))
        self.assertTrue(np.isfinite(calculate_ndvi(red, nir)).all())

    def test_detecta_manchas_simuladas(self):
        red, nir = [np.array(Image.open(BytesIO(blob)), dtype=np.float32) for blob in imagem_sintetica(1)]
        regions, _, _, _ = detect_regions(calculate_ndvi(red, nir))
        self.assertGreaterEqual(len(regions), 1)


if __name__ == "__main__":
    unittest.main()
