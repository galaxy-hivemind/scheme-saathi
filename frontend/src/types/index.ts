/**
 * Scheme Saathi — Core TypeScript Interfaces
 * Strictly matches docs/api-contracts.md
 */

export interface APIErrorDetail {
  field?: string;
  message: string;
}

export interface APIError {
  code: string;
  message: string;
  details?: APIErrorDetail[];
}

export interface APIResponse<T> {
  success: boolean;
  data: T | null;
  error: APIError | null;
  request_id: string;
}

export interface UserProfile {
  id: string;                      // UUID
  user_id: string;                 // UUID (foreign key to auth user)
  full_name: string;
  date_of_birth?: string;          // ISO 8601 date: "YYYY-MM-DD"
  gender?: string;                 // "male" | "female" | "transgender" | "other"
  state?: string;
  district?: string;
  residence_type?: "rural" | "urban" | "semi_urban";
  occupation?: string;
  annual_family_income?: number;   // INR
  preferred_language: "hi" | "en"; // default "hi"
  profile_data?: Record<string, unknown>; // scheme-specific extra fields
  created_at: string;              // ISO 8601 datetime
  updated_at: string;
}

export function isProfileComplete(profile: UserProfile | null | undefined): boolean {
  if (!profile) return false;
  return Boolean(
    profile.full_name?.trim() &&
    profile.date_of_birth &&
    profile.gender &&
    profile.state?.trim() &&
    profile.district?.trim() &&
    profile.residence_type &&
    profile.occupation &&
    profile.annual_family_income !== undefined &&
    profile.annual_family_income !== null
  );
}

export interface Scheme {
  id: string;
  scheme_code: string;
  name: string;
  description: string;
  ministry: string;
  category: SchemeCategory;
  benefits: string;
  target_beneficiaries: string;
  geographic_scope: "central" | "state";
  official_url: string;
  application_url?: string;
  source_url: string;
  last_retrieved_at: string;
  last_verified_at: string;
  scheme_status: "active" | "inactive" | "pending_verification";
}

export type SchemeCategory =
  | "agriculture"
  | "education"
  | "health"
  | "housing"
  | "employment"
  | "women_welfare"
  | "children_welfare"
  | "senior_citizens"
  | "disability"
  | "financial_inclusion"
  | "social_security"
  | "skill_development";

export type EligibilityOutcome =
  | "eligible"
  | "not_eligible"
  | "potentially_eligible"
  | "insufficient_information";

export interface EligibilityConditionResult {
  field: string;
  operator: string;
  expected_value: unknown;
  actual_value: unknown;
  passed: boolean | null;  // null = unknown (missing data)
  explanation: string;
}

export interface EligibilityResult {
  scheme_id: string;
  scheme_code?: string;
  scheme_name?: string;
  overall_status?: "PASS" | "FAIL" | "UNKNOWN";
  result: EligibilityOutcome;
  eligible?: boolean | null;
  rule_version_id?: string;
  rule_version?: number;
  is_authoritative?: boolean;
  is_provisional?: boolean;
  criteria_complete?: boolean;
  limitations?: string;
  matched_conditions?: EligibilityConditionResult[];
  failed_conditions?: EligibilityConditionResult[];
  unknown_conditions?: EligibilityConditionResult[];
  condition_results: EligibilityConditionResult[];
  missing_fields: string[];
  evaluated_at: string;
  explanation: string;
}

export interface BatchEligibilityResponse {
  total_evaluated: number;
  eligible_count: number;
  ineligible_count: number;
  unknown_count: number;
  results: EligibilityResult[];
}

export interface DocumentRequirement {
  id: string;
  scheme_id?: string;
  document_type: string;
  title?: string;
  description?: string;
  is_mandatory: boolean;
  alternatives?: string[];
  issuing_authority?: string;
  guidance?: string;
  source_url?: string;
  last_verified_at?: string;
}

export interface UserDocument {
  id: string;
  user_id: string;
  document_type: string;
  upload_status: "pending" | "uploaded" | "failed";
  ocr_status?: "pending" | "processing" | "completed" | "failed" | "not_applicable";
  review_status?: "pending_review" | "accepted" | "rejected";
  created_at: string;
  updated_at: string;
}

export type ApplicationLifecycleState =
  | "draft"
  | "validated"
  | "awaiting_confirmation"
  | "submitted"
  | "validation_failed"
  | "submission_failed"
  | "cancelled";

export interface ValidationResult {
  passed: boolean;
  errors: Array<{ field: string; message: string }>;
  warnings: Array<{ field: string; message: string }>;
}

export interface ApplicationDraft {
  id: string;
  user_id: string;
  scheme_id: string;
  scheme_name?: string;
  form_data: Record<string, unknown>;
  lifecycle_state: ApplicationLifecycleState;
  validation_result?: ValidationResult;
  reference_number?: string;
  submission_source?: "official_integration" | "portal_handoff" | "simulated_demo";
  confirmed_at?: string;
  created_at: string;
  updated_at: string;
  submitted_at?: string;
}

export interface ApplicationStatus {
  application_id: string;
  status: string;
  source_type: "official_integration" | "user_reported" | "simulated_demo";
  source_reference?: string;
  notes?: string;
  recorded_at: string;
}

export type ChatResponseType =
  | "text"
  | "scheme_cards"
  | "eligibility_result"
  | "document_checklist"
  | "application_guide"
  | "benefits_info"
  | "status_tracking"
  | "application_draft"
  | "form_draft"
  | "confirmation_request"
  | "confirmation_result"
  | "tracking_update";

export interface ApplicationGuideData {
  scheme_id: string;
  scheme_code: string;
  scheme_name: string;
  official_url?: string;
  application_url: string;
  steps: string[];
  offline_procedure?: string;
  citizen_eligibility_status?: string | null;
  citizen_eligibility_notes?: string;
}

export interface BenefitsInfoData {
  scheme_id: string;
  scheme_code: string;
  scheme_name: string;
  benefits: string;
  official_url?: string;
}

export interface StatusTrackingData {
  scheme_id: string;
  scheme_code: string;
  scheme_name: string;
  status_url: string;
  post_steps: string[];
}

export interface ChatMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "tool";
  message_content: string;
  spoken_text?: string;
  detected_language?: string;
  response_type?: ChatResponseType;
  data?: unknown;
  suggested_followups?: string[];
  engine_mode?: 'deterministic' | 'gemini_grounded';
  created_at: string;
  workflow_step?: string;
  active_scheme?: any;
  eligibility_summary?: any;
  checklist_data?: any;
  form_draft_data?: any;
  confirmation_data?: any;
}

export interface AgentResponse {
  conversation_id: string;
  message: string;
  spoken_text?: string;
  detected_language?: string;
  response_type: ChatResponseType;
  data?: unknown;
  suggested_followups?: string[];
  requires_action?: boolean;
  action_type?: "confirm_submission" | "upload_document" | "complete_profile";
  engine_mode?: 'deterministic' | 'gemini_grounded';
  workflow_step?: string;
  active_scheme?: any;
  eligibility_summary?: any;
  checklist_data?: any;
  form_draft_data?: any;
  confirmation_data?: any;
}

export interface Notification {
  id: string;
  user_id: string;
  title: string;
  message: string;
  notification_type: "info" | "action_required" | "update";
  read_at?: string;
  created_at: string;
}

export interface HealthStatus {
  status: string;
  timestamp: string;
  version?: string;
  database?: string;
}
