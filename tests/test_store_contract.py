from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from services.store.app import create_app, database


def reading(event_id='contract-01', zone='Central'):
    return {
        'event_id': event_id, 'source_type': 'simulado', 'zone': zone,
        'observed_at': datetime.now(timezone.utc).isoformat(),
        'temperature_c': 30, 'humidity_pct': 60, 'heat_index_c': 32,
        'risk_level': 'atencao', 'algorithm_version': 'heat-index-v1',
    }


class StoreContractTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / 'fixture.db'
        self.app = create_app(self.path, 'fixture-service-key')
        self.client = self.app.test_client()

    def tearDown(self):
        self.temporary.cleanup()

    def post(self, payload):
        return self.client.post('/v1/readings', json=payload,
                                headers={'X-Service-Key': 'fixture-service-key'})

    def test_conflicting_event_does_not_acknowledge_or_change_the_original(self):
        payload = reading()
        self.assertEqual(self.post(payload).status_code, 201)
        for field, value in {'temperature_c': 31, 'zone': 'Norte',
                             'risk_level': 'alerta', 'algorithm_version': 'heat-index-v2'}.items():
            with self.subTest(field=field):
                response = self.post({**payload, field: value})
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.get_json()['status'], 'conflict')
        with database(self.path) as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM readings').fetchone()[0], 1)
            self.assertEqual(connection.execute('SELECT temperature_c FROM readings').fetchone()[0], 30)

    def test_equal_instant_in_another_timezone_is_the_same_receipt(self):
        payload = reading()
        first = self.post(payload).get_json()
        offset = timezone(timedelta(hours=-3))
        same = {**payload, 'observed_at': datetime.fromisoformat(payload['observed_at']).astimezone(offset).isoformat()}
        duplicate = self.post(same)
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(duplicate.get_json()['id'], first['id'])

    def test_exact_retry_survives_a_service_restart(self):
        payload = reading()
        first = self.post(payload).get_json()
        restarted = create_app(self.path, 'fixture-service-key').test_client()
        response = restarted.post('/v1/readings', json=payload,
                                  headers={'X-Service-Key': 'fixture-service-key'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['id'], first['id'])

    def test_concurrent_conflicting_events_have_only_one_successful_insert(self):
        payload = reading()
        def send(item):
            with self.app.test_client() as client:
                return client.post('/v1/readings', json=item,
                                   headers={'X-Service-Key': 'fixture-service-key'}).status_code
        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(send, (payload, {**payload, 'humidity_pct': 70})))
        self.assertCountEqual(statuses, [201, 409])

    def test_invalid_enum_types_are_controlled_validation_failures(self):
        for field in ('zone', 'source_type', 'risk_level'):
            for value in ([], {}, True, None):
                with self.subTest(field=field, value=value):
                    self.assertEqual(self.post({**reading(), field: value}).status_code, 422)

    def test_large_integer_is_rejected_without_overflow_or_write(self):
        self.assertEqual(self.post({**reading(), 'temperature_c': 10**500}).status_code, 422)

    def test_wrong_unicode_key_is_rejected_without_an_internal_error(self):
        response = self.client.get('/v1/snapshot', headers={'X-Service-Key': 'chave-inválida'})
        self.assertEqual(response.status_code, 401)

    def test_snapshot_preserves_every_zone_despite_a_busy_other_zone(self):
        central = reading('central-01', 'Central')
        self.assertEqual(self.post(central).status_code, 201)
        for index in range(31):
            self.assertEqual(self.post(reading(f'north-{index}', 'Norte')).status_code, 201)
        snapshot = self.client.get('/v1/snapshot', headers={'X-Service-Key': 'fixture-service-key'}).get_json()
        self.assertEqual({row['zone'] for row in snapshot['latest_readings']}, {'Central', 'Norte'})
        self.assertEqual(len(snapshot['readings']), 30)

    def test_latest_zone_observation_ignores_delayed_delivery(self):
        newest = reading('newest')
        older = {**reading('older'), 'observed_at': (datetime.fromisoformat(newest['observed_at']) - timedelta(minutes=10)).isoformat()}
        self.assertEqual(self.post(newest).status_code, 201)
        self.assertEqual(self.post(older).status_code, 201)
        snapshot = self.client.get('/v1/snapshot', headers={'X-Service-Key': 'fixture-service-key'}).get_json()
        self.assertEqual(snapshot['latest_readings'][0]['event_id'], 'newest')

    def test_event_lookup_is_authenticated_and_returns_the_stored_receipt(self):
        payload = reading()
        accepted = self.post(payload).get_json()
        self.assertEqual(self.client.get('/v1/readings/contract-01').status_code, 401)
        response = self.client.get('/v1/readings/contract-01', headers={'X-Service-Key': 'fixture-service-key'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['id'], accepted['id'])


if __name__ == '__main__':
    unittest.main()
