"""
Minimal example: generate signing headers for a DeBank API request.

No external dependencies required.
"""

from debank_sign import sign_headers

# Sign a GET request
params = {"addr": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"}
headers = sign_headers(params, "GET", "/user/total_balance")

print("Generated headers:")
for k, v in headers.items():
    print(f"  {k}: {v}")

# Use with any HTTP client. Example with urllib (stdlib):
import json
from urllib.request import Request, urlopen
from urllib.parse import urlencode

url = f"https://api.debank.com/user/total_balance?{urlencode(params)}"
req = Request(url, headers={
    **headers,
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
})

try:
    with urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
        print(f"\nHTTP {resp.status}")
        print(json.dumps(data, indent=2)[:500])
except Exception as e:
    print(f"\nRequest failed: {e}")
