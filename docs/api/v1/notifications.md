# Citizen Notifications & Action Alerts API Contract (v1)

## Overview

The Citizen Notifications engine delivers timely alerts, status changes, and required action reminders to citizens. It features unread count badge counters for real-time notification bells, pagination, filterable read states, and delivery hook integration for SMS and WhatsApp channels.

### Security Architecture & Invariants

1. **Strict Tenant Isolation (Anti-IDOR):** Citizens can only list, view, or mark their own notifications as read (`user_id == current_user.id`). Cross-account actions return HTTP 403 Forbidden.
2. **Canonical Notification Types:**
   - `status_update`: Alert triggered when an application status changes (e.g. SUBMITTED, IN_REVIEW, APPROVED).
   - `document_expiry`: Warning that an uploaded identity/income certificate is approaching expiration.
   - `action_required`: Immediate action needed by the citizen (e.g. resubmit document, biometric verification).
   - `system`: Important system announcement or policy update.
3. **Priority Classes:**
   - `LOW`: Informational notices.
   - `NORMAL`: Standard application lifecycle transitions.
   - `HIGH`: Critical updates such as approvals or benefit disbursements.
   - `URGENT`: Action items with statutory deadlines.

---

## Endpoints

### 1. List Notifications
`GET /api/v1/notifications`

Retrieve a paginated list of notifications for the authenticated citizen.

**Headers:** `Authorization: Bearer <jwt>`

**Query Parameters:**
- `is_read` (`boolean`, optional): Filter by read status (`true` or `false`).
- `notification_type` (`string`, optional): Filter by type (`status_update`, `document_expiry`, `action_required`, `system`).
- `limit` (`integer`, optional, default 50, max 100): Page limit.
- `offset` (`integer`, optional, default 0): Page offset.

**Response (`200 OK`):**
```json
{
  "items": [
    {
      "id": "c1b2a3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
      "user_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
      "application_id": "f5a4b3c2-1d0e-4f8a-9b7c-3d2e1f0a9b8c",
      "title": "Application Update: PM Kisan Samman Nidhi",
      "message": "Status changed to IN_REVIEW. Details: Under field verification by Tehsildar",
      "notification_type": "status_update",
      "priority": "NORMAL",
      "channels": ["in_app"],
      "is_read": false,
      "read_at": null,
      "created_at": "2026-11-11T14:30:00Z"
    }
  ],
  "total": 1,
  "unread_count": 1
}
```

---

### 2. Get Unread Count
`GET /api/v1/notifications/unread-count`

Retrieve unread notification count for notification bell badge indicator.

**Headers:** `Authorization: Bearer <jwt>`

**Response (`200 OK`):**
```json
{
  "unread_count": 1
}
```

---

### 3. Mark Notification as Read
`PUT /api/v1/notifications/{notification_id}/read`

Mark a specific notification as read.

**Headers:** `Authorization: Bearer <jwt>`

**Response (`200 OK`):**
```json
{
  "id": "c1b2a3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
  "user_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
  "application_id": "f5a4b3c2-1d0e-4f8a-9b7c-3d2e1f0a9b8c",
  "title": "Application Update: PM Kisan Samman Nidhi",
  "message": "Status changed to IN_REVIEW. Details: Under field verification by Tehsildar",
  "notification_type": "status_update",
  "priority": "NORMAL",
  "channels": ["in_app"],
  "is_read": true,
  "read_at": "2026-11-11T14:35:00Z",
  "created_at": "2026-11-11T14:30:00Z"
}
```

---

### 4. Mark All Notifications as Read
`PUT /api/v1/notifications/read-all`

Mark all unread notifications as read.

**Headers:** `Authorization: Bearer <jwt>`

**Response (`200 OK`):**
```json
{
  "updated_count": 1
}
```
