import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { ApplicationsPage } from '../ApplicationsPage';
import { HandoffConfirmationWidget } from '@/components/chat/HandoffConfirmationWidget';
import { LanguageProvider } from '@/context/LanguageContext';
import { AuthProvider } from '@/context/AuthContext';
import { ApiModeProvider } from '@/context/ApiModeContext';
import { ApplicationDraft } from '@/types';

const confirmedManualDraft: ApplicationDraft = {
  id: 'app-p7-1',
  user_id: 'u-1',
  scheme_id: 'PM-KISAN',
  scheme_code: 'PM-KISAN',
  scheme_name: 'Pradhan Mantri Kisan Samman Nidhi',
  official_url: 'https://pmkisan.gov.in/',
  lifecycle_state: 'confirmed',
  version: 2,
  confirmed_version: 2,
  confirmed_at: '2026-11-12T01:00:00Z',
  integration_supported: false,
  form_data: { applicant_name: 'Ramesh Kumar', village: 'Shivpur' },
  review_summary: {
    application_id: 'app-p7-1',
    scheme_code: 'PM-KISAN',
    scheme_name: 'Pradhan Mantri Kisan Samman Nidhi',
    schema_available: true,
    form_supported: true,
    lifecycle_state: 'confirmed',
    version: 2,
    data_hash: 'hash123456',
    sections: [
      {
        section_id: 'p',
        title: 'Personal Details',
        fields: [
          {
            name: 'applicant_name',
            label: 'Farmer Full Name',
            type: 'text',
            value: 'Ramesh Kumar',
            required: true,
            source_badge: 'Verified Document',
          },
          {
            name: 'village',
            label: 'Village',
            type: 'text',
            value: 'Shivpur',
            required: true,
            source_badge: 'Citizen Entered',
          },
        ],
      },
    ],
  },
  created_at: '2026-11-12T00:00:00Z',
  updated_at: '2026-11-12T01:00:00Z',
};

const invalidatedAndFailedDrafts: ApplicationDraft[] = [
  {
    ...confirmedManualDraft,
    id: 'app-p7-invalidated',
    lifecycle_state: 'draft',
    version: 3,
    confirmed_at: null,
    confirmed_version: null,
    confirmation_invalidated_at: '2026-11-12T02:00:00Z',
  },
  {
    ...confirmedManualDraft,
    id: 'app-p7-uncertain',
    lifecycle_state: 'submission_unknown',
    submission_outcome: 'submission_unknown',
    blind_retry_blocked: true,
  },
  {
    ...confirmedManualDraft,
    id: 'app-pm-kisan-e472b7',
    lifecycle_state: 'submitted',
    submission_source: 'portal_handoff',
    reference_number: 'SAATHI/READY/2026/4359A6',
    legacy_synthetic_submission: true,
    is_verified_government_submission: false,
    external_reference_id: null,
  },
];

describe('Phase 7 ApplicationsPage Review, Confirmation & Safe Submission UI', () => {
  it('displays confirmed manual-portal banner, provenance tags, and version cleanly across en/hi/mr', () => {
    const enHtml = renderToStaticMarkup(
      <MemoryRouter>
        <ApiModeProvider>
          <LanguageProvider initialLanguage="en">
            <AuthProvider>
              <ApplicationsPage initialApplications={[confirmedManualDraft]} />
            </AuthProvider>
          </LanguageProvider>
        </ApiModeProvider>
      </MemoryRouter>
    );
    expect(enHtml).toContain('CONFIRMED');
    expect(enHtml).toContain('v2');
    expect(enHtml).toContain('Verified Document');
    expect(enHtml).toContain('Citizen Entered');
    expect(enHtml).toContain('Portal Submission Guidance');

    const hiHtml = renderToStaticMarkup(
      <MemoryRouter>
        <ApiModeProvider>
          <LanguageProvider initialLanguage="hi">
            <AuthProvider>
              <ApplicationsPage initialApplications={[confirmedManualDraft]} />
            </AuthProvider>
          </LanguageProvider>
        </ApiModeProvider>
      </MemoryRouter>
    );
    expect(hiHtml).toContain('आधिकारिक पोर्टल निर्देश');
    expect(hiHtml).not.toContain('Portal Submission Guidance');

    const mrHtml = renderToStaticMarkup(
      <MemoryRouter>
        <ApiModeProvider>
          <LanguageProvider initialLanguage="mr">
            <AuthProvider>
              <ApplicationsPage initialApplications={[confirmedManualDraft]} />
            </AuthProvider>
          </LanguageProvider>
        </ApiModeProvider>
      </MemoryRouter>
    );
    expect(mrHtml).toContain('पोर्टल सादरीकरण मार्गदर्शन');
    expect(mrHtml).not.toContain('Portal Submission Guidance');
  });

  it('displays confirmation-invalidated warning, distinct submission_unknown banner, and quarantines synthetic SAATHI refs', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <ApiModeProvider>
          <LanguageProvider initialLanguage="en">
            <AuthProvider>
              <ApplicationsPage initialApplications={invalidatedAndFailedDrafts} />
            </AuthProvider>
          </LanguageProvider>
        </ApiModeProvider>
      </MemoryRouter>
    );
    expect(html).toContain('changed after your previous confirmation');
    expect(html).toContain('SUBMISSION UNKNOWN');
    expect(html).toContain('Reconcile Submission Status');
    expect(html).toContain('UNVERIFIED LEGACY PACKET');
    expect(html).not.toContain('SAATHI/READY/2026/4359A6');
    expect(html).not.toContain('Submitted Ref:');

    const widgetHtml = renderToStaticMarkup(
      <MemoryRouter>
        <HandoffConfirmationWidget
          language="en"
          data={{
            requires_confirmation: false,
            confirmed: true,
            submitted: false,
            lifecycle_state: 'submission_unknown',
            submission_status: 'submission_unknown',
            scheme_code: 'PM-KISAN',
            official_portal_url: 'https://pmkisan.gov.in',
          }}
        />
      </MemoryRouter>
    );
    expect(widgetHtml).toContain('Submission Outcome Unknown');
    expect(widgetHtml).toContain('Submission Unknown');
    expect(widgetHtml).not.toContain('Manual Official Portal Next Steps');
  });

  it('renders Step 5 portal_submitted records cleanly across en/hi/mr and Mode B return-reference form in Chat widget', () => {
    const portalSubmittedDraft: ApplicationDraft = {
      ...confirmedManualDraft,
      id: 'app-e2e-pmk-99',
      lifecycle_state: 'portal_submitted',
      submission_source: 'portal_assisted',
      submission_method: 'portal_assisted',
      official_reference_number: 'PMK-MH-2026-998812',
      reference_source: 'citizen_reported_portal_reference',
      submission_date: '2026-11-12T06:30:00Z',
      portal_url: 'https://pmkisan.gov.in/registrationform.aspx',
      tracking_url: 'https://pmkisan.gov.in/BeneficiaryStatus_New.aspx',
      is_verified_government_submission: false,
      portal_integration: {
        scheme_code: 'PM-KISAN',
        submission_method: 'portal_assisted',
        submission_method_label: 'Mode B: Portal-Assisted Guided Submission',
        official_application_url: 'https://pmkisan.gov.in/registrationform.aspx',
        tracking_url: 'https://pmkisan.gov.in/BeneficiaryStatus_New.aspx',
      },
      application_record: {
        citizen_id: 'u-1',
        scheme_id: 'scheme-1',
        application_id: 'app-e2e-pmk-99',
        official_reference_number: 'PMK-MH-2026-998812',
        submission_date: '2026-11-12T06:30:00Z',
        portal_url: 'https://pmkisan.gov.in/registrationform.aspx',
        tracking_url: 'https://pmkisan.gov.in/BeneficiaryStatus_New.aspx',
        application_status: 'portal_submitted',
        submission_method: 'portal_assisted',
      },
    };

    const enHtml = renderToStaticMarkup(
      <MemoryRouter>
        <ApiModeProvider>
          <LanguageProvider initialLanguage="en">
            <AuthProvider>
              <ApplicationsPage initialApplications={[portalSubmittedDraft, confirmedManualDraft]} />
            </AuthProvider>
          </LanguageProvider>
        </ApiModeProvider>
      </MemoryRouter>
    );
    expect(enHtml).toContain('PORTAL SUBMITTED');
    expect(enHtml).toContain('PMK-MH-2026-998812');
    expect(enHtml).toContain('app-e2e-pmk-99');
    expect(enHtml).toContain('Status Tracking URL');
    expect(enHtml).toContain('Record Official Portal Reference');

    const hiHtml = renderToStaticMarkup(
      <MemoryRouter>
        <ApiModeProvider>
          <LanguageProvider initialLanguage="hi">
            <AuthProvider>
              <ApplicationsPage initialApplications={[portalSubmittedDraft, confirmedManualDraft]} />
            </AuthProvider>
          </LanguageProvider>
        </ApiModeProvider>
      </MemoryRouter>
    );
    expect(hiHtml).toContain('पोर्टल पर जमा');
    expect(hiHtml).toContain('पोर्टल संदर्भ संख्या दर्ज करें');
    expect(hiHtml).not.toContain('PORTAL SUBMITTED');

    const mrHtml = renderToStaticMarkup(
      <MemoryRouter>
        <ApiModeProvider>
          <LanguageProvider initialLanguage="mr">
            <AuthProvider>
              <ApplicationsPage initialApplications={[portalSubmittedDraft, confirmedManualDraft]} />
            </AuthProvider>
          </LanguageProvider>
        </ApiModeProvider>
      </MemoryRouter>
    );
    expect(mrHtml).toContain('पोर्टलवर सादर');
    expect(mrHtml).toContain('अधिकृत पोर्टल संदर्भ नोंदवा');
    expect(mrHtml).not.toContain('PORTAL SUBMITTED');

    // Mode B HandoffConfirmationWidget shows official steps, OTP/CAPTCHA notice, and citizen return reference input
    const modeBWidgetHtml = renderToStaticMarkup(
      <MemoryRouter>
        <HandoffConfirmationWidget
          language="en"
          onRecordPortalReference={() => {}}
          data={{
            requires_confirmation: false,
            confirmed: true,
            submitted: false,
            application_id: 'app-e2e-pmk-99',
            scheme_code: 'PM-KISAN',
            lifecycle_state: 'confirmed',
            official_portal_url: 'https://pmkisan.gov.in/registrationform.aspx',
            tracking_url: 'https://pmkisan.gov.in/BeneficiaryStatus_New.aspx',
            portal_integration: {
              scheme_code: 'PM-KISAN',
              submission_method: 'portal_assisted',
              submission_method_label: 'Mode B: Portal-Assisted Guided Submission',
              official_application_url: 'https://pmkisan.gov.in/registrationform.aspx',
              tracking_url: 'https://pmkisan.gov.in/BeneficiaryStatus_New.aspx',
              security_controls_notice: 'Official login, OTP, and CAPTCHA must be completed directly by you.',
              official_instructions: {
                online_steps: ['Open pmkisan.gov.in', 'Complete OTP & submit'],
              },
            },
          }}
        />
      </MemoryRouter>
    );
    expect(modeBWidgetHtml).toContain('Mode B: Portal-Assisted Guided Submission');
    expect(modeBWidgetHtml).toContain('Save Portal Reference');
    expect(modeBWidgetHtml).toContain('Track Application Status');
    expect(modeBWidgetHtml).toContain('Official login, OTP, and CAPTCHA');
  });
});
