"""Tests for Conversation History, SQLite Persistence, and Auth Endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from syntrak.config import SyntrakConfig
from syntrak.server.app import create_app
from syntrak.server.auth import create_jwt_token
from syntrak.server.db import Database


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_syntrak.db"
    return Database(db_path=db_file)


def test_database_crud(temp_db):
    # Test user creation
    user = temp_db.upsert_user("user-123", "dev@example.com", "Dev Tester", "https://img.com/avatar.png")
    assert user["id"] == "user-123"
    assert user["email"] == "dev@example.com"

    # Test conversation creation
    conv = temp_db.create_conversation("user-123", "Initial Chat")
    assert conv["id"] is not None
    assert conv["title"] == "Initial Chat"

    # Test adding messages
    msg1 = temp_db.add_message(conv["id"], "user", "Hello Syntrak!")
    assert msg1["content"] == "Hello Syntrak!"

    msg2 = temp_db.add_message(conv["id"], "assistant", "Hello! How can I help?", events=[{"event_type": "done"}])
    assert msg2["role"] == "assistant"
    assert len(msg2["events"]) == 1

    # Test retrieval
    messages = temp_db.get_messages(conv["id"])
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"

    # Test title update
    updated = temp_db.update_conversation_title(conv["id"], "Renamed Chat", user_id="user-123")
    assert updated is True
    conv_updated = temp_db.get_conversation(conv["id"])
    assert conv_updated["title"] == "Renamed Chat"

    # Test delete
    deleted = temp_db.delete_conversation(conv["id"], user_id="user-123")
    assert deleted is True
    assert temp_db.get_conversation(conv["id"]) is None


@pytest.mark.asyncio
async def test_conversation_api_endpoints(temp_db):
    cfg = SyntrakConfig()
    app = create_app(config=cfg, db=temp_db)

    test_user = {"id": "test-user-456", "email": "test@syntrak.io", "name": "Syntrak Tester"}
    token = create_jwt_token(test_user)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Test /api/auth/me
        me_res = await client.get("/api/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["email"] == "test@syntrak.io"

        # 2. Test create conversation
        create_res = await client.post("/api/conversations", json={"title": "Refactor Code"}, headers=headers)
        assert create_res.status_code == 200
        conv_data = create_res.json()
        conv_id = conv_data["id"]
        assert conv_data["title"] == "Refactor Code"

        # 3. Test list conversations
        list_res = await client.get("/api/conversations", headers=headers)
        assert list_res.status_code == 200
        convs = list_res.json()
        assert len(convs) == 1
        assert convs[0]["id"] == conv_id

        # 4. Test get conversation detail
        detail_res = await client.get(f"/api/conversations/{conv_id}", headers=headers)
        assert detail_res.status_code == 200
        assert detail_res.json()["title"] == "Refactor Code"

        # 5. Test rename conversation
        rename_res = await client.patch(f"/api/conversations/{conv_id}", json={"title": "Updated Refactor"}, headers=headers)
        assert rename_res.status_code == 200
        assert rename_res.json()["title"] == "Updated Refactor"

        # 6. Test delete conversation
        del_res = await client.delete(f"/api/conversations/{conv_id}", headers=headers)
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "success"

        # Verify it is deleted
        get_deleted = await client.get(f"/api/conversations/{conv_id}", headers=headers)
        assert get_deleted.status_code == 404

        # 7. Test Logout endpoint
        logout_res = await client.post("/api/auth/logout")
        assert logout_res.status_code == 200
        assert logout_res.json()["status"] == "success"


