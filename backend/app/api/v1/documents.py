"""
Document API endpoints:
- Secure file upload with magic byte sniffing, MIME validation, 10MB limit.
- List citizen documents with optional family beneficiary filtering.
- Retrieve document metadata and secure streaming download.
- Delete document and remove physical storage.
- Generate scheme document checklist.
"""
from typing import Optional
import uuid
import logging
from fastapi import APIRouter, Depends, Query, File, Form, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.dependencies import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.document import (
    CitizenDocumentResponse,
    DocumentListResponse,
    DocumentChecklistResponse,
)
from app.services import document_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/upload",
    response_model=APIResponse[CitizenDocumentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload citizen document",
)
def upload_document(
    file: UploadFile = File(..., description="Document file to upload (PDF, JPEG, PNG, max 10MB)"),
    document_type: str = Form(..., description="Canonical document type (e.g. aadhaar, income_certificate)"),
    beneficiary_id: Optional[uuid.UUID] = Form(None, description="Optional family beneficiary ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[CitizenDocumentResponse]:
    """
    Upload and securely store a citizen document for the account holder or a family beneficiary.
    Validates file magic bytes (not just declared MIME type), enforces a 10MB limit,
    calculates SHA-256 checksum, and stores the file in protected storage.
    """
    doc = document_service.save_uploaded_document(
        db=db,
        current_user=current_user,
        file=file,
        document_type=document_type,
        beneficiary_id=beneficiary_id,
    )
    return APIResponse(
        success=True,
        data=CitizenDocumentResponse.model_validate(doc),
        message="Document uploaded successfully.",
    )


@router.get(
    "",
    response_model=APIResponse[DocumentListResponse],
    status_code=status.HTTP_200_OK,
    summary="List citizen documents",
)
def list_documents(
    beneficiary_id: Optional[uuid.UUID] = Query(None, description="Filter by family beneficiary ID"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[DocumentListResponse]:
    """List uploaded documents belonging to the authenticated citizen."""
    docs = document_service.list_documents(
        db=db,
        current_user=current_user,
        beneficiary_id=beneficiary_id,
        document_type=document_type,
    )
    items = [CitizenDocumentResponse.model_validate(d) for d in docs]
    return APIResponse(
        success=True,
        data=DocumentListResponse(items=items, total=len(items)),
    )


@router.get(
    "/checklist/{scheme_id}",
    response_model=APIResponse[DocumentChecklistResponse],
    status_code=status.HTTP_200_OK,
    summary="Get scheme document checklist",
)
def get_document_checklist(
    scheme_id: uuid.UUID,
    beneficiary_id: Optional[uuid.UUID] = Query(None, description="Optional family beneficiary ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[DocumentChecklistResponse]:
    """
    Generate the document checklist for a scheme against uploaded citizen documents.
    Identifies uploaded vs missing requirements, matching direct types and alternatives.
    """
    checklist = document_service.get_checklist(
        db=db,
        current_user=current_user,
        scheme_id=scheme_id,
        beneficiary_id=beneficiary_id,
    )
    return APIResponse(
        success=True,
        data=checklist,
    )


@router.get(
    "/{document_id}",
    response_model=APIResponse[CitizenDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="Get document metadata",
)
def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[CitizenDocumentResponse]:
    """Retrieve metadata of a specific uploaded document with strict user ownership verification."""
    doc = document_service.get_document_by_id(db, document_id, current_user.id)
    return APIResponse(
        success=True,
        data=CitizenDocumentResponse.model_validate(doc),
    )


@router.get(
    "/{document_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Download or stream document file",
)
def download_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Securely stream or download document file with ownership validation."""
    doc = document_service.get_document_by_id(db, document_id, current_user.id)
    physical_path = document_service.get_document_physical_path(doc)

    return FileResponse(
        path=physical_path,
        media_type=doc.mime_type,
        filename=doc.file_name,
        content_disposition_type="inline",
    )


@router.delete(
    "/{document_id}",
    response_model=APIResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Delete citizen document",
)
def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[dict]:
    """Delete a document record and its underlying physical storage."""
    document_service.delete_document(db, document_id, current_user.id)
    return APIResponse(
        success=True,
        data={"deleted": True, "document_id": str(document_id)},
        message="Document deleted successfully.",
    )
