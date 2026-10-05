import unittest
from unittest.mock import patch

from common.http_client import ServiceUnavailable
from gateway.clients import RiskClient, StoreClient


class DependencyContractsTest(unittest.TestCase):
    def test_invalid_snapshot_collections_are_dependency_failures(self):
        for body in ({}, {'readings': None, 'bulletins': [], 'latest_readings': []},
                     {'readings': [], 'bulletins': 'none', 'latest_readings': []},
                     {'readings': [], 'bulletins': [], 'latest_readings': [{}]}):
            with self.subTest(body=body), patch('gateway.clients.request_json', return_value=(200, body)):
                with self.assertRaises(ServiceUnavailable):
                    StoreClient('http://fixture.invalid', 'fixture').snapshot()

    def test_invalid_risk_success_is_not_used_as_a_real_assessment(self):
        bodies = [{}, {'level': 'normal', 'heat_index_c': float('nan'), 'algorithm_version': 'heat-index-v1'},
                  {'level': [], 'heat_index_c': 30, 'algorithm_version': 'heat-index-v1'},
                  {'level': 'normal', 'heat_index_c': 30, 'algorithm_version': '<script>'}]
        for body in bodies:
            with self.subTest(body=body), patch('gateway.clients.request_json', return_value=(200, body)):
                with self.assertRaises(ServiceUnavailable):
                    RiskClient('http://fixture.invalid', 'fixture').evaluate(30, 60)

    def test_unavailable_risk_response_is_a_dependency_failure(self):
        with patch('gateway.clients.request_json', return_value=(503, {'error': 'private fixture detail'})):
            with self.assertRaises(ServiceUnavailable) as error:
                RiskClient('http://fixture.invalid', 'fixture').evaluate(30, 60)
        self.assertNotIn('private fixture detail', str(error.exception))

    def test_store_failure_details_are_not_returned_to_a_public_caller(self):
        client = StoreClient('http://fixture.invalid', 'fixture')
        for method, payload in ((client.add_reading, {'event_id': 'fixture-01'}),
                                (client.add_bulletin, {'title': 'fixture'})):
            with self.subTest(method=method.__name__), patch('gateway.clients.request_json', return_value=(503, {'error': 'private fixture detail'})):
                with self.assertRaises(ServiceUnavailable) as error:
                    method(payload)
                self.assertNotIn('private fixture detail', str(error.exception))

    def test_reading_receipt_must_match_event_and_status(self):
        for status, body in ((201, {'status': 'accepted', 'id': 1, 'event_id': 'another'}),
                             (200, {'status': 'accepted', 'id': 1, 'event_id': 'fixture-01'}),
                             (201, {'status': 'accepted', 'id': True, 'event_id': 'fixture-01'})):
            with self.subTest(status=status, body=body), patch('gateway.clients.request_json', return_value=(status, body)):
                with self.assertRaises(ServiceUnavailable):
                    StoreClient('http://fixture.invalid', 'fixture').add_reading({'event_id': 'fixture-01'})


if __name__ == '__main__':
    unittest.main()
