from sqlalchemy import and_, or_

from app.core.auth import AuthContext
from app.models.document import Document
from app.services.citation_formatter import RetrievedChunk


def document_acl_filter(auth: AuthContext):
    if auth.is_admin:
        return True

    group_clauses = [Document.allowed_group_ids.contains([group]) for group in auth.groups]
    return or_(
        Document.visibility == "public",
        Document.owner_id == auth.user_id,
        Document.allowed_user_ids.contains([auth.user_id]),
        and_(Document.visibility == "org", or_(*group_clauses)) if group_clauses else False,
        or_(*group_clauses) if group_clauses else False,
    )


def can_access_document(document: Document | None, auth: AuthContext) -> bool:
    if document is None:
        return False
    if auth.is_admin:
        return True
    if document.visibility == "public":
        return True
    if document.owner_id == auth.user_id:
        return True
    if auth.user_id in (document.allowed_user_ids or []):
        return True
    if set(auth.groups) & set(document.allowed_group_ids or []):
        return True
    return False


def filter_retrieved_chunks(results: list[RetrievedChunk], auth: AuthContext) -> tuple[list[RetrievedChunk], int]:
    allowed: list[RetrievedChunk] = []
    denied = 0
    for result in results:
        if can_access_document(getattr(result.chunk, "document", None), auth):
            allowed.append(result)
        else:
            denied += 1
    return allowed, denied

