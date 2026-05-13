# debank-api-sign

Reverse-engineered request signing for the [DeBank](https://debank.com) API.

DeBank protects its API with 4 custom HTTP headers that must be present on every request. Without them, the server returns `429 Too Many Requests`. This library replicates the signing algorithm so you can make authenticated API calls from Python.

## Install

```bash
pip install debank-api-sign
```

Or clone and install locally:

```bash
git clone https://github.com/youruser/debank-api-sign.git
cd debank-api-sign
pip install -e .
```

The core signer has **zero dependencies** (stdlib only). The optional `DeBankAPI` client requires `requests`.

## Quick Start

### Signing only (zero dependencies)

```python
from debank_sign import sign_headers

params = {"addr": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"}
headers = sign_headers(params, "GET", "/user/total_balance")

print(headers)
# {
#   'x-api-ts':    '1715567000',
#   'x-api-nonce': 'n_Xk7tR9pQm',
#   'x-api-ver':   'v2',
#   'x-api-sign':  'a7bc200d...',
# }
```

Then pass the headers to any HTTP client you like (`requests`, `httpx`, `aiohttp`, `curl`, etc.).

### With the built-in client

```python
from debank_sign import DeBankAPI

api = DeBankAPI()

# Public endpoint
chains = api.get("/chain/list")
print(chains["status"])  # 200

# User endpoint
balance = api.get("/user/total_balance", {"addr": "0xd8dA..."})
print(balance["data"])
```

### With curl

Generate headers in Python then use them in a shell command:

```python
from debank_sign import sign_headers

h = sign_headers({"email": "user@example.com"}, "GET", "/user/email_exists")
print(f'curl -H "x-api-ts: {h["x-api-ts"]}" '
      f'-H "x-api-nonce: {h["x-api-nonce"]}" '
      f'-H "x-api-ver: {h["x-api-ver"]}" '
      f'-H "x-api-sign: {h["x-api-sign"]}" '
      f'"https://api.debank.com/user/email_exists?email=user@example.com"')
```

## How the Signing Works

### The 4 Headers

| Header | Value |
|---|---|
| `x-api-ts` | Current Unix timestamp (seconds) |
| `x-api-nonce` | `n_` + random alphanumeric string (5-20 chars) |
| `x-api-ver` | `v2` |
| `x-api-sign` | HMAC-SHA256 signature (hex) |

### The Algorithm

```
1.  sorted_params = sort query params by key, join as "key=value" with "&"
2.  payload       = sorted_params + "\n" + METHOD + "\n" + path
3.  payload_hash  = SHA256(payload).hex()
4.  sign_input    = nonce + str(timestamp) + payload_hash
5.  signature     = HMAC-SHA256(key="debank-api", msg=sign_input).hex()
```

### Worked Example

```
Request:  GET /user/total_balance?addr=0xABC123
Params:   {"addr": "0xABC123"}
Method:   GET
Path:     /user/total_balance

Step 1:   sorted_params = "addr=0xABC123"
Step 2:   payload       = "addr=0xABC123\nGET\n/user/total_balance"
Step 3:   payload_hash  = sha256(payload) = "8f3a..."
Step 4:   sign_input    = "n_Xk7tR9pQm" + "1715567000" + "8f3a..."
Step 5:   signature     = hmac_sha256("debank-api", sign_input) = "a7bc..."
```

## How This Was Reverse-Engineered

### Source Material

- **APK**: `com.debank.meme` v1.6.11 (DeBank Android app)
- **Web JS**: `debank.com` production bundles

### Tools Used

| Tool | Purpose |
|---|---|
| jadx 1.5.0 | Java decompilation from DEX |
| apktool 2.9.3 | APK resource decoding, smali disassembly |
| strings / ripgrep | Binary string extraction from Hermes bytecode |
| Browser DevTools | Web JS chunk analysis |

### Reverse Engineering Steps

#### 1. APK Decompilation

The DeBank app is React Native with Hermes bytecode (v96). The native Java layer is minimal -- just a `CustomNetworkModule` that creates an OkHttp client with **no certificate pinning**:

```java
// CustomNetworkModule.kt
new OkHttpClient.Builder()
    .dispatcher(dispatcher)
    .writeTimeout(10L, TimeUnit.SECONDS)
    .readTimeout(30L, TimeUnit.SECONDS)
    .cookieJar(new ReactCookieJarContainer())
    .build();  // No CertificatePinner
```

#### 2. Finding the Headers

The header names are hex-encoded in the web JS (module `24610`, chunk `610.b8e3a928.js`):

```javascript
const u = [
  (0,r.FX)("782d6170692d7473"),        // x-api-ts
  (0,r.FX)("782d6170692d6e6f6e6365"),  // x-api-nonce
  (0,r.FX)("782d6170692d766572"),      // x-api-ver
  (0,r.FX)("782d6170692d7369676e")     // x-api-sign
];
```

The `FX` function is a hex-to-ASCII decoder (`module 89465`).

#### 3. The Signing Sandbox

The actual signing runs inside a **QuickJS interpreter sandbox** (`quickjs-emscripten`). The signing bytecode is a base64-encoded serialized AST loaded in module `35653`:

```javascript
const A = new QuickJSInterpreter();
// Inject crypto primitives into the sandbox:
//   sss(msg)       = SHA256(msg).hex()
//   hssss(key,msg) = HMAC-SHA256(key, msg).hex()
A.run(decodedBytecode, false);
```

The sandbox exports a function `gsD(params, method, path, options)` that returns `{signature, nonce, ts, version}`.

#### 4. Decompiling the Sandbox Bytecode

The base64 payload decodes (after triple URL-decoding) to a JSON AST with opcodes, string tables, and function definitions. Key function analysis:

| Function | Strings | Purpose |
|---|---|---|
| `c` | `debank-api\n`, `000120`, `000121` | Builds the HMAC key |
| `u` | `sortParams`, `toUpperCase`, `\n` | Builds the signing payload |
| `s` | `n_`, `randString` | Generates the nonce |
| `v` | `sss`, `hssss`, `000120` | v2 signing (SHA256 + HMAC) |
| `gsD` (anonymous) | `nonce`, `timestamp`, `getSecond`, `signature`, `ts` | Main entry point |

#### 5. Extracting the Algorithm

By tracing the opcode flow of function `v`:

1. Call `c("000120")` to build the key -> `"debank-api"`
2. Call `u(params, method, path)` to build the payload string
3. Call `sss(payload)` -> SHA256 hash
4. Call `hssss(key, nonce + ts + hash)` -> HMAC-SHA256 signature

#### 6. Verification

Confirmed by making live API requests:

```
GET /chain/list with signing headers -> HTTP 200 (85 chains returned)
GET /chain/list without headers      -> HTTP 200 (no signing needed for this endpoint)
GET /user/total_balance without      -> HTTP 429
GET /user/total_balance with signing -> HTTP 200 (on non-flagged IPs)
```

## Known API Endpoints

A partial list discovered during reverse engineering:

<details>
<summary>User & Auth</summary>

```
/user/email_exists          - Check if email is registered
/user/login_by_email        - Email login
/user/login                 - Wallet login
/user/login_by_qrcode       - QR code login
/user/logout                - Logout
/user/info                  - User profile
/user/total_balance         - Portfolio total value
/user/effective_usd_value   - Effective USD value
/user/effective_rank        - User ranking
/user/badge_list            - User badges
/user/followers             - Follower list
/user/following_list        - Following list
/user/credit                - Credit score
/user/third_account         - Linked accounts
```
</details>

<details>
<summary>Portfolio</summary>

```
/portfolio/all_token_list           - All tokens
/portfolio/all_complex_protocol_list - DeFi protocol positions
/portfolio/all_history_token_list   - Historical tokens
/portfolio/app_list                 - Connected DApps
/portfolio/list                     - Portfolio listing
/asset/total_net_curve              - Net worth curve
```
</details>

<details>
<summary>Social / Stream</summary>

```
/feed/list              - Feed
/feed/hot_list          - Trending
/feed/search            - Search posts
/article/recent_post    - Recent articles
/article/top_earners    - Top earners
/channel/list           - Channels
/channel/search         - Search channels
```
</details>

<details>
<summary>Messaging (Hi)</summary>

```
/hi/session/initialize       - Start chat session
/hi/message/add              - Send message
/hi/message/list             - Message history
/hi/unread_message_count     - Unread count
/hi/user/info                - Hi user info
```
</details>

<details>
<summary>Other</summary>

```
/chain/list                  - Supported chains
/chain/nonce                 - Chain nonce
/notification/list           - Notifications
/notification/unread_count   - Unread notifications
/contract/simulate           - Simulate transaction
/convert/quote               - Swap quote
/badge/user_can_mint         - Badge eligibility
```
</details>

## CloudFront WAF Notes

DeBank fronts their API with **AWS CloudFront** which applies additional IP-reputation-based rate limiting on sensitive paths (`/user/*`, `/feed/*`, `/portfolio/*`). The signing headers alone are not sufficient -- the source IP must also pass CloudFront's bot detection.

Endpoints like `/chain/list` and `/notification/unread_count` work from any IP with just the signing headers.

For `user` endpoints, you may need to route through a non-flagged residential IP.

## Project Structure

```
debank-api-sign/
  debank_sign/
    __init__.py      - Package exports
    signer.py        - Core signing algorithm (zero deps)
    client.py        - Optional requests-based API client
  examples/
    basic_sign.py    - Minimal signing example
    fetch_balance.py - Fetch a wallet balance
  pyproject.toml     - Package metadata
  README.md          - This file
  LICENSE            - MIT License
```

## License

MIT
