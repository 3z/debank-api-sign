"""
Tests for the signing algorithm.

Run with: python -m pytest tests/ -v
Or just:  python tests/test_signer.py
"""

import hashlib
import hmac
import unittest

from debank_sign.signer import sign, sign_headers, _sort_params


class TestSortParams(unittest.TestCase):
    """Verify the canonical parameter serialization."""

    def test_empty(self):
        self.assertEqual(_sort_params({}), "")

    def test_single(self):
        self.assertEqual(_sort_params({"addr": "0xABC"}), "addr=0xABC")

    def test_sorted_order(self):
        params = {"z": "3", "a": "1", "m": "2"}
        self.assertEqual(_sort_params(params), "a=1&m=2&z=3")

    def test_none_value(self):
        self.assertEqual(_sort_params({"key": None}), "key=")

    def test_numeric_value(self):
        self.assertEqual(_sort_params({"page": 1}), "page=1")


class TestSign(unittest.TestCase):
    """Verify the signing output structure and determinism."""

    def test_returns_required_keys(self):
        result = sign({}, "GET", "/chain/list")
        self.assertIn("signature", result)
        self.assertIn("nonce", result)
        self.assertIn("ts", result)
        self.assertIn("version", result)

    def test_version_is_v2(self):
        result = sign({}, "GET", "/chain/list")
        self.assertEqual(result["version"], "v2")

    def test_nonce_prefix(self):
        result = sign({}, "GET", "/test")
        self.assertTrue(result["nonce"].startswith("n_"))

    def test_deterministic_with_fixed_inputs(self):
        """Given the same nonce and ts, output must be identical."""
        kwargs = {"nonce": "n_test123", "ts": 1700000000}
        r1 = sign({"addr": "0xABC"}, "GET", "/user/total_balance", **kwargs)
        r2 = sign({"addr": "0xABC"}, "GET", "/user/total_balance", **kwargs)
        self.assertEqual(r1["signature"], r2["signature"])

    def test_signature_matches_manual_computation(self):
        """Verify the output matches a hand-computed reference."""
        params = {"email": "test@example.com"}
        method = "GET"
        path = "/user/email_exists"
        nonce = "n_abc123"
        ts = 1700000000

        # Manual computation
        sorted_p = "email=test@example.com"
        payload = f"{sorted_p}\n{method}\n{path}"
        payload_hash = hashlib.sha256(payload.encode()).hexdigest()
        sign_input = f"{nonce}{ts}{payload_hash}"
        expected_sig = hmac.new(
            b"debank-api", sign_input.encode(), hashlib.sha256
        ).hexdigest()

        result = sign(params, method, path, nonce=nonce, ts=ts)
        self.assertEqual(result["signature"], expected_sig)

    def test_different_params_produce_different_signatures(self):
        kwargs = {"nonce": "n_fixed", "ts": 1700000000}
        r1 = sign({"email": "a@b.com"}, "GET", "/test", **kwargs)
        r2 = sign({"email": "x@y.com"}, "GET", "/test", **kwargs)
        self.assertNotEqual(r1["signature"], r2["signature"])

    def test_different_methods_produce_different_signatures(self):
        kwargs = {"nonce": "n_fixed", "ts": 1700000000}
        r1 = sign({}, "GET", "/test", **kwargs)
        r2 = sign({}, "POST", "/test", **kwargs)
        self.assertNotEqual(r1["signature"], r2["signature"])

    def test_different_paths_produce_different_signatures(self):
        kwargs = {"nonce": "n_fixed", "ts": 1700000000}
        r1 = sign({}, "GET", "/path/a", **kwargs)
        r2 = sign({}, "GET", "/path/b", **kwargs)
        self.assertNotEqual(r1["signature"], r2["signature"])


class TestSignHeaders(unittest.TestCase):
    """Verify the header dict output."""

    def test_header_names(self):
        headers = sign_headers({}, "GET", "/test")
        self.assertIn("x-api-ts", headers)
        self.assertIn("x-api-nonce", headers)
        self.assertIn("x-api-ver", headers)
        self.assertIn("x-api-sign", headers)
        self.assertEqual(len(headers), 4)

    def test_ts_is_string(self):
        headers = sign_headers({}, "GET", "/test")
        self.assertIsInstance(headers["x-api-ts"], str)
        int(headers["x-api-ts"])  # must be parseable

    def test_sign_is_hex(self):
        headers = sign_headers({}, "GET", "/test")
        int(headers["x-api-sign"], 16)  # must be valid hex
        self.assertEqual(len(headers["x-api-sign"]), 64)  # SHA-256 hex


if __name__ == "__main__":
    unittest.main()
