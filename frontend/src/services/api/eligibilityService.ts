import { apiClient } from './client';
import { EligibilityResult, BatchEligibilityResponse } from '@/types';
import { MOCK_ELIGIBILITY_RESULTS } from '../mock/mockData';

export const eligibilityService = {
  async checkEligibility(
    schemeId: string,
    profileOverride?: Record<string, unknown>
  ): Promise<EligibilityResult> {
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
    return apiClient.post<EligibilityResult>('/eligibility/check?include_pending=true', {
      scheme_id: schemeId,
      profile_override: profileOverride,
    });
  },

  async evaluateAll(params?: {
    include_pending?: boolean;
    category?: string;
    profile_override?: Record<string, unknown>;
  }): Promise<BatchEligibilityResponse> {
    if (apiClient.isMockMode()) {
      const mockList: EligibilityResult[] = Object.values(MOCK_ELIGIBILITY_RESULTS);
      const eligibleCount = mockList.filter((r) => r.result === 'eligible').length;
      const ineligibleCount = mockList.filter((r) => r.result === 'not_eligible').length;
      const unknownCount = mockList.length - eligibleCount - ineligibleCount;

      return Promise.resolve({
        total_evaluated: mockList.length,
        eligible_count: eligibleCount,
        ineligible_count: ineligibleCount,
        unknown_count: unknownCount,
        results: mockList,
      });
    }

    return apiClient.post<BatchEligibilityResponse>('/eligibility/evaluate-all', {
      include_pending: params?.include_pending ?? true,
      category: params?.category,
      profile_override: params?.profile_override,
    });
  },
};
