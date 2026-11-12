import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { SchemeDetailsPage } from '../SchemeDetailsPage';
import { LanguageProvider } from '@/context/LanguageContext';
import { AuthProvider } from '@/context/AuthContext';
import { ApiModeProvider } from '@/context/ApiModeContext';
import { Scheme, DocumentRequirement } from '@/types';

const mockScheme: Scheme = {
  id: '80ad3246-dd26-4108-a530-1bee5eab72e3',
  scheme_code: 'PM-KISAN',
  name: 'Pradhan Mantri Kisan Samman Nidhi',
  short_title: 'PM-KISAN',
  description: 'A Central Sector Scheme to provide income support to all landholding farmer families across India.',
  ministry: 'Ministry of Agriculture and Farmers Welfare',
  department: 'Department of Agriculture and Farmers Welfare',
  category: 'agriculture',
  geographic_scope: 'central',
  target_beneficiaries: ['Small and marginal farmer families', 'Landholding farmers'],
  benefits: 'Financial benefit of Rs. 6,000 per year payable in three equal instalments of Rs. 2,000 every four months directly into Aadhaar-seeded bank accounts through DBT.',
  official_url: 'https://pmkisan.gov.in/',
  application_url: 'https://pmkisan.gov.in/registrationform.aspx',
  source_url: 'https://pmkisan.gov.in/Documents/OperationalGuidelines.pdf',
  scheme_status: 'active',
  last_retrieved_at: '2026-11-10T10:00:00Z',
  last_verified_at: '2026-11-10T12:00:00Z',
  source_evidence: [
    {
      claim: 'benefits',
      statement: 'Rs. 6,000 per year transferred in three equal instalments via DBT into Aadhaar-seeded accounts.',
      source_url: 'https://pmkisan.gov.in/Documents/OperationalGuidelines.pdf',
      issuing_authority: 'Ministry of Agriculture and Farmers Welfare',
      citation: 'Clause 2.1',
      verification_status: 'verified',
    },
  ],
};

const mockDocs: DocumentRequirement[] = [
  {
    id: 'doc-pmkisan-01',
    document_type: 'aadhaar_card',
    title: 'Aadhaar Card',
    is_mandatory: true,
    issuing_authority: 'UIDAI',
    guidance: 'Link Aadhaar with active bank account for DBT payment.',
  },
  {
    id: 'doc-pmkisan-02',
    document_type: 'land_records',
    title: '7/12 Land Record Extract',
    is_mandatory: true,
    issuing_authority: 'State Revenue Department',
    guidance: 'Demonstrating cultivable land ownership title.',
  },
];

describe('SchemeDetailsPage Tab System', () => {
  it('renders all 6 scheme detail tabs: Overview, Benefits, Eligibility, Documents, Application, Sources', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={['/schemes/80ad3246-dd26-4108-a530-1bee5eab72e3']}>
        <ApiModeProvider>
          <LanguageProvider>
            <AuthProvider>
              <Routes>
                <Route
                  path="/schemes/:id"
                  element={
                    <SchemeDetailsPage
                      initialScheme={mockScheme}
                      initialDocuments={mockDocs}
                    />
                  }
                />
              </Routes>
            </AuthProvider>
          </LanguageProvider>
        </ApiModeProvider>
      </MemoryRouter>
    );

    // Tab buttons exist
    expect(html).toContain('Overview');
    expect(html).toContain('Benefits');
    expect(html).toContain('Eligibility');
    expect(html).toContain('Documents');
    expect(html).toContain('Application');
    expect(html).toContain('Sources');
    expect(html).toContain('Pradhan Mantri Kisan Samman Nidhi');
    expect(html).toContain('Central Sector');
  });

  it('renders Benefits content when ?tab=benefits is passed in URL', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={['/schemes/80ad3246-dd26-4108-a530-1bee5eab72e3?tab=benefits']}>
        <ApiModeProvider>
          <LanguageProvider>
            <AuthProvider>
              <Routes>
                <Route
                  path="/schemes/:id"
                  element={
                    <SchemeDetailsPage
                      initialScheme={mockScheme}
                      initialDocuments={mockDocs}
                    />
                  }
                />
              </Routes>
            </AuthProvider>
          </LanguageProvider>
        </ApiModeProvider>
      </MemoryRouter>
    );

    expect(html).toContain('Direct Benefit Transfer');
    expect(html).toContain('Financial benefit of Rs. 6,000 per year');
    expect(html).toContain('Aadhaar-seeded bank accounts');
  });

  it('renders Required Documents checklist tab content when ?tab=documents is passed', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={['/schemes/80ad3246-dd26-4108-a530-1bee5eab72e3?tab=documents']}>
        <ApiModeProvider>
          <LanguageProvider>
            <AuthProvider>
              <Routes>
                <Route
                  path="/schemes/:id"
                  element={
                    <SchemeDetailsPage
                      initialScheme={mockScheme}
                      initialDocuments={mockDocs}
                    />
                  }
                />
              </Routes>
            </AuthProvider>
          </LanguageProvider>
        </ApiModeProvider>
      </MemoryRouter>
    );

    expect(html).toContain('official documents registered for this scheme');
    expect(html).toContain('Aadhaar Card');
    expect(html).toContain('7/12 Land Record Extract');
    expect(html).toContain('UIDAI');
  });

  it('renders Official Application Process steps when ?tab=application is passed', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={['/schemes/80ad3246-dd26-4108-a530-1bee5eab72e3?tab=application']}>
        <ApiModeProvider>
          <LanguageProvider>
            <AuthProvider>
              <Routes>
                <Route
                  path="/schemes/:id"
                  element={
                    <SchemeDetailsPage
                      initialScheme={mockScheme}
                      initialDocuments={mockDocs}
                    />
                  }
                />
              </Routes>
            </AuthProvider>
          </LanguageProvider>
        </ApiModeProvider>
      </MemoryRouter>
    );

    expect(html).toContain('https://pmkisan.gov.in/registrationform.aspx');
    expect(html).toContain('ई-केवाईसी');
    expect(html).toContain('DBT');
  });

  it('renders Official Government Sources & Evidence when ?tab=sources is passed', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={['/schemes/80ad3246-dd26-4108-a530-1bee5eab72e3?tab=sources']}>
        <ApiModeProvider>
          <LanguageProvider>
            <AuthProvider>
              <Routes>
                <Route
                  path="/schemes/:id"
                  element={
                    <SchemeDetailsPage
                      initialScheme={mockScheme}
                      initialDocuments={mockDocs}
                    />
                  }
                />
              </Routes>
            </AuthProvider>
          </LanguageProvider>
        </ApiModeProvider>
      </MemoryRouter>
    );

    expect(html).toContain('https://pmkisan.gov.in/Documents/OperationalGuidelines.pdf');
    expect(html).toContain('Clause 2.1');
    expect(html).toContain('verified');
  });

  it('renders structured APY benefits including 5 pension slabs, contribution matrix, spouse entitlement, nominee corpus, and co-contribution clarification when ?tab=benefits is viewed for APY', () => {
    const mockApyScheme: Scheme = {
      id: '12e075b0-cb82-4535-b9aa-22a57fa44d5a',
      scheme_code: 'APY',
      name: 'Atal Pension Yojana',
      short_title: 'APY',
      description: 'Government-backed periodic pension scheme targeted at workers in the unorganised sector.',
      ministry: 'Ministry of Finance',
      department: 'Department of Financial Services',
      category: 'social_security',
      geographic_scope: 'central',
      target_beneficiaries: ['Indian citizens aged 18 to 40 years', 'Non-taxpayers'],
      benefits: 'Guaranteed minimum monthly pension of Rs. 1,000, Rs. 2,000, Rs. 3,000, Rs. 4,000, or Rs. 5,000 to the subscriber upon reaching 60 years of age.',
      official_url: 'https://www.pfrda.org.in/',
      application_url: 'https://enps.nsdl.com/eNPS/ApySubRegistration.html',
      source_url: 'https://www.pfrda.org.in/',
      scheme_status: 'active',
      last_retrieved_at: '2026-11-10T10:00:00Z',
      last_verified_at: '2026-11-10T12:00:00Z',
    };

    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={['/schemes/12e075b0-cb82-4535-b9aa-22a57fa44d5a?tab=benefits']}>
        <ApiModeProvider>
          <LanguageProvider>
            <AuthProvider>
              <Routes>
                <Route
                  path="/schemes/:id"
                  element={
                    <SchemeDetailsPage
                      initialScheme={mockApyScheme}
                      initialDocuments={[]}
                    />
                  }
                />
              </Routes>
            </AuthProvider>
          </LanguageProvider>
        </ApiModeProvider>
      </MemoryRouter>
    );

    // 1. Guaranteed pension slabs
    expect(html).toContain('₹1,000');
    expect(html).toContain('₹5,000');
    expect(html).toContain('₹1.70 Lakh');
    expect(html).toContain('₹8.50 Lakh');

    // 2. Tripartite protection (Subscriber, Spouse, Nominee)
    expect(html).toContain('Subscriber');
    expect(html).toContain('Spouse');
    expect(html).toContain('Nominee');

    // 3. Contribution schedule
    expect(html).toContain('18 yrs');
    expect(html).toContain('40 yrs');
    expect(html).toContain('₹42');
    expect(html).toContain('₹1,454');

    // 4. Government co-contribution & sovereign guarantee clarification
    expect(html).toContain('Co-Contribution');
    expect(html).toContain('Sovereign');

    // 5. Income tax exclusion rule
    expect(html).toContain('1 Oct 2022');
  });
});
