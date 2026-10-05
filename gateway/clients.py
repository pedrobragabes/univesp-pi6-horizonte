from __future__ import annotations

import re
from urllib.parse import quote

from common.http_client import ServiceUnavailable, request_json
from common.validation import bounded_number, one_of, utc_instant

ZONES = {"Norte", "Central", "Sul"}
EVENT_PATTERN = re.compile(r"^[A-Za-z0-9:_-]{1,140}$")
ALGORITHM_PATTERN = re.compile(r"^[a-z0-9-]{3,40}$")


def stored_reading(value: object) -> dict:
    if not isinstance(value, dict) or type(value.get("id")) is not int or value["id"] <= 0:
        raise ValueError("Leitura interna inválida.")
    item = dict(value)
    if not isinstance(item.get("event_id"), str) or not EVENT_PATTERN.fullmatch(item["event_id"]):
        raise ValueError("Evento interno inválido.")
    for field, choices in (("zone", ZONES), ("source_type", {"simulado", "experimental", "hardware"}),
                           ("risk_level", {"normal", "atencao", "alerta"})):
        if not one_of(item.get(field), choices):
            raise ValueError("Estado interno inválido.")
    if not isinstance(item.get("algorithm_version"), str) or not ALGORITHM_PATTERN.fullmatch(item["algorithm_version"]):
        raise ValueError("Versão interna inválida.")
    for field, lower, upper in (("temperature_c", -20, 60), ("humidity_pct", 0, 100), ("heat_index_c", -20, 100)):
        item[field] = bounded_number(item[field], lower, upper)
    for field in ("observed_at", "received_at"):
        item[field] = utc_instant(item[field]).isoformat()
    return item


def valid_receipt(status: int, body: dict, event_id: str | None = None) -> bool:
    expected = "accepted" if status == 201 else "duplicate"
    return (status in {200, 201} and type(body.get("id")) is int and body["id"] > 0
            and body.get("status") == expected
            and (event_id is None or body.get("event_id") == event_id))


class StoreClient:
    def __init__(self, base_url: str, service_key: str):
        self.base_url = base_url
        self.service_key = service_key

    def snapshot(self) -> dict:
        status, body = request_json(self.base_url, "/v1/snapshot", self.service_key)
        if status != 200:
            raise ServiceUnavailable("Falha no serviço de registro.")
        try:
            if not all(isinstance(body.get(field), list) for field in ("readings", "latest_readings", "bulletins")):
                raise ValueError
            if len(body["readings"]) > 30 or len(body["latest_readings"]) > 3 or len(body["bulletins"]) > 10:
                raise ValueError
            readings = [stored_reading(item) for item in body["readings"]]
            latest = [stored_reading(item) for item in body["latest_readings"]]
            if len({row["zone"] for row in latest}) != len(latest):
                raise ValueError
            bulletins = []
            for bulletin in body["bulletins"]:
                if not isinstance(bulletin, dict) or type(bulletin.get("id")) is not int or bulletin["id"] <= 0:
                    raise ValueError
                if not one_of(bulletin.get("zone"), ZONES):
                    raise ValueError
                if not all(isinstance(bulletin.get(field), str) and 3 <= len(bulletin[field]) <= limit
                           for field, limit in (("title", 100), ("guidance", 400))):
                    raise ValueError
                bulletins.append({**bulletin, "created_at": utc_instant(bulletin["created_at"]).isoformat()})
            return {"readings": readings, "latest_readings": latest, "bulletins": bulletins}
        except (ValueError, KeyError, TypeError) as error:
            raise ServiceUnavailable("Resposta inválida do serviço de registro.") from error

    def find_event(self, event_id: str) -> dict | None:
        status, body = request_json(self.base_url, "/v1/readings/" + quote(event_id, safe=""), self.service_key)
        if status == 404:
            return None
        if status != 200:
            raise ServiceUnavailable("Falha ao consultar o evento.")
        try:
            item = stored_reading(body)
            if item["event_id"] != event_id:
                raise ValueError
            return item
        except (ValueError, KeyError, TypeError) as error:
            raise ServiceUnavailable("Resposta inválida do serviço de registro.") from error

    def add_reading(self, payload: dict) -> tuple[int, dict]:
        status, body = request_json(self.base_url, "/v1/readings", self.service_key, "POST", payload)
        if status == 409:
            return 409, {"status": "conflict", "error": "Evento já utilizado por outra leitura."}
        if status in {400, 422}:
            return status, {"error": "Leitura recusada pelo contrato de registro."}
        if status not in {200, 201}:
            raise ServiceUnavailable("Serviço de registro temporariamente indisponível.")
        if status in {200, 201} and not valid_receipt(status, body, payload["event_id"]):
            raise ServiceUnavailable("Recibo inválido do serviço de registro.")
        return status, body

    def add_bulletin(self, payload: dict) -> tuple[int, dict]:
        status, body = request_json(self.base_url, "/v1/bulletins", self.service_key, "POST", payload)
        if status in {400, 422}:
            return status, {"error": "Título, orientação ou zona inválidos."}
        if status != 201:
            raise ServiceUnavailable("Serviço de registro temporariamente indisponível.")
        if status == 201 and not valid_receipt(status, body):
            raise ServiceUnavailable("Recibo inválido do boletim.")
        return status, body

    def audit(self, event_type: str, actor_role: str, outcome: str) -> None:
        status, body = request_json(self.base_url, "/v1/audit", self.service_key, "POST", {"event_type": event_type, "actor_role": actor_role, "outcome": outcome})
        if status != 201 or body.get("status") != "accepted":
            raise ServiceUnavailable("Auditoria não confirmada.")

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
        if 400 <= status < 500:
            raise ValueError("Medição recusada pelo serviço de avaliação.")
        if status != 200:
            raise ServiceUnavailable("Serviço de avaliação temporariamente indisponível.")
        try:
            if not one_of(body.get("level"), {"normal", "atencao", "alerta"}):
                raise ValueError
            bounded_number(body["heat_index_c"], -20, 100)
            if not isinstance(body.get("algorithm_version"), str) or not ALGORITHM_PATTERN.fullmatch(body["algorithm_version"]):
                raise ValueError
            if not all(isinstance(body.get(field), str) and body[field] for field in ("warning", "explanation")):
                raise ValueError
            if not isinstance(body.get("actions"), list) or not 1 <= len(body["actions"]) <= 10 or not all(isinstance(action, str) and 1 <= len(action) <= 120 for action in body["actions"]):
                raise ValueError
        except (ValueError, KeyError, TypeError) as error:
            raise ServiceUnavailable("Resposta inválida do serviço de avaliação.") from error
        return body

    def health(self) -> bool:
        status, body = request_json(self.base_url, "/health", self.service_key)
        return status == 200 and body.get("status") == "ok"
