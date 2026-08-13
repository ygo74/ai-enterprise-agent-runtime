# 02-jwt-authentication: OpenAI-compatible endpoint with JWT validation

This example shows how to protect `/v1/responses` and `/v1/chat/completions` with JWT validation in the Python runtime.

Implemented checks:
- Bearer token extraction from `Authorization` header
- Allowed algorithm validation (`HS256` in this example)
- Signature validation
- Required claims validation (`sub`, `exp`, `nbf`, `iss`, `aud`)
- `iss` and `aud` validation
- Expiration / not-before validation

## Files

- `openai_responses_jwt_app.py`: FastAPI app + JWT configuration
- `generate_dev_jwt.py`: helper to generate a local short-lived dev token
- `.env.sample`: local configuration template

## Install

```powershell
cd docs/examples/python-langchain-fastapi/02-jwt-authentication
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

## Run

```powershell
python -m uvicorn openai_responses_jwt_app:app --reload --port 8002
```

## Generate a test JWT

```powershell
$token = python generate_dev_jwt.py --secret "change-me-in-local-env" --subject "alice"
```

## Call protected endpoint

```powershell
$body = @{
  model = "gpt-5-chat"
  input = "hello from jwt"
  metadata = @{
    request_id = "jwt-demo-001"
    route_key = "jwt-protected-agent"
  }
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8002/v1/responses" `
  -ContentType "application/json" `
  -Headers @{ Authorization = "Bearer $token" } `
  -Body $body
```

If `Authorization` is missing or invalid, the runtime returns `401` with a structured authentication error.
