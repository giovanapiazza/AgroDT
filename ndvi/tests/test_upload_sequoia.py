"""Testes da importacao de ZIP Sequoia e dos novos mapas."""
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image
import app


def tiff_bytes(value):
    buffer = io.BytesIO()
    Image.fromarray(np.full((30, 40), value, dtype=np.uint16)).save(buffer, format="TIFF")
    return buffer.getvalue()


class UploadSequoiaTest(unittest.TestCase):
    def test_importa_pares_e_gera_heatmap(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(app, "ROOT", Path(tmp)):
            app.init_db()
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w") as z:
                for seq in ("0000", "0001"):
                    z.writestr(f"captura_{seq}_RED.TIF", tiff_bytes(9000))
                    z.writestr(f"captura_{seq}_NIR.TIF", tiff_bytes(51000))
                    z.writestr(f"captura_{seq}_REG.TIF", tiff_bytes(20000))
            result = app.import_sequoia_zip(archive.getvalue(), "teste_real")
            self.assertEqual(result["processed"], 2)
            self.assertEqual(result["failed"], 0)
            for capture in result["captures"]:
                folder = app.ROOT / "analisadas" / "teste_real" / capture["capture_id"]
                self.assertTrue((folder / "heatmap_ndvi.png").is_file())
                self.assertTrue((folder / "red_preview.png").is_file())
                self.assertTrue((folder / "nir_preview.png").is_file())
                self.assertTrue((folder / "originais" / "red.tif").is_file())
                self.assertTrue((folder / "originais" / "nir.tif").is_file())
                self.assertAlmostEqual(capture["mean_ndvi"], 0.7, places=3)

    def test_monitoramento_pasta_entrada(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(app, "ROOT", Path(tmp)):
            app.init_db()
            folder = app.ROOT / "entrada" / "voo_pasta" / "captura_teste"
            folder.mkdir(parents=True)
            (folder / "red.tif").write_bytes(tiff_bytes(9000))
            (folder / "nir.tif").write_bytes(tiff_bytes(51000))
            import os
            old = 1
            os.utime(folder / "red.tif", (old, old))
            os.utime(folder / "nir.tif", (old, old))
            app.register_manual_pairs()
            self.assertEqual(app.get_capture("captura_teste")["status"], "processed")


if __name__ == "__main__":
    unittest.main()
