import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
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
} from 'lucide-react';

export const SchemeDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { t, language } = useLanguage();
  const { profile, isAuthenticated, token } = useAuth();

  const [scheme, setScheme] = useState<Scheme | null>(null);
  const [eligibility, setEligibility] = useState<EligibilityResult | null>(null);
  const [documents, setDocuments] = useState<DocumentRequirement[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [checkingEligibility, setCheckingEligibility] = useState<boolean>(false);
  const [eligibilityError, setEligibilityError] = useState<string | null>(null);
  const [isLoginOpen, setIsLoginOpen] = useState<boolean>(false);

  useEffect(() => {
    const loadData = async () => {
      if (!id) return;
      setLoading(true);
      try {
        const s = await schemeService.getSchemeById(id);
        setScheme(s);
        let docs: DocumentRequirement[] = (s as any)?.documents || [];
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
    return <Spinner size="lg" label={language === 'hi' ? 'योजना विवरण लोड हो रहा है...' : 'Loading scheme details...'} />;
  }

  if (!scheme) {
    return (
      <div className="text-center py-16 space-y-4">
        <p className="text-navy/60">{language === 'hi' ? 'योजना प्राप्त नहीं हुई।' : 'Scheme not found.'}</p>
        <Button variant="outline" onClick={() => navigate('/schemes')}>
          {language === 'hi' ? 'योजना सूची पर वापस जाएं' : 'Back to Schemes'}
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-7 max-w-4xl mx-auto pb-12">
      {/* Back button */}
      <Link
        to="/schemes"
        className="inline-flex items-center gap-2 text-xs font-semibold text-navy/60 hover:text-navy transition-colors group"
      >
        <ArrowLeft className="w-4 h-4 transition-transform group-hover:-translate-x-1" />
        <span>{language === 'hi' ? 'सभी योजनाओं पर वापस जाएं' : 'Back to schemes catalog'}</span>
      </Link>

      {/* Main Scheme Hero Banner */}
      <div className="bg-white rounded-3xl border border-navy/8 p-6 sm:p-9 space-y-4 shadow-subtle relative overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2.5">
          <Badge variant="category">{scheme.category.replace(/_/g, ' ').toUpperCase()}</Badge>
          <div className="flex items-center gap-3 text-xs text-navy/60 font-medium">
            <span className="flex items-center gap-1.5 text-sage-green bg-sage-light px-2.5 py-0.5 rounded-full border border-sage/30 font-semibold">
              <ShieldCheck className="w-3.5 h-3.5" />
              {scheme.scheme_status}
            </span>
            <span className="flex items-center gap-1">
              <Calendar className="w-3.5 h-3.5 text-navy/40" />
              Verified: {scheme.last_verified_at}
            </span>
          </div>
        </div>

        <h1 className="text-2xl sm:text-4xl font-bold font-editorial text-navy leading-tight tracking-tight">
          {scheme.name}
        </h1>

        <div className="flex items-center gap-2 text-xs text-navy/70 font-semibold">
          <Building className="w-4 h-4 text-saffron shrink-0" />
          <span>{scheme.ministry}</span>
        </div>

        <p className="text-sm text-navy/70 leading-relaxed pt-1 max-w-3xl">{scheme.description}</p>

        {/* Check Eligibility / Portal Actions */}
        <div className="flex flex-wrap items-center gap-3 pt-5 border-t border-navy/8">
          <Button
            variant="saffron"
            size="md"
            leftIcon={<Sparkles className="w-4 h-4" />}
            onClick={handleCheckEligibility}
            isLoading={checkingEligibility}
          >
            {t.actions.checkEligibility}
          </Button>

          <a
            href={scheme.official_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold border border-navy/15 text-navy bg-white hover:bg-ivory-50 transition-all duration-200 shadow-subtle"
          >
            <span>{t.labels.officialPortal}</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>

        {/* Error notification banner if check failed */}
        {eligibilityError && (
          <div className="mt-4 p-4 rounded-2xl bg-rose-50 border border-rose-200 text-xs text-rose-950 flex items-center justify-between gap-3 animate-fade-in-up">
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
      </div>

      {/* Deterministic Eligibility Outcome Result */}
      {eligibility && (
        <div className="bg-white rounded-3xl border border-navy/12 p-6 sm:p-8 shadow-premium space-y-6 animate-fade-in-up">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-navy/8">
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
                <h3 className="font-bold font-editorial text-navy text-lg sm:text-xl">
                  {language === 'hi' ? 'आपकी पात्रता परिणाम' : 'Your Eligibility Result'}
                </h3>
                <p className="text-xs text-navy/50">
                  {language === 'hi'
                    ? 'सटीक नियम-आधारित मूल्यांकन (PostgreSQL Criteria AST)'
                    : 'Deterministic rule evaluation against official statutory criteria'}
                </p>
              </div>
            </div>

            <div>
              <Badge variant={eligibility.result}>
                {eligibility.result === 'eligible'
                  ? '● ELIGIBLE'
                  : eligibility.result === 'potentially_eligible'
                  ? '● POTENTIALLY ELIGIBLE'
                  : eligibility.result === 'insufficient_information'
                  ? '● INSUFFICIENT INFO'
                  : '● NOT ELIGIBLE'}
              </Badge>
            </div>
          </div>

          <p className="text-sm font-medium text-navy/80 leading-relaxed bg-ivory-100/80 p-4 rounded-2xl border border-navy/6">
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
            <div className="space-y-3">
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

          {/* Statutory limitation notice if present */}
          {eligibility.limitations && (
            <div className="p-3.5 rounded-xl bg-ivory-100 border border-navy/10 text-xs text-navy/70 leading-relaxed">
              <span className="font-semibold text-navy block mb-0.5">Statutory Evaluation Scope:</span>
              {eligibility.limitations}
            </div>
          )}

          {eligibility.result === 'eligible' && (
            <div className="pt-3 flex items-center justify-between border-t border-navy/8">
              <span className="text-xs text-navy/60 font-medium">
                {language === 'hi' ? 'सभी शर्तें पूर्ण हैं। अब आवेदन ड्राफ्ट करें।' : 'All baseline conditions met. Proceed to application preparation.'}
              </span>
              <Link to="/applications">
                <Button variant="saffron" size="md" rightIcon={<ArrowRight className="w-4 h-4" />}>
                  {t.actions.applyNow}
                </Button>
              </Link>
            </div>
          )}
        </div>
      )}

      {/* Scheme Benefits & Target Beneficiaries Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <h3 className="font-bold font-editorial text-navy text-base">{t.labels.benefits}</h3>
          </CardHeader>
          <CardContent className="p-6">
            <p className="text-sm text-navy/80 leading-relaxed font-medium bg-sage-light/60 p-4 rounded-2xl border border-sage/20">
              {scheme.benefits}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h3 className="font-bold font-editorial text-navy text-base">{t.labels.targetBeneficiaries}</h3>
          </CardHeader>
          <CardContent className="p-6">
            <p className="text-sm text-navy/80 leading-relaxed bg-ivory-100/70 p-4 rounded-2xl border border-navy/6">
              {scheme.target_beneficiaries}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Required Documents Checklist for this Scheme */}
      <Card>
        <CardHeader className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-ivory-100 flex items-center justify-center text-navy border border-navy/8">
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
            <div className="p-6 text-center text-xs text-navy/60 bg-ivory-100 rounded-xl border border-navy/8">
              {scheme.scheme_status === 'pending_verification'
                ? 'Document checklist for this scheme is currently pending administrative verification.'
                : 'No specific document checklist registered yet. Standard KYC documentation (Aadhaar, Bank Account) applies.'}
            </div>
          ) : (
            documents.map((doc) => (
              <div
                key={doc.id}
                className="flex items-start justify-between gap-4 p-4 rounded-2xl border border-navy/8 bg-white hover:border-navy/20 hover:shadow-subtle transition-all duration-200"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
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
                    <p className="text-[10px] text-navy/40">Verified: {doc.last_verified_at}</p>
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

      {/* Source Integrity Footer Notice */}
      <StatusBanner
        type="info"
        title="Source Integrity & Official Portal Reference"
        message={`Data verified against official guidelines (${scheme.source_url}) on ${scheme.last_verified_at}. Scheme Saathi provides assistive guidance and deterministic eligibility calculations.`}
      />

      <LoginModal isOpen={isLoginOpen} onClose={() => setIsLoginOpen(false)} />
    </div>
  );
};
