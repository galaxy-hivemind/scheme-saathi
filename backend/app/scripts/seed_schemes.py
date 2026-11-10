"""
Authoritative Seed Data Importer for Government Schemes.

Provides:
- In-memory schema and duplicate pre-validation (zero DB connection on error).
- Read-only `--dry-run` with before/after diffs and zero DML execution.
- Fail-closed verified-field override protection via `--allow-override-verified`.
- Append-only rule versioning with controlled supersession.
- Document reconciliation with soft-deactivation.
- Single atomic transaction with automatic rollback on error.
"""
from typing import List, Dict, Any, Optional, Tuple
import argparse
import json
import logging
import os
from pathlib import Path
import sys
from datetime import date, datetime, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.scheme import Scheme
from app.models.scheme_rule_version import SchemeRuleVersion
from app.models.scheme_document import SchemeDocument
from app.schemas.scheme import (
    SchemeSeedSchema,
    SchemeStatus,
    MaterialClaim,
    VerificationStatus,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_schemes")

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "schemes"

PROTECTED_FIELDS = [
    "name",
    "short_title",
    "description",
    "ministry",
    "department",
    "category",
    "geographic_scope",
    "target_beneficiaries",
    "benefits",
    "official_url",
    "application_url",
    "source_url",
    "source_evidence",
    "scheme_status",
]


def load_and_prevalidate_seed_files(data_dir: Path) -> List[SchemeSeedSchema]:
    """
    Load and validate all JSON files in data_dir in memory.
    Fails immediately if any file is malformed, invalid, or has duplicate scheme codes.
    Zero database connections are opened during this phase.
    """
    if not data_dir.exists() or not data_dir.is_dir():
        raise FileNotFoundError(f"Data directory '{data_dir}' does not exist or is not a directory.")

    json_files = sorted(list(data_dir.glob("*.json")))
    if not json_files:
        raise ValueError(f"No JSON seed files found in '{data_dir}'.")

    validated_seeds: List[SchemeSeedSchema] = []
    seen_codes: Dict[str, Path] = {}

    for file_path in json_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except Exception as e:
            raise ValueError(f"Failed to read/parse JSON from {file_path.name}: {e}")

        try:
            seed = SchemeSeedSchema.model_validate(raw_data)
        except Exception as e:
            raise ValueError(f"Schema validation failed for {file_path.name}: {e}")

        if seed.scheme_code in seen_codes:
            prior_file = seen_codes[seed.scheme_code]
            raise ValueError(
                f"Duplicate scheme_code '{seed.scheme_code}' found in {file_path.name} "
                f"(already defined in {prior_file.name})."
            )

        seen_codes[seed.scheme_code] = file_path
        validated_seeds.append(seed)

    return validated_seeds


def compute_scheme_diff(existing: Scheme, incoming: SchemeSeedSchema) -> Dict[str, Tuple[Any, Any]]:
    """Compare fields of existing DB scheme with incoming seed schema."""
    diff = {}
    for field in PROTECTED_FIELDS:
        old_val = getattr(existing, field)
        new_val = getattr(incoming, field)

        # Normalize URLs and Enums for comparison
        if hasattr(new_val, "value"):
            new_val = new_val.value
        elif str(type(new_val)).find("HttpUrl") != -1 or hasattr(new_val, "unicode_string"):
            new_val = str(new_val) if new_val is not None else None

        if field == "source_evidence":
            # Compare serialized evidence lists
            new_evidence_dict = [e.model_dump(mode="json") for e in incoming.source_evidence]
            if old_val != new_evidence_dict:
                diff[field] = (old_val, new_evidence_dict)
        elif old_val != new_val:
            diff[field] = (old_val, new_val)

    return diff


def execute_seed_import(
    data_dir: Path,
    dry_run: bool = False,
    allow_override_verified: bool = False,
    session: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Executes the seed import or dry run.
    """
    # 1. Prevalidation Phase (Zero DB touch)
    seeds = load_and_prevalidate_seed_files(data_dir)
    logger.info(f"Pre-validation passed for {len(seeds)} scheme seed files.")

    close_session_at_end = False
    if session is None:
        session = SessionLocal()
        close_session_at_end = True

    summary = {
        "added": 0,
        "updated": 0,
        "skipped": 0,
        "demoted_to_pending": 0,
        "rule_versions_added": 0,
        "documents_added": 0,
        "documents_updated": 0,
        "documents_deactivated": 0,
        "diffs": {},
    }

    try:
        if dry_run:
            logger.info("Executing DRY-RUN: Evaluating plan and diffs (0 DML statements).")
            # In dry-run, we only SELECT
            for seed in seeds:
                existing = session.scalar(select(Scheme).where(Scheme.scheme_code == seed.scheme_code))
                if existing is None:
                    summary["added"] += 1
                    summary["diffs"][seed.scheme_code] = {"action": "INSERT", "fields": "all"}
                    if seed.eligibility_criteria:
                        summary["rule_versions_added"] += 1
                    summary["documents_added"] += len(seed.required_documents)
                else:
                    is_verified = (existing.scheme_status == "active") or (existing.last_verified_at is not None)
                    diff = compute_scheme_diff(existing, seed)
                    if not diff:
                        summary["diffs"][seed.scheme_code] = {"action": "NOOP (Idempotent)"}
                    elif is_verified and not allow_override_verified:
                        summary["skipped"] += 1
                        summary["diffs"][seed.scheme_code] = {
                            "action": "SKIP (Verified without --allow-override-verified)",
                            "conflicts": {k: {"db": v[0], "seed": v[1]} for k, v in diff.items()},
                        }
                    else:
                        summary["updated"] += 1
                        summary["diffs"][seed.scheme_code] = {
                            "action": "UPDATE",
                            "changes": {k: {"old": v[0], "new": v[1]} for k, v in diff.items()},
                        }

            logger.info("Dry-run plan computation completed successfully.")
            return summary

        # 2. Normal Import Phase: Open single atomic transaction
        with session.begin():
            for seed in seeds:
                existing = session.scalar(select(Scheme).where(Scheme.scheme_code == seed.scheme_code))

                if existing is None:
                    # New Scheme
                    new_scheme = Scheme(
                        scheme_code=seed.scheme_code,
                        name=seed.name,
                        short_title=seed.short_title,
                        description=seed.description,
                        ministry=seed.ministry,
                        department=seed.department,
                        category=seed.category.value,
                        geographic_scope=seed.geographic_scope,
                        target_beneficiaries=seed.target_beneficiaries,
                        benefits=seed.benefits,
                        official_url=str(seed.official_url) if seed.official_url else None,
                        application_url=str(seed.application_url) if seed.application_url else None,
                        source_url=str(seed.source_url),
                        source_evidence=[e.model_dump(mode="json") for e in seed.source_evidence],
                        scheme_status=seed.scheme_status.value,
                        last_retrieved_at=seed.last_retrieved_at,
                        last_verified_at=seed.last_verified_at,
                    )
                    session.add(new_scheme)
                    session.flush()  # Obtain new_scheme.id
                    summary["added"] += 1

                    # Add Rule Version if criteria present
                    if seed.eligibility_criteria:
                        rule_v = SchemeRuleVersion(
                            scheme_id=new_scheme.id,
                            version=1,
                            is_active=True,
                            effective_from=date.today(),
                            eligibility_criteria=seed.eligibility_criteria,
                            change_summary="Initial seed version",
                            source_url=str(seed.source_url),
                        )
                        session.add(rule_v)
                        summary["rule_versions_added"] += 1

                    # Add Documents
                    for doc in seed.required_documents:
                        s_doc = SchemeDocument(
                            scheme_id=new_scheme.id,
                            document_type=doc.document_type,
                            title=doc.title,
                            description=doc.description,
                            is_mandatory=doc.is_mandatory,
                            is_active=True,
                            alternatives=doc.alternatives,
                            issuing_authority=doc.issuing_authority,
                            guidance=doc.guidance,
                            source_url=str(doc.source_url) if doc.source_url else None,
                            last_verified_at=doc.last_verified_at,
                        )
                        session.add(s_doc)
                        summary["documents_added"] += 1

                else:
                    # Existing Scheme
                    is_verified = (existing.scheme_status == "active") or (existing.last_verified_at is not None)
                    diff = compute_scheme_diff(existing, seed)

                    if not diff:
                        logger.info(f"Scheme '{seed.scheme_code}' is identical to DB; skipping metadata update.")
                    elif is_verified and not allow_override_verified:
                        # Skip entire aggregate on conflict without explicit override
                        summary["skipped"] += 1
                        logger.warning(
                            f"Skipping verified scheme '{seed.scheme_code}' due to conflicts. "
                            f"Pass --allow-override-verified to override. Conflicts: {list(diff.keys())}"
                        )
                        continue
                    else:
                        # Apply updates
                        summary["updated"] += 1

                        # Determine if fresh verified evidence is present for all material claims
                        has_fresh_verified = (seed.scheme_status == SchemeStatus.ACTIVE) and all(
                            e.verification_status == VerificationStatus.VERIFIED for e in seed.source_evidence
                        )

                        existing.name = seed.name
                        existing.short_title = seed.short_title
                        existing.description = seed.description
                        existing.ministry = seed.ministry
                        existing.department = seed.department
                        existing.category = seed.category.value
                        existing.geographic_scope = seed.geographic_scope
                        existing.target_beneficiaries = seed.target_beneficiaries
                        existing.benefits = seed.benefits
                        existing.official_url = str(seed.official_url) if seed.official_url else None
                        existing.application_url = str(seed.application_url) if seed.application_url else None
                        existing.source_url = str(seed.source_url)
                        existing.source_evidence = [e.model_dump(mode="json") for e in seed.source_evidence]
                        existing.last_retrieved_at = seed.last_retrieved_at

                        if has_fresh_verified:
                            existing.scheme_status = SchemeStatus.ACTIVE.value
                            existing.last_verified_at = seed.last_verified_at
                        else:
                            existing.scheme_status = SchemeStatus.PENDING_VERIFICATION.value
                            existing.last_verified_at = None
                            summary["demoted_to_pending"] += 1
                            logger.info(
                                f"Scheme '{seed.scheme_code}' updated with incomplete/unverified evidence; "
                                f"set to pending_verification and last_verified_at cleared."
                            )

                    # Reconcile Rule Versions
                    active_rule = session.scalar(
                        select(SchemeRuleVersion).where(
                            and_(
                                SchemeRuleVersion.scheme_id == existing.id,
                                SchemeRuleVersion.is_active.is_(True),
                            )
                        )
                    )

                    if seed.eligibility_criteria is not None:
                        if active_rule is None:
                            # Create initial rule version
                            new_v = SchemeRuleVersion(
                                scheme_id=existing.id,
                                version=1,
                                is_active=True,
                                effective_from=date.today(),
                                eligibility_criteria=seed.eligibility_criteria,
                                change_summary="Initial rule version",
                                source_url=str(seed.source_url),
                            )
                            session.add(new_v)
                            summary["rule_versions_added"] += 1
                        elif active_rule.eligibility_criteria != seed.eligibility_criteria:
                            # Supersede active rule version
                            active_rule.is_active = False
                            active_rule.effective_to = date.today()

                            max_v = session.scalar(
                                select(func.max(SchemeRuleVersion.version)).where(
                                    SchemeRuleVersion.scheme_id == existing.id
                                )
                            ) or 1

                            new_v = SchemeRuleVersion(
                                scheme_id=existing.id,
                                version=max_v + 1,
                                is_active=True,
                                effective_from=date.today(),
                                eligibility_criteria=seed.eligibility_criteria,
                                change_summary="Updated rule version from seed import",
                                source_url=str(seed.source_url),
                            )
                            session.add(new_v)
                            summary["rule_versions_added"] += 1

                    # Reconcile Documents
                    existing_docs = {
                        d.document_type: d
                        for d in session.scalars(
                            select(SchemeDocument).where(SchemeDocument.scheme_id == existing.id)
                        ).all()
                    }
                    seed_doc_types = set()

                    for doc in seed.required_documents:
                        seed_doc_types.add(doc.document_type)
                        if doc.document_type in existing_docs:
                            ed = existing_docs[doc.document_type]
                            ed.title = doc.title
                            ed.description = doc.description
                            ed.is_mandatory = doc.is_mandatory
                            ed.is_active = True
                            ed.alternatives = doc.alternatives
                            ed.issuing_authority = doc.issuing_authority
                            ed.guidance = doc.guidance
                            ed.source_url = str(doc.source_url) if doc.source_url else None
                            ed.last_verified_at = doc.last_verified_at
                            summary["documents_updated"] += 1
                        else:
                            nd = SchemeDocument(
                                scheme_id=existing.id,
                                document_type=doc.document_type,
                                title=doc.title,
                                description=doc.description,
                                is_mandatory=doc.is_mandatory,
                                is_active=True,
                                alternatives=doc.alternatives,
                                issuing_authority=doc.issuing_authority,
                                guidance=doc.guidance,
                                source_url=str(doc.source_url) if doc.source_url else None,
                                last_verified_at=doc.last_verified_at,
                            )
                            session.add(nd)
                            summary["documents_added"] += 1

                    # Soft-deactivate omitted documents
                    for dtype, ed in existing_docs.items():
                        if dtype not in seed_doc_types and ed.is_active:
                            ed.is_active = False
                            summary["documents_deactivated"] += 1

        logger.info(
            f"Import complete: {summary['added']} added, {summary['updated']} updated, "
            f"{summary['skipped']} skipped, {summary['rule_versions_added']} rule versions appended."
        )
        return summary

    finally:
        if close_session_at_end:
            session.close()


def main():
    parser = argparse.ArgumentParser(description="Scheme Saathi Seed Data Importer")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing scheme JSON files (default: backend/data/schemes/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run validation and diff computation without executing any DML statements.",
    )
    parser.add_argument(
        "--allow-override-verified",
        action="store_true",
        help="Allow updating material fields on active/verified schemes.",
    )

    args = parser.parse_args()

    try:
        summary = execute_seed_import(
            data_dir=args.data_dir,
            dry_run=args.dry_run,
            allow_override_verified=args.allow_override_verified,
        )
        print(json.dumps(summary, indent=2, default=str))
        sys.exit(0)
    except Exception as e:
        logger.error(f"Seed import failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
