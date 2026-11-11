# Conversational Intake & Agent API Contract (v1)

## Overview

The Conversational Intake & Agent module provides an AI-orchestrated conversational layer powered by Google Gemini (default: `gemini-3.8-flash`) or a local deterministic rule-based fallback engine.

Citizens can converse in Hindi, English, and Hinglish to discover schemes, evaluate statutory welfare eligibility, and stage updates to family beneficiaries or their own profile.

### Security Architecture & Separation of Powers

1. **Deterministic Rule Authority:** Statutory eligibility is never calculated or overridden by Gemini. All eligibility checks execute exclusively via the deterministic AST rule engine (`app/eligibility/engine.py`).
2. **Zero Model Database Writes:** The AI model cannot create, update, or delete profiles. Confirmation tools (`confirm_beneficiary_creation`, `confirm_profile_update`) are excluded from model tools.
3. **Durable Pending Actions (`pending_actions`):** Actions staged by proposal tools are stored in PostgreSQL with status `PENDING` and a 15-minute TTL.
4. **Independent Citizen Confirmation Endpoint:** The citizen explicitly confirms staged actions via `POST /api/v1/agent/actions/{action_id}/confirm`. The endpoint accepts no client override payload; it acquires a database row-level lock (`SELECT ... FOR UPDATE`), verifies ownership and state, and executes the exact persisted payload.
5. **Account vs Family Beneficiary Isolation:** Account-holder updates dispatch to `profile_service.update_user_profile()`, while family-member updates dispatch to `beneficiary_service.update_beneficiary()`. Updating `self` via `beneficiary_service` is rejected with HTTP 400.
6. **Demographic Integrity (Zero Fabrication):** Approximate ages (e.g., 62) are stored in `profile_data["approximate_age"]` with `date_of_birth = None`. Missing statutory fields produce tri-state `UNKNOWN` outcomes with bilingual `NextQuestion` guidance.

---

## Endpoints

### 1. Citizen Conversational Chat
`POST /api/v1/agent/chat`

**Headers:** `Authorization: Bearer <jwt>`

**Request Body (`ChatRequest`):**
```json
{
  "message": "Meri maa ke liye kaunsi schemes hain? Umra 62 saal hai, gaon mein rehti hain.",
  "conversation_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
  "beneficiary_id": null,
  "language": "hi"
}
```

**Response (`APIResponse[ChatResponse]`):**
```json
{
  "success": true,
  "data": {
    "conversation_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
    "message_id": "b1ffca00-8d1c-4fe9-aa7e-7cc0ce491b22",
    "role": "assistant",
    "content": "आपकी माताजी के लिए इंदिरा गांधी राष्ट्रीय वृद्धावस्था पेंशन योजना उपलब्ध हो सकती है। क्या आप उनका विवरण जोड़ना चाहते हैं?",
    "response_type": "confirmation_request",
    "structured_data": {
      "schemes": [
        {
          "id": "c2ddbb11-7c2d-4ef0-998f-8dd1df502c33",
          "scheme_code": "IGNOAPS",
          "name": "Indira Gandhi National Old Age Pension Scheme"
        }
      ]
    },
    "pending_action": {
      "action_id": "e3eeaa22-6b3e-4fa1-889e-9ee2ea613d44",
      "action_type": "create_beneficiary",
      "summary_en": "Add family member: Sunita Devi (Mother, age ~62)",
      "summary_hi": "परिवार के सदस्य को जोड़ें: Sunita Devi (mother, age ~62)",
      "expires_at": "2026-11-11T15:30:00Z"
    },
    "created_at": "2026-11-11T15:15:00Z"
  },
  "error": null,
  "request_id": "req-0111f2fb-480b-4f03"
}
```

---

### 2. Confirm Staged Pending Action
`POST /api/v1/agent/actions/{action_id}/confirm`

Explicitly confirms and executes a staged pending action.

**Headers:** `Authorization: Bearer <jwt>`  
**Path Parameters:** `action_id: UUID`  
**Request Body:** None. (Executes exact persisted payload).

**Response (`APIResponse[ActionExecutionResponse]`):**
```json
{
  "success": true,
  "data": {
    "action_id": "e3eeaa22-6b3e-4fa1-889e-9ee2ea613d44",
    "action_type": "create_beneficiary",
    "status": "EXECUTED",
    "affected_entity_id": "f4ffbb33-5c4f-4ab2-770f-0ff3fb724e55",
    "executed_at": "2026-11-11T15:16:42Z",
    "message": "Family member 'Sunita Devi' (mother) added successfully."
  },
  "error": null,
  "request_id": "req-0111f2fb-480b-4f03"
}
```

**Errors:**
- `401 Unauthorized`: Missing or invalid JWT.
- `404 Not Found`: Action does not exist or belongs to another user.
- `409 Conflict`: Action is already `EXECUTED` or `CANCELLED`.
- `410 Gone`: Action has expired (`now > expires_at`).

---

### 3. Cancel Staged Pending Action
`POST /api/v1/agent/actions/{action_id}/cancel`

Cancels a staged pending action before execution.

**Headers:** `Authorization: Bearer <jwt>`  
**Path Parameters:** `action_id: UUID`  
**Request Body:** None.

**Response (`APIResponse[ActionCancelResponse]`):**
```json
{
  "success": true,
  "data": {
    "action_id": "e3eeaa22-6b3e-4fa1-889e-9ee2ea613d44",
    "status": "CANCELLED",
    "message": "Pending action cancelled."
  },
  "error": null,
  "request_id": "req-0111f2fb-480b-4f03"
}
```

---

### 4. List Conversations
`GET /api/v1/agent/conversations`

**Headers:** `Authorization: Bearer <jwt>`  
**Query Parameters:** `page: int = 1`, `limit: int = 20`

**Response (`APIResponse[List[ConversationSummaryResponse]]`):**
```json
{
  "success": true,
  "data": [
    {
      "id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
      "title": "Meri maa ke liye kaunsi schemes hain?",
      "language": "hi",
      "status": "active",
      "updated_at": "2026-11-11T15:16:42Z"
    }
  ],
  "error": null,
  "request_id": "req-0111f2fb-480b-4f03"
}
```

---

### 5. Get Conversation Detail
`GET /api/v1/agent/conversations/{conversation_id}`

**Headers:** `Authorization: Bearer <jwt>`  
**Path Parameters:** `conversation_id: UUID`

**Response (`APIResponse[ConversationDetailResponse]`):**
```json
{
  "success": true,
  "data": {
    "id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
    "title": "Meri maa ke liye kaunsi schemes hain?",
    "language": "hi",
    "status": "active",
    "beneficiary_id": null,
    "context_state": {},
    "messages": [
      {
        "id": "11111111-2222-3333-4444-555555555555",
        "role": "user",
        "content": "Meri maa ke liye kaunsi schemes hain? Umra 62 saal hai, gaon mein rehti hain.",
        "response_type": "text",
        "structured_data": null,
        "created_at": "2026-11-11T15:14:55Z"
      },
      {
        "id": "22222222-3333-4444-5555-666666666666",
        "role": "assistant",
        "content": "आपकी माताजी के लिए...",
        "response_type": "confirmation_request",
        "structured_data": {},
        "created_at": "2026-11-11T15:15:00Z"
      }
    ],
    "created_at": "2026-11-11T15:14:55Z",
    "updated_at": "2026-11-11T15:15:00Z"
  },
  "error": null,
  "request_id": "req-0111f2fb-480b-4f03"
}
```

