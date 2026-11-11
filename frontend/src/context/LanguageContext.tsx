import React, { createContext, useContext, useState, ReactNode } from 'react';

type Language = 'hi' | 'en';

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  toggleLanguage: () => void;
  t: (key: string) => string;
}

const translations: Record<Language, Record<string, string>> = {
  hi: {
    // Nav & Shell
    'app.title': 'योजना साथी',
    'app.subtitle': 'सरकारी कल्याणकारी योजना सहायक',
    'nav.chat': 'बातचीत',
    'nav.schemes': 'योजनाएं',
    'nav.documents': 'दस्तावेज़',
    'nav.applications': 'आवेदन',
    'nav.tracking': 'ट्रैकिंग',
    'nav.profile': 'प्रोफ़ाइल',
    'nav.notifications': 'सूचनाएं',
    'nav.logout': 'लॉग आउट',
    'nav.login': 'लॉग इन',
    'nav.register': 'पंजीकरण',

    // Auth
    'auth.welcome': 'योजना साथी में आपका स्वागत है',
    'auth.login_title': 'अपने खाते में प्रवेश करें',
    'auth.register_title': 'नया नागरिक खाता बनाएं',
    'auth.email': 'ईमेल पता',
    'auth.password': 'पासवर्ड',
    'auth.full_name': 'पूरा नाम',
    'auth.preferred_language': 'पसंदीदा भाषा',
    'auth.btn_login': 'प्रवेश करें',
    'auth.btn_register': 'खाता बनाएं',
    'auth.no_account': 'खाता नहीं है? पंजीकरण करें',
    'auth.has_account': 'पहले से खाता है? प्रवेश करें',

    // Chat
    'chat.placeholder': 'अपनी भाषा में पूछें (उदा. क्या मुझे पीएम-किसान मिल सकता है?)...',
    'chat.send': 'भेजें',
    'chat.suggest_kisan': 'पीएम किसान योजना की पात्रता क्या है?',
    'chat.suggest_ayushman': 'आयुष्मान भारत योजना के लिए कौन से दस्तावेज़ चाहिए?',
    'chat.suggest_svanidhi': 'पीएम स्वनिधि ऋण के लिए आवेदन कैसे करें?',
    'chat.action_confirm': 'पुष्टि करें',
    'chat.action_cancel': 'रद्द करें',
    'chat.action_pending': 'नागरिक पुष्टि की प्रतीक्षा है',

    // Schemes
    'schemes.search_placeholder': 'योजना का नाम, मंत्रालय या लाभ खोजें...',
    'schemes.all_categories': 'सभी श्रेणियां',
    'schemes.agriculture': 'कृषि',
    'schemes.health': 'स्वास्थ्य',
    'schemes.housing': 'आवास',
    'schemes.pension': 'पेंशन',
    'schemes.business': 'व्यवसाय व स्वरोजगार',
    'schemes.education': 'शिक्षा',
    'schemes.btn_check_eligibility': 'पात्रता जांचें',
    'schemes.btn_view_details': 'विवरण देखें',
    'schemes.verified_badge': '2026 आधिकारिक रूप से सत्यापित',
    'schemes.documents_required': 'आवश्यक दस्तावेज़',
    'schemes.official_portal': 'आधिकारिक पोर्टल',

    // Eligibility
    'eligibility.title': 'पारदर्शी पात्रता मूल्यांकन',
    'eligibility.eligible': 'पात्र (Eligible)',
    'eligibility.ineligible': 'अपात्र (Ineligible)',
    'eligibility.potentially_eligible': 'संभावित पात्र / अतिरिक्त जानकारी आवश्यक',
    'eligibility.matched': 'पूरी की गई शर्तें',
    'eligibility.failed': 'अपूर्ण शर्तें',
    'eligibility.missing': 'अतिरिक्त जानकारी आवश्यक',
    'eligibility.answer_question': 'प्रश्न का उत्तर दें',

    // Documents
    'docs.title': 'दस्तावेज़ तत्परता चेकलिस्ट',
    'docs.ready_status': 'आवेदन के लिए तैयार',
    'docs.missing_status': 'दस्तावेज़ शेष हैं',
    'docs.upload_btn': 'दस्तावेज़ अपलोड करें',
    'docs.drag_drop': 'फ़ाइल यहाँ खींचें या चुनने के लिए क्लिक करें (PDF, JPG, PNG, अधिकतम 10MB)',
    'docs.mandatory': 'अनिवार्य',
    'docs.optional': 'वैकल्पिक',
    'docs.where_to_get': 'यह दस्तावेज़ कहाँ से प्राप्त करें',
    'docs.verified': 'सत्यापित',

    // Applications & Tracking
    'apps.title': 'योजना आवेदन ड्राफ्ट व पोर्टल हैंडऑफ़',
    'apps.status_draft': 'ड्राफ्ट तैयार हो रहा है',
    'apps.status_ready': 'पोर्टल पर जमा करने के लिए तैयार',
    'apps.status_submitted': 'आधिकारिक पोर्टल पर जमा किया गया',
    'apps.status_in_review': 'विभागीय समीक्षाधीन',
    'apps.status_approved': 'स्वीकृत (Approved)',
    'apps.status_disbursed': 'लाभ वितरित (Disbursed)',
    'apps.btn_apply_portal': 'आधिकारिक पोर्टल पर आवेदन करें',
    'apps.btn_log_submission': 'स्वीकृति संदर्भ संख्या (Acknowledgement ID) दर्ज करें',
    'apps.ref_placeholder': 'उदा. PMKISAN/2026/123456',
    'apps.btn_save_ref': 'संदर्भ संख्या सहेजें',

    // Tracking
    'tracking.title': 'आवेदन स्थिति व समय-सीमा',
    'tracking.timeline': 'प्रगति समय-सीमा (Audit Trail)',
    'tracking.btn_sync': 'आधिकारिक पोर्टल से स्थिति सिंक करें',

    // Notifications
    'notifications.title': 'नागरिक सूचना केंद्र',
    'notifications.mark_all_read': 'सभी को पढ़ा हुआ चिन्हित करें',
    'notifications.empty': 'कोई नई सूचना नहीं है',
  },
  en: {
    // Nav & Shell
    'app.title': 'Scheme Saathi',
    'app.subtitle': 'Government Welfare Scheme Assistant',
    'nav.chat': 'Chat',
    'nav.schemes': 'Schemes',
    'nav.documents': 'Documents',
    'nav.applications': 'Applications',
    'nav.tracking': 'Tracking',
    'nav.profile': 'Profile',
    'nav.notifications': 'Notifications',
    'nav.logout': 'Sign Out',
    'nav.login': 'Sign In',
    'nav.register': 'Register',

    // Auth
    'auth.welcome': 'Welcome to Scheme Saathi',
    'auth.login_title': 'Sign in to your citizen account',
    'auth.register_title': 'Create a new citizen account',
    'auth.email': 'Email Address',
    'auth.password': 'Password',
    'auth.full_name': 'Full Name',
    'auth.preferred_language': 'Preferred Language',
    'auth.btn_login': 'Sign In',
    'auth.btn_register': 'Create Account',
    'auth.no_account': "Don't have an account? Register here",
    'auth.has_account': 'Already registered? Sign in here',

    // Chat
    'chat.placeholder': 'Ask in your language (e.g. Am I eligible for PM-KISAN?)...',
    'chat.send': 'Send',
    'chat.suggest_kisan': 'What is the eligibility for PM-KISAN?',
    'chat.suggest_ayushman': 'Which documents are required for Ayushman Bharat?',
    'chat.suggest_svanidhi': 'How do I apply for PM SVANidhi street vendor loan?',
    'chat.action_confirm': 'Confirm Action',
    'chat.action_cancel': 'Cancel',
    'chat.action_pending': 'Waiting for Citizen Confirmation',

    // Schemes
    'schemes.search_placeholder': 'Search schemes by keyword, ministry, or benefit...',
    'schemes.all_categories': 'All Categories',
    'schemes.agriculture': 'Agriculture',
    'schemes.health': 'Health',
    'schemes.housing': 'Housing',
    'schemes.pension': 'Pension',
    'schemes.business': 'Business & Livelihood',
    'schemes.education': 'Education',
    'schemes.btn_check_eligibility': 'Check Eligibility',
    'schemes.btn_view_details': 'View Details',
    'schemes.verified_badge': '2026 Officially Verified',
    'schemes.documents_required': 'Required Documents',
    'schemes.official_portal': 'Official Portal',

    // Eligibility
    'eligibility.title': 'Transparent Eligibility Breakdown',
    'eligibility.eligible': 'Eligible',
    'eligibility.ineligible': 'Ineligible',
    'eligibility.potentially_eligible': 'Potentially Eligible / Additional Info Needed',
    'eligibility.matched': 'Matched Criteria',
    'eligibility.failed': 'Failed Criteria',
    'eligibility.missing': 'Missing Information',
    'eligibility.answer_question': 'Answer Question',

    // Documents
    'docs.title': 'Document Readiness Checklist',
    'docs.ready_status': 'Ready for Application',
    'docs.missing_status': 'Documents Pending',
    'docs.upload_btn': 'Upload Document',
    'docs.drag_drop': 'Drag and drop file here, or click to browse (PDF, JPG, PNG up to 10MB)',
    'docs.mandatory': 'Mandatory',
    'docs.optional': 'Optional',
    'docs.where_to_get': 'Where to obtain this document',
    'docs.verified': 'Verified',

    // Applications & Tracking
    'apps.title': 'Scheme Application Drafts & Portal Handoff',
    'apps.status_draft': 'Draft Preparing',
    'apps.status_ready': 'Ready for Portal Submission',
    'apps.status_submitted': 'Submitted to Official Portal',
    'apps.status_in_review': 'Under Departmental Review',
    'apps.status_approved': 'Approved',
    'apps.status_disbursed': 'Benefit Disbursed',
    'apps.btn_apply_portal': 'Apply on Official Government Portal',
    'apps.btn_log_submission': 'Record Acknowledgement Reference Number',
    'apps.ref_placeholder': 'e.g. PMKISAN/2026/123456',
    'apps.btn_save_ref': 'Save Reference Number',

    // Tracking
    'tracking.title': 'Application Status & Timeline',
    'tracking.timeline': 'Progress Timeline (Audit Trail)',
    'tracking.btn_sync': 'Sync Status from Official Portal',

    // Notifications
    'notifications.title': 'Citizen Notification Center',
    'notifications.mark_all_read': 'Mark All as Read',
    'notifications.empty': 'No new notifications',
  },
};

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export const LanguageProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [language, setLanguageState] = useState<Language>(() => {
    const saved = localStorage.getItem('scheme_saathi_lang');
    return saved === 'en' ? 'en' : 'hi';
  });

  const setLanguage = (lang: Language) => {
    setLanguageState(lang);
    localStorage.setItem('scheme_saathi_lang', lang);
  };

  const toggleLanguage = () => {
    setLanguage(language === 'hi' ? 'en' : 'hi');
  };

  const t = (key: string): string => {
    return translations[language][key] || translations['en'][key] || key;
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage, toggleLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useLanguage = (): LanguageContextType => {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
};
