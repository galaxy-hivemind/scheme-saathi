import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ShieldCheck,
  CheckCircle2,
  ExternalLink,
  Copy,
  Check,
  Building2,
  FolderKanban,
  ArrowRight,
  Info,
  AlertTriangle,
} from 'lucide-react';
import { Button } from '@/components/common/Button';
import {
  ApplicationReviewSummary,
  NormalizedApplicationRecord,
  PortalIntegrationInfo,
} from '@/types';

export interface ConfirmationPayload {
  requires_confirmation?: boolean;
  confirmed?: boolean;
  confirmed_at?: string;
  confirmed_version?: number;
  confirmed_hash?: string;
  application_id?: string | null;
  version?: number;
  data_hash?: string | null;
  integration_supported?: boolean;
  manual_portal_required?: boolean;
  submitted?: boolean;
  lifecycle_state?: string;
  submission_status?: string;
  external_reference_id?: string | null;
  handoff_reference?: string;
  official_portal_url?: string;
  portal_url?: string;
  tracking_url?: string | null;
  submission_method?: string;
  official_reference_number?: string | null;
  reference_source?: string | null;
  submission_date?: string | null;
  scheme_code?: string;
  portal_integration?: PortalIntegrationInfo;
  application_record?: NormalizedApplicationRecord;
  review_summary?: ApplicationReviewSummary;
  message?: string;
}

interface HandoffConfirmationWidgetProps {
  data: ConfirmationPayload;
  language?: 'en' | 'hi' | 'mr';
  onConfirm?: (meta?: { expected_version?: number; expected_hash?: string; idempotency_key?: string }) => void;
  onRecordPortalReference?: (
    officialReferenceNumber: string,
    meta?: { application_id?: string | null }
  ) => void;
}

export const HandoffConfirmationWidget: React.FC<HandoffConfirmationWidgetProps> = ({
  data,
  language = 'en',
  onConfirm,
  onRecordPortalReference,
}) => {
  const [consentChecked, setConsentChecked] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);
  const [portalRefInput, setPortalRefInput] = useState<string>('');
  const [portalRefError, setPortalRefError] = useState<string | null>(null);
  const [portalRefSubmitting, setPortalRefSubmitting] = useState<boolean>(false);

  const pickText = (en: string, hi: string, mr: string) => {
    if (language === 'hi') return hi;
    if (language === 'mr') return mr;
    return en;
  };

  const portalInfo = data.portal_integration || data.review_summary?.portal_integration;
  const appRecord = data.application_record || data.review_summary?.application_record;
  const internalAppId = data.application_id || appRecord?.application_id || null;
  const portalUrl =
    portalInfo?.official_application_url ||
    data.official_portal_url ||
    data.portal_url ||
    appRecord?.portal_url ||
    portalInfo?.official_url ||
    'https://india.gov.in';
  const trackingUrl = data.tracking_url || appRecord?.tracking_url || portalInfo?.tracking_url || null;
  const portalRefRaw =
    data.official_reference_number ||
    appRecord?.official_reference_number ||
    data.review_summary?.submission?.official_reference_number ||
    null;
  const portalRef =
    portalRefRaw &&
    !String(portalRefRaw).toUpperCase().startsWith('SAATHI/') &&
    (!internalAppId || String(portalRefRaw) !== String(internalAppId))
      ? portalRefRaw
      : null;

  const rawExtRef =
    data.external_reference_id ||
    (!String(data.handoff_reference || '').toUpperCase().startsWith('SAATHI/') ? data.handoff_reference : null) ||
    null;
  const extRef = rawExtRef && !String(rawExtRef).toUpperCase().startsWith('SAATHI/') ? rawExtRef : null;
  const reviewVersion = data.version ?? data.review_summary?.version ?? data.confirmed_version ?? 1;
  const reviewHash = data.data_hash ?? data.review_summary?.data_hash ?? data.confirmed_hash ?? null;
  const isSubmissionUnknown =
    data.lifecycle_state === 'submission_unknown' ||
    data.submission_status === 'submission_unknown' ||
    data.submission_status === 'uncertain';
  const isSubmissionFailed =
    !isSubmissionUnknown &&
    (data.lifecycle_state === 'submission_failed' ||
      data.submission_status === 'submission_failed' ||
      data.submission_status === 'failed_retryable' ||
      data.submission_status === 'failed_permanent');
  const isPortalSubmitted =
    !isSubmissionUnknown &&
    !isSubmissionFailed &&
    (data.lifecycle_state === 'portal_submitted' ||
      data.submission_status === 'portal_submitted' ||
      (Boolean(portalRef) && !data.integration_supported));
  const isOfficialSubmitted = Boolean(
    !isPortalSubmitted && !isSubmissionUnknown && !isSubmissionFailed && data.submitted && extRef
  );
  const isAwaitingConsent = Boolean(
    data.requires_confirmation &&
      !data.confirmed &&
      !extRef &&
      !portalRef &&
      !isPortalSubmitted &&
      !isSubmissionUnknown
  );
  const displayRef = portalRef || extRef;
  const portalSteps = portalInfo?.official_instructions?.online_steps || [];
  const submissionDate = data.submission_date || appRecord?.submission_date || null;
  const submissionMethod =
    portalInfo?.submission_method_label ||
    data.submission_method ||
    appRecord?.submission_method ||
    (data.integration_supported
      ? pickText('Mode A: Direct Authorized API', 'मोड A: प्रत्यक्ष अधिकृत API', 'पद्धत A: थेट अधिकृत API')
      : pickText('Mode B: Portal-Assisted', 'मोड B: पोर्टल-सहाय्यित', 'पद्धत B: पोर्टल-सहाय्यित'));

  const handleCopyRef = () => {
    if (displayRef) {
      navigator.clipboard.writeText(displayRef);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }
  };

  const handlePortalRefSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!onRecordPortalReference) return;
    const trimmed = portalRefInput.trim();
    if (!trimmed) {
      setPortalRefError(
        pickText(
          'Enter the official application reference number returned by the government portal.',
          'सरकारी पोर्टल द्वारा दी गई आधिकारिक संदर्भ संख्या दर्ज करें।',
          'शासकीय पोर्टलवरून मिळालेला अधिकृत संदर्भ क्रमांक नोंदवा.'
        )
      );
      return;
    }
    const upper = trimmed.toUpperCase();
    if (
      upper.startsWith('SAATHI/') ||
      upper.startsWith('APP-') ||
      (internalAppId && trimmed.toLowerCase() === String(internalAppId).toLowerCase())
    ) {
      setPortalRefError(
        pickText(
          'Internal draft IDs and synthetic references cannot be saved as official portal references.',
          'आंतरिक ड्राफ्ट ID या सिंथेटिक संदर्भ को आधिकारिक पोर्टल संदर्भ के रूप में सहेजा नहीं जा सकता।',
          'अंतर्गत मसुदा आयडी किंवा कृत्रिम संदर्भ अधिकृत पोर्टल संदर्भ म्हणून जतन करता येत नाहीत.'
        )
      );
      return;
    }
    setPortalRefError(null);
    setPortalRefSubmitting(true);
    onRecordPortalReference(trimmed, { application_id: internalAppId });
    setTimeout(() => setPortalRefSubmitting(false), 1200);
  };

  const handleConfirmClick = () => {
    if (!onConfirm) return;
    const idemKey = `chat:${data.application_id || data.scheme_code || 'scheme'}:v${reviewVersion}:${(reviewHash || 'hash').slice(0, 12)}`;
    onConfirm({
      expected_version: reviewVersion,
      expected_hash: reviewHash || undefined,
      idempotency_key: idemKey,
    });
  };

  // Stage A: Complete Application Review Summary + Explicit Citizen Authorization
  if (isAwaitingConsent) {
    const sections = data.review_summary?.sections || [];
    const docItems = data.review_summary?.documents?.items || [];

    return (
      <div className="w-full mt-3.5 bg-linear-to-b from-white to-amber-50/40 rounded-2xl border border-amber-200/80 shadow-subtle p-4 space-y-3.5">
        <div className="flex items-start justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-amber-100 text-amber-800 flex items-center justify-center border border-amber-300 shadow-xs shrink-0">
              <ShieldCheck className="w-4 h-4 text-amber-700" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-navy font-editorial">
                {pickText(
                  'Complete Application Review & Explicit Consent',
                  'पूर्ण आवेदन समीक्षा एवं अंतिम नागरिक सहमति',
                  'अर्जाची संपूर्ण तपासणी व अंतिम संमती'
                )}
              </h4>
              <p className="text-[11px] text-navy/60">
                {pickText(
                  'Your confirmation applies strictly to this exact reviewed version.',
                  'आपकी पुष्टि केवल इस समीक्षित संस्करण पर लागू होगी।',
                  'तुमची संमती केवळ या तपासलेल्या आवृत्तीसाठीच लागू होईल.'
                )}
              </p>
            </div>
          </div>

          <span className="text-[10px] font-mono bg-ivory-100 text-navy/80 px-2 py-0.5 rounded border border-navy/10">
            v{reviewVersion}
            {reviewHash ? ` • ${reviewHash.slice(0, 8)}` : ''}
          </span>
        </div>

        {/* Reviewed Fields Summary */}
        {sections.length > 0 && (
          <div className="bg-white rounded-xl p-3 border border-navy/10 space-y-2.5 max-h-60 overflow-y-auto">
            {sections.map((sec) => (
              <div key={sec.section_id} className="space-y-1.5">
                <div className="text-[10px] font-bold uppercase tracking-wider text-navy/60 border-b border-navy/8 pb-0.5">
                  {sec.title}
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-[11px]">
                  {sec.fields.map((f) => (
                    <div key={f.name} className="bg-ivory-50/70 rounded-lg px-2 py-1 border border-navy/6">
                      <div className="flex items-center justify-between gap-1 text-[10px] text-navy/60">
                        <span className="truncate font-medium">{f.label}</span>
                        {f.source_badge && (
                          <span className="text-[9px] px-1.5 py-0.2 rounded bg-white border border-navy/10 text-navy/70 shrink-0">
                            {f.source_badge}
                          </span>
                        )}
                      </div>
                      <div className="font-semibold text-navy truncate">
                        {f.value !== null && f.value !== undefined && String(f.value).trim() !== ''
                          ? String(f.value)
                          : pickText('Not provided', 'उपलब्ध नहीं', 'नमूद केलेले नाही')}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Verified Documents Summary */}
        {docItems.length > 0 && (
          <div className="flex flex-wrap gap-1.5 text-[10.5px]">
            {docItems.map((doc) => (
              <span
                key={doc.document_type}
                className={`px-2 py-0.5 rounded-full border font-medium ${
                  doc.status === 'verified'
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : doc.status === 'waived'
                    ? 'bg-slate-50 text-slate-600 border-slate-200'
                    : 'bg-amber-50 text-amber-800 border-amber-200'
                }`}
              >
                {doc.title}: {doc.status_label}
              </span>
            ))}
          </div>
        )}

        {/* Official Portal Integration Summary (Stage A) */}
        <div className="bg-white rounded-xl p-3 border border-navy/10 space-y-1.5 text-[11px] text-navy/85">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <span className="font-bold text-navy flex items-center gap-1.5">
              <Building2 className="w-3.5 h-3.5 text-saffron shrink-0" />
              <span>
                {portalInfo?.submission_method_label ||
                  (data.integration_supported
                    ? pickText('Mode A: Direct Authorized API', 'मोड A: प्रत्यक्ष अधिकृत API', 'पद्धत A: थेट अधिकृत API')
                    : pickText(
                        'Mode B: Portal-Assisted Guided Submission',
                        'मोड B: पोर्टल-सहाय्यित निर्देशित आवेदन',
                        'पद्धत B: पोर्टल-सहाय्यित मार्गदर्शित अर्ज'
                      ))}
              </span>
            </span>
            {portalInfo?.application_availability_label && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-ivory-100 text-navy/75 border border-navy/10 font-medium">
                {portalInfo.application_availability_label}
              </span>
            )}
          </div>
          {portalUrl && (
            <div className="text-[10.5px] text-navy/70 break-all">
              <span className="font-semibold text-navy/85">
                {pickText('Official Portal:', 'आधिकारिक पोर्टल:', 'अधिकृत पोर्टल:')}{' '}
              </span>
              <a
                href={portalUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="underline text-saffron-dark hover:text-navy"
              >
                {portalUrl}
              </a>
            </div>
          )}
          {trackingUrl && (
            <div className="text-[10.5px] text-navy/70 break-all">
              <span className="font-semibold text-navy/85">
                {pickText('Status Tracking URL:', 'स्थिति ट्रैकिंग लिंक:', 'स्थिती तपासणी लिंक:')}{' '}
              </span>
              <a
                href={trackingUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="underline text-saffron-dark hover:text-navy"
              >
                {trackingUrl}
              </a>
            </div>
          )}
          {portalInfo?.security_controls_notice && (
            <p className="text-[10.5px] text-amber-900 bg-amber-50/70 px-2.5 py-1.5 rounded-lg border border-amber-200/70">
              {portalInfo.security_controls_notice}
            </p>
          )}
        </div>

        {/* Explicit Authorization Disclosure & Consent Checkbox */}
        <div className="bg-white rounded-xl p-3 border border-amber-200/70 space-y-2 text-xs text-navy/90">
          <div className="flex items-start gap-2 text-[11.5px] leading-relaxed text-navy/85">
            <Info className="w-3.5 h-3.5 text-amber-700 shrink-0 mt-0.5" />
            <span>
              {data.integration_supported
                ? pickText(
                    `Authorizing this action submits version v${reviewVersion} to the verified official portal gateway.`,
                    `इसकी पुष्टि करने से संस्करण v${reviewVersion} सत्यापित आधिकारिक पोर्टल गेटवे पर सबमिट किया जाएगा।`,
                    `या संमतीने आवृत्ती v${reviewVersion} सत्यापित अधिकृत पोर्टल गेटवेवर सादर केली जाईल.`
                  )
                : pickText(
                    `No direct government API submission is active for this scheme. Confirming locks your explicit authorization of version v${reviewVersion}; final submission must be completed manually on the official portal.`,
                    `इस योजना के लिए प्रत्यक्ष सरकारी API सबमिशन उपलब्ध नहीं है। पुष्टि करने से संस्करण v${reviewVersion} पर आपकी स्वीकृति दर्ज होती है; अंतिम आवेदन आपको आधिकारिक पोर्टल पर स्वयं जमा करना होगा।`,
                    `या योजनेसाठी थेट शासकीय API सादरीकरण उपलब्ध नाही. संमती दिल्याने आवृत्ती v${reviewVersion} ची अधिकृत नोंद होते; अंतिम अर्ज अधिकृत पोर्टलवर स्वतः सादर करावा लागेल.`
                  )}
            </span>
          </div>

          <label className="flex items-start gap-2 pt-1 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={consentChecked}
              onChange={(e) => setConsentChecked(e.target.checked)}
              className="mt-0.5 rounded text-saffron focus:ring-saffron w-4 h-4"
            />
            <span className="text-[11.5px] font-medium leading-snug">
              {pickText(
                `I have reviewed all fields and documents in version v${reviewVersion} and explicitly authorize this confirmation.`,
                `मैंने संस्करण v${reviewVersion} के सभी विवरण और दस्तावेज़ों की समीक्षा कर ली है और इसकी स्पष्ट स्वीकृति देता/देती हूँ।`,
                `मी आवृत्ती v${reviewVersion} मधील सर्व माहिती व कागदपत्रे तपासली आहेत आणि स्पष्ट संमती देत आहे.`
              )}
            </span>
          </label>
        </div>

        {onConfirm && (
          <div className="flex justify-end pt-1">
            <Button
              variant="saffron"
              size="sm"
              disabled={!consentChecked}
              onClick={handleConfirmClick}
              rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
              className="font-bold shadow-subtle text-xs"
            >
              {pickText(
                `Confirm Reviewed Version v${reviewVersion}`,
                `समीक्षित संस्करण v${reviewVersion} की पुष्टि करें`,
                `तपासलेली आवृत्ती v${reviewVersion} नक्की करा`
              )}
            </Button>
          </div>
        )}
      </div>
    );
  }

  // Stage B: Post-Confirmation Outcome (Manual Portal Required, Submission Unknown, Failed, or Verified External Portal Receipt)
  return (
    <div
      className={`w-full mt-3.5 rounded-2xl border shadow-subtle p-4 space-y-3.5 ${
        isOfficialSubmitted
          ? 'bg-linear-to-b from-white to-sage-light/30 border-sage/30'
          : isSubmissionUnknown
          ? 'bg-linear-to-b from-white to-amber-50/50 border-amber-300'
          : isSubmissionFailed
          ? 'bg-linear-to-b from-white to-rose-50/40 border-rose-200'
          : 'bg-linear-to-b from-white to-emerald-50/30 border-emerald-200'
      }`}
    >
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <div
            className={`w-8 h-8 rounded-xl flex items-center justify-center border shadow-xs ${
              isSubmissionUnknown
                ? 'bg-amber-100 text-amber-800 border-amber-300'
                : isSubmissionFailed
                ? 'bg-rose-100 text-rose-700 border-rose-200'
                : 'bg-sage-light text-sage-green border-sage/30'
            }`}
          >
            {isSubmissionUnknown ? (
              <AlertTriangle className="w-4 h-4 text-amber-700" />
            ) : isSubmissionFailed ? (
              <AlertTriangle className="w-4 h-4 text-rose-600" />
            ) : (
              <CheckCircle2 className="w-4 h-4 text-sage-green" />
            )}
          </div>
          <div>
            <h4 className="text-xs font-bold text-navy font-editorial flex items-center gap-1.5">
              <span>
                {isPortalSubmitted
                  ? pickText(
                      `Official Portal Reference Recorded (v${reviewVersion})`,
                      `आधिकारिक पोर्टल संदर्भ संख्या दर्ज (v${reviewVersion})`,
                      `अधिकृत पोर्टल संदर्भ क्रमांक नोंदवला (v${reviewVersion})`
                    )
                  : isOfficialSubmitted
                  ? pickText(
                      'Submitted via Official Portal Integration',
                      'आधिकारिक पोर्टल एकीकरण द्वारा सबमिट किया गया',
                      'अधिकृत पोर्टल जोडणीद्वारे सादर झाले'
                    )
                  : isSubmissionUnknown
                  ? pickText(
                      'Submission Outcome Unknown — Reconciliation Required',
                      'सबमिशन परिणाम अनिश्चित — पोर्टल जांच आवश्यक',
                      'सादरीकरण स्थिती अनिश्चित — पोर्टल तपासणी आवश्यक'
                    )
                  : isSubmissionFailed
                  ? pickText(
                      'Official Portal Submission Failed',
                      'आधिकारिक पोर्टल पर सबमिशन असफल रहा',
                      'अधिकृत पोर्टलवर अर्ज सादर होऊ शकला नाही'
                    )
                  : pickText(
                      `Confirmed (v${reviewVersion}) — Complete Submission on Official Portal`,
                      `पुष्टि दर्ज (v${reviewVersion}) — आधिकारिक पोर्टल पर अंतिम आवेदन करें`,
                      `संमती नोंदवली (v${reviewVersion}) — अधिकृत पोर्टलवर अर्ज सादर करा`
                    )}
              </span>
            </h4>
            <p className="text-[11px] text-navy/60">
              {isPortalSubmitted
                ? pickText(
                    'Official portal application reference reported by citizen is persisted cleanly (separate from internal draft ID).',
                    'आधिकारिक सरकारी पोर्टल की संदर्भ संख्या सुरक्षित रूप से दर्ज की गई है (आंतरिक ड्राफ्ट ID से अलग)।',
                    'शासकीय पोर्टलवर सादर केलेला अधिकृत संदर्भ क्रमांक सुरक्षित नोंदवला आहे (अंतर्गत मसुदा आयडीपासून वेगळा).'
                  )
                : isOfficialSubmitted
                ? pickText(
                    'Authoritative external reference received and recorded',
                    'आधिकारिक बाह्य संदर्भ संख्या प्राप्त एवं दर्ज की गई',
                    'अधिकृत बाह्य संदर्भ क्रमांक प्राप्त झाला व नोंदवला गेला'
                  )
                : isSubmissionUnknown
                ? pickText(
                    'The portal request timed out or returned an ambiguous response. Blind retries are blocked until reconciled.',
                    'आधिकारिक पोर्टल अनुरोध समय समाप्त या अस्पष्ट रहा। स्थिति पुष्टि तक पुनः प्रयास अवरुद्ध है।',
                    'अधिकृत पोर्टल विनंतीची वेळ संपली किंवा प्रतिसाद अस्पष्ट राहिला. स्थिती तपासेपर्यंत पुन्हा प्रयत्न बंद केला आहे.'
                  )
                : isSubmissionFailed
                ? (data.message ||
                    pickText(
                      'The official portal did not accept this attempt. Check error details in Applications.',
                      'आधिकारिक पोर्टल ने यह प्रयास स्वीकार नहीं किया। आवेदन पृष्ठ पर विवरण देखें।',
                      'अधिकृत पोर्टलने हा प्रयत्न स्वीकारला नाही. अर्ज पृष्ठावर तपशील पहा.'
                    ))
                : pickText(
                    'Scheme Saathi never bypasses portal OTP/CAPTCHA or fakes submissions. Follow the official portal steps below and return with your portal reference number.',
                    'योजना साथी कभी OTP/कैप्चा बायपास नहीं करता। नीचे दिए चरणों से पोर्टल पर आवेदन कर अपनी संदर्भ संख्या यहाँ दर्ज करें।',
                    'योजना साथी कधीही OTP/कॅप्चा बायपास करत नाही. खालील पायऱ्यांनी पोर्टलवर अर्ज सादर करून संदर्भ क्रमांक येथे नोंदवा.'
                  )}
            </p>
          </div>
        </div>

        <span
          className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
            isPortalSubmitted
              ? 'bg-teal-100 text-teal-900 border-teal-300'
              : isOfficialSubmitted
              ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
              : isSubmissionUnknown
              ? 'bg-amber-100 text-amber-900 border-amber-300'
              : isSubmissionFailed
              ? 'bg-rose-100 text-rose-800 border-rose-200'
              : 'bg-amber-50 text-amber-900 border-amber-200'
          }`}
        >
          {isPortalSubmitted
            ? pickText('Portal Submitted (Citizen Reported)', 'पोर्टल पर जमा (नागरिक दर्ज)', 'पोर्टलवर सादर (नागरिकाने नोंदवले)')
            : isOfficialSubmitted
            ? pickText('Submitted', 'सबमिट किया गया', 'सादर केले')
            : isSubmissionUnknown
            ? pickText('Submission Unknown', 'स्थिति अनिश्चित', 'स्थिती अनिश्चित')
            : isSubmissionFailed
            ? pickText('Submission Failed', 'सबमिशन विफल', 'सादरीकरण अयशस्वी')
            : pickText('Official Portal Next', 'आधिकारिक पोर्टल चरण', 'अधिकृत पोर्टल आवश्यक')}
        </span>
      </div>

      {/* ONLY render official reference box when Mode A API or Mode B citizen-returned official portal reference exists */}
      {displayRef && (
        <div className="bg-white rounded-xl p-3 border border-navy/10 space-y-2.5 shadow-xs">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <span className="text-[10px] uppercase font-bold text-navy/50 tracking-wider block">
                {isPortalSubmitted
                  ? pickText(
                      'Official Portal Application Reference Number',
                      'आधिकारिक पोर्टल आवेदन संदर्भ संख्या',
                      'अधिकृत पोर्टल अर्ज संदर्भ क्रमांक'
                    )
                  : pickText(
                      'Official Portal Transaction Reference',
                      'आधिकारिक पोर्टल संदर्भ क्रमांक',
                      'अधिकृत पोर्टल संदर्भ क्रमांक'
                    )}
              </span>
              <span className="font-mono font-bold text-sm text-navy tracking-wide select-all block truncate">
                {displayRef}
              </span>
            </div>

            <button
              type="button"
              onClick={handleCopyRef}
              className={`flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg border transition-all shrink-0 font-medium ${
                copied
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-300'
                  : 'bg-ivory-100 hover:bg-ivory-200 text-navy/70 border-navy/10'
              }`}
              title="Copy reference number"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? pickText('Copied', 'कॉपी हो गया', 'कॉपी झाले') : pickText('Copy', 'कॉपी', 'कॉपी')}</span>
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 pt-2 border-t border-navy/6 text-[10.5px] text-navy/75">
            {internalAppId && (
              <div className="font-mono truncate">
                <span className="font-sans font-semibold text-navy/60">
                  {pickText('Internal Draft ID:', 'आंतरिक ड्राफ्ट ID:', 'अंतर्गत मसुदा आयडी:')}{' '}
                </span>
                {internalAppId}
              </div>
            )}
            <div>
              <span className="font-semibold text-navy/60">
                {pickText('Submission Method:', 'आवेदन माध्यम:', 'अर्ज पद्धत:')}{' '}
              </span>
              {portalInfo?.submission_method_label || submissionMethod}
            </div>
            {submissionDate && (
              <div>
                <span className="font-semibold text-navy/60">
                  {pickText('Submission Date:', 'सबमिशन तिथि:', 'सादर केल्याची तारीख:')}{' '}
                </span>
                {new Date(submissionDate).toLocaleString()}
              </div>
            )}
          </div>
        </div>
      )}

      {isSubmissionUnknown && (
        <div className="bg-amber-50/90 rounded-xl p-3 border border-amber-200 space-y-1 text-xs text-amber-950">
          <div className="font-bold flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-700 shrink-0" />
            <span>
              {pickText(
                'Blind Retries Blocked Until Reconciled',
                'पोर्टल जांच तक पुनः प्रयास अवरुद्ध है',
                'स्थिती तपासेपर्यंत थेट पुन्हा प्रयत्न बंद आहे'
              )}
            </span>
          </div>
          <p className="text-[11.5px] text-amber-900/90">
            {pickText(
              'Open Applications to reconcile whether the official portal accepted the dispatched request.',
              'यह जानने के लिए कि पोर्टल को आवेदन प्राप्त हुआ या नहीं, मेरे आवेदन पृष्ठ पर स्थिति की जांच करें।',
              'पोर्टलवर अर्ज पोहोचला की नाही हे तपासण्यासाठी माझे अर्ज पृष्ठावर स्थिती तपासा.'
            )}
          </p>
        </div>
      )}

      {!isOfficialSubmitted && !isPortalSubmitted && !isSubmissionUnknown && !isSubmissionFailed && (
        <div className="bg-white/90 rounded-xl p-3 border border-navy/8 space-y-2.5 text-xs text-navy/90">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <h5 className="text-[10.5px] font-bold text-navy uppercase tracking-wider flex items-center gap-1">
              <Building2 className="w-3 h-3 text-saffron" />
              <span>
                {portalInfo?.submission_method_label ||
                  pickText(
                    'Official Portal Submission Steps',
                    'आधिकारिक पोर्टल पर अगले चरण',
                    'अधिकृत पोर्टलवरील पुढील पायऱ्या'
                  )}
              </span>
            </h5>
            {internalAppId && (
              <span className="text-[10px] font-mono text-navy/55">
                {pickText('Draft ID:', 'ड्राफ्ट ID:', 'मसुदा आयडी:')} {internalAppId}
              </span>
            )}
          </div>

          <div className="space-y-1.5 text-[11.5px] text-navy/80">
            {portalSteps.length > 0 ? (
              portalSteps.map((stepText, idx) => (
                <div key={idx} className="flex items-start gap-2">
                  <span className="w-4 h-4 rounded-full bg-saffron-light text-saffron-dark font-bold text-[10px] flex items-center justify-center shrink-0 mt-0.5">
                    {idx + 1}
                  </span>
                  <span>{stepText}</span>
                </div>
              ))
            ) : (
              <>
                <div className="flex items-start gap-2">
                  <span className="w-4 h-4 rounded-full bg-saffron-light text-saffron-dark font-bold text-[10px] flex items-center justify-center shrink-0 mt-0.5">
                    1
                  </span>
                  <span>
                    {pickText(
                      'Open the official government portal below.',
                      'नीचे दिए गए बटन से आधिकारिक सरकारी पोर्टल खोलें।',
                      'खालील बटणावर क्लिक करून अधिकृत शासकीय पोर्टल उघडा.'
                    )}
                  </span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="w-4 h-4 rounded-full bg-saffron-light text-saffron-dark font-bold text-[10px] flex items-center justify-center shrink-0 mt-0.5">
                    2
                  </span>
                  <span>
                    {pickText(
                      'Submit manually using your confirmed field values, complete portal OTP/CAPTCHA, and save your official reference number below.',
                      'पुष्ट विवरणों और सत्यापित दस्तावेज़ों के साथ पोर्टल पर आवेदन जमा करें, OTP/कैप्चा पूरा करें और प्राप्त संदर्भ संख्या नीचे दर्ज करें।',
                      'नक्की केलेल्या माहितीसह पोर्टलवर अर्ज सादर करा, OTP/कॅप्चा पूर्ण करा आणि मिळालेला अधिकृत संदर्भ क्रमांक खाली नोंदवा.'
                    )}
                  </span>
                </div>
              </>
            )}
          </div>

          {portalInfo?.official_instructions?.offline_process && (
            <p className="text-[11px] text-navy/70 bg-ivory-50 px-2.5 py-1.5 rounded-lg border border-navy/8">
              <span className="font-semibold text-navy">
                {pickText('Offline / CSC Alternative:', 'ऑफ़लाइन / CSC विकल्प:', 'ऑफलाइन / CSC पर्याय:')}{' '}
              </span>
              {portalInfo.official_instructions.offline_process}
            </p>
          )}

          {portalInfo?.security_controls_notice && (
            <p className="text-[10.5px] text-amber-900 bg-amber-50/70 px-2.5 py-1.5 rounded-lg border border-amber-200/70">
              {portalInfo.security_controls_notice}
            </p>
          )}

          {onRecordPortalReference && (
            <form
              onSubmit={handlePortalRefSubmit}
              className="pt-2.5 mt-2 border-t border-navy/8 space-y-2"
            >
              <label className="block text-[11px] font-bold text-navy">
                {pickText(
                  'Submitted on official portal? Record official reference number:',
                  'क्या आधिकारिक पोर्टल पर सबमिट कर दिया? संदर्भ संख्या दर्ज करें:',
                  'अधिकृत पोर्टलवर अर्ज सादर केला का? अधिकृत संदर्भ क्रमांक नोंदवा:'
                )}
              </label>
              <div className="flex flex-col sm:flex-row gap-2">
                <input
                  type="text"
                  value={portalRefInput}
                  onChange={(e) => {
                    setPortalRefInput(e.target.value);
                    if (portalRefError) setPortalRefError(null);
                  }}
                  placeholder={pickText(
                    'e.g. PMK-MH-2026-998812',
                    'उदा. PMK-MH-2026-998812',
                    'उदा. PMK-MH-2026-998812'
                  )}
                  className="flex-1 rounded-xl border border-navy/15 bg-ivory-50/50 px-3 py-1.5 text-xs text-navy font-mono focus:outline-none focus:border-saffron"
                />
                <Button
                  type="submit"
                  variant="saffron"
                  size="sm"
                  disabled={portalRefSubmitting}
                  className="text-xs font-bold shrink-0"
                >
                  {pickText('Save Portal Reference', 'पोर्टल संदर्भ सहेजें', 'पोर्टल संदर्भ जतन करा')}
                </Button>
              </div>
              {portalRefError && (
                <p className="text-[10.5px] text-rose-700 font-medium">{portalRefError}</p>
              )}
            </form>
          )}
        </div>
      )}

      <div className="pt-2 border-t border-navy/8 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5 flex-wrap">
        <Link
          to="/applications"
          className="inline-flex items-center justify-center gap-1.5 text-xs font-semibold text-navy/70 hover:text-navy px-3 py-1.5 rounded-xl border border-navy/10 hover:bg-ivory-100 transition-colors"
        >
          <FolderKanban className="w-3.5 h-3.5 text-saffron" />
          <span>{pickText('View Applications', 'मेरे आवेदन देखें', 'माझे सर्व अर्ज पहा')}</span>
        </Link>

        <div className="flex items-center gap-2 flex-wrap justify-end">
          {trackingUrl && (
            <a
              href={trackingUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-1.5 px-3 py-2 border border-navy/15 bg-white hover:bg-ivory-100 text-navy font-semibold text-xs rounded-xl transition-all"
            >
              <span>{pickText('Track Application Status', 'स्थिति ट्रैक करें', 'अर्ज स्थिती पहा')}</span>
              <ExternalLink className="w-3.5 h-3.5 text-saffron" />
            </a>
          )}

          {portalUrl && (
            <a
              href={portalUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-1.5 px-4 py-2 bg-saffron hover:bg-saffron-dark text-white font-bold text-xs rounded-xl shadow-subtle hover:shadow-premium transition-all"
            >
              <span>{pickText('Open Official Portal', 'आधिकारिक पोर्टल खोलें', 'अधिकृत शासकीय पोर्टल उघडा')}</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          )}
        </div>
      </div>
    </div>
  );
};
