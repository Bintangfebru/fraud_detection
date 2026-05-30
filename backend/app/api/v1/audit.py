"""
FraudShield — Audit Log Router  (/api/v1/audit)

Menyediakan GET /api/v1/audit?page=1&page_size=50
yang dipanggil frontend Audit.tsx — sebelumnya 404.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AnyRole, get_current_user, get_session
from app.core.logging import get_logger
from app.models.user import User
from app.repositories.fraud_repo import AuditLogRepository

router = APIRouter(prefix="/audit", tags=["Audit"])
log = get_logger("api.audit")

# Role rank: auditor=0, analyst=1, admin=2
_ROLE_RANK = {"auditor": 0, "analyst": 1, "admin": 2}


@router.get(
    "",
    summary="Paginated audit log",
    dependencies=[AnyRole],
)
async def get_audit_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    actor: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Returns PaginatedResponse<AuditLog> matching frontend types/api.ts.
    Auditors hanya bisa lihat entry milik sendiri.
    """
    repo = AuditLogRepository(session)

    # Auditors hanya bisa lihat entry mereka sendiri
    user_rank = _ROLE_RANK.get(str(current_user.role), 0)
    if user_rank == 0:
        # auditor — paksa filter ke username sendiri
        effective_actor = current_user.username
    else:
        # analyst / admin — bisa filter bebas atau lihat semua
        effective_actor = actor  # None = semua

    data = await repo.list_paginated(
        page=page,
        page_size=page_size,
        actor=effective_actor,
    )

    serialized_items = []
    for e in data["items"]:
        serialized_items.append({
            "id": str(e.id),
            "actor": e.actor,
            "action": e.action,
            "resource_type": e.resource_type or "",
            "resource_id": str(e.resource_id) if e.resource_id else "",
            "metadata": e.detail or {},
            "created_at": e.created_at.isoformat(),
        })

    return {
        "items": serialized_items,
        "total": data["total"],
        "page": data["page"],
        "page_size": data["page_size"],
        "pages": data["pages"],
    }