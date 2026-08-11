from __future__ import annotations

import hmac
import math
import os

from flask import Flask, jsonify, request

ALGORITHM_VERSION = "heat-index-v1"
DEFAULT_SERVICE_KEY = "development-service-key"


def heat_index_celsius(temperature_c: float, humidity_pct: float) -> float:
    if temperature_c < 26.7 or humidity_pct < 40:
        return temperature_c
    temperature_f = temperature_c * 9 / 5 + 32
    rh = humidity_pct
    index_f = (
        -42.379 + 2.04901523 * temperature_f + 10.14333127 * rh
        - 0.22475541 * temperature_f * rh - 0.00683783 * temperature_f**2
        - 0.05481717 * rh**2 + 0.00122874 * temperature_f**2 * rh
        + 0.00085282 * temperature_f * rh**2 - 0.00000199 * temperature_f**2 * rh**2
    )
    return (index_f - 32) * 5 / 9


def evaluate(temperature_c: float, humidity_pct: float) -> dict:
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) for value in (temperature_c, humidity_pct)):
        raise ValueError("Temperatura e umidade devem ser números finitos.")
    if not -20 <= temperature_c <= 60 or not 0 <= humidity_pct <= 100:
        raise ValueError("Medição fora das faixas aceitas pelo experimento.")
    heat_index = round(heat_index_celsius(float(temperature_c), float(humidity_pct)), 1)
    if heat_index >= 40:
        level = "alerta"
        actions = ["Interromper esforço intenso", "Procurar local fresco", "Verificar pessoas vulneráveis"]
    elif heat_index >= 32:
        level = "atencao"
        actions = ["Reforçar hidratação", "Reduzir exposição ao sol", "Acompanhar novas medições"]
    else:
        level = "normal"
        actions = ["Manter hidratação", "Continuar acompanhamento"]
    return {
        "level": level,
        "heat_index_c": heat_index,
        "algorithm_version": ALGORITHM_VERSION,
        "explanation": f"Índice de calor estimado em {heat_index:.1f} °C a partir de temperatura e umidade.",
        "actions": actions,
        "warning": "Indicador experimental; não substitui orientação oficial ou avaliação de saúde.",
    }


def create_app(service_key: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config["SERVICE_KEY"] = service_key or os.getenv("HORIZONTE_SERVICE_KEY", DEFAULT_SERVICE_KEY)

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "risk", "algorithm": ALGORITHM_VERSION})

    @app.post("/v1/evaluate")
    def evaluate_route():
        if not hmac.compare_digest(request.headers.get("X-Service-Key", ""), app.config["SERVICE_KEY"]):
            return jsonify({"error": "Serviço não autorizado."}), 401
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or set(payload) != {"temperature_c", "humidity_pct"}:
            return jsonify({"error": "Contrato de avaliação inválido."}), 422
        try:
            return jsonify(evaluate(payload["temperature_c"], payload["humidity_pct"]))
        except (ValueError, TypeError) as error:
            return jsonify({"error": str(error)}), 422

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=3011, debug=False)
