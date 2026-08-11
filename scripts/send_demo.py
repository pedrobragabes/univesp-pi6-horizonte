from __future__ import annotations

import json
import os
import secrets
import time
import urllib.request

SAMPLES = [
    ("Norte", 25.0, 55.0),
    ("Central", 30.0, 65.0),
    ("Sul", 34.0, 70.0),
]


def main() -> None:
    url = os.getenv("HORIZONTE_GATEWAY_URL", "http://127.0.0.1:3010")
    key = os.getenv("HORIZONTE_DEVICE_KEY", "development-device-key")
    boot_id = secrets.token_hex(4)
    for sequence, (zone, temperature, humidity) in enumerate(SAMPLES):
        payload = {
            "schema_version": 1,
            "device_id": "sentinela-demo-01",
            "boot_id": boot_id,
            "sequence": sequence,
            "observed_at": int(time.time()),
            "temperature_c_filtered": temperature,
            "humidity_pct_filtered": humidity,
            "zone": zone,
        }
        request = urllib.request.Request(
            f"{url}/api/device/readings",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "X-Device-Key": key},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            print(zone, response.status, response.read().decode("utf-8"))


if __name__ == "__main__":
    main()
