import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import {
  InteractiveChecklistWidget,
  ChecklistPayload,
} from '../InteractiveChecklistWidget';

describe('InteractiveChecklistWidget Component', () => {
  const samplePayload: ChecklistPayload = {
    scheme_code: 'PM-KISAN',
    scheme_name: 'Pradhan Mantri Kisan Samman Nidhi',
    total_documents: 4,
    mandatory_total: 3,
    mandatory_ready: 2,
    readiness_percentage: 66.7,
    items: [
      {
        document_type: 'aadhaar_card',
        title: 'Aadhaar Card',
        is_mandatory: true,
        status: 'verified',
        sourcing: {
          issuing_authority: 'UIDAI',
          where_to_obtain: 'Aadhaar Seva Kendra / UIDAI Portal',
          verified_fee: 'Free for mandatory updates',
          processing_time_sla: 'Immediate / 5-15 days',
          portal_url: 'https://myaadhaar.uidai.gov.in',
        },
      },
      {
        document_type: 'bank_passbook',
        title: 'Bank Passbook',
        is_mandatory: true,
        status: 'uploaded',
      },
      {
        document_type: 'land_records',
        title: '7/12 Land Record Extract',
        is_mandatory: true,
        status: 'missing',
        sourcing: {
          issuing_authority: 'Revenue Department Maharashtra',
          where_to_obtain: 'Mahabhulekh / Aaple Sarkar / Talathi Office',
          verified_fee: '₹15 (Digitally Signed Extract)',
          processing_time_sla: 'Instant online / 3 days offline',
          portal_url: 'https://bhulekh.mahabhumi.gov.in',
        },
      },
      {
        document_type: 'caste_certificate',
        title: 'Caste Certificate',
        is_mandatory: false,
        status: 'expired',
      },
      {
        document_type: 'income_certificate',
        title: 'Income Certificate',
        is_mandatory: false,
        status: 'verification_pending',
      },
    ],
  };

  it('renders scheme name, document count, and readiness percentage accurately', () => {
    const html = renderToStaticMarkup(
      <InteractiveChecklistWidget data={samplePayload} />
    );

    expect(html).toContain('Pradhan Mantri Kisan Samman Nidhi');
    expect(html).toContain('PM-KISAN');
    expect(html).toContain('67% Ready');
    expect(html).toContain('2 of 3 mandatory documents ready');
  });

  it('accurately displays all 5 document statuses without fabricating verification', () => {
    const html = renderToStaticMarkup(
      <InteractiveChecklistWidget data={samplePayload} />
    );

    // 1. Verified in Vault
    expect(html).toContain('● Verified in Vault');
    // 2. In Vault / Uploaded (not marked as verified)
    expect(html).toContain('● In Vault / Uploaded');
    // 3. Missing / Required
    expect(html).toContain('● Missing / Required');
    // 4. Expired
    expect(html).toContain('● Expired');
    // 5. Verification Pending
    expect(html).toContain('● Verification Pending');
  });

  it('correctly labels mandatory vs optional documents without dual-language mashups', () => {
    // English rendering
    const htmlEn = renderToStaticMarkup(
      <InteractiveChecklistWidget data={samplePayload} lang="en" />
    );
    expect(htmlEn).toContain('Mandatory');
    expect(htmlEn).toContain('Optional');
    expect(htmlEn).not.toContain('अनिवार्य (Mandatory)');

    // Marathi rendering
    const htmlMr = renderToStaticMarkup(
      <InteractiveChecklistWidget data={samplePayload} lang="mr" />
    );
    expect(htmlMr).toContain('अनिवार्य');
    expect(htmlMr).toContain('ऐच्छिक');
    expect(htmlMr).not.toContain('अनिवार्य (Mandatory)');
  });

  it('renders pre-fill application draft button with clean action text', () => {
    const htmlEn = renderToStaticMarkup(
      <InteractiveChecklistWidget
        data={samplePayload}
        lang="en"
        onPrefillClick={() => {}}
      />
    );
    expect(htmlEn).toContain('Pre-fill Application Draft');

    const htmlMr = renderToStaticMarkup(
      <InteractiveChecklistWidget
        data={samplePayload}
        lang="mr"
        onPrefillClick={() => {}}
      />
    );
    expect(htmlMr).toContain('अर्जाचा मसुदा भरा');
  });

  it('renders sourcing info button for items with verified sourcing metadata', () => {
    const html = renderToStaticMarkup(
      <InteractiveChecklistWidget data={samplePayload} />
    );

    expect(html).toContain('Sourcing Info');
  });
});
