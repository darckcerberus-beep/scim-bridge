# scim-bridge

A **simple, customisable SCIM 2.0 bridge** written in Python.  
Use it to connect an identity provider (IdP) such as Okta, Azure AD, or JumpCloud to any software that exposes a **REST API for user management** but does **not** natively support the SCIM protocol.

---

## How it works

```
Identity Provider (Okta / AzureAD / ...)
        │  SCIM 2.0 over HTTPS
        ▼
  ┌─────────────┐
  │  server.py  │  ← Flask HTTP server, validates bearer token
  │  (bridge)   │
  └──────┬──────┘
         │  translates via adapter.py
         ▼
  ┌─────────────┐
  │  Target API │  ← your app's existing REST API
  └─────────────┘
```

1. **`server.py`** — Flask server that exposes the SCIM 2.0 `/Users` endpoints.  
2. **`adapter.py`** — Translates between SCIM 2.0 and the target API's user model. **Edit this file** for each target system.  
3. **`config.py`** — Reads all settings from environment variables (`.env`).

---

## Quick start

```bash
# 1. Clone the repo
git clone https://github.com/darckcerberus-beep/scim-bridge.git
cd scim-bridge

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure the bridge
cp .env.example .env
# Edit .env with your target API URL, credentials, and a strong bearer token

# 4. Run
python server.py
```

The bridge listens on `http://0.0.0.0:3000` by default.

---

## Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `PORT` | `3000` | Port the bridge listens on |
| `SCIM_BEARER_TOKEN` | *(required)* | Secret token your IdP sends |
| `TARGET_API_BASE_URL` | `http://localhost:4000` | Base URL of the target REST API |
| `TARGET_AUTH_TYPE` | `bearer` | `bearer` \| `basic` \| `apikey` |
| `TARGET_AUTH_TOKEN` | — | Token for bearer auth |
| `TARGET_AUTH_USERNAME` | — | Username for basic auth |
| `TARGET_AUTH_PASSWORD` | — | Password for basic auth |
| `TARGET_AUTH_HEADER` | `X-Api-Key` | Header name for apikey auth |
| `TARGET_AUTH_KEY` | — | API key value |
| `TARGET_ENDPOINT_*` | `/users`, `/users/{id}` | Override any endpoint path |
| `DEBUG` | `false` | Set to `true` for verbose logs |

---

## Customising for your target system

Open **`adapter.py`** and update two functions:

- **`scim_to_target(scim_user)`** — maps SCIM fields → target API fields  
- **`target_to_scim(target_user)`** — maps target API fields → SCIM fields

The comments in the file mark exactly which dicts to edit with `⚠️ Customise this`.

---

## Supported SCIM operations

| Method | Path | Operation |
|---|---|---|
| `GET` | `/scim/v2/Users` | List users |
| `POST` | `/scim/v2/Users` | Create user |
| `GET` | `/scim/v2/Users/<id>` | Get user |
| `PUT` | `/scim/v2/Users/<id>` | Replace user |
| `PATCH` | `/scim/v2/Users/<id>` | Update user |
| `DELETE` | `/scim/v2/Users/<id>` | Delete user |
| `GET` | `/scim/v2/ServiceProviderConfig` | Bridge capabilities |

---

## Production deployment

For production, run behind **gunicorn** instead of Flask's dev server:

```bash
pip install gunicorn
gunicorn -w 2 -b 0.0.0.0:3000 "server:app"
```
