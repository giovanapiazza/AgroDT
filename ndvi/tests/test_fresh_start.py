"""Garante que cada inicializacao NDVI possa comecar vazia com backup seguro."""
from pathlib import Path
import tempfile
import unittest

from limpar_historico import archive_storage


class FreshStartTests(unittest.TestCase):
    def test_archive_removes_old_dashboard_data_but_preserves_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "armazenamento"
            (root / "dados").mkdir(parents=True)
            (root / "dados" / "capturas.sqlite3").write_bytes(b"sqlite-old")
            (root / "ortomosaicos" / "voo_antigo").mkdir(parents=True)
            (root / "ortomosaicos" / "voo_antigo" / "preview.png").write_bytes(b"old")
            preserved_source = Path(directory) / "data" / "voo_01" / "RED.tif"
            preserved_source.parent.mkdir(parents=True)
            preserved_source.write_bytes(b"original")
            backup = archive_storage(root)
            self.assertIsNotNone(backup)
            self.assertFalse(root.exists())
            self.assertEqual((backup / "dados" / "capturas.sqlite3").read_bytes(),
                             b"sqlite-old")
            self.assertTrue((backup / "ortomosaicos" / "voo_antigo" / "preview.png").exists())
            self.assertEqual(preserved_source.read_bytes(), b"original")
            root.mkdir()
            (root / "dados").mkdir()
            (root / "dados" / "capturas.sqlite3").write_bytes(b"new")
            second = archive_storage(root)
            self.assertNotEqual(second, backup)
            self.assertTrue(backup.exists())
            self.assertEqual((second / "dados" / "capturas.sqlite3").read_bytes(), b"new")

    def test_first_start_without_storage_does_not_create_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "armazenamento"
            self.assertIsNone(archive_storage(root))

    def test_symlink_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            real = base / "real"
            real.mkdir()
            link = base / "armazenamento"
            link.symlink_to(real, target_is_directory=True)
            with self.assertRaises(ValueError):
                archive_storage(link)
            self.assertTrue(real.exists())


if __name__ == "__main__":
    unittest.main()
