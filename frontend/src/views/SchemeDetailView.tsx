import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { api } from '../api/client';
import { useLanguage } from '../context/LanguageContext';
import { saveOfflineDraft } from '../utils/offlineSync';
import { SpeechPlayerButton } from '../components/SpeechPlayerButton';
import { Scheme, BeneficiaryProfile, EligibilityResult } from '../types';
import {
  ArrowLeft,
  ExternalLink,
  ShieldCheck,
  Building2,
  FileText,
  CheckCircle2,
  XCircle,
  HelpCircle,
  FolderPlus,
  Loader2,
  AlertCircle,
} from 'lucide-react';

export const SchemeDetailView: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { t, language } = useLanguage();

  const [scheme, setScheme] = useState<Scheme | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Beneficiaries list for eligibility checking
  const [beneficiaries, setBeneficiaries] = useState<BeneficiaryProfile[]>([]);
  const [selectedBeneficiaryId, setSelectedBeneficiaryId] = useState<string>('');

  // Eligibility evaluation state
  const [evaluating, setEvaluating] = useState(false);
  const [eligibilityResult, setEligibilityResult] = useState<EligibilityResult | null>(null);
  const [evalError, setEvalError] = useState<string | null>(null);

  // Application creation state
  const [creatingApp, setCreatingApp] = useState(false);
  const [appSuccessMessage, setAppSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    if (id) {
      loadScheme(id);
      loadBeneficiaries();
    }
  }, [id]);

  const loadScheme = async (schemeId: string) => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.schemes.get(schemeId);
      setScheme(data);
    } catch (err: any) {
      const cached = localStorage.getItem('scheme_saathi_cached_schemes');
      if (cached) {
        try {
          const list = JSON.parse(cached);
          const found = list.find((s: any) => s.id === schemeId);
          if (found) {
            setScheme(found);
            return;
          }
        } catch {
          // ignore cache parse error
        }
      }
      setError(err?.response?.data?.message || 'Failed to load scheme details');
    } finally {
      setLoading(false);
    }
  };

  const loadBeneficiaries = async () => {
    try {
      const list = await api.beneficiaries.list();
      setBeneficiaries(list);
    } catch {
      // Non-blocking
    }
  };

  const handleEvaluateEligibility = async () => {
    if (!scheme) return;
    try {
      setEvaluating(true);
      setEvalError(null);
      const result = await api.eligibility.evaluate(
        scheme.id,
        selectedBeneficiaryId ? selectedBeneficiaryId : null
      );
      setEligibilityResult(result);
    } catch (err: any) {
      setEvalError(err?.response?.data?.message || 'Eligibility check failed');
    } finally {
      setEvaluating(false);
    }
  };

  const handleCreateApplication = async () => {
    if (!scheme) return;
    try {
      setCreatingApp(true);
      if (!navigator.onLine) {
        // Offline: save draft locally
        saveOfflineDraft(scheme.id, selectedBeneficiaryId ? selectedBeneficiaryId : null);
        setAppSuccessMessage(
          language === 'hi'
            ? 'ऑफ़लाइन ड्राफ्ट सहेजा गया — इंटरनेट कनेक्ट होते ही स्वचालित सिंक होगा!'
            : 'Offline draft saved — will automatically sync when online!'
        );
        setTimeout(() => {
          navigate('/applications');
        }, 1200);
        return;
      }

      const draft = await api.applications.createDraft(
        scheme.id,
        selectedBeneficiaryId ? selectedBeneficiaryId : null
      );
      setAppSuccessMessage(
        language === 'hi'
          ? `आवेदन ड्राफ्ट सफलतापूर्वक तैयार किया गया!`
          : `Application draft created successfully!`
      );
      setTimeout(() => {
        navigate(`/applications?id=${draft.id}`);
      }, 1200);
    } catch (err: any) {
      if (!navigator.onLine || err.message === 'Network Error') {
        saveOfflineDraft(scheme.id, selectedBeneficiaryId ? selectedBeneficiaryId : null);
        setAppSuccessMessage(
          language === 'hi'
            ? 'ऑफ़लाइन ड्राफ्ट सहेजा गया — इंटरनेट कनेक्ट होते ही स्वचालित सिंक होगा!'
            : 'Offline draft saved — will automatically sync when online!'
        );
        setTimeout(() => {
          navigate('/applications');
        }, 1200);
      } else {
        setEvalError(err?.response?.data?.message || 'Failed to create application draft');
      }
    } finally {
      setCreatingApp(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-20">
        <Loader2 className="w-8 h-8 text-emerald-600 animate-spin" />
      </div>
    );
  }

  if (error || !scheme) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
          <AlertCircle className="w-10 h-10 text-red-500 mx-auto mb-3" />
          <h2 className="text-lg font-bold text-red-800">
            {language === 'hi' ? 'योजना लोड करने में त्रुटि' : 'Scheme Not Found'}
          </h2>
          <p className="text-red-600 mt-1">{error || 'Scheme could not be located.'}</p>
          <button
            onClick={() => navigate('/schemes')}
            className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700"
          >
            {language === 'hi' ? 'योजना सूची पर वापस जाएं' : 'Back to Schemes'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 pb-24 space-y-6">
      {/* Top Breadcrumb / Back */}
      <div className="flex items-center justify-between">
        <Link
          to="/schemes"
          className="inline-flex items-center text-sm font-medium text-slate-600 hover:text-emerald-700 transition"
        >
          <ArrowLeft className="w-4 h-4 mr-1.5" />
          {language === 'hi' ? 'सभी योजनाएं' : 'Back to All Schemes'}
        </Link>
        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          <ShieldCheck className="w-3.5 h-3.5 mr-1" />
          {t('schemes.verified_badge')}
        </span>
      </div>

      {/* Scheme Header Card */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
        <div className="flex flex-wrap items-center gap-2 mb-2">
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wide bg-emerald-100 text-emerald-800">
            {scheme.scheme_code}
          </span>
          <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700 capitalize">
            {scheme.category}
          </span>
        </div>

        <div className="flex items-start justify-between gap-3">
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 leading-tight">
            {scheme.name}
          </h1>
          <SpeechPlayerButton
            text={`${scheme.name}. ${scheme.description}. ${scheme.benefits_summary || ''}`}
            size="md"
          />
        </div>
        {scheme.short_title && (
          <p className="text-sm font-semibold text-emerald-700 mt-1">{scheme.short_title}</p>
        )}

        <div className="flex items-center text-xs text-slate-500 mt-2">
          <Building2 className="w-3.5 h-3.5 mr-1 text-slate-400" />
          <span>{scheme.ministry}</span>
        </div>

        <p className="mt-4 text-slate-700 text-sm sm:text-base leading-relaxed">
          {scheme.description}
        </p>

        {/* Benefits Box */}
        {scheme.benefits_summary && (
          <div className="mt-5 p-4 bg-emerald-50/70 border border-emerald-200/80 rounded-xl">
            <h3 className="text-xs font-bold uppercase tracking-wider text-emerald-900 mb-1">
              {language === 'hi' ? 'मुख्य लाभ' : 'Key Benefits & Entitlements'}
            </h3>
            <p className="text-sm text-emerald-950 font-medium leading-relaxed">
              {scheme.benefits_summary}
            </p>
          </div>
        )}

        {/* External Portal & Action Buttons */}
        <div className="mt-6 flex flex-wrap gap-3 pt-4 border-t border-slate-100">
          <a
            href={scheme.official_portal_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center px-4 py-2.5 rounded-xl border border-slate-300 text-slate-700 bg-white hover:bg-slate-50 text-sm font-medium transition shadow-sm"
          >
            <span>{t('schemes.official_portal')}</span>
            <ExternalLink className="w-4 h-4 ml-2 text-slate-400" />
          </a>
          <button
            onClick={handleCreateApplication}
            disabled={creatingApp}
            className="inline-flex items-center px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold transition shadow-sm disabled:opacity-60"
          >
            {creatingApp ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <FolderPlus className="w-4 h-4 mr-2" />
            )}
            {language === 'hi' ? 'आवेदन ड्राफ्ट बनाएं' : 'Create Application Draft'}
          </button>
        </div>

        {appSuccessMessage && (
          <div className="mt-3 p-3 bg-emerald-100 text-emerald-800 rounded-lg text-sm font-medium">
            {appSuccessMessage}
          </div>
        )}
      </div>

      {/* Interactive Eligibility Evaluator */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100">
          <div>
            <h2 className="text-lg font-bold text-slate-900">{t('eligibility.title')}</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              {language === 'hi'
                ? 'अपने या परिवार के सदस्य के प्रोफ़ाइल के आधार पर तुरंत पात्रता जांचें'
                : 'Evaluate criteria based on statutory policy rules for you or a family member'}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <select
              value={selectedBeneficiaryId}
              onChange={(e) => setSelectedBeneficiaryId(e.target.value)}
              className="text-xs bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              <option value="">{language === 'hi' ? 'स्वयं (खाता धारक)' : 'Self (Account Holder)'}</option>
              {beneficiaries.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.full_name} ({b.relationship})
                </option>
              ))}
            </select>

            <button
              onClick={handleEvaluateEligibility}
              disabled={evaluating}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg transition disabled:opacity-60 flex items-center shadow-sm"
            >
              {evaluating ? (
                <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
              ) : (
                <ShieldCheck className="w-3.5 h-3.5 mr-1.5" />
              )}
              {t('schemes.btn_check_eligibility')}
            </button>
          </div>
        </div>

        {evalError && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-xs">
            {evalError}
          </div>
        )}

        {/* Evaluation Results Breakdown */}
        {eligibilityResult && (
          <div className="mt-5 space-y-4">
            <div
              className={`p-4 rounded-xl border flex items-center justify-between ${
                eligibilityResult.overall_status === 'PASS'
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                  : eligibilityResult.overall_status === 'FAIL'
                  ? 'bg-red-50 border-red-200 text-red-900'
                  : 'bg-amber-50 border-amber-200 text-amber-900'
              }`}
            >
              <div className="flex items-center space-x-3">
                {eligibilityResult.overall_status === 'PASS' && (
                  <CheckCircle2 className="w-6 h-6 text-emerald-600 flex-shrink-0" />
                )}
                {eligibilityResult.overall_status === 'FAIL' && (
                  <XCircle className="w-6 h-6 text-red-600 flex-shrink-0" />
                )}
                {eligibilityResult.overall_status === 'UNKNOWN' && (
                  <HelpCircle className="w-6 h-6 text-amber-600 flex-shrink-0" />
                )}
                <div>
                  <h4 className="font-bold text-sm">
                    {eligibilityResult.overall_status === 'PASS' && t('eligibility.eligible')}
                    {eligibilityResult.overall_status === 'FAIL' && t('eligibility.ineligible')}
                    {eligibilityResult.overall_status === 'UNKNOWN' &&
                      t('eligibility.potentially_eligible')}
                  </h4>
                  <p className="text-xs mt-0.5 opacity-90">
                    {language === 'hi'
                      ? eligibilityResult.explanation_hi
                      : eligibilityResult.explanation_en}
                  </p>
                </div>
              </div>
            </div>

            {/* Matched conditions */}
            {eligibilityResult.matched_conditions?.length > 0 && (
              <div>
                <h5 className="text-xs font-bold uppercase tracking-wider text-emerald-700 mb-2 flex items-center">
                  <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                  {t('eligibility.matched')} ({eligibilityResult.matched_conditions.length})
                </h5>
                <div className="space-y-1.5">
                  {eligibilityResult.matched_conditions.map((cond, idx) => (
                    <div
                      key={idx}
                      className="text-xs p-2.5 bg-emerald-50/50 rounded-lg border border-emerald-100 flex items-start justify-between"
                    >
                      <span className="font-medium text-emerald-950">
                        {language === 'hi'
                          ? cond.description_hi || cond.field
                          : cond.description_en || cond.field}
                      </span>
                      <span className="text-[11px] font-semibold text-emerald-700 uppercase">
                        PASS
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Failed conditions */}
            {eligibilityResult.failed_conditions?.length > 0 && (
              <div>
                <h5 className="text-xs font-bold uppercase tracking-wider text-red-700 mb-2 flex items-center">
                  <XCircle className="w-3.5 h-3.5 mr-1" />
                  {t('eligibility.failed')} ({eligibilityResult.failed_conditions.length})
                </h5>
                <div className="space-y-1.5">
                  {eligibilityResult.failed_conditions.map((cond, idx) => (
                    <div
                      key={idx}
                      className="text-xs p-2.5 bg-red-50/50 rounded-lg border border-red-100 flex items-start justify-between"
                    >
                      <div>
                        <span className="font-medium text-red-950">
                          {language === 'hi'
                            ? cond.description_hi || cond.field
                            : cond.description_en || cond.field}
                        </span>
                        {cond.reason && (
                          <p className="text-[11px] text-red-600 mt-0.5">{cond.reason}</p>
                        )}
                      </div>
                      <span className="text-[11px] font-semibold text-red-700 uppercase">FAIL</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Unknown conditions & Questions */}
            {eligibilityResult.unknown_conditions?.length > 0 && (
              <div>
                <h5 className="text-xs font-bold uppercase tracking-wider text-amber-700 mb-2 flex items-center">
                  <HelpCircle className="w-3.5 h-3.5 mr-1" />
                  {t('eligibility.missing')} ({eligibilityResult.unknown_conditions.length})
                </h5>
                <div className="space-y-2">
                  {eligibilityResult.next_questions?.map((q, idx) => (
                    <div
                      key={idx}
                      className="text-xs p-3 bg-amber-50/60 rounded-lg border border-amber-200"
                    >
                      <p className="font-semibold text-amber-950">
                        {language === 'hi' ? q.question_hi : q.question_en}
                      </p>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        <Link
                          to="/profile"
                          className="px-2.5 py-1 bg-white border border-amber-300 text-amber-900 rounded font-medium hover:bg-amber-100 transition"
                        >
                          {language === 'hi' ? 'प्रोफ़ाइल अपडेट करें' : 'Update Profile to Answer'}
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Statutory Document Requirements */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div>
            <h2 className="text-lg font-bold text-slate-900">{t('schemes.documents_required')}</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              {language === 'hi'
                ? 'इस योजना के लिए आवश्यक दस्तावेज़ व स्वीकार्य विकल्प'
                : 'Statutory document checklist and acceptable alternatives for this scheme'}
            </p>
          </div>
          <Link
            to={`/documents?scheme_id=${scheme.id}`}
            className="text-xs font-semibold text-emerald-600 hover:text-emerald-700 flex items-center"
          >
            <FileText className="w-3.5 h-3.5 mr-1" />
            {language === 'hi' ? 'दस्तावेज़ चेकलिस्ट खोलें' : 'Open Document Checklist'}
          </Link>
        </div>

        <div className="mt-4 divide-y divide-slate-100">
          {scheme.documents && scheme.documents.length > 0 ? (
            scheme.documents.map((doc) => (
              <div key={doc.id} className="py-3.5 first:pt-0 last:pb-0">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="font-semibold text-slate-900 text-sm">
                      {language === 'hi' ? doc.description_hi : doc.description_en}
                    </span>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                        doc.is_mandatory
                          ? 'bg-red-50 text-red-700 border border-red-200'
                          : 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      {doc.is_mandatory ? t('docs.mandatory') : t('docs.optional')}
                    </span>
                  </div>
                </div>

                {doc.acceptable_alternatives && doc.acceptable_alternatives.length > 0 && (
                  <p className="text-xs text-slate-500 mt-1">
                    <span className="font-medium text-slate-700">
                      {language === 'hi' ? 'स्वीकार्य विकल्प: ' : 'Alternatives: '}
                    </span>
                    {doc.acceptable_alternatives.join(', ')}
                  </p>
                )}

                {(doc.where_to_obtain_en || doc.where_to_obtain_hi) && (
                  <p className="text-xs text-emerald-700 mt-1 bg-emerald-50/50 p-1.5 rounded">
                    <span className="font-semibold">
                      {language === 'hi' ? 'कहाँ से प्राप्त करें: ' : 'Where to obtain: '}
                    </span>
                    {language === 'hi' ? doc.where_to_obtain_hi : doc.where_to_obtain_en}
                  </p>
                )}
              </div>
            ))
          ) : (
            <p className="text-sm text-slate-500 py-4">
              {language === 'hi'
                ? 'इस योजना के लिए कोई विशिष्ट दस्तावेज़ आवश्यकताएं सूचीबद्ध नहीं हैं।'
                : 'No specific documents listed for this scheme.'}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
