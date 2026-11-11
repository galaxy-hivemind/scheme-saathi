"""
Top-level API v1 router — aggregates all sub-routers.
"""
from fastapi import APIRouter
from app.api.v1 import (
    health,
    auth,
    profile,
    beneficiaries,
    schemes,
    eligibility,
    chat,
    documents,
    applications,
    tracking,
    notifications,
)

api_router = APIRouter()

# Health check (public)
api_router.include_router(health.router, tags=["Health"])

# Authentication (public login/register, authenticated /me)
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])

# Profile (authenticated)
api_router.include_router(profile.router, prefix="/profile", tags=["Profile"])

# Beneficiaries (authenticated — self and family members)
api_router.include_router(beneficiaries.router, prefix="/beneficiaries", tags=["Beneficiaries"])

# Scheme Catalogue (authenticated)
api_router.include_router(schemes.router, prefix="/schemes", tags=["Schemes"])

# Eligibility Engine (authenticated)
api_router.include_router(eligibility.router, prefix="/eligibility", tags=["Eligibility"])

# Agent / Conversational Intake (authenticated)
api_router.include_router(chat.router, prefix="/agent", tags=["Agent / Conversational Intake"])

# Documents (authenticated — secure file upload, download, checklist)
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])

# Applications (authenticated — application drafts, attached documents, portal handoff)
api_router.include_router(applications.router, prefix="/applications", tags=["Applications"])

# Tracking (authenticated — status timeline, history audit trail, portal sync)
api_router.include_router(tracking.router, prefix="/tracking", tags=["Application Tracking"])

# Notifications (authenticated — citizen alerts, unread counter)
api_router.include_router(notifications.router, prefix="/notifications", tags=["Citizen Notifications"])
