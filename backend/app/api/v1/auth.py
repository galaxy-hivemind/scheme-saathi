"""
Authentication endpoints for user registration, login, and identity verification.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.dependencies import get_db
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from app.schemas.common import APIResponse
from app.services import auth_service

router = APIRouter()


@router.post(
    "/register",
    response_model=APIResponse[TokenResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new citizen account",
)
def register(
    req: RegisterRequest,
    db: Session = Depends(get_db),
) -> APIResponse[TokenResponse]:
    """
    Register a new user account with email, password, and optional full name.
    Automatically creates the citizen profile and returns a signed JWT access token.
    """
    user, token_response = auth_service.register_user(db, req)
    return APIResponse.ok(token_response)


@router.post(
    "/login",
    response_model=APIResponse[TokenResponse],
    status_code=status.HTTP_200_OK,
    summary="Log in with email and password",
)
def login(
    req: LoginRequest,
    db: Session = Depends(get_db),
) -> APIResponse[TokenResponse]:
    """
    Authenticate an existing citizen and receive a signed JWT access token.
    """
    user, token_response = auth_service.authenticate_user(db, req)
    return APIResponse.ok(token_response)


@router.get(
    "/me",
    response_model=APIResponse[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user identity",
)
def get_current_user_info(
    current_user: User = Depends(get_current_user),
) -> APIResponse[UserResponse]:
    """
    Returns basic identity information for the verified authenticated user.
    """
    return APIResponse.ok(UserResponse.model_validate(current_user))
