# Scheme Saathi — Bilingual Citizen Journey Frontend UI

Responsive, accessible, mobile-first bilingual (Hindi / English) Single-Page Application (SPA) designed to empower Indian citizens to discover, evaluate, and apply for government welfare schemes.

Built with **React 18**, **TypeScript**, **Vite**, and **Tailwind CSS**.

---

## 1. Key Architectural Principles

1. **Zero Client-Side Business Decisions**
   The frontend never manufactures eligibility decisions, infers missing demographics (e.g. calculating DOB from age), or fabricates scheme criteria. All eligibility evaluations are executed deterministically by the backend statutory rules engine.

2. **Bilingual by Design (Hindi First)**
   Fully localized interface supporting both **Hindi (`hi`)** and **English (`en`)** via `LanguageContext`. Language toggle is accessible globally in the navigation header with instant re-rendering and localStorage persistence.

3. **Human-in-the-Loop Confirmation Gate**
   AI model proposals for demographic or profile updates are rendered as explicit, durable pending actions. The citizen must click "Confirm" or "Cancel" before any database writes occur.

4. **Official Portal Handoff & Ack Logging**
   Provides direct deep-links to official central/state ministry portals, and allows citizens to record official application/acknowledgement reference IDs for tracking.

5. **Live Status Tracking & Departmental Audit Trail**
   Step-progress visualization (`DRAFT` $\to$ `SUBMITTED` $\to$ `IN_REVIEW` $\to$ `APPROVED` $\to$ `DISBURSED`) and a timestamped timeline audit trail capturing every state change and source verification.

---

## 2. Core Views & Features

| View | Route | Description |
|---|---|---|
| **Conversational Intake** | `/` | Multilingual chat interface with voice speech input (Web Speech API), smart suggestion chips, and pending action confirmation dialogs. |
| **Schemes Catalogue** | `/schemes` | Full-text search, category filters (Agriculture, Health, Housing, Business, etc.), verified 2026 badges, and quick eligibility check. |
| **Scheme Details** | `/schemes/:id` | Detailed scheme specifications, statutory criteria breakdown, required documents list, official portal link, and application draft creation. |
| **Document Vault & Checklist** | `/documents` | Scheme document readiness progress bar, mandatory vs optional tags, acceptable alternatives, and secure upload with SHA-256 integrity hashing. |
| **Applications & Handoff** | `/applications` | Filterable list of application packages, external portal links, and acknowledgement ID recording modal. |
| **Timeline Tracking** | `/tracking` | Visual step tracker, official portal sync, and chronological status transition audit trail. |
| **Profile & Beneficiaries** | `/profile` | Account holder socio-economic profile and family member beneficiary management (strict isolation without cross-contamination). |
| **Notifications** | Drawer | Slide-out notifications center polling unread alerts every 30 seconds with mark-as-read controls. |

---

## 3. Technology Stack

- **Runtime & Framework:** Node.js $\ge$ 18, React 18.3.1
- **Language & Compiler:** TypeScript 5.6.3, Vite 6.0.3
- **Styling:** Tailwind CSS 3.4.16, PostCSS, Autoprefixer
- **Routing:** React Router v6 (`react-router-dom`)
- **HTTP Client:** Axios 1.7.9 with JWT interceptor and typed service methods
- **Icons:** Lucide React 0.468.0

---

## 4. Setup & Running Locally

### Prerequisites
- Node.js $\ge$ 18.x
- Backend API running at `http://localhost:8000/api/v1`

### Installation
```bash
cd frontend
npm install
```

### Development Server
```bash
npm run dev
```
Starts Vite local dev server at `http://localhost:5173`.

### Production Build
```bash
npm run build
```
Typechecks with `tsc` and compiles optimized production assets into `dist/`.

---

## 5. Environment Configuration

Create a `.env` file in `frontend/` to customize the backend URL if running outside the default localhost:
```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```
