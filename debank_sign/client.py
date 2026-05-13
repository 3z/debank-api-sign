"""
Minimal convenience client wrapping :mod:`debank_sign.signer`.

Uses the ``requests`` library (must be installed separately).
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

try:
    import requests as _requests
except ImportError:  # pragma: no cover
    _requests = None  # type: ignore[assignment]

from debank_sign.signer import sign_headers

BASE_URL = "https://api.debank.com"

# Default browser-like headers sent with every request.
_DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://debank.com",
    "Referer": "https://debank.com/",
    "source": "web",
}


class DeBankAPI:
    """Thin API client with automatic request signing.

    Parameters
    ----------
    base_url:
        Override the default API base (``https://api.debank.com``).
    proxy:
        Optional HTTP/SOCKS proxy URL forwarded to ``requests``.
    timeout:
        Default request timeout in seconds.
    headers:
        Extra headers merged into every request.

    Example
    -------
    >>> api = DeBankAPI()
    >>> api.get("/chain/list")
    {'status': 200, 'data': {...}}
    """

    def __init__(
        self,
        base_url: str = BASE_URL,
        *,
        proxy: Optional[str] = None,
        timeout: int = 15,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        if _requests is None:
            raise RuntimeError(
                "The 'requests' package is required for DeBankAPI.  "
                "Install it with: pip install requests"
            )
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = _requests.Session()
        self.session.headers.update(_DEFAULT_HEADERS)
        if headers:
            self.session.headers.update(headers)
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

    # ------------------------------------------------------------------
    # Core request method
    # ------------------------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Send a signed request and return ``{status, data, headers}``."""
        params = params or {}
        sign_params = params if method.upper() == "GET" else (data or {})
        hdrs = sign_headers(sign_params, method, path)

        url = f"{self.base_url}{path}"
        if method.upper() == "GET":
            resp = self.session.get(
                url, params=params, headers=hdrs, timeout=self.timeout, **kwargs
            )
        else:
            hdrs["Content-Type"] = "application/json"
            resp = self.session.post(
                url, json=data, headers=hdrs, timeout=self.timeout, **kwargs
            )

        try:
            body = resp.json()
        except Exception:
            body = resp.text

        return {
            "status": resp.status_code,
            "data": body,
            "headers": dict(resp.headers),
        }

    def get(self, path: str, params: Optional[Dict[str, Any]] = None, **kw):
        """Signed ``GET`` request."""
        return self.request("GET", path, params=params, **kw)

    def post(self, path: str, data: Optional[Dict[str, Any]] = None, **kw):
        """Signed ``POST`` request."""
        return self.request("POST", path, data=data, **kw)
