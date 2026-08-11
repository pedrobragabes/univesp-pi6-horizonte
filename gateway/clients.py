from __future__ import annotations

from common.http_client import request_json


class StoreClient:
    def __init__(self, base_url: str, service_key: str):
        self.base_url = base_url
        self.service_key = service_key

    def snapshot(self) -> dict:
        status, body = request_json(self.base_url, "/v1/snapshot", self.service_key)
        if status != 200:
            raise RuntimeError(body.get("error", "Falha no serviço de registro."))
        return body

    def add_reading(self, payload: dict) -> tuple[int, dict]:
        return request_json(self.base_url, "/v1/readings", self.service_key, "POST", payload)

    def add_bulletin(self, payload: dict) -> tuple[int, dict]:
        return request_json(self.base_url, "/v1/bulletins", self.service_key, "POST", payload)

    def audit(self, event_type: str, actor_role: str, outcome: str) -> None:
        request_json(self.base_url, "/v1/audit", self.service_key, "POST", {"event_type": event_type, "actor_role": actor_role, "outcome": outcome})

    def health(self) -> bool:
        status, body = request_json(self.base_url, "/health", self.service_key)
        return status == 200 and body.get("status") == "ok"


class RiskClient:
    def __init__(self, base_url: str, service_key: str):
        self.base_url = base_url
        self.service_key = service_key

    def evaluate(self, temperature_c: float, humidity_pct: float) -> dict:
        status, body = request_json(
            self.base_url,
            "/v1/evaluate",
            self.service_key,
            "POST",
            {"temperature_c": temperature_c, "humidity_pct": humidity_pct},
        )
        if status != 200:
            raise ValueError(body.get("error", "Avaliação recusada."))
        return body

    def health(self) -> bool:
        status, body = request_json(self.base_url, "/health", self.service_key)
        return status == 200 and body.get("status") == "ok"
