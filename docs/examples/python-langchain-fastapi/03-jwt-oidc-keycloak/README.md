# 03-jwt-oidc-keycloak: OpenAI-compatible endpoint with OIDC/Keycloak JWT validation

This example shows how to protect `/v1/responses` and `/v1/chat/completions` with JWT
validation backed by a real OIDC provider (Keycloak), using JWKS-based signature
verification instead of a shared static secret.

Implemented checks:
- Bearer token extraction from `Authorization` header
- Allowed algorithm validation (`RS256` in this example)
- Signature validation against keys fetched from the Keycloak JWKS endpoint (cached, matched by `kid`)
- Required claims validation (`sub`, `exp`, `iss`, `aud`)
- `iss` and `aud` validation
- Expiration / not-before validation

## Files

- `openai_responses_jwt_app.py`: FastAPI app + `JwksKeyResolver` configuration
- `docker-compose.yml`: local Keycloak instance for testing
- `realm-export.json`: pre-configured realm (`agent-runtime-demo`), public client (`agent-runtime-cli`) and test user (`alice` / `alice`)
- `.env.sample`: local configuration template

## Install

```powershell
cd docs/examples/python-langchain-fastapi/03-jwt-oidc-keycloak
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Set `PYTHONPATH` to use the package from this repository:

```powershell
$env:PYTHONPATH="../../..\packages\python"
```

## Configure

```powershell
Copy-Item .env.sample .env
```

Use only local/dev placeholders in this repository. Never commit real secrets.

## Start a local Keycloak

```powershell
docker compose up -d
```

Keycloak is available at `http://localhost:8080` (admin console: `admin` / `admin`).
The `agent-runtime-demo` realm, the public client `agent-runtime-cli` and the test
user `alice` (password `alice`) are imported automatically on startup.

## Run the app

```powershell
python -m uvicorn openai_responses_jwt_app:app --reload --port 8001
```

## Get a test JWT from Keycloak

This uses the Resource Owner Password Credentials grant on the public client, which
is only enabled here for local testing convenience.

```powershell
$response = Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8080/realms/agent-runtime-demo/protocol/openid-connect/token" `
  -ContentType "application/x-www-form-urlencoded" `
  -Body @{
    grant_type = "password"
    client_id  = "agent-runtime-cli"
    username   = "alice"
    password   = "alice"
  }

$token = $response.access_token
```

## Call protected endpoint

```powershell
$body = @{
  model = "gpt-5-chat"
  input = "hello from oidc"
  metadata = @{
    request_id = "oidc-demo-001"
    route_key = "jwt-protected-agent"
  }
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8001/v1/responses" `
  -ContentType "application/json" `
  -Headers @{ Authorization = "Bearer $token" } `
  -Body $body
```

If `Authorization` is missing or invalid, the runtime returns `401` with a structured
authentication error.

## Notes

- `JwksKeyResolver` fetches and caches the JWKS document (`cache_ttl_seconds`, default
  300s) and picks the right key using the `kid` from the token header, so key rotation
  on the Keycloak side does not require restarting the app.
- There is no `.well-known/openid-configuration` discovery in the runtime code: the
  JWKS URL and issuer are built directly from `KEYCLOAK_BASE_URL` and `KEYCLOAK_REALM`.
- For a production IdP, replace the password grant with an interactive flow
  (Authorization Code + PKCE) — it is only used here to obtain a token without a browser.
