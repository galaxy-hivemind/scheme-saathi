// ── Scheme Saathi Frontend TypeScript Types ─────────────────────────────────

export interface User {
  id: string;
  email: string;
  is_active: boolean;
  created_at: string;
  profile?: UserProfile;
}

export interface UserProfile {
  id: string;
  user_id: string;
  full_name: string;
  date_of_birth?: string | null;
  gender?: string | null;
  state?: string | null;
  district?: string | null;
  residence_type?: 'rural' | 'urban' | 'semi_urban' | null;
  occupation?: string | null;
  annual_family_income?: number | null;
  preferred_language: 'hi' | 'en';
  profile_data?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface BeneficiaryProfile {
  id: string;
  user_id: string;
  full_name: string;
  relationship: 'father' | 'mother' | 'spouse' | 'son' | 'daughter' | 'sibling' | 'guardian' | 'other';
  date_of_birth?: string | null;
  gender?: string | null;
  state?: string | null;
  district?: string | null;
  residence_type?: 'rural' | 'urban' | 'semi_urban' | null;
  occupation?: string | null;
  annual_family_income?: number | null;
  profile_data?: Record<string, any>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SchemeDocument {
  id: string;
  scheme_id: string;
  document_type: string;
  is_mandatory: boolean;
  description_en: string;
  description_hi: string;
  acceptable_alternatives?: string[];
  issuing_authority?: string;
  where_to_obtain_en?: string;
  where_to_obtain_hi?: string;
}

export interface Scheme {
  id: string;
  scheme_code: string;
  name: string;
  short_title?: string;
  description: string;
  ministry: string;
  category: string;
  scheme_status: 'active' | 'inactive' | 'pending_verification';
  benefits_summary?: string;
  benefits?: Record<string, any>;
  target_beneficiaries?: string[];
  official_portal_url: string;
  application_channel?: string;
  documents?: SchemeDocument[];
  last_verified_at?: string;
}

export interface SchemeSummary {
  id: string;
  scheme_code: string;
  name: string;
  short_title?: string;
  ministry: string;
  category: string;
  scheme_status: string;
  benefits_summary?: string;
  official_portal_url: string;
}

export interface ConditionResult {
  condition_id?: string;
  field: string;
  operator: string;
  expected_value: any;
  actual_value?: any;
  status: 'PASS' | 'FAIL' | 'UNKNOWN';
  reason?: string;
  description_en?: string;
  description_hi?: string;
}

export interface MissingFieldQuestion {
  field: string;
  question_en: string;
  question_hi: string;
  expected_type: string;
  suggested_options?: string[];
}

export interface EligibilityResult {
  scheme_id: string;
  scheme_code?: string;
  scheme_name?: string;
  overall_status: 'PASS' | 'FAIL' | 'UNKNOWN';
  result?: 'eligible' | 'ineligible' | 'potentially_eligible' | 'insufficient_information';
  matched_conditions: ConditionResult[];
  failed_conditions: ConditionResult[];
  unknown_conditions: ConditionResult[];
  missing_fields: string[];
  next_questions: MissingFieldQuestion[];
  explanation_en: string;
  explanation_hi: string;
  evaluated_at: string;
}

export interface PendingAction {
  id: string;
  conversation_id: string;
  user_id: string;
  beneficiary_id?: string | null;
  action_type: 'create_beneficiary' | 'update_beneficiary' | 'update_user_profile';
  payload: Record<string, any>;
  summary: {
    en: string;
    hi: string;
  };
  status: 'PENDING' | 'CONFIRMED' | 'CANCELLED' | 'EXPIRED';
  expires_at: string;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
  action_id?: string;
}

export interface ChatConversation {
  id: string;
  user_id: string;
  title?: string;
  created_at: string;
  updated_at: string;
}

export interface CitizenDocument {
  id: string;
  user_id: string;
  beneficiary_id?: string | null;
  document_type: string;
  file_name: string;
  file_size_bytes: number;
  mime_type: string;
  checksum_sha256: string;
  verification_status: 'PENDING' | 'VERIFIED' | 'REJECTED' | 'EXPIRED';
  rejection_reason?: string | null;
  created_at: string;
}

export interface ChecklistItem {
  document_type: string;
  is_mandatory: boolean;
  description_en: string;
  description_hi: string;
  acceptable_alternatives?: string[];
  where_to_obtain_en?: string;
  where_to_obtain_hi?: string;
  status: 'FULFILLED' | 'MISSING' | 'REJECTED';
  matched_document?: CitizenDocument | null;
}

export interface DocumentChecklistResponse {
  scheme_id: string;
  scheme_name: string;
  target_name: string;
  applicant_type: 'self' | 'beneficiary';
  total_required: number;
  total_fulfilled: number;
  is_ready_for_application: boolean;
  items: ChecklistItem[];
}

export interface ApplicationDraft {
  id: string;
  user_id: string;
  beneficiary_id?: string | null;
  scheme_id: string;
  scheme_code?: string;
  scheme_name: string;
  target_name: string;
  status: 'DRAFT' | 'READY' | 'SUBMITTED' | 'IN_REVIEW' | 'APPROVED' | 'REJECTED' | 'DISBURSED' | 'ARCHIVED';
  prefilled_data: Record<string, any>;
  attached_documents: Array<{
    document_type: string;
    document_id: string;
    file_name: string;
  }>;
  official_portal_url: string;
  notes?: string | null;
  external_reference_number?: string | null;
  submitted_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface StatusHistoryItem {
  id: string;
  application_id: string;
  status: string;
  source_type: 'user_reported' | 'official_integration' | 'portal_sync' | 'admin_action';
  source_reference?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface ApplicationTimelineResponse {
  application_id: string;
  scheme_id: string;
  scheme_name: string;
  scheme_code?: string | null;
  applicant_type: 'self' | 'beneficiary';
  target_name: string;
  current_status: string;
  external_reference_number?: string | null;
  official_portal_url: string;
  submitted_at?: string | null;
  history: StatusHistoryItem[];
  created_at: string;
  updated_at: string;
}

export interface NotificationItem {
  id: string;
  user_id: string;
  application_id?: string | null;
  title: string;
  message: string;
  notification_type: 'status_update' | 'document_expiry' | 'action_required' | 'system';
  priority: 'LOW' | 'NORMAL' | 'HIGH' | 'URGENT';
  channels: string[];
  is_read: boolean;
  read_at?: string | null;
  created_at: string;
}

export interface NotificationListResponse {
  items: NotificationItem[];
  total: number;
  unread_count: number;
}

export interface OCRExtractionResponse {
  document_id: string;
  document_type: string;
  ocr_status: 'COMPLETED' | 'UNAVAILABLE' | 'FAILED' | 'PARTIAL' | 'PENDING';
  extraction_engine: string;
  raw_text_snippet: string;
  extracted_fields: Record<string, any>;
  confidence_score: number;
  pii_masked: boolean;
  pending_action_id?: string | null;
  disclaimer: string;
  extracted_at: string;
}
