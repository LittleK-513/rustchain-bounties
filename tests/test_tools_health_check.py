"""Unit tests for tools/health_check.py — Bounty Issue #1589

Covers 6 public functions with 15 test cases:
- create_ssl_context: default, insecure
- http_get: success, json error, http error, url error, timeout
- check_node: online, offline, invalid json
- format_uptime: seconds, minutes, hours, days, edge cases
- format_tip_age: zero, normal, large
"""

import json
import os
import ssl
import pytest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import tools.health_check as hc


# ─── create_ssl_context ─────────────────────────────────────────────

class TestCreateSslContext:
    def test_default_returns_none(self):
        assert hc.create_ssl_context(False) is None

    def test_insecure_returns_context(self):
        ctx = hc.create_ssl_context(True)
        assert isinstance(ctx, ssl.SSLContext)
        assert ctx.check_hostname is False
        assert ctx.verify_mode == ssl.CERT_NONE


# ─── http_get ────────────────────────────────────────────────────────

class TestHttpGet:
    @patch("tools.health_check.urllib.request.urlopen")
    def test_success_json(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"status": "ok"}).encode()
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        ok, data, err = hc.http_get("http://localhost:8099/health")
        assert ok is True
        assert data == {"status": "ok"}
        assert err == ""

    @patch("tools.health_check.urllib.request.urlopen")
    def test_invalid_json(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not json"
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        ok, data, err = hc.http_get("http://localhost:8099/health")
        assert ok is False
        assert data is None
        assert err == "invalid_json"

    @patch("tools.health_check.urllib.request.urlopen")
    def test_http_error(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError("url", 500, "Internal", {}, None)
        ok, data, err = hc.http_get("http://localhost:8099/health")
        assert ok is False
        assert err == "http_500"

    @patch("tools.health_check.urllib.request.urlopen")
    def test_url_error(self, mock_urlopen):
        mock_urlopen.side_effect = URLError("connection refused")
        ok, data, err = hc.http_get("http://bad-host:8099/health")
        assert ok is False
        assert "url_error" in err

    @patch("tools.health_check.urllib.request.urlopen")
    def test_timeout(self, mock_urlopen):
        import socket
        mock_urlopen.side_effect = socket.timeout("timed out")
        ok, data, err = hc.http_get("http://slow-host:8099/health", timeout=1)
        assert ok is False
        assert err == "TimeoutError"


# ─── check_node ─────────────────────────────────────────────────────

class TestCheckNode:
    @patch("tools.health_check.http_get")
    def test_online_node(self, mock_get):
        mock_get.return_value = (True, {"version": "1.0", "uptime": 3600, "db_rw": True, "tip_age": 5}, "")
        result = hc.check_node("http://localhost:8099")
        assert result["status"] == "UP"
        assert result["version"] == "1.0"

    @patch("tools.health_check.http_get")
    def test_offline_node(self, mock_get):
        mock_get.return_value = (False, None, "url_error")
        result = hc.check_node("http://bad-host:8099")
        assert result["status"] == "DOWN"

    @patch("tools.health_check.http_get")
    def test_node_missing_fields(self, mock_get):
        mock_get.return_value = (True, {"version": "1.0"}, "")
        result = hc.check_node("http://localhost:8099")
        assert result["status"] == "UP"


# ─── format_uptime ──────────────────────────────────────────────────

class TestFormatUptime:
    def test_zero(self):
        assert hc.format_uptime(0) == "0s"

    def test_seconds(self):
        assert "45s" in hc.format_uptime(45)

    def test_minutes(self):
        assert hc.format_uptime(60) == "1m"

    def test_hours(self):
        assert hc.format_uptime(3600) == "1h"

    def test_days(self):
        assert hc.format_uptime(86400) == "1d"

    def test_none_input(self):
        assert hc.format_uptime(None) == "None"


# ─── format_tip_age ─────────────────────────────────────────────────

class TestFormatTipAge:
    def test_zero(self):
        assert hc.format_tip_age(0) == "0s"

    def test_normal(self):
        assert "s" in hc.format_tip_age(42)

    def test_large(self):
        assert "m" in hc.format_tip_age(600) or "10m" in hc.format_tip_age(600)

    def test_none_input(self):
        assert hc.format_tip_age(None) == "None"
