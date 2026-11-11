"""
Top-level API v1 router — aggregates all sub-routers.
"""
from fastapi import APIRouter
from app.api.v1 import health, auth, profile, schemes, eligibility, agent, documents, applications

api_router = APIRouter()

# Health check (public)
api_router.include_router(health.router, tags=["Health"])

# Authentication (public login/register, authenticated /me)
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])

# Profile (authenticated)
api_router.include_router(profile.router, prefix="/profile", tags=["Profile"])

# Scheme Catalogue (authenticated)
api_router.include_router(schemes.router, prefix="/schemes", tags=["Schemes"])

# Deterministic Eligibility Evaluation Engine (Phase 3)
api_router.include_router(eligibility.router, prefix="/eligibility", tags=["Eligibility"])

# Multilingual AI Voice Assistant (Phase 3 Voice AI)
api_router.include_router(agent.router, prefix="/agent", tags=["Agent"])

# Citizen Document Vault & Checklist (authenticated)
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])

# Application Readiness & Official Portal Guidance (authenticated)
api_router.include_router(applications.router, prefix="/applications", tags=["Applications"])
