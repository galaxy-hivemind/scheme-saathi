"""
Top-level API v1 router — aggregates all sub-routers.
"""
from fastapi import APIRouter
from app.api.v1 import health, auth, profile, beneficiaries, schemes, eligibility, chat, documents, applications

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

# Future feature routers (Phases 3-8):
# from app.api.v1 import eligibility, documents, applications, tracking, notifications, agent
# api_router.include_router(eligibility.router, prefix="/eligibility", tags=["Eligibility"])
# api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
# api_router.include_router(applications.router, prefix="/applications", tags=["Applications"])
# api_router.include_router(tracking.router, prefix="/tracking", tags=["Tracking"])
# api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
# api_router.include_router(agent.router, prefix="/agent", tags=["Agent"])
