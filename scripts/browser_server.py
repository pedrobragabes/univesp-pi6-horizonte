"""Three disposable HTTP processes with synthetic data, exclusively on loopback."""
import json
import multiprocessing
import signal
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from flask import render_template
from werkzeug.serving import make_server

SERVICE_KEY = 'fixture-service-only'
DEVICE_KEY = 'fixture-device-only'
PASSWORD = 'fixture-operator-only'


def serve(name, path):
    if name == 'store':
        from services.store.app import create_app
        app = create_app(Path(path), SERVICE_KEY)
        port = 3489
    elif name == 'risk':
        from services.risk.app import create_app
        app = create_app(SERVICE_KEY)
        port = 3488
    else:
        from gateway.app import create_app
        app = create_app('http://127.0.0.1:3489', 'http://127.0.0.1:3488',
                         SERVICE_KEY, 'fixture-session-only', PASSWORD, DEVICE_KEY)
        port = 3487

        @app.get('/fixture-ready')
        def ready():
            from common.http_client import request_json
            status, body = request_json('http://127.0.0.1:3489', '/v1/snapshot', SERVICE_KEY)
            return ({'ready': True}, 200) if status == 200 and len(body['latest_readings']) == 3 else ({'ready': False}, 503)

        @app.get('/empty-fixture')
        def empty():
            return render_template('dashboard.html', zones=[{'zone': z, 'risk_level': 'indisponivel'} for z in ('Central', 'Norte', 'Sul')], bulletins=[], unavailable=False)

        @app.get('/degraded-fixture')
        def degraded():
            return render_template('dashboard.html', zones=[{'zone': z, 'risk_level': 'indisponivel'} for z in ('Central', 'Norte', 'Sul')], bulletins=[], unavailable=True)

    with make_server('127.0.0.1', port, app) as server:
        server.serve_forever()


def wait_ready(url):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.05)
    raise RuntimeError('Fixture HTTP não iniciou.')


def stop_signal(_number, _frame):
    raise KeyboardInterrupt


def main():
    signal.signal(signal.SIGTERM, stop_signal)
    signal.signal(signal.SIGINT, stop_signal)
    with tempfile.TemporaryDirectory(prefix='horizonte-browser-') as directory:
        context = multiprocessing.get_context('spawn')
        children = [context.Process(target=serve, args=(name, str(Path(directory) / 'fixture.db')))
                    for name in ('store', 'risk', 'gateway')]
        try:
            for child in children:
                child.start()
            for port in (3489, 3488, 3487):
                wait_ready(f'http://127.0.0.1:{port}/health')
            for index, (zone, temperature, humidity) in enumerate((('Norte', 25, 55), ('Central', 30, 65), ('Sul', 34, 70))):
                body = {'schema_version': 1, 'device_id': 'fixture-sim-01', 'boot_id': 'a1b2c3d4',
                        'sequence': index, 'observed_at': int(time.time()), 'zone': zone,
                        'temperature_c_filtered': temperature, 'humidity_pct_filtered': humidity, 'source_type': 'simulado'}
                request = urllib.request.Request('http://127.0.0.1:3487/api/device/readings',
                    data=json.dumps(body).encode(), method='POST',
                    headers={'Content-Type': 'application/json', 'X-Device-Key': DEVICE_KEY})
                with urllib.request.urlopen(request, timeout=3) as response:
                    assert response.status == 201
            while all(child.is_alive() for child in children):
                time.sleep(0.2)
            raise RuntimeError('Processo da fixture encerrou antes do teste.')
        except KeyboardInterrupt:
            pass
        finally:
            for child in children:
                if child.is_alive():
                    child.terminate()
                child.join(timeout=5)
                if child.is_alive():
                    child.kill()
                    child.join(timeout=5)


if __name__ == '__main__':
    main()
