from fastapi.testclient import TestClient

import main
from services import auth as auth_service
from storage.memory_store import MemoryStore


def _isolated_store() -> MemoryStore:
    store = MemoryStore()
    store._mongo_available = False
    store._counters_mem = {}
    store._users_mem = {}
    store._sessions_mem = {}
    return store


def test_jwt_survives_username_change_and_rotates_on_password_change(monkeypatch):
    store = _isolated_store()
    monkeypatch.setattr(auth_service, "store", store)
    monkeypatch.setattr(main, "store", store)

    with TestClient(main.app) as client:
        login_response = client.post(
            "/api/auth/login",
            json={"username": "Admin", "password": "Admin@1234", "role": "admin"},
        )
        assert login_response.status_code == 200
        original_token = login_response.json()["sessionId"]

        me_response = client.get("/api/auth/me")
        assert me_response.status_code == 200
        assert me_response.json()["username"] == "Admin"

        rename_response = client.post(
            "/api/auth/change-username",
            json={"currentPassword": "Admin@1234", "newUsername": "AdminRenamed"},
        )
        assert rename_response.status_code == 200
        renamed_token = rename_response.headers.get(auth_service.SESSION_HEADER_NAME)
        assert renamed_token
        assert renamed_token != original_token

        me_after_rename = client.get("/api/auth/me")
        assert me_after_rename.status_code == 200
        assert me_after_rename.json()["username"] == "AdminRenamed"

        password_response = client.post(
            "/api/auth/change-password",
            json={"currentPassword": "Admin@1234", "newPassword": "Admin@5678"},
        )
        assert password_response.status_code == 200
        password_token = password_response.headers.get(auth_service.SESSION_HEADER_NAME)
        assert password_token
        assert password_token != renamed_token

        me_after_password_change = client.get("/api/auth/me")
        assert me_after_password_change.status_code == 200
        assert me_after_password_change.json()["username"] == "AdminRenamed"

    with TestClient(main.app) as stale_client:
        stale_token_response = stale_client.get(
            "/api/auth/me",
            headers={auth_service.SESSION_HEADER_NAME: renamed_token},
        )
        assert stale_token_response.status_code == 401
