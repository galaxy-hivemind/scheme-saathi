export type Language = 'hi' | 'en';

export interface Translations {
  appName: string;
  appTagline: string;
  nav: {
    home: string;
    schemes: string;
    chat: string;
    eligibility: string;
    documents: string;
    applications: string;
    dashboard: string;
    profile: string;
  };
  actions: {
    checkEligibility: string;
    viewDetails: string;
    applyNow: string;
    uploadDocument: string;
    submitApplication: string;
    saveDraft: string;
    retry: string;
    cancel: string;
    confirm: string;
    search: string;
    filter: string;
    exploreSchemes: string;
    startChat: string;
    editProfile: string;
  };
  status: {
    eligible: string;
    notEligible: string;
    potentiallyEligible: string;
    insufficientInfo: string;
    draft: string;
    validated: string;
    awaitingConfirmation: string;
    submitted: string;
    validationFailed: string;
    submissionFailed: string;
    cancelled: string;
  };
  labels: {
    category: string;
    ministry: string;
    benefits: string;
    targetBeneficiaries: string;
    officialPortal: string;
    verifiedOn: string;
    missingDocuments: string;
    requiredDocuments: string;
    uploadedDocuments: string;
    mockModeNotice: string;
  };
}

export const translations: Record<Language, Translations> = {
  en: {
    appName: "Scheme Saathi",
    appTagline: "AI-powered welfare scheme companion for Indian citizens",
    nav: {
      home: "Home",
      schemes: "Schemes",
      chat: "Saathi Assistant",
      eligibility: "Eligibility",
      documents: "Documents",
      applications: "Applications",
      dashboard: "Dashboard",
      profile: "Profile",
    },
    actions: {
      checkEligibility: "Check Eligibility",
      viewDetails: "View Scheme",
      applyNow: "Start Application",
      uploadDocument: "Upload Document",
      submitApplication: "Submit Application",
      saveDraft: "Save Draft",
      retry: "Retry",
      cancel: "Cancel",
      confirm: "Confirm & Proceed",
      search: "Search schemes...",
      filter: "Filter by category",
      exploreSchemes: "Discover Schemes",
      startChat: "Ask Scheme Saathi",
      editProfile: "Edit Profile",
    },
    status: {
      eligible: "Eligible",
      notEligible: "Not Eligible",
      potentiallyEligible: "Potentially Eligible",
      insufficientInfo: "Needs More Information",
      draft: "Draft",
      validated: "Validated",
      awaitingConfirmation: "Awaiting Confirmation",
      submitted: "Submitted",
      validationFailed: "Validation Failed",
      submissionFailed: "Submission Failed",
      cancelled: "Cancelled",
    },
    labels: {
      category: "Category",
      ministry: "Ministry",
      benefits: "Benefits",
      targetBeneficiaries: "Target Beneficiaries",
      officialPortal: "Official Portal",
      verifiedOn: "Verified on",
      missingDocuments: "Missing Documents",
      requiredDocuments: "Required Documents",
      uploadedDocuments: "Uploaded Documents",
      mockModeNotice: "Demo / Mock Mode Active — Real backend endpoints will connect when available",
    },
  },
  hi: {
    appName: "योजना साथी",
    appTagline: "भारतीय नागरिकों के लिए AI-संचालित सरकारी योजना सहायक",
    nav: {
      home: "होम",
      schemes: "सरकारी योजनाएं",
      chat: "साथी सहायक",
      eligibility: "पात्रता जांच",
      documents: "दस्तावेज़",
      applications: "आवेदन स्थिति",
      dashboard: "डैशबोर्ड",
      profile: "प्रोफ़ाइल",
    },
    actions: {
      checkEligibility: "पात्रता जांचें",
      viewDetails: "योजना विवरण",
      applyNow: "आवेदन शुरू करें",
      uploadDocument: "दस्तावेज़ अपलोड करें",
      submitApplication: "आवेदन जमा करें",
      saveDraft: "ड्राफ्ट सहेजें",
      retry: "पुनः प्रयास करें",
      cancel: "रद्द करें",
      confirm: "पुष्टि करें और आगे बढ़ें",
      search: "योजना खोजें...",
      filter: "श्रेणी अनुसार चुनें",
      exploreSchemes: "योजनाएं खोजें",
      startChat: "साथी से पूछें",
      editProfile: "प्रोफ़ाइल बदलें",
    },
    status: {
      eligible: "पात्र (Eligible)",
      notEligible: "अपात्र (Not Eligible)",
      potentiallyEligible: "संभावित पात्र",
      insufficientInfo: "अधूरी जानकारी",
      draft: "ड्राफ्ट",
      validated: "सत्यापित",
      awaitingConfirmation: "पुष्टि प्रतीक्षित",
      submitted: "जमा किया गया",
      validationFailed: "सत्यापन विफल",
      submissionFailed: "प्रस्तुतीकरण विफल",
      cancelled: "रद्द",
    },
    labels: {
      category: "श्रेणी",
      ministry: "मंत्रालय",
      benefits: "योजना के लाभ",
      targetBeneficiaries: "लक्षित लाभार्थी",
      officialPortal: "आधिकारिक पोर्टल",
      verifiedOn: "सत्यापित तिथि",
      missingDocuments: "शेष दस्तावेज़",
      requiredDocuments: "आवश्यक दस्तावेज़",
      uploadedDocuments: "अपलोड किए गए दस्तावेज़",
      mockModeNotice: "डेमो / मॉक मोड सक्रिय — बैकएंड उपलब्ध होने पर लाइव डेटा लोड होगा",
    },
  },
};
