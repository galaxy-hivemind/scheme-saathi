import { apiClient } from './client';
import { ApplicationDraft, ApplicationStatus, ValidationResult } from '@/types';
import { MOCK_APPLICATIONS, MOCK_APPLICATION_STATUS } from '../mock/mockData';

let localApplications: ApplicationDraft[] = [...MOCK_APPLICATIONS];

export const applicationService = {
  async getApplications(): Promise<ApplicationDraft[]> {
    if (apiClient.isMockMode()) {
      return Promise.resolve([...localApplications]);
    }
    return apiClient.get<ApplicationDraft[]>('/applications');
  },

  async getApplicationById(id: string): Promise<ApplicationDraft> {
    if (apiClient.isMockMode()) {
      const app = localApplications.find((a) => a.id === id);
      if (!app) {
        throw { code: 'NOT_FOUND', message: `Application ${id} not found.` };
      }
      return Promise.resolve(app);
    }
    return apiClient.get<ApplicationDraft>(`/applications/${id}`);
  },

  async createDraft(schemeId: string, formData: Record<string, unknown> = {}): Promise<ApplicationDraft> {
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
    return apiClient.post<ApplicationDraft>('/applications/draft', { scheme_id: schemeId, form_data: formData });
  },

  async updateDraft(id: string, formData: Record<string, unknown>): Promise<ApplicationDraft> {
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
    return apiClient.put<ApplicationDraft>(`/applications/${id}`, { form_data: formData });
  },

  async validateDraft(id: string): Promise<ValidationResult> {
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
    return apiClient.post<ValidationResult>(`/applications/${id}/validate`);
  },

  async confirmApplication(id: string): Promise<{ confirmed: boolean; message: string }> {
    if (apiClient.isMockMode()) {
      const app = localApplications.find((a) => a.id === id);
      if (app) {
        app.confirmed_at = new Date().toISOString();
        app.lifecycle_state = "awaiting_confirmation";
      }
      return Promise.resolve({
        confirmed: true,
        message: "Explicit user confirmation recorded successfully.",
      });
    }
    return apiClient.post<{ confirmed: boolean; message: string }>(`/applications/${id}/confirm`);
  },

  async submitApplication(id: string): Promise<{ success: boolean; reference_number?: string; portal_url?: string }> {
    if (apiClient.isMockMode()) {
      const app = localApplications.find((a) => a.id === id);
      const refNo = `SAATHI/SIM/${new Date().getFullYear()}/${Math.floor(100000 + Math.random() * 900000)}`;
      if (app) {
        app.lifecycle_state = "submitted";
        app.reference_number = refNo;
        app.submitted_at = new Date().toISOString();
        app.submission_source = "simulated_demo";
      }
      return Promise.resolve({
        success: true,
        reference_number: refNo,
      });
    }
    return apiClient.post<{ success: boolean; reference_number?: string; portal_url?: string }>(`/applications/${id}/submit`);
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
};
