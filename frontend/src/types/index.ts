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
  preferred_language: "hi" | "en" | "mr"; // default "hi"
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
  short_title?: string;
  description: string;
  ministry: string;
  department?: string;
  category: SchemeCategory;
  benefits: string;
  target_beneficiaries: string | string[];
  geographic_scope: "central" | "state";
  official_url: string;
  application_url?: string;
  source_url: string;
  last_retrieved_at: string;
  last_verified_at: string;
  scheme_status: "active" | "inactive" | "pending_verification";
  source_evidence?: Array<{
    claim: string;
    statement: string;
    source_url: string;
    issuing_authority?: string;
    verification_status?: string;
    verified_at?: string;
    citation?: string;
    publication_date?: string | null;
    retrieved_at?: string;
    source_type?: string;
  }>;
  documents?: DocumentRequirement[];
  required_documents?: DocumentRequirement[];
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

export type DocumentLifecycleStatus =
  | "uploaded"
  | "ocr_processing"
  | "extracted"
  | "awaiting_citizen_review"
  | "reviewed"
  | "verified"
  | "rejected";

export interface UserDocument {
  id: string;
  user_id: string;
  document_type: string;
  file_name?: string;
  content_type?: string;
  size_bytes?: number;
  sha256?: string;
  upload_status: "pending" | "uploaded" | "failed";
  ocr_status?: "pending" | "processing" | "completed" | "limited" | "failed" | "not_applicable";
  ocr_engine?: string;
  ocr_confidence?: number;
  ocr_note?: string;
  extracted_fields?: Record<string, any>;
  reviewed_fields?: Record<string, any>;
  lifecycle_status?: DocumentLifecycleStatus;
  verification_status?: DocumentLifecycleStatus | string;
  review_status?: "pending_review" | "reviewed" | "verified" | "accepted" | "rejected";
  citizen_confirmed_accurate?: boolean;
  rejection_reason?: string | null;
  reviewed_at?: string | null;
  verified_at?: string | null;
  audit_trail?: Array<{ timestamp: string; action: string; details: string }>;
  created_at: string;
  updated_at: string;
}

export type ApplicationLifecycleState =
  | "draft"
  | "validated"
  | "awaiting_confirmation"
  | "confirmed"
  | "submitting"
  | "submitted"
  | "portal_submitted"
  | "validation_failed"
  | "submission_failed"
  | "submission_unknown"
  | "cancelled";

export interface PortalIntegrationInfo {
  scheme_id?: string;
  scheme_code?: string;
  scheme_name?: string;
  portal_name?: string;
  official_url?: string;
  official_application_url?: string;
  tracking_url?: string;
  source_url?: string;
  application_availability?: string;
  application_availability_label?: string;
  submission_method?: "direct_api" | "portal_assisted" | "manual" | string;
  submission_method_label?: string;
  supported_api_integration?: boolean;
  api_provider?: string | null;
  structured_form_supported?: boolean;
  required_documents?: Array<string | { doc_type?: string; label?: string; document_name?: string; mandatory?: boolean }>;
  security_controls_notice?: string;
  official_instructions?: {
    summary?: string;
    online_steps?: string[];
    offline_process?: string;
    offline_guidance?: string;
    verification_status?: string;
    source_url?: string;
    security_notice?: string;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface NormalizedApplicationRecord {
  citizen_id: string;
  scheme_id: string;
  application_id: string;
  official_reference_number?: string | null;
  submission_date?: string | null;
  portal_url?: string | null;
  tracking_url?: string | null;
  application_status: string;
  submission_method: string;
  submission_source?: string | null;
  reference_source?: string | null;
  is_verified_government_submission?: boolean;
  [key: string]: unknown;
}

export interface ReadinessDocumentItem {
  document_type: string;
  title: string;
  is_mandatory: boolean;
  applicable: boolean;
  status: string;
  status_label: string;
  reason?: string | null;
  vault_document_id?: string | null;
}

export interface ReadinessBreakdown {
  profile: {
    complete: boolean;
    percentage: number;
    filled_count: number;
    total_count: number;
    missing_fields: string[];
    missing_labels: string[];
  };
  form: {
    complete: boolean;
    percentage: number;
    filled_mandatory: number;
    total_mandatory: number;
    missing_fields: string[];
    invalid_fields: string[];
  };
  documents: {
    complete: boolean;
    percentage: number;
    applicable_mandatory: number;
    verified: number;
    reviewed: number;
    awaiting_review: number;
    rejected: number;
    missing: number;
    waived: number;
    items: ReadinessDocumentItem[];
  };
}

export interface ValidationResult {
  passed: boolean;
  overall_percentage?: number;
  errors: Array<{ field: string; message: string }>;
  warnings: Array<{ field: string; message: string }>;
  breakdown?: ReadinessBreakdown;
}

export interface ApplicationReviewField {
  name: string;
  label: string;
  type: string;
  value: any;
  required: boolean;
  is_missing?: boolean;
  source_tier?: string | null;
  source_category?: "verified_document" | "profile_derived" | "citizen_entered" | "system_default" | "missing" | string;
  source_badge?: string;
  conflict?: any;
  unverified_ocr_hint?: any;
}

export interface ApplicationReviewSection {
  section_id: string;
  title: string;
  fields: ApplicationReviewField[];
}

export interface ApplicationReviewSummary {
  application_id?: string | null;
  scheme_code: string;
  scheme_name: string;
  schema_available: boolean;
  form_supported: boolean;
  lifecycle_state: ApplicationLifecycleState;
  version: number;
  data_hash: string;
  sections: ApplicationReviewSection[];
  missing_mandatory_fields?: string[];
  conflicting_fields?: any[];
  documents?: ReadinessBreakdown["documents"];
  validation_result?: ValidationResult;
  confirmation?: {
    confirmed: boolean;
    valid: boolean;
    confirmed_at?: string | null;
    confirmed_by_user_id?: string | null;
    confirmed_version?: number | null;
    confirmed_hash?: string | null;
    invalidated_at?: string | null;
  };
  submission?: {
    integration_supported: boolean;
    integration_mode: "official_integration" | "direct_api" | "portal_assisted" | "manual" | "manual_portal_required" | string;
    integration_provider?: string | null;
    manual_submission_required: boolean;
    official_portal_url?: string;
    tracking_url?: string;
    submission_method?: string;
    external_reference_id?: string | null;
    official_reference_number?: string | null;
    submission_date?: string | null;
    submitted_at?: string | null;
    blind_retry_blocked?: boolean;
    last_attempt?: any;
  };
  portal_integration?: PortalIntegrationInfo;
  application_record?: NormalizedApplicationRecord;
  audit_trail?: Array<{ timestamp: string; action: string; actor?: string; details: string }>;
}

export interface ApplicationDraft {
  id: string;
  user_id: string;
  scheme_id: string;
  scheme_code?: string;
  scheme_name?: string;
  official_url?: string;
  portal_url?: string;
  tracking_url?: string;
  schema_available?: boolean;
  prefill_summary?: any;
  review_summary?: ApplicationReviewSummary;
  portal_integration?: PortalIntegrationInfo;
  application_record?: NormalizedApplicationRecord;
  form_data: Record<string, unknown>;
  lifecycle_state: ApplicationLifecycleState;
  version?: number;
  data_hash?: string;
  confirmed_version?: number | null;
  confirmed_hash?: string | null;
  confirmation_invalidated_at?: string | null;
  submission_outcome?: string;
  submission_method?: string;
  integration_supported?: boolean;
  integration_provider?: string | null;
  external_reference_id?: string | null;
  official_reference_number?: string | null;
  reference_source?: string | null;
  submission_date?: string | null;
  blind_retry_blocked?: boolean;
  legacy_synthetic_submission?: boolean;
  is_verified_government_submission?: boolean;
  legacy_reference_number?: string | null;
  validation_result?: ValidationResult;
  reference_number?: string;
  submission_source?: "official_integration" | "portal_assisted" | "portal_handoff" | "manual_portal_required" | "legacy_handoff_unverified" | string;
  confirmed_at?: string | null;
  created_at: string;
  updated_at: string;
  submitted_at?: string;
}

export interface SchemeFormField {
  name: string;
  label: string;
  type: 'text' | 'number' | 'select' | 'textarea' | 'date';
  required: boolean;
  options?: string[];
  pattern?: string;
  placeholder?: string;
  profile_field?: string;
  default?: string | number | boolean;
}

export interface SchemeFormSection {
  section_id: string;
  title: string;
  fields: SchemeFormField[];
}

export interface SchemeFormSchema {
  scheme_code: string;
  scheme_name?: string;
  title: string;
  form_supported: boolean;
  schema_available?: boolean;
  schema_status?: string;
  message?: string;
  official_portal?: string;
  sections: SchemeFormSection[];
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
  tool_calls_used?: string[];
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
  tool_calls_used?: string[];
}

export interface PersistedConversationTurn {
  id?: string;
  role: "user" | "assistant" | "tool";
  content: string;
  spoken_text?: string;
  language?: string;
  response_type?: string;
  workflow_step?: string;
  active_scheme?: any;
  active_scheme_code?: string | null;
  engine_mode?: string;
  suggested_followups?: string[];
  tool_calls?: string[];
  data?: unknown;
  eligibility_summary?: unknown;
  checklist_data?: unknown;
  form_draft_data?: unknown;
  confirmation_data?: unknown;
  created_at?: string;
}

export interface PersistedConversationResponse {
  conversation_id: string;
  active_scheme_code?: string | null;
  workflow_step?: string;
  language?: string;
  state?: Record<string, any>;
  turns: PersistedConversationTurn[];
  updated_at?: string | null;
}

export interface ConversationSummary {
  conversation_id: string;
  active_scheme_code?: string | null;
  workflow_step?: string;
  language?: string;
  turn_count?: number;
  updated_at?: string | null;
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
