from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path

from werkzeug.serving import make_server

from common.http_client import request_json
from gateway.app import create_app as create_gateway
from services.risk.app import create_app as create_risk, evaluate
from services.store.app import create_app as create_store, database


class LocalServer:
    def __init__(self, app):
        self.server = make_server("127.0.0.1", 0, app)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        if self.thread.is_alive():
            self.server.shutdown()
            self.thread.join(timeout=3)
        self.server.server_close()


class HorizonteTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary.name) / "horizonte.db"
        self.service_key = "test-service-key"
        self.device_key = "test-device-key"
        self.risk_server = LocalServer(create_risk(self.service_key))
        self.store_server = LocalServer(create_store(self.database_path, self.service_key))
        self.risk_server.start()
        self.store_server.start()
        self.gateway = create_gateway(
            self.store_server.url,
            self.risk_server.url,
            self.service_key,
            "test-session-secret",
            "operator-test-password",
            self.device_key,
        )
        self.client = self.gateway.test_client()

    def tearDown(self):
        self.store_server.stop()
        self.risk_server.stop()
        self.temporary.cleanup()

    def csrf(self) -> str:
        with self.client.session_transaction() as session:
            return session["csrf"]

    def login(self):
        self.client.get("/operacao")
        return self.client.post("/login", data={"csrf": self.csrf(), "password": "operator-test-password"})

    def test_risk_engine_is_explainable(self):
        normal = evaluate(24, 50)
        alert = evaluate(34, 70)
        self.assertEqual(normal["level"], "normal")
        self.assertEqual(alert["level"], "alerta")
        self.assertEqual(alert["algorithm_version"], "heat-index-v1")
        self.assertIn("experimental", alert["warning"])

    def test_operator_flow_crosses_services_and_audits(self):
        self.assertEqual(self.login().status_code, 302)
        measurement = self.client.post(
            "/operacao/medicoes",
            data={"csrf": self.csrf(), "zone": "Central", "source_type": "simulado", "temperature_c": "34", "humidity_pct": "70"},
            follow_redirects=True,
        )
        self.assertIn("Medição avaliada e registrada", measurement.get_data(as_text=True))
        bulletin = self.client.post(
            "/operacao/boletins",
            data={"csrf": self.csrf(), "zone": "Central", "title": "Pausa no período mais quente", "guidance": "Priorize sombra e hidratação; acompanhe os canais oficiais."},
            follow_redirects=True,
        )
        self.assertIn("Boletim publicado", bulletin.get_data(as_text=True))
        dashboard = self.client.get("/").get_data(as_text=True)
        self.assertIn("alerta", dashboard)
        self.assertIn("Pausa no período mais quente", dashboard)
        with database(self.database_path) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM readings").fetchone()[0], 1)
            self.assertGreaterEqual(connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0], 3)

    def test_device_contract_is_authenticated_and_idempotent(self):
        payload = {
            "schema_version": 1,
            "device_id": "sentinela-01",
            "boot_id": "a1b2c3d4",
            "sequence": 7,
            "observed_at": int(time.time()),
            "temperature_c_filtered": 31.5,
            "humidity_pct_filtered": 68.0,
            "zone": "Norte",
        }
        self.assertEqual(self.client.post("/api/device/readings", json=payload).status_code, 401)
        first = self.client.post("/api/device/readings", json=payload, headers={"X-Device-Key": self.device_key})
        duplicate = self.client.post("/api/device/readings", json=payload, headers={"X-Device-Key": self.device_key})
        self.assertEqual(first.status_code, 201)
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(duplicate.get_json()["status"], "duplicate")
        with database(self.database_path) as connection:
            connection.execute("UPDATE readings SET received_at = '2024-01-01T00:00:00+00:00'")
        self.assertIn("A última leitura venceu", self.client.get("/").get_data(as_text=True))

    def test_store_rejects_non_numeric_internal_measurement(self):
        payload = {
            "event_id": "bad-value-1", "source_type": "simulado", "zone": "Sul",
            "observed_at": "2026-08-11T12:00:00+00:00", "temperature_c": "quente",
            "humidity_pct": 60, "heat_index_c": 30, "risk_level": "normal",
            "algorithm_version": "heat-index-v1",
        }
        status, body = request_json(self.store_server.url, "/v1/readings", self.service_key, "POST", payload)
        self.assertEqual(status, 422)
        self.assertIn("números finitos", body["error"])

    def test_login_requires_csrf_and_valid_password(self):
        self.client.get("/operacao")
        self.assertEqual(self.client.post("/login", data={"password": "operator-test-password"}).status_code, 400)
        denied = self.client.post("/login", data={"csrf": self.csrf(), "password": "wrong"}, follow_redirects=True)
        self.assertIn("Credencial inválida", denied.get_data(as_text=True))

    def test_health_and_security_headers(self):
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertTrue(all(health.get_json()["dependencies"].values()))
        dashboard = self.client.get("/")
        self.assertIn("frame-ancestors", dashboard.headers["Content-Security-Policy"])
        self.assertNotIn("style=", dashboard.get_data(as_text=True))

    def test_public_page_degrades_when_store_is_unavailable(self):
        unavailable = create_gateway("http://127.0.0.1:1", self.risk_server.url, self.service_key, "secret", "password", self.device_key).test_client()
        page = unavailable.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("DADOS TEMPORARIAMENTE INDISPONÍVEIS", page.get_data(as_text=True))
        self.assertEqual(unavailable.get("/api/status").status_code, 503)

    def device_payload(self, sequence=40, zone="Central"):
        return {"schema_version": 1, "device_id": "sentinela-test-01", "boot_id": "a1b2c3d4",
                "sequence": sequence, "observed_at": int(time.time()),
                "temperature_c_filtered": 30, "humidity_pct_filtered": 60, "zone": zone}

    def post_device(self, payload, key=None):
        return self.client.post("/api/device/readings", json=payload,
                                headers={"X-Device-Key": self.device_key if key is None else key})

    def test_device_sequence_conflict_is_rejected_without_replacing_data(self):
        payload = self.device_payload()
        self.assertEqual(self.post_device(payload).status_code, 201)
        self.assertEqual(self.post_device({**payload, "temperature_c_filtered": 35}).status_code, 409)
        with database(self.database_path) as connection:
            self.assertEqual(connection.execute("SELECT temperature_c FROM readings").fetchone()[0], 30)

    def test_stored_retry_can_be_confirmed_while_risk_service_is_unavailable(self):
        payload = self.device_payload()
        first = self.post_device(payload).get_json()
        self.risk_server.stop()
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 503)
        self.assertFalse(health.get_json()["dependencies"]["risk"])
        duplicate = self.post_device(payload)
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(duplicate.get_json()["id"], first["id"])

    def test_device_types_are_strict_and_do_not_cause_internal_errors(self):
        for field, values in {"schema_version": (True, 1.0), "observed_at": (True, "1", 1.5, 10**500),
                              "zone": ([], {}), "temperature_c_filtered": (10**500, float("inf"))}.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    self.assertEqual(self.post_device({**self.device_payload(), field: value}).status_code, 422)

    def test_unicode_credentials_and_csrf_are_controlled_failures(self):
        self.assertEqual(self.post_device(self.device_payload(), key="inválida").status_code, 401)
        self.client.get("/operacao")
        self.assertEqual(self.client.post("/login", data={"csrf": "inválido", "password": "wrong"}).status_code, 400)
        denied = self.client.post("/login", data={"csrf": self.csrf(), "password": "inválida"}, follow_redirects=True)
        self.assertEqual(denied.status_code, 200)
        self.assertIn("Credencial inválida", denied.get_data(as_text=True))

    def test_old_observation_is_unavailable_even_if_it_just_arrived(self):
        payload = self.device_payload()
        payload["observed_at"] -= 600
        self.assertEqual(self.post_device(payload).status_code, 201)
        self.assertIn("A última leitura venceu", self.client.get("/").get_data(as_text=True))

    def test_delayed_delivery_does_not_replace_a_newer_zone_observation(self):
        newest = self.device_payload(40)
        oldest = {**self.device_payload(41), "observed_at": newest["observed_at"] - 600}
        self.assertEqual(self.post_device(newest).status_code, 201)
        self.assertEqual(self.post_device(oldest).status_code, 201)
        snapshot = self.client.get("/api/status").get_json()
        self.assertEqual(snapshot["latest_readings"][0]["event_id"], "sentinela-test-01:a1b2c3d4:40")
        self.assertNotIn("A última leitura venceu", self.client.get("/").get_data(as_text=True))

    def test_simulator_source_is_explicit_and_preserved(self):
        payload = {**self.device_payload(), "source_type": "simulado"}
        self.assertEqual(self.post_device(payload).status_code, 201)
        snapshot = self.client.get("/api/status").get_json()
        self.assertEqual(snapshot["readings"][0]["source_type"], "simulado")

    def test_oversized_device_body_is_a_controlled_rejection(self):
        response = self.client.post("/api/device/readings", data=" " * 9000,
                                    content_type="application/json", headers={"X-Device-Key": self.device_key})
        self.assertEqual(response.status_code, 413)
        self.assertIsInstance(response.get_json(), dict)


if __name__ == "__main__":
    unittest.main()
