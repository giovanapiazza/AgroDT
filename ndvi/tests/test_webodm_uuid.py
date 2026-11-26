"""WebODM 4 pode retornar UUID para tarefas; jamais converter para int."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import webodm_ortomosaico as webodm


class WebODMIDTests(unittest.TestCase):
    UUID = "00f92c01-f412-40e5-815d-77358e7e6784"

    def test_project_numeric_and_task_uuid(self):
        with patch.object(webodm, "api_request", return_value={"id": 11}):
            self.assertEqual(webodm.project("token", "http://localhost:8000", "teste"), 11)
        with patch.object(webodm, "api_request", return_value={"id": self.UUID}):
            self.assertEqual(webodm.project("token", "http://localhost:8000", "teste"), self.UUID)

    def test_task_uuid_not_integer(self):
        with patch.object(webodm, "api_request", return_value={"id": self.UUID}):
            from tempfile import TemporaryDirectory
            with TemporaryDirectory() as directory:
                red = Path(directory) / "IMG_01_RED.TIF"
                nir = Path(directory) / "IMG_01_NIR.TIF"
                red.write_bytes(b"original RED")
                nir.write_bytes(b"original NIR")
                task_id = webodm.create_task("token", "http://localhost:8000", 11, [red, nir], "teste")
                self.assertEqual(task_id, self.UUID)
                self.assertIsInstance(task_id, str)

    def test_task_uuid_routes(self):
        with patch.object(webodm, "api_request", return_value={"status": 20}) as request:
            webodm.task_status("token", "http://localhost:8000", 11, self.UUID)
            self.assertIn(self.UUID, request.call_args.args[2])

    def test_invalid_identifiers_rejected(self):
        for value in ("../etc/passwd", "", "abc/def", None, False, 0):
            with self.subTest(value=value), self.assertRaises(webodm.WebODMError):
                webodm.parse_webodm_id(value, "tarefa")

    def test_existing_numeric_ids_supported(self):
        self.assertEqual(webodm.parse_webodm_id("22", "tarefa"), 22)
        self.assertEqual(webodm.parse_webodm_id(22, "tarefa"), 22)


if __name__ == "__main__":
    unittest.main()
