import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from common.http_client import ServiceUnavailable, request_json


class Response(io.BytesIO):
    status = 200


class HttpClientTest(unittest.TestCase):
    def test_success_with_html_or_non_object_json_is_a_dependency_failure(self):
        for body in (b'<html>OK</html>', b'[]', b'null', b'"ok"', b'{', b'\xff'):
            with self.subTest(body=body):
                with patch('urllib.request.urlopen', return_value=Response(body)):
                    with self.assertRaises(ServiceUnavailable):
                        request_json('http://fixture.invalid', '/health', 'fixture-key')

    def test_excessive_dependency_response_is_bounded_and_rejected(self):
        body = b'{"padding":"' + b'a' * 1_048_577 + b'"}'
        with patch('urllib.request.urlopen', return_value=Response(body)):
            with self.assertRaises(ServiceUnavailable):
                request_json('http://fixture.invalid', '/health', 'fixture-key')

    def test_non_object_error_body_is_controlled_and_its_stream_is_closed(self):
        stream = io.BytesIO(b'[]')
        error = HTTPError('http://fixture.invalid', 503, 'Unavailable', {}, stream)
        with patch('urllib.request.urlopen', side_effect=error):
            status, body = request_json('http://fixture.invalid', '/health', 'fixture-key')
        self.assertEqual(status, 503)
        self.assertIsInstance(body, dict)
        self.assertTrue(stream.closed)


if __name__ == '__main__':
    unittest.main()
