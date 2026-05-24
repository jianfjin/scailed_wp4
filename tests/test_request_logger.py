"""Tests for RequestLogger middleware.

Uses unittest.TestCase style (works without pytest plugin config).
"""
from __future__ import annotations

from unittest import TestCase
from unittest.mock import Mock

from pathfinder.middleware.request_logger import RequestLogger, get_logger


def _mock_request(method="GET", path="/health", ip="127.0.0.1", ua="test"):
    """Build a minimal mock FastAPI Request."""
    req = Mock()
    req.method = method
    req.url.path = path
    req.headers.get = Mock(return_value=ua)
    req.headers.get.side_effect = lambda k, d=None: {
        "x-forwarded-for": None,
        "user-agent": ua,
    }.get(k.lower(), d)
    req.client = Mock()
    req.client.host = ip
    req.path_params = {}
    return req


def _mock_response(status_code=200):
    resp = Mock()
    resp.status_code = status_code
    return resp


class TestRequestLogger(TestCase):
    def setUp(self):
        # Fresh logger for each test
        self.logger = RequestLogger()

    def test_singleton(self):
        a = get_logger()
        b = get_logger()
        self.assertIs(a, b)

    def test_log_adds_to_buffer(self):
        self.logger.log(_mock_request(), _mock_response(), duration_ms=5)
        recent = self.logger.get_recent(10)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["ip"], "127.0.0.1")

    def test_buffer_maxlen(self):
        for i in range(1010):
            self.logger.log(
                _mock_request(path=f"/test/{i}"),
                _mock_response(),
                duration_ms=1,
            )
        self.assertEqual(len(self.logger.get_recent(2000)), 1000)

    def test_get_stats_empty(self):
        stats = self.logger.get_stats()
        self.assertEqual(stats["total_requests"], 0)
        self.assertEqual(stats["error_rate"], 0.0)

    def test_get_stats_counts(self):
        self.logger.log(_mock_request(path="/ok"), _mock_response(200), duration_ms=10)
        self.logger.log(_mock_request(path="/err"), _mock_response(500), duration_ms=50)
        self.logger.log(_mock_request(path="/ok"), _mock_response(200), duration_ms=5)
        stats = self.logger.get_stats()
        self.assertEqual(stats["total_requests"], 3)
        self.assertEqual(stats["error_count"], 1)
        self.assertEqual(stats["unique_ips"], 1)
        self.assertIn("/ok", [e["endpoint"] for e in stats["top_endpoints"]])
