"""
Authentication service for user management, password hashing, and JWT tokens.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import psycopg2
from fastapi import HTTPException, status
from jose import JWTError, jwt

from config import get_settings
from database import get_db
from schemas.auth import TokenPayload, UserCreate, UserLogin, UserResponse

_settings = get_settings()
SECRET_KEY = _settings.jwt_secret_key
ALGORITHM = _settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = _settings.jwt_access_token_expire_minutes


def _coerce_created_at(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise ValueError(f"Unsupported created_at value: {value!r}")


def _to_user_response(row) -> UserResponse:
    return UserResponse(
        id=int(row["id"]),
        email=row["email"],
        username=row["username"],
        is_active=bool(row["is_active"]),
        created_at=_coerce_created_at(row["created_at"]),
    )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    password_bytes = plain_password.encode("utf-8")[:72]
    hashed_bytes = (
        hashed_password.encode("utf-8") if isinstance(hashed_password, str) else hashed_password
    )
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def get_password_hash(password: str) -> str:
    """Hash a plain password."""
    password_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if "sub" in to_encode and to_encode["sub"] is not None:
        to_encode["sub"] = str(to_encode["sub"])
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[TokenPayload]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            return None
        return TokenPayload(sub=int(user_id), exp=payload.get("exp"))
    except JWTError:
        return None


class AuthService:
    """Service for authentication operations."""

    def create_user(self, user_data: UserCreate) -> UserResponse:
        """Create a new user with hashed password."""
        hashed_password = get_password_hash(user_data.password)

        with get_db() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO users (email, username, hashed_password, is_active)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, email, username, is_active, created_at
                    """,
                    (user_data.email, user_data.username, hashed_password, True),
                )
                row = cursor.fetchone()
                conn.commit()
                return _to_user_response(row)
            except psycopg2.IntegrityError as exc:
                conn.rollback()
                constraint_name = str(
                    getattr(getattr(exc, "diag", None), "constraint_name", "") or ""
                ).lower()
                error_msg = str(exc).lower()
                if "email" in constraint_name or "email" in error_msg:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email already registered",
                    )
                if "username" in constraint_name or "username" in error_msg:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Username already taken",
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User already exists",
                )

    def authenticate_user(self, login_data: UserLogin) -> UserResponse:
        """Authenticate a user by email and password."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, email, username, hashed_password, is_active, created_at
                FROM users
                WHERE email = %s
                """,
                (login_data.email,),
            )
            row = cursor.fetchone()

            if not row:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="No account found with this email address. Please register first.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            if not verify_password(login_data.password, row["hashed_password"]):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect password. Please try again.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            if not row["is_active"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your account has been disabled. Please contact support.",
                )

            return _to_user_response(row)

    def get_user_by_id(self, user_id: int) -> Optional[UserResponse]:
        """Get a user by ID."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, email, username, is_active, created_at
                FROM users
                WHERE id = %s
                """,
                (user_id,),
            )
            row = cursor.fetchone()

            if not row:
                return None

            return _to_user_response(row)


_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """Get or create the auth service singleton."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
