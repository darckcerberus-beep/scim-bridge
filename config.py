"""
config.py
---------
Central place for all runtime configuration.
Values are read from environment variables (loaded from .env by server.py).

Change only this file to adjust bridge behaviour without touching core logic.
"""

import os
from dotenv import load_dotenv

# Load .env file if present (ignored in production if env vars are already set)
load_dotenv()


# --------------------------------------------------------------------------
# SCIM bridge server
# --------------------------------------------------------------------------

# TCP port the Flask server listens on
PORT: int = int(os.getenv("PORT", "3000"))

# Static bearer token your IdP sends in the Authorization header.
# Keep this value secret.
SCIM_BEARER_TOKEN: str = os.getenv("SCIM_BEARER_TOKEN", "change-me")

# Enable verbose debug logging when True
DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"


# --------------------------------------------------------------------------
# Target API  (the system without native SCIM support)
# --------------------------------------------------------------------------

# Base URL of the target API, e.g. "https://app.example.com/api"
TARGET_API_BASE_URL: str = os.getenv("TARGET_API_BASE_URL", "http://localhost:4000")

# How to authenticate against the target API.
# Supported values: "bearer" | "basic" | "apikey"
TARGET_AUTH_TYPE: str = os.getenv("TARGET_AUTH_TYPE", "bearer")

# Used when TARGET_AUTH_TYPE == "bearer"
TARGET_AUTH_TOKEN: str = os.getenv("TARGET_AUTH_TOKEN", "")

# Used when TARGET_AUTH_TYPE == "basic"
TARGET_AUTH_USERNAME: str = os.getenv("TARGET_AUTH_USERNAME", "")
TARGET_AUTH_PASSWORD: str = os.getenv("TARGET_AUTH_PASSWORD", "")

# Used when TARGET_AUTH_TYPE == "apikey"
TARGET_AUTH_HEADER: str = os.getenv("TARGET_AUTH_HEADER", "X-Api-Key")
TARGET_AUTH_KEY: str = os.getenv("TARGET_AUTH_KEY", "")


# --------------------------------------------------------------------------
# Target API endpoint mapping
# Use {id} as a placeholder for the user identifier.
# Override these via environment variables to match the target system's API.
# --------------------------------------------------------------------------

TARGET_ENDPOINTS: dict = {
    # List all users  (GET)
    "list_users":   os.getenv("TARGET_ENDPOINT_LIST_USERS",   "/users"),
    # Get a single user by id  (GET)
    "get_user":     os.getenv("TARGET_ENDPOINT_GET_USER",     "/users/{id}"),
    # Create a new user  (POST)
    "create_user":  os.getenv("TARGET_ENDPOINT_CREATE_USER",  "/users"),
    # Replace a user by id  (PUT)
    "replace_user": os.getenv("TARGET_ENDPOINT_REPLACE_USER", "/users/{id}"),
    # Update a user by id  (PATCH)
    "update_user":  os.getenv("TARGET_ENDPOINT_UPDATE_USER",  "/users/{id}"),
    # Delete a user by id  (DELETE)
    "delete_user":  os.getenv("TARGET_ENDPOINT_DELETE_USER",  "/users/{id}"),
}
