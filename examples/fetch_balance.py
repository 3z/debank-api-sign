"""
Fetch a wallet's total balance using the DeBankAPI client.

Requires: pip install requests
"""

from debank_sign import DeBankAPI

api = DeBankAPI()

# -------------------------------------------------------------------
# 1. Verify signing works with a public endpoint
# -------------------------------------------------------------------
print("[1] GET /chain/list")
result = api.get("/chain/list")
print(f"    Status: {result['status']}")
if result["status"] == 200:
    chains = result["data"]
    if isinstance(chains, dict):
        chains = chains.get("data", {}).get("chains", chains)
    if isinstance(chains, list):
        print(f"    Chains: {len(chains)}")
        print(f"    First 5: {[c.get('name', c.get('id')) for c in chains[:5]]}")

# -------------------------------------------------------------------
# 2. Fetch a wallet balance (requires non-flagged IP)
# -------------------------------------------------------------------
addr = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"  # vitalik.eth
print(f"\n[2] GET /user/total_balance  addr={addr[:16]}...")
result = api.get("/user/total_balance", {"addr": addr})
print(f"    Status: {result['status']}")
print(f"    Data:   {str(result['data'])[:200]}")

# -------------------------------------------------------------------
# 3. Check email existence
# -------------------------------------------------------------------
email = "test@example.com"
print(f"\n[3] GET /user/email_exists  email={email}")
result = api.get("/user/email_exists", {"email": email})
print(f"    Status: {result['status']}")
print(f"    Data:   {result['data']}")
