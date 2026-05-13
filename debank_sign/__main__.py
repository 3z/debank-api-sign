"""
CLI entry point.

Usage:
    python -m debank_sign GET /chain/list
    python -m debank_sign GET /user/total_balance addr=0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045
    python -m debank_sign GET /user/email_exists email=user@example.com

Prints the signed headers as JSON, or makes the request if --request is passed.
"""

from __future__ import annotations

import argparse
import json
import sys

from debank_sign.signer import sign_headers


def _parse_params(raw: list[str]) -> dict:
    params = {}
    for item in raw:
        if "=" in item:
            k, v = item.split("=", 1)
            params[k] = v
    return params


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="debank_sign",
        description="Generate DeBank API signing headers.",
    )
    parser.add_argument("method", help="HTTP method (GET, POST)")
    parser.add_argument("path", help="API path, e.g. /user/total_balance")
    parser.add_argument(
        "params",
        nargs="*",
        help="Query params as key=value pairs",
    )
    parser.add_argument(
        "--request", "-r",
        action="store_true",
        help="Actually make the request (requires 'requests' package)",
    )
    parser.add_argument(
        "--base-url",
        default="https://api.debank.com",
        help="API base URL (default: https://api.debank.com)",
    )
    parser.add_argument(
        "--proxy",
        default=None,
        help="HTTP/SOCKS proxy URL",
    )
    parser.add_argument(
        "--curl",
        action="store_true",
        help="Print a ready-to-paste curl command instead of JSON",
    )

    args = parser.parse_args()
    params = _parse_params(args.params or [])
    headers = sign_headers(params, args.method, args.path)

    if args.curl:
        from urllib.parse import urlencode

        hdr_flags = " ".join(f'-H "{k}: {v}"' for k, v in headers.items())
        qs = f"?{urlencode(params)}" if params else ""
        url = f"{args.base_url}{args.path}{qs}"
        print(f"curl {hdr_flags} \\\n  '{url}'")
        return

    if args.request:
        try:
            from debank_sign.client import DeBankAPI
        except RuntimeError:
            print("error: --request requires the 'requests' package", file=sys.stderr)
            print("       pip install requests", file=sys.stderr)
            sys.exit(1)

        api = DeBankAPI(base_url=args.base_url, proxy=args.proxy)
        if args.method.upper() == "GET":
            result = api.get(args.path, params)
        else:
            result = api.post(args.path, params)

        print(json.dumps(result["data"], indent=2, ensure_ascii=False))
        sys.exit(0 if result["status"] == 200 else 1)

    print(json.dumps(headers, indent=2))


if __name__ == "__main__":
    main()
