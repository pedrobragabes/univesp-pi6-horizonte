from __future__ import annotations

import json
import urllib.error
import urllib.request


class ServiceUnavailable(RuntimeError):
    pass


MAX_RESPONSE_BYTES = 1_048_576


def read_object(response) -> dict:
    raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError('Resposta excede o limite.')
    body = json.loads(raw)
    if not isinstance(body, dict):
        raise ValueError('Resposta não é um objeto JSON.')
    return body


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
            try:
                return response.status, read_object(response)
            except (ValueError, UnicodeDecodeError) as error:
                raise ServiceUnavailable('Resposta inválida do serviço.') from error
    except urllib.error.HTTPError as error:
        try:
            try:
                detail = read_object(error)
            except (ValueError, UnicodeDecodeError):
                detail = {"error": "Resposta inválida do serviço."}
        finally:
            error.close()
        return error.code, detail
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise ServiceUnavailable('Serviço temporariamente indisponível.') from error
