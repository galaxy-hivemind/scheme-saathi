import { apiClient } from './client';
import { EligibilityResult } from '@/types';
import { MOCK_ELIGIBILITY_RESULTS } from '../mock/mockData';

export const eligibilityService = {
  async checkEligibility(schemeId: string): Promise<EligibilityResult> {
    if (apiClient.isMockMode()) {
      const result = MOCK_ELIGIBILITY_RESULTS[schemeId] || {
        scheme_id: schemeId,
        result: "potentially_eligible",
        condition_results: [
          {
            field: "annual_family_income",
            operator: "exists",
            expected_value: "specified",
            actual_value: 120000,
            passed: true,
            explanation: "Income matches baseline threshold.",
          },
        ],
        missing_fields: ["domicile_certificate_verified"],
        rule_version_id: "rule-generic-v1",
        evaluated_at: new Date().toISOString(),
        explanation: "Based on standard profile attributes you appear potentially eligible, but domicile proof is needed for confirmation.",
      };
      return Promise.resolve(result);
    }
    return apiClient.post<EligibilityResult>('/eligibility/check', { scheme_id: schemeId });
  },
};
