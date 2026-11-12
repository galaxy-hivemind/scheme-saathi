import { describe, it, expect, beforeAll, vi } from 'vitest';
import { apiClient } from '../client';
import { schemeService } from '../schemeService';
import { eligibilityService } from '../eligibilityService';
import { applicationService } from '../applicationService';
import { documentService } from '../documentService';

describe('Frontend Services & API Contract Matching', () => {
  beforeAll(() => {
    apiClient.setMockMode(true);
  });
  it('retrieves schemes list matching Scheme interface', async () => {
    const schemes = await schemeService.getSchemes();
    expect(schemes.length).toBeGreaterThan(0);
    const pmKisan = schemes.find((s) => s.scheme_code === 'PM-KISAN');
    expect(pmKisan).toBeDefined();
    expect(pmKisan?.ministry).toBe('Ministry of Agriculture and Farmers Welfare');
    expect(pmKisan?.geographic_scope).toBe('central');
    expect(pmKisan?.scheme_status).toBe('active');
  });

  it('filters schemes by keyword and category', async () => {
    const agSchemes = await schemeService.getSchemes({ category: 'agriculture' });
    expect(agSchemes.every((s) => s.category === 'agriculture')).toBe(true);

    const searchResults = await schemeService.getSchemes({ q: 'kisan' });
    expect(searchResults.some((s) => s.scheme_code === 'PM-KISAN')).toBe(true);
  });

  it('evaluates deterministic eligibility results', async () => {
    const result = await eligibilityService.checkEligibility('scheme-pm-kisan-01');
    expect(result.scheme_id).toBe('scheme-pm-kisan-01');
    expect(['eligible', 'not_eligible', 'potentially_eligible', 'insufficient_information']).toContain(result.result);
    expect(result.condition_results.length).toBeGreaterThan(0);
    expect(result.condition_results[0]).toHaveProperty('passed');
    expect(result.condition_results[0]).toHaveProperty('explanation');
  });

  it('manages document checklists and user documents', async () => {
    const checklist = await documentService.getChecklist('scheme-pm-kisan-01');
    expect(checklist.length).toBeGreaterThan(0);
    expect(checklist.some((d) => d.document_type === 'aadhaar')).toBe(true);

    const userDocs = await documentService.getUserDocuments();
    expect(Array.isArray(userDocs)).toBe(true);
  });

  it('handles application drafting, validation, and confirmation lifecycle', async () => {
    const draft = await applicationService.createDraft('scheme-pm-kisan-01', {
      applicant_name: 'Test Citizen',
      land_holding_acres: 1.0,
      state: 'Uttar Pradesh',
    });
    expect(draft.id).toBeDefined();
    expect(draft.lifecycle_state).toBe('draft');

    const validation = await applicationService.validateDraft(draft.id);
    expect(validation).toHaveProperty('passed');

    const confirmation = await applicationService.confirmApplication(draft.id);
    expect(confirmation.confirmed).toBe(true);

    const submission = await applicationService.submitApplication(draft.id);
    expect(submission.success).toBe(true);
    expect(submission.manual_portal_required).toBe(true);
    expect(submission.submitted).toBe(false);
    expect(submission.external_reference_id).toBeNull();
  });

  it('fetches scheme-specific form schema and updates draft packet', async () => {
    const schema = await applicationService.getFormSchema('PM-KISAN');
    expect(schema).toBeDefined();
    expect(schema.sections.length).toBeGreaterThan(0);
    const allFieldNames = schema.sections.flatMap((s) => s.fields.map((f) => f.name));
    expect(allFieldNames).toContain('aadhaar_number');
    expect(allFieldNames).toContain('bank_account_number');

    const draft = await applicationService.createDraft('PM-KISAN', {
      applicant_name: 'Ramesh Kumar',
    });
    const updated = await applicationService.updateDraft(draft.id, {
      applicant_name: 'Ramesh Kumar',
      village: 'Shivpur',
      khasra_khatauni_no: '104/2',
      bank_account_number: '123456789012',
      ifsc_code: 'SBIN0001234',
    });
    expect(updated.id).toBe(draft.id);
    expect(updated.form_data?.village).toBe('Shivpur');
  });

  it('enforces honest document lifecycle: upload never auto-verifies until citizen review & verify', async () => {
    const file = new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], 'aadhaar.png', {
      type: 'image/png',
    });
    const uploaded = await documentService.uploadDocument('aadhaar_card', file);
    expect(uploaded.lifecycle_status).toBe('awaiting_citizen_review');
    expect(uploaded.verification_status).not.toBe('verified');
    expect(uploaded.citizen_confirmed_accurate).toBe(false);

    const reviewed = await documentService.reviewDocument(
      uploaded.id,
      { holder_name: 'Ramesh Kumar', document_number: '234567890123' },
      true
    );
    expect(reviewed.lifecycle_status).toBe('reviewed');
    expect(reviewed.citizen_confirmed_accurate).toBe(true);

    const verified = await documentService.verifyDocument(uploaded.id);
    expect(verified.lifecycle_status).toBe('verified');

    const del = await documentService.deleteDocument(uploaded.id);
    expect(del.deleted).toBe(true);
  });

  it('forwards selected language parameter on application readiness calls', async () => {
    apiClient.setMockMode(false);
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValueOnce([]);
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue({ passed: true, errors: [], warnings: [] });

    await applicationService.getApplications('mr');
    expect(getSpy).toHaveBeenCalledWith('/applications', { lang: 'mr' });

    await applicationService.validateDraft('draft-123', 'hi');
    expect(postSpy).toHaveBeenCalledWith('/applications/draft-123/validate?lang=hi');

    getSpy.mockRestore();
    postSpy.mockRestore();
    apiClient.setMockMode(true);
  });
});
