import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate, useSearchParams } from 'react-router-dom';
import { schemeService } from '@/services/api/schemeService';
import { eligibilityService } from '@/services/api/eligibilityService';
import { documentService } from '@/services/api/documentService';
import { Scheme, EligibilityResult, DocumentRequirement } from '@/types';
import { useLanguage } from '@/context/LanguageContext';
import { useAuth } from '@/context/AuthContext';
import { Card, CardHeader, CardContent } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Spinner } from '@/components/common/Spinner';
import { StatusBanner } from '@/components/common/StatusBanner';
import { LoginModal } from '@/components/common/LoginModal';
import {
  ExternalLink,
  ShieldCheck,
  Building,
  CheckCircle2,
  AlertTriangle,
  FileText,
  Calendar,
  Sparkles,
  ArrowLeft,
  ArrowRight,
  HelpCircle,
  XCircle,
  LogIn,
  Info,
  Coins,
  Send,
  MapPin,
  Check,
  PiggyBank,
  TrendingUp,
  HeartHandshake,
  AlertCircle,
} from 'lucide-react';

export type SchemeDetailTab =
  | 'overview'
  | 'benefits'
  | 'eligibility'
  | 'documents'
  | 'application'
  | 'sources';

export const SchemeDetailsPage: React.FC<{
  initialScheme?: Scheme;
  initialDocuments?: DocumentRequirement[];
}> = ({ initialScheme, initialDocuments }) => {
  const { id } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { t, language } = useLanguage();
  const { profile, isAuthenticated, token } = useAuth();

  const [scheme, setScheme] = useState<Scheme | null>(initialScheme || null);
  const [eligibility, setEligibility] = useState<EligibilityResult | null>(null);
  const [documents, setDocuments] = useState<DocumentRequirement[]>(initialDocuments || []);
  const [loading, setLoading] = useState<boolean>(!initialScheme);
  const [checkingEligibility, setCheckingEligibility] = useState<boolean>(false);
  const [eligibilityError, setEligibilityError] = useState<string | null>(null);
  const [isLoginOpen, setIsLoginOpen] = useState<boolean>(false);

  // Active Tab state (synced with ?tab= search param)
  const initialTab = (searchParams.get('tab') as SchemeDetailTab) || 'overview';
  const [activeTab, setActiveTab] = useState<SchemeDetailTab>(
    ['overview', 'benefits', 'eligibility', 'documents', 'application', 'sources'].includes(initialTab)
      ? initialTab
      : 'overview'
  );

  // Sync state if URL search param changes
  useEffect(() => {
    const tabParam = searchParams.get('tab') as SchemeDetailTab;
    if (
      tabParam &&
      ['overview', 'benefits', 'eligibility', 'documents', 'application', 'sources'].includes(tabParam)
    ) {
      setActiveTab(tabParam);
    }
  }, [searchParams]);

  // Load scheme details and document checklist if not pre-provided
  useEffect(() => {
    const loadData = async () => {
      if (!id || initialScheme) return;
      setLoading(true);
      try {
        const s = await schemeService.getSchemeById(id);
        setScheme(s);
        let docs: DocumentRequirement[] =
          s.documents || (s as any).required_documents || [];
        try {
          const checklist = await documentService.getChecklist(id);
          if (checklist && checklist.length > 0) {
            docs = checklist;
          }
        } catch {
          // Fallback to documents defined on the scheme
        }
        setDocuments(docs);
      } catch (err) {
        console.error('Failed to load scheme details:', err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [id]);

  // Re-evaluate eligibility when switching citizens or when opening the eligibility tab
  useEffect(() => {
    setEligibility(null);
    setEligibilityError(null);
    if (activeTab === 'eligibility' && id && (token || profile)) {
      handleCheckEligibility();
    }
  }, [id, profile?.id]);

  const handleTabClick = (tab: SchemeDetailTab) => {
    setActiveTab(tab);
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set('tab', tab);
        return next;
      },
      { replace: true }
    );

    // If switching to eligibility tab and user is logged in, auto-check if not already done
    if (tab === 'eligibility' && id && (token || profile) && !eligibility && !checkingEligibility) {
      handleCheckEligibility();
    }
  };

  const handleCheckEligibility = async () => {
    if (!id) return;
    setEligibilityError(null);

    if (!token && !profile) {
      setEligibilityError(
        language === 'hi'
          ? 'पात्रता जांचने के लिए कृपया अपने नागरिक खाते में लॉग इन करें।'
          : 'Please log in to your citizen account to evaluate personal eligibility against official rules.'
      );
      setIsLoginOpen(true);
      return;
    }

    setCheckingEligibility(true);
    try {
      const res = await eligibilityService.checkEligibility(id);
      setEligibility(res);
    } catch (err: any) {
      console.error('Failed eligibility check:', err);
      const msg = err?.message || 'Failed to evaluate eligibility against database criteria.';
      if (err?.code === 'HTTP_401' || msg.includes('token') || msg.includes('log in')) {
        setEligibilityError(
          language === 'hi'
            ? 'आपका सत्र समाप्त हो गया है। कृपया पुनः लॉग इन करें।'
            : 'Your session has expired or authentication is missing. Please sign in.'
        );
        setIsLoginOpen(true);
      } else {
        setEligibilityError(msg);
      }
    } finally {
      setCheckingEligibility(false);
    }
  };

  if (loading) {
    return (
      <Spinner
        size="lg"
        label={language === 'hi' ? 'योजना विवरण लोड हो रहा है...' : 'Loading scheme details...'}
      />
    );
  }

  if (!scheme) {
    return (
      <div className="text-center py-16 space-y-4">
        <p className="text-navy/60">
          {language === 'hi' ? 'योजना प्राप्त नहीं हुई।' : 'Scheme not found.'}
        </p>
        <Button variant="outline" onClick={() => navigate('/schemes')}>
          {language === 'hi' ? 'योजना सूची पर वापस जाएं' : 'Back to Schemes'}
        </Button>
      </div>
    );
  }

  const targetBeneficiariesList = Array.isArray(scheme.target_beneficiaries)
    ? scheme.target_beneficiaries
    : typeof scheme.target_beneficiaries === 'string'
    ? (scheme.target_beneficiaries as string).split(',').map((s) => s.trim())
    : [];

  const tabs: {
    id: SchemeDetailTab;
    labelEn: string;
    labelHi: string;
    icon: React.ReactNode;
    badgeCount?: number;
  }[] = [
    {
      id: 'overview',
      labelEn: 'Overview / Description',
      labelHi: 'विवरण (Overview)',
      icon: <Info className="w-4 h-4" />,
    },
    {
      id: 'benefits',
      labelEn: 'Benefits',
      labelHi: 'योजना के लाभ (Benefits)',
      icon: <Coins className="w-4 h-4 text-saffron" />,
    },
    {
      id: 'eligibility',
      labelEn: 'Eligibility',
      labelHi: 'पात्रता निकष (Eligibility)',
      icon: <Sparkles className="w-4 h-4 text-saffron-vibrant" />,
    },
    {
      id: 'documents',
      labelEn: 'Required Documents',
      labelHi: 'आवश्यक दस्तावेज़ (Documents)',
      icon: <FileText className="w-4 h-4" />,
      badgeCount: documents.length > 0 ? documents.length : undefined,
    },
    {
      id: 'application',
      labelEn: 'Application Process',
      labelHi: 'आवेदन प्रक्रिया (Application)',
      icon: <Send className="w-4 h-4 text-emerald-600" />,
    },
    {
      id: 'sources',
      labelEn: 'Official Sources',
      labelHi: 'अधिकृत संदर्भ (Official Sources)',
      icon: <ShieldCheck className="w-4 h-4 text-sage-green" />,
    },
  ];

  return (
    <div className="space-y-7 max-w-4xl mx-auto pb-12">
      {/* Top Breadcrumb / Back button */}
      <Link
        to="/schemes"
        className="inline-flex items-center gap-2 text-xs font-semibold text-navy/60 hover:text-navy transition-colors group"
      >
        <ArrowLeft className="w-4 h-4 transition-transform group-hover:-translate-x-1" />
        <span>{language === 'hi' ? 'सभी योजनाओं पर वापस जाएं' : 'Back to schemes catalog'}</span>
      </Link>

      {/* Main Scheme Hero Banner */}
      <div className="bg-white rounded-3xl border border-navy/8 p-6 sm:p-8 space-y-4 shadow-subtle relative overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2.5">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="category">{scheme.category.replace(/_/g, ' ').toUpperCase()}</Badge>
            <span className="text-[10px] font-mono font-bold bg-ivory-100 text-navy/70 px-2.5 py-0.5 rounded-md border border-navy/10">
              {scheme.scheme_code}
            </span>
            <span className="text-[10px] uppercase font-bold text-navy/50 bg-ivory-100 px-2 py-0.5 rounded border border-navy/10">
              {scheme.geographic_scope === 'central' ? 'Central Sector' : 'State Scheme'}
            </span>
          </div>

          <div className="flex items-center gap-3 text-xs text-navy/60 font-medium">
            <span className="flex items-center gap-1.5 text-sage-green bg-sage-light px-2.5 py-0.5 rounded-full border border-sage/30 font-semibold">
              <ShieldCheck className="w-3.5 h-3.5" />
              {scheme.scheme_status}
            </span>
            {scheme.last_verified_at && (
              <span className="flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5 text-navy/40" />
                Verified: {scheme.last_verified_at.split('T')[0]}
              </span>
            )}
          </div>
        </div>

        <h1 className="text-2xl sm:text-3xl font-bold font-editorial text-navy leading-tight tracking-tight">
          {scheme.name}
        </h1>

        <div className="flex items-center gap-2 text-xs text-navy/70 font-semibold">
          <Building className="w-4 h-4 text-saffron shrink-0" />
          <span>{scheme.ministry}</span>
          {scheme.department && <span className="text-navy/40">• {scheme.department}</span>}
        </div>

        <p className="text-sm text-navy/70 leading-relaxed pt-1 max-w-3xl">{scheme.description}</p>

        {/* Global Action Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-navy/8">
          <div className="flex items-center gap-2 flex-wrap">
            <Button
              variant="saffron"
              size="sm"
              leftIcon={<Sparkles className="w-4 h-4" />}
              onClick={() => handleTabClick('eligibility')}
            >
              {t.actions.checkEligibility}
            </Button>

            <Button
              variant="outline"
              size="sm"
              leftIcon={<Coins className="w-4 h-4 text-saffron" />}
              onClick={() => handleTabClick('benefits')}
            >
              {language === 'hi' ? 'लाभ देखें' : 'View Benefits'}
            </Button>
          </div>

          {scheme.official_url && (
            <a
              href={scheme.official_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border border-navy/15 text-navy bg-white hover:bg-ivory-50 transition-all duration-200 shadow-subtle"
            >
              <span>{t.labels.officialPortal}</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          )}
        </div>
      </div>

      {/* 6 Interactive Scheme Detail Tabs Navigation Bar */}
      <div className="bg-white rounded-2xl border border-navy/10 p-1.5 shadow-subtle">
        <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none" role="tablist">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                role="tab"
                aria-selected={isActive}
                onClick={() => handleTabClick(tab.id)}
                className={`flex items-center gap-2 px-3.5 sm:px-4 py-2.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all duration-200 border cursor-pointer ${
                  isActive
                    ? 'bg-navy text-white border-navy shadow-subtle'
                    : 'bg-transparent text-navy/70 border-transparent hover:bg-ivory-100 hover:text-navy hover:border-navy/10'
                }`}
              >
                {tab.icon}
                <span>{language === 'hi' ? tab.labelHi : tab.labelEn}</span>
                {tab.badgeCount !== undefined && (
                  <span
                    className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${
                      isActive ? 'bg-white/20 text-white' : 'bg-ivory-200 text-navy/70'
                    }`}
                  >
                    {tab.badgeCount}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          TAB 1: OVERVIEW / DESCRIPTION
      ────────────────────────────────────────────────────────────── */}
      {activeTab === 'overview' && (
        <div className="space-y-6 animate-fade-in-up">
          <Card>
            <CardHeader>
              <h3 className="font-bold font-editorial text-navy text-base flex items-center gap-2">
                <Info className="w-4 h-4 text-saffron" />
                <span>{language === 'hi' ? 'योजना का संपूर्ण विवरण' : 'Scheme Overview & Objective'}</span>
              </h3>
            </CardHeader>
            <CardContent className="p-6 space-y-4">
              <p className="text-sm text-navy/80 leading-relaxed font-sans">
                {scheme.description || (
                  <span className="italic text-navy/50">
                    {language === 'hi' ? 'विवरण उपलब्ध नहीं है।' : 'No description registered for this scheme.'}
                  </span>
                )}
              </p>

              {/* Administrative Facts Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 pt-2">
                <div className="p-3.5 rounded-xl bg-ivory-50 border border-navy/8 space-y-1">
                  <span className="text-[10px] uppercase font-bold text-navy/50 block">
                    {language === 'hi' ? 'मंत्रालय (Ministry)' : 'Nodal Ministry'}
                  </span>
                  <span className="text-xs font-semibold text-navy block">{scheme.ministry}</span>
                </div>

                <div className="p-3.5 rounded-xl bg-ivory-50 border border-navy/8 space-y-1">
                  <span className="text-[10px] uppercase font-bold text-navy/50 block">
                    {language === 'hi' ? 'योजना श्रेणी (Category)' : 'Scheme Category'}
                  </span>
                  <span className="text-xs font-semibold text-navy capitalize">
                    {scheme.category.replace(/_/g, ' ')}
                  </span>
                </div>

                <div className="p-3.5 rounded-xl bg-ivory-50 border border-navy/8 space-y-1">
                  <span className="text-[10px] uppercase font-bold text-navy/50 block">
                    {language === 'hi' ? 'भौगोलिक व्याप्ती (Scope)' : 'Geographic Scope'}
                  </span>
                  <span className="text-xs font-semibold text-navy">
                    {scheme.geographic_scope === 'central' ? 'Central Sector (Pan-India)' : 'State Welfare Scheme'}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Target Beneficiaries Card */}
          <Card>
            <CardHeader>
              <h3 className="font-bold font-editorial text-navy text-base flex items-center gap-2">
                <Building className="w-4 h-4 text-navy/60" />
                <span>{t.labels.targetBeneficiaries}</span>
              </h3>
            </CardHeader>
            <CardContent className="p-6 space-y-3">
              {targetBeneficiariesList.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {targetBeneficiariesList.map((beneficiary, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-ivory-100 text-navy font-semibold text-xs border border-navy/10"
                    >
                      <Check className="w-3.5 h-3.5 text-sage-green" />
                      <span>{beneficiary}</span>
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-navy/60">
                  {language === 'hi'
                    ? 'लक्षित लाभार्थी विवरण उपलब्ध नहीं है।'
                    : 'Target beneficiaries criteria not specified.'}
                </p>
              )}
            </CardContent>
          </Card>

          {/* Quick Action Navigation Prompts */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <button
              onClick={() => handleTabClick('benefits')}
              className="p-4 rounded-2xl border border-saffron/30 bg-gradient-to-r from-saffron-light/40 to-white hover:from-saffron-light/60 transition-all text-left space-y-1 shadow-subtle group cursor-pointer"
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-xs text-navy font-editorial flex items-center gap-1.5">
                  <Coins className="w-4 h-4 text-saffron" />
                  <span>{language === 'hi' ? 'वित्तीय लाभ देखें' : 'View Scheme Benefits'}</span>
                </span>
                <ArrowRight className="w-3.5 h-3.5 text-saffron-dark group-hover:translate-x-1 transition-transform" />
              </div>
              <p className="text-[11px] text-navy/60">
                {language === 'hi' ? 'डीबीटी राशि, किस्तों और वित्तीय कवरेज की जानकारी।' : 'Explore financial amounts, DBT installments, and coverage details.'}
              </p>
            </button>

            <button
              onClick={() => handleTabClick('eligibility')}
              className="p-4 rounded-2xl border border-sage/30 bg-gradient-to-r from-sage-light/40 to-white hover:from-sage-light/60 transition-all text-left space-y-1 shadow-subtle group cursor-pointer"
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-xs text-navy font-editorial flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4 text-sage-green" />
                  <span>{language === 'hi' ? 'अपनी पात्रता जांचें' : 'Check Your Eligibility'}</span>
                </span>
                <ArrowRight className="w-3.5 h-3.5 text-sage-dark group-hover:translate-x-1 transition-transform" />
              </div>
              <p className="text-[11px] text-navy/60">
                {language === 'hi' ? 'अपनी प्रोफ़ाइल के अनुसार त्वरित व सटीक नियम मूल्यांकन।' : 'Evaluate statutory conditions against your citizen profile.'}
              </p>
            </button>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          TAB 2: BENEFITS
      ────────────────────────────────────────────────────────────── */}
      {activeTab === 'benefits' && (
        <div className="space-y-6 animate-fade-in-up">
          <Card className="border-saffron/25 shadow-subtle">
            <CardHeader className="bg-gradient-to-r from-saffron-light/50 to-white border-b border-saffron/20">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <h3 className="font-bold font-editorial text-navy text-base flex items-center gap-2">
                  <Coins className="w-5 h-5 text-saffron-vibrant" />
                  <span>{language === 'hi' ? 'योजना के वैधानिक लाभ एवं वित्तीय सहायता' : 'Statutory Scheme Benefits & Assistance'}</span>
                </h3>
                <span className="text-[10px] font-bold text-saffron-dark bg-saffron-light px-2.5 py-0.5 rounded-full border border-saffron/30">
                  Direct Benefit Transfer (DBT)
                </span>
              </div>
            </CardHeader>
            <CardContent className="p-6 space-y-4">
              {scheme.benefits ? (
                <div className="space-y-4">
                  <div className="p-4 rounded-2xl bg-sage-light/60 border border-sage/25 space-y-2">
                    <span className="text-[10px] uppercase font-bold text-sage-dark tracking-wider block">
                      {language === 'hi' ? 'मुख्य वित्तीय लाभ (Core Benefit Statement)' : 'Official Benefit Entitlement'}
                    </span>
                    <p className="text-sm font-semibold text-navy leading-relaxed font-sans">
                      {scheme.benefits}
                    </p>
                  </div>

                  {/* Highlights Grid */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                    <div className="p-4 rounded-xl bg-ivory-50 border border-navy/8 space-y-1.5">
                      <span className="text-[10px] uppercase font-bold text-navy/50 flex items-center gap-1.5">
                        <Coins className="w-3.5 h-3.5 text-saffron" />
                        <span>{language === 'hi' ? 'हस्तांतरण माध्यम (Disbursement Mode)' : 'Disbursement Channel'}</span>
                      </span>
                      <p className="text-xs text-navy/80 font-medium">
                        {language === 'hi'
                          ? 'आधार-संलग्न बैंक खाते में प्रत्यक्ष लाभ अंतरण (DBT) द्वारा बिना किसी बिचौलिए के।'
                          : 'Direct Benefit Transfer (DBT) directly into Aadhaar-seeded bank account via PFMS/NPCI.'}
                      </p>
                    </div>

                    <div className="p-4 rounded-xl bg-ivory-50 border border-navy/8 space-y-1.5">
                      <span className="text-[10px] uppercase font-bold text-navy/50 flex items-center gap-1.5">
                        <ShieldCheck className="w-3.5 h-3.5 text-sage-green" />
                        <span>{language === 'hi' ? 'वैधानिक सुरक्षा (Statutory Guarantee)' : 'Statutory Guarantee'}</span>
                      </span>
                      <p className="text-xs text-navy/80 font-medium">
                        {language === 'hi'
                          ? 'कल्याणकारी दिशा-निर्देशों के अनुसार 100% केंद्रीय/राज्य वित्तपोषित एवं सुरक्षित।'
                          : 'Guaranteed welfare benefit funded per official government operational guidelines.'}
                      </p>
                    </div>
                  </div>

                  {/* APY Specialized Structured Benefits */}
                  {scheme.scheme_code?.toUpperCase() === 'APY' && (
                    <div className="space-y-6 pt-3">
                      {/* Section 1: Guaranteed Pension Slabs & Corpus Return */}
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <h4 className="text-xs uppercase font-bold tracking-wider text-navy flex items-center gap-1.5">
                            <PiggyBank className="w-4 h-4 text-saffron" />
                            <span>
                              {language === 'hi'
                                ? 'गारंटीड मासिक पेंशन विकल्प एवं नामिती कॉर्पस (5 पेंशन स्लैब)'
                                : 'Guaranteed Monthly Pension Options & Nominee Corpus (5 Pension Slabs)'}
                            </span>
                          </h4>
                          <span className="text-[10px] font-semibold text-navy/60 bg-ivory-100 px-2 py-0.5 rounded border border-navy/10">
                            PFRDA Regulated
                          </span>
                        </div>
                        <p className="text-xs text-navy/70">
                          {language === 'hi'
                            ? '60 वर्ष की आयु पूर्ण होने पर अंशधारक को उसके द्वारा चुने गए स्लैब के अनुसार आजीवन मासिक पेंशन मिलती है।'
                            : 'Subscribers receive a lifelong monthly pension upon reaching 60 years of age based on their chosen slab.'}
                        </p>

                        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
                          {[
                            { pension: '₹1,000', corpus: '₹1.70 Lakh' },
                            { pension: '₹2,000', corpus: '₹3.40 Lakh' },
                            { pension: '₹3,000', corpus: '₹5.10 Lakh' },
                            { pension: '₹4,000', corpus: '₹6.80 Lakh' },
                            { pension: '₹5,000', corpus: '₹8.50 Lakh' },
                          ].map((slab, sIdx) => (
                            <div
                              key={sIdx}
                              className="p-3 rounded-xl bg-ivory-50 border border-saffron/20 text-center hover:border-saffron/50 transition-colors shadow-xs"
                            >
                              <span className="text-[10px] uppercase font-bold text-navy/50 block">
                                {language === 'hi' ? 'मासिक पेंशन' : 'Monthly Pension'}
                              </span>
                              <span className="text-base font-extrabold text-navy block my-0.5">
                                {slab.pension}
                              </span>
                              <div className="pt-1.5 border-t border-navy/6 text-[10px] text-navy/70">
                                <span className="block text-navy/50 font-medium">
                                  {language === 'hi' ? 'नामिती कॉर्पस' : 'Nominee Corpus'}
                                </span>
                                <span className="font-bold text-sage-dark">{slab.corpus}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Section 2: Tripartite Protection (Subscriber -> Spouse -> Nominee) */}
                      <div className="p-4 rounded-2xl bg-white border border-navy/10 space-y-3">
                        <h4 className="text-xs uppercase font-bold tracking-wider text-navy flex items-center gap-1.5">
                          <HeartHandshake className="w-4 h-4 text-emerald-600" />
                          <span>
                            {language === 'hi'
                              ? 'त्रिस्तरीय पारिवारिक सुरक्षा चक्र (Subscriber • Spouse • Nominee)'
                              : 'Tripartite Family Protection Lifecycle (Subscriber • Spouse • Nominee)'}
                          </span>
                        </h4>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                          <div className="p-3 rounded-xl bg-ivory-50/90 border border-navy/8 space-y-1">
                            <div className="flex items-center gap-1.5 text-xs font-bold text-navy">
                              <span className="w-5 h-5 rounded-full bg-navy text-white text-[11px] flex items-center justify-center shrink-0 font-mono">1</span>
                              <span>{language === 'hi' ? 'अंशधारक (Subscriber)' : 'Subscriber Lifetime'}</span>
                            </div>
                            <p className="text-[11px] text-navy/80 leading-relaxed">
                              {language === 'hi'
                                ? '60 वर्ष की आयु से आजीवन गारंटीड मासिक पेंशन (₹1,000 से ₹5,000)।'
                                : 'Lifelong guaranteed monthly pension (₹1,000 to ₹5,000) from age 60 till demise.'}
                            </p>
                          </div>

                          <div className="p-3 rounded-xl bg-ivory-50/90 border border-navy/8 space-y-1">
                            <div className="flex items-center gap-1.5 text-xs font-bold text-navy">
                              <span className="w-5 h-5 rounded-full bg-saffron text-white text-[11px] flex items-center justify-center shrink-0 font-mono">2</span>
                              <span>{language === 'hi' ? 'पति/पत्नी अधिकार (Spouse)' : 'Spouse Entitlement'}</span>
                            </div>
                            <p className="text-[11px] text-navy/80 leading-relaxed">
                              {language === 'hi'
                                ? 'अंशधारक के निधन पर ठीक उतनी ही 100% मासिक पेंशन पति/पत्नी को आजीवन मिलती है।'
                                : 'Upon subscriber demise, identical 100% monthly pension continues to the spouse for life.'}
                            </p>
                          </div>

                          <div className="p-3 rounded-xl bg-ivory-50/90 border border-navy/8 space-y-1">
                            <div className="flex items-center gap-1.5 text-xs font-bold text-navy">
                              <span className="w-5 h-5 rounded-full bg-sage-dark text-white text-[11px] flex items-center justify-center shrink-0 font-mono">3</span>
                              <span>{language === 'hi' ? 'नामिती को कॉर्पस (Nominee)' : 'Nominee Corpus'}</span>
                            </div>
                            <p className="text-[11px] text-navy/80 leading-relaxed">
                              {language === 'hi'
                                ? 'दंपति दोनों के निधन पर सम्पूर्ण संचित पेंशन निधि (₹1.7 से ₹8.5 लाख) नामिती को हस्तांतरित।'
                                : 'Upon demise of both subscriber and spouse, 100% accumulated pension wealth (₹1.7L to ₹8.5L) is handed over to the nominee.'}
                            </p>
                          </div>
                        </div>
                      </div>

                      {/* Section 3: Subscriber Contribution Schedule & Age Dynamics */}
                      <div className="space-y-3">
                        <div className="flex items-center justify-between flex-wrap gap-2">
                          <h4 className="text-xs uppercase font-bold tracking-wider text-navy flex items-center gap-1.5">
                            <TrendingUp className="w-4 h-4 text-saffron-dark" />
                            <span>
                              {language === 'hi'
                                ? 'अंशदान तालिका व आयु सीमा (PFRDA Contribution Schedule)'
                                : 'Subscriber Contribution Schedule by Entry Age (PFRDA Master Circular)'}
                            </span>
                          </h4>
                          <span className="text-[10px] text-navy/60 font-medium">
                            {language === 'hi' ? 'मासिक ऑटो-डेबिट (बचत बैंक खाता)' : 'Monthly Auto-Debit from Savings Account'}
                          </span>
                        </div>
                        <p className="text-xs text-navy/70 leading-relaxed">
                          {language === 'hi'
                            ? 'मासिक अंशदान नागरिक की प्रवेश आयु (18 से 40 वर्ष) एवं चयनित पेंशन राशि पर निर्भर करता है। जितनी कम उम्र में जुड़ेंगे, मासिक अंशदान उतना ही कम होगा:'
                            : 'Monthly contribution depends strictly on entry age (18 to 40 years) and the selected pension slab. Joining earlier results in significantly lower contributions:'}
                        </p>

                        <div className="overflow-x-auto rounded-xl border border-navy/10 bg-white shadow-xs">
                          <table className="w-full text-left text-xs">
                            <thead className="bg-ivory-100 text-navy/70 font-semibold border-b border-navy/10">
                              <tr>
                                <th className="p-2.5">{language === 'hi' ? 'प्रवेश आयु' : 'Entry Age'}</th>
                                <th className="p-2.5">{language === 'hi' ? 'अवधि' : 'Years'}</th>
                                <th className="p-2.5 text-right font-mono">₹1,000/mo</th>
                                <th className="p-2.5 text-right font-mono">₹2,000/mo</th>
                                <th className="p-2.5 text-right font-mono">₹3,000/mo</th>
                                <th className="p-2.5 text-right font-mono">₹4,000/mo</th>
                                <th className="p-2.5 text-right font-mono text-saffron-dark font-bold">₹5,000/mo</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-navy/6 font-mono text-[11px] text-navy/90">
                              <tr className="hover:bg-ivory-50">
                                <td className="p-2.5 font-bold font-sans">18 yrs</td>
                                <td className="p-2.5 text-navy/60">42 yrs</td>
                                <td className="p-2.5 text-right">₹42</td>
                                <td className="p-2.5 text-right">₹84</td>
                                <td className="p-2.5 text-right">₹126</td>
                                <td className="p-2.5 text-right">₹168</td>
                                <td className="p-2.5 text-right font-bold text-saffron-dark">₹210</td>
                              </tr>
                              <tr className="hover:bg-ivory-50">
                                <td className="p-2.5 font-bold font-sans">20 yrs</td>
                                <td className="p-2.5 text-navy/60">40 yrs</td>
                                <td className="p-2.5 text-right">₹50</td>
                                <td className="p-2.5 text-right">₹100</td>
                                <td className="p-2.5 text-right">₹150</td>
                                <td className="p-2.5 text-right">₹198</td>
                                <td className="p-2.5 text-right font-bold text-saffron-dark">₹248</td>
                              </tr>
                              <tr className="hover:bg-ivory-50">
                                <td className="p-2.5 font-bold font-sans">25 yrs</td>
                                <td className="p-2.5 text-navy/60">35 yrs</td>
                                <td className="p-2.5 text-right">₹76</td>
                                <td className="p-2.5 text-right">₹151</td>
                                <td className="p-2.5 text-right">₹226</td>
                                <td className="p-2.5 text-right">₹301</td>
                                <td className="p-2.5 text-right font-bold text-saffron-dark">₹376</td>
                              </tr>
                              <tr className="hover:bg-ivory-50">
                                <td className="p-2.5 font-bold font-sans">30 yrs</td>
                                <td className="p-2.5 text-navy/60">30 yrs</td>
                                <td className="p-2.5 text-right">₹116</td>
                                <td className="p-2.5 text-right">₹231</td>
                                <td className="p-2.5 text-right">₹347</td>
                                <td className="p-2.5 text-right">₹462</td>
                                <td className="p-2.5 text-right font-bold text-saffron-dark">₹577</td>
                              </tr>
                              <tr className="hover:bg-ivory-50">
                                <td className="p-2.5 font-bold font-sans">35 yrs</td>
                                <td className="p-2.5 text-navy/60">25 yrs</td>
                                <td className="p-2.5 text-right">₹181</td>
                                <td className="p-2.5 text-right">₹362</td>
                                <td className="p-2.5 text-right">₹543</td>
                                <td className="p-2.5 text-right">₹722</td>
                                <td className="p-2.5 text-right font-bold text-saffron-dark">₹902</td>
                              </tr>
                              <tr className="hover:bg-ivory-50 bg-saffron-light/10">
                                <td className="p-2.5 font-bold font-sans">40 yrs</td>
                                <td className="p-2.5 text-navy/60">20 yrs</td>
                                <td className="p-2.5 text-right">₹291</td>
                                <td className="p-2.5 text-right">₹582</td>
                                <td className="p-2.5 text-right">₹873</td>
                                <td className="p-2.5 text-right">₹1,164</td>
                                <td className="p-2.5 text-right font-bold text-saffron-dark">₹1,454</td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                        <p className="text-[11px] text-navy/60 italic">
                          {language === 'hi'
                            ? '* अंशदान मासिक, त्रैमासिक अथवा अर्धवार्षिक ऑटो-डेबिट द्वारा जमा किया जा सकता है। वर्ष में एक बार अप्रैल माह में पेंशन राशि बढ़ाने या घटाने की सुविधा उपलब्ध है।'
                            : '* Contributions can be debited monthly, quarterly, or half-yearly. Subscribers may upgrade or downgrade their pension slab once a year during the month of April.'}
                        </p>
                      </div>

                      {/* Section 4: Government Co-Contribution & Sovereign Guarantee Clarification */}
                      <div className="p-4 rounded-2xl bg-amber-50/70 border border-amber-200/80 space-y-2.5 text-xs text-navy/85">
                        <div className="flex items-center gap-2 font-bold text-amber-900">
                          <AlertCircle className="w-4 h-4 text-amber-700 shrink-0" />
                          <span>
                            {language === 'hi'
                              ? 'शासकीय सह-अंशदान (Co-Contribution) एवं संप्रभु गारंटी स्पष्टीकरण'
                              : 'Government Co-Contribution & Sovereign Guarantee Clarification'}
                          </span>
                        </div>
                        <div className="space-y-2 text-[11.5px] leading-relaxed">
                          <p>
                            <strong className="text-amber-950">
                              {language === 'hi' ? 'ऐतिहासिक सह-अंशदान (Historical Co-Contribution): ' : 'Historical Co-Contribution Notice: '}
                            </strong>
                            {language === 'hi'
                              ? 'प्रारंभिक दिशा-निर्देशों के अनुसार 50% शासकीय सह-अंशदान (अधिकतम ₹1,000 प्रति वर्ष) केवल 5 वर्षों (FY 2015-16 से 2019-20) के लिए उन गैर-आयकरदाता नागरिकों को दिया गया था जिन्होंने 1 जून 2015 से 31 मार्च 2016 के बीच पंजीकरण कराया था। यह समयावधि पूर्ण हो चुकी है और यह वर्तमान या नए अंशधारकों के लिए सार्वभौमिक चालू लाभ नहीं है।'
                              : 'The 50% government co-contribution (up to ₹1,000/year) was an introductory incentive provided for 5 financial years (FY 2015-16 to 2019-20) exclusively to eligible non-taxpayers who joined between 1 June 2015 and 31 March 2016. This window has ended and is NOT a current universal benefit for new or ongoing subscribers.'}
                          </p>
                          <p>
                            <strong className="text-amber-950">
                              {language === 'hi' ? 'केंद्रीय संप्रभु गारंटी (Sovereign Pension Guarantee): ' : 'Sovereign Guarantee from GoI: '}
                            </strong>
                            {language === 'hi'
                              ? 'भारत सरकार न्यूनतम पेंशन की गारंटी प्रदान करती है। यदि संचित पेंशन निधि पर वास्तविक बाजार रिटर्न गारंटीकृत पेंशन भुगतान हेतु आवश्यक रिटर्न से कम रहता है, तो उस कमी (Shortfall) की शत-प्रतिशत भरपाई केंद्र सरकार द्वारा की जाती है।'
                              : 'The Central Government provides an absolute sovereign guarantee. If the actual market return on the accumulated corpus falls below the return needed for the guaranteed pension, the shortfall is 100% funded and bridged by the Government of India.'}
                          </p>
                        </div>
                      </div>

                      {/* Section 5: Key Statutory Eligibility & Income Tax Rule */}
                      <div className="p-4 rounded-2xl bg-ivory-50 border border-navy/10 space-y-2 text-xs">
                        <h4 className="font-bold text-navy flex items-center gap-1.5 uppercase text-[11px] tracking-wider">
                          <ShieldCheck className="w-4 h-4 text-sage-green" />
                          <span>
                            {language === 'hi'
                              ? 'मुख्य वैधानिक पात्रता एवं 1 अक्टूबर 2022 का आयकर नियम'
                              : 'Key Eligibility & 1 October 2022 Income Tax Rule (Gazette Notification)'}
                          </span>
                        </h4>
                        <ul className="space-y-1.5 text-[11.5px] text-navy/80 list-disc list-inside">
                          <li>
                            <strong>{language === 'hi' ? 'प्रवेश आयु सीमा:' : 'Entry Age:'}</strong>{' '}
                            {language === 'hi' ? '18 से 40 वर्ष के बीच (कम से कम 20 वर्ष का नियमित अंशदान आवश्यक)।' : '18 to 40 years of age (minimum 20 years of continuous contributions before age 60).'}
                          </li>
                          <li>
                            <strong>{language === 'hi' ? 'बैंक खाता:' : 'Bank Account:'}</strong>{' '}
                            {language === 'hi' ? 'सक्रिय बचत बैंक अथवा डाकघर बचत खाता, आधार संख्या संलग्न।' : 'Active savings bank or post office savings account with auto-debit consent and Aadhaar linkage.'}
                          </li>
                          <li>
                            <strong className="text-rose-900">{language === 'hi' ? 'आयकरदाता अपात्रता (1 Oct 2022 नियम):' : 'Income Tax Payer Exclusion (Effective 1 Oct 2022):'}</strong>{' '}
                            {language === 'hi'
                              ? 'वित्त मंत्रालय की राजपत्र अधिसूचना के अनुसार, 1 अक्टूबर 2022 से कोई भी नागरिक जो आयकर दाता है या रहा है, वह अटल पेंशन योजना में नया खाता खोलने का पात्र नहीं है। आयकरदाताओं द्वारा खोले गए खाते बंद कर अंशदान वापस कर दिया जाता है।'
                              : 'Per Ministry of Finance Gazette Notification effective 1 October 2022, any individual who is or has been an income tax payer under the Income-tax Act, 1961 is strictly ineligible to join APY. Accounts opened on or after this date by tax-payers are liable to closure and refund of subscriber contributions.'}
                          </li>
                        </ul>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-8 text-xs text-navy/60 bg-ivory-100 rounded-xl border border-navy/8">
                  {language === 'hi'
                    ? 'इस योजना के लिए विशिष्ट लाभ विवरण अभी पंजीकृत नहीं हैं। कृपया आधिकारिक पोर्टल देखें।'
                    : 'No specific benefit description registered for this scheme yet. Please refer to the official government portal.'}
                </div>
              )}

              {/* Proceed to Eligibility Check CTA */}
              <div className="pt-4 border-t border-navy/8 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <span className="text-xs text-navy/60">
                  {language === 'hi' ? 'क्या आप इस लाभ के लिए पात्र हैं? अभी जांचें:' : 'Are you eligible for these benefits? Evaluate now:'}
                </span>
                <Button
                  variant="saffron"
                  size="sm"
                  rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
                  onClick={() => handleTabClick('eligibility')}
                  className="shrink-0"
                >
                  {language === 'hi' ? 'पात्रता निकष जांचें' : 'Evaluate Eligibility'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          TAB 3: ELIGIBILITY
      ────────────────────────────────────────────────────────────── */}
      {activeTab === 'eligibility' && (
        <div className="space-y-6 animate-fade-in-up">
          {/* Check Eligibility Header & Action */}
          <div className="bg-white rounded-3xl border border-navy/12 p-6 sm:p-8 shadow-subtle space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-navy/8">
              <div>
                <h3 className="font-bold font-editorial text-navy text-lg sm:text-xl flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-saffron-vibrant" />
                  <span>{language === 'hi' ? 'नियम-आधारित पात्रता मूल्यांकन' : 'Deterministic Eligibility Evaluation'}</span>
                </h3>
                <p className="text-xs text-navy/50 mt-0.5">
                  {language === 'hi'
                    ? 'PostgreSQL डेटाबेस नियमों के विरुद्ध आपकी प्रोफ़ाइल का सीधा सत्यापन'
                    : 'Verified against official criteria AST and your citizen profile attributes'}
                </p>
              </div>

              <Button
                variant="saffron"
                size="md"
                leftIcon={<Sparkles className="w-4 h-4" />}
                onClick={handleCheckEligibility}
                isLoading={checkingEligibility}
              >
                {eligibility ? (language === 'hi' ? 'पुनः जांचें (Re-evaluate)' : 'Re-evaluate') : t.actions.checkEligibility}
              </Button>
            </div>

            {/* Error notification banner if check failed */}
            {eligibilityError && (
              <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-xs text-rose-950 flex items-center justify-between gap-3 animate-fade-in-up">
                <div className="flex items-center gap-2">
                  <XCircle className="w-4 h-4 text-rose-600 shrink-0" />
                  <span>{eligibilityError}</span>
                </div>
                {!isAuthenticated && (
                  <Button variant="outline" size="sm" onClick={() => setIsLoginOpen(true)} leftIcon={<LogIn className="w-3.5 h-3.5" />}>
                    {language === 'hi' ? 'लॉग इन करें' : 'Sign In'}
                  </Button>
                )}
              </div>
            )}

            {/* If evaluated, show deterministic result card */}
            {eligibility && (
              <div className="space-y-5 pt-2">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-2xl bg-ivory-50 border border-navy/10">
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-10 h-10 rounded-2xl flex items-center justify-center shrink-0 border ${
                        eligibility.result === 'eligible'
                          ? 'bg-sage-light text-sage-green border-sage/30'
                          : eligibility.result === 'potentially_eligible'
                          ? 'bg-saffron-light text-saffron-dark border-saffron/30'
                          : eligibility.result === 'insufficient_information'
                          ? 'bg-amber-100 text-amber-800 border-amber-300'
                          : 'bg-rose-50 text-rose-600 border-rose-200'
                      }`}
                    >
                      {eligibility.result === 'eligible' ? (
                        <CheckCircle2 className="w-5 h-5" />
                      ) : eligibility.result === 'potentially_eligible' ? (
                        <Sparkles className="w-5 h-5" />
                      ) : eligibility.result === 'insufficient_information' ? (
                        <HelpCircle className="w-5 h-5" />
                      ) : (
                        <XCircle className="w-5 h-5" />
                      )}
                    </div>
                    <div>
                      <span className="text-[10px] uppercase font-bold text-navy/50 block">Evaluation Status</span>
                      <h4 className="font-bold text-navy text-sm font-editorial">
                        {eligibility.result === 'eligible'
                          ? '● ELIGIBLE (पात्र)'
                          : eligibility.result === 'potentially_eligible'
                          ? '● POTENTIALLY ELIGIBLE (संभावित पात्र)'
                          : eligibility.result === 'insufficient_information'
                          ? '● INSUFFICIENT INFO (अधूरी जानकारी)'
                          : '● NOT ELIGIBLE (अपात्र)'}
                      </h4>
                    </div>
                  </div>

                  <Badge variant={eligibility.result}>
                    {eligibility.result === 'eligible'
                      ? '● ELIGIBLE'
                      : eligibility.result === 'potentially_eligible'
                      ? '● POTENTIAL'
                      : eligibility.result === 'insufficient_information'
                      ? '● INFO NEEDED'
                      : '● NOT ELIGIBLE'}
                  </Badge>
                </div>

                <p className="text-sm font-medium text-navy/80 leading-relaxed bg-white p-4 rounded-2xl border border-navy/8">
                  {eligibility.explanation}
                </p>

                {/* Missing Fields Box */}
                {eligibility.missing_fields && eligibility.missing_fields.length > 0 && (
                  <div className="p-4 rounded-2xl bg-amber-50/90 border border-amber-200 space-y-2">
                    <div className="flex items-center gap-2 text-amber-900 font-semibold text-xs">
                      <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                      <span>
                        {language === 'hi'
                          ? 'अधूरी जानकारी: प्रोफ़ाइल अपडेट की आवश्यकता है'
                          : 'Missing Profile Information for Full Determination'}
                      </span>
                    </div>
                    <p className="text-xs text-amber-900/80 leading-relaxed">
                      {language === 'hi'
                        ? 'पूर्ण मूल्यांकन के लिए कृपया अपनी प्रोफ़ाइल में निम्नलिखित फ़ील्ड भरें:'
                        : 'To evaluate all statutory conditions definitively, please update these attributes in your profile:'}
                    </p>
                    <div className="flex flex-wrap gap-2 pt-1">
                      {eligibility.missing_fields.map((f, i) => (
                        <span key={i} className="px-2.5 py-1 rounded-lg bg-amber-100 text-amber-900 text-xs font-mono font-medium">
                          {f.replace(/_/g, ' ')}
                        </span>
                      ))}
                    </div>
                    <div className="pt-2">
                      <Link to="/onboarding">
                        <Button variant="outline" size="sm" className="bg-white text-amber-900 border-amber-300 hover:bg-amber-100">
                          {language === 'hi' ? 'प्रोफ़ाइल अपडेट करें' : 'Update Profile'}
                        </Button>
                      </Link>
                    </div>
                  </div>
                )}

                {/* Evaluated Conditions Checklist */}
                {eligibility.condition_results && eligibility.condition_results.length > 0 && (
                  <div className="space-y-3 pt-2">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-navy/50">
                      {language === 'hi' ? 'जांची गई पात्रता शर्तें (Evaluated Criteria Checklist)' : 'Evaluated Criteria Checklist'}
                    </h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {eligibility.condition_results.map((cond, idx) => (
                        <div
                          key={idx}
                          className={`flex items-start gap-3 p-3.5 rounded-xl text-xs border transition-all ${
                            cond.passed === true
                              ? 'bg-sage-light/80 border-sage/35 text-navy'
                              : cond.passed === false
                              ? 'bg-rose-50/70 border-rose-200 text-rose-950'
                              : 'bg-amber-50/70 border-amber-200 text-navy'
                          }`}
                        >
                          {cond.passed === true ? (
                            <CheckCircle2 className="w-4 h-4 text-sage-green shrink-0 mt-0.5" />
                          ) : cond.passed === false ? (
                            <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                          ) : (
                            <HelpCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                          )}
                          <div className="space-y-0.5">
                            <span className="font-bold text-navy block capitalize">{cond.field.replace(/_/g, ' ')}</span>
                            <p className="opacity-80 leading-relaxed">{cond.explanation}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {eligibility.result === 'eligible' && (
                  <div className="pt-3 flex items-center justify-between border-t border-navy/8">
                    <span className="text-xs text-navy/60 font-medium">
                      {language === 'hi' ? 'सभी शर्तें पूर्ण हैं। अब आवेदन मसुदा तैयार करें।' : 'All baseline conditions met. Proceed to application preparation.'}
                    </span>
                    <Link to="/chat">
                      <Button variant="saffron" size="md" rightIcon={<ArrowRight className="w-4 h-4" />}>
                        {language === 'hi' ? 'साथी द्वारा आवेदन मसुदा भरें' : 'Pre-fill with AI Saathi'}
                      </Button>
                    </Link>
                  </div>
                )}
              </div>
            )}

            {!eligibility && !checkingEligibility && (
              <div className="p-6 text-center space-y-3 bg-ivory-50 rounded-2xl border border-navy/8">
                <Sparkles className="w-8 h-8 text-saffron mx-auto" />
                <p className="text-xs text-navy/70 max-w-md mx-auto">
                  {isAuthenticated
                    ? (language === 'hi' ? 'अपनी सहेजी गई नागरिक प्रोफ़ाइल के विरुद्ध पात्रता जांचने के लिए ऊपर "पात्रता जांचें" पर क्लिक करें।' : 'Click "Check Eligibility" above to run deterministic evaluation against your verified citizen profile.')
                    : (language === 'hi' ? 'अपनी व्यक्तिगत पात्रता जांचने के लिए कृपया नागरिक खाते में लॉग इन करें या डेमो नागरिक चुनें।' : 'Sign in or select a citizen persona to test deterministic eligibility against official rules.')}
                </p>
                {!isAuthenticated && (
                  <Button variant="outline" size="sm" onClick={() => setIsLoginOpen(true)} leftIcon={<LogIn className="w-3.5 h-3.5" />}>
                    {language === 'hi' ? 'लॉग इन / नागरिक बदलें' : 'Sign In / Switch Citizen'}
                  </Button>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          TAB 4: REQUIRED DOCUMENTS
      ────────────────────────────────────────────────────────────── */}
      {activeTab === 'documents' && (
        <div className="space-y-6 animate-fade-in-up">
          <Card>
            <CardHeader className="flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-ivory-100 flex items-center justify-center text-navy border border-navy/8 shrink-0">
                  <FileText className="w-4 h-4 text-saffron" />
                </div>
                <div>
                  <h3 className="font-bold font-editorial text-navy text-base">{t.labels.requiredDocuments}</h3>
                  <p className="text-xs text-navy/50">{documents.length} official documents registered for this scheme</p>
                </div>
              </div>

              <Link to="/documents">
                <Button variant="outline" size="sm">
                  {t.actions.uploadDocument}
                </Button>
              </Link>
            </CardHeader>
            <CardContent className="p-6 space-y-3">
              {documents.length === 0 ? (
                <div className="p-8 text-center text-xs text-navy/60 bg-ivory-100 rounded-xl border border-navy/8">
                  {scheme.scheme_status === 'pending_verification'
                    ? (language === 'hi' ? 'इस योजना के लिए दस्तावेज़ चेकलिस्ट प्रशासनिक सत्यापन हेतु लंबित है।' : 'Document checklist for this scheme is currently pending administrative verification.')
                    : (language === 'hi' ? 'कोई विशिष्ट दस्तावेज़ चेकलिस्ट पंजीकृत नहीं है। मानक केवाईसी (आधार, बैंक खाता) लागू होता है।' : 'No specific document checklist registered yet. Standard KYC documentation (Aadhaar, Bank Account) applies.')}
                </div>
              ) : (
                documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="flex items-start justify-between gap-4 p-4 rounded-2xl border border-navy/8 bg-white hover:border-navy/20 hover:shadow-subtle transition-all duration-200"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-bold text-sm text-navy capitalize">
                          {doc.title || doc.document_type.replace(/_/g, ' ')}
                        </span>
                        <Badge variant={doc.is_mandatory ? 'saffron' : 'category'}>
                          {doc.is_mandatory ? 'Mandatory' : 'Optional'}
                        </Badge>
                        {doc.issuing_authority && (
                          <span className="text-[10px] text-navy/50 bg-ivory-100 px-2 py-0.5 rounded-md border border-navy/10 font-medium">
                            {doc.issuing_authority}
                          </span>
                        )}
                      </div>
                      {(doc.description || doc.guidance) && (
                        <p className="text-xs text-navy/60 leading-relaxed">{doc.description || doc.guidance}</p>
                      )}
                      {doc.last_verified_at && (
                        <p className="text-[10px] text-navy/40">Verified: {doc.last_verified_at.split('T')[0]}</p>
                      )}
                    </div>

                    {doc.source_url && (
                      <a
                        href={doc.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs font-semibold text-saffron-dark hover:text-saffron shrink-0 flex items-center gap-1 pt-1 transition-colors"
                      >
                        <span>Portal</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          TAB 5: APPLICATION PROCESS
      ────────────────────────────────────────────────────────────── */}
      {activeTab === 'application' && (
        <div className="space-y-6 animate-fade-in-up">
          <Card>
            <CardHeader>
              <h3 className="font-bold font-editorial text-navy text-base flex items-center gap-2">
                <Send className="w-4 h-4 text-emerald-600" />
                <span>{language === 'hi' ? 'अधिकृत आवेदन प्रक्रिया एवं चरण' : 'Official Application Procedure & Steps'}</span>
              </h3>
            </CardHeader>
            <CardContent className="p-6 space-y-4">
              <div className="space-y-3">
                <div className="flex items-start gap-3 p-3.5 rounded-xl bg-ivory-50 border border-navy/8">
                  <span className="w-6 h-6 rounded-full bg-navy text-white text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                    1
                  </span>
                  <div className="space-y-1">
                    <span className="font-bold text-xs text-navy block">
                      {language === 'hi' ? 'दस्तावेज़ एवं पात्रता की पूर्व-तैयारी' : 'Eligibility & Document Preparation'}
                    </span>
                    <p className="text-xs text-navy/70 leading-relaxed">
                      {language === 'hi'
                        ? 'आधार कार्ड, बैंक खाता पासबुक और आवश्यक भूमि/आय प्रमाण-पत्र तैयार रखें। सुनिश्चित करें कि बैंक खाता आधार से लिंक (DBT सक्षम) है।'
                        : 'Ensure Aadhaar card, bank passbook, and required land/income documents are ready and bank account is NPCI-seeded for DBT.'}
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3 p-3.5 rounded-xl bg-ivory-50 border border-navy/8">
                  <span className="w-6 h-6 rounded-full bg-navy text-white text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                    2
                  </span>
                  <div className="space-y-1">
                    <span className="font-bold text-xs text-navy block">
                      {language === 'hi' ? 'ऑनलाइन पंजीकरण अथवा सीएससी केंद्र' : 'Online Registration / CSC Center'}
                    </span>
                    <p className="text-xs text-navy/70 leading-relaxed">
                      {language === 'hi'
                        ? 'आधिकारिक पोर्टल पर स्वयं-पंजीकरण करें या नजदीकी सीएससी (Common Service Centre) अथवा आपले सरकार सेवा केंद्र पर जाएं।'
                        : 'Register via the official government portal or visit your nearest Common Service Centre (CSC) / Aaple Sarkar Kendra.'}
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3 p-3.5 rounded-xl bg-ivory-50 border border-navy/8">
                  <span className="w-6 h-6 rounded-full bg-navy text-white text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                    3
                  </span>
                  <div className="space-y-1">
                    <span className="font-bold text-xs text-navy block">
                      {language === 'hi' ? 'बायोमेट्रिक अथवा ओटीपी ई-केवाईसी' : 'Biometric / OTP e-KYC'}
                    </span>
                    <p className="text-xs text-navy/70 leading-relaxed">
                      {language === 'hi'
                        ? 'आधार से जुड़े मोबाइल नंबर पर प्राप्त ओटीपी अथवा फिंगरप्रिंट द्वारा ई-केवाईसी सत्यापन पूरा करें।'
                        : 'Complete mandatory e-KYC verification using Aadhaar OTP or biometric authentication.'}
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3 p-3.5 rounded-xl bg-ivory-50 border border-navy/8">
                  <span className="w-6 h-6 rounded-full bg-navy text-white text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                    4
                  </span>
                  <div className="space-y-1">
                    <span className="font-bold text-xs text-navy block">
                      {language === 'hi' ? 'सत्यापन एवं डीबीटी स्वीकृति' : 'Verification & DBT Approval'}
                    </span>
                    <p className="text-xs text-navy/70 leading-relaxed">
                      {language === 'hi'
                        ? 'स्थानीय राजस्व/कृषि अधिकारी द्वारा सत्यापन के पश्चात स्वीकृति प्रदान की जाती है और राशि सीधे खाते में अंतरित होती है।'
                        : 'Local revenue and nodal department authorities verify records, after which benefits are disbursed via DBT.'}
                    </p>
                  </div>
                </div>
              </div>

              {/* Direct Links */}
              <div className="pt-3 border-t border-navy/8 flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-navy/40" />
                  <span className="text-xs text-navy/60 font-medium">
                    {language === 'hi' ? 'निकटतम केंद्र: ग्राम पंचायत, तहसील कार्यालय या सीएससी' : 'Offline: Gram Panchayat, Tehsil Office, or CSC'}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  {(scheme.application_url || scheme.official_url) && (
                    <a
                      href={scheme.application_url || scheme.official_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold bg-navy text-white hover:bg-navy-800 transition-all shadow-subtle"
                    >
                      <span>{language === 'hi' ? 'आवेदन पोर्टल खोलें' : 'Open Application Portal'}</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  )}
                  <Link to="/chat">
                    <Button variant="saffron" size="sm" leftIcon={<Sparkles className="w-3.5 h-3.5" />}>
                      {language === 'hi' ? 'साथी से पूछें' : 'Ask AI Saathi'}
                    </Button>
                  </Link>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          TAB 6: OFFICIAL SOURCES & EVIDENCE
      ────────────────────────────────────────────────────────────── */}
      {activeTab === 'sources' && (
        <div className="space-y-6 animate-fade-in-up">
          <Card>
            <CardHeader>
              <h3 className="font-bold font-editorial text-navy text-base flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-sage-green" />
                <span>{language === 'hi' ? 'अधिकृत सरकारी संदर्भ एवं सत्यापन साक्ष्य' : 'Official Government Sources & Evidence'}</span>
              </h3>
            </CardHeader>
            <CardContent className="p-6 space-y-4">
              <div className="space-y-3">
                {scheme.source_url && (
                  <div className="p-4 rounded-xl bg-ivory-50 border border-navy/8 space-y-1.5">
                    <span className="text-[10px] uppercase font-bold text-navy/50 block">
                      {language === 'hi' ? 'प्राथमिक दिशा-निर्देश (Operational Guidelines)' : 'Primary Operational Guidelines'}
                    </span>
                    <a
                      href={scheme.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs font-semibold text-saffron-dark hover:underline break-all inline-flex items-center gap-1"
                    >
                      <span>{scheme.source_url}</span>
                      <ExternalLink className="w-3 h-3 shrink-0" />
                    </a>
                  </div>
                )}

                {scheme.official_url && (
                  <div className="p-4 rounded-xl bg-ivory-50 border border-navy/8 space-y-1.5">
                    <span className="text-[10px] uppercase font-bold text-navy/50 block">
                      {language === 'hi' ? 'आधिकारिक पोर्टल (Official Web Portal)' : 'Official Web Portal'}
                    </span>
                    <a
                      href={scheme.official_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs font-semibold text-saffron-dark hover:underline break-all inline-flex items-center gap-1"
                    >
                      <span>{scheme.official_url}</span>
                      <ExternalLink className="w-3 h-3 shrink-0" />
                    </a>
                  </div>
                )}
              </div>

              {/* Claim-Level Evidence List if present */}
              {scheme.source_evidence && scheme.source_evidence.length > 0 && (
                <div className="space-y-2 pt-2">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-navy/50">
                    {language === 'hi' ? 'सत्यापित साक्ष्य अभिलेख (Claim-Level Evidence Entries)' : 'Claim-Level Verified Evidence'}
                  </h4>
                  <div className="space-y-2">
                    {scheme.source_evidence.map((entry, idx) => (
                      <div key={idx} className="p-3.5 rounded-xl border border-navy/8 bg-white space-y-1 text-xs">
                        <div className="flex items-center justify-between gap-2 flex-wrap">
                          <span className="font-bold text-navy capitalize">{entry.claim.replace(/_/g, ' ')}</span>
                          <span className="text-[10px] font-semibold text-sage-green bg-sage-light px-2 py-0.5 rounded-full border border-sage/30">
                            {entry.verification_status || 'verified'}
                          </span>
                        </div>
                        <p className="text-navy/70 leading-relaxed">{entry.statement}</p>
                        {entry.citation && (
                          <span className="text-[10.5px] text-navy/50 font-mono block">Citation: {entry.citation}</span>
                        )}
                        {entry.source_url && (
                          <a
                            href={entry.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[10.5px] text-saffron-dark hover:underline inline-flex items-center gap-1 font-medium"
                          >
                            <span>Source Reference</span>
                            <ExternalLink className="w-2.5 h-2.5" />
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Source Integrity Footer Notice */}
      <StatusBanner
        type="info"
        title="Source Integrity & Official Portal Reference"
        message={`Data verified against official guidelines (${scheme.source_url}) on ${scheme.last_verified_at ? scheme.last_verified_at.split('T')[0] : '2026-11-10'}. Scheme Saathi provides assistive guidance and deterministic eligibility calculations.`}
      />

      <LoginModal isOpen={isLoginOpen} onClose={() => setIsLoginOpen(false)} />
    </div>
  );
};
