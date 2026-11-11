"""
Beneficiary Management API Endpoints.
Supports retrieving, creating, updating, and deleting family beneficiaries,
as well as listing the account holder (self) alongside all family beneficiaries.
"""
from typing import List, Dict, Any
import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.dependencies import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.beneficiary import (
    BeneficiaryCreate,
    BeneficiaryUpdate,
    BeneficiaryResponse,
)
from app.services import beneficiary_service

router = APIRouter()


@router.get(
    "",
    response_model=APIResponse[List[BeneficiaryResponse]],
    status_code=status.HTTP_200_OK,
    summary="List all beneficiaries (self and family members)",
)
def list_beneficiaries(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[List[BeneficiaryResponse]]:
    """
    List all beneficiaries for the authenticated account holder.
    Returns the primary account holder ('self') first, followed by all family beneficiaries.
    """
    beneficiaries = beneficiary_service.list_beneficiaries(db, current_user)
    return APIResponse.ok(beneficiaries)


@router.post(
    "",
    response_model=APIResponse[BeneficiaryResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a family beneficiary",
)
def create_beneficiary(
    payload: BeneficiaryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[BeneficiaryResponse]:
    """
    Register an additional family beneficiary (father, mother, spouse, child, etc.)
    under the authenticated user account.
    """
    beneficiary = beneficiary_service.create_beneficiary(db, current_user, payload)
    return APIResponse.ok(beneficiary)


@router.get(
    "/{beneficiary_id}",
    response_model=APIResponse[BeneficiaryResponse],
    status_code=status.HTTP_200_OK,
    summary="Retrieve a beneficiary by UUID",
)
def get_beneficiary(
    beneficiary_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[BeneficiaryResponse]:
    """
    Retrieve a specific beneficiary (self or family member) by UUID.
    Enforces strict IDOR protection: returns 404 if not found or unauthorized.
    """
    beneficiary = beneficiary_service.get_beneficiary(db, current_user, beneficiary_id)
    return APIResponse.ok(beneficiary)


@router.put(
    "/{beneficiary_id}",
    response_model=APIResponse[BeneficiaryResponse],
    status_code=status.HTTP_200_OK,
    summary="Update a beneficiary by UUID",
)
def update_beneficiary(
    beneficiary_id: uuid.UUID,
    payload: BeneficiaryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[BeneficiaryResponse]:
    """
    Update details for a specific beneficiary (self or family member).
    Enforces strict IDOR protection: returns 404 if not found or unauthorized.
    """
    beneficiary = beneficiary_service.update_beneficiary(db, current_user, beneficiary_id, payload)
    return APIResponse.ok(beneficiary)


@router.delete(
    "/{beneficiary_id}",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Delete a family beneficiary by UUID",
)
def delete_beneficiary(
    beneficiary_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[Dict[str, Any]]:
    """
    Delete a family beneficiary by UUID.
    Attempting to delete the primary account holder self profile is rejected with 400.
    Enforces strict IDOR protection: returns 404 if not found or unauthorized.
    """
    beneficiary_service.delete_beneficiary(db, current_user, beneficiary_id)
    return APIResponse.ok({"message": f"Beneficiary with ID '{beneficiary_id}' deleted successfully."})
