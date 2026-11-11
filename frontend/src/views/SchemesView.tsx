import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useLanguage } from '../context/LanguageContext';
import { api } from '../api/client';
import { SchemeSummary, EligibilityResult } from '../types';
import { SpeechPlayerButton } from '../components/SpeechPlayerButton';
import { SpeechRecognizer, isSpeechRecognitionSupported } from '../utils/speechRecognition';
import {
  Compass,
  Search,
  Mic,
  MicOff,
  CheckCircle2,
  XCircle,
  AlertCircle,
  ExternalLink,
  FileCheck2,
  ShieldCheck,
  Building,
  Loader2,
  X,
} from 'lucide-react';

export const SchemesView: React.FC = () => {
  const { t, language } = useLanguage();

  const [schemes, setSchemes] = useState<SchemeSummary[]>(() => {
    try {
      const cached = localStorage.getItem('scheme_saathi_cached_schemes');
      return cached ? JSON.parse(cached) : [];
    } catch {
      return [];
    }
  });
  const [total, setTotal] = useState<number>(() => {
    try {
      const cached = localStorage.getItem('scheme_saathi_cached_schemes');
      return cached ? JSON.parse(cached).length : 0;
    } catch {
      return 0;
    }
  });
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(() => !localStorage.getItem('scheme_saathi_cached_schemes'));
  const [isVoiceSearching, setIsVoiceSearching] = useState<boolean>(false);

  const recognizerRef = useRef<SpeechRecognizer | null>(null);

  // Quick Eligibility Evaluation Modal State
  const [evaluatingScheme, setEvaluatingScheme] = useState<SchemeSummary | null>(null);
  const [evalResult, setEvalResult] = useState<EligibilityResult | null>(null);
  const [isEvaluating, setIsEvaluating] = useState<boolean>(false);

  const categories = [
    { id: '', label: t('schemes.all_categories') },
    { id: 'agriculture', label: t('schemes.agriculture') },
    { id: 'health', label: t('schemes.health') },
    { id: 'housing', label: t('schemes.housing') },
    { id: 'pension', label: t('schemes.pension') },
    { id: 'business', label: t('schemes.business') },
    { id: 'education', label: t('schemes.education') },
  ];

  const fetchSchemes = async () => {
    setIsLoading(true);
    try {
      const data = await api.schemes.list({
        q: searchQuery.trim() || undefined,
        category: selectedCategory || undefined,
        limit: 20,
      });
      const items = data.items || [];
      setSchemes(items);
      setTotal(data.total || 0);
      if (!searchQuery && !selectedCategory && items.length > 0) {
        localStorage.setItem('scheme_saathi_cached_schemes', JSON.stringify(items));
      }
    } catch (err) {
      console.warn('Network fetch failed, attempting to read from offline schemes cache:', err);
      const cached = localStorage.getItem('scheme_saathi_cached_schemes');
      if (cached) {
        try {
          const parsed = JSON.parse(cached);
          let filtered = parsed;
          if (selectedCategory) {
            filtered = filtered.filter((s: any) => s.category?.toLowerCase() === selectedCategory.toLowerCase());
          }
          if (searchQuery) {
            const q = searchQuery.toLowerCase();
            filtered = filtered.filter((s: any) => s.name?.toLowerCase().includes(q) || s.scheme_code?.toLowerCase().includes(q));
          }
          setSchemes(filtered);
          setTotal(filtered.length);
        } catch {
          // ignore cache parse error
        }
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchSchemes();
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery, selectedCategory]);

  const handleQuickEvaluate = async (scheme: SchemeSummary) => {
    setEvaluatingScheme(scheme);
    setEvalResult(null);
    setIsEvaluating(true);

    try {
      const result = await api.eligibility.evaluate(scheme.id);
      setEvalResult(result);
    } catch (err: any) {
      console.error('Eligibility check error:', err);
    } finally {
      setIsEvaluating(false);
    }
  };

  const handleVoiceSearch = () => {
    if (!isSpeechRecognitionSupported()) {
      alert(
        language === 'hi'
          ? 'आपके ब्राउज़र में आवाज़ पहचान (Voice Search) समर्थित नहीं है।'
          : 'Voice search is not supported in this browser.'
      );
      return;
    }

    if (isVoiceSearching) {
      recognizerRef.current?.stop();
      setIsVoiceSearching(false);
      return;
    }

    const recognizer = new SpeechRecognizer(
      {
        onStart: () => setIsVoiceSearching(true),
        onFinalResult: (transcript) => {
          setSearchQuery(transcript);
          setIsVoiceSearching(false);
        },
        onError: () => setIsVoiceSearching(false),
        onEnd: () => setIsVoiceSearching(false),
      },
      { lang: language === 'hi' ? 'hi-IN' : 'en-IN' }
    );

    recognizerRef.current = recognizer;
    recognizer.start();
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center space-x-2">
            <Compass className="w-6 h-6 text-orange-600" />
            <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">
              {language === 'hi' ? 'सरकारी कल्याणकारी योजनाएं' : 'Central Welfare Schemes'}
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            {language === 'hi'
              ? 'आधिकारिक 2026 प्रमाणों के साथ सत्यापित केंद्रीय सरकारी योजनाएं'
              : 'Verified central government welfare schemes backed by official 2026 notifications'}
          </p>
        </div>
        <div className="text-xs font-semibold text-slate-500 bg-slate-100 px-3 py-1.5 rounded-lg self-start sm:self-auto">
          {language === 'hi' ? `कुल योजनाएं: ${total}` : `Total Schemes: ${total}`}
        </div>
      </div>

      {/* Search & Category Filter Bar */}
      <div className="space-y-3">
        <div className="relative">
          <Search className="w-5 h-5 text-slate-400 absolute left-3.5 top-3.5" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t('schemes.search_placeholder')}
            className="w-full pl-11 pr-12 py-3 text-sm rounded-2xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-600 bg-white shadow-sm transition-colors"
          />
          <button
            type="button"
            onClick={handleVoiceSearch}
            className={`absolute right-3 top-2.5 p-1.5 rounded-xl border transition-colors ${
              isVoiceSearching
                ? 'bg-rose-600 text-white border-rose-600 animate-pulse'
                : 'text-slate-400 hover:text-orange-600 hover:bg-orange-50 border-transparent'
            }`}
            title={language === 'hi' ? 'बोलकर खोजें / Voice Search' : 'Voice search'}
            aria-label="Voice search schemes"
          >
            {isVoiceSearching ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
          </button>
        </div>

        {/* Category Pills */}
        <div className="flex overflow-x-auto pb-2 gap-2 scrollbar-none">
          {categories.map((cat) => (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all shadow-sm ${
                selectedCategory === cat.id
                  ? 'bg-orange-600 text-white shadow-orange-500/20'
                  : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 hover:border-slate-300'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Scheme Cards Grid */}
      {isLoading ? (
        <div className="py-24 text-center">
          <Loader2 className="w-8 h-8 text-orange-600 animate-spin mx-auto mb-3" />
          <p className="text-sm font-medium text-slate-500">योजनाएं खोजी जा रही हैं... / Searching schemes...</p>
        </div>
      ) : schemes.length === 0 ? (
        <div className="py-20 text-center bg-white rounded-2xl border border-slate-200">
          <Compass className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <p className="text-sm font-semibold text-slate-700">कोई योजना नहीं मिली / No schemes found</p>
          <p className="text-xs text-slate-400 mt-1">कृपया भिन्न खोज शब्द या श्रेणी चुनें / Try different keywords</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {schemes.map((scheme) => (
            <div
              key={scheme.id}
              className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm hover:shadow-md hover:border-orange-300 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-extrabold uppercase px-2 py-0.5 rounded-md bg-orange-100 text-orange-800 tracking-wider">
                      {scheme.scheme_code}
                    </span>
                    <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-md flex items-center space-x-1">
                      <ShieldCheck className="w-3 h-3 text-emerald-600" />
                      <span>{t('schemes.verified_badge')}</span>
                    </span>
                  </div>

                  <SpeechPlayerButton
                    text={`${scheme.name}. ${scheme.benefits_summary || ''}`}
                    size="sm"
                  />
                </div>

                <h2 className="text-base font-bold text-slate-900 tracking-tight leading-snug mb-1">
                  {scheme.name}
                </h2>

                <div className="flex items-center space-x-1.5 text-xs text-slate-500 mb-3">
                  <Building className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                  <span className="truncate">{scheme.ministry}</span>
                </div>

                {scheme.benefits_summary && (
                  <p className="text-xs text-slate-600 line-clamp-3 mb-4 leading-relaxed bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                    {scheme.benefits_summary}
                  </p>
                )}
              </div>

              {/* Action Buttons */}
              <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2">
                <button
                  onClick={() => handleQuickEvaluate(scheme)}
                  className="py-2 px-3.5 bg-gradient-to-r from-orange-600 to-orange-500 hover:from-orange-700 hover:to-orange-600 text-white rounded-xl text-xs font-semibold shadow-sm shadow-orange-500/20 transition-all flex items-center space-x-1.5"
                >
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>{t('schemes.btn_check_eligibility')}</span>
                </button>

                <div className="flex items-center space-x-2">
                  <Link
                    to={`/documents?scheme_id=${scheme.id}`}
                    className="p-2 text-slate-500 hover:text-emerald-700 hover:bg-emerald-50 rounded-xl transition-colors border border-slate-200"
                    title={t('schemes.documents_required')}
                  >
                    <FileCheck2 className="w-4 h-4" />
                  </Link>

                  <a
                    href={scheme.official_portal_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-2 text-slate-500 hover:text-blue-700 hover:bg-blue-50 rounded-xl transition-colors border border-slate-200"
                    title={t('schemes.official_portal')}
                  >
                    <ExternalLink className="w-4 h-4" />
                  </a>

                  <Link
                    to={`/schemes/${scheme.id}`}
                    className="py-2 px-3 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-medium transition-colors"
                  >
                    {t('schemes.btn_view_details')}
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Quick Eligibility Evaluation Modal */}
      {evaluatingScheme && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-lg bg-white rounded-3xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[90vh]">
            {/* Modal Header */}
            <div className="p-4 sm:p-5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
              <div>
                <span className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded bg-orange-100 text-orange-800">
                  {evaluatingScheme.scheme_code}
                </span>
                <h3 className="font-bold text-base text-slate-900 mt-1">
                  {evaluatingScheme.name}
                </h3>
              </div>
              <button
                onClick={() => setEvaluatingScheme(null)}
                className="p-1.5 text-slate-400 hover:text-slate-700 rounded-xl hover:bg-slate-200 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-5 overflow-y-auto space-y-4">
              {isEvaluating ? (
                <div className="py-12 text-center space-y-3">
                  <Loader2 className="w-8 h-8 text-orange-600 animate-spin mx-auto" />
                  <p className="text-xs font-semibold text-slate-600">
                    नियम इंजन द्वारा पात्रता की गणना हो रही है... / Evaluating criteria...
                  </p>
                </div>
              ) : evalResult ? (
                <div className="space-y-4">
                  {/* Status Banner */}
                  <div
                    className={`p-4 rounded-2xl border flex items-center space-x-3 ${
                      evalResult.overall_status === 'PASS'
                        ? 'bg-emerald-50 border-emerald-300 text-emerald-900'
                        : evalResult.overall_status === 'FAIL'
                        ? 'bg-rose-50 border-rose-300 text-rose-900'
                        : 'bg-amber-50 border-amber-300 text-amber-900'
                    }`}
                  >
                    {evalResult.overall_status === 'PASS' ? (
                      <CheckCircle2 className="w-6 h-6 text-emerald-600 shrink-0" />
                    ) : evalResult.overall_status === 'FAIL' ? (
                      <XCircle className="w-6 h-6 text-rose-600 shrink-0" />
                    ) : (
                      <AlertCircle className="w-6 h-6 text-amber-600 shrink-0" />
                    )}
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <h4 className="font-extrabold text-sm">
                          {evalResult.overall_status === 'PASS'
                            ? t('eligibility.eligible')
                            : evalResult.overall_status === 'FAIL'
                            ? t('eligibility.ineligible')
                            : t('eligibility.potentially_eligible')}
                        </h4>
                        <SpeechPlayerButton
                          text={language === 'hi' ? evalResult.explanation_hi : evalResult.explanation_en}
                          size="sm"
                        />
                      </div>
                      <p className="text-xs mt-0.5 opacity-90">
                        {language === 'hi' ? evalResult.explanation_hi : evalResult.explanation_en}
                      </p>
                    </div>
                  </div>

                  {/* Matched Conditions */}
                  {evalResult.matched_conditions?.length > 0 && (
                    <div>
                      <h5 className="text-xs font-bold uppercase tracking-wider text-emerald-800 mb-2 flex items-center space-x-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                        <span>{t('eligibility.matched')} ({evalResult.matched_conditions.length})</span>
                      </h5>
                      <div className="space-y-1.5">
                        {evalResult.matched_conditions.map((c, i) => (
                          <div key={i} className="p-2.5 bg-emerald-50/50 rounded-xl border border-emerald-100 text-xs text-slate-700 flex justify-between">
                            <span>{language === 'hi' ? c.description_hi || c.field : c.description_en || c.field}</span>
                            <span className="font-semibold text-emerald-700">PASS</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Failed Conditions */}
                  {evalResult.failed_conditions?.length > 0 && (
                    <div>
                      <h5 className="text-xs font-bold uppercase tracking-wider text-rose-800 mb-2 flex items-center space-x-1.5">
                        <XCircle className="w-3.5 h-3.5 text-rose-600" />
                        <span>{t('eligibility.failed')} ({evalResult.failed_conditions.length})</span>
                      </h5>
                      <div className="space-y-1.5">
                        {evalResult.failed_conditions.map((c, i) => (
                          <div key={i} className="p-2.5 bg-rose-50/50 rounded-xl border border-rose-100 text-xs text-slate-700 flex justify-between">
                            <span>{language === 'hi' ? c.description_hi || c.field : c.description_en || c.field}</span>
                            <span className="font-semibold text-rose-700">FAIL</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Next Questions / Missing Information */}
                  {evalResult.next_questions?.length > 0 && (
                    <div>
                      <h5 className="text-xs font-bold uppercase tracking-wider text-amber-800 mb-2 flex items-center space-x-1.5">
                        <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
                        <span>{t('eligibility.missing')} ({evalResult.next_questions.length})</span>
                      </h5>
                      <div className="space-y-2">
                        {evalResult.next_questions.map((q, i) => (
                          <div key={i} className="p-3 bg-amber-50/60 rounded-xl border border-amber-200 text-xs space-y-1.5">
                            <p className="font-semibold text-slate-800">
                              {language === 'hi' ? q.question_hi : q.question_en}
                            </p>
                            <Link
                              to={`/profile`}
                              className="inline-block text-[11px] font-semibold text-orange-600 hover:underline"
                            >
                              प्रोफ़ाइल में यह जानकारी जोड़ें / Add in Profile &rarr;
                            </Link>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="py-8 text-center text-xs text-slate-500">
                  पात्रता परिणाम उपलब्ध नहीं है / No result available
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
              <Link
                to={`/documents?scheme_id=${evaluatingScheme.id}`}
                className="py-2 px-3 text-xs font-semibold text-emerald-700 hover:bg-emerald-50 rounded-xl transition-colors border border-emerald-300"
              >
                दस्तावेज़ चेकलिस्ट / Checklist &rarr;
              </Link>
              <button
                onClick={() => setEvaluatingScheme(null)}
                className="py-2 px-4 bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-xl text-xs font-semibold transition-colors"
              >
                बंद करें / Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
