"""
FraudShield — User Management Router  (/api/v1/users/*)
Full CRUD for user accounts. Admin-only except GET /me (in auth router).
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminOnly, get_current_user, get_session
from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.auth import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["User Management"])
log = get_logger("api.users")


@router.get(
    "",
    response_model=dict,
    summary="List all users (Admin only)",
    dependencies=[AdminOnly],
)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return a paginated list of all FraudShield users."""
    repo = UserRepository(session)
    offset = (page - 1) * page_size
    users = await repo.get_all(offset=offset, limit=page_size)
    total = await repo.count()
    return {
        "items": [UserOut.model_validate(u).model_dump() for u in users],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
    }


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user (Admin only)",
    dependencies=[AdminOnly],
)
async def create_user(
    body: UserCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    """Admin creates a new user with any role."""
    repo = UserRepository(session)
    if await repo.username_exists(body.username):
        raise ConflictError(f"Username '{body.username}' is already taken.")
    if await repo.email_exists(body.email):
        raise ConflictError(f"Email '{body.email}' is already registered.")

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    created = await repo.create(user)
    log.info(f"[{current_user.username}] Created user: {body.username} role={body.role}")
    return UserOut.model_validate(created)


@router.get(
    "/{user_id}",
    response_model=UserOut,
    summary="Get a specific user by ID (Admin only)",
    dependencies=[AdminOnly],
)
async def get_user(
    user_id: str = Path(..., description="User UUID"),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    """Fetch a single user by their UUID."""
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if not user:
        raise NotFoundError(f"User '{user_id}' not found.")
    return UserOut.model_validate(user)


@router.patch(
    "/{user_id}",
    response_model=UserOut,
    summary="Update a user's email, role, or active status (Admin only)",
    dependencies=[AdminOnly],
)
async def update_user(
    user_id: str,
    body: UserUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    """Partially update a user. Only provided fields are changed."""
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if not user:
        raise NotFoundError(f"User '{user_id}' not found.")

    updates: dict = {}
    if body.email is not None:
        if await repo.email_exists(body.email) and user.email != body.email:
            raise ConflictError(f"Email '{body.email}' is already in use.")
        updates["email"] = body.email
    if body.role is not None:
        updates["role"] = body.role
    if body.is_active is not None:
        updates["is_active"] = body.is_active

    updated = await repo.update(user, **updates)
    log.info(f"[{current_user.username}] Updated user {user_id}: {updates}")
    return UserOut.model_validate(updated)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Deactivate a user (Admin only — soft delete)",
    dependencies=[AdminOnly],
)
async def deactivate_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """
    Soft-delete: sets is_active=False. The user can no longer log in.
    Hard deletion is intentionally unsupported to preserve audit trail integrity.
    """
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if not user:
        raise NotFoundError(f"User '{user_id}' not found.")
    if user.id == current_user.id:
        from app.core.exceptions import PermissionDeniedError
        raise PermissionDeniedError("You cannot deactivate your own account.")

    await repo.deactivate(user)
    log.info(f"[{current_user.username}] Deactivated user: {user_id}")
