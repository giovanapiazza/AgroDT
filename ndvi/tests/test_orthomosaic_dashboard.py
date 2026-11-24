"""Testes da orquestracao WebODM sem depender de servidor WebODM real."""
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import orthomosaic_dashboard as dashboard


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "storage"
        self.here = Path(self.tmp.name) / "ndvi"
        (self.here / "data" / "voo_01").mkdir(parents=True)
        for index in range(3):
            (self.here / "data" / "voo_01" / f"IMG_{index:04}.JPG").write_bytes(
                b"jpeg-original-" + str(index).encode())
        self.webodm = types.ModuleType("webodm_ortomosaico")
        self.webodm.collect_images = lambda folder: sorted(Path(folder).rglob("*.JPG")) or sorted(Path(folder).rglob("*.TIF"))
        self.webodm.authenticate = lambda *args: "token"
        self.webodm.project = lambda *args: 11
        self.webodm.create_task = lambda *args: 22
        self.webodm.task_status = lambda *args: {"status": 40}
        def download(*args):
            out = Path(args[-1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"TIFF-test")
        self.webodm.download_orthophoto = download
        self.catalog = types.ModuleType("orthomosaic_catalog")
        def preview(path):
            path.with_name("preview.png").write_bytes(b"PNG-test")
            return {"width": 80, "height": 90, "bands": 4, "crs": "EPSG:4326"}
        self.catalog.build_preview = preview
        self.patch_modules = patch.dict(sys.modules, {
            "webodm_ortomosaico": self.webodm, "orthomosaic_catalog": self.catalog})
        self.patch_modules.start()
        self.addCleanup(self.patch_modules.stop)
        self.patch_env = patch.dict(os.environ, {
            "WEBODM_USER": "local_user", "WEBODM_PASSWORD": "not-shared",
            "WEBODM_URL": "http://127.0.0.1:8000"})
        self.patch_env.start()
        self.addCleanup(self.patch_env.stop)

    def _wait(self, flight):
        thread = dashboard._workers.get(flight)
        if thread:
            thread.join(timeout=3)
        return dashboard.read_state(self.root, flight)

    def test_discover_and_process_local_flight(self):
        self.assertEqual(dashboard.list_sources(self.root, self.here), [
            {"flight_id": "voo_01", "source": "data", "images_count": 3}])
        dashboard.start_job(self.root, self.here, "voo_01")
        result = self._wait("voo_01")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["progress"], 100)
        self.assertEqual(result["task_id"], 22)
        self.assertEqual(result["bands"], 4)
        self.assertTrue((self.root / "ortomosaicos" / "voo_01" / "preview.png").exists())
        with self.assertRaises(ValueError):
            dashboard.start_job(self.root, self.here, "voo_01")

    def test_import_zip_preserves_bytes(self):
        pack = Path(self.tmp.name) / "images.zip"
        with zipfile.ZipFile(pack, "w") as archive:
            archive.writestr("dir/IMG_01.TIF", b"tif-original-EXIF-1")
            archive.writestr("dir/IMG_02.TIF", b"tif-original-EXIF-2")
            archive.writestr("README.txt", b"ignored")
        imported = dashboard.import_zip(pack, self.root, "voo_02")
        self.assertEqual(imported["images_count"], 2)
        self.assertEqual((self.root / "voos_originais" / "voo_02" /
                          "IMG_01.TIF").read_bytes(), b"tif-original-EXIF-1")
        self.assertEqual(len(dashboard.list_sources(self.root, self.here)), 2)
        dashboard.start_job(self.root, self.here, "voo_02", source="upload")
        self.assertEqual(self._wait("voo_02")["status"], "completed")

    def test_zip_traversal_and_duplicate_rejected(self):
        pack = Path(self.tmp.name) / "bad.zip"
        with zipfile.ZipFile(pack, "w") as archive:
            archive.writestr("../IMG_01.TIF", b"a")
            archive.writestr("IMG_02.TIF", b"b")
        with self.assertRaises(ValueError):
            dashboard.import_zip(pack, self.root, "bad_01")
        self.assertFalse((self.root / "voos_originais" / "bad_01").exists())
        with zipfile.ZipFile(pack, "w") as archive:
            archive.writestr("a/IMG_01.TIF", b"a")
            archive.writestr("b/IMG_01.TIF", b"b")
        with self.assertRaises(ValueError):
            dashboard.import_zip(pack, self.root, "bad_02")

    def test_resume_existing_remote_job(self):
        dashboard.save_state(self.root, "voo_01", status="processing",
                             project_id=11, task_id=22)
        dashboard.resume_jobs(self.root)
        self.assertEqual(self._wait("voo_01")["status"], "completed")

    def test_no_credentials_stored_or_exposed(self):
        dashboard.start_job(self.root, self.here, "voo_01")
        self._wait("voo_01")
        state = (self.root / "ortomosaicos" / "voo_01" /
                 "processamento.json").read_text()
        self.assertNotIn("not-shared", state)
        self.assertNotIn("local_user", state)

    def test_failed_upload_is_reported(self):
        self.webodm.authenticate = lambda *args: (
            _ for _ in ()).throw(ValueError("Credenciais rejeitadas"))
        dashboard.start_job(self.root, self.here, "voo_01")
        result = self._wait("voo_01")
        self.assertEqual(result["status"], "failed")
        self.assertIn("Credenciais rejeitadas", result["message"])


if __name__ == "__main__":
    unittest.main()
