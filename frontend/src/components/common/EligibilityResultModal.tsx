import React from 'react';
import { Link } from 'react-router-dom';
import { Scheme, EligibilityResult } from '@/types';
import { useLanguage } from '@/context/LanguageContext';
import { Modal } from '@/components/common/Modal';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Spinner } from '@/components/common/Spinner';
import {
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  XCircle,
  Sparkles,
  ArrowRight,
  ShieldCheck,
} from 'lucide-react';

interface EligibilityResultModalProps {
  isOpen: boolean;
  onClose: () => void;
  scheme: Scheme | null;
  eligibility: EligibilityResult | null;
  loading?: boolean;
  error?: string | null;
}

export const EligibilityResultModal: React.FC<EligibilityResultModalProps> = ({
  isOpen,
  onClose,
  scheme,
  eligibility,
  loading = false,
  error = null,
}) => {
  const { language } = useLanguage();

  if (!isOpen) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      maxWidth="lg"
      title={
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-saffron" />
          <span className="font-editorial text-base sm:text-lg font-bold text-navy">
            {language === 'hi' ? 'पात्रता मूल्यांकन परिणाम' : 'Deterministic Eligibility Evaluation'}
          </span>
        </div>
      }
      footer={
        <div className="w-full flex items-center justify-between gap-3">
          <Button variant="outline" size="sm" onClick={onClose}>
            {language === 'hi' ? 'बंद करें' : 'Close'}
          </Button>

          {scheme && (
            <div className="flex items-center gap-2">
              <Link to={`/schemes/${scheme.id}`} onClick={onClose}>
                <Button variant="outline" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                  {language === 'hi' ? 'संपूर्ण विवरण व दस्तावेज़' : 'Full Scheme Details'}
                </Button>
              </Link>

              {eligibility?.result === 'eligible' && (
                <Link to="/applications" onClick={onClose}>
                  <Button variant="saffron" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                    {language === 'hi' ? 'आवेदन तैयारी' : 'Start Application'}
                  </Button>
                </Link>
              )}
            </div>
          )}
        </div>
      }
    >
      <div className="space-y-5 p-1">
        {loading ? (
          <div className="py-12">
            <Spinner
              size="lg"
              label={
                language === 'hi'
                  ? 'आपकी प्रोफ़ाइल के विरुद्ध नियमों का मूल्यांकन किया जा रहा है...'
                  : 'Evaluating criteria AST against your verified PostgreSQL profile...'
              }
            />
          </div>
        ) : error ? (
          <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-950 text-xs flex items-center gap-2">
            <XCircle className="w-5 h-5 text-rose-600 shrink-0" />
            <span>{error}</span>
          </div>
        ) : !eligibility || !scheme ? (
          <div className="text-center py-8 text-xs text-navy/60">
            {language === 'hi' ? 'कोई मूल्यांकन डेटा उपलब्ध नहीं है।' : 'No evaluation data available.'}
          </div>
        ) : (
          <div className="space-y-5">
            {/* Scheme Top Banner */}
            <div className="p-4 rounded-2xl bg-ivory-100/80 border border-navy/8 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <Badge variant="category">{scheme.category.replace(/_/g, ' ').toUpperCase()}</Badge>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-semibold text-sage-green bg-sage-light px-2 py-0.5 rounded-full border border-sage/30 flex items-center gap-1">
                    <ShieldCheck className="w-3 h-3" />
                    {scheme.scheme_status}
                  </span>
                </div>
              </div>
              <h3 className="font-bold text-navy text-lg font-editorial">{scheme.name}</h3>
              <p className="text-xs text-navy/60 leading-relaxed line-clamp-2">{scheme.description}</p>
            </div>

            {/* Outcome Badge and Overall Explanation */}
            <div className="flex items-center justify-between gap-4 p-4 rounded-2xl bg-white border border-navy/10 shadow-subtle">
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
                  <h4 className="font-bold text-navy text-sm">
                    {language === 'hi' ? 'पात्रता स्थिति' : 'Deterministic Determination'}
                  </h4>
                  <p className="text-[11px] text-navy/50">
                    Rule Version: {eligibility.rule_version_id || 'v1-authoritative'}
                  </p>
                </div>
              </div>

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

            <p className="text-xs font-medium text-navy/80 leading-relaxed bg-ivory-50 p-3.5 rounded-xl border border-navy/6">
              {eligibility.explanation}
            </p>

            {/* Missing Profile Fields Alert */}
            {eligibility.missing_fields && eligibility.missing_fields.length > 0 && (
              <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-xs space-y-2">
                <div className="flex items-center gap-2 text-amber-900 font-bold">
                  <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                  <span>
                    {language === 'hi'
                      ? 'पूर्ण मूल्यांकन हेतु आवश्यक प्रोफ़ाइल फ़ील्ड:'
                      : 'Missing Profile Attributes for Definitive Evaluation:'}
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {eligibility.missing_fields.map((f, i) => (
                    <span
                      key={i}
                      className="px-2 py-0.5 rounded bg-amber-100 text-amber-900 text-[10px] font-mono font-semibold"
                    >
                      {f.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
                <div className="pt-1">
                  <Link to="/onboarding" onClick={onClose}>
                    <Button variant="outline" size="sm" className="bg-white text-amber-900 border-amber-300 hover:bg-amber-100">
                      {language === 'hi' ? 'प्रोफ़ाइल अपडेट करें' : 'Update Profile'}
                    </Button>
                  </Link>
                </div>
              </div>
            )}

            {/* AST Evaluated Conditions Checklist */}
            {eligibility.condition_results && eligibility.condition_results.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-[11px] font-bold uppercase tracking-wider text-navy/50">
                  {language === 'hi' ? 'जांची गई वैधानिक शर्तें' : 'Statutory Criteria Evaluation Checklist'}
                </h4>
                <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                  {eligibility.condition_results.map((cond, idx) => (
                    <div
                      key={idx}
                      className={`flex items-start gap-2.5 p-3 rounded-xl text-xs border transition-all ${
                        cond.passed === true
                          ? 'bg-sage-light/70 border-sage/30 text-navy'
                          : cond.passed === false
                          ? 'bg-rose-50/70 border-rose-200 text-rose-950'
                          : 'bg-amber-50/70 border-amber-200 text-navy'
                      }`}
                    >
                      {cond.passed === true ? (
                        <CheckCircle2 className="w-4 h-4 text-sage-green shrink-0 mt-0.5" />
                      ) : cond.passed === false ? (
                        <XCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                      ) : (
                        <HelpCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                      )}
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-navy capitalize">{cond.field.replace(/_/g, ' ')}</span>
                          <span className="text-[10px] text-navy/50 font-mono">[{cond.operator}]</span>
                        </div>
                        <p className="opacity-80 text-[11px] leading-relaxed">{cond.explanation}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Scope Limitation */}
            {eligibility.limitations && (
              <p className="text-[10px] text-navy/50 italic border-t border-navy/6 pt-2">
                *{eligibility.limitations}
              </p>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
};
