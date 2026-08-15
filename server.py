"""
server.py
---------
Minimal SCIM 2.0 bridge built with Flask.

Supported SCIM endpoints (Users only):
  GET    /scim/v2/Users          - list users
  POST   /scim/v2/Users          - create a user
  GET    /scim/v2/Users/<id>     - get a user
  PUT    /scim/v2/Users/<id>     - replace a user
  PATCH  /scim/v2/Users/<id>     - update a user
  DELETE /scim/v2/Users/<id>     - delete a user

The bridge forwards each SCIM operation to the target system's REST API
(configured in config.py / .env) and translates between SCIM and the target
format using adapter.py.

Run:
  pip install -r requirements.txt
  cp .env.example .env   # then edit .env
  python server.py
"""

import logging
import sys
from functools import wraps
from typing import Callable

import requests
from flask import Flask, Response, jsonify, request

import adapter
import config as cfg

# --------------------------------------------------------------------------
# Logging setup
# --------------------------------------------------------------------------
# Use DEBUG level when cfg.DEBUG is True, INFO otherwise.
logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG if cfg.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("scim_bridge.server")

# --------------------------------------------------------------------------
# Flask app
# --------------------------------------------------------------------------
app = Flask(__name__)

# Silence Flask's own request logger in non-debug mode to reduce noise
if not cfg.DEBUG:
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.WARNING)

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _build_auth_headers() -> dict:
    """Return the HTTP headers needed to authenticate against the target API."""
    auth_type = cfg.TARGET_AUTH_TYPE.lower()

    if auth_type == "bearer":
        return {"Authorization": f"******"}

    if auth_type == "apikey":
        return {cfg.TARGET_AUTH_HEADER: cfg.TARGET_AUTH_KEY}

    # "basic" auth is handled by requests' auth= parameter, not headers
    return {}


def _build_auth_kwargs() -> dict:
    """Return keyword arguments for requests.request() authentication."""
    if cfg.TARGET_AUTH_TYPE.lower() == "basic":
        return {"auth": (cfg.TARGET_AUTH_USERNAME, cfg.TARGET_AUTH_PASSWORD)}
    return {}


def _target_url(endpoint_key: str, user_id: str = "") -> str:
    """
    Build a full URL for the target API.

    :param endpoint_key: Key in cfg.TARGET_ENDPOINTS (e.g. "get_user")
    :param user_id: The user identifier to substitute for {id}
    :returns: Absolute URL string
    """
    path: str = cfg.TARGET_ENDPOINTS[endpoint_key].replace("{id}", user_id)
    url = f"{cfg.TARGET_API_BASE_URL}{path}"
    logger.debug("Resolved target URL for '%s': %s", endpoint_key, url)
    return url


def _call_target(method: str, url: str, json_body: dict | None = None) -> requests.Response:
    """
    Make an HTTP request to the target API.

    :param method:    HTTP method (GET, POST, PUT, PATCH, DELETE)
    :param url:       Full target URL
    :param json_body: Optional JSON payload
    :returns: requests.Response
    :raises: requests.HTTPError when the target API returns a 4xx/5xx status
    """
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        **_build_auth_headers(),
    }
    kwargs = _build_auth_kwargs()

    logger.debug("→ %s %s  body=%s", method, url, json_body)
    response = requests.request(
        method,
        url,
        headers=headers,
        json=json_body,
        timeout=30,
        **kwargs,
    )
    logger.debug("← %s %s", response.status_code, response.text[:500])
    response.raise_for_status()
    return response


def _scim_error(message: str, status: int) -> tuple:
    """Return a SCIM-compliant error response tuple (Flask can return it directly)."""
    body = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
        "detail":  message,
        "status":  str(status),
    }
    return jsonify(body), status


# --------------------------------------------------------------------------
# Authentication decorator
# --------------------------------------------------------------------------

def require_scim_auth(f: Callable) -> Callable:
    """
    Decorator that verifies the incoming SCIM request carries a valid
    bearer token matching SCIM_BEARER_TOKEN from config.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header: str = request.headers.get("Authorization", "")
        logger.debug("Incoming Authorization header: %s", auth_header[:30])

        if not auth_header.startswith("Bearer "):
            logger.warning("Missing or malformed Authorization header")
            return _scim_error("Unauthorized – ****** required", 401)

        token = auth_header[len("Bearer "):]
        if token != cfg.SCIM_BEARER_TOKEN:
            logger.warning("Invalid bearer token presented")
            return _scim_error("Unauthorized – invalid token", 401)

        return f(*args, **kwargs)

    return decorated


# --------------------------------------------------------------------------
# SCIM /Users endpoints
# --------------------------------------------------------------------------

@app.route("/scim/v2/Users", methods=["GET"])
@require_scim_auth
def list_users() -> tuple:
    """
    SCIM: List Users
    GET /scim/v2/Users

    Fetches all users from the target API and wraps them in a SCIM
    ListResponse envelope.
    """
    logger.info("SCIM list_users request")

    try:
        resp = _call_target("GET", _target_url("list_users"))
        raw_users: list = resp.json()

        # Translate each target user object into a SCIM User dict
        scim_users = [adapter.target_to_scim(u) for u in raw_users]

        list_response = {
            "schemas":      ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
            "totalResults": len(scim_users),
            "startIndex":   1,
            "itemsPerPage": len(scim_users),
            "Resources":    scim_users,
        }
        logger.debug("Returning %d users", len(scim_users))
        return jsonify(list_response), 200

    except requests.HTTPError as exc:
        logger.error("Target API error on list_users: %s", exc)
        return _scim_error("Target API error – see server logs", 502)


@app.route("/scim/v2/Users/<string:user_id>", methods=["GET"])
@require_scim_auth
def get_user(user_id: str) -> tuple:
    """
    SCIM: Get User
    GET /scim/v2/Users/<user_id>

    Fetches a single user from the target API by ID.
    """
    logger.info("SCIM get_user request for id=%s", user_id)

    try:
        resp = _call_target("GET", _target_url("get_user", user_id))
        scim_user = adapter.target_to_scim(resp.json())
        return jsonify(scim_user), 200

    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return _scim_error(f"User {user_id} not found", 404)
        logger.error("Target API error on get_user: %s", exc)
        return _scim_error("Target API error – see server logs", 502)


@app.route("/scim/v2/Users", methods=["POST"])
@require_scim_auth
def create_user() -> tuple:
    """
    SCIM: Create User
    POST /scim/v2/Users

    Translates the incoming SCIM User payload and creates the user in the
    target API.
    """
    scim_user: dict = request.get_json(force=True, silent=True) or {}
    logger.info("SCIM create_user request: userName=%s", scim_user.get("userName"))
    logger.debug("create_user payload: %s", scim_user)

    try:
        target_payload = adapter.scim_to_target(scim_user)
        resp = _call_target("POST", _target_url("create_user"), target_payload)
        created_scim = adapter.target_to_scim(resp.json())
        return jsonify(created_scim), 201

    except requests.HTTPError as exc:
        logger.error("Target API error on create_user: %s", exc)
        return _scim_error("Target API error – see server logs", 502)


@app.route("/scim/v2/Users/<string:user_id>", methods=["PUT"])
@require_scim_auth
def replace_user(user_id: str) -> tuple:
    """
    SCIM: Replace User (full update)
    PUT /scim/v2/Users/<user_id>

    Replaces all attributes of an existing user in the target API.
    """
    scim_user: dict = request.get_json(force=True, silent=True) or {}
    logger.info("SCIM replace_user request for id=%s", user_id)
    logger.debug("replace_user payload: %s", scim_user)

    try:
        target_payload = adapter.scim_to_target(scim_user)
        resp = _call_target("PUT", _target_url("replace_user", user_id), target_payload)
        updated_scim = adapter.target_to_scim(resp.json())
        return jsonify(updated_scim), 200

    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return _scim_error(f"User {user_id} not found", 404)
        logger.error("Target API error on replace_user: %s", exc)
        return _scim_error("Target API error – see server logs", 502)


@app.route("/scim/v2/Users/<string:user_id>", methods=["PATCH"])
@require_scim_auth
def update_user(user_id: str) -> tuple:
    """
    SCIM: Update User (partial update)
    PATCH /scim/v2/Users/<user_id>

    Applies a SCIM PatchOp to the user.  For simplicity the bridge converts
    the patch operations into a flat dict and sends it as a PATCH to the
    target API.  Extend this function for more complex PatchOp handling.
    """
    scim_patch: dict = request.get_json(force=True, silent=True) or {}
    logger.info("SCIM update_user request for id=%s", user_id)
    logger.debug("update_user patch body: %s", scim_patch)

    # Flatten SCIM PatchOp Operations into a simple dict for the target API.
    # Each operation has: { "op": "replace", "path": "active", "value": false }
    patch_payload: dict = {}
    for op in scim_patch.get("Operations", []):
        op_type: str = op.get("op", "").lower()
        path: str    = op.get("path", "")
        value        = op.get("value")

        logger.debug("PatchOp: op=%s path=%s value=%s", op_type, path, value)

        if op_type in ("replace", "add") and path:
            patch_payload[path] = value
        elif op_type == "remove" and path:
            patch_payload[path] = None

    try:
        resp = _call_target("PATCH", _target_url("update_user", user_id), patch_payload)
        updated_scim = adapter.target_to_scim(resp.json())
        return jsonify(updated_scim), 200

    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return _scim_error(f"User {user_id} not found", 404)
        logger.error("Target API error on update_user: %s", exc)
        return _scim_error("Target API error – see server logs", 502)


@app.route("/scim/v2/Users/<string:user_id>", methods=["DELETE"])
@require_scim_auth
def delete_user(user_id: str) -> tuple:
    """
    SCIM: Delete User
    DELETE /scim/v2/Users/<user_id>

    Deletes a user from the target API.
    """
    logger.info("SCIM delete_user request for id=%s", user_id)

    try:
        _call_target("DELETE", _target_url("delete_user", user_id))
        # SCIM spec requires 204 No Content on successful deletion
        return Response(status=204)

    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return _scim_error(f"User {user_id} not found", 404)
        logger.error("Target API error on delete_user: %s", exc)
        return _scim_error("Target API error – see server logs", 502)


# --------------------------------------------------------------------------
# SCIM /ServiceProviderConfig  (discovery endpoint)
# --------------------------------------------------------------------------

@app.route("/scim/v2/ServiceProviderConfig", methods=["GET"])
@require_scim_auth
def service_provider_config() -> tuple:
    """
    SCIM: Service Provider Configuration
    GET /scim/v2/ServiceProviderConfig

    Returns the capabilities of this SCIM bridge so IdPs can discover what
    operations are supported.
    """
    logger.info("SCIM ServiceProviderConfig request")

    config_response = {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
        "documentationUri": "https://github.com/darckcerberus-beep/scim-bridge",
        "patch":    {"supported": True},
        "bulk":     {"supported": False, "maxOperations": 0, "maxPayloadSize": 0},
        "filter":   {"supported": False, "maxResults": 0},
        "changePassword":  {"supported": False},
        "sort":     {"supported": False},
        "etag":     {"supported": False},
        "authenticationSchemes": [
            {
                "type":        "oauthbearertoken",
                "name":        "OAuth ******",
                "description": "Authentication scheme using the OAuth ****** Standard",
            }
        ],
    }
    return jsonify(config_response), 200


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info(
        "Starting SCIM bridge on port %d  (debug=%s, target=%s)",
        cfg.PORT,
        cfg.DEBUG,
        cfg.TARGET_API_BASE_URL,
    )
    # Use Flask's built-in dev server.
    # In production, run behind gunicorn or uvicorn instead.
    app.run(host="0.0.0.0", port=cfg.PORT, debug=cfg.DEBUG)
