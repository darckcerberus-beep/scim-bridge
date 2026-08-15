"""
adapter.py
----------
Translates SCIM 2.0 user objects into the format expected by the target API,
and translates target API responses back into SCIM 2.0 objects.

THIS IS THE FILE YOU CUSTOMISE for each target system.

Two functions you must implement / adjust:
  scim_to_target(scim_user)   -> dict to POST/PUT/PATCH to the target API
  target_to_scim(target_user) -> SCIM 2.0 User dict

The default implementations assume the target API uses a simple JSON user model:
  { "id": "...", "email": "...", "firstName": "...", "lastName": "...", "active": true }
Override as needed.
"""

import logging
from typing import Any

import config as cfg

# --------------------------------------------------------------------------
# Module-level logger
# --------------------------------------------------------------------------
# server.py configures the root logger; we just grab a child logger here.
logger = logging.getLogger("scim_bridge.adapter")


# --------------------------------------------------------------------------
# SCIM → Target API translation
# --------------------------------------------------------------------------

def scim_to_target(scim_user: dict) -> dict:
    """
    Convert a SCIM 2.0 User dict into the payload the target API expects.

    Customise this function to match the target system's user model.

    :param scim_user: SCIM 2.0 User dict received from the identity provider
    :returns: Payload dict to send to the target API
    """
    logger.debug("scim_to_target input: %s", scim_user)

    # --- Extract commonly used SCIM fields with safe defaults ---------------

    # Primary email (fall back to userName if no emails list is present)
    emails: list = scim_user.get("emails", [])
    primary_email: str = next(
        (e["value"] for e in emails if e.get("primary")),
        emails[0]["value"] if emails else scim_user.get("userName", ""),
    )

    name: dict = scim_user.get("name", {})
    first_name: str = name.get("givenName", "")
    last_name: str = name.get("familyName", "")

    # ⚠️  Customise this dict to match the target system's expected fields.
    target_payload: dict = {
        "email":     primary_email,
        "firstName": first_name,
        "lastName":  last_name,
        # SCIM uses "active" (bool) to signal enabled / disabled state
        "active":    scim_user.get("active", True),
        # Pass through the SCIM userName as a username field
        "username":  scim_user.get("userName", primary_email),
    }

    logger.debug("scim_to_target output: %s", target_payload)
    return target_payload


# --------------------------------------------------------------------------
# Target API → SCIM translation
# --------------------------------------------------------------------------

def target_to_scim(target_user: dict) -> dict:
    """
    Convert a target API user dict into a SCIM 2.0 User dict.

    Customise this function to match the target system's user model.

    :param target_user: User dict returned by the target API
    :returns: SCIM 2.0 User dict
    """
    logger.debug("target_to_scim input: %s", target_user)

    user_id: Any = target_user.get("id", "")
    email: str   = target_user.get("email", target_user.get("username", str(user_id)))
    first: str   = target_user.get("firstName", "")
    last: str    = target_user.get("lastName", "")

    # ⚠️  Customise this dict to match the SCIM fields your IdP expects.
    scim_user: dict = {
        "schemas":  ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "id":       str(user_id),
        "userName": email,
        "name": {
            "givenName":  first,
            "familyName": last,
            "formatted":  f"{first} {last}".strip(),
        },
        "emails": [{"value": email, "primary": True}] if email else [],
        "active": target_user.get("active", True),
        # SCIM meta block (required by the spec)
        "meta": {
            "resourceType": "User",
            "location": f"{cfg.TARGET_API_BASE_URL}/Users/{user_id}",
        },
    }

    logger.debug("target_to_scim output: %s", scim_user)
    return scim_user
