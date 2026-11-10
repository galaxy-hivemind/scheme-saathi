# Scheme Saathi — System Architecture

## 1. Overview

Scheme Saathi is a mobile-first, conversational AI platform that helps Indian citizens discover, evaluate, and apply for central-government welfare schemes.

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                             │
│          React + TypeScript (Vite) — Mobile-first PWA           │
│  Chat UI  │  Scheme Cards  │  Document Upload  │  Tracking       │
└───────────────────────────┬─────────────────────────────────────┘
                            │  HTTPS / REST + JSON
┌───────────────────────────▼─────────────────────────────────────┐
│                      BACKEND LAYER                              │
│                   FastAPI (Python 3.14)                         │
│                                                                 │
│  ┌─────────────────┐   ┌──────────────────────────────────────┐ │
│  │   API Routes    │   │          AI Agent Orchestrator       │ │
│  │  /api/v1/...    │◄──│  Gemini 1.5 Pro + Tool Calling       │ │
│  └────────┬────────┘   │  (single orchestrator, not multi-    │ │
│           │            │   agent — coordinates all tools)     │ │
│           │            └──────────────────────────────────────┘ │
│           ▼                                                     │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Service Layer                            ││
│  │  ProfileService │ SchemeService │ ApplicationService        ││
│  │  DocumentService │ TrackingService │ NotificationService    ││
│  └─────────────────────────────────────────────────────────────┘│
│           │                                                     │
│  ┌────────▼──────────────────────────────────────────────────┐  │
│  │              Eligibility Rule Engine (deterministic)      │  │
│  │  Python evaluator — NEVER delegates decisions to LLM      │  │
│  └───────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┴───────────────────┐
        ▼                                       ▼
┌───────────────┐                       ┌───────────────────┐
│  PostgreSQL   │                       │ Supabase Storage  │
│  (Supabase /  │                       │ Private documents │
│   standard)   │                       │   (Phase 4)       │
└───────────────┘                       └───────────────────┘
```

---

## 2. Component responsibilities

### 2.1 Frontend (React + TypeScript)
- Renders conversational UI, scheme cards, document checklists.
- Sends chat messages to `/api/v1/agent/chat`.
- Renders structured JSON responses from the agent.
- Manages file uploads through the upload endpoint.
- **Does NOT evaluate eligibility or make business decisions.**

### 2.2 API Routes (FastAPI)
- Thin route handlers — validate requests and delegate to services.
- Return typed `APIResponse` wrappers.
- Apply authentication middleware.
- Apply rate limiting.

### 2.3 AI Agent Orchestrator
- Single Gemini-powered orchestrator.
- Understands citizen intent in Hindi and English.
- Selects and calls registered backend tools.
- Maintains conversation and workflow state.
- **Cannot override eligibility results.**
- **Cannot submit applications without user confirmation.**

### 2.4 Service Layer
- Business logic lives here, not in routes.
- Each service is independently testable.
- Services call database models and external APIs.

### 2.5 Eligibility Rule Engine
- Deterministic Python evaluator.
- Operates on scheme rule JSON + user profile data.
- Returns `eligible | not_eligible | potentially_eligible | insufficient_information`.
- Produces per-condition explanations.
- **Results are final — the LLM can explain them but not change them.**

### 2.6 Database (PostgreSQL via Supabase)
- All persistent state.
- Row-level security enforced at the application layer.
- UUIDs for all primary keys.
- Soft-delete patterns for sensitive records.

---

## 3. Agent orchestration flow

```
Citizen message
      │
      ▼
  Orchestrator (Gemini)
      │  understands intent, may ask clarifying questions
      │
      ▼
  Tool selection & calling
      │
      ├── get_user_profile()       → ProfileService
      ├── search_schemes()         → SchemeService
      ├── check_eligibility()      → EligibilityEngine (deterministic)
      ├── build_document_checklist() → DocumentService
      ├── create_application_draft() → ApplicationService
      ├── request_application_confirmation() → requires human input
      └── submit_application()     → ApplicationService (after confirmation)
      │
      ▼
  Structured response (JSON)
      │
      ▼
  Frontend renders cards / messages
```

---

## 4. Security model

| Concern | Approach |
|---|---|
| Authentication | Self-contained JWT access tokens (HMAC-SHA256) + bcrypt password hashing |
| Authorization | Service layer enforces user ownership |
| Secrets | Environment variables only, never committed |
| Document privacy | Supabase Storage with signed URLs |
| LLM guardrails | Tool inputs validated before execution |
| Submission safety | Explicit confirmation record required |
| Data minimization | Collect only fields needed for active schemes |
| Test Database Safety | Verified DDL gateways (`safe_drop_all`, etc.) with fail-closed live catalog verification. Development rule mandates all test destructive operations route through gateways. Direct raw SQL/DDL bypassing gateways is prohibited by test policy and restricted by database-level role permissions and session lockout. |

---

## 5. Data flow — eligibility check

```
1. User provides profile data (via chat or profile form)
2. Orchestrator calls check_eligibility(user_id, scheme_id)
3. EligibilityEngine loads scheme rules (versioned JSON)
4. Engine evaluates each rule condition against user profile
5. Engine returns: result + per-condition explanations + missing fields
6. Result is stored in eligibility_checks table (with rule version)
7. Orchestrator passes result to Gemini for natural-language explanation
8. Gemini explains result — it cannot modify the result
9. Frontend renders eligibility card
```

---

## 6. Source integrity & Verification Architecture

In Phase 2, source integrity is enforced at both data model and ingestion layers:
- `source_url` — authoritative primary government portal or notification URL.
- `source_evidence` — JSONB array of atomic `SourceEvidenceEntry` records substantiating 6 material claims (`scheme_existence`, `operational_status`, `benefit_structure`, `eligibility_criteria`, `documentation_requirements`, `application_channel`).
- `last_retrieved_at` — UTC timestamp of official document retrieval.
- `last_verified_at` — UTC timestamp of editorial/factual verification (mandatory for `active`, null for `pending_verification`).
- `scheme_status` — `active | inactive | pending_verification`.

The system guarantees:
1. Schemes lacking complete 2026 verification evidence remain `pending_verification` and are hidden from citizen searches by default (`GET /api/v1/schemes`).
2. The seed importer refuses to overwrite verified schemes without explicit override authorization (`--allow-override-verified`).
3. Eligibility rule definitions are append-only; updates close the prior version and insert a new version incremented by 1.
4. Fast discovery uses PostgreSQL Full-Text Search (GIN index over text vectors and beneficiary array vectors) with fallback handling for stop words and punctuation.
