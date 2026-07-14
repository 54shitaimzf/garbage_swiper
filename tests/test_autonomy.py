import json
import tempfile
import threading
import time
import unittest
from http.client import HTTPConnection

from autonomy.config import Registry
from autonomy.controller import MissionController, MissionError
from autonomy.server import AutonomyHTTPServer, AutonomyRequestHandler


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.controller = MissionController(
            registry=Registry(),
            mode="mock",
            mapping_output_dir=self.tmp.name,
            mock_duration_sec=0.02,
        )

    def tearDown(self):
        self.controller.shutdown()
        self.tmp.cleanup()

    def test_map_and_route_whitelists_are_read_only(self):
        self.assertEqual({"lab", "yahboomcar"}, {item["id"] for item in self.controller.list_maps()})
        self.assertIn("patrol_lab", {item["id"] for item in self.controller.list_routes()})
        with self.assertRaises(MissionError):
            self.controller.select_map("../../etc/passwd")

    def test_disabled_route_cannot_move(self):
        self.controller.activate()
        self.controller.select_map("lab")
        with self.assertRaises(MissionError):
            self.controller.start("patrol_lab")
        self.assertEqual("ready", self.controller.status()["state"])

    def test_mock_mapping_never_overwrites(self):
        self.controller.activate()
        self.controller.mapping_start()
        self.controller.mapping_stop()
        saved = self.controller.mapping_save("smoke_map")
        self.assertTrue(saved["saved_map"]["yaml"].endswith("smoke_map.yaml"))
        with self.assertRaises(MissionError):
            self.controller.mapping_save("smoke_map")


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        controller = MissionController(mapping_output_dir=self.tmp.name, mock_duration_sec=0.02)
        self.server = AutonomyHTTPServer(("127.0.0.1", 0), controller)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.controller.shutdown()
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def call(self, method, path, body=None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=2)
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"} if payload is not None else {}
        connection.request(method, path, payload, headers)
        response = connection.getresponse()
        data = json.loads(response.read().decode("utf-8"))
        connection.close()
        return response.status, data

    def test_health_maps_and_safe_api(self):
        status, payload = self.call("GET", "/healthz")
        self.assertEqual(200, status)
        self.assertEqual(8082, payload["port"])
        status, payload = self.call("GET", "/api/maps")
        self.assertEqual(200, status)
        self.assertEqual(2, len(payload["maps"]))
        status, payload = self.call("POST", "/api/mission/start", {"route_id": "patrol_lab"})
        self.assertEqual(409, status)
        self.assertFalse(payload["ok"])

    def test_static_page_does_not_require_legacy_gateway(self):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=2)
        connection.request("GET", "/")
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        connection.close()
        self.assertEqual(200, response.status)
        self.assertIn("自主任务控制台", body)
        self.assertIn("8081", body)


if __name__ == "__main__":
    unittest.main()
