"""
Phase 7 Comprehensive Tests: Universal Application Review, Validation,
Version-Bound Explicit Confirmation, Safe Submission Orchestration & State Machine.
"""
import uuid
import pytest
from fastapi import HTTPException

from app.models.user import User
from app.models.user_profile import UserProfile
from app.agents.tools import tool_submit_form
from app.services.prefill_service import run_universal_prefill
from app.services.submission_service import (
    PortalReconciliationResult,
    PortalSubmissionResult,
    STATE_AWAITING_CONFIRMATION,
    STATE_CONFIRMED,
    STATE_DRAFT,
    STATE_SUBMISSION_FAILED,
    STATE_SUBMISSION_UNKNOWN,
    STATE_SUBMITTED,
    STATE_SUBMITTING,
    STATE_VALIDATED,
    clear_registered_portal_adapters,
    is_verified_government_submission,
    register_portal_adapter,
    sanitize_legacy_unverified_submission,
    validate_state_transition,
)
from app.api.v1.applications import (
    ConfirmApplicationRequest,
    CreateDraftRequest,
    SubmitApplicationRequest,
    UpdateDraftRequest,
    confirm_application,
    create_application_draft,
    get_application_review,
    get_application_status,
    get_applications,
    reconcile_submission,
    submit_application,
    update_application_draft,
    validate_application_draft,
)
from tests.unit.test_documents_and_applications import MockSession


def _build_ready_farmer():
    from decimal import Decimal
    uid = uuid.uuid4()
    user = User(id=uid, email="farmer7@example.com")
    profile = UserProfile(
        id=uuid.uuid4(),
        user_id=uid,
        full_name="Ramesh Kumar",
        age=42,
        gender="male",
        state="Uttar Pradesh",
        district="Varanasi",
        residence_type="rural",
        occupation="farmer",
        annual_family_income=Decimal("85000.00"),
        profile_data={
            "caste_category": "OBC",
            "land_holding_acres": 1.5,
            "sub_district": "Pindra",
            "village": "Shivpur",
            "phone_number": "9876543210",
            "documents": [
                {
                    "id": "doc-aadhaar",
                    "user_id": str(uid),
                    "document_type": "aadhaar_card",
                    "lifecycle_status": "verified",
                    "sha256": "aaa111",
                    "verified_at": "2026-11-11T10:00:00Z",
                    "reviewed_fields": {"holder_name": "Ramesh Kumar", "document_number": "234567890123"},
                },
                {
                    "id": "doc-bank",
                    "user_id": str(uid),
                    "document_type": "bank_passbook",
                    "lifecycle_status": "verified",
                    "sha256": "bbb222",
                    "verified_at": "2026-11-11T10:05:00Z",
                    "reviewed_fields": {"document_number": "123456789012", "ifsc_code": "SBIN0001234"},
                },
                {
                    "id": "doc-land",
                    "user_id": str(uid),
                    "document_type": "land_records",
                    "lifecycle_status": "verified",
                    "sha256": "ccc333",
                    "verified_at": "2026-11-11T10:10:00Z",
                    "reviewed_fields": {"khasra_number": "104/2"},
                },
            ],
        },
    )
    return user, profile, MockSession(profile=profile)


def test_part1_complete_review_provenance_conflicts_and_trilingual():
    """Verify full field-by-field review attributes, provenance categories, missing badges, and conflicts."""
    user, profile, db = _build_ready_farmer()
    # Conflicting Aadhaar in profile vs verified Vault document (plus missing land_ownership_type & explicit citizen village override)
    profile.profile_data["aadhaar"] = "999988887777"
    draft = create_application_draft(
        payload=CreateDraftRequest(
            scheme_id="PM-KISAN",
            form_data={"village": "Rampur"},
        ),
        current_user=user,
        db=db,
    ).data
    app_id = draft["id"]

    review = get_application_review(app_id=app_id, lang="en", current_user=user, db=db).data
    assert review["application_id"] == app_id
    assert review["version"] >= 1
    assert len(review["data_hash"]) == 64

    fields = {f["name"]: f for sec in review["sections"] for f in sec["fields"]}
    assert fields["applicant_name"]["source_category"] == "verified_document"
    assert fields["gender"]["source_category"] == "profile_derived"
    assert fields["village"]["source_category"] == "citizen_entered"
    assert fields["land_ownership_type"]["is_missing"] is True
    assert fields["land_ownership_type"]["value"] == ""
    assert fields["aadhaar_number"]["conflict"] is not None

    # Confirm cannot validate while conflict + missing field remain
    val_res = validate_application_draft(app_id=app_id, lang="mr", current_user=user, db=db).data
    assert val_res["passed"] is False
    assert any("आवश्यक" in e["message"] or "भरलेली नाही" in e["message"] or "तफावत" in e["message"] for e in val_res["errors"])


def test_part2_scheme_specific_rules_ownership_and_revalidation():
    """Verify scheme rules block domain-invalid values, isolate citizens, and revalidate pre-submit."""
    user, profile, db = _build_ready_farmer()

    # 1. Domain rule violation: AB-PMJAY 70+ Senior Citizen selected by 42-year-old
    draft_pmjay = create_application_draft(
        payload=CreateDraftRequest(
            scheme_id="AB-PMJAY",
            form_data={
                "coverage_category": "Senior Citizen (70+ Universal Cover)",
                "aadhaar_number": "234567890123",
                "existing_ayushman_card": "No",
            },
        ),
        current_user=user,
        db=db,
    ).data
    val_pmjay = validate_application_draft(app_id=draft_pmjay["id"], lang="en", current_user=user, db=db).data
    assert val_pmjay["passed"] is False
    assert any("70 years" in e["message"] for e in val_pmjay["errors"])

    # 2. Cross-citizen isolation
    other_user = User(id=uuid.uuid4(), email="intruder@example.com")
    with pytest.raises(HTTPException) as exc_404:
        get_application_review(app_id=draft_pmjay["id"], current_user=other_user, db=db)
    assert exc_404.value.status_code == 404


def test_part3_explicit_confirmation_version_binding_and_invalidation():
    """Verify confirmation binds to reviewed version/hash and automatically invalidates if data or docs change."""
    user, profile, db = _build_ready_farmer()
    draft = create_application_draft(
        payload=CreateDraftRequest(
            scheme_id="PM-KISAN",
            form_data={"land_ownership_type": "Single"},
        ),
        current_user=user,
        db=db,
    ).data
    app_id = draft["id"]

    # Validate advances cleanly: draft -> validated -> awaiting_confirmation (NEVER submitted!)
    val = validate_application_draft(app_id=app_id, current_user=user, db=db).data
    assert val["passed"] is True
    rev1 = get_application_review(app_id=app_id, current_user=user, db=db).data
    assert rev1["lifecycle_state"] == STATE_AWAITING_CONFIRMATION

    # Reject confirmation if consent_acknowledged is False
    with pytest.raises(HTTPException) as exc_consent:
        confirm_application(
            app_id=app_id,
            payload=ConfirmApplicationRequest(
                consent_acknowledged=False,
                expected_version=rev1["version"],
                expected_hash=rev1["data_hash"],
            ),
            current_user=user,
            db=db,
        )
    assert exc_consent.value.status_code == 400

    # Reject stale expected_version / expected_hash
    with pytest.raises(HTTPException) as exc_stale:
        confirm_application(
            app_id=app_id,
            payload=ConfirmApplicationRequest(
                consent_acknowledged=True,
                expected_version=rev1["version"] + 9,
            ),
            current_user=user,
            db=db,
        )
    assert exc_stale.value.status_code == 409

    # Valid explicit confirmation -> transitions to 'confirmed' and records citizen/version/hash/timestamp
    conf = confirm_application(
        app_id=app_id,
        payload=ConfirmApplicationRequest(
            consent_acknowledged=True,
            expected_version=rev1["version"],
            expected_hash=rev1["data_hash"],
        ),
        current_user=user,
        db=db,
    ).data
    assert conf["confirmed"] is True
    assert conf["citizen_id"] == str(user.id)
    assert conf["application_id"] == app_id
    assert conf["confirmed_version"] == rev1["version"]
    assert conf["confirmed_hash"] == rev1["data_hash"]
    assert conf["lifecycle_state"] == STATE_CONFIRMED

    # Modify draft after confirmation -> MUST invalidate prior confirmation!
    updated = update_application_draft(
        app_id=app_id,
        payload=UpdateDraftRequest(form_data={"land_ownership_type": "Joint"}),
        current_user=user,
        db=db,
    ).data
    assert updated["confirmed_at"] is None
    assert updated["confirmed_hash"] is None
    assert updated["confirmation_invalidated_at"] is not None
    assert updated["version"] == rev1["version"] + 1
    assert updated["lifecycle_state"] == STATE_AWAITING_CONFIRMATION

    # Attempting to submit invalidated draft without fresh confirmation MUST be rejected!
    with pytest.raises(HTTPException) as exc_unconf:
        submit_application(app_id=app_id, current_user=user, db=db)
    assert exc_unconf.value.status_code == 400

    # Re-confirm v2, then reject a Vault document BEFORE submit -> pre-submit revalidation invalidates & blocks!
    rev2 = get_application_review(app_id=app_id, current_user=user, db=db).data
    confirm_application(
        app_id=app_id,
        payload=ConfirmApplicationRequest(
            consent_acknowledged=True,
            expected_version=rev2["version"],
            expected_hash=rev2["data_hash"],
        ),
        current_user=user,
        db=db,
    )
    profile.profile_data["documents"][2]["lifecycle_status"] = "rejected"
    profile.profile_data["documents"][2]["rejection_reason"] = "Illegible scan"

    with pytest.raises(HTTPException) as exc_doc_revoked:
        submit_application(app_id=app_id, current_user=user, db=db)
    assert exc_doc_revoked.value.status_code in (400, 422)


def test_part4_manual_portal_honesty_never_simulates_success():
    """When no authorized portal integration exists, never mark 'submitted' or invent government transaction IDs."""
    clear_registered_portal_adapters()
    user, profile, db = _build_ready_farmer()
    draft = create_application_draft(
        payload=CreateDraftRequest(
            scheme_id="PM-KISAN",
            form_data={"land_ownership_type": "Single"},
        ),
        current_user=user,
        db=db,
    ).data
    app_id = draft["id"]
    confirm_application(app_id=app_id, current_user=user, db=db)

    sub = submit_application(app_id=app_id, lang="en", current_user=user, db=db).data
    assert sub["submitted"] is False
    assert sub["manual_portal_required"] is True
    assert sub["integration_supported"] is False
    assert sub["external_reference_id"] is None
    assert sub["lifecycle_state"] == STATE_CONFIRMED
    assert "pmkisan.gov.in" in sub["portal_url"]
    assert "SAATHI/" not in str(sub)

    # Chat tool_submit_form respects same non-fabrication guarantee
    chat_sub = tool_submit_form(db=db, user=user, profile=profile, scheme_code_or_name="PM-KISAN", confirmed=True)
    assert chat_sub["submitted"] is False
    assert chat_sub["manual_portal_required"] is True
    assert chat_sub["external_reference_id"] is None


def test_part4_and_part5_authorized_adapter_idempotency_retry_and_uncertainty():
    """
    Exercise authorized external portal integration paths:
    1. Timeout -> submission_failed with outcome='uncertain' & blind_retry_blocked=True
    2. Blind retry blocked (409) until reconcile_submission confirms status
    3. Reconcile 'not_received' unlocks safe retry -> verified 'submitted' with portal external_reference_id
    4. Same idempotency_key replays safely without second external call; different key blocks duplicate (409)
    """
    class MockAuthorizedPortalAdapter:
        provider_name = "NIC-PMKISAN-GW"
        is_authorized = True

        def __init__(self):
            self.calls = 0
            self.mode = "timeout"

        def submit(self, application, idempotency_key, lang="en"):
            self.calls += 1
            if self.mode == "timeout":
                raise TimeoutError("Upstream NIC gateway read timed out after sending request")
            if self.mode == "fail_retryable":
                return PortalSubmissionResult(
                    outcome="failed_retryable",
                    message="Gateway busy (503). Safe to retry.",
                )
            return PortalSubmissionResult(
                outcome="submitted",
                external_reference_id="GOV-UP-PMKISAN-2026-998811",
                portal_status="ACCEPTED",
                raw_response={"ack": "OK", "tx": "GOV-UP-PMKISAN-2026-998811"},
            )

        def check_status(self, application_id, idempotency_key, attempt_id):
            return PortalReconciliationResult(
                resolved_outcome="not_received",
                message="Gateway confirmed transaction was not recorded.",
            )

    adapter = MockAuthorizedPortalAdapter()
    register_portal_adapter("PM-KISAN", adapter)
    try:
        user, profile, db = _build_ready_farmer()
        draft = create_application_draft(
            payload=CreateDraftRequest(
                scheme_id="PM-KISAN",
                form_data={"land_ownership_type": "Single"},
            ),
            current_user=user,
            db=db,
        ).data
        app_id = draft["id"]
        confirm_application(app_id=app_id, current_user=user, db=db)

        # 1. Timeout -> 504 + distinct lifecycle_state == 'submission_unknown' + blind_retry_blocked
        with pytest.raises(HTTPException) as exc_timeout:
            submit_application(
                app_id=app_id,
                payload=SubmitApplicationRequest(idempotency_key="idem-key-1"),
                current_user=user,
                db=db,
            )
        assert exc_timeout.value.status_code == 504
        apps_after_timeout = get_applications(current_user=user, db=db).data
        app_rec = next(a for a in apps_after_timeout if a["id"] == app_id)
        assert app_rec["lifecycle_state"] == STATE_SUBMISSION_UNKNOWN
        assert app_rec["submission_outcome"] == STATE_SUBMISSION_UNKNOWN
        assert app_rec["blind_retry_blocked"] is True

        # 2. Blind retry, edit, validate, and re-confirm MUST all be blocked without reconciliation
        with pytest.raises(HTTPException) as exc_blind:
            submit_application(
                app_id=app_id,
                payload=SubmitApplicationRequest(idempotency_key="idem-key-1"),
                current_user=user,
                db=db,
            )
        assert exc_blind.value.status_code == 409
        with pytest.raises(HTTPException) as exc_edit:
            update_application_draft(
                app_id=app_id,
                payload=UpdateDraftRequest(form_data={"land_ownership_type": "Joint"}),
                current_user=user,
                db=db,
            )
        assert exc_edit.value.status_code == 409
        assert adapter.calls == 1  # External gateway was NOT called again!

        # 3. Reconcile status ('not_received') -> unlocks safe retry cleanly
        rec = reconcile_submission(app_id=app_id, current_user=user, db=db).data
        assert rec["resolved"] is True
        assert rec["retry_allowed"] is True

        # 4. Retry with explicit retryable failure first, then verified portal success
        adapter.mode = "fail_retryable"
        res_fail = submit_application(
            app_id=app_id,
            payload=SubmitApplicationRequest(idempotency_key="idem-key-2"),
            current_user=user,
            db=db,
        ).data
        assert res_fail["submitted"] is False
        assert res_fail["lifecycle_state"] == STATE_SUBMISSION_FAILED
        assert res_fail["retry_allowed"] is True

        adapter.mode = "success"
        res_ok = submit_application(
            app_id=app_id,
            payload=SubmitApplicationRequest(idempotency_key="idem-key-3"),
            current_user=user,
            db=db,
        ).data
        assert res_ok["submitted"] is True
        assert res_ok["lifecycle_state"] == STATE_SUBMITTED
        assert res_ok["external_reference_id"] == "GOV-UP-PMKISAN-2026-998811"
        assert res_ok["integration_provider"] == "NIC-PMKISAN-GW"

        # 5. Idempotent replay with same key returns stored receipt without calling adapter again
        calls_before_replay = adapter.calls
        res_replay = submit_application(
            app_id=app_id,
            payload=SubmitApplicationRequest(idempotency_key="idem-key-3"),
            current_user=user,
            db=db,
        ).data
        assert res_replay["idempotent_replay"] is True
        assert res_replay["external_reference_id"] == "GOV-UP-PMKISAN-2026-998811"
        assert adapter.calls == calls_before_replay

        # 6. Different idempotency key after submitted -> blocked with 409 Conflict!
        with pytest.raises(HTTPException) as exc_dup:
            submit_application(
                app_id=app_id,
                payload=SubmitApplicationRequest(idempotency_key="idem-key-different"),
                current_user=user,
                db=db,
            )
        assert exc_dup.value.status_code == 409
    finally:
        clear_registered_portal_adapters()


def test_part5_strict_state_machine_transitions():
    """Verify state transition validator permits exact workflow edges and rejects invalid jumps."""
    validate_state_transition(STATE_DRAFT, STATE_VALIDATED)
    validate_state_transition(STATE_VALIDATED, STATE_AWAITING_CONFIRMATION)
    validate_state_transition(STATE_AWAITING_CONFIRMATION, STATE_CONFIRMED)
    validate_state_transition(STATE_CONFIRMED, STATE_SUBMITTING)
    validate_state_transition(STATE_SUBMITTING, STATE_SUBMITTED)
    validate_state_transition(STATE_SUBMITTING, STATE_SUBMISSION_FAILED)
    validate_state_transition(STATE_SUBMITTING, STATE_SUBMISSION_UNKNOWN)
    validate_state_transition(STATE_SUBMISSION_UNKNOWN, STATE_SUBMITTED)
    validate_state_transition(STATE_SUBMISSION_UNKNOWN, STATE_CONFIRMED)
    validate_state_transition(STATE_SUBMISSION_UNKNOWN, STATE_SUBMISSION_FAILED)

    for bad_from, bad_to in [
        (STATE_DRAFT, STATE_SUBMITTED),
        (STATE_DRAFT, STATE_CONFIRMED),
        (STATE_DRAFT, STATE_SUBMISSION_UNKNOWN),
        (STATE_VALIDATED, STATE_SUBMITTED),
        (STATE_AWAITING_CONFIRMATION, STATE_SUBMITTING),
        (STATE_SUBMITTED, STATE_DRAFT),
    ]:
        with pytest.raises(HTTPException) as exc:
            validate_state_transition(bad_from, bad_to)
        assert exc.value.status_code == 409


def test_ambiguous_response_and_uncertain_exception_persist_submission_unknown():
    """
    Verify post-dispatch uncertain exceptions and ambiguous portal responses (missing
    authoritative external_reference_id or outcome='uncertain') strictly persist
    lifecycle_state == 'submission_unknown', never 'submission_failed' or 'submitted',
    and keep blind retries blocked until portal status reconciles cleanly.
    """
    class UncertainException(RuntimeError):
        outcome_uncertain = True

    class MockAmbiguousAdapter:
        provider_name = "NIC-AMBIGUOUS-GW"
        is_authorized = True

        def __init__(self):
            self.mode = "uncertain_exc"
            self.reconcile_mode = "still_uncertain"

        def submit(self, application, idempotency_key, lang="en"):
            if self.mode == "uncertain_exc":
                raise UncertainException("Socket reset after POST body flush")
            return PortalSubmissionResult(
                outcome="submitted",
                external_reference_id=None,
                message="200 OK without transaction reference",
            )

        def check_status(self, application_id, idempotency_key, attempt_id):
            if self.reconcile_mode == "still_uncertain":
                return PortalReconciliationResult(resolved_outcome="still_uncertain")
            return PortalReconciliationResult(
                resolved_outcome="submitted",
                external_reference_id="GOV-NIC-RECON-2026-5544",
            )

    adapter = MockAmbiguousAdapter()
    register_portal_adapter("PM-KISAN", adapter)
    try:
        # Case A: Exception with outcome_uncertain=True -> submission_unknown
        user, profile, db = _build_ready_farmer()
        app_id = create_application_draft(
            payload=CreateDraftRequest(scheme_id="PM-KISAN", form_data={"land_ownership_type": "Single"}),
            current_user=user,
            db=db,
        ).data["id"]
        confirm_application(app_id=app_id, current_user=user, db=db)

        with pytest.raises(HTTPException) as exc_u:
            submit_application(app_id=app_id, payload=SubmitApplicationRequest(idempotency_key="amb-1"), current_user=user, db=db)
        assert exc_u.value.status_code == 502

        apps = get_applications(current_user=user, db=db).data
        rec_a = next(a for a in apps if a["id"] == app_id)
        assert rec_a["lifecycle_state"] == STATE_SUBMISSION_UNKNOWN
        assert rec_a["blind_retry_blocked"] is True

        rec_still = reconcile_submission(app_id=app_id, current_user=user, db=db).data
        assert rec_still["resolved"] is False
        assert rec_still["lifecycle_state"] == STATE_SUBMISSION_UNKNOWN
        assert rec_still["blind_retry_blocked"] is True

        # Case B: 'submitted' response missing external_reference_id -> submission_unknown -> reconcile 'submitted'
        user2, profile2, db2 = _build_ready_farmer()
        adapter.mode = "missing_ref"
        app_id2 = create_application_draft(
            payload=CreateDraftRequest(scheme_id="PM-KISAN", form_data={"land_ownership_type": "Single"}),
            current_user=user2,
            db=db2,
        ).data["id"]
        confirm_application(app_id=app_id2, current_user=user2, db=db2)

        with pytest.raises(HTTPException) as exc_missing:
            submit_application(app_id=app_id2, payload=SubmitApplicationRequest(idempotency_key="amb-2"), current_user=user2, db=db2)
        assert exc_missing.value.status_code == 502

        apps2 = get_applications(current_user=user2, db=db2).data
        rec_b = next(a for a in apps2 if a["id"] == app_id2)
        assert rec_b["lifecycle_state"] == STATE_SUBMISSION_UNKNOWN
        assert rec_b["external_reference_id"] is None

        adapter.reconcile_mode = "submitted"
        rec_ok = reconcile_submission(app_id=app_id2, current_user=user2, db=db2).data
        assert rec_ok["resolved"] is True
        assert rec_ok["lifecycle_state"] == STATE_SUBMITTED
        assert rec_ok["external_reference_id"] == "GOV-NIC-RECON-2026-5544"
    finally:
        clear_registered_portal_adapters()


def test_legacy_synthetic_submission_quarantine_preserves_records():
    """
    Historical pre-Phase-7 portal_handoff records carrying SAATHI/READY/... references
    and fake 'submitted' states must be preserved safely without DB deletion, yet
    never surfaced as genuine government submissions or coerced to 100% passed.
    """
    user, profile, db = _build_ready_farmer()
    profile.profile_data["applications"] = [
        {
            "id": "app-draft-0f5d0232",
            "user_id": str(user.id),
            "scheme_code": "PMAY-G",
            "scheme_name": "Pradhan Mantri Awaas Yojana - Gramin",
            "lifecycle_state": "submitted",
            "submission_source": "portal_handoff",
            "reference_number": "SAATHI/READY/2026/4B9C33",
            "confirmed_at": "2026-11-11T21:00:22+00:00",
            "form_data": {"applicant_name": "Ramesh Kumar"},
            "validation_result": {"passed": True, "overall_percentage": 100.0, "errors": [], "warnings": []},
            "created_at": "2026-11-11T20:00:00+00:00",
            "updated_at": "2026-11-11T21:00:22+00:00",
        },
        {
            "id": "app-pm-kisan-e472b7",
            "user_id": str(user.id),
            "scheme_code": "PM-KISAN",
            "scheme_name": "PM-KISAN Samman Nidhi",
            "lifecycle_state": "submitted",
            "submission_source": "portal_handoff",
            "reference_number": "SAATHI/READY/2026/4359A6",
            "confirmed_at": "2026-11-11T19:27:16+00:00",
            "form_data": {"applicant_name": "Ramesh Kumar"},
            "validation_result": {
                "passed": False,
                "overall_percentage": 57.1,
                "errors": [{"field": "mandatory_fields", "message": "6 mandatory fields require input."}],
                "warnings": [],
            },
            "created_at": "2026-11-11T19:00:00+00:00",
            "updated_at": "2026-11-11T19:27:16+00:00",
        },
    ]

    listed = get_applications(current_user=user, db=db).data
    assert len(listed) == 2  # Both records preserved cleanly, never deleted!

    pmayg = next(a for a in listed if a["id"] == "app-draft-0f5d0232")
    pmkisan = next(a for a in listed if a["id"] == "app-pm-kisan-e472b7")

    for rec in (pmayg, pmkisan):
        assert rec["lifecycle_state"] != STATE_SUBMITTED
        assert rec["legacy_synthetic_submission"] is True
        assert rec["is_verified_government_submission"] is False
        assert rec["external_reference_id"] is None
        assert rec["reference_number"] is None
        assert not is_verified_government_submission(rec)

    assert pmkisan["lifecycle_state"] == STATE_DRAFT
    assert pmkisan["validation_result"]["passed"] is False
    assert pmkisan["validation_result"]["overall_percentage"] == 57.1

    st = get_application_status(app_id="app-pm-kisan-e472b7", current_user=user, db=db).data
    assert st["is_verified_government_submission"] is False
    assert st["legacy_synthetic_submission"] is True
    assert st["source_reference"] is None
    assert st["status"] != STATE_SUBMITTED
