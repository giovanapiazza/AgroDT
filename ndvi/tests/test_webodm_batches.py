"""Envio em lotes preserva uma tarefa unica e todas as imagens do voo."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import webodm_ortomosaico as webodm


class BatchUploadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.images = []
        for i in range(50):
            file = Path(self.temp.name) / f"IMG_{i:04}.tif"
            file.write_bytes(f"TIFF_{i}".encode())
            self.images.append(file)

    def test_large_mission_is_one_partial_task_and_three_batches(self):
        calls = []

        def request(method, base, endpoint, token=None, **kwargs):
            calls.append((method, endpoint, kwargs))
            if endpoint == "/api/projects/5/tasks/":
                return {"id": "00f92c01-f412-40e5-815d-77358e7e6784"}
            return {"status": "ok"}

        with patch.object(webodm, "api_request", side_effect=request):
            task_id = webodm.create_task("token", "http://localhost:8000", 5,
                                        self.images, "voo_teste")
        self.assertEqual(task_id, "00f92c01-f412-40e5-815d-77358e7e6784")
        self.assertEqual(len(calls), 5)
        self.assertEqual(calls[0][2]["data"]["partial"], "true")
        self.assertEqual([len(call[2]["files"]) for call in calls[1:4]], [24, 24, 2])
        self.assertTrue(all(call[1].endswith("/upload/") for call in calls[1:4]))
        self.assertTrue(calls[-1][1].endswith("/commit/"))
        filenames = [part[1][0] for call in calls[1:4] for part in call[2]["files"]]
        self.assertEqual(filenames, [p.name for p in self.images])

    def test_no_commit_if_upload_fails(self):
        calls = []

        def request(method, base, endpoint, token=None, **kwargs):
            calls.append(endpoint)
            if endpoint.endswith("/upload/"):
                raise webodm.WebODMError("HTTP 400")
            return {"id": "00f92c01-f412-40e5-815d-77358e7e6784"}

        with patch.object(webodm, "api_request", side_effect=request):
            with self.assertRaisesRegex(webodm.WebODMError, "Envio incompleto"):
                webodm.create_task("token", "http://localhost:8000", 5,
                                  self.images, "voo_teste")
        self.assertFalse(any(url.endswith("/commit/") for url in calls))

    def test_small_mission_keeps_single_request(self):
        with patch.object(webodm, "api_request",
                          return_value={"id": 42}) as req:
            task = webodm.create_task("token", "http://localhost:8000", 5,
                                     self.images[:2], "voo_teste")
        self.assertEqual(task, 42)
        self.assertEqual(req.call_count, 1)
        self.assertNotIn("partial", req.call_args.kwargs["data"])


if __name__ == "__main__":
    unittest.main()
