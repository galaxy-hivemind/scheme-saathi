/**
 * Authoritative E2E Test Mock Data Fixtures for Scheme Saathi.
 * Conforms to Backend FastAPI v1 API Contracts and Frontend TypeScript types.
 */

import {
  User,
  UserProfile,
  BeneficiaryProfile,
  SchemeSummary,
  Scheme,
  EligibilityResult,
  CitizenDocument,
  OCRExtractionResponse,
  PendingAction,
  ApplicationDraft,
  ApplicationTimelineResponse,
  NotificationItem,
} from '../types';

export const mockUser: User = {
  id: '3fa85f64-5717-4562-b3fc-2c963f66afa6',
  email: 'ramesh.kumar@example.com',
  is_active: true,
  created_at: '2026-11-01T10:00:00Z',
};

export const mockTokenResponse = {
  access_token: 'mock-jwt-token-scheme-saathi-session-32chars',
  token_type: 'bearer',
  expires_in_seconds: 604800,
  user_id: mockUser.id,
  email: mockUser.email,
};

export const mockUserProfile: UserProfile = {
  id: '4ba85f64-5717-4562-b3fc-2c963f66afa7',
  user_id: mockUser.id,
  full_name: 'Ramesh Kumar',
  preferred_language: 'hi',
  state: 'Uttar Pradesh',
  district: 'Varanasi',
  pincode: '221001',
  profile_data: {
    occupation: 'Small Farmer',
    family_members_count: 4,
  },
  created_at: '2026-11-01T10:00:00Z',
  updated_at: '2026-11-10T12:00:00Z',
};

export const mockBeneficiaryProfile: BeneficiaryProfile = {
  id: '5ca85f64-5717-4562-b3fc-2c963f66afa8',
  user_id: mockUser.id,
  full_name: 'Ramesh Kumar',
  gender: 'MALE',
  age: 42,
  annual_income: 120000,
  caste_category: 'OBC',
  state: 'Uttar Pradesh',
  district: 'Varanasi',
  is_farmer: true,
  landholding_acres: 1.5,
  has_pucca_house: false,
  is_street_vendor: false,
  is_student: false,
  is_pregnant: false,
  is_lactating: false,
  created_at: '2026-11-01T10:00:00Z',
  updated_at: '2026-11-10T12:00:00Z',
};

export const mockSchemesList: SchemeSummary[] = [
  {
    id: '6da85f64-5717-4562-b3fc-2c963f66afa9',
    scheme_code: 'PM-KISAN',
    name: 'Pradhan Mantri Kisan Samman Nidhi (पीएम-किसान)',
    ministry: 'Ministry of Agriculture and Farmers Welfare',
    category: 'agriculture',
    benefits_summary: '₹6,000 per year direct income support in three equal installments of ₹2,000 to eligible farmer families.',
    official_portal_url: 'https://pmkisan.gov.in/',
    is_active: true,
  },
  {
    id: '7ea85f64-5717-4562-b3fc-2c963f66afb0',
    scheme_code: 'PMAY-G',
    name: 'Pradhan Mantri Awas Yojana - Gramin (पीएम आवास योजना - ग्रामीण)',
    ministry: 'Ministry of Rural Development',
    category: 'housing',
    benefits_summary: 'Financial assistance of ₹1,20,000 in plains and ₹1,30,000 in hilly states for construction of pucca house.',
    official_portal_url: 'https://pmayg.nic.in/',
    is_active: true,
  },
  {
    id: '8fa85f64-5717-4562-b3fc-2c963f66afb1',
    scheme_code: 'PM-JAY',
    name: 'Ayushman Bharat PM-JAY (आयुष्मान भारत)',
    ministry: 'Ministry of Health and Family Welfare',
    category: 'health',
    benefits_summary: 'Free healthcare coverage up to ₹5,00,000 per family per year for secondary and tertiary hospitalization.',
    official_portal_url: 'https://pmjay.gov.in/',
    is_active: true,
  },
  {
    id: '9aa85f64-5717-4562-b3fc-2c963f66afb2',
    scheme_code: 'PMSVANIDHI',
    name: 'PM SVANidhi (पीएम स्वनिधि)',
    ministry: 'Ministry of Housing and Urban Affairs',
    category: 'business',
    benefits_summary: 'Collateral-free working capital loan up to ₹50,000 with 7% interest subsidy for urban street vendors.',
    official_portal_url: 'https://pmsvanidhi.mohua.gov.in/',
    is_active: true,
  },
];

export const mockSchemeDetail: Scheme = {
  ...mockSchemesList[0],
  description: 'Central sector scheme to supplement financial needs of landholding farmers for agricultural inputs and domestic needs.',
  eligibility_rules: [
    { rule_id: 'r1', field: 'is_farmer', operator: 'EQUALS', value: true, description: 'Must be an active cultivator/farmer' },
    { rule_id: 'r2', field: 'landholding_acres', operator: 'LESS_THAN_OR_EQUAL', value: 5.0, description: 'Landholding must not exceed 5.0 acres' },
  ],
  required_documents: [
    { document_type: 'aadhaar_card', is_mandatory: true, description: 'Aadhaar Card with linked bank account' },
    { document_type: 'land_records_ro_r', is_mandatory: true, description: 'Land Record (Khatauni / Khasra)' },
  ],
  benefit_details: {
    amount: 6000,
    frequency: 'Yearly',
    disbursement_mode: 'Direct Benefit Transfer (DBT)',
  },
  application_guidance: 'Eligible farmers can apply online at pmkisan.gov.in or through Common Service Centres (CSC).',
  created_at: '2026-11-01T10:00:00Z',
  updated_at: '2026-11-10T12:00:00Z',
};

export const mockEligibilityResult: any = {
  scheme_id: mockSchemesList[0].id,
  scheme_name: mockSchemesList[0].name,
  scheme_code: mockSchemesList[0].scheme_code,
  overall_status: 'PASS',
  status: 'ELIGIBLE',
  is_eligible: true,
  matched_conditions: [
    {
      field: 'is_farmer',
      operator: 'EQUALS',
      value: true,
      description_hi: 'नागरिक एक सत्यापित किसान परिवार हैं',
      description_en: 'Citizen is an active farmer family',
      status: 'PASS',
    },
    {
      field: 'landholding_acres',
      operator: 'LESS_THAN_OR_EQUAL',
      value: 1.5,
      description_hi: 'भूमि धारण 5 एकड़ से कम है (1.5 एकड़)',
      description_en: 'Landholding is under 5.0 acres',
      status: 'PASS',
    },
  ],
  matched_rules: [
    'नागरिक एक सत्यापित किसान परिवार हैं / Citizen is an active farmer family',
    'भूमि धारण 5 एकड़ से कम है (1.5 एकड़) / Landholding is under 5.0 acres',
  ],
  failed_conditions: [],
  failed_rules: [],
  missing_information: [],
  benefit_amount: 6000,
  confidence_score: 1.0,
  evaluated_at: '2026-11-11T12:00:00Z',
  explanation_hi: 'आपकी भूमि व व्यवसाय विवरण के आधार पर आप PM-KISAN योजना के सभी पात्रता मानदंडों को पूरा करते हैं।',
  explanation_en: 'Based on your landholding and farmer profile, you meet 100% of the eligibility criteria for PM-KISAN.',
};

export const mockDocuments: CitizenDocument[] = [
  {
    id: 'b2a85f64-5717-4562-b3fc-2c963f66afb4',
    user_id: mockUser.id,
    beneficiary_id: null,
    document_type: 'aadhaar_card',
    file_name: 'aadhaar_card_masked.pdf',
    mime_type: 'application/pdf',
    file_size_bytes: 245000,
    checksum_sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    verification_status: 'VERIFIED',
    rejection_reason: null,
    created_at: '2026-11-05T09:00:00Z',
  },
  {
    id: 'c3a85f64-5717-4562-b3fc-2c963f66afb5',
    user_id: mockUser.id,
    beneficiary_id: null,
    document_type: 'land_records_ro_r',
    file_name: 'khasra_khatauni.pdf',
    mime_type: 'application/pdf',
    file_size_bytes: 412000,
    checksum_sha256: 'a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e',
    verification_status: 'PENDING',
    rejection_reason: null,
    created_at: '2026-11-08T11:20:00Z',
  },
];

export const mockOcrExtraction: OCRExtractionResponse = {
  document_id: 'b2a85f64-5717-4562-b3fc-2c963f66afb4',
  document_type: 'aadhaar_card',
  ocr_status: 'COMPLETED',
  extraction_engine: 'tesseract_devanagari_v2',
  raw_text_snippet: 'भारत सरकार GOVERNMENT OF INDIA\nरमेश कुमार Ramesh Kumar\nजन्म तिथि / DOB: 12/05/1984\nपुरुष / MALE\nXXXXXXXX1234',
  extracted_fields: {
    full_name: 'Ramesh Kumar',
    gender: 'MALE',
    date_of_birth: '1984-05-12',
    aadhaar_masked: 'XXXXXXXX1234',
    state: 'Uttar Pradesh',
    district: 'Varanasi',
    pincode: '221001',
  },
  confidence_score: 0.96,
  pii_masked: true,
  pending_action_id: 'd4a85f64-5717-4562-b3fc-2c963f66afb6',
  disclaimer: 'OCR extraction suggestions require explicit citizen confirmation before updating beneficiary records.',
  extracted_at: '2026-11-11T12:00:00Z',
};

export const mockPendingAction: PendingAction = {
  id: 'd4a85f64-5717-4562-b3fc-2c963f66afb6',
  conversation_id: 'conv-e2e-123',
  user_id: mockUser.id,
  action_type: 'update_beneficiary',
  payload: {
    full_name: 'Ramesh Kumar',
    gender: 'MALE',
    aadhaar_masked: 'XXXXXXXX1234',
    state: 'Uttar Pradesh',
    district: 'Varanasi',
    pincode: '221001',
  },
  summary: {
    hi: 'सत्यापित आधार कार्ड के आधार पर नागरिक प्रोफ़ाइल अपडेट करें',
    en: 'Update citizen profile using extracted Aadhaar card details',
  },
  status: 'PENDING',
  expires_at: '2026-11-11T12:15:00Z',
  created_at: '2026-11-11T12:00:00Z',
};

export const mockApplicationDraft: ApplicationDraft = {
  id: 'e5a85f64-5717-4562-b3fc-2c963f66afb7',
  user_id: mockUser.id,
  beneficiary_id: null,
  scheme_id: mockSchemesList[0].id,
  scheme_code: 'PM-KISAN',
  scheme_name: 'Pradhan Mantri Kisan Samman Nidhi (पीएम-किसान)',
  target_name: 'Ramesh Kumar (Self)',
  status: 'READY',
  prefilled_data: {
    applicant_name: 'Ramesh Kumar',
    land_area_acres: 1.5,
    state: 'Uttar Pradesh',
    district: 'Varanasi',
  },
  attached_documents: [
    {
      document_type: 'aadhaar_card',
      document_id: 'b2a85f64-5717-4562-b3fc-2c963f66afb4',
      file_name: 'aadhaar_card_masked.pdf',
    },
    {
      document_type: 'land_records_ro_r',
      document_id: 'c3a85f64-5717-4562-b3fc-2c963f66afb5',
      file_name: 'khasra_khatauni.pdf',
    },
  ],
  official_portal_url: 'https://pmkisan.gov.in/RegistrationForm.aspx?ref=scheme-saathi',
  notes: 'Documents verified. Ready to apply on official government portal.',
  external_reference_number: null,
  submitted_at: null,
  created_at: '2026-11-10T16:00:00Z',
  updated_at: '2026-11-10T16:00:00Z',
};

export const mockTrackingTimeline: ApplicationTimelineResponse = {
  application_id: mockApplicationDraft.id,
  scheme_id: mockSchemesList[0].id,
  scheme_name: 'Pradhan Mantri Kisan Samman Nidhi (पीएम-किसान)',
  scheme_code: 'PM-KISAN',
  applicant_type: 'self',
  target_name: 'Ramesh Kumar (Self)',
  current_status: 'SUBMITTED',
  external_reference_number: 'PMK-2026-UP-88419',
  official_portal_url: 'https://pmkisan.gov.in/',
  submitted_at: '2026-11-10T16:15:00Z',
  history: [
    {
      id: 'h1',
      application_id: mockApplicationDraft.id,
      status: 'DRAFT',
      source_type: 'user_reported',
      notes: 'Application draft created on Scheme Saathi',
      created_at: '2026-11-10T16:00:00Z',
    },
    {
      id: 'h2',
      application_id: mockApplicationDraft.id,
      status: 'READY',
      source_type: 'user_reported',
      notes: 'All required documents verified and attached',
      created_at: '2026-11-10T16:05:00Z',
    },
    {
      id: 'h3',
      application_id: mockApplicationDraft.id,
      status: 'SUBMITTED',
      source_type: 'portal_sync',
      source_reference: 'PMK-2026-UP-88419',
      notes: 'Citizen submitted application on official PM-KISAN portal',
      created_at: '2026-11-10T16:15:00Z',
    },
  ],
  created_at: '2026-11-10T16:00:00Z',
  updated_at: '2026-11-10T16:15:00Z',
};

export const mockNotifications: NotificationItem[] = [
  {
    id: 'f6a85f64-5717-4562-b3fc-2c963f66afb8',
    user_id: mockUser.id,
    application_id: mockApplicationDraft.id,
    title: 'PM-KISAN आवेदन जमा हुआ / Application Submitted',
    message: 'आपका PM-KISAN आवेदन राज्य स्तर पर सत्यापन के लिए भेजा गया है। / Application sent for state verification.',
    notification_type: 'status_update',
    priority: 'HIGH',
    channels: ['in_app', 'sms'],
    is_read: false,
    read_at: null,
    created_at: '2026-11-10T16:15:00Z',
  },
];
