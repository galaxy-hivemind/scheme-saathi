import React, { useState } from 'react';
import { useLanguage } from '@/context/LanguageContext';
import {
  FileText,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  ArrowRight,
  Sparkles,
  Building2,
  Clock,
  IndianRupee,
  MapPin,
} from 'lucide-react';
import { Button } from '@/components/common/Button';

export interface SourcingInfo {
  issuing_authority?: string;
  where_to_obtain?: string;
  verified_fee?: string;
  processing_time_sla?: string;
  expected_processing_days?: string;
  portal_url?: string;
  official_url?: string;
}

export interface ChecklistItem {
  document_type: string;
  title: string;
  is_mandatory: boolean;
  status: 'verified' | 'uploaded' | 'extracted' | 'pending_review' | 'verification_pending' | 'expired' | 'missing' | string;
  sourcing?: SourcingInfo;
  vault_document_id?: string;
}

export interface ChecklistPayload {
  scheme_code?: string;
  scheme_name?: string;
  total_documents?: number;
  mandatory_total?: number;
  mandatory_count?: number;
  mandatory_ready?: number;
  readiness_percentage?: number;
  is_ready_for_prefill?: boolean;
  is_ready_for_application?: boolean;
  items?: ChecklistItem[];
}

export interface InteractiveChecklistWidgetProps {
  data: ChecklistPayload;
  schemeName?: string;
  lang?: 'en' | 'hi' | 'mr';
  onPrefillClick?: () => void;
  onAskMissingDoc?: (docTitle: string) => void;
}

const SCHEME_NAME_MAP: Record<string, string> = {
  'PM-KISAN': 'प्रधानमंत्री किसान सन्मान निधी (PM-KISAN)',
  'KCC': 'किसान क्रेडिट कार्ड (Kisan Credit Card)',
  'PM-SVANIDHI': 'पीएम स्वनिधी योजना (PM SVANidhi)',
  'NSP-CSSS': 'केंद्रीय क्षेत्र शिष्यवृत्ती (NSP Central Sector Scheme)',
  'PMMVY': 'प्रधानमंत्री मातृ वंदना योजना (PMMVY)',
  'WIDOW-PENSION': 'इंदिरा गांधी राष्ट्रीय विधवा निवृत्तीवेतन योजना (Widow Pension)',
  'MLBY-MH': 'मुख्यमंत्री माझी लाडकी बहीण योजना (Majhi Ladki Bahin)',
  'AB-PMJAY': 'आयुष्मान भारत — वय वंदना (AB-PMJAY 70+)',
};

export const InteractiveChecklistWidget: React.FC<InteractiveChecklistWidgetProps> = ({
  data,
  schemeName,
  lang,
  onPrefillClick,
  onAskMissingDoc,
}) => {
  const { language } = useLanguage();
  const activeLang = lang || language || 'en';
  const [expandedDocs, setExpandedDocs] = useState<Record<string, boolean>>({});

  const items = data.items || [];
  const mandatoryTotal =
    data.mandatory_total ??
    data.mandatory_count ??
    items.filter((d) => d.is_mandatory).length;

  const mandatoryReady =
    data.mandatory_ready ??
    items.filter((d) => d.is_mandatory && (d.status === 'verified' || d.status === 'uploaded' || d.status === 'extracted')).length;

  const progressPercent =
    data.readiness_percentage !== undefined
      ? Math.round(data.readiness_percentage)
      : mandatoryTotal > 0
      ? Math.round((mandatoryReady / mandatoryTotal) * 100)
      : 100;

  const toggleExpand = (docType: string) => {
    setExpandedDocs((prev) => ({
      ...prev,
      [docType]: !prev[docType],
    }));
  };

  const schemeDisplayName =
    data.scheme_name ||
    schemeName ||
    (data.scheme_code ? SCHEME_NAME_MAP[data.scheme_code] : undefined) ||
    data.scheme_code ||
    (activeLang === 'en' ? 'Scheme Documents' : activeLang === 'hi' ? 'योजना दस्तावेज़' : 'योजना कागदपत्रे');

  const titleHeader =
    activeLang === 'en'
      ? 'Required Document Checklist'
      : activeLang === 'hi'
      ? 'आवश्यक दस्तावेज़ चेकलिस्ट'
      : 'आवश्यक कागदपत्रे पडताळणी यादी';

  const readySummaryText =
    activeLang === 'en'
      ? `${mandatoryReady} of ${mandatoryTotal} mandatory documents ready`
      : activeLang === 'hi'
      ? `${mandatoryTotal} में से ${mandatoryReady} अनिवार्य दस्तावेज़ तैयार हैं`
      : `${mandatoryTotal} पैकी ${mandatoryReady} अनिवार्य कागदपत्रे उपलब्ध`;

  return (
    <div className="w-full mt-3.5 bg-gradient-to-b from-white to-ivory-50/60 rounded-2xl border border-navy/12 shadow-subtle p-4 space-y-4">
      {/* Header & Readiness Counter */}
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-saffron-light text-saffron-dark flex items-center justify-center border border-saffron/30 shadow-xs shrink-0">
              <FileText className="w-4 h-4 text-saffron-vibrant" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-navy font-editorial flex items-center gap-1.5 flex-wrap">
                <span>{titleHeader}</span>
                {data.scheme_code && (
                  <span className="text-[10px] font-mono bg-ivory-100 text-navy/70 px-2 py-0.5 rounded border border-navy/10">
                    {data.scheme_code}
                  </span>
                )}
              </h4>
              <p className="text-[11px] text-navy/60 font-sans">
                {schemeDisplayName && <span className="font-semibold text-navy/80 mr-1.5">{schemeDisplayName} •</span>}
                <span>{readySummaryText}</span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span
              className={`text-xs font-bold px-2.5 py-1 rounded-full border ${
                progressPercent === 100
                  ? 'bg-sage-light text-sage-green border-sage/30'
                  : 'bg-amber-50 text-amber-800 border-amber-200'
              }`}
            >
              {progressPercent}% {activeLang === 'en' ? 'Ready' : activeLang === 'hi' ? 'तैयार' : 'सज्ज'}
            </span>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-navy/8 rounded-full h-1.5 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              progressPercent === 100 ? 'bg-sage-green' : 'bg-saffron'
            }`}
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* Document Items List */}
      <div className="space-y-2">
        {items.map((doc) => {
          const isVerified = doc.status === 'verified';
          const isUploaded = doc.status === 'uploaded' || doc.status === 'extracted';
          const isPending =
            doc.status === 'pending_review' ||
            doc.status === 'verification_pending' ||
            doc.status === 'pending';
          const isExpired = doc.status === 'expired';
          const isMissing = doc.status === 'missing' || (!isVerified && !isUploaded && !isPending && !isExpired);

          const isExpanded = !!expandedDocs[doc.document_type];
          const sourcing = doc.sourcing;

          const processingTime = sourcing?.processing_time_sla || sourcing?.expected_processing_days;
          const portalUrl = sourcing?.portal_url || sourcing?.official_url;
          const hasSourcingInfo = Boolean(
            sourcing &&
              (sourcing.issuing_authority ||
                sourcing.where_to_obtain ||
                sourcing.verified_fee ||
                processingTime ||
                portalUrl)
          );

          const cardBorderClass = isVerified
            ? 'bg-white border-navy/10 hover:border-emerald-200'
            : isUploaded
            ? 'bg-white border-navy/10 hover:border-blue-200'
            : isPending
            ? 'bg-white border-navy/10 hover:border-indigo-200'
            : isExpired
            ? 'bg-rose-50/30 border-rose-200/70 hover:border-rose-300'
            : 'bg-amber-50/40 border-amber-200/70 hover:border-amber-300';

          const mandatoryTag = doc.is_mandatory
            ? (activeLang === 'en' ? 'Mandatory' : 'अनिवार्य')
            : (activeLang === 'en' ? 'Optional' : activeLang === 'hi' ? 'वैकल्पिक' : 'ऐच्छिक');

          const statusBadgeText = isVerified
            ? (activeLang === 'en' ? '● Verified in Vault' : activeLang === 'hi' ? '● डिजीलॉकर में सत्यापित' : '● व्हॉल्टमध्ये पडताळलेले')
            : isUploaded
            ? (activeLang === 'en' ? '● In Vault / Uploaded' : activeLang === 'hi' ? '● अपलोड किया गया' : '● व्हॉल्टमध्ये उपलब्ध')
            : isPending
            ? (activeLang === 'en' ? '● Verification Pending' : activeLang === 'hi' ? '● सत्यापन लंबित' : '● पडताळणी प्रलंबित')
            : isExpired
            ? (activeLang === 'en' ? '● Expired' : activeLang === 'hi' ? '● कालावधि समाप्त' : '● कालबाह्य')
            : (activeLang === 'en' ? '● Missing / Required' : activeLang === 'hi' ? '● अनुपलब्ध / आवश्यक' : '● आवश्यक / उपलब्ध नाही');

          return (
            <div
              key={doc.document_type}
              className={`rounded-xl border transition-all ${cardBorderClass} p-3 text-xs shadow-xs space-y-2`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-2.5 min-w-0">
                  <div className="mt-0.5 shrink-0">
                    {isVerified ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    ) : isUploaded ? (
                      <CheckCircle2 className="w-4 h-4 text-blue-600" />
                    ) : isPending ? (
                      <Clock className="w-4 h-4 text-indigo-600" />
                    ) : isExpired ? (
                      <AlertTriangle className="w-4 h-4 text-rose-600" />
                    ) : (
                      <AlertCircle className="w-4 h-4 text-amber-600" />
                    )}
                  </div>
                  <div className="min-w-0 space-y-1">
                    <span className="font-semibold text-navy block text-xs truncate">
                      {doc.title}
                    </span>
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span
                        className={`text-[9.5px] px-1.5 py-0.5 rounded font-medium ${
                          doc.is_mandatory
                            ? 'bg-rose-50 text-rose-700 border border-rose-200'
                            : 'bg-ivory-100 text-navy/60 border border-navy/10'
                        }`}
                      >
                        {mandatoryTag}
                      </span>

                      <span
                        className={`text-[9.5px] px-1.5 py-0.5 rounded font-semibold ${
                          isVerified
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : isUploaded
                            ? 'bg-blue-50 text-blue-700 border border-blue-200'
                            : isPending
                            ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                            : isExpired
                            ? 'bg-rose-50 text-rose-700 border border-rose-300'
                            : 'bg-amber-100 text-amber-900 border border-amber-300'
                        }`}
                      >
                        {statusBadgeText}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Sourcing toggle button */}
                {hasSourcingInfo && (
                  <button
                    type="button"
                    onClick={() => toggleExpand(doc.document_type)}
                    className="flex items-center gap-1 text-[11px] font-semibold text-saffron-dark hover:text-saffron transition-colors px-2 py-1 rounded-lg hover:bg-saffron-light shrink-0"
                    title={activeLang === 'en' ? 'View official sourcing guidance' : activeLang === 'hi' ? 'दस्तावेज़ कैसे प्राप्त करें, देखें' : 'कागदपत्र कसे मिळवावे ते पहा'}
                  >
                    <span>
                      {isExpanded
                        ? (activeLang === 'en' ? 'Hide Info' : activeLang === 'hi' ? 'छुपाएं' : 'माहिती लपवा')
                        : (activeLang === 'en' ? 'Sourcing Info' : activeLang === 'hi' ? 'प्राप्ति केंद्र' : 'कसे मिळवावे')}
                    </span>
                    {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                  </button>
                )}
              </div>

              {/* Expandable Official Government Sourcing Details */}
              {isExpanded && sourcing && hasSourcingInfo && (
                <div className="mt-2 pt-2 border-t border-navy/8 bg-ivory-50/80 rounded-lg p-2.5 space-y-2 text-[11px] text-navy/80">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {sourcing.issuing_authority && (
                      <div className="flex items-start gap-1.5">
                        <Building2 className="w-3.5 h-3.5 text-navy/50 shrink-0 mt-0.5" />
                        <div>
                          <span className="font-bold text-navy block text-[10px] uppercase">
                            {activeLang === 'en' ? 'Issuing Authority:' : activeLang === 'hi' ? 'जारीकर्ता प्राधिकरण:' : 'सक्षम प्राधिकरण:'}
                          </span>
                          <span>{sourcing.issuing_authority}</span>
                        </div>
                      </div>
                    )}

                    {sourcing.where_to_obtain && (
                      <div className="flex items-start gap-1.5">
                        <MapPin className="w-3.5 h-3.5 text-navy/50 shrink-0 mt-0.5" />
                        <div>
                          <span className="font-bold text-navy block text-[10px] uppercase">
                            {activeLang === 'en' ? 'Where to Obtain:' : activeLang === 'hi' ? 'कहाँ प्राप्त करें:' : 'कुठे मिळेल:'}
                          </span>
                          <span>{sourcing.where_to_obtain}</span>
                        </div>
                      </div>
                    )}

                    {sourcing.verified_fee && (
                      <div className="flex items-start gap-1.5">
                        <IndianRupee className="w-3.5 h-3.5 text-navy/50 shrink-0 mt-0.5" />
                        <div>
                          <span className="font-bold text-navy block text-[10px] uppercase">
                            {activeLang === 'en' ? 'Statutory Fee:' : activeLang === 'hi' ? 'सरकारी शुल्क:' : 'अधिकृत शुल्क:'}
                          </span>
                          <span className="font-semibold text-emerald-800">{sourcing.verified_fee}</span>
                        </div>
                      </div>
                    )}

                    {processingTime && (
                      <div className="flex items-start gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-navy/50 shrink-0 mt-0.5" />
                        <div>
                          <span className="font-bold text-navy block text-[10px] uppercase">
                            {activeLang === 'en' ? 'Processing Time:' : activeLang === 'hi' ? 'प्रसंस्करण समय:' : 'अपेक्षित कालावधी:'}
                          </span>
                          <span>{processingTime}</span>
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center justify-between pt-1 border-t border-navy/6 flex-wrap gap-2">
                    {portalUrl && (
                      <a
                        href={portalUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-[10.5px] font-bold text-saffron-dark hover:underline"
                      >
                        <span>{activeLang === 'en' ? 'Official Portal' : activeLang === 'hi' ? 'आधिकारिक पोर्टल' : 'अधिकृत संकेतस्थळ'}</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}

                    {isMissing && onAskMissingDoc && (
                      <button
                        type="button"
                        onClick={() => onAskMissingDoc(doc.title)}
                        className="text-[10px] text-navy/70 hover:text-navy underline flex items-center gap-1"
                      >
                        <HelpCircle className="w-3 h-3 text-saffron" />
                        <span>
                          {activeLang === 'en'
                            ? 'How to obtain this document?'
                            : activeLang === 'hi'
                            ? 'दस्तावेज़ कैसे प्राप्त करें?'
                            : 'कागदपत्र कसे मिळवावे?'}
                        </span>
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Call to Action: Proceed to Pre-fill Draft */}
      <div className="pt-2 border-t border-navy/8 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <p className="text-[11px] text-navy/60 flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-saffron-vibrant shrink-0" />
          <span>
            {mandatoryReady >= mandatoryTotal
              ? (activeLang === 'en'
                  ? 'All mandatory documents are ready. You can now proceed to pre-fill your application draft.'
                  : activeLang === 'hi'
                  ? 'सभी अनिवार्य दस्तावेज़ तैयार हैं। आप आवेदन का मसौदा भर सकते हैं।'
                  : 'सर्व आवश्यक कागदपत्रे उपलब्ध आहेत. आपण आता अर्जाचा मसुदा तयार करू शकता.')
              : (activeLang === 'en'
                  ? 'You can pre-fill an application draft using your available profile details.'
                  : activeLang === 'hi'
                  ? 'उपलब्ध जानकारी के आधार पर आप मसौदा तैयार कर सकते हैं।'
                  : 'उपलब्ध माहितीच्या आधारे आपण तात्पुरता मसुदा तयार करू शकता.')}
          </span>
        </p>

        {onPrefillClick && (
          <Button
            variant="saffron"
            size="sm"
            onClick={onPrefillClick}
            rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
            className="shrink-0 font-bold shadow-subtle"
          >
            {activeLang === 'en'
              ? 'Pre-fill Application Draft'
              : activeLang === 'hi'
              ? 'आवेदन का मसौदा भरें'
              : 'अर्जाचा मसुदा भरा'}
          </Button>
        )}
      </div>
    </div>
  );
};
