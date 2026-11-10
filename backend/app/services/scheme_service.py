"""
Service layer for Government Schemes catalogue search and retrieval.
"""
from typing import Optional, List, Tuple
import uuid

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.models.scheme import Scheme
from app.models.scheme_document import SchemeDocument


def get_schemes(
    db: Session,
    q: Optional[str] = None,
    category: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    include_pending: bool = False,
) -> Tuple[List[Scheme], int]:
    """
    Retrieve paginated schemes with optional category filtering and full-text search.
    - Excludes inactive schemes unconditionally.
    - Excludes pending_verification schemes unless include_pending=True.
    - PostgreSQL FTS filtering is applied only when plainto_tsquery produces searchable lexemes.
    - Results are stably ordered by (Scheme.name ASC, Scheme.id ASC).
    """
    page = max(1, page)
    limit = max(1, min(50, limit))
    offset = (page - 1) * limit

    base_filter = [Scheme.scheme_status != "inactive"]

    if not include_pending:
        base_filter.append(Scheme.scheme_status == "active")
    else:
        base_filter.append(Scheme.scheme_status.in_(["active", "pending_verification"]))

    if category:
        base_filter.append(Scheme.category == category)

    # Search query processing via PostgreSQL plainto_tsquery lexeme detection
    if q and q.strip():
        search_term = q.strip()[:100]
        # Query PostgreSQL plainto_tsquery to see if the search term yields searchable lexemes
        node_count = db.scalar(select(func.numnode(func.plainto_tsquery("english", search_term))))
        if node_count and node_count > 0:
            fts_vector = func.to_tsvector(
                "english",
                func.coalesce(Scheme.scheme_code, "")
                + " "
                + func.coalesce(Scheme.name, "")
                + " "
                + func.coalesce(Scheme.description, "")
                + " "
                + func.coalesce(Scheme.ministry, "")
                + " "
                + func.coalesce(Scheme.category, "")
                + " "
                + func.coalesce(Scheme.benefits, ""),
            ).op("||")(func.array_to_tsvector(Scheme.target_beneficiaries))
            base_filter.append(fts_vector.op("@@")(func.plainto_tsquery("english", search_term)))

    # Total count query
    count_query = select(func.count(Scheme.id)).where(and_(*base_filter))
    total = db.scalar(count_query) or 0

    # Paginated items query
    items_query = (
        select(Scheme)
        .where(and_(*base_filter))
        .order_by(Scheme.name.asc(), Scheme.id.asc())
        .offset(offset)
        .limit(limit)
    )
    items = list(db.scalars(items_query).all())

    return items, total


def get_scheme_by_id(
    db: Session,
    scheme_id: uuid.UUID,
    include_pending: bool = False,
) -> Optional[Scheme]:
    """
    Retrieve single scheme by UUID with visibility checks:
    - Inactive schemes return None (404).
    - Pending schemes return None (404) unless include_pending=True.
    - Active schemes return 200 with full details.
    """
    scheme = db.scalar(select(Scheme).where(Scheme.id == scheme_id))
    if scheme is None:
        return None

    if scheme.scheme_status == "inactive":
        return None

    if scheme.scheme_status == "pending_verification" and not include_pending:
        return None

    return scheme


def get_active_documents_for_scheme(db: Session, scheme_id: uuid.UUID) -> List[SchemeDocument]:
    """Retrieve only active document requirements for a scheme."""
    query = (
        select(SchemeDocument)
        .where(
            and_(
                SchemeDocument.scheme_id == scheme_id,
                SchemeDocument.is_active.is_(True),
            )
        )
        .order_by(SchemeDocument.document_type.asc())
    )
    return list(db.scalars(query).all())
