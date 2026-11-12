import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { DocumentsPage } from '../DocumentsPage';
import { ApplicationsPage } from '../ApplicationsPage';
import { LanguageProvider } from '@/context/LanguageContext';
import { AuthProvider } from '@/context/AuthContext';
import { ApiModeProvider } from '@/context/ApiModeContext';
import { ApplicationDraft, UserDocument } from '@/types';

const sampleDocs: UserDocument[] = [
  {
    id: 'doc-awaiting-1',
    user_id: 'u-1',
    document_type: 'aadhaar_card',
    file_name: 'aadhaar_front.png',
    upload_status: 'uploaded',
    ocr_status: 'limited',
    lifecycle_status: 'awaiting_citizen_review',
    verification_status: 'awaiting_citizen_review',
    review_status: 'pending_review',
    citizen_confirmed_accurate: false,
    extracted_fields: {},
    reviewed_fields: {},
    created_at: '2026-11-12T00:00:00Z',
    updated_at: '2026-11-12T00:00:00Z',
  },
  {
    id: 'doc-reviewed-2',
    user_id: 'u-1',
    document_type: 'bank_passbook',
    file_name: 'passbook.pdf',
    upload_status: 'uploaded',
    ocr_status: 'completed',
    lifecycle_status: 'reviewed',
    verification_status: 'reviewed',
    review_status: 'reviewed',
    citizen_confirmed_accurate: true,
    extracted_fields: { ifsc_code: 'SBIN0001234' },
    reviewed_fields: { holder_name: 'Ramesh Kumar', ifsc_code: 'SBIN0001234', account_number: '123456789012' },
    created_at: '2026-11-12T00:00:00Z',
    updated_at: '2026-11-12T00:00:00Z',
  },
  {
    id: 'doc-rejected-3',
    user_id: 'u-1',
    document_type: 'income_certificate',
    file_name: 'expired_income.pdf',
    upload_status: 'uploaded',
    ocr_status: 'completed',
    lifecycle_status: 'rejected',
    verification_status: 'rejected',
    review_status: 'rejected',
    rejection_reason: 'Certificate expired (expiry date 2024-03-31 is in the past).',
    created_at: '2026-11-12T00:00:00Z',
    updated_at: '2026-11-12T00:00:00Z',
  },
];

const samplePmaygDraft: ApplicationDraft = {
  id: 'app-draft-pmayg-1',
  user_id: 'u-1',
  scheme_id: 'scheme-pmay-g-01',
  scheme_code: 'PMAY-G',
  scheme_name: 'Pradhan Mantri Awaas Yojana - Gramin',
  official_url: 'https://pmayg.nic.in/',
  lifecycle_state: 'validation_failed',
  form_data: {
    applicant_name: 'Ramesh Kumar',
    land_availability: 'Landless / Assistance Required',
    mgnrega_wage_convergence: 'No',
  },
  validation_result: {
    passed: false,
    overall_percentage: 82,
    errors: [{ field: 'documents', message: 'Verification pending for Aadhaar Card.' }],
    warnings: [],
    breakdown: {
      profile: {
        complete: true,
        percentage: 100,
        filled_count: 4,
        total_count: 4,
        missing_fields: [],
        missing_labels: [],
      },
      form: {
        complete: true,
        percentage: 100,
        filled_mandatory: 6,
        total_mandatory: 6,
        missing_fields: [],
        invalid_fields: [],
      },
      documents: {
        complete: false,
        percentage: 50,
        applicable_mandatory: 2,
        verified: 1,
        reviewed: 0,
        awaiting_review: 1,
        rejected: 0,
        missing: 0,
        waived: 2,
        items: [
          {
            document_type: 'aadhaar',
            title: 'Aadhaar Card',
            is_mandatory: true,
            applicable: true,
            status: 'awaiting_citizen_review',
            status_label: 'Awaiting Citizen Review',
          },
          {
            document_type: 'bank_passbook',
            title: 'Bank Account Passbook',
            is_mandatory: true,
            applicable: true,
            status: 'verified',
            status_label: 'Verified',
          },
          {
            document_type: 'land_possession',
            title: 'Homestead Land / Allotment Proof',
            is_mandatory: true,
            applicable: false,
            status: 'waived_not_applicable',
            status_label: 'Waived (Landless / Assistance)',
          },
          {
            document_type: 'job_card',
            title: 'MGNREGA Job Card',
            is_mandatory: false,
            applicable: false,
            status: 'waived_not_applicable',
            status_label: 'Not Selected for Convergence',
          },
        ],
      },
    },
  },
  created_at: '2026-11-12T00:00:00Z',
  updated_at: '2026-11-12T00:00:00Z',
};

describe('Phase 5 Document Integrity & Application Readiness UI', () => {
  it('renders honest lifecycle badges in DocumentsPage and never auto-labels unreviewed uploads as Verified', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <ApiModeProvider>
          <LanguageProvider initialLanguage="en">
            <AuthProvider>
              <DocumentsPage initialDocuments={sampleDocs} />
            </AuthProvider>
          </LanguageProvider>
        </ApiModeProvider>
      </MemoryRouter>
    );

    expect(html).toContain('Awaiting Citizen Review');
    expect(html).toContain('Reviewed (Pending Verification)');
    expect(html).toContain('Rejected');
    expect(html).toContain('0 verified');
    expect(html).toContain('2 awaiting review/verification');
    expect(html).toContain('1 rejected');
    expect(html).toContain('Certificate expired (expiry date 2024-03-31 is in the past).');
  });

  it('renders DocumentsPage cleanly in Hindi and Marathi without dual-language parenthetical mashups', () => {
    const hiHtml = renderToStaticMarkup(
      <MemoryRouter>
        <ApiModeProvider>
          <LanguageProvider initialLanguage="hi">
            <AuthProvider>
              <DocumentsPage initialDocuments={sampleDocs} />
            </AuthProvider>
          </LanguageProvider>
        </ApiModeProvider>
      </MemoryRouter>
    );
    expect(hiHtml).toContain('नागरिक समीक्षा लंबित');
    expect(hiHtml).toContain('समीक्षित (सत्यापन शेष)');
    expect(hiHtml).not.toContain('Awaiting Citizen Review');

    const mrHtml = renderToStaticMarkup(
      <MemoryRouter>
        <ApiModeProvider>
          <LanguageProvider initialLanguage="mr">
            <AuthProvider>
              <DocumentsPage initialDocuments={sampleDocs} />
            </AuthProvider>
          </LanguageProvider>
        </ApiModeProvider>
      </MemoryRouter>
    );
    expect(mrHtml).toContain('नागरिक तपासणी प्रलंबित');
    expect(mrHtml).toContain('तपासलेले (पडताळणी बाकी)');
    expect(mrHtml).not.toContain('Awaiting Citizen Review');
  });

  it('renders 3-pillar Readiness Breakdown and waived document statuses on ApplicationsPage in en, hi, mr', () => {
    const enHtml = renderToStaticMarkup(
      <MemoryRouter>
        <ApiModeProvider>
          <LanguageProvider initialLanguage="en">
            <AuthProvider>
              <ApplicationsPage initialApplications={[samplePmaygDraft]} />
            </AuthProvider>
          </LanguageProvider>
        </ApiModeProvider>
      </MemoryRouter>
    );

    expect(enHtml).toContain('82% Ready');
    expect(enHtml).toContain('Profile');
    expect(enHtml).toContain('Application Fields');
    expect(enHtml).toContain('Verified Docs');
    expect(enHtml).toContain('Waived (Landless / Assistance)');
    expect(enHtml).toContain('Assess Readiness');

    const hiHtml = renderToStaticMarkup(
      <MemoryRouter>
        <ApiModeProvider>
          <LanguageProvider initialLanguage="hi">
            <AuthProvider>
              <ApplicationsPage initialApplications={[samplePmaygDraft]} />
            </AuthProvider>
          </LanguageProvider>
        </ApiModeProvider>
      </MemoryRouter>
    );
    expect(hiHtml).toContain('सत्यापित दस्तावेज़');
    expect(hiHtml).toContain('तत्परता जांचें');
    expect(hiHtml).not.toContain('Verified Docs');

    const mrHtml = renderToStaticMarkup(
      <MemoryRouter>
        <ApiModeProvider>
          <LanguageProvider initialLanguage="mr">
            <AuthProvider>
              <ApplicationsPage initialApplications={[samplePmaygDraft]} />
            </AuthProvider>
          </LanguageProvider>
        </ApiModeProvider>
      </MemoryRouter>
    );
    expect(mrHtml).toContain('पडताळलेली कागदपत्रे');
    expect(mrHtml).toContain('सज्जता तपासा');
    expect(mrHtml).not.toContain('Verified Docs');
  });
});
