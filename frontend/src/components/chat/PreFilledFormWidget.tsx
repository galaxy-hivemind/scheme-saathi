import React, { useState } from 'react';
import {
  FileEdit,
  CheckCircle2,
  ArrowRight,
  Save,
  Check,
  ShieldCheck,
  AlertTriangle,
  ExternalLink,
  Info,
} from 'lucide-react';
import { Button } from '@/components/common/Button';
import { PortalIntegrationInfo } from '@/types';

export interface ConflictCandidate {
  value: any;
  source_tier: string;
  source_label: string;
}

export interface FieldConflict {
  field: string;
  label: string;
  candidates: ConflictCandidate[];
  message: string;
}

export interface UnverifiedOcrHint {
  suggested_value: any;
  source_tier: string;
  source_label: string;
  document_id?: string;
}

export interface FormFieldItem {
  name: string;
  label: string;
  type: string;
  required: boolean;
  conditional?: boolean;
  value: any;
  is_prefilled: boolean;
  requires_input?: boolean;
  source_tier?: string | null;
  source_label?: string | null;
  conflict?: FieldConflict | null;
  unverified_ocr_hint?: UnverifiedOcrHint | null;
  validation_error?: string | null;
  placeholder?: string;
  pattern?: string;
  options?: Array<string | { value: string; label: string }>;
}

export interface FormSectionItem {
  section_id: string;
  title: string;
  fields: FormFieldItem[];
}

export interface FormDraftPayload {
  draft_id?: string;
  application_id?: string;
  scheme_code?: string;
  scheme_name?: string;
  scheme_title?: string;
  official_portal?: string;
  form_supported?: boolean;
  schema_available?: boolean;
  schema_status?: string;
  message?: string;
  readiness_percentage?: number;
  prefill_percentage?: number;
  total_fields?: number;
  total_mandatory_fields?: number;
  filled_mandatory_fields?: number;
  auto_populated_fields?: number;
  requires_input_count?: number;
  conflicting_fields?: FieldConflict[];
  sections?: FormSectionItem[];
  form_data?: Record<string, any>;
  values?: Record<string, any>;
  can_confirm?: boolean;
  portal_integration?: PortalIntegrationInfo;
  missing_fields?: Array<string | { name?: string; field?: string; label?: string }>;
  missing_mandatory_documents?: Array<string | { doc_type?: string; label?: string; document_name?: string }>;
}

interface PreFilledFormWidgetProps {
  data: FormDraftPayload;
  language?: 'en' | 'hi' | 'mr';
  onConfirmSubmit?: (formData: Record<string, any>) => void;
  onSaveDraft?: (formData: Record<string, any>) => void;
}

export const PreFilledFormWidget: React.FC<PreFilledFormWidgetProps> = ({
  data,
  language = 'en',
  onConfirmSubmit,
  onSaveDraft,
}) => {
  const pickText = (en: string, hi: string, mr: string) => {
    if (language === 'hi') return hi;
    if (language === 'mr') return mr;
    return en;
  };

  // Schema Unavailable State (Strict Schema Integrity: never invent fallback fields)
  if (data.form_supported === false || data.schema_available === false) {
    return (
      <div className="w-full mt-3.5 bg-linear-to-b from-white to-amber-50/40 rounded-2xl border border-amber-200/80 shadow-subtle p-4 space-y-3">
        <div className="flex items-start gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-amber-100 text-amber-800 flex items-center justify-center border border-amber-300 shrink-0">
            <Info className="w-4 h-4 text-amber-700" />
          </div>
          <div className="space-y-1">
            <h4 className="text-xs font-bold text-navy font-editorial flex items-center gap-1.5 flex-wrap">
              <span>
                {pickText(
                  'Structured Application Schema Unavailable',
                  'आवेदन फ़ॉर्म स्कीमा उपलब्ध नहीं है',
                  'अर्ज फॉर्म नमुना उपलब्ध नाही'
                )}
              </span>
              {data.scheme_code && (
                <span className="text-[10px] font-mono bg-ivory-100 text-navy/70 px-2 py-0.5 rounded border border-navy/10">
                  {data.scheme_code}
                </span>
              )}
            </h4>
            <p className="text-xs text-navy/80 leading-relaxed">
              {data.message ||
                pickText(
                  'Verified application form field mapping is unavailable for this scheme. Eligibility and document checklists remain separate and available, while the form must be filled on the official government portal.',
                  'इस योजना के लिए सत्यापित आवेदन फ़ॉर्म मैपिंग उपलब्ध नहीं है। पात्रता और दस्तावेज़ जांच उपलब्ध हैं, परंतु आवेदन आधिकारिक सरकारी पोर्टल पर करना होगा।',
                  'या योजनेसाठी पडताळलेला अर्ज फॉर्म नमुना उपलब्ध नाही. पात्रता व कागदपत्र तपासणी उपलब्ध आहे, परंतु अर्ज थेट अधिकृत शासकीय पोर्टलवर भरावा लागेल.'
                )}
            </p>
          </div>
        </div>

        {data.portal_integration?.submission_method_label && (
          <div className="text-[11px] text-navy/80 bg-white/80 rounded-xl p-2.5 border border-navy/8 space-y-1.5">
            <div className="font-bold text-navy">{data.portal_integration.submission_method_label}</div>
            {Array.isArray(data.portal_integration.official_instructions?.online_steps) &&
              data.portal_integration.official_instructions.online_steps.length > 0 && (
                <ul className="list-disc pl-4 space-y-0.5 text-navy/75">
                  {data.portal_integration.official_instructions.online_steps.slice(0, 4).map((step, i) => (
                    <li key={i}>{step}</li>
                  ))}
                </ul>
              )}
          </div>
        )}

        {(data.official_portal || data.portal_integration?.official_application_url || data.portal_integration?.official_url) && (
          <div className="flex justify-end gap-2 pt-1 flex-wrap">
            {data.portal_integration?.tracking_url && (
              <a
                href={data.portal_integration.tracking_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-ivory-100 text-navy font-semibold text-xs rounded-xl border border-navy/15 transition-all"
              >
                <span>{pickText('Tracking Portal', 'ट्रैकिंग पोर्टल', 'स्थिती पोर्टल')}</span>
                <ExternalLink className="w-3 h-3 text-saffron" />
              </a>
            )}
            <a
              href={
                data.portal_integration?.official_application_url ||
                data.official_portal ||
                data.portal_integration?.official_url
              }
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-saffron hover:bg-saffron-dark text-white font-bold text-xs rounded-xl shadow-subtle transition-all"
            >
              <span>{pickText('Apply on Official Portal', 'आधिकारिक पोर्टल पर जाएं', 'अधिकृत पोर्टलवर अर्ज करा')}</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        )}
      </div>
    );
  }

  const [formData, setFormData] = useState<Record<string, any>>(() => {
    const initial: Record<string, any> = { ...(data.form_data || data.values || {}) };
    if (data.sections) {
      for (const sec of data.sections) {
        for (const f of sec.fields) {
          if (initial[f.name] === undefined && f.value !== undefined) {
            initial[f.name] = f.value === null ? '' : f.value;
          }
        }
      }
    }
    return initial;
  });

  const [resolvedConflicts, setResolvedConflicts] = useState<Record<string, boolean>>({});
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [showValidationBanner, setShowValidationBanner] = useState<boolean>(false);
  const [savedNotice, setSavedNotice] = useState<boolean>(false);

  const sections = data.sections || [];
  const readiness = data.prefill_percentage ?? data.readiness_percentage ?? 0;

  const isEmpty = (v: any) =>
    v === undefined ||
    v === null ||
    String(v).trim() === '' ||
    ['null', 'undefined', 'none'].includes(String(v).trim().toLowerCase());

  const validateSingleField = (field: FormFieldItem, val: any): string => {
    if (field.conflict && !resolvedConflicts[field.name]) {
      return field.conflict.message;
    }
    if (field.required && isEmpty(val)) {
      return pickText(
        `${field.label} is required`,
        `${field.label} अनिवार्य है`,
        `${field.label} भरणे आवश्यक आहे`
      );
    }
    if (!isEmpty(val) && field.pattern) {
      try {
        if (!new RegExp(field.pattern).test(String(val).trim())) {
          return pickText(
            `Invalid format for ${field.label}`,
            `${field.label} का प्रारूप अमान्य है`,
            `${field.label} चा नमुना अवैध आहे`
          );
        }
      } catch {
        // Ignore malformed pattern
      }
    }
    return '';
  };

  const handleFieldChange = (field: FormFieldItem, value: any) => {
    setFormData((prev) => ({
      ...prev,
      [field.name]: value,
    }));
    if (field.conflict) {
      setResolvedConflicts((prev) => ({ ...prev, [field.name]: true }));
    }
    const err = validateSingleField(field, value);
    setFieldErrors((prev) => {
      const next = { ...prev };
      if (err) {
        next[field.name] = err;
      } else {
        delete next[field.name];
      }
      return next;
    });
    setSavedNotice(false);
  };

  const handlePickConflictValue = (field: FormFieldItem, value: any) => {
    setResolvedConflicts((prev) => ({ ...prev, [field.name]: true }));
    setFormData((prev) => ({ ...prev, [field.name]: value }));
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next[field.name];
      return next;
    });
    setSavedNotice(false);
  };

  const handleSave = () => {
    if (onSaveDraft) {
      onSaveDraft(formData);
    }
    setSavedNotice(true);
    setTimeout(() => setSavedNotice(false), 3000);
  };

  const handleProceed = () => {
    const errors: Record<string, string> = {};
    for (const sec of sections) {
      for (const field of sec.fields) {
        const curVal = formData[field.name];
        const isCondRequired =
          data.scheme_code === 'PMAY-G' && field.name === 'mgnrega_job_card_number'
            ? String(formData['mgnrega_wage_convergence'] || '').trim().toLowerCase() === 'yes'
            : field.required;
        const effectiveField = { ...field, required: isCondRequired };
        const err = validateSingleField(effectiveField, curVal);
        if (err) {
          errors[field.name] = err;
        }
      }
    }
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) {
      setShowValidationBanner(true);
      return;
    }
    setShowValidationBanner(false);
    if (onConfirmSubmit) {
      onConfirmSubmit(formData);
    }
  };

  const unresolvedConflictCount = sections
    .flatMap((s) => s.fields)
    .filter((f) => f.conflict && !resolvedConflicts[f.name]).length;

  return (
    <div className="w-full mt-3.5 bg-linear-to-b from-white to-ivory-50/70 rounded-2xl border border-navy/12 shadow-subtle p-4 space-y-4">
      {/* Header & Readiness Counter */}
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-saffron-light text-saffron-dark flex items-center justify-center border border-saffron/30 shadow-xs">
              <FileEdit className="w-4 h-4 text-saffron-vibrant" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-navy font-editorial flex items-center gap-1.5 flex-wrap">
                <span>
                  {pickText(
                    'Pre-Filled Application Draft',
                    'पूर्व-भरा आवेदन मसौदा',
                    'पूर्व-भरलेला अर्ज मसुदा'
                  )}
                </span>
                {data.scheme_code && (
                  <span className="text-[10px] font-mono bg-ivory-100 text-navy/70 px-2 py-0.5 rounded border border-navy/10">
                    {data.scheme_code}
                  </span>
                )}
              </h4>
              <p className="text-[11px] text-navy/60">
                {pickText(
                  'Populated strictly from verified citizen profile, Vault documents & session answers',
                  'सत्यापित नागरिक प्रोफ़ाइल, दस्तावेज़ वॉल्ट और सत्र उत्तरों पर आधारित',
                  'पडताळलेले नागरिक प्रोफाईल, दस्तऐवज व्हॉल्ट व संभाषण उत्तरांवर आधारित'
                )}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span
              className={`text-xs font-bold px-2.5 py-1 rounded-full border ${
                readiness >= 100 && unresolvedConflictCount === 0
                  ? 'bg-sage-light text-sage-green border-sage/30'
                  : 'bg-amber-50 text-amber-800 border-amber-200'
              }`}
            >
              {readiness}% {pickText('Pre-filled', 'पूर्ण', 'पूर्ण')}
            </span>
          </div>
        </div>

        {/* Readiness Progress Bar */}
        <div className="w-full bg-navy/8 rounded-full h-1.5 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              readiness >= 100 && unresolvedConflictCount === 0 ? 'bg-sage-green' : 'bg-saffron'
            }`}
            style={{ width: `${Math.min(100, readiness)}%` }}
          />
        </div>

        {(data.portal_integration?.submission_method_label ||
          (Array.isArray(data.missing_mandatory_documents) && data.missing_mandatory_documents.length > 0)) && (
          <div className="flex flex-wrap items-center gap-1.5 pt-0.5 text-[10.5px]">
            {data.portal_integration?.submission_method_label && (
              <span className="px-2 py-0.5 rounded-full bg-ivory-100 text-navy/75 border border-navy/10 font-medium">
                {data.portal_integration.submission_method_label}
              </span>
            )}
            {Array.isArray(data.missing_mandatory_documents) && data.missing_mandatory_documents.length > 0 && (
              <span className="px-2 py-0.5 rounded-full bg-amber-50 text-amber-900 border border-amber-200 font-medium">
                {pickText(
                  `Missing mandatory docs: ${data.missing_mandatory_documents.length}`,
                  `अनिवार्य दस्तावेज़ शेष: ${data.missing_mandatory_documents.length}`,
                  `प्रलंबित आवश्यक कागदपत्रे: ${data.missing_mandatory_documents.length}`
                )}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Conflict Summary Banner */}
      {unresolvedConflictCount > 0 && (
        <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-950 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <span>
            {pickText(
              `${unresolvedConflictCount} field(s) have conflicting information across your sources. Please select the accurate value below.`,
              `${unresolvedConflictCount} फ़ील्ड में स्रोतों के बीच विरोधाभास है। कृपया नीचे सही मान चुनें।`,
              `${unresolvedConflictCount} रकान्यांमध्ये स्रोतांमधील माहिती जुळत नाही. कृपया खालील अचूक पर्याय निवडा.`
            )}
          </span>
        </div>
      )}

      {/* Form Sections */}
      <div className="space-y-3">
        {sections.map((section) => (
          <div
            key={section.section_id}
            className="rounded-xl border border-navy/10 bg-white p-3 space-y-3 shadow-xs"
          >
            <h5 className="text-[11px] font-bold text-navy/90 uppercase tracking-wider border-b border-navy/6 pb-1.5 flex items-center justify-between">
              <span>{section.title}</span>
              <span className="text-[9.5px] font-normal text-navy/50">
                {section.fields.filter((f) => !isEmpty(formData[f.name])).length} / {section.fields.length}{' '}
                {pickText('filled', 'भरे गए', 'भरलेले')}
              </span>
            </h5>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {section.fields.map((field) => {
                const curVal = formData[field.name] ?? '';
                const filled = !isEmpty(curVal);
                const hasUnresolvedConflict = Boolean(field.conflict && !resolvedConflicts[field.name]);
                const err = fieldErrors[field.name] || '';

                return (
                  <div key={field.name} className="space-y-1">
                    <div className="flex items-center justify-between gap-1 flex-wrap">
                      <label className="text-[11px] font-semibold text-navy flex items-center gap-1">
                        <span>{field.label}</span>
                        {field.required && <span className="text-rose-600">*</span>}
                      </label>

                      {hasUnresolvedConflict ? (
                        <span className="text-[9px] font-semibold text-rose-700 bg-rose-50 px-1.5 py-0.5 rounded border border-rose-200 inline-flex items-center gap-0.5">
                          <AlertTriangle className="w-2.5 h-2.5" />
                          <span>{pickText('Conflict', 'विरोधाभास', 'तफावत')}</span>
                        </span>
                      ) : filled ? (
                        <span className="text-[9px] font-medium text-sage-green bg-sage-light/60 px-1.5 py-0.5 rounded border border-sage/20 inline-flex items-center gap-0.5">
                          <Check className="w-2.5 h-2.5" />
                          <span>
                            {field.source_label ||
                              pickText('Pre-filled', 'पूर्व-भरा', 'पूर्व-भरलेले')}
                          </span>
                        </span>
                      ) : field.required ? (
                        <span className="text-[9px] font-medium text-amber-800 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                          {pickText('Citizen Input Needed', 'प्रविष्टि आवश्यक', 'माहिती आवश्यक')}
                        </span>
                      ) : (
                        <span className="text-[9px] text-navy/45">
                          {pickText('Optional', 'वैकल्पिक', 'ऐच्छिक')}
                        </span>
                      )}
                    </div>

                    {field.type === 'select' && field.options ? (
                      <select
                        value={curVal}
                        onChange={(e) => handleFieldChange(field, e.target.value)}
                        className={`w-full text-xs bg-ivory-50/60 border rounded-lg px-2.5 py-1.5 text-navy focus:outline-none focus:ring-1 ${
                          err || hasUnresolvedConflict
                            ? 'border-rose-400 focus:ring-rose-400'
                            : 'border-navy/15 focus:ring-saffron'
                        }`}
                      >
                        <option value="">
                          {pickText('Select an option', 'विकल्प चुनें', 'पर्याय निवडा')}
                        </option>
                        {field.options.map((opt) => {
                          const optValue = typeof opt === 'string' ? opt : opt.value;
                          const optLabel = typeof opt === 'string' ? opt : opt.label;
                          return (
                            <option key={optValue} value={optValue}>
                              {optLabel}
                            </option>
                          );
                        })}
                      </select>
                    ) : (
                      <input
                        type={field.type === 'number' ? 'number' : field.type === 'date' ? 'date' : 'text'}
                        value={curVal}
                        placeholder={
                          field.placeholder ||
                          pickText(`Enter ${field.label}`, `${field.label} दर्ज करें`, `${field.label} भरा`)
                        }
                        onChange={(e) => handleFieldChange(field, e.target.value)}
                        className={`w-full text-xs bg-ivory-50/60 border rounded-lg px-2.5 py-1.5 text-navy placeholder-navy/30 focus:outline-none focus:ring-1 ${
                          err || hasUnresolvedConflict
                            ? 'border-rose-400 focus:ring-rose-400'
                            : 'border-navy/15 focus:ring-saffron'
                        }`}
                      />
                    )}

                    {/* Conflict Resolution Choices */}
                    {hasUnresolvedConflict && field.conflict && (
                      <div className="p-2 rounded-lg bg-amber-50/80 border border-amber-200/80 space-y-1.5">
                        <p className="text-[10px] text-amber-950 font-medium">{field.conflict.message}</p>
                        <div className="flex flex-wrap gap-1.5">
                          {field.conflict.candidates.map((cand, idx) => (
                            <button
                              key={idx}
                              type="button"
                              onClick={() => handlePickConflictValue(field, cand.value)}
                              className="text-[10px] px-2 py-0.5 rounded bg-white border border-amber-300 hover:border-saffron text-navy font-semibold"
                            >
                              {cand.source_label}: {String(cand.value)}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Unverified OCR Hint (never auto-filled) */}
                    {!filled && !hasUnresolvedConflict && field.unverified_ocr_hint && (
                      <p className="text-[10px] text-navy/60">
                        {pickText(
                          `Unverified OCR in Vault (${field.unverified_ocr_hint.suggested_value}) — review & verify in Document Vault or type manually.`,
                          `वॉल्ट में असत्यापित OCR (${field.unverified_ocr_hint.suggested_value}) — कृपया दस्तावेज़ वॉल्ट में सत्यापित करें या स्वयं भरें।`,
                          `व्हॉल्टमध्ये अपडताळलेला OCR (${field.unverified_ocr_hint.suggested_value}) — दस्तऐवज व्हॉल्टमध्ये पडताळा किंवा स्वतः भरा.`
                        )}
                      </p>
                    )}

                    {err && !hasUnresolvedConflict && (
                      <p className="text-[10px] text-rose-600 font-medium">{err}</p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Official Safety Notice */}
      <div className="bg-sage-light/30 border border-sage/20 rounded-xl p-2.5 flex items-start gap-2 text-[11px] text-navy/80">
        <ShieldCheck className="w-4 h-4 text-sage-green shrink-0 mt-0.5" />
        <div>
          <span className="font-bold text-navy block text-[10.5px]">
            {pickText(
              'Explicit Citizen Consent Guarantee',
              'स्पष्ट नागरिक सहमति गारंटी',
              'नागरिक स्पष्ट संमती हमी'
            )}
          </span>
          <span>
            {pickText(
              'Nothing is submitted automatically. After validating mandatory fields and Vault documents, you confirm explicitly before official portal handoff.',
              'बिना आपकी सहमति के कुछ भी जमा नहीं होता। अनिवार्य विवरण और दस्तावेज़ सत्यापन के बाद ही पोर्टल पैकेट बनता है।',
              'तुमच्या स्पष्ट संमतीशिवाय अर्ज सादर होत नाही. सर्व अनिवार्य माहिती व कागदपत्रांच्या पडताळणीनंतरच पोर्टल संच तयार होतो.'
            )}
          </span>
        </div>
      </div>

      {/* Validation Summary Banner when citizen attempts to proceed with missing/invalid/conflicting fields */}
      {showValidationBanner && Object.keys(fieldErrors).length > 0 && (
        <div
          role="alert"
          className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-900 flex items-start gap-2"
        >
          <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
          <div>
            <span className="font-bold">
              {pickText(
                `Please resolve ${Object.keys(fieldErrors).length} field(s) marked above before proceeding.`,
                `आगे बढ़ने से पहले कृपया ऊपर चिह्नित ${Object.keys(fieldErrors).length} फ़ील्ड ठीक करें।`,
                `पुढे जाण्यापूर्वी कृपया वरील ${Object.keys(fieldErrors).length} रकाने तपासा आणि पूर्ण करा.`
              )}
            </span>
          </div>
        </div>
      )}

      {/* Action Footer */}
      <div className="pt-2 border-t border-navy/8 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {onSaveDraft && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleSave}
              leftIcon={<Save className="w-3.5 h-3.5" />}
              className="text-xs"
            >
              {pickText('Save Draft', 'ड्राफ्ट सहेजें', 'मसुदा सेव्ह करा')}
            </Button>
          )}

          {savedNotice && (
            <span className="text-xs font-semibold text-sage-green flex items-center gap-1 animate-fade-in-up">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>{pickText('Draft Saved!', 'ड्राफ्ट सहेजा गया!', 'मसुदा जतन केला!')}</span>
            </span>
          )}
        </div>

        {onConfirmSubmit && (
          <Button
            type="button"
            variant="saffron"
            size="sm"
            onClick={handleProceed}
            rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
            className="font-bold shadow-subtle text-xs"
          >
            {pickText('Proceed to Confirmation', 'पुष्टि के लिए आगे बढ़ें', 'माहिती तपासा व नक्की करा')}
          </Button>
        )}
      </div>
    </div>
  );
};
