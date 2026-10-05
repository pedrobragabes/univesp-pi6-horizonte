from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from flask import Flask, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge
from common.validation import bounded_number, one_of, require_recent, secret_matches, utc_instant

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE = ROOT / "data" / "horizonte.db"
DEFAULT_SERVICE_KEY = "development-service-key"
ZONES = {"Norte", "Central", "Sul"}
EVENT_PATTERN = re.compile(r"^[A-Za-z0-9:_-]{1,140}$")
ALGORITHM_PATTERN = re.compile(r"^[a-z0-9-]{3,40}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL UNIQUE,
  source_type TEXT NOT NULL,
  zone TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  received_at TEXT NOT NULL,
  temperature_c REAL NOT NULL,
  humidity_pct REAL NOT NULL,
  heat_index_c REAL NOT NULL,
  risk_level TEXT NOT NULL,
  algorithm_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bulletins (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  zone TEXT NOT NULL,
  title TEXT NOT NULL,
  guidance TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_type TEXT NOT NULL,
  actor_role TEXT NOT NULL,
  outcome TEXT NOT NULL,
  occurred_at TEXT NOT NULL
);
"""


@contextmanager
def database(path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def create_app(database_path: Path = DEFAULT_DATABASE, service_key: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(DATABASE=Path(database_path), SERVICE_KEY=service_key or os.getenv("HORIZONTE_SERVICE_KEY", DEFAULT_SERVICE_KEY), MAX_CONTENT_LENGTH=8192)
    app.config["DATABASE"].parent.mkdir(parents=True, exist_ok=True)
    with database(app.config["DATABASE"]) as connection:
        connection.executescript(SCHEMA)

    def authorized() -> bool:
        return secret_matches(request.headers.get("X-Service-Key", ""), app.config["SERVICE_KEY"])

    @app.errorhandler(RequestEntityTooLarge)
    def oversized_body(_error):
        return jsonify({"error": "Mensagem excede o limite de 8192 bytes."}), 413

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "store"})

    @app.get("/v1/snapshot")
    def snapshot():
        if not authorized():
            return jsonify({"error": "Serviço não autorizado."}), 401
        with database(app.config["DATABASE"]) as connection:
            readings = connection.execute("SELECT * FROM readings ORDER BY id DESC LIMIT 30").fetchall()
            latest = connection.execute(
                """SELECT * FROM (
                    SELECT r.*, ROW_NUMBER() OVER (PARTITION BY zone
                        ORDER BY julianday(observed_at) DESC, received_at DESC, id DESC) AS rank
                    FROM readings r
                ) WHERE rank = 1 ORDER BY zone"""
            ).fetchall()
            bulletins = connection.execute("SELECT * FROM bulletins ORDER BY id DESC LIMIT 10").fetchall()
        latest_readings = [{key: row[key] for key in row.keys() if key != "rank"} for row in latest]
        return jsonify({"readings": [dict(row) for row in readings], "latest_readings": latest_readings,
                        "bulletins": [dict(row) for row in bulletins]})

    @app.get("/v1/readings/<event_id>")
    def stored_reading(event_id):
        if not authorized():
            return jsonify({"error": "Serviço não autorizado."}), 401
        if not EVENT_PATTERN.fullmatch(event_id):
            return jsonify({"error": "Identificador de evento inválido."}), 422
        with database(app.config["DATABASE"]) as connection:
            row = connection.execute("SELECT * FROM readings WHERE event_id = ?", (event_id,)).fetchone()
        if row is None:
            return jsonify({"error": "Evento não encontrado."}), 404
        return jsonify(dict(row))

    @app.post("/v1/readings")
    def add_reading():
        if not authorized():
            return jsonify({"error": "Serviço não autorizado."}), 401
        payload = request.get_json(silent=True)
        required = {"event_id", "source_type", "zone", "observed_at", "temperature_c", "humidity_pct", "heat_index_c", "risk_level", "algorithm_version"}
        if not isinstance(payload, dict) or set(payload) != required or not one_of(payload.get("zone"), ZONES):
            return jsonify({"error": "Contrato de leitura inválido."}), 422
        if not one_of(payload["source_type"], {"simulado", "experimental", "hardware"}) or not one_of(payload["risk_level"], {"normal", "atencao", "alerta"}):
            return jsonify({"error": "Origem ou nível inválido."}), 422
        try:
            for field, minimum, maximum in (("temperature_c", -20, 60), ("humidity_pct", 0, 100), ("heat_index_c", -20, 100)):
                payload[field] = bounded_number(payload[field], minimum, maximum)
        except ValueError:
            return jsonify({"error": "Medições devem ser números finitos nas faixas aceitas."}), 422
        if not isinstance(payload["event_id"], str) or not EVENT_PATTERN.fullmatch(payload["event_id"]):
            return jsonify({"error": "Identificador de evento inválido."}), 422
        if not isinstance(payload["algorithm_version"], str) or not ALGORITHM_PATTERN.fullmatch(payload["algorithm_version"]):
            return jsonify({"error": "Versão de algoritmo inválida."}), 422
        try:
            observed = utc_instant(payload["observed_at"])
            payload["observed_at"] = observed.isoformat()
            with database(app.config["DATABASE"]) as connection:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute("SELECT * FROM readings WHERE event_id = ?", (payload["event_id"],)).fetchone()
                if existing is not None:
                    # Existing databases may contain a different ISO UTC offset.
                    original = dict(existing)
                    original["observed_at"] = utc_instant(original["observed_at"]).isoformat()
                    if any(original[field] != value for field, value in payload.items()):
                        return jsonify({"status": "conflict", "error": "Evento já utilizado por outra leitura."}), 409
                    return jsonify({"id": existing["id"], "status": "duplicate", "event_id": payload["event_id"]}), 200
                require_recent(observed)
                cursor = connection.execute(
                    """INSERT INTO readings(event_id,source_type,zone,observed_at,received_at,temperature_c,humidity_pct,heat_index_c,risk_level,algorithm_version)
                    VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (payload["event_id"], payload["source_type"], payload["zone"], payload["observed_at"], datetime.now(timezone.utc).isoformat(), payload["temperature_c"], payload["humidity_pct"], payload["heat_index_c"], payload["risk_level"], payload["algorithm_version"]),
                )
                reading_id = cursor.lastrowid
        except ValueError:
            return jsonify({"error": "Data de observação inválida ou fora da janela."}), 422
        return jsonify({"id": reading_id, "status": "accepted", "event_id": payload["event_id"]}), 201

    @app.post("/v1/bulletins")
    def add_bulletin():
        if not authorized():
            return jsonify({"error": "Serviço não autorizado."}), 401
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or set(payload) != {"zone", "title", "guidance"} or not one_of(payload.get("zone"), ZONES):
            return jsonify({"error": "Contrato de boletim inválido."}), 422
        if not all(isinstance(payload[field], str) and 3 <= len(payload[field].strip()) <= limit for field, limit in (("title", 100), ("guidance", 400))):
            return jsonify({"error": "Título ou orientação fora do limite."}), 422
        with database(app.config["DATABASE"]) as connection:
            cursor = connection.execute(
                "INSERT INTO bulletins(zone,title,guidance,created_at) VALUES(?,?,?,?)",
                (payload["zone"], payload["title"].strip(), payload["guidance"].strip(), datetime.now(timezone.utc).isoformat()),
            )
        return jsonify({"id": cursor.lastrowid, "status": "accepted"}), 201

    @app.post("/v1/audit")
    def audit():
        if not authorized():
            return jsonify({"error": "Serviço não autorizado."}), 401
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or set(payload) != {"event_type", "actor_role", "outcome"}:
            return jsonify({"error": "Contrato de auditoria inválido."}), 422
        values = [payload[field] for field in ("event_type", "actor_role", "outcome")]
        if not all(isinstance(value, str) and 1 <= len(value) <= 80 for value in values):
            return jsonify({"error": "Evento de auditoria inválido."}), 422
        with database(app.config["DATABASE"]) as connection:
            connection.execute(
                "INSERT INTO audit_events(event_type,actor_role,outcome,occurred_at) VALUES(?,?,?,?)",
                (*values, datetime.now(timezone.utc).isoformat()),
            )
        return jsonify({"status": "accepted"}), 201

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=3012, debug=False)
