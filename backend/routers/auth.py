"""
Authentication Router - FastAPI endpoints for user authentication.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from schemas.auth import UserCreate, UserLogin, Token, UserResponse
from services.auth_service import get_auth_service, AuthService, decode_access_token, create_access_token

# Security scheme for JWT token
security = HTTPBearer()

router = APIRouter(prefix="/auth", tags=["authentication"])


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: AuthService = Depends(get_auth_service)
) -> UserResponse:
    """Dependency to get the current authenticated user from JWT token."""
    token = credentials.credentials
    token_payload = decode_access_token(token)
    
    if token_payload is None or token_payload.sub is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = auth_service.get_user_by_id(token_payload.sub)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    return user


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Register a new user.
    
    Returns:
        Token object containing JWT access token and user data.
    """
    # Create user
    user = auth_service.create_user(user_data)
    
    # Generate access token
    access_token = create_access_token({"sub": user.id})
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=user
    )


@router.post("/login", response_model=Token)
async def login(
    login_data: UserLogin,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Authenticate a user and return JWT token.
    
    Returns:
        Token object containing JWT access token and user data.
    """
    # authenticate_user now raises HTTPException with descriptive messages
    user = auth_service.authenticate_user(login_data)
    
    # Generate access token
    access_token = create_access_token({"sub": user.id})
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=user
    )


@router.post("/logout")
async def logout():
    """
    Logout endpoint (client-side token removal).
    
    Note: JWT tokens are stateless. The client should remove the token.
    This endpoint is provided for completeness and future blacklist implementation.
    """
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get current authenticated user information.
    
    Returns:
        UserResponse object with user details.
    """
    return current_user
