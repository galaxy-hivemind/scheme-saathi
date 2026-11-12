import { apiClient } from './client';
import {
  ApplicationDraft,
  ApplicationReviewSummary,
  PortalIntegrationInfo,
  ApplicationStatus,
  ValidationResult,
  SchemeFormSchema,
} from '@/types';
import { MOCK_APPLICATIONS, MOCK_APPLICATION_STATUS } from '../mock/mockData';

let localApplications: ApplicationDraft[] = [...MOCK_APPLICATIONS];

export interface ConfirmApplicationRequestPayload {
  consent_acknowledged?: boolean;
  expected_version?: number;
  expected_hash?: string;
}

export interface SubmitApplicationResult {
  success: boolean;
  submitted?: boolean;
  manual_portal_required?: boolean;
  integration_supported?: boolean;
  idempotent_replay?: boolean;
  lifecycle_state?: string;
  submission_status?: string;
  external_reference_id?: string | null;
  reference_number?: string | null;
  portal_url?: string;
  confirmed_version?: number;
  confirmed_hash?: string;
  message?: string;
  retry_allowed?: boolean;
  blind_retry_blocked?: boolean;
}

export interface RecordPortalReferencePayload {
  official_reference_number: string;
  submission_date?: string;
  portal_notes?: string;
  confirmation_acknowledged?: boolean;
}

export const applicationService = {
  async getApplications(lang: string = 'en'): Promise<ApplicationDraft[]> {
    if (apiClient.isMockMode()) {
      return Promise.resolve([...localApplications]);
    }
    return apiClient.get<ApplicationDraft[]>('/applications', { lang });
  },

  async getApplicationById(id: string, lang: string = 'en'): Promise<ApplicationDraft> {
    if (apiClient.isMockMode()) {
      const app = localApplications.find((a) => a.id === id);
      if (!app) {
        throw { code: 'NOT_FOUND', message: `Application ${id} not found.` };
      }
      return Promise.resolve(app);
    }
    return apiClient.get<ApplicationDraft>(`/applications/${id}`, { lang });
  },

  async createDraft(
    schemeId: string,
    formData: Record<string, unknown> = {},
    lang: string = 'en'
  ): Promise<ApplicationDraft> {
    if (apiClient.isMockMode()) {
      const newDraft: ApplicationDraft = {
        id: `app-draft-${Date.now()}`,
        user_id: "user-101-uuid",
        scheme_id: schemeId,
        form_data: formData,
        lifecycle_state: "draft",
        validation_result: {
          passed: false,
          errors: [],
          warnings: [{ field: "form_data", message: "Draft needs review and validation." }],
        },
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      localApplications.unshift(newDraft);
      return Promise.resolve(newDraft);
    }
    return apiClient.post<ApplicationDraft>(`/applications/draft?lang=${encodeURIComponent(lang)}`, {
      scheme_id: schemeId,
      form_data: formData,
    });
  },

  async updateDraft(
    id: string,
    formData: Record<string, unknown>,
    lang: string = 'en'
  ): Promise<ApplicationDraft> {
    if (apiClient.isMockMode()) {
      const index = localApplications.findIndex((a) => a.id === id);
      if (index === -1) throw { code: 'NOT_FOUND', message: 'Application not found' };
      localApplications[index] = {
        ...localApplications[index],
        form_data: { ...localApplications[index].form_data, ...formData },
        updated_at: new Date().toISOString(),
      };
      return Promise.resolve(localApplications[index]);
    }
    return apiClient.put<ApplicationDraft>(`/applications/${id}?lang=${encodeURIComponent(lang)}`, {
      form_data: formData,
    });
  },

  async validateDraft(id: string, lang: string = 'en'): Promise<ValidationResult> {
    if (apiClient.isMockMode()) {
      const app = localApplications.find((a) => a.id === id);
      const passed = Object.keys(app?.form_data || {}).length > 2;
      const result: ValidationResult = {
        passed,
        errors: passed ? [] : [{ field: "required_fields", message: "Please fill in all mandatory application details." }],
        warnings: [],
      };
      if (app) {
        app.lifecycle_state = passed ? "awaiting_confirmation" : "validation_failed";
        app.validation_result = result;
      }
      return Promise.resolve(result);
    }
    return apiClient.post<ValidationResult>(`/applications/${id}/validate?lang=${encodeURIComponent(lang)}`);
  },

  async getApplicationReview(id: string, lang: string = 'en'): Promise<ApplicationReviewSummary> {
    if (apiClient.isMockMode()) {
      const app = localApplications.find((a) => a.id === id);
      if (!app) throw { code: 'NOT_FOUND', message: `Application ${id} not found.` };
      return Promise.resolve(
        app.review_summary || {
          application_id: app.id,
          scheme_code: app.scheme_code || app.scheme_id,
          scheme_name: app.scheme_name || app.scheme_id,
          schema_available: true,
          form_supported: true,
          lifecycle_state: app.lifecycle_state,
          version: app.version || 1,
          data_hash: app.data_hash || 'mock-hash',
          sections: [],
          confirmation: {
            confirmed: Boolean(app.confirmed_at),
            valid: Boolean(app.confirmed_at),
            confirmed_at: app.confirmed_at,
            confirmed_version: app.confirmed_version || 1,
          },
          submission: {
            integration_supported: false,
            integration_mode: 'manual_portal_required',
            manual_submission_required: true,
            official_portal_url: app.official_url || 'https://india.gov.in',
          },
        }
      );
    }
    return apiClient.get<ApplicationReviewSummary>(`/applications/${id}/review`, { lang });
  },

  async getPortalRegistry(lang: string = 'en'): Promise<PortalIntegrationInfo[]> {
    if (apiClient.isMockMode()) {
      return Promise.resolve([]);
    }
    return apiClient.get<PortalIntegrationInfo[]>(
      `/applications/portal-registry?lang=${encodeURIComponent(lang)}`
    );
  },

  async getSchemePortalIntegration(
    schemeIdentifier: string,
    lang: string = 'en'
  ): Promise<PortalIntegrationInfo> {
    if (apiClient.isMockMode()) {
      return Promise.resolve({
        scheme_code: schemeIdentifier,
        submission_method: 'portal_assisted',
        official_url: 'https://www.india.gov.in/',
        official_application_url: 'https://www.india.gov.in/',
      });
    }
    return apiClient.get<PortalIntegrationInfo>(
      `/applications/portal-registry/${encodeURIComponent(schemeIdentifier)}?lang=${encodeURIComponent(lang)}`
    );
  },

  async recordPortalReference(
    id: string,
    payload: {
      official_reference_number: string;
      submission_date?: string;
      portal_notes?: string;
      confirmation_acknowledged?: boolean;
    },
    lang: string = 'en'
  ): Promise<ApplicationDraft> {
    if (apiClient.isMockMode()) {
      const ref = String(payload.official_reference_number || '').trim();
      const index = localApplications.findIndex((a) => a.id === id);
      if (index === -1) throw { code: 'NOT_FOUND', message: 'Application not found' };
      const nowIso = new Date().toISOString();
      localApplications[index] = {
        ...localApplications[index],
        lifecycle_state: 'portal_submitted',
        official_reference_number: ref,
        reference_source: 'citizen_reported_portal_reference',
        submission_source: 'portal_assisted',
        submission_method: 'portal_assisted',
        submission_date: payload.submission_date || nowIso,
        submitted_at: payload.submission_date || nowIso,
        is_verified_government_submission: false,
        updated_at: nowIso,
      };
      return Promise.resolve(localApplications[index]);
    }
    return apiClient.post<ApplicationDraft>(
      `/applications/${id}/portal-reference?lang=${encodeURIComponent(lang)}`,
      payload
    );
  },

  async confirmApplication(
    id: string,
    lang: string = 'en',
    payload?: ConfirmApplicationRequestPayload
  ): Promise<{
    confirmed: boolean;
    confirmed_at?: string;
    confirmed_version?: number;
    confirmed_hash?: string;
    lifecycle_state?: string;
    manual_submission_required?: boolean;
    official_portal_url?: string;
    message: string;
  }> {
    if (apiClient.isMockMode()) {
      const app = localApplications.find((a) => a.id === id);
      const nowIso = new Date().toISOString();
      if (app) {
        app.confirmed_at = nowIso;
        app.confirmed_version = app.version || 1;
        app.lifecycle_state = 'confirmed';
      }
      return Promise.resolve({
        confirmed: true,
        confirmed_at: nowIso,
        confirmed_version: app?.version || 1,
        lifecycle_state: 'confirmed',
        manual_submission_required: true,
        official_portal_url: app?.official_url || 'https://india.gov.in',
        message: 'Explicit citizen confirmation recorded successfully.',
      });
    }
    return apiClient.post(
      `/applications/${id}/confirm?lang=${encodeURIComponent(lang)}`,
      payload || { consent_acknowledged: true }
    );
  },

  async submitApplication(
    id: string,
    lang: string = 'en',
    payload?: { idempotency_key?: string }
  ): Promise<SubmitApplicationResult> {
    if (apiClient.isMockMode()) {
      const app = localApplications.find((a) => a.id === id);
      if (app) {
        app.lifecycle_state = 'confirmed';
        app.submission_outcome = 'manual_portal_required';
        app.submission_source = 'manual_portal_required';
      }
      const portalUrl = app?.official_url || 'https://india.gov.in';
      return Promise.resolve({
        success: true,
        submitted: false,
        manual_portal_required: true,
        integration_supported: false,
        lifecycle_state: 'confirmed',
        submission_status: 'manual_portal_required',
        external_reference_id: null,
        reference_number: null,
        portal_url: portalUrl,
        message: `Manual submission on the official portal (${portalUrl}) is required.`,
      });
    }
    return apiClient.post<SubmitApplicationResult>(
      `/applications/${id}/submit?lang=${encodeURIComponent(lang)}`,
      payload || {}
    );
  },

  async reconcileSubmission(
    id: string,
    lang: string = 'en'
  ): Promise<{ resolved: boolean; lifecycle_state?: string; retry_allowed?: boolean; blind_retry_blocked?: boolean; message: string }> {
    if (apiClient.isMockMode()) {
      return Promise.resolve({
        resolved: false,
        blind_retry_blocked: true,
        message: 'Reconciliation unavailable in offline demo mode.',
      });
    }
    return apiClient.post(`/applications/${id}/reconcile?lang=${encodeURIComponent(lang)}`, {});
  },

  async getStatus(id: string): Promise<ApplicationStatus> {
    if (apiClient.isMockMode()) {
      const status = MOCK_APPLICATION_STATUS[id] || {
        application_id: id,
        status: "Draft Saved Locally",
        source_type: "simulated_demo",
        recorded_at: new Date().toISOString(),
      };
      return Promise.resolve(status);
    }
    return apiClient.get<ApplicationStatus>(`/applications/${id}/status`);
  },

  async getFormSchema(schemeIdentifier: string, lang: string = 'en'): Promise<SchemeFormSchema> {
    if (apiClient.isMockMode()) {
      const code = schemeIdentifier.toUpperCase();
      if (code.includes('KISAN')) {
        return Promise.resolve({
          scheme_code: 'PM-KISAN',
          title: 'Pradhan Mantri Kisan Samman Nidhi Application Form',
          form_supported: true,
          schema_available: true,
          official_portal: 'https://pmkisan.gov.in',
          sections: [
            {
              section_id: 'personal_info',
              title: 'Personal & Identification Details',
              fields: [
                { name: 'applicant_name', label: 'Farmer Full Name', type: 'text', required: true, profile_field: 'full_name' },
                { name: 'gender', label: 'Gender', type: 'select', options: ['MALE', 'FEMALE', 'OTHER'], required: true, profile_field: 'gender' },
                { name: 'category', label: 'Social Category', type: 'select', options: ['General', 'OBC', 'SC', 'ST'], required: true, profile_field: 'caste_category' },
                { name: 'aadhaar_number', label: '12-Digit Aadhaar Number', type: 'text', required: true, pattern: '^[0-9]{12}$' },
                { name: 'mobile_number', label: 'Mobile Number', type: 'text', required: true, pattern: '^[6-9][0-9]{9}$' },
              ],
            },
            {
              section_id: 'location_info',
              title: 'Location Details',
              fields: [
                { name: 'state', label: 'State', type: 'text', required: true },
                { name: 'district', label: 'District', type: 'text', required: true },
                { name: 'sub_district_block', label: 'Sub-District / Block', type: 'text', required: true },
                { name: 'village', label: 'Village', type: 'text', required: true },
              ],
            },
            {
              section_id: 'land_bank_info',
              title: 'Land & Bank Details',
              fields: [
                { name: 'land_ownership_type', label: 'Land Ownership Type', type: 'select', options: ['Single', 'Joint'], required: true },
                { name: 'khasra_khatauni_no', label: 'Khasra / Khatauni / Survey No.', type: 'text', required: true },
                { name: 'land_area_acres', label: 'Cultivable Land Area (Acres)', type: 'number', required: true },
                { name: 'bank_account_number', label: 'Bank Account Number', type: 'text', required: true, pattern: '^[0-9]{9,18}$' },
                { name: 'ifsc_code', label: 'Bank IFSC Code', type: 'text', required: true, pattern: '^[A-Z]{4}0[A-Z0-9]{6}$' },
              ],
            },
          ],
        });
      }
      return Promise.resolve({
        scheme_code: schemeIdentifier,
        title: `${schemeIdentifier} — Official Portal Application`,
        form_supported: false,
        schema_available: false,
        schema_status: 'unavailable',
        message: `Verified application form schema and field mapping are unavailable for ${schemeIdentifier}. Complete submission directly on the official government portal.`,
        official_portal: 'https://india.gov.in',
        sections: [],
      });
    }
    return apiClient.get<SchemeFormSchema>(`/applications/schema/${encodeURIComponent(schemeIdentifier)}`, { lang });
  },
};
