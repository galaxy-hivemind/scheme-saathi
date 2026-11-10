import { describe, it, expect } from 'vitest';
import { schemeService } from '../schemeService';
import { eligibilityService } from '../eligibilityService';
import { applicationService } from '../applicationService';
import { documentService } from '../documentService';

describe('Frontend Services & API Contract Matching', () => {
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
    expect(submission.reference_number).toBeDefined();
  });
});
