import { describe, it, expect } from 'vitest';
import { cleanMarkdownForSpeech, splitTextIntoSpeechChunks } from '../useVoiceAssistant';

describe('useVoiceAssistant - Speech Chunking & Markdown Cleaning', () => {
  it('cleanMarkdownForSpeech cleans markdown formatting, URLs, and emojis while preserving content', () => {
    const raw = (
      '**Pradhan Mantri Kisan Samman Nidhi (PM-KISAN):**\n\n' +
      '💰 **Benefits:** Financial benefit of ₹6,000 per year transferred in 3 equal instalments.\n' +
      '🌐 **Official Portal:** [https://pmkisan.gov.in/](https://pmkisan.gov.in/)\n' +
      '1. Visit the portal.\n' +
      '2. Complete mandatory e-KYC.'
    );

    const cleaned = cleanMarkdownForSpeech(raw, 'en');
    expect(cleaned).not.toContain('**');
    expect(cleaned).not.toContain('💰');
    expect(cleaned).not.toContain('🌐');
    expect(cleaned).not.toContain('https://pmkisan.gov.in/');
    expect(cleaned).toContain('₹6,000 per year transferred in 3 equal instalments');
    expect(cleaned).toContain('1. Visit the portal');
    expect(cleaned).toContain('2. Complete mandatory e-KYC');
  });

  it('Case 1: handles a short 2-line response cleanly', () => {
    const text = 'Yes, you are eligible for this welfare program. You can submit your application on the official state portal.';
    const chunks = splitTextIntoSpeechChunks(text, 'en');
    expect(chunks.length).toBeGreaterThanOrEqual(1);
    expect(chunks.join(' ')).toContain('Yes, you are eligible for this welfare program');
    expect(chunks.join(' ')).toContain('You can submit your application on the official state portal');
  });

  it('Case 2: handles a 10-15 line response and preserves all paragraphs in order', () => {
    const lines = [
      'Welcome to Scheme Saathi welfare advisory.',
      'We provide verified guidance for Indian citizens.',
      '1. Check your state eligibility status.',
      '2. Gather all required land and income certificates.',
      '3. Visit the designated administrative portal.',
      '4. Complete Aadhaar authentication with mobile OTP.',
      '5. Enter your bank details linked with NPCI mapper.',
      '6. Upload the supporting documents.',
      '7. Submit your form and receive your acknowledgment ID.',
      '8. Track your verification status with local revenue officials.',
      '9. Receive direct benefit transfer upon final approval.',
      'For further inquiries, contact your local Gram Panchayat.'
    ];
    const fullText = lines.join('\n');
    const chunks = splitTextIntoSpeechChunks(fullText, 'en');

    expect(chunks.length).toBeGreaterThanOrEqual(5);
    chunks.forEach((chunk) => {
      expect(chunk.length).toBeLessThanOrEqual(180);
    });
    // Verify first and last line are preserved
    expect(chunks[0]).toContain('Welcome to Scheme Saathi');
    expect(chunks[chunks.length - 1]).toContain('Gram Panchayat');
  });

  it('Case 3: handles a long explanation about KCC with interest rates and subventions', () => {
    const kccText = (
      '**Kisan Credit Card Scheme (KCC):**\n\n' +
      'Revolving agricultural credit facility up to ₹3,00,000 for farmers. ' +
      'The benchmark lending rate is 7% per annum supported by 1.5% institutional subvention from GoI to banks under the Modified Interest Subvention Scheme. ' +
      'Farmers who repay on or before the scheduled due date receive an additional 3% Prompt Repayment Incentive, resulting in an effective net interest rate of 4% per annum. ' +
      'Collateral-free credit is available up to ₹1.60 Lakh.'
    );
    const chunks = splitTextIntoSpeechChunks(kccText, 'en');

    expect(chunks.length).toBeGreaterThan(1);
    const combined = chunks.join(' ');
    expect(combined).toContain('7% per annum');
    expect(combined).toContain('1.5%');
    expect(combined).toContain('3% Prompt Repayment Incentive');
    expect(combined).toContain('4% per annum');
    expect(combined).toContain('₹1.60 Lakh');
  });

  it('Case 4: handles a detailed PM-KISAN eligibility and documents response', () => {
    const pmkisanText = (
      '**PM-KISAN Required Documents and Eligibility:**\n\n' +
      '- **Aadhaar Card** (Mandatory): Required for identity verification and e-KYC.\n' +
      '- **Land Ownership Document** (Mandatory): 7/12 extract or Khatauni showing landholding.\n' +
      '- **Bank Account Passbook** (Mandatory): Aadhaar-seeded bank account for DBT payment.\n' +
      '- **Mobile Number** (Mandatory): Linked to Aadhaar for OTP verification.'
    );
    const chunks = splitTextIntoSpeechChunks(pmkisanText, 'en');
    expect(chunks.length).toBeGreaterThanOrEqual(3);
    const combined = chunks.join(' ');
    expect(combined).toContain('Aadhaar Card');
    expect(combined).toContain('7/12 extract');
    expect(combined).toContain('Bank Account Passbook');
    expect(combined).toContain('Mobile Number');
  });

  it('Case 5: handles Marathi response with Devanagari numerals and grammar', () => {
    const mrText = (
      '**महात्मा ज्योतिराव फुले जन आरोग्य योजना (MPJAY-MH):**\n\n' +
      '१. अधिकृत शासकीय पोर्टलला भेट द्या.\n' +
      '२. नवीन नोंदणी लिंकवर क्लिक करा.\n' +
      '३. तुमचा १२ अंकी आधार क्रमांक आणि मोबाईल नंबर टाका.\n' +
      '४. कुटुंबाचा तपशील व रेशन कार्ड जोडा.\n' +
      '५. अर्ज सबमिट करून पोचपावती जतन करा.'
    );
    const chunks = splitTextIntoSpeechChunks(mrText, 'mr');
    expect(chunks.length).toBeGreaterThanOrEqual(2);
    const combined = chunks.join(' ');
    expect(combined).toContain('शासकीय पोर्टलला भेट द्या');
    expect(combined).toContain('नवीन नोंदणी');
    expect(combined).toContain('आधार क्रमांक');
    expect(combined).toContain('रेशन कार्ड');
  });

  it('Case 6: handles Hindi response', () => {
    const hiText = (
      '**प्रधानमंत्री किसान सम्मान निधि योजना:**\n\n' +
      'इस योजना के तहत सभी पात्र भूमिधारक किसान परिवारों को प्रति वर्ष ₹6,000 की वित्तीय सहायता दी जाती है। ' +
      'यह राशि हर चार महीने में ₹2,000 की तीन समान किस्तों में सीधे बैंक खाते में भेजी जाती है। ' +
      'आवेदन करने के लिए आधिकारिक पोर्टल पर जाकर फार्मर्स कॉर्नर में न्यू फार्मर रजिस्ट्रेशन विकल्प चुनें।'
    );
    const chunks = splitTextIntoSpeechChunks(hiText, 'hi');
    expect(chunks.length).toBeGreaterThanOrEqual(2);
    const combined = chunks.join(' ');
    expect(combined).toContain('प्रति वर्ष ₹6,000 की वित्तीय सहायता');
    expect(combined).toContain('₹2,000 की तीन समान किस्तों');
    expect(combined).toContain('न्यू फार्मर रजिस्ट्रेशन');
  });

  it('Case 7: preserves numbered steps and bullet points distinctly', () => {
    const stepsText = (
      'Follow these exact steps:\n' +
      '1. Open the portal.\n' +
      '2. Enter Aadhaar.\n' +
      '3. Verify OTP.\n' +
      '4. Upload land records.\n' +
      '5. Save registration ID.'
    );
    const chunks = splitTextIntoSpeechChunks(stepsText, 'en');
    const combined = chunks.join(' ');
    expect(combined).toContain('1. Open the portal');
    expect(combined).toContain('2. Enter Aadhaar');
    expect(combined).toContain('3. Verify OTP');
    expect(combined).toContain('4. Upload land records');
    expect(combined).toContain('5. Save registration ID');
  });
});
