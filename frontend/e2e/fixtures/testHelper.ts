import { Page } from '@playwright/test';
import {
  mockUser,
  mockTokenResponse,
  mockUserProfile,
  mockBeneficiaryProfile,
  mockSchemesList,
  mockSchemeDetail,
  mockEligibilityResult,
  mockDocuments,
  mockOcrExtraction,
  mockPendingAction,
  mockApplicationDraft,
  mockTrackingTimeline,
  mockNotifications,
} from './mockData';

/**
 * Intercepts all backend API endpoints with deterministic JSON fixtures.
 * Enables zero-dependency, ultra-reliable CI testing without third-party network access.
 */
export async function setupApiMocks(page: Page): Promise<void> {
  // 1. Health probe
  await page.route('**/api/v1/health', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: { status: 'healthy', version: '0.1.0' },
      }),
    });
  });

  // 2. Auth routes
  await page.route('**/api/v1/auth/register', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: mockTokenResponse }),
    });
  });

  await page.route('**/api/v1/auth/login', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: mockTokenResponse }),
    });
  });

  await page.route('**/api/v1/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: mockUser }),
    });
  });

  // 3. User & Beneficiary Profiles
  await page.route('**/api/v1/profile', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: mockUserProfile }),
    });
  });

  await page.route('**/api/v1/beneficiaries', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          items: [mockBeneficiaryProfile],
          total: 1,
        },
      }),
    });
  });

  await page.route('**/api/v1/beneficiaries/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: mockBeneficiaryProfile }),
    });
  });

  // 4. Schemes Catalogue & Details
  await page.route(/\/api\/v1\/schemes\?/, async (route) => {
    const url = new URL(route.request().url());
    const category = url.searchParams.get('category');
    const q = url.searchParams.get('q')?.toLowerCase();

    let filtered = [...mockSchemesList];
    if (category) {
      filtered = filtered.filter((s) => s.category.toLowerCase() === category.toLowerCase());
    }
    if (q) {
      filtered = filtered.filter((s) => s.name.toLowerCase().includes(q) || s.scheme_code.toLowerCase().includes(q));
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          items: filtered,
          total: filtered.length,
          page: 1,
          limit: 20,
          total_pages: 1,
        },
      }),
    });
  });

  await page.route(/\/api\/v1\/schemes\/[a-zA-Z0-9-]+$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: mockSchemeDetail }),
    });
  });

  // 5. Deterministic Eligibility Check
  await page.route(/\/api\/v1\/eligibility\/evaluate\/.*/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: mockEligibilityResult }),
    });
  });

  await page.route('**/api/v1/eligibility/evaluate-all', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { results: [mockEligibilityResult] } }),
    });
  });

  // 6. Conversational AI Assistant & Pending Actions
  await page.route('**/api/v1/agent/chat', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          conversation_id: 'conv-e2e-123',
          message: 'नमस्ते रमेश जी! आपकी भूमि रिकॉर्ड और आधार के अनुसार आप PM-KISAN योजना के लिए 100% पात्र हैं।',
          pending_action: mockPendingAction,
          intent: 'eligibility_inquiry',
        },
      }),
    });
  });

  await page.route('**/api/v1/agent/actions/pending', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: [mockPendingAction] }),
    });
  });

  await page.route(/\/api\/v1\/agent\/actions\/[a-zA-Z0-9-]+\/confirm/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          action_id: mockPendingAction.id,
          status: 'CONFIRMED',
          confirmed_at: '2026-11-11T12:05:00Z',
        },
      }),
    });
  });

  await page.route(/\/api\/v1\/agent\/actions\/[a-zA-Z0-9-]+\/cancel/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          action_id: mockPendingAction.id,
          status: 'CANCELLED',
        },
      }),
    });
  });

  // 7. Documents Vault & OCR Extraction Engine
  await page.route('**/api/v1/documents/upload', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: mockDocuments[0] }),
    });
  });

  await page.route(/\/api\/v1\/documents\/[a-zA-Z0-9-]+$/, async (route) => {
    if (route.request().method() === 'DELETE') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, message: 'Document deleted successfully' }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: mockDocuments[0] }),
      });
    }
  });

  await page.route(/\/api\/v1\/documents(\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          items: mockDocuments,
          total: mockDocuments.length,
        },
      }),
    });
  });

  await page.route(/\/api\/v1\/documents\/checklist\/.*/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          scheme_id: mockSchemesList[0].id,
          scheme_name: mockSchemesList[0].name,
          target_name: 'Ramesh Kumar (Self)',
          applicant_type: 'self',
          total_required: 2,
          total_fulfilled: 2,
          is_ready_for_application: true,
          items: [
            {
              document_type: 'aadhaar_card',
              is_mandatory: true,
              description_en: 'Aadhaar Card with linked bank account',
              description_hi: 'बैंक खाते से लिंक आधार कार्ड',
              status: 'FULFILLED',
              matched_document: mockDocuments[0],
            },
            {
              document_type: 'land_records_ro_r',
              is_mandatory: true,
              description_en: 'Land Records (Khatauni / Khasra)',
              description_hi: 'भूमि अभिलेख (खसरा / खतौनी)',
              status: 'FULFILLED',
              matched_document: mockDocuments[1],
            },
          ],
        },
      }),
    });
  });

  await page.route(/\/api\/v1\/documents\/[a-zA-Z0-9-]+\/ocr$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: mockOcrExtraction }),
    });
  });

  // 8. Application Drafts & Tracking
  await page.route('**/api/v1/applications/draft', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: mockApplicationDraft }),
    });
  });

  await page.route(/\/api\/v1\/applications\/[a-zA-Z0-9-]+\/submit/, async (route) => {
    const postData = route.request().postDataJSON() || {};
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          ...mockApplicationDraft,
          status: 'SUBMITTED',
          external_reference_number: postData.external_reference_number || 'PMK-2026-UP-88419',
        },
      }),
    });
  });

  await page.route(/\/api\/v1\/applications\/[a-zA-Z0-9-]+$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: mockApplicationDraft }),
    });
  });

  await page.route(/\/api\/v1\/applications(\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          items: [mockApplicationDraft],
          total: 1,
        },
      }),
    });
  });

  await page.route(/\/api\/v1\/tracking\/[a-zA-Z0-9-]+\/timeline/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockTrackingTimeline),
    });
  });

  await page.route(/\/api\/v1\/tracking\/[a-zA-Z0-9-]+\/sync/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ...mockTrackingTimeline,
        current_status: 'IN_REVIEW',
      }),
    });
  });

  // 9. Notifications
  await page.route('**/api/v1/notifications/unread-count', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ unread_count: 1 }),
    });
  });

  await page.route(/\/api\/v1\/notifications(\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: mockNotifications,
        total: 1,
        unread_count: 1,
      }),
    });
  });
}

/**
 * Pre-populates citizen authentication session in localStorage before page load.
 */
export async function injectAuthSession(page: Page): Promise<void> {
  await page.goto('/login');
  await page.evaluate((token) => {
    localStorage.setItem('scheme_saathi_token', token);
  }, mockTokenResponse.access_token);
}

/**
 * Performs citizen login through the browser UI.
 */
export async function loginViaUI(page: Page): Promise<void> {
  await page.goto('/login');
  await page.fill('input[type="email"]', mockUser.email);
  await page.fill('input[type="password"]', 'StrongCitizenPassword123!');
  await page.click('button[type="submit"]');
  await page.waitForURL('/');
}
