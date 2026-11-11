# End-to-End (E2E) Browser Testing with Playwright

## Overview

Scheme Saathi includes a comprehensive, deterministic Playwright browser test suite covering the entire citizen journey lifecycle across desktop (`chromium`) and mobile (`Pixel 5`) emulation viewports.

The test suite validates:
1. **Citizen Authentication & Session Management**: Registration, login, JWT storage in `localStorage`, protected route redirects, and logout.
2. **Bilingual Localization & Language Switcher**: Default Hindi Devanagari typography, real-time toggling between Hindi and English, and preference persistence across page reloads.
3. **Welfare Scheme Discovery & Eligibility Evaluation**: Catalogue rendering, 2026 verified badges, search by keywords, category pill filters (Agriculture, Housing, Health), quick eligibility evaluation modal, and scheme detail views.
4. **Conversational AI Assistant & Agency Gates**: Welcome greeting, suggested chips, conversational responses, and **Human-in-the-Loop Confirmation Gate** execution for pending actions.
5. **Document Vault, OCR Extraction Engine & UIDAI PII Masking**: Document readiness checklists, SHA-256 checksum verification in vault, OCR modal preview, and strict validation that **Aadhaar PII is masked (`XXXXXXXX1234`)** before profile update confirmation.
6. **Application Drafts, Portal Handoff & Tracking Timeline**: Draft creation, official portal handoff link verification (`pmkisan.gov.in`), external reference ID recording, vertical audit trail timeline, portal sync simulation, and slide-out notification drawer badge.
7. **End-to-End Citizen Journey Lifecycle**: Comprehensive multi-step workflow tying all core capabilities together in a continuous user session.

---

## Directory Structure

```
frontend/
├── playwright.config.ts          # Playwright config with Vite webServer & multi-viewport projects
├── e2e/
│   ├── fixtures/
│   │   ├── mockData.ts          # Authoritative JSON fixtures conforming to backend API schemas
│   │   └── testHelper.ts        # API route interceptors (`setupApiMocks`), session injectors, login helpers
│   ├── auth.spec.ts             # Authentication & session protection tests
│   ├── bilingual.spec.ts        # Hindi/English localization & Devanagari typography tests
│   ├── schemes.spec.ts          # Schemes catalogue, category filter & eligibility modal tests
│   ├── chat.spec.ts             # Conversational agent & pending action gate tests
│   ├── documents_ocr.spec.ts    # Document vault, OCR extraction & UIDAI PII masking tests
│   ├── tracking.spec.ts         # Application drafts, portal handoff & audit timeline tests
│   └── full_journey.spec.ts     # Complete citizen journey lifecycle test
```

---

## Zero-Dependency Route Mocking Philosophy

To ensure ultra-fast, 100% deterministic CI execution without depending on external government portals or live Gemini API tokens, all network calls to `/api/v1/*` are intercepted at the browser network layer using Playwright's `page.route()` in `e2e/fixtures/testHelper.ts`.

All fixtures in `e2e/fixtures/mockData.ts` strictly conform to the production FastAPI response schemas:
```ts
{
  "success": true,
  "data": { ... }
}
```

---

## Running E2E Tests Locally

### Prerequisites

From the `frontend/` directory, ensure dependencies and Playwright browser binaries are installed:

```bash
cd frontend
npm install
npx playwright install chromium
```

### Execution Commands

```bash
# Run all E2E tests across Desktop Chromium and Mobile Pixel 5
npm run test:e2e

# Run with interactive UI mode (debugger & timeline inspector)
npm run test:e2e:ui

# Run a specific test spec
npx playwright test auth.spec.ts

# Open HTML test execution report
npm run test:e2e:report
```

---

## Continuous Integration (CI)

The Playwright test suite executes on every push and pull request targeting `main` or `frontend/**` branches via `.github/workflows/e2e.yml`.

If a test fails in CI, Playwright generates a failure trace, screenshot, and HTML report uploaded as a GitHub Actions artifact (`playwright-report`), retained for 14 days.
