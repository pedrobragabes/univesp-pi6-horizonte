from __future__ import annotations

import os
import re
import secrets
import uuid
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.exceptions import RequestEntityTooLarge

from common.http_client import ServiceUnavailable
from gateway.clients import RiskClient, StoreClient
from common.validation import bounded_number, one_of, require_recent, secret_matches

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SECRET = "development-session-secret"
DEFAULT_OPERATOR_PASSWORD = "change-me"
DEFAULT_DEVICE_KEY = "development-device-key"
ZONES = {"Norte", "Central", "Sul"}
DEVICE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,39}$")
BOOT_PATTERN = re.compile(r"^[0-9a-f]{8}$")


def create_app(
    store_url: str | None = None,
    risk_url: str | None = None,
    service_key: str | None = None,
    secret_key: str | None = None,
    operator_password: str | None = None,
    device_key: str | None = None,
) -> Flask:
    app = Flask(__name__, template_folder=str(ROOT / "templates"), static_folder=str(ROOT / "static"))
    app.config.update(
        SECRET_KEY=secret_key or os.getenv("HORIZONTE_SESSION_SECRET", DEFAULT_SECRET),
        OPERATOR_PASSWORD=operator_password or os.getenv("HORIZONTE_OPERATOR_PASSWORD", DEFAULT_OPERATOR_PASSWORD),
        DEVICE_KEY=device_key or os.getenv("HORIZONTE_DEVICE_KEY", DEFAULT_DEVICE_KEY),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=8192,
    )
    internal_key = service_key or os.getenv("HORIZONTE_SERVICE_KEY", "development-service-key")
    app.config["DEVELOPMENT_CONFIG"] = (
        app.config["SECRET_KEY"] == DEFAULT_SECRET
        or app.config["OPERATOR_PASSWORD"] == DEFAULT_OPERATOR_PASSWORD
        or app.config["DEVICE_KEY"] == DEFAULT_DEVICE_KEY
        or internal_key == "development-service-key"
    )
    store = StoreClient(store_url or os.getenv("HORIZONTE_STORE_URL", "http://127.0.0.1:3012"), internal_key)
    risk = RiskClient(risk_url or os.getenv("HORIZONTE_RISK_URL", "http://127.0.0.1:3011"), internal_key)

    @app.errorhandler(RequestEntityTooLarge)
    def oversized_body(_error):
        return jsonify({"error": "Mensagem excede o limite de 8192 bytes."}), 413

    @app.after_request
    def security_headers(response):
        response.headers["Content-Security-Policy"] = "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; img-src 'self' data:; object-src 'none'; style-src 'self'; form-action 'self'"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    def csrf_token() -> str:
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(24)
        return session["csrf"]

    app.jinja_env.globals["csrf_token"] = csrf_token

    def valid_csrf() -> bool:
        supplied = request.form.get("csrf", "")
        expected = session.get("csrf", "")
        return bool(expected) and secret_matches(supplied, expected)

    def operator_required(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            if session.get("role") != "operator":
                return redirect(url_for("operation"))
            return function(*args, **kwargs)
        return wrapped

    def safe_audit(event_type: str, role: str, outcome: str) -> None:
        try:
            store.audit(event_type, role, outcome)
        except (ServiceUnavailable, RuntimeError):
            pass

    @app.get("/")
    def home():
        unavailable = False
        try:
            snapshot = store.snapshot()
        except (ServiceUnavailable, RuntimeError):
            snapshot = {"readings": [], "latest_readings": [], "bulletins": []}
            unavailable = True
        latest_by_zone = {}
        for reading in snapshot["latest_readings"]:
            if reading["zone"] in latest_by_zone:
                continue
            item = dict(reading)
            received_at = datetime.fromisoformat(item["received_at"])
            now = datetime.now(timezone.utc)
            item["age_seconds"] = max(0, int((now - received_at).total_seconds()))
            observation_age = int((now - datetime.fromisoformat(item["observed_at"])).total_seconds())
            item["observation_age_seconds"] = max(0, observation_age)
            item["future"] = observation_age < -300
            if item["age_seconds"] > 300 or abs(observation_age) > 300:
                item["risk_level"] = "indisponivel"
                item["stale"] = True
            latest_by_zone[item["zone"]] = item
        return render_template(
            "dashboard.html",
            zones=[latest_by_zone.get(zone, {"zone": zone, "risk_level": "indisponivel"}) for zone in sorted(ZONES)],
            bulletins=snapshot["bulletins"],
            unavailable=unavailable,
        )

    @app.route("/operacao", methods=["GET"])
    def operation():
        return render_template(
            "operation.html",
            authenticated=session.get("role") == "operator",
            development=app.config["DEVELOPMENT_CONFIG"],
            zones=sorted(ZONES),
        )

    @app.post("/login")
    def login():
        if not valid_csrf():
            return "CSRF inválido", 400
        if not secret_matches(request.form.get("password", ""), app.config["OPERATOR_PASSWORD"]):
            safe_audit("operator_login", "anonymous", "denied")
            flash("Credencial inválida.", "error")
            return redirect(url_for("operation"))
        session["role"] = "operator"
        session["csrf"] = secrets.token_urlsafe(24)
        safe_audit("operator_login", "operator", "success")
        return redirect(url_for("operation"))

    @app.post("/logout")
    @operator_required
    def logout():
        if not valid_csrf():
            return "CSRF inválido", 400
        safe_audit("operator_logout", "operator", "success")
        session.clear()
        return redirect(url_for("home"))

    @app.post("/operacao/medicoes")
    @operator_required
    def add_measurement():
        if not valid_csrf():
            return "CSRF inválido", 400
        try:
            zone = request.form["zone"]
            source_type = request.form["source_type"]
            if zone not in ZONES or source_type not in {"simulado", "experimental"}:
                raise ValueError("Zona ou origem inválida.")
            temperature = float(request.form["temperature_c"])
            humidity = float(request.form["humidity_pct"])
            assessment = risk.evaluate(temperature, humidity)
            status, body = store.add_reading({
                "event_id": uuid.uuid4().hex,
                "source_type": source_type,
                "zone": zone,
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "temperature_c": temperature,
                "humidity_pct": humidity,
                "heat_index_c": assessment["heat_index_c"],
                "risk_level": assessment["level"],
                "algorithm_version": assessment["algorithm_version"],
            })
            if status not in {200, 201}:
                raise RuntimeError(body.get("error", "Registro recusado."))
        except (KeyError, ValueError, RuntimeError, ServiceUnavailable) as error:
            safe_audit("measurement_create", "operator", "failed")
            flash(str(error), "error")
            return redirect(url_for("operation"))
        safe_audit("measurement_create", "operator", "success")
        flash("Medição avaliada e registrada.", "success")
        return redirect(url_for("operation"))

    @app.post("/operacao/boletins")
    @operator_required
    def add_bulletin():
        if not valid_csrf():
            return "CSRF inválido", 400
        try:
            status, body = store.add_bulletin({"zone": request.form["zone"], "title": request.form["title"], "guidance": request.form["guidance"]})
            if status != 201:
                raise RuntimeError(body.get("error", "Boletim recusado."))
        except (KeyError, RuntimeError, ServiceUnavailable) as error:
            safe_audit("bulletin_create", "operator", "failed")
            flash(str(error), "error")
            return redirect(url_for("operation"))
        safe_audit("bulletin_create", "operator", "success")
        flash("Boletim publicado.", "success")
        return redirect(url_for("operation"))

    @app.post("/api/device/readings")
    def device_reading():
        if not secret_matches(request.headers.get("X-Device-Key", ""), app.config["DEVICE_KEY"]):
            return jsonify({"error": "Dispositivo não autorizado."}), 401
        payload = request.get_json(silent=True)
        required = {"schema_version", "device_id", "boot_id", "sequence", "observed_at", "temperature_c_filtered", "humidity_pct_filtered", "zone"}
        if (not isinstance(payload, dict) or not required <= set(payload) <= required | {"source_type"}
                or type(payload.get("schema_version")) is not int or payload.get("schema_version") != 1
                or not one_of(payload.get("zone"), ZONES)):
            return jsonify({"error": "Contrato do dispositivo inválido."}), 422
        try:
            if not isinstance(payload["device_id"], str) or not DEVICE_PATTERN.fullmatch(payload["device_id"]):
                raise ValueError("Identificador do dispositivo inválido.")
            if not isinstance(payload["boot_id"], str) or not BOOT_PATTERN.fullmatch(payload["boot_id"]):
                raise ValueError("Identificador de inicialização inválido.")
            if isinstance(payload["sequence"], bool) or not isinstance(payload["sequence"], int) or not 0 <= payload["sequence"] <= 4_294_967_295:
                raise ValueError("Sequência inválida.")
            temperature = bounded_number(payload["temperature_c_filtered"], -20, 60)
            humidity = bounded_number(payload["humidity_pct_filtered"], 0, 100)
            epoch = payload["observed_at"]
            if type(epoch) is not int or not 0 <= epoch <= 4_102_444_800:
                raise ValueError("Horário do dispositivo inválido.")
            observed = datetime.fromtimestamp(epoch, timezone.utc)
            source_type = payload.get("source_type", "hardware")
            if not one_of(source_type, {"simulado", "experimental", "hardware"}):
                raise ValueError("Origem inválida.")
            event_id = f"{payload['device_id']}:{payload['boot_id']}:{payload['sequence']}"
            identity = {field: payload[field] for field in ("device_id", "boot_id", "sequence")}
            contents = {"event_id": event_id, "source_type": source_type,
                        "zone": payload["zone"], "observed_at": observed.isoformat(),
                        "temperature_c": temperature, "humidity_pct": humidity}
            previous = store.find_event(event_id)
            if previous is not None:
                if any(previous[field] != value for field, value in contents.items()):
                    return jsonify({"status": "conflict", "error": "Sequência já utilizada por outra leitura."}), 409
                return jsonify({"id": previous["id"], "event_id": event_id, "status": "duplicate", **identity}), 200
            require_recent(observed)
            assessment = risk.evaluate(temperature, humidity)
            status, body = store.add_reading({
                **contents,
                "heat_index_c": assessment["heat_index_c"],
                "risk_level": assessment["level"],
                "algorithm_version": assessment["algorithm_version"],
            })
            return jsonify({**body, **identity} if status in {200, 201} else body), status
        except ValueError:
            return jsonify({"error": "Leitura do dispositivo inválida."}), 422
        except (OverflowError, OSError, RuntimeError, ServiceUnavailable):
            return jsonify({"error": "Serviço temporariamente indisponível."}), 503

    @app.get("/api/status")
    def api_status():
        try:
            return jsonify(store.snapshot())
        except (ServiceUnavailable, RuntimeError):
            return jsonify({"error": "Dados temporariamente indisponíveis."}), 503

    @app.get("/health")
    def health():
        dependencies = {"store": False, "risk": False}
        try:
            dependencies["store"] = store.health()
        except ServiceUnavailable:
            pass
        try:
            dependencies["risk"] = risk.health()
        except ServiceUnavailable:
            pass
        healthy = all(dependencies.values())
        return jsonify({"status": "ok" if healthy else "degraded", "service": "gateway", "dependencies": dependencies}), 200 if healthy else 503

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=3010, debug=False)
