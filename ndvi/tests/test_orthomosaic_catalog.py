"""Testes de catalogo WebODM sem exigir servidor WebODM instalado."""
import json
from pathlib import Path
import tempfile
import unittest

from orthomosaic_catalog import list_mosaics


class OrthomosaicCatalogTests(unittest.TestCase):
    def test_catalogo_vazio(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(list_mosaics(Path(directory)), [])

    def test_catalogo_com_voo_e_metadados(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "ortomosaicos" / "voo_01"
            folder.mkdir(parents=True)
            (folder / "orthophoto.tif").write_bytes(b"mock")
            (folder / "preview.png").write_bytes(b"mock")
            (folder / "webodm_tarefa.json").write_text(
                json.dumps({"project_id": 2, "task_id": 7, "images_count": 24}), encoding="utf-8")
            (folder / "ortomosaico_info.json").write_text(
                json.dumps({"width": 500, "height": 600, "bands": 5, "crs": "EPSG:32722"}), encoding="utf-8")
            result = list_mosaics(Path(directory))
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["flight_id"], "voo_01")
            self.assertTrue(result[0]["has_preview"])
            self.assertTrue(result[0]["has_orthophoto"])
            self.assertEqual(result[0]["bands"], 5)
            self.assertEqual(result[0]["task_id"], 7)

    def test_ignorar_nomes_invalidos(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "ortomosaicos" / "voo com espacos"
            folder.mkdir(parents=True)
            self.assertEqual(list_mosaics(Path(directory)), [])


if __name__ == "__main__":
    unittest.main()
