"""
Core signing logic for the DeBank API.

The DeBank API requires 4 custom headers on every request to prevent
automated access. These headers are generated using HMAC-SHA256 with
a static key and a payload derived from the request parameters.

Algorithm (reverse-engineered from QuickJS sandbox bytecode in web chunk
6101.4aa3c89e.js, module 35653):

    1. Serialize query parameters: sort keys alphabetically, join as
       ``key=value`` pairs separated by ``&``.
    2. Build the signing payload::

           payload = sorted_params + "\\n" + METHOD + "\\n" + path

    3. Generate a random nonce prefixed with ``n_``.
    4. Get the current Unix timestamp in seconds.
    5. Compute the signature::

           payload_hash = SHA256(payload)
           signature    = HMAC-SHA256(key, nonce + str(ts) + payload_hash)

       where ``key`` is the static string ``"debank-api"``.

    6. Attach the result as HTTP headers::

           x-api-ts    = <timestamp>
           x-api-nonce = <nonce>
           x-api-ver   = "v2"
           x-api-sign  = <signature>

Header names are hex-obfuscated in the source (module 24610)::

    782d6170692d7473       -> x-api-ts
    782d6170692d6e6f6e6365 -> x-api-nonce
    782d6170692d766572     -> x-api-ver
    782d6170692d7369676e   -> x-api-sign
"""

from __future__ import annotations

import hashlib
import hmac
import math
import random
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: HMAC key used for request signing.  Extracted from the QuickJS sandbox
#: function ``c()`` in module 35653 (string table entry ``"debank-api\\n"``).
SIGN_KEY: str = "debank-api"

#: Signing protocol version sent in the ``x-api-ver`` header.
VERSION: str = "v2"

#: Character set used by the nonce generator (matches the sandbox
#: ``randString`` implementation).
NONCE_CHARSET: str = (
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXTZ"
    "abcdefghiklmnopqrstuvwxyz"
)

#: Default minimum length of the random portion of the nonce.
NONCE_MIN_LEN: int = 5

#: Default maximum length of the random portion of the nonce.
NONCE_MAX_LEN: int = 20

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rand_string(length: int) -> str:
    """Return a random string of *length* characters from :data:`NONCE_CHARSET`."""
    return "".join(random.choice(NONCE_CHARSET) for _ in range(length))


def _sort_params(params: Dict[str, Any]) -> str:
    """Serialize *params* into the canonical query string used for signing.

    Keys are sorted lexicographically.  ``None`` values are replaced with
    the empty string.  All values are converted to their ``str``
    representation.  Key/value pairs are joined with ``&``.

    This replicates the ``sortParams`` function in module 63335 where the
    separator is decoded from ``ew("0026")`` -> ``&``.
    """
    if not params:
        return ""
    return "&".join(
        f"{k}={''.strip() if params[k] is None else params[k]}"
        for k in sorted(str(k) for k in params.keys())
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sign(
    params: Dict[str, Any],
    method: str,
    path: str,
    *,
    nonce: Optional[str] = None,
    ts: Optional[int] = None,
) -> Dict[str, str]:
    """Compute the DeBank signing fields for a single request.

    Parameters
    ----------
    params:
        The query-string parameters (for GET) or body fields (for POST).
    method:
        HTTP method (``"GET"``, ``"POST"``, ...).
    path:
        The URL path **without** query string, e.g. ``"/user/email_exists"``.
    nonce:
        Optional fixed nonce.  Generated randomly when *None*.
    ts:
        Optional fixed timestamp (Unix seconds).  Uses ``time.time()`` when
        *None*.

    Returns
    -------
    dict
        A dictionary with keys ``signature``, ``nonce``, ``ts``, and
        ``version``.
    """
    if nonce is None:
        nonce = "n_" + _rand_string(
            random.randint(NONCE_MIN_LEN, NONCE_MAX_LEN)
        )
    if ts is None:
        ts = math.floor(time.time())

    payload = f"{_sort_params(params)}\n{method.upper()}\n{path}"
    payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    sign_input = f"{nonce}{ts}{payload_hash}"
    signature = hmac.new(
        SIGN_KEY.encode("utf-8"),
        sign_input.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return {
        "signature": signature,
        "nonce": nonce,
        "ts": str(ts),
        "version": VERSION,
    }


def sign_headers(
    params: Dict[str, Any],
    method: str,
    path: str,
    **kwargs,
) -> Dict[str, str]:
    """Return the four HTTP headers required by the DeBank API.

    Accepts the same arguments as :func:`sign`.  The returned dictionary
    can be merged directly into a ``requests``-style headers dict.
    """
    s = sign(params, method, path, **kwargs)
    return {
        "x-api-ts": s["ts"],
        "x-api-nonce": s["nonce"],
        "x-api-ver": s["version"],
        "x-api-sign": s["signature"],
    }


def sign_and_build_url(
    base_url: str,
    path: str,
    params: Dict[str, Any],
    method: str = "GET",
) -> tuple[str, Dict[str, str]]:
    """Convenience helper that returns ``(full_url, headers)``.

    Parameters
    ----------
    base_url:
        E.g. ``"https://api.debank.com"``.
    path:
        E.g. ``"/chain/list"``.
    params:
        Query parameters.
    method:
        HTTP method.

    Returns
    -------
    tuple[str, dict]
        The full URL with encoded query string and the signing headers.
    """
    headers = sign_headers(params, method, path)
    qs = urlencode(params) if params else ""
    url = f"{base_url.rstrip('/')}{path}"
    if qs:
        url = f"{url}?{qs}"
    return url, headers
