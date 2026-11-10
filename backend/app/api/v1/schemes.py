"""
Government Scheme Catalogue API endpoints.
Provides authenticated endpoints for listing/searching and retrieving details of welfare schemes.
"""
from typing import Optional
import math
import uuid
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.dependencies import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.scheme import (
    SchemeCategory,
    SchemeSummaryResponse,
    SchemeListResponse,
    SchemeDetailResponse,
    SchemeDocumentResponse,
    SourceEvidenceEntry,
)
from app.services import scheme_service

router = APIRouter()


@router.get(
    "",
    response_model=APIResponse[SchemeListResponse],
    status_code=status.HTTP_200_OK,
    summary="Search and list welfare schemes",
)
def list_schemes(
    q: Optional[str] = Query(None, max_length=100, description="Search keyword matching name, ministry, benefits, etc."),
    category: Optional[str] = Query(None, description="Filter by canonical category"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    limit: int = Query(20, ge=1, le=50, description="Items per page (max 50)"),
    include_pending: bool = Query(False, description="Whether to include pending_verification schemes"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[SchemeListResponse]:
    """
    Search and list welfare schemes with pagination and category filtering.
    Requires Phase 1 native JWT authentication.
    """
    # Validate canonical category if provided
    if category is not None:
        try:
            SchemeCategory(category)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid category '{category}'. Must be one of {[c.value for c in SchemeCategory]}.",
            )

    items, total = scheme_service.get_schemes(
        db=db,
        q=q,
        category=category,
        page=page,
        limit=limit,
        include_pending=include_pending,
    )

    total_pages = math.ceil(total / limit) if total > 0 else 0

    response_data = SchemeListResponse(
        items=[SchemeSummaryResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )
    return APIResponse.ok(response_data)


@router.get(
    "/{scheme_id}",
    response_model=APIResponse[SchemeDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="Get detailed scheme catalogue metadata and document requirements",
)
def get_scheme(
    scheme_id: uuid.UUID,
    include_pending: bool = Query(False, description="Whether to include pending_verification scheme"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[SchemeDetailResponse]:
    """
    Retrieve comprehensive scheme details, active document requirements, and claim-level source evidence.
    Internal machine-readable eligibility rule JSON is strictly excluded from response.
    Requires Phase 1 native JWT authentication.
    """
    scheme = scheme_service.get_scheme_by_id(
        db=db,
        scheme_id=scheme_id,
        include_pending=include_pending,
    )

    if scheme is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheme not found",
        )

    active_docs = scheme_service.get_active_documents_for_scheme(db, scheme.id)

    # Format source evidence entries
    evidence_entries = []
    if scheme.source_evidence:
        for entry in scheme.source_evidence:
            try:
                evidence_entries.append(SourceEvidenceEntry.model_validate(entry))
            except Exception:
                pass

    detail_data = SchemeDetailResponse(
        id=scheme.id,
        scheme_code=scheme.scheme_code,
        name=scheme.name,
        short_title=scheme.short_title,
        description=scheme.description,
        ministry=scheme.ministry,
        department=scheme.department,
        category=scheme.category,
        geographic_scope=scheme.geographic_scope,
        target_beneficiaries=scheme.target_beneficiaries,
        benefits=scheme.benefits,
        official_url=scheme.official_url,
        application_url=scheme.application_url,
        source_url=scheme.source_url,
        scheme_status=scheme.scheme_status,
        last_retrieved_at=scheme.last_retrieved_at,
        last_verified_at=scheme.last_verified_at,
        source_evidence=evidence_entries,
        required_documents=[SchemeDocumentResponse.model_validate(doc) for doc in active_docs],
    )

    return APIResponse.ok(detail_data)
