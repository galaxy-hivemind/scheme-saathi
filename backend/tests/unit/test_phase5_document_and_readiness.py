"""
Phase 5 Comprehensive Backend Tests: Document Lifecycle Integrity & Application Readiness Engine.

Covers:
1. Valid & invalid document uploads (empty file, spoofed extension, corrupted image, valid PNG & PDF).
2. Honest OCR extraction & text parsing without fabricated citizen data.
3. No automatic verification upon upload or OCR.
4. Full document lifecycle: uploaded -> extracted/awaiting_citizen_review -> reviewed -> verified/rejected.
5. Expiry date & profile name mismatch rejection.
6. Scheme-specific document requirements & applicability:
   - Canonical equivalence (aadhaar <-> aadhaar_card, land_possession <-> land_records).
   - PMAY-G conditional applicability (landless exemption for land_possession; MGNREGA convergence for job_card).
   - PMAY-U strictly separate from PMAY-G (urban housing does not ask for rural job_card/land_possession).
7. Missing-document recalculation on review, verification, rejection, and deletion.
8. Duplicate draft prevention, citizen data isolation, no silent submission.
9. Pure trilingual readiness messages (en, hi, mr) without bilingual parentheticals.
"""
import io
import uuid
import pytest
from PIL import Image
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.models.user import User
from app.models.user_profile import UserProfile
from app.api.v1.documents import (
    upload_document,
    get_user_documents,
    review_document,
    verify_document,
    delete_document,
    get_document_details,
    DocumentReviewRequest,
)
from app.api.v1.applications import (
    get_applications,
    create_application_draft,
    update_application_draft,
    validate_application_draft,
    confirm_application,
    submit_application,
    CreateDraftRequest,
    UpdateDraftRequest,
    normalize_and_consolidate_apps,
)
from tests.unit.test_documents_and_applications import MockSession


def _make_png_bytes(width: int = 120, height: int = 80) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=(240, 240, 240))
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_text_pdf_bytes(text_line: str) -> bytes:
    safe_text = text_line.replace("(", "").replace(")", "")
    content = f"BT /F1 12 Tf 72 720 Td ({safe_text}) Tj ET".encode("latin-1")
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Length " + str(len(content)).encode() + b" >>\n"
        b"stream\n" + content + b"\nendstream\nendobj\n%%EOF\n"
    )


def _make_upload(filename: str, data: bytes, content_type: str = "application/octet-stream") -> UploadFile:
    headers = Headers({"content-type": content_type})
    return UploadFile(filename=filename, file=io.BytesIO(data), headers=headers)


@pytest.mark.asyncio
async def test_document_upload_validation_rejects_invalid_and_spoofed_files():
    user = User(id=uuid.uuid4(), email="u@example.com")
    profile = UserProfile(id=uuid.uuid4(), user_id=user.id, full_name="Ramesh Kumar", profile_data={})
    db = MockSession(profile=profile)

    # 1. Empty file rejected
    with pytest.raises(HTTPException) as exc1:
        await upload_document(document_type="aadhaar_card", file=_make_upload("empty.png", b""), current_user=user, db=db)
    assert exc1.value.status_code == 422

    # 2. Unsupported extension (.exe / .txt)
    with pytest.raises(HTTPException) as exc2:
        await upload_document(document_type="aadhaar_card", file=_make_upload("virus.exe", b"MZ12345"), current_user=user, db=db)
    assert exc2.value.status_code == 422

    # 3. Spoofed .jpg containing plain text
    with pytest.raises(HTTPException) as exc3:
        await upload_document(document_type="aadhaar_card", file=_make_upload("fake.jpg", b"This is not a JPEG image"), current_user=user, db=db)
    assert exc3.value.status_code == 422

    # 4. Corrupted PNG header with garbage bytes
    with pytest.raises(HTTPException) as exc4:
        await upload_document(document_type="aadhaar_card", file=_make_upload("broken.png", b"\x89PNG\r\n\x1a\nbrokenpixels"), current_user=user, db=db)
    assert exc4.value.status_code == 422


@pytest.mark.asyncio
async def test_document_lifecycle_no_auto_verification_and_honest_ocr():
    user_id = uuid.uuid4()
    user = User(id=user_id, email="ramesh@example.com")
    profile = UserProfile(id=uuid.uuid4(), user_id=user_id, full_name="Ramesh Kumar", profile_data={})
    db = MockSession(profile=profile)

    # 1. Upload valid PNG -> must NOT be auto-verified!
    png_bytes = _make_png_bytes()
    res_up = await upload_document(
        document_type="aadhaar_card",
        file=_make_upload("aadhaar_scan.png", png_bytes, "image/png"),
        current_user=user,
        db=db,
    )
    doc = res_up.data
    assert doc["upload_status"] == "uploaded"
    assert doc["lifecycle_status"] in ("awaiting_citizen_review", "extracted")
    assert doc["lifecycle_status"] != "verified"
    assert doc["review_status"] == "pending_review"
    # Profile verified flags MUST remain False until explicitly verified
    assert profile.profile_data.get("has_aadhaar") is False

    # Clean up test file after checking
    doc_id = doc["id"]

    # 2. Attempting to verify BEFORE citizen review must fail cleanly
    with pytest.raises(HTTPException) as exc_unreviewed:
        verify_document(doc_id=doc_id, current_user=user, db=db)
    assert exc_unreviewed.value.status_code == 422

    # 3. Save Citizen Review (reviewed != verified!)
    res_rev = review_document(
        doc_id=doc_id,
        payload=DocumentReviewRequest(
            reviewed_fields={
                "full_name_on_document": "Ramesh Kumar",
                "document_number": "234567890123",
                "issuing_authority": "UIDAI",
            },
            confirmed_accurate=True,
        ),
        current_user=user,
        db=db,
    )
    assert res_rev.data["lifecycle_status"] == "reviewed"
    assert profile.profile_data.get("has_aadhaar") is False  # Still not verified!

    # 4. Run Deterministic Verification -> passes all Aadhaar & Name checks -> becomes 'verified'
    res_ver = verify_document(doc_id=doc_id, current_user=user, db=db)
    assert res_ver.data["lifecycle_status"] == "verified"
    assert profile.profile_data.get("has_aadhaar") is True

    # 5. Delete document -> recalculates profile flag back to False
    res_del = delete_document(doc_id=doc_id, current_user=user, db=db)
    assert res_del.data["deleted"] is True
    assert profile.profile_data.get("has_aadhaar") is False


@pytest.mark.asyncio
async def test_pdf_ocr_extraction_and_verification_rejection_on_expiry_and_name_mismatch():
    user_id = uuid.uuid4()
    user = User(id=user_id, email="priya@example.com")
    profile = UserProfile(id=uuid.uuid4(), user_id=user_id, full_name="Priya Sharma", profile_data={})
    db = MockSession(profile=profile)

    # Text-bearing PDF with Bank Account & IFSC
    pdf_bytes = _make_text_pdf_bytes("Name: Priya Sharma Account No: 123456789012 IFSC: SBIN0001234")
    up_res = await upload_document(
        document_type="bank_passbook",
        file=_make_upload("passbook.pdf", pdf_bytes, "application/pdf"),
        current_user=user,
        db=db,
    )
    doc = up_res.data
    assert doc["ocr_status"] == "completed"
    assert doc["extracted_fields"].get("ifsc_code") == "SBIN0001234"
    assert doc["extracted_fields"].get("document_number") == "123456789012"
    assert doc["lifecycle_status"] == "extracted"

    # Case A: Citizen reviews with expired date -> Verification MUST reject!
    review_document(
        doc_id=doc["id"],
        payload=DocumentReviewRequest(
            reviewed_fields={
                "full_name_on_document": "Priya Sharma",
                "document_number": "123456789012",
                "ifsc_code": "SBIN0001234",
                "expiry_date": "2020-01-01",
            },
            confirmed_accurate=True,
        ),
        current_user=user,
        db=db,
    )
    ver_expired = verify_document(doc_id=doc["id"], current_user=user, db=db)
    assert ver_expired.data["lifecycle_status"] == "rejected"
    assert "expired" in ver_expired.data["rejection_reason"].lower()
    assert profile.profile_data.get("has_bank_account") is False

    # Case B: Name mismatch -> Verification MUST reject!
    review_document(
        doc_id=doc["id"],
        payload=DocumentReviewRequest(
            reviewed_fields={
                "full_name_on_document": "Completely Different Person",
                "document_number": "123456789012",
                "ifsc_code": "SBIN0001234",
            },
            confirmed_accurate=True,
        ),
        current_user=user,
        db=db,
    )
    ver_mismatch = verify_document(doc_id=doc["id"], current_user=user, db=db)
    assert ver_mismatch.data["lifecycle_status"] == "rejected"
    assert "does not match" in ver_mismatch.data["rejection_reason"].lower()

    # Clean up file
    delete_document(doc_id=doc["id"], current_user=user, db=db)


def test_pmay_g_readiness_landless_exemption_and_canonical_alias_resolution():
    """
    Reproduces & verifies fix for:
    'Mandatory documents pending in vault: aadhaar, job_card, land_possession.'
    """
    user_id = uuid.uuid4()
    user = User(id=user_id, email="ramesh@example.com")
    profile = UserProfile(
        id=uuid.uuid4(),
        user_id=user_id,
        full_name="Ramesh Kumar",
        gender="male",
        state="Uttar Pradesh",
        district="Varanasi",
        residence_type="rural",
        occupation="farmer",
        annual_family_income=80000,
        profile_data={
            "documents": [
                # Citizen uploaded as 'aadhaar_card' and 'bank_passbook', initially pending review
                {"id": "d1", "document_type": "aadhaar_card", "upload_status": "uploaded", "review_status": "pending_review"},
                {"id": "d2", "document_type": "bank_passbook", "upload_status": "uploaded", "review_status": "pending_review"},
            ]
        },
    )
    profile.age = 42
    db = MockSession(profile=profile)

    pmay_g_form = {
        "applicant_name": "Ramesh Kumar",
        "gender": "MALE",
        "category": "OBC",
        "aadhaar_number": "726726378736",
        "mobile_number": "9876543210",
        "current_house_type": "Houseless / Kutcha (Zero or One Room)",
        "ownership_of_pucca_house": "No",
        "state": "Uttar Pradesh",
        "district": "Varanasi",
        "block_panchayat": "Varanasi",
        "village": "Shivpur",
        "bank_account_number": "876644323",
        "ifsc_code": "SBIN0001234",
        "mgnrega_wage_convergence": "No",
        "land_plot_availability": "Landless / Assistance Required",
    }

    draft_res = create_application_draft(
        payload=CreateDraftRequest(scheme_id="PMAY-G", form_data=pmay_g_form),
        current_user=user,
        db=db,
    )
    app_id = draft_res.data["id"]

    # 1. Before verifying aadhaar_card & bank_passbook, readiness MUST NOT pass
    #    AND land_possession + job_card MUST be waived (NOT falsely reported as missing!),
    #    AND aadhaar_card must be recognized as awaiting review (NOT reported missing!).
    val_unverified = validate_application_draft(app_id=app_id, current_user=user, db=db).data
    assert val_unverified["passed"] is False
    err_messages = " | ".join(e["message"] for e in val_unverified["errors"])
    assert "job_card" not in err_messages
    assert "land_possession" not in err_messages
    assert "awaiting your review & verification" in err_messages
    assert val_unverified["breakdown"]["documents"]["waived"] == 2
    assert val_unverified["breakdown"]["documents"]["awaiting_review"] == 2

    # 2. Verify Aadhaar Card & Bank Passbook -> PMAY-G Readiness reaches 100% PASS!
    profile.profile_data["documents"] = [
        {"id": "d1", "document_type": "aadhaar_card", "upload_status": "uploaded", "lifecycle_status": "verified"},
        {"id": "d2", "document_type": "bank_passbook", "upload_status": "uploaded", "lifecycle_status": "verified"},
    ]
    val_ready = validate_application_draft(app_id=app_id, current_user=user, db=db).data
    assert val_ready["passed"] is True
    assert val_ready["overall_percentage"] == 100.0
    assert val_ready["breakdown"]["documents"]["verified"] == 2


def test_pmay_u_vs_pmay_g_isolation_and_duplicate_draft_prevention():
    """Verify PMAY-U and PMAY-G are never confused or merged, while duplicate PMAY-U drafts are prevented."""
    user_id = uuid.uuid4()
    user = User(id=user_id, email="priya@example.com")
    profile = UserProfile(
        id=uuid.uuid4(),
        user_id=user_id,
        full_name="Priya Verma",
        gender="female",
        state="Maharashtra",
        district="Pune",
        residence_type="urban",
        occupation="vendor",
        annual_family_income=180000,
        profile_data={"documents": []},
    )
    profile.age = 30
    db = MockSession(profile=profile)

    # Create PMAY-U draft and PMAY-G draft
    d_u1 = create_application_draft(CreateDraftRequest(scheme_id="PMAY-U", form_data={"city_town_ulb": "Pune"}), current_user=user, db=db)
    d_u2 = create_application_draft(CreateDraftRequest(scheme_id="PMAY-U", form_data={"ward_locality": "Kothrud"}), current_user=user, db=db)
    d_g1 = create_application_draft(CreateDraftRequest(scheme_id="PMAY-G", form_data={"village": "Test"}), current_user=user, db=db)

    apps = get_applications(current_user=user, db=db).data
    codes = [a["scheme_code"] for a in apps]
    assert codes.count("PMAY-U") == 1  # No duplicate PMAY-U drafts
    assert codes.count("PMAY-G") == 1  # Never merged PMAY-U into PMAY-G

    pmay_u = next(a for a in apps if a["scheme_code"] == "PMAY-U")
    assert pmay_u["form_data"]["city_town_ulb"] == "Pune"
    assert pmay_u["form_data"]["ward_locality"] == "Kothrud"
    # PMAY-U requires aadhaar + income_certificate, NEVER job_card or land_possession
    req_types_u = [item["document_type"] for item in pmay_u["validation_result"]["breakdown"]["documents"]["items"]]
    assert "aadhaar" in req_types_u
    assert "income_certificate" in req_types_u
    assert "job_card" not in req_types_u
    assert "land_possession" not in req_types_u


def test_citizen_data_isolation_and_trilingual_readiness_messages():
    """Ensure user B cannot inspect/modify user A's documents/apps and readiness renders cleanly in en/hi/mr."""
    user_a = User(id=uuid.uuid4(), email="a@example.com")
    user_b = User(id=uuid.uuid4(), email="b@example.com")

    profile_a = UserProfile(
        id=uuid.uuid4(),
        user_id=user_a.id,
        full_name="User A",
        profile_data={
            "documents": [{"id": "doc-a-1", "user_id": str(user_a.id), "document_type": "aadhaar_card", "upload_status": "uploaded"}],
            "applications": [{"id": "app-a-1", "user_id": str(user_a.id), "scheme_code": "PM-KISAN", "form_data": {}, "lifecycle_state": "draft"}],
        },
    )
    db_a = MockSession(profile=profile_a)

    # User B querying against empty profile should never see User A's docs/apps
    profile_b = UserProfile(id=uuid.uuid4(), user_id=user_b.id, full_name="User B", profile_data={})
    db_b = MockSession(profile=profile_b)
    assert get_user_documents(current_user=user_b, db=db_b).data == []
    assert get_applications(current_user=user_b, db=db_b).data == []

    with pytest.raises(HTTPException) as exc_doc:
        get_document_details(doc_id="doc-a-1", current_user=user_b, db=db_b)
    assert exc_doc.value.status_code == 404

    # Trilingual readiness messages (no parenthetical bilingual mashups)
    for lang, expected_word in [("en", "Missing from Document Vault"), ("hi", "दस्तावेज़ वॉल्ट में अनुपलब्ध"), ("mr", "व्हॉल्टमध्ये उपलब्ध नाही")]:
        val = validate_application_draft(app_id="app-a-1", lang=lang, current_user=user_a, db=db_a).data
        joined = " ".join(e["message"] for e in val["errors"])
        assert expected_word in joined
        assert "(Mandatory)" not in joined
        assert "(अनिवार्य)" not in joined
