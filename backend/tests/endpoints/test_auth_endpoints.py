"""
Endpoint tests for authentication routes.

These tests use a fake AuthService, so they do not require PostgreSQL.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status


class FakeAuthService:
    """
    Fake auth service matching the methods used by routers/auth.py.
    """

    def __init__(self):
        from schemas.auth import UserResponse

        self.user = UserResponse(
            id=1,
            email="taha@example.com",
            username="taha",
            is_active=True,
            created_at=datetime(2026, 1, 1, 12, 0, 0),
        )

    def create_user(self, user_data):
        from schemas.auth import UserResponse

        if user_data.email == "exists@example.com":
            raise HTTPException(status_code=400, detail="Email already registered")

        return UserResponse(
            id=2,
            email=user_data.email,
            username=user_data.username,
            is_active=True,
            created_at=datetime(2026, 1, 1, 12, 0, 0),
        )

    def authenticate_user(self, login_data):
        if login_data.email != "taha@example.com" or login_data.password != "correct-password":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect password. Please try again.",
            )

        return self.user

    def get_user_by_id(self, user_id):
        if int(user_id) == self.user.id:
            return self.user
        return None


@pytest.fixture
def fake_auth_service(client):
    """
    Override the real auth service dependency with FakeAuthService.
    """
    import main
    import routers.auth as auth_router

    service = FakeAuthService()
    main.app.dependency_overrides[auth_router.get_auth_service] = lambda: service
    return service


def test_register_returns_token_and_user(client, fake_auth_service):
    """Successful registration should return token and safe user data."""
    response = client.post(
        "/auth/register",
        json={
            "email": "new@example.com",
            "username": "newuser",
            "password": "strong-password",
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["user"]["email"] == "new@example.com"
    assert "password" not in data["user"]


def test_register_rejects_invalid_email(client, fake_auth_service):
    """Invalid email should be rejected by Pydantic."""
    response = client.post(
        "/auth/register",
        json={
            "email": "not-an-email",
            "username": "newuser",
            "password": "strong-password",
        },
    )

    assert response.status_code == 422


def test_login_returns_token_for_valid_credentials(client, fake_auth_service):
    """Valid login should return token and user info."""
    response = client.post(
        "/auth/login",
        json={
            "email": "taha@example.com",
            "password": "correct-password",
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["user"]["username"] == "taha"


def test_login_rejects_wrong_credentials(client, fake_auth_service):
    """Wrong login details should return 401."""
    response = client.post(
        "/auth/login",
        json={
            "email": "taha@example.com",
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401


def test_me_returns_current_user_from_bearer_token(client, fake_auth_service, monkeypatch):
    """
    /auth/me should return the current user.

    We patch token decoding here because JWT internals belong in auth service
    unit tests, not endpoint tests.
    """
    import routers.auth as auth_router

    monkeypatch.setattr(
        auth_router,
        "decode_access_token",
        lambda _token: SimpleNamespace(sub=fake_auth_service.user.id),
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer fake-token"},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["id"] == 1
    assert data["email"] == "taha@example.com"


def test_logout_returns_message(client):
    """Logout currently tells frontend to remove token client-side."""
    response = client.post("/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"message": "Successfully logged out"}