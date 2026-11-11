# Citizen Documents API Contract (v1)

## Overview

The Citizen Documents module provides secure, zero-trust document upload, integrity verification, streaming file download, and automated scheme document checklist evaluation for Indian welfare schemes.

### Security Architecture & Invariants

1. **Zero-Trust File Sniffing (Magic Bytes):** Rather than blindly trusting client-supplied `Content-Type` headers, the service inspects binary magic bytes on stream:
   - PDF: `%PDF-` (`0x25 0x50 0x44 0x46`)
   - JPEG: `\xFF\xD8\xFF`
   - PNG: `\x89PNG\r\n\x1a\n` (`0x89 0x50 0x4E 0x47 0x0D 0x0A 0x1A 0x0A`)
   Disguised text or binary payloads renamed with valid extensions are rejected immediately with HTTP 422.
2. **File Size Ceiling:** Maximum upload size is strictly capped at 10MB (10,485,760 bytes). Streams exceeding this limit are aborted immediately, returning HTTP 413 (`PayloadTooLargeError`).
3. **Cryptographic Checksum:** SHA-256 digest is calculated during chunked streaming and stored in `checksum_sha256` for integrity tracking and deduplication.
4. **Filename Sanitization:** Path traversal sequences (`..`, `/`, `\`), null bytes (`\x00`), and control characters are stripped. Files are saved in protected user-isolated storage (`<STORAGE_DIR>/<user_id>/<doc_uuid>_<safe_filename>`) with `0o700` permissions.
5. **Anti-IDOR Tenant Isolation:** All operations enforce `user_id == current_user.id`. If a document is tagged with `beneficiary_id`, family ownership is validated; referencing another citizen's family member returns HTTP 404.

---

## Endpoints

### 1. Upload Citizen Document
`POST /api/v1/documents/upload`

**Headers:** `Authorization: Bearer <jwt>`, `Content-Type: multipart/form-data`

**Form Fields:**
- `file`: Binary document file (PDF, JPEG, or PNG; max 10MB)
- `document_type`: Canonical document identifier (e.g. `aadhaar`, `pan`, `income_certificate`, `caste_certificate`, `domicile_certificate`, `ration_card`, `bank_passbook`, `land_record`, `disability_certificate`, `other`)
- `beneficiary_id`: (Optional) UUID of target family beneficiary; null for account holder self

**Response (`201 Created`):**
```json
{
  "success": true,
  "data": {
    "id": "e4b3c2d1-7a8b-4c9d-8e1f-2a3b4c5d6e7f",
    "user_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
    "beneficiary_id": null,
    "document_type": "aadhaar",
    "file_name": "aadhaar.pdf",
    "file_size_bytes": 204850,
    "mime_type": "application/pdf",
    "checksum_sha256": "8f4e2b1c...",
    "verification_status": "PENDING",
    "rejection_reason": null,
    "extracted_metadata": {},
    "created_at": "2026-11-11T10:00:00Z",
    "updated_at": "2026-11-11T10:00:00Z"
  },
  "message": "Document uploaded successfully."
}
```

---

### 2. List Citizen Documents
`GET /api/v1/documents`

**Headers:** `Authorization: Bearer <jwt>`

**Query Parameters:**
- `beneficiary_id`: (Optional) Filter by family beneficiary UUID
- `document_type`: (Optional) Filter by canonical document type

**Response (`200 OK`):**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "e4b3c2d1-7a8b-4c9d-8e1f-2a3b4c5d6e7f",
        "user_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
        "beneficiary_id": null,
        "document_type": "aadhaar",
        "file_name": "aadhaar.pdf",
        "file_size_bytes": 204850,
        "mime_type": "application/pdf",
        "checksum_sha256": "8f4e2b1c...",
        "verification_status": "PENDING",
        "rejection_reason": null,
        "extracted_metadata": {},
        "created_at": "2026-11-11T10:00:00Z",
        "updated_at": "2026-11-11T10:00:00Z"
      }
    ],
    "total": 1
  }
}
```

---

### 3. Get Document Checklist for Scheme
`GET /api/v1/documents/checklist/{scheme_id}`

**Headers:** `Authorization: Bearer <jwt>`

**Query Parameters:**
- `beneficiary_id`: (Optional) UUID of family beneficiary; null for account holder self

**Response (`200 OK`):**
```json
{
  "success": true,
  "data": {
    "scheme_id": "b3c2d1e0-6a7b-4c8d-9e0f-1a2b3c4d5e6f",
    "scheme_code": "PM-KISAN",
    "scheme_name": "PM Kisan Samman Nidhi",
    "beneficiary_id": null,
    "target_name": "Ramesh Kumar",
    "total_mandatory": 2,
    "uploaded_mandatory": 1,
    "is_complete": false,
    "completion_percentage": 50.0,
    "mandatory_documents": [
      {
        "document_type": "aadhaar",
        "title": "Aadhaar Card",
        "description": "Unique Identification Document",
        "is_mandatory": true,
        "status": "UPLOADED",
        "guidance": "Download e-Aadhaar from uidai.gov.in",
        "issuing_authority": "UIDAI",
        "alternatives": null,
        "attached_document_id": "e4b3c2d1-7a8b-4c9d-8e1f-2a3b4c5d6e7f",
        "attached_file_name": "aadhaar.pdf",
        "attached_verification_status": "PENDING"
      },
      {
        "document_type": "land_records",
        "title": "Land Ownership Record (Khata/Khasra/ROR)",
        "description": "Proof of cultivable agricultural land",
        "is_mandatory": true,
        "status": "MISSING",
        "guidance": "Obtain certified copy from state revenue portal or CSC Kendra",
        "issuing_authority": "State Revenue Department",
        "alternatives": ["jamabandi", "patta", "khasra_extract"],
        "attached_document_id": null,
        "attached_file_name": null,
        "attached_verification_status": null
      }
    ],
    "optional_documents": []
  }
}
```

---

### 4. Get Document Metadata
`GET /api/v1/documents/{document_id}`

**Headers:** `Authorization: Bearer <jwt>`

**Response (`200 OK`):** Returns `CitizenDocumentResponse`.

---

### 5. Download Document File
`GET /api/v1/documents/{document_id}/download`

**Headers:** `Authorization: Bearer <jwt>`

**Response (`200 OK`):** Binary stream with `Content-Type: application/pdf` (or `image/jpeg`, `image/png`) and `Content-Disposition: inline`.

---

### 6. Delete Document
`DELETE /api/v1/documents/{document_id}`

**Headers:** `Authorization: Bearer <jwt>`

**Response (`200 OK`):**
```json
{
  "success": true,
  "data": {
    "deleted": true,
    "document_id": "e4b3c2d1-7a8b-4c9d-8e1f-2a3b4c5d6e7f"
  },
  "message": "Document deleted successfully."
}
```
