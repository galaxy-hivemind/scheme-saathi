import { describe, it, expect, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { PreFilledFormWidget, FormDraftPayload } from '../PreFilledFormWidget';
import { HandoffConfirmationWidget, ConfirmationPayload } from '../HandoffConfirmationWidget';

const pmKisanDraftPayload: FormDraftPayload = {
  scheme_code: 'PM-KISAN',
  scheme_title: 'Pradhan Mantri Kisan Samman Nidhi Application Form',
  form_supported: true,
  schema_available: true,
  prefill_percentage: 42.9,
  total_fields: 15,
  total_mandatory_fields: 14,
  filled_mandatory_fields: 6,
  sections: [
    {
      section_id: 'personal_info',
      title: 'Applicant Personal Details',
      fields: [
        {
          name: 'applicant_name',
          label: 'Farmer Full Name',
          type: 'text',
          required: true,
          value: 'Ramesh Kumar',
          is_prefilled: true,
          source_label: 'Citizen Profile',
        },
        {
          name: 'gender',
          label: 'Gender',
          type: 'select',
          required: true,
          value: 'MALE',
          is_prefilled: true,
          source_label: 'Citizen Profile',
          options: ['MALE', 'FEMALE', 'OTHER'] as any,
        },
        {
          name: 'aadhaar_number',
          label: '12-Digit Aadhaar Number',
          type: 'text',
          required: true,
          value: '',
          is_prefilled: false,
          requires_input: true,
          conflict: {
            field: 'aadhaar_number',
            label: '12-Digit Aadhaar Number',
            message: "Conflicting values detected for '12-Digit Aadhaar Number'.",
            candidates: [
              { value: '234567890123', source_tier: 'verified_document', source_label: 'Verified Document' },
              { value: '726726378736', source_tier: 'citizen_profile', source_label: 'Citizen Profile' },
            ],
          },
        },
        {
          name: 'khasra_khatauni_no',
          label: 'Survey / Khasra / Khatauni Number',
          type: 'text',
          required: true,
          value: '',
          is_prefilled: false,
          requires_input: true,
          unverified_ocr_hint: {
            suggested_value: '104/2',
            source_tier: 'extracted_ocr_unverified',
            source_label: 'Unverified OCR',
          },
        },
      ],
    },
  ],
};

describe('Phase 6 PreFilledFormWidget & HandoffConfirmationWidget', () => {
  it('renders string[] select options, provenance badges, conflict candidates, and unverified OCR hints cleanly', () => {
    const html = renderToStaticMarkup(
      <PreFilledFormWidget
        data={pmKisanDraftPayload}
        language="en"
        onSaveDraft={vi.fn()}
        onConfirmSubmit={vi.fn()}
      />
    );

    expect(html).toContain('Pre-Filled Application Draft');
    expect(html).toContain('42.9% Pre-filled');
    expect(html).toContain('Citizen Profile');
    expect(html).toContain('MALE');
    expect(html).toContain('Conflicting values detected');
    expect(html).toContain('Verified Document: 234567890123');
    expect(html).toContain('Unverified OCR in Vault (104/2)');
    expect(html).toContain('Citizen Input Needed');
  });

  it('renders unavailable-schema state cleanly for APY in en, hi, and mr without fake fallback inputs', () => {
    const apyUnavailable: FormDraftPayload = {
      scheme_code: 'APY',
      form_supported: false,
      schema_available: false,
      official_portal: 'https://enps.nsdl.com/eNPS/ApySubRegistration.html',
    };

    const enHtml = renderToStaticMarkup(<PreFilledFormWidget data={apyUnavailable} language="en" />);
    expect(enHtml).toContain('Structured Application Schema Unavailable');
    expect(enHtml).toContain('Apply on Official Portal');
    expect(enHtml).toContain('https://enps.nsdl.com/eNPS/ApySubRegistration.html');
    expect(enHtml).not.toContain('<input');

    const hiHtml = renderToStaticMarkup(<PreFilledFormWidget data={apyUnavailable} language="hi" />);
    expect(hiHtml).toContain('आवेदन फ़ॉर्म स्कीमा उपलब्ध नहीं है');
    expect(hiHtml).not.toContain('Structured Application Schema Unavailable');

    const mrHtml = renderToStaticMarkup(<PreFilledFormWidget data={apyUnavailable} language="mr" />);
    expect(mrHtml).toContain('अर्ज फॉर्म नमुना उपलब्ध नाही');
    expect(mrHtml).not.toContain('Structured Application Schema Unavailable');
  });

  it('renders HandoffConfirmationWidget in pure en, hi, and mr across Stage A and Stage B', () => {
    const stageA: ConfirmationPayload = {
      requires_confirmation: true,
      scheme_code: 'PM-KISAN',
      version: 2,
      data_hash: 'abcdef1234567890',
      manual_portal_required: true,
      review_summary: {
        application_id: 'app-1',
        scheme_code: 'PM-KISAN',
        scheme_name: 'PM-KISAN',
        schema_available: true,
        form_supported: true,
        lifecycle_state: 'awaiting_confirmation',
        version: 2,
        data_hash: 'abcdef1234567890',
        sections: [
          {
            section_id: 'p1',
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
            ],
          },
        ],
      },
    };
    const aHtmlEn = renderToStaticMarkup(
      <MemoryRouter>
        <HandoffConfirmationWidget data={stageA} language="en" onConfirm={vi.fn()} />
      </MemoryRouter>
    );
    expect(aHtmlEn).toContain('Complete Application Review');
    expect(aHtmlEn).toContain('v2');
    expect(aHtmlEn).toContain('Ramesh Kumar');
    expect(aHtmlEn).toContain('Verified Document');
    expect(aHtmlEn).not.toContain('अंतिम संमती');

    const stageBManualMr: ConfirmationPayload = {
      requires_confirmation: false,
      confirmed: true,
      confirmed_version: 2,
      submitted: false,
      manual_portal_required: true,
      external_reference_id: null,
      official_portal_url: 'https://pmkisan.gov.in',
    };
    const bHtmlMr = renderToStaticMarkup(
      <MemoryRouter>
        <HandoffConfirmationWidget data={stageBManualMr} language="mr" />
      </MemoryRouter>
    );
    expect(bHtmlMr).toContain('संमती नोंदवली (v2)');
    expect(bHtmlMr).toContain('अधिकृत शासकीय पोर्टल उघडा');
    expect(bHtmlMr).not.toContain('Open Official Portal');
    expect(bHtmlMr).not.toContain('SAATHI/');

    const stageBSubmittedEn: ConfirmationPayload = {
      requires_confirmation: false,
      confirmed: true,
      confirmed_version: 2,
      submitted: true,
      external_reference_id: 'GOV-PMKISAN-2026-9988',
      official_portal_url: 'https://pmkisan.gov.in',
    };
    const bHtmlSub = renderToStaticMarkup(
      <MemoryRouter>
        <HandoffConfirmationWidget data={stageBSubmittedEn} language="en" />
      </MemoryRouter>
    );
    expect(bHtmlSub).toContain('GOV-PMKISAN-2026-9988');
    expect(bHtmlSub).toContain('Submitted via Official Portal Integration');
  });
});
