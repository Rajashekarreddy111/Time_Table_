import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Callable

from fastapi import Depends, HTTPException, Request, Response

from storage.memory_store import store

SESSION_COOKIE_NAME = "tt_session"
SESSION_TTL_DAYS = 7
ALLOWED_ROLES = {"admin", "coordinator"}


def _validation_error(message: str, details: list | None = None, status_code: int = 400) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": "ValidationError", "message": message, "details": details or []},
    )


def _normalize_role(role: str) -> str:
    return str(role or "").strip().lower()


def _sanitize_username(username: str) -> str:
    return str(username or "").strip()


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt_bytes = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, 200_000)
    return f"pbkdf2_sha256${salt_bytes.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, salt_hex, digest_hex = password_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    expected = _hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(expected, password_hash)


def _public_user(document: dict) -> dict:
    return {
        "id": str(document.get("id", "")),
        "username": str(document.get("username", "")),
        "role": str(document.get("role", "")),
    }


def ensure_default_admin() -> None:
    username = os.getenv("ADMIN_USERNAME", "Admin").strip()
    password = os.getenv("ADMIN_PASSWORD", "Admin@123").strip()
    existing = store.get_user_by_username(username)
    if existing:
        return

    existing_admins = store.list_users_by_creator(None, role="admin")
    if existing_admins:
        return

    store.create_user(
        username,
        {
            "id": store.next_user_id(),
            "role": "admin",
            "passwordHash": _hash_password(password),
            "createdBy": None,
            "createdAt": datetime.now(timezone.utc),
        },
    )


def authenticate_user(
    username: str,
    password: str,
    role: str,
) -> dict:
    ensure_default_admin()
    normalized_username = _sanitize_username(username)
    normalized_role = _normalize_role(role)
    if normalized_role not in ALLOWED_ROLES:
        raise _validation_error("Invalid role selected", [], status_code=401)
    user = store.get_user_by_username(normalized_username)
    if not user or str(user.get("role", "")).lower() != normalized_role:
        raise _validation_error("Invalid username, password, or role", [], status_code=401)
    if not verify_password(password, str(user.get("passwordHash", ""))):
        raise _validation_error("Invalid username, password, or role", [], status_code=401)
    return user


def create_session_for_user(user: dict, response: Response) -> None:
    session_id = store.next_session_id()
    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)
    store.save_session(
        session_id,
        {
            "username": user["username"],
            "role": user["role"],
            "expiresAt": expires_at,
        },
    )
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=int(timedelta(days=SESSION_TTL_DAYS).total_seconds()),
        path="/",
    )


def clear_session(response: Response, request: Request) -> None:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        store.delete_session(session_id)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


def get_current_user(request: Request) -> dict:
    ensure_default_admin()
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        raise _validation_error("Authentication required", [], status_code=401)
    session = store.get_session(session_id)
    if not session:
        raise _validation_error("Session expired or invalid", [], status_code=401)
    expires_at = session.get("expiresAt")
    if isinstance(expires_at, datetime):
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            store.delete_session(session_id)
            raise _validation_error("Session expired or invalid", [], status_code=401)
    user = store.get_user_by_username(str(session.get("username", "")))
    if not user:
        store.delete_session(session_id)
        raise _validation_error("Session user no longer exists", [], status_code=401)
    return user


def require_roles(*roles: str) -> Callable:
    normalized_roles = {_normalize_role(role) for role in roles}

    def dependency(user: dict = Depends(get_current_user)) -> dict:
        user_role = _normalize_role(str(user.get("role", "")))
        if user_role not in normalized_roles:
            raise _validation_error("You do not have permission to perform this action", [], status_code=403)
        return user

    return dependency


def create_coordinator(
    username: str,
    password: str,
    admin_user: dict,
) -> dict:
    normalized_username = _sanitize_username(username)
    if not normalized_username:
        raise _validation_error("Username is required", [])
    if len(password) < 6:
        raise _validation_error("Password must be at least 6 characters long", [])
    created = store.create_user(
        normalized_username,
        {
            "id": store.next_user_id(),
            "role": "coordinator",
            "passwordHash": _hash_password(password),
            "createdBy": admin_user["username"],
            "createdAt": datetime.now(timezone.utc),
        },
    )
    if not created:
        raise _validation_error("Username already exists", [{"username": normalized_username}], status_code=409)
    user = store.get_user_by_username(normalized_username)
    return _public_user(user or {"id": "", "username": normalized_username, "role": "coordinator"})


def list_coordinators(admin_user: dict) -> list[dict]:
    items = store.list_users_by_creator(admin_user["username"], role="coordinator")
    return [
        {
            "id": str(item.get("id", "")),
            "username": str(item.get("username", "")),
            "role": "coordinator",
            "createdBy": str(item.get("createdBy", "")) or None,
        }
        for item in items
    ]


def change_admin_password(admin_user: dict, current_password: str, new_password: str) -> None:
    if len(new_password) < 6:
        raise _validation_error("New password must be at least 6 characters long", [])
    stored_user = store.get_user_by_username(admin_user["username"])
    if not stored_user or not verify_password(current_password, str(stored_user.get("passwordHash", ""))):
        raise _validation_error("Current password is incorrect", [], status_code=401)
    store.update_user_password(admin_user["username"], _hash_password(new_password))


def change_admin_username(admin_user: dict, current_password: str, new_username: str) -> dict:
    normalized_username = _sanitize_username(new_username)
    if not normalized_username:
        raise _validation_error("New username is required", [])
    if normalized_username == str(admin_user.get("username", "")):
        raise _validation_error("New username must be different from the current username", [])
    stored_user = store.get_user_by_username(str(admin_user.get("username", "")))
    if not stored_user or not verify_password(current_password, str(stored_user.get("passwordHash", ""))):
        raise _validation_error("Current password is incorrect", [], status_code=401)
    renamed = store.rename_user(str(admin_user.get("username", "")), normalized_username)
    if not renamed:
        raise _validation_error("Username already exists", [{"username": normalized_username}], status_code=409)
    updated_user = store.get_user_by_username(normalized_username)
    return _public_user(updated_user or {"id": "", "username": normalized_username, "role": "admin"})


def reset_coordinator_password(username: str, new_password: str, admin_user: dict) -> None:
    if len(new_password) < 6:
        raise _validation_error("New password must be at least 6 characters long", [])
    user = store.get_user_by_username(_sanitize_username(username))
    if not user or str(user.get("role", "")).lower() != "coordinator":
        raise _validation_error("Coordinator not found", [], status_code=404)
    if str(user.get("createdBy", "")) != str(admin_user.get("username", "")):
        raise _validation_error("You can only manage coordinators you created", [], status_code=403)
    store.update_user_password(str(user.get("username", "")), _hash_password(new_password))
    store.delete_sessions_by_username(str(user.get("username", "")))


def delete_coordinator(username: str, admin_user: dict) -> None:
    user = store.get_user_by_username(_sanitize_username(username))
    if not user or str(user.get("role", "")).lower() != "coordinator":
        raise _validation_error("Coordinator not found", [], status_code=404)
    if str(user.get("createdBy", "")) != str(admin_user.get("username", "")):
        raise _validation_error("You can only manage coordinators you created", [], status_code=403)
    store.delete_user(str(user.get("username", "")))
