from __future__ import annotations

import json
import urllib.error
import urllib.request


class ServiceUnavailable(RuntimeError):
    pass


def request_json(base_url: str, path: str, service_key: str, method: str = "GET", payload: dict | None = None) -> tuple[int, dict]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json", "X-Service-Key": service_key},
    )
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        try:
            try:
                detail = json.loads(error.read())
            except (json.JSONDecodeError, UnicodeDecodeError):
                detail = {"error": "Resposta inválida do serviço."}
        finally:
            error.close()
        return error.code, detail
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise ServiceUnavailable(str(error)) from error
