import React, { useEffect, useState } from 'react';
import { applicationService } from '@/services/api/applicationService';
import { ApplicationDraft, ApplicationReviewSummary, SchemeFormSchema } from '@/types';
import { useLanguage } from '@/context/LanguageContext';
import { useAuth } from '@/context/AuthContext';
import { Card, CardContent } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Spinner } from '@/components/common/Spinner';
import { Modal } from '@/components/common/Modal';
import { StatusBanner } from '@/components/common/StatusBanner';
import { EmptyState } from '@/components/common/EmptyState';
import {
  FolderKanban,
  CheckCircle2,
  Clock,
  Send,
  ShieldCheck,
  FileText,
  ExternalLink,
  Sparkles,
  AlertTriangle,
  Pencil,
  Save,
  Check,
  Layers,
  UserCheck,
  FileCheck2,
  ArrowRight,
} from 'lucide-react';
import { Link } from 'react-router-dom';

export const ApplicationsPage: React.FC<{ initialApplications?: ApplicationDraft[] }> = ({
  initialApplications,
}) => {
  const { language } = useLanguage();
  const { profile, user, isLoading: authLoading } = useAuth();
  const [applications, setApplications] = useState<ApplicationDraft[]>(initialApplications ?? []);
  const [loading, setLoading] = useState<boolean>(initialApplications === undefined);
  const [actionError, setActionError] = useState<string | null>(null);

  // Confirmation modal state
  const [confirmingApp, setConfirmingApp] = useState<ApplicationDraft | null>(null);
  const [confirmReview, setConfirmReview] = useState<ApplicationReviewSummary | null>(null);
  const [loadingReview, setLoadingReview] = useState<boolean>(false);
  const [confirmConsentChecked, setConfirmConsentChecked] = useState<boolean>(false);
  const [validatingId, setValidatingId] = useState<string | null>(null);
  const [submittingId, setSubmittingId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [successInfo, setSuccessInfo] = useState<{
    id: string;
    mode: 'submitted' | 'portal_submitted' | 'manual_portal_required' | 'confirmed';
    ref?: string | null;
    version?: number;
    portalUrl?: string;
    trackingUrl?: string;
    message?: string;
  } | null>(null);

  // Mode B Citizen Portal Return Reference modal state
  const [portalRefApp, setPortalRefApp] = useState<ApplicationDraft | null>(null);
  const [portalRefNumber, setPortalRefNumber] = useState<string>('');
  const [portalRefDate, setPortalRefDate] = useState<string>('');
  const [portalRefNotes, setPortalRefNotes] = useState<string>('');
  const [portalRefError, setPortalRefError] = useState<string | null>(null);
  const [recordingPortalRef, setRecordingPortalRef] = useState<boolean>(false);

  // Edit modal state
  const [editingApp, setEditingApp] = useState<ApplicationDraft | null>(null);
  const [editingSchema, setEditingSchema] = useState<SchemeFormSchema | null>(null);
  const [formValues, setFormValues] = useState<Record<string, any>>({});
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [loadingSchema, setLoadingSchema] = useState<boolean>(false);
  const [savingDraft, setSavingDraft] = useState<boolean>(false);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null);
  const [resolvedModalConflicts, setResolvedModalConflicts] = useState<Record<string, boolean>>({});

  const pickText = (en: string, hi: string, mr: string) => {
    if (language === 'hi') return hi;
    if (language === 'mr') return mr;
    return en;
  };

  const fetchApps = async () => {
    setLoading(true);
    try {
      const data = await applicationService.getApplications(language);
      setApplications(data);
    } catch (err) {
      console.error('Failed to load applications:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (initialApplications !== undefined) return;
    if (authLoading) return;
    if (!user && !profile) {
      setApplications([]);
      setLoading(false);
      return;
    }
    fetchApps();
  }, [language, user?.id, authLoading]);

  // Format and clean values so literal 'null' or 'undefined' is never shown
  const renderCleanValue = (val: unknown) => {
    if (
      val === null ||
      val === undefined ||
      val === '' ||
      String(val).trim() === '' ||
      String(val).trim().toLowerCase() === 'null' ||
      String(val).trim().toLowerCase() === 'undefined'
    ) {
      return (
        <span className="text-amber-800 bg-amber-50/80 px-2 py-0.5 rounded text-[11px] font-medium border border-amber-200/70 inline-flex items-center gap-1">
          <AlertTriangle className="w-3 h-3 text-amber-600 shrink-0" />
          <span>{pickText('Not provided', 'उपलब्ध नहीं', 'नमूद केलेले नाही')}</span>
        </span>
      );
    }
    return <span className="font-semibold text-navy truncate block">{String(val)}</span>;
  };

  const handleValidateReadiness = async (appId: string) => {
    setValidatingId(appId);
    setActionError(null);
    try {
      await applicationService.validateDraft(appId, language);
      await fetchApps();
    } catch (err: any) {
      setActionError(err?.message || 'Failed to validate readiness.');
    } finally {
      setValidatingId(null);
    }
  };

  const handleOpenConfirmModal = async (app: ApplicationDraft) => {
    setConfirmingApp(app);
    setConfirmReview(app.review_summary || null);
    setConfirmConsentChecked(false);
    setActionError(null);
    setLoadingReview(true);
    try {
      const review = await applicationService.getApplicationReview(app.id, language);
      setConfirmReview(review);
    } catch (err) {
      console.error('Failed to fetch application review:', err);
    } finally {
      setLoadingReview(false);
    }
  };

  const handleConfirmOnly = async () => {
    if (!confirmingApp || !confirmConsentChecked) return;
    setSubmitting(true);
    setActionError(null);
    try {
      const targetVersion = confirmReview?.version ?? confirmingApp.version ?? 1;
      const targetHash = confirmReview?.data_hash ?? confirmingApp.data_hash;
      const res = await applicationService.confirmApplication(confirmingApp.id, language, {
        consent_acknowledged: true,
        expected_version: targetVersion,
        expected_hash: targetHash,
      });
      setSuccessInfo({
        id: confirmingApp.id,
        mode: 'confirmed',
        version: res.confirmed_version || targetVersion,
        portalUrl: confirmingApp.official_url || res.official_portal_url || 'https://india.gov.in',
        message: res.message,
      });
      setConfirmingApp(null);
      setConfirmReview(null);
      await fetchApps();
    } catch (err: any) {
      setActionError(
        err?.message ||
          pickText(
            'Unable to confirm application version. Please re-validate fields and Vault documents.',
            'आवेदन की पुष्टि नहीं हो सकी। कृपया सभी विवरण और दस्तावेज़ पुनः जांचें।',
            'अर्जाची पुष्टी होऊ शकली नाही. कृपया सर्व माहिती व कागदपत्रे पुन्हा तपासा.'
          )
      );
      setConfirmingApp(null);
      await fetchApps();
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmitOrPortalHandoff = async (app: ApplicationDraft) => {
    setSubmittingId(app.id);
    setActionError(null);
    try {
      const ver = app.confirmed_version ?? app.version ?? 1;
      const hashPrefix = (app.confirmed_hash ?? app.data_hash ?? 'draft').slice(0, 12);
      const idemKey = `ui:${app.user_id || 'citizen'}:${app.id}:v${ver}:${hashPrefix}`;
      const res = await applicationService.submitApplication(app.id, language, {
        idempotency_key: idemKey,
      });
      if (res.submitted && res.external_reference_id) {
        setSuccessInfo({
          id: app.id,
          mode: 'submitted',
          ref: res.external_reference_id,
          portalUrl: app.official_url || res.portal_url || 'https://india.gov.in',
          message: res.message,
        });
      } else {
        setSuccessInfo({
          id: app.id,
          mode: 'manual_portal_required',
          version: res.confirmed_version || ver,
          portalUrl: app.official_url || res.portal_url || 'https://india.gov.in',
          message: res.message,
        });
      }
      await fetchApps();
    } catch (err: any) {
      setActionError(
        err?.message ||
          pickText(
            'Submission blocked or failed safely. Please inspect readiness or reconcile previous attempt status.',
            'सबमिशन अवरुद्ध या विफल रहा। कृपया स्थिति की जांच करें।',
            'अर्ज सादरीकरण थांबवले किंवा अयशस्वी झाले. कृपया स्थिती तपासा.'
          )
      );
      await fetchApps();
    } finally {
      setSubmittingId(null);
    }
  };

  const handleReconcileSubmission = async (appId: string) => {
    setSubmittingId(appId);
    setActionError(null);
    try {
      const res = await applicationService.reconcileSubmission(appId, language);
      if (res.resolved) {
        setSuccessInfo({
          id: appId,
          mode: res.lifecycle_state === 'submitted' ? 'submitted' : 'confirmed',
          message: res.message,
        });
      } else {
        setActionError(res.message);
      }
      await fetchApps();
    } catch (err: any) {
      setActionError(err?.message || 'Reconciliation failed.');
    } finally {
      setSubmittingId(null);
    }
  };

  const handleOpenPortalRefModal = (app: ApplicationDraft) => {
    setPortalRefApp(app);
    setPortalRefNumber(app.official_reference_number || '');
    setPortalRefDate('');
    setPortalRefNotes('');
    setPortalRefError(null);
  };

  const handleSavePortalReference = async () => {
    if (!portalRefApp) return;
    const trimmed = portalRefNumber.trim();
    if (!trimmed) {
      setPortalRefError(
        pickText(
          'Enter the official portal application reference number returned after portal submission.',
          'आधिकारिक पोर्टल पर सबमिट करने के बाद प्राप्त आधिकारिक संदर्भ संख्या दर्ज करें।',
          'अधिकृत पोर्टलवर अर्ज सादर केल्यानंतर मिळालेला अधिकृत संदर्भ क्रमांक नोंदवा.'
        )
      );
      return;
    }
    const upper = trimmed.toUpperCase();
    if (
      upper.startsWith('SAATHI/') ||
      upper.startsWith('APP-') ||
      trimmed.toLowerCase() === portalRefApp.id.toLowerCase()
    ) {
      setPortalRefError(
        pickText(
          'Internal draft IDs (app-...) and synthetic SAATHI/... strings are rejected. Enter the official government portal reference number.',
          'आंतरिक ड्राफ्ट ID या सिंथेटिक संदर्भ मान्य नहीं हैं। कृपया सरकारी पोर्टल से प्राप्त वास्तविक संदर्भ संख्या दर्ज करें।',
          'अंतर्गत मसुदा आयडी किंवा कृत्रिम संदर्भ स्वीकारले जात नाहीत. कृपया शासकीय पोर्टलचा अधिकृत संदर्भ क्रमांक नोंदवा.'
        )
      );
      return;
    }

    setRecordingPortalRef(true);
    setPortalRefError(null);
    setActionError(null);
    try {
      const updated = await applicationService.recordPortalReference(
        portalRefApp.id,
        {
          official_reference_number: trimmed,
          submission_date: portalRefDate.trim() || undefined,
          portal_notes: portalRefNotes.trim() || undefined,
          confirmation_acknowledged: true,
        },
        language
      );
      setSuccessInfo({
        id: portalRefApp.id,
        mode: 'portal_submitted',
        ref: updated.official_reference_number || trimmed,
        portalUrl:
          updated.portal_url ||
          updated.official_url ||
          portalRefApp.portal_url ||
          portalRefApp.official_url ||
          'https://india.gov.in',
        trackingUrl:
          updated.tracking_url ||
          portalRefApp.tracking_url ||
          portalRefApp.portal_integration?.tracking_url,
        message: pickText(
          'Official portal reference number saved separately from your internal draft ID.',
          'आधिकारिक पोर्टल संदर्भ संख्या आपके आंतरिक ड्राफ्ट ID से अलग सफलतापूर्वक सहेजी गई।',
          'अधिकृत पोर्टल संदर्भ क्रमांक तुमच्या अंतर्गत मसुदा आयडीपासून स्वतंत्रपणे जतन केला गेला.'
        ),
      });
      setPortalRefApp(null);
      await fetchApps();
    } catch (err: any) {
      setPortalRefError(
        err?.message ||
          pickText(
            'Unable to save official portal reference. Ensure explicit confirmation was completed first.',
            'आधिकारिक पोर्टल संदर्भ सहेजा नहीं जा सका। कृपया सुनिश्चित करें कि स्पष्ट पुष्टि पहले पूरी हो चुकी है।',
            'अधिकृत पोर्टल संदर्भ जतन करता आला नाही. कृपया आधी स्पष्ट संमती पूर्ण झाल्याची खात्री करा.'
          )
      );
    } finally {
      setRecordingPortalRef(false);
    }
  };

  // Open Edit Modal for an application draft
  const handleOpenEdit = async (app: ApplicationDraft) => {
    setEditingApp(app);
    setSaveSuccessMsg(null);
    setFormErrors({});
    setResolvedModalConflicts({});
    setLoadingSchema(true);

    try {
      const schemeKey = app.scheme_code || app.scheme_id;
      const schema = await applicationService.getFormSchema(schemeKey, language);
      setEditingSchema(schema);

      const initialValues: Record<string, any> = {};
      const rawForm = app.form_data || {};
      const prefillMap: Record<string, any> = {};
      (app.prefill_summary?.sections || []).forEach((ps: any) => {
        (ps.fields || []).forEach((pf: any) => {
          prefillMap[pf.name] = pf;
        });
      });

      const normalizeOptionMatch = (raw: any, options?: string[]): string => {
        const s = String(raw ?? '').trim();
        if (!options || options.length === 0 || !s) return s;
        const matched = options.find((o) => o.toLowerCase() === s.toLowerCase());
        return matched || s;
      };

      if (schema && schema.sections) {
        schema.sections.forEach((sec) => {
          sec.fields.forEach((field) => {
            const rawVal = rawForm[field.name];
            const prefillMeta = prefillMap[field.name];
            const prefillVal = prefillMeta?.value;

            if (
              rawVal !== undefined &&
              rawVal !== null &&
              String(rawVal).toLowerCase() !== 'null' &&
              String(rawVal).toLowerCase() !== 'undefined' &&
              String(rawVal).trim() !== ''
            ) {
              initialValues[field.name] =
                field.type === 'select' ? normalizeOptionMatch(rawVal, field.options) : rawVal;
            } else if (
              prefillVal !== undefined &&
              prefillVal !== null &&
              String(prefillVal).trim() !== '' &&
              !prefillMeta?.conflict
            ) {
              initialValues[field.name] =
                field.type === 'select' ? normalizeOptionMatch(prefillVal, field.options) : prefillVal;
            } else if (field.profile_field && profile) {
              const pVal =
                (profile as any)[field.profile_field] ??
                (profile.profile_data as any)?.[field.profile_field];
              const isPlaceholderName =
                field.profile_field === 'full_name' &&
                typeof pVal === 'string' &&
                pVal.trim().toLowerCase() === 'citizen';
              if (
                !isPlaceholderName &&
                pVal !== undefined &&
                pVal !== null &&
                String(pVal).toLowerCase() !== 'null'
              ) {
                initialValues[field.name] =
                  field.type === 'select' ? normalizeOptionMatch(pVal, field.options) : pVal;
              } else {
                initialValues[field.name] = field.default !== undefined && !field.profile_field ? field.default : '';
              }
            } else {
              initialValues[field.name] =
                field.default !== undefined && !field.profile_field ? field.default : '';
            }
          });
        });
      }

      Object.entries(rawForm).forEach(([k, v]) => {
        if (
          initialValues[k] === undefined &&
          v !== null &&
          String(v).toLowerCase() !== 'null' &&
          String(v).toLowerCase() !== 'undefined'
        ) {
          initialValues[k] = v;
        }
      });

      setFormValues(initialValues);
    } catch (err) {
      console.error('Failed to load schema:', err);
      const cleanData: Record<string, any> = {};
      Object.entries(app.form_data || {}).forEach(([k, v]) => {
        cleanData[k] = v === null || String(v).toLowerCase() === 'null' ? '' : v;
      });
      setFormValues(cleanData);
    } finally {
      setLoadingSchema(false);
    }
  };

  const getFieldFormatErrorMessage = (name: string): string => {
    if (name.includes('mobile') || name.includes('phone')) {
      return pickText(
        'Enter valid 10-digit mobile number starting with 6-9',
        '6-9 से शुरू होने वाला मान्य 10-अंकीय मोबाइल नंबर दर्ज करें',
        '६-९ ने सुरू होणारा वैध १०-अंकी मोबाईल नंबर टाका'
      );
    }
    if (name.includes('aadhaar')) {
      return pickText(
        'Enter valid 12-digit Aadhaar number',
        'मान्य 12-अंकीय आधार संख्या दर्ज करें',
        'वैध १२-अंकी आधार क्रमांक टाका'
      );
    }
    if (name.includes('ifsc')) {
      return pickText(
        'Enter valid 11-character IFSC code (e.g. SBIN0001234)',
        'मान्य 11-अक्षरीय IFSC कोड दर्ज करें (उदा. SBIN0001234)',
        'वैध ११-अक्षरी IFSC कोड टाका (उदा. SBIN0001234)'
      );
    }
    if (name.includes('account')) {
      return pickText(
        'Enter valid 9 to 18-digit bank account number',
        'मान्य 9 से 18 अंकीय बैंक खाता संख्या दर्ज करें',
        'वैध ९ ते १८ अंकी बँक खाते क्रमांक टाका'
      );
    }
    return pickText('Invalid format', 'अमान्य प्रारूप', 'अवैध नमुना');
  };

  const handleFieldChange = (name: string, value: any, pattern?: string) => {
    setResolvedModalConflicts((prev) => ({ ...prev, [name]: true }));
    setFormValues((prev) => ({
      ...prev,
      [name]: value,
    }));

    if (pattern && value && String(value).trim() !== '') {
      try {
        const regex = new RegExp(pattern);
        if (!regex.test(String(value).trim())) {
          setFormErrors((prev) => ({
            ...prev,
            [name]: getFieldFormatErrorMessage(name),
          }));
          return;
        }
      } catch {}
    }

    setFormErrors((prev) => {
      const next = { ...prev };
      delete next[name];
      return next;
    });
  };

  const handleSaveDraft = async (assessAfterSave: boolean = false) => {
    if (!editingApp) return;
    setSavingDraft(true);
    setSaveSuccessMsg(null);
    setActionError(null);

    try {
      const cleanPayload: Record<string, any> = {};
      Object.entries(formValues).forEach(([k, v]) => {
        if (
          v === null ||
          v === undefined ||
          String(v).trim().toLowerCase() === 'null' ||
          String(v).trim().toLowerCase() === 'undefined'
        ) {
          cleanPayload[k] = '';
        } else {
          cleanPayload[k] = typeof v === 'string' ? v.trim() : v;
        }
      });

      await applicationService.updateDraft(editingApp.id, cleanPayload, language);
      if (assessAfterSave) {
        await applicationService.validateDraft(editingApp.id, language);
      }

      await fetchApps();
      setSaveSuccessMsg(
        pickText(
          'Application draft changes saved successfully.',
          'आवेदन मसौदा सफलतापूर्वक सहेजा गया।',
          'अर्जाचा मसुदा यशस्वीरित्या जतन केला गेला.'
        )
      );

      setTimeout(
        () => {
          setEditingApp(null);
          setSaveSuccessMsg(null);
        },
        assessAfterSave ? 1000 : 600
      );
    } catch (err: any) {
      setActionError(err?.message || 'Failed to persist application changes.');
    } finally {
      setSavingDraft(false);
    }
  };

  const getLifecycleBadgeLabel = (state: string): string => {
    const map: Record<string, { en: string; hi: string; mr: string }> = {
      draft: { en: 'DRAFT', hi: 'मसौदा', mr: 'मसुदा' },
      validated: { en: 'VALIDATED', hi: 'सत्यापित', mr: 'तपासलेला' },
      validation_failed: { en: 'ACTION REQUIRED', hi: 'कार्रवाई आवश्यक', mr: 'दुरुस्ती आवश्यक' },
      awaiting_confirmation: { en: 'AWAITING CONFIRMATION', hi: 'पुष्टि प्रतीक्षित', mr: 'संमती प्रलंबित' },
      confirmed: { en: 'CONFIRMED', hi: 'पुष्ट', mr: 'नक्की झालेला' },
      submitting: { en: 'SUBMITTING', hi: 'प्रस्तुत हो रहा', mr: 'सादर होत आहे' },
      submitted: { en: 'SUBMITTED', hi: 'सबमिट किया गया', mr: 'सादर केले' },
      portal_submitted: { en: 'PORTAL SUBMITTED', hi: 'पोर्टल पर जमा', mr: 'पोर्टलवर सादर' },
      submission_failed: { en: 'SUBMISSION FAILED', hi: 'प्रस्तुति विफल', mr: 'सादरीकरण अयशस्वी' },
      submission_unknown: { en: 'SUBMISSION UNKNOWN', hi: 'स्थिति अनिश्चित', mr: 'स्थिती अनिश्चित' },
    };
    const item = map[state];
    return item ? pickText(item.en, item.hi, item.mr) : state.toUpperCase();
  };

  return (
    <div className="space-y-7 max-w-4xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div className="space-y-1">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-saffron-light text-saffron-dark text-xs font-semibold border border-saffron/30">
            <FolderKanban className="w-3.5 h-3.5 text-saffron-vibrant" />
            <span>
              {pickText('Application Preparation & Tracking', 'आवेदन तैयारी व ट्रैकिंग', 'अर्ज तयारी व मागोवा')}
            </span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold font-editorial text-navy tracking-tight">
            {pickText('Applications & Readiness', 'आवेदन एवं तत्परता', 'अर्ज आणि सज्जता')}
          </h1>
          <p className="text-xs sm:text-sm text-navy/60 max-w-xl leading-relaxed">
            {pickText(
              'Complete scheme-specific application forms, verify required documents in your Vault, and assess readiness for official government portal handoff.',
              'योजना-विशिष्ट आवेदन पत्र पूर्ण करें, अपने वॉल्ट में आवश्यक दस्तावेज़ सत्यापित करें और आधिकारिक पोर्टल के लिए तत्परता जांचें।',
              'योजनेनुसार अर्ज भरा, दस्तऐवज व्हॉल्टमध्ये कागदपत्रे पडताळून घ्या आणि अधिकृत पोर्टलसाठी सज्जता तपासा.'
            )}
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Link to="/documents">
            <Button variant="outline" size="md">
              {pickText('Document Vault', 'दस्तावेज़ वॉल्ट', 'दस्तऐवज व्हॉल्ट')}
            </Button>
          </Link>
          <Link to="/schemes">
            <Button variant="saffron" size="md">
              {pickText('+ Start New Application', '+ नया आवेदन शुरू करें', '+ नवीन अर्ज सुरू करा')}
            </Button>
          </Link>
        </div>
      </div>

      {/* Workflow Stepper Bar */}
      <div className="p-4 rounded-2xl bg-white border border-navy/8 shadow-subtle">
        <div className="flex items-center justify-between gap-2 overflow-x-auto pb-1">
          {[
            { step: '1', en: 'Draft Created', hi: 'ड्राफ्ट निर्मित', mr: 'मसुदा तयार' },
            { step: '2', en: 'Edit Details', hi: 'विवरण संपादन', mr: 'माहिती संपादन' },
            { step: '3', en: 'Verify Docs', hi: 'दस्तावेज़ सत्यापन', mr: 'कागदपत्र पडताळणी' },
            { step: '4', en: 'Citizen Confirm', hi: 'नागरिक पुष्टि', mr: 'नागरिक संमती' },
            { step: '5', en: 'Portal Handoff', hi: 'पोर्टल प्रस्तुतीकरण', mr: 'अधिकृत पोर्टल' },
          ].map((item, idx) => (
            <div key={idx} className="flex items-center gap-2 shrink-0">
              <span className="w-6 h-6 rounded-full bg-ivory-200 text-navy font-bold text-xs flex items-center justify-center font-mono border border-navy/10">
                {item.step}
              </span>
              <span className="text-xs font-semibold text-navy/80 whitespace-nowrap">
                {pickText(item.en, item.hi, item.mr)}
              </span>
              {idx < 4 && <span className="text-navy/20 font-bold ml-1">&rarr;</span>}
            </div>
          ))}
        </div>
      </div>

      {/* Explicit Consent & Independence Banner */}
      <StatusBanner
        type="demo"
        title={pickText(
          'Explicit Consent & Official Portal Guidance Policy',
          'नागरिक स्पष्ट सहमति एवं आधिकारिक पोर्टल नीति',
          'नागरिक स्पष्ट संमती व अधिकृत पोर्टल धोरण'
        )}
        message={pickText(
          'Scheme Saathi prepares your verified application readiness packet and never submits applications without your explicit confirmation. Final submission takes place on the authoritative government portal.',
          'योजना साथी आपका सत्यापित आवेदन पैकेट तैयार करता है और आपकी स्पष्ट पुष्टि के बिना कभी आवेदन जमा नहीं करता। अंतिम प्रस्तुतीकरण आधिकारिक सरकारी पोर्टल पर होता है।',
          'योजना साथी तुमचा पडताळलेला अर्ज संच तयार करते आणि तुमच्या स्पष्ट संमतीशिवाय कधीही अर्ज सादर करत नाही. अंतिम सादरीकरण अधिकृत शासकीय पोर्टलवरच केले जाते.'
        )}
      />

      {actionError && (
        <StatusBanner
          type="danger"
          title={pickText('Readiness Validation Blocked Action', 'कार्रवाई रोकी गई', 'कारवाई थांबवली')}
          message={actionError}
        />
      )}

      {successInfo && (
        <StatusBanner
          type={successInfo.mode === 'submitted' || successInfo.mode === 'portal_submitted' ? 'success' : 'info'}
          title={
            successInfo.mode === 'portal_submitted'
              ? pickText(
                  'Official Portal Reference Recorded (Citizen Reported)',
                  'आधिकारिक पोर्टल संदर्भ संख्या दर्ज (नागरिक द्वारा रिपोर्ट)',
                  'अधिकृत पोर्टल संदर्भ क्रमांक नोंदवला (नागरिकाने नोंदवलेला)'
                )
              : successInfo.mode === 'submitted'
              ? pickText(
                  'Submitted via Official Portal Integration',
                  'आधिकारिक पोर्टल पर सबमिट किया गया',
                  'अधिकृत पोर्टलवर सादर केले'
                )
              : successInfo.mode === 'manual_portal_required'
              ? pickText(
                  `Confirmed (v${successInfo.version || 1}) — Manual Portal Submission Required`,
                  `पुष्टि दर्ज (v${successInfo.version || 1}) — आधिकारिक पोर्टल पर स्वयं सबमिट करें`,
                  `संमती नोंदवली (v${successInfo.version || 1}) — अधिकृत पोर्टलवर स्वतः सादर करा`
                )
              : pickText(
                  `Explicit Confirmation Recorded (v${successInfo.version || 1})`,
                  `स्पष्ट नागरिक पुष्टि दर्ज (v${successInfo.version || 1})`,
                  `नागरिकाची स्पष्ट संमती नोंदवली (v${successInfo.version || 1})`
                )
          }
          message={
            successInfo.ref
              ? pickText(
                  `Official External Portal Reference: ${successInfo.ref}.`,
                  `आधिकारिक बाह्य पोर्टल संदर्भ संख्या: ${successInfo.ref}।`,
                  `अधिकृत बाह्य पोर्टल संदर्भ क्रमांक: ${successInfo.ref}.`
                )
              : successInfo.message ||
                pickText(
                  'Complete final filing directly on the official government portal below.',
                  'कृपया नीचे दिए आधिकारिक सरकारी पोर्टल पर अंतिम आवेदन स्वयं पूरा करें।',
                  'कृपया खालील अधिकृत शासकीय पोर्टलवर अंतिम अर्ज स्वतः सादर करा.'
                )
          }
          action={
            <div className="flex items-center gap-2 flex-wrap">
              {successInfo.trackingUrl && (
                <a href={successInfo.trackingUrl} target="_blank" rel="noopener noreferrer">
                  <Button size="sm" variant="outline" rightIcon={<ExternalLink className="w-3.5 h-3.5" />}>
                    {pickText('Track Status', 'स्थिति ट्रैक करें', 'स्थिती पहा')}
                  </Button>
                </a>
              )}
              {successInfo.portalUrl && (
                <a href={successInfo.portalUrl} target="_blank" rel="noopener noreferrer">
                  <Button size="sm" variant="saffron" rightIcon={<ExternalLink className="w-3.5 h-3.5" />}>
                    {pickText('Open Official Portal', 'आधिकारिक पोर्टल खोलें', 'अधिकृत पोर्टल उघडा')}
                  </Button>
                </a>
              )}
              <Button size="sm" variant="outline" onClick={() => setSuccessInfo(null)}>
                {pickText('Dismiss', 'बंद करें', 'बंद करा')}
              </Button>
            </div>
          }
        />
      )}

      {/* Applications List */}
      {loading ? (
        <Spinner
          size="lg"
          label={pickText('Loading application drafts...', 'आवेदन लोड हो रहे हैं...', 'अर्ज लोड होत आहेत...')}
        />
      ) : applications.length === 0 ? (
        <EmptyState
          title={pickText('No Active Applications', 'कोई सक्रिय आवेदन नहीं है', 'कोणतेही सक्रिय अर्ज नाहीत')}
          description={pickText(
            'You have not drafted any scheme applications yet. Browse schemes to get started.',
            'आपने अभी तक कोई आवेदन तैयार नहीं किया है। शुरू करने के लिए योजनाएं देखें।',
            'तुम्ही अद्याप कोणत्याही योजनेचा अर्ज तयार केलेला नाही. सुरुवात करण्यासाठी योजना पहा.'
          )}
          actionLabel={pickText('Browse Schemes', 'योजनाएं देखें', 'योजना पहा')}
          onAction={() => (window.location.href = '/schemes')}
        />
      ) : (
        <div className="space-y-5">
          {applications.map((app) => {
            const breakdown = app.validation_result?.breakdown;
            const overallPct = app.validation_result?.overall_percentage;
            const isLegacySynthetic = Boolean(app.legacy_synthetic_submission);
            const portalRefNum =
              app.official_reference_number ||
              app.application_record?.official_reference_number ||
              null;
            const isPortalSubmitted =
              !isLegacySynthetic &&
              (app.lifecycle_state === 'portal_submitted' ||
                (Boolean(portalRefNum) &&
                  app.submission_source === 'portal_assisted' &&
                  !app.external_reference_id));
            const isOfficialSubmitted =
              !isLegacySynthetic &&
              !isPortalSubmitted &&
              app.lifecycle_state === 'submitted' &&
              Boolean(app.external_reference_id) &&
              !String(app.external_reference_id).toUpperCase().startsWith('SAATHI/') &&
              app.submission_source === 'official_integration';
            const isSubmissionUnknown =
              app.lifecycle_state === 'submission_unknown' ||
              (app.lifecycle_state === 'submission_failed' &&
                Boolean(app.blind_retry_blocked) &&
                (app.submission_outcome === 'uncertain' || app.submission_outcome === 'submission_unknown'));
            const displayState: string = isLegacySynthetic
              ? app.validation_result?.passed
                ? 'validated'
                : 'draft'
              : isSubmissionUnknown
              ? 'submission_unknown'
              : isPortalSubmitted
              ? 'portal_submitted'
              : app.lifecycle_state === 'submitted' && !isOfficialSubmitted
              ? 'draft'
              : app.lifecycle_state;
            const resolvedPortalUrl =
              app.portal_url ||
              app.application_record?.portal_url ||
              app.portal_integration?.official_application_url ||
              app.official_url ||
              app.portal_integration?.official_url ||
              '';
            const resolvedTrackingUrl =
              app.tracking_url ||
              app.application_record?.tracking_url ||
              app.portal_integration?.tracking_url ||
              '';
            const resolvedSubmissionMethod =
              app.portal_integration?.submission_method_label ||
              app.submission_method ||
              app.application_record?.submission_method ||
              (app.integration_supported
                ? pickText('Mode A: Direct Authorized API', 'मोड A: प्रत्यक्ष अधिकृत API', 'पद्धत A: थेट अधिकृत API')
                : pickText('Mode B: Portal-Assisted', 'मोड B: पोर्टल-सहाय्यित', 'पद्धत B: पोर्टल-सहाय्यित'));
            const resolvedSubmissionDate =
              app.submission_date ||
              app.application_record?.submission_date ||
              app.submitted_at ||
              null;

            return (
              <Card key={app.id} hoverable className="overflow-hidden border-navy/10 shadow-subtle">
                <CardContent className="p-6 space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-navy/6">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-2xl bg-ivory-100 flex items-center justify-center text-navy shrink-0 border border-navy/8">
                        <FileText className="w-5 h-5 text-saffron-dark" />
                      </div>
                      <div>
                        <h3 className="font-bold font-editorial text-navy text-lg">
                          {app.scheme_name || app.scheme_code || app.scheme_id}
                        </h3>
                        <p className="text-xs text-navy/50 font-mono">
                          {app.scheme_code ? `${app.scheme_code} • ` : ''}Draft ID: {app.id} • v{app.version || 1} •{' '}
                          {new Date(app.created_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 flex-wrap">
                      {typeof overallPct === 'number' && !isOfficialSubmitted && !isPortalSubmitted && (
                        <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-ivory-100 text-navy border border-navy/12">
                          {Math.round(overallPct)}% {pickText('Ready', 'तैयार', 'सज्ज')}
                        </span>
                      )}
                      <Badge variant={displayState as any}>
                        {isLegacySynthetic
                          ? pickText('UNVERIFIED LEGACY PACKET', 'असत्यापित पूर्व पैकेट', 'असत्यापित जुने पॅकेट')
                          : getLifecycleBadgeLabel(displayState)}
                      </Badge>
                    </div>
                  </div>

                  {/* Historical / Legacy Synthetic Submission Quarantine Notice */}
                  {isLegacySynthetic && (
                    <div className="p-3 rounded-xl bg-amber-50/90 border border-amber-200 text-xs text-amber-950 flex items-start gap-2">
                      <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
                      <span>
                        {pickText(
                          'Historical readiness packet preserved for audit records. It is not a verified official government portal submission; start or use an active application draft for verified Phase 7 filing.',
                          'यह ऐतिहासिक तत्परता पैकेट ऑडिट रिकॉर्ड के लिए सुरक्षित है। यह कोई सत्यापित सरकारी पोर्टल सबमिशन नहीं है; कृपया सक्रिय आवेदन ड्राफ्ट का उपयोग करें।',
                          'हे ऐतिहासिक सज्जता पॅकेट ऑडिट नोंदीसाठी जतन केले आहे. हा अधिकृत सरकारी पोर्टलवर सादर केलेला अर्ज नाही; कृपया सक्रिय अर्जाचा वापर करा.'
                        )}
                      </span>
                    </div>
                  )}

                  {/* Submission Unknown Reconciliation Notice */}
                  {isSubmissionUnknown && (
                    <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-300 text-xs text-amber-950 space-y-1">
                      <div className="font-bold flex items-center gap-1.5">
                        <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0" />
                        <span>
                          {pickText(
                            'Submission Outcome Unknown — Reconciliation Required',
                            'सबमिशन परिणाम अनिश्चित — स्थिति की पुष्टि आवश्यक',
                            'सादरीकरण स्थिती अनिश्चित — पोर्टल तपासणी आवश्यक'
                          )}
                        </span>
                      </div>
                      <p className="text-amber-900">
                        {pickText(
                          'The official portal request timed out or returned an ambiguous response after dispatch. Blind retries are disabled to prevent duplicate filing; click Reconcile Submission Status below.',
                          'आधिकारिक पोर्टल अनुरोध समय समाप्त या अस्पष्ट रहा। दोहरा आवेदन रोकने के लिए पुनः प्रयास बंद है; नीचे सबमिशन स्थिति जांचें।',
                          'अधिकृत पोर्टल विनंतीची वेळ संपली किंवा प्रतिसाद अस्पष्ट राहिला. दुहेरी अर्ज टाळण्यासाठी थेट पुन्हा प्रयत्न बंद केला आहे; खालील स्थिती तपासा बटणावर क्लिक करा.'
                        )}
                      </p>
                    </div>
                  )}

                  {/* Confirmation Invalidated Notice when edits occurred after confirmation */}
                  {app.confirmation_invalidated_at && !app.confirmed_at && !isOfficialSubmitted && !isLegacySynthetic && (
                    <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-950 flex items-start gap-2">
                      <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                      <span>
                        {pickText(
                          'Application details, profile data, or Vault documents changed after your previous confirmation. Please review and re-confirm the updated version.',
                          'पिछली पुष्टि के बाद आवेदन विवरण, प्रोफ़ाइल या दस्तावेज़ बदल गए हैं। कृपया अद्यतन संस्करण की समीक्षा कर पुनः पुष्टि करें।',
                          'मागील संमतीनंतर अर्जाची माहिती, प्रोफाईल किंवा दस्तऐवज बदलले आहेत. कृपया अद्ययावत आवृत्ती तपासून पुन्हा संमती द्या.'
                        )}
                      </span>
                    </div>
                  )}

                  {/* Confirmed — Manual Official Portal Required Banner */}
                  {app.lifecycle_state === 'confirmed' && (
                    <div className="p-3.5 rounded-xl bg-emerald-50/70 border border-emerald-200 text-xs text-navy space-y-1">
                      <div className="font-bold text-emerald-900 flex items-center gap-1.5">
                        <CheckCircle2 className="w-4 h-4 text-emerald-700 shrink-0" />
                        <span>
                          {pickText(
                            `Explicit Confirmation Active for Version v${app.confirmed_version || app.version || 1}`,
                            `संस्करण v${app.confirmed_version || app.version || 1} के लिए नागरिक पुष्टि सक्रिय है`,
                            `आवृत्ती v${app.confirmed_version || app.version || 1} साठी नागरिकाची संमती नोंदवली आहे`
                          )}
                        </span>
                      </div>
                      <p className="text-navy/80">
                        {app.integration_supported
                          ? pickText(
                              'Ready to submit via authorized official portal integration.',
                              'सत्यापित आधिकारिक पोर्टल एकीकरण के माध्यम से सबमिट करने के लिए तैयार।',
                              'अधिकृत पोर्टल जोडणीद्वारे अर्ज सादर करण्यासाठी सज्ज.'
                            )
                          : pickText(
                              'No automated government portal integration is active for this scheme. Click Portal Submission Guidance or open the official government portal to submit manually.',
                              'इस योजना के लिए स्वचालित सरकारी पोर्टल एकीकरण सक्रिय नहीं है। आधिकारिक पोर्टल पर मैन्युअल रूप से आवेदन जमा करने के लिए नीचे क्लिक करें।',
                              'या योजनेसाठी स्वयंचलित शासकीय पोर्टल जोडणी उपलब्ध नाही. अधिकृत पोर्टलवर स्वतः अर्ज सादर करण्यासाठी खाली क्लिक करा.'
                            )}
                      </p>
                    </div>
                  )}

                  {/* Multi-Pillar Readiness Breakdown */}
                  {breakdown && !isOfficialSubmitted && !isSubmissionUnknown && (
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                      {/* Pillar 1: Profile */}
                      <div className="p-3 rounded-xl border border-navy/8 bg-ivory-50/70 space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-navy flex items-center gap-1.5">
                            <UserCheck className="w-3.5 h-3.5 text-saffron" />
                            {pickText('Profile', 'प्रोफ़ाइल', 'प्रोफाईल')}
                          </span>
                          <span className={breakdown.profile.complete ? 'text-emerald-700 font-bold' : 'text-amber-700 font-bold'}>
                            {breakdown.profile.filled_count}/{breakdown.profile.total_count}
                          </span>
                        </div>
                        {!breakdown.profile.complete && (
                          <Link to="/onboarding" className="text-[11px] text-saffron-dark font-semibold hover:underline inline-flex items-center gap-1">
                            <span>{pickText('Complete Profile', 'प्रोफ़ाइल पूर्ण करें', 'प्रोफाईल पूर्ण करा')}</span>
                            <ArrowRight className="w-3 h-3" />
                          </Link>
                        )}
                      </div>

                      {/* Pillar 2: Form Fields */}
                      <div className="p-3 rounded-xl border border-navy/8 bg-ivory-50/70 space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-navy flex items-center gap-1.5">
                            <Pencil className="w-3.5 h-3.5 text-saffron" />
                            {pickText('Application Fields', 'आवेदन विवरण', 'अर्ज माहिती')}
                          </span>
                          {(breakdown.form as any).schema_available === false ? (
                            <span className="text-amber-700 font-bold text-[11px]">
                              {pickText('Schema Unavailable', 'स्कीमा अनुपलब्ध', 'नमुना उपलब्ध नाही')}
                            </span>
                          ) : (
                            <span className={breakdown.form.complete ? 'text-emerald-700 font-bold' : 'text-amber-700 font-bold'}>
                              {breakdown.form.filled_mandatory}/{breakdown.form.total_mandatory}
                            </span>
                          )}
                        </div>
                        {(breakdown.form as any).schema_available !== false && !breakdown.form.complete && (
                          <button
                            type="button"
                            onClick={() => handleOpenEdit(app)}
                            className="text-[11px] text-saffron-dark font-semibold hover:underline inline-flex items-center gap-1"
                          >
                            <span>{pickText('Fill Missing Fields', 'शेष विवरण भरें', 'माहिती भरा')}</span>
                            <ArrowRight className="w-3 h-3" />
                          </button>
                        )}
                      </div>

                      {/* Pillar 3: Documents */}
                      <div className="p-3 rounded-xl border border-navy/8 bg-ivory-50/70 space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-navy flex items-center gap-1.5">
                            <FileCheck2 className="w-3.5 h-3.5 text-saffron" />
                            {pickText('Verified Docs', 'सत्यापित दस्तावेज़', 'पडताळलेली कागदपत्रे')}
                          </span>
                          <span className={breakdown.documents.complete ? 'text-emerald-700 font-bold' : 'text-amber-700 font-bold'}>
                            {breakdown.documents.verified}/{breakdown.documents.applicable_mandatory}
                          </span>
                        </div>
                        {!breakdown.documents.complete && (
                          <Link to="/documents" className="text-[11px] text-saffron-dark font-semibold hover:underline inline-flex items-center gap-1">
                            <span>{pickText('Open Document Vault', 'दस्तावेज़ वॉल्ट खोलें', 'व्हॉल्ट उघडा')}</span>
                            <ArrowRight className="w-3 h-3" />
                          </Link>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Per-Document Applicability Status Chips */}
                  {breakdown?.documents?.items && breakdown.documents.items.length > 0 && app.lifecycle_state !== 'submitted' && (
                    <div className="flex flex-wrap gap-2">
                      {breakdown.documents.items.map((item) => {
                        const chipClass =
                          item.status === 'verified'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : item.status === 'waived'
                            ? 'bg-slate-50 text-slate-600 border-slate-200'
                            : item.status === 'rejected'
                            ? 'bg-rose-50 text-rose-700 border-rose-200'
                            : item.status === 'reviewed'
                            ? 'bg-blue-50 text-blue-700 border-blue-200'
                            : 'bg-amber-50 text-amber-800 border-amber-200';
                        return (
                          <span
                            key={item.document_type}
                            className={`text-[11px] px-2.5 py-1 rounded-lg border font-medium ${chipClass}`}
                            title={item.reason || ''}
                          >
                            {item.title}: <strong>{item.status_label}</strong>
                          </span>
                        );
                      })}
                    </div>
                  )}

                  {/* Validation & Readiness Status Alert */}
                  {app.validation_result && (
                    <div
                      className={`p-4 rounded-2xl border text-xs space-y-1.5 ${
                        app.validation_result.passed
                          ? 'bg-sage-light/70 border-sage/35 text-navy'
                          : 'bg-amber-50 border-amber-200 text-amber-950'
                      }`}
                    >
                      <div className="flex items-center gap-2 font-bold">
                        {app.validation_result.passed ? (
                          <>
                            <CheckCircle2 className="w-4 h-4 text-sage-green shrink-0" />
                            <span className="text-sage-dark font-bold">
                              {pickText(
                                'Application Readiness Verified (100% Ready)',
                                'आवेदन तत्परता सत्यापित (100% तैयार)',
                                'अर्ज सज्जता पडताळली (१००% सज्ज)'
                              )}
                            </span>
                          </>
                        ) : (
                          <>
                            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                            <span className="text-amber-900 font-bold">
                              {pickText(
                                'Action Required for Application Readiness',
                                'आवेदन पूर्ण करने हेतु आवश्यक कदम',
                                'अर्ज पूर्ण करण्यासाठी आवश्यक बाबी'
                              )}
                            </span>
                          </>
                        )}
                      </div>
                      {app.validation_result.errors?.map((err, idx) => (
                        <p key={idx} className="opacity-90 leading-relaxed">
                          • {err.message}
                        </p>
                      ))}
                      {app.validation_result.warnings?.map((warn, idx) => (
                        <p key={idx} className="opacity-80 leading-relaxed italic">
                          • {warn.message}
                        </p>
                      ))}
                    </div>
                  )}

                  {/* Form Data & Provenance Snapshot */}
                  <div className="p-4.5 rounded-2xl bg-ivory-50/80 border border-navy/8 text-xs space-y-2.5">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-navy/60 uppercase tracking-wider text-[10px] block">
                        {pickText(
                          'Applicant Form Attributes Snapshot',
                          'आवेदक विवरण सारांश',
                          'अर्जदाराची माहिती'
                        )}
                      </span>
                      <span className="text-[10px] text-navy/50">
                        {app.review_summary?.sections
                          ? app.review_summary.sections.reduce((acc, s) => acc + s.fields.length, 0)
                          : Object.keys(app.form_data || {}).length}{' '}
                        {pickText('fields', 'फ़ील्ड', 'रकाने')}
                      </span>
                    </div>

                    {app.review_summary?.sections && app.review_summary.sections.length > 0 ? (
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                        {app.review_summary.sections
                          .flatMap((s) => s.fields)
                          .map((field) => (
                            <div key={field.name} className="space-y-0.5">
                              <div className="flex items-center justify-between gap-1">
                                <span className="text-navy/60 text-[11px] truncate" title={field.label}>
                                  {field.label}:
                                </span>
                                {field.conflict ? (
                                  <span className="text-[9px] text-rose-700 bg-rose-50 px-1 rounded border border-rose-200 shrink-0 font-semibold">
                                    {pickText('Conflict', 'विरोधाभास', 'तफावत')}
                                  </span>
                                ) : field.source_badge && !field.is_missing && field.value !== '' ? (
                                  <span className="text-[9px] text-navy/65 bg-white px-1 rounded border border-navy/10 shrink-0">
                                    {field.source_badge}
                                  </span>
                                ) : null}
                              </div>
                              {renderCleanValue(field.value)}
                            </div>
                          ))}
                      </div>
                    ) : (
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                        {Object.entries(app.form_data || {}).map(([key, val]) => (
                          <div key={key} className="space-y-0.5">
                            <span className="text-navy/50 capitalize text-[11px] block">
                              {key.replace(/_/g, ' ')}:
                            </span>
                            {renderCleanValue(val)}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Normalized Step 5 Application Record & Official Portal Details */}
                  {!isLegacySynthetic && (
                    <div className="p-3.5 rounded-xl bg-ivory-50/70 border border-navy/8 text-xs space-y-2">
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <span className="font-bold text-navy/70 uppercase tracking-wider text-[10px]">
                          {pickText(
                            'Application Record & Official Portal Integration',
                            'आवेदन रिकॉर्ड एवं आधिकारिक पोर्टल विवरण',
                            'अर्ज नोंद व अधिकृत पोर्टल तपशील'
                          )}
                        </span>
                        <span className="text-[10.5px] font-semibold px-2 py-0.5 rounded-full bg-white text-navy/80 border border-navy/10">
                          {resolvedSubmissionMethod}
                        </span>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5 text-[11px]">
                        <div>
                          <span className="text-navy/55 block text-[10px]">
                            {pickText('Internal Application ID', 'आंतरिक आवेदन ID', 'अंतर्गत अर्ज आयडी')}
                          </span>
                          <span className="font-mono font-semibold text-navy break-all">{app.id}</span>
                        </div>
                        <div>
                          <span className="text-navy/55 block text-[10px]">
                            {pickText('Official Reference Number', 'आधिकारिक संदर्भ संख्या', 'अधिकृत संदर्भ क्रमांक')}
                          </span>
                          <span className="font-mono font-semibold text-navy break-all">
                            {portalRefNum ||
                              (isOfficialSubmitted ? app.external_reference_id : null) ||
                              pickText('Not yet recorded', 'अभी दर्ज नहीं', 'अद्याप नोंदवलेला नाही')}
                          </span>
                        </div>
                        <div>
                          <span className="text-navy/55 block text-[10px]">
                            {pickText('Submission Date', 'सबमिशन तिथि', 'सादर केल्याची तारीख')}
                          </span>
                          <span className="font-medium text-navy">
                            {resolvedSubmissionDate
                              ? new Date(resolvedSubmissionDate).toLocaleString()
                              : pickText('Pending citizen submission', 'नागरिक सबमिशन लंबित', 'अर्ज सादरीकरण प्रलंबित')}
                          </span>
                        </div>
                      </div>

                      {(resolvedPortalUrl || resolvedTrackingUrl) && (
                        <div className="flex items-center gap-3 flex-wrap pt-1 border-t border-navy/6 text-[11px]">
                          {resolvedPortalUrl && (
                            <a
                              href={resolvedPortalUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 font-semibold text-saffron-dark hover:underline break-all"
                            >
                              <span>{pickText('Official Portal URL', 'आधिकारिक पोर्टल लिंक', 'अधिकृत पोर्टल लिंक')}</span>
                              <ExternalLink className="w-3 h-3 shrink-0" />
                            </a>
                          )}
                          {resolvedTrackingUrl && (
                            <a
                              href={resolvedTrackingUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 font-semibold text-navy/80 hover:text-navy hover:underline break-all"
                            >
                              <span>{pickText('Status Tracking URL', 'स्थिति ट्रैकिंग लिंक', 'स्थिती तपासणी लिंक')}</span>
                              <ExternalLink className="w-3 h-3 shrink-0 text-saffron" />
                            </a>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Application Actions */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2">
                    <div className="flex items-center gap-2 text-xs text-navy/60">
                      <Clock className="w-4 h-4 text-navy/40" />
                      <span>
                        {pickText('Last modified:', 'अंतिम संशोधन:', 'शेवटचा बदल:')}{' '}
                        {new Date(app.updated_at).toLocaleDateString()}
                      </span>
                    </div>

                    <div className="flex items-center gap-2.5 flex-wrap">
                      {!isOfficialSubmitted &&
                        !isPortalSubmitted &&
                        app.lifecycle_state !== 'submitting' &&
                        !isSubmissionUnknown &&
                        !isLegacySynthetic && (
                        <>
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={() => handleOpenEdit(app)}
                            leftIcon={<Pencil className="w-3.5 h-3.5 text-saffron" />}
                          >
                            {pickText('Edit Application', 'आवेदन संपादित करें', 'अर्ज संपादित करा')}
                          </Button>

                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleValidateReadiness(app.id)}
                            isLoading={validatingId === app.id}
                            leftIcon={<Sparkles className="w-3.5 h-3.5 text-saffron" />}
                          >
                            {pickText('Assess Readiness', 'तत्परता जांचें', 'सज्जता तपासा')}
                          </Button>
                        </>
                      )}

                      {!isLegacySynthetic && app.lifecycle_state === 'awaiting_confirmation' && app.validation_result?.passed && (
                        <Button
                          variant="saffron"
                          size="sm"
                          leftIcon={<CheckCircle2 className="w-4 h-4" />}
                          onClick={() => handleOpenConfirmModal(app)}
                        >
                          {pickText('Review & Confirm', 'समीक्षा व पुष्टि करें', 'तपासा व संमती द्या')}
                        </Button>
                      )}

                      {(app.lifecycle_state === 'confirmed' ||
                        (app.lifecycle_state === 'submission_failed' && !app.blind_retry_blocked)) &&
                        !isPortalSubmitted &&
                        !isSubmissionUnknown &&
                        !isLegacySynthetic && (
                        <>
                          <Button
                            variant="saffron"
                            size="sm"
                            leftIcon={<Send className="w-3.5 h-3.5" />}
                            onClick={() => handleSubmitOrPortalHandoff(app)}
                            isLoading={submittingId === app.id}
                          >
                            {app.integration_supported
                              ? pickText('Submit to Official Portal', 'आधिकारिक पोर्टल पर सबमिट करें', 'अधिकृत पोर्टलवर सादर करा')
                              : pickText('Portal Submission Guidance', 'आधिकारिक पोर्टल निर्देश', 'पोर्टल सादरीकरण मार्गदर्शन')}
                          </Button>
                          {!app.integration_supported && (
                            <Button
                              variant="outline"
                              size="sm"
                              leftIcon={<CheckCircle2 className="w-3.5 h-3.5 text-saffron" />}
                              onClick={() => handleOpenPortalRefModal(app)}
                            >
                              {pickText(
                                'Record Official Portal Reference',
                                'पोर्टल संदर्भ संख्या दर्ज करें',
                                'अधिकृत पोर्टल संदर्भ नोंदवा'
                              )}
                            </Button>
                          )}
                        </>
                      )}

                      {(isSubmissionUnknown || (app.lifecycle_state === 'submission_failed' && app.blind_retry_blocked)) && (
                        <Button
                          variant="saffron"
                          size="sm"
                          leftIcon={<AlertTriangle className="w-3.5 h-3.5" />}
                          onClick={() => handleReconcileSubmission(app.id)}
                          isLoading={submittingId === app.id}
                        >
                          {pickText('Reconcile Submission Status', 'सबमिशन स्थिति जांचें', 'सादरीकरण स्थिती तपासा')}
                        </Button>
                      )}

                      {isPortalSubmitted && (
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-semibold text-teal-900 bg-teal-50 px-3 py-1.5 rounded-full border border-teal-300 flex items-center gap-1.5">
                            <CheckCircle2 className="w-3.5 h-3.5 text-teal-700" />
                            {pickText('Portal Ref (Citizen Reported):', 'पोर्टल संदर्भ:', 'पोर्टल संदर्भ:')}{' '}
                            {portalRefNum}
                          </span>
                          {resolvedTrackingUrl && (
                            <a href={resolvedTrackingUrl} target="_blank" rel="noopener noreferrer">
                              <Button variant="outline" size="sm" rightIcon={<ExternalLink className="w-3.5 h-3.5" />}>
                                {pickText('Track Status', 'स्थिति ट्रैक करें', 'स्थिती पहा')}
                              </Button>
                            </a>
                          )}
                          {resolvedPortalUrl && (
                            <a href={resolvedPortalUrl} target="_blank" rel="noopener noreferrer">
                              <Button variant="saffron" size="sm" rightIcon={<ExternalLink className="w-3.5 h-3.5" />}>
                                {pickText('Official Portal', 'आधिकारिक पोर्टल', 'अधिकृत पोर्टल')}
                              </Button>
                            </a>
                          )}
                        </div>
                      )}

                      {isOfficialSubmitted && (
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-sage-green bg-sage-light px-3 py-1.5 rounded-full border border-sage/30 flex items-center gap-1.5">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            {pickText('Submitted Ref:', 'आधिकारिक संदर्भ:', 'अधिकृत संदर्भ:')}{' '}
                            {app.external_reference_id}
                          </span>
                          {resolvedPortalUrl && (
                            <a href={resolvedPortalUrl} target="_blank" rel="noopener noreferrer">
                              <Button variant="saffron" size="sm" rightIcon={<ExternalLink className="w-3.5 h-3.5" />}>
                                {pickText('Official Portal', 'आधिकारिक पोर्टल', 'अधिकृत पोर्टल')}
                              </Button>
                            </a>
                          )}
                        </div>
                      )}

                      <Link to={`/schemes/${app.scheme_id}`}>
                        <Button variant="outline" size="sm">
                          {pickText('Scheme Details', 'योजना विवरण', 'योजना तपशील')}
                        </Button>
                      </Link>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Interactive Edit Application Modal */}
      {editingApp && (
        <Modal
          isOpen={!!editingApp}
          onClose={() => setEditingApp(null)}
          maxWidth="xl"
          title={
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-saffron-light flex items-center justify-center text-saffron-dark shrink-0">
                <Pencil className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-base font-bold text-navy font-editorial leading-tight">
                  {editingSchema?.title || editingApp.scheme_name || 'Application Form'}
                </h3>
                <p className="text-[11px] text-navy/50 font-normal">
                  {pickText(
                    'Complete mandatory fields, correct attributes, and save changes.',
                    'अनिवार्य विवरण दर्ज करें एवं त्रुटियों को सुधारें।',
                    'अनिवार्य माहिती भरा, तपशील तपासा आणि बदल जतन करा.'
                  )}
                </p>
              </div>
            </div>
          }
          footer={
            <div className="flex items-center justify-between w-full flex-wrap gap-2">
              <span className="text-[11px] text-navy/50 italic">
                * {pickText('Indicates required mandatory field', 'अनिवार्य फ़ील्ड दर्शाता है', 'अनिवार्य माहिती दर्शवते')}
              </span>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={() => setEditingApp(null)} disabled={savingDraft}>
                  {pickText('Cancel', 'रद्द करें', 'रद्द करा')}
                </Button>
                {editingSchema?.form_supported !== false && (
                  <>
                    <Button
                      variant="primary"
                      size="sm"
                      leftIcon={<Save className="w-3.5 h-3.5" />}
                      onClick={() => handleSaveDraft(false)}
                      isLoading={savingDraft}
                    >
                      {pickText('Save Draft', 'ड्राफ्ट सहेजें', 'मसुदा जतन करा')}
                    </Button>
                    <Button
                      variant="saffron"
                      size="sm"
                      leftIcon={<Sparkles className="w-3.5 h-3.5" />}
                      onClick={() => handleSaveDraft(true)}
                      isLoading={savingDraft}
                    >
                      {pickText('Save & Assess Readiness', 'सहेजें व तत्परता जांचें', 'जतन करा व सज्जता तपासा')}
                    </Button>
                  </>
                )}
              </div>
            </div>
          }
        >
          {loadingSchema ? (
            <div className="py-12">
              <Spinner label={pickText('Loading application form schema...', 'फ़ॉर्म लोड हो रहा है...', 'अर्ज लोड होत आहे...')} />
            </div>
          ) : (
            <div className="space-y-6 max-h-[65vh] overflow-y-auto pr-1">
              {saveSuccessMsg && (
                <div className="p-3 bg-sage-light text-sage-dark rounded-xl text-xs font-semibold flex items-center gap-2 border border-sage/30">
                  <Check className="w-4 h-4 text-sage-green shrink-0" />
                  <span>{saveSuccessMsg}</span>
                </div>
              )}

              {editingSchema?.form_supported === false || editingSchema?.schema_available === false ? (
                <div className="p-5 rounded-2xl bg-amber-50 border border-amber-200 text-amber-950 space-y-3 text-xs">
                  <div className="flex items-start gap-2.5">
                    <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                    <div className="space-y-1">
                      <h4 className="font-bold text-sm text-navy">
                        {pickText(
                          'Application Schema Unavailable',
                          'आवेदन फ़ॉर्म स्कीमा उपलब्ध नहीं है',
                          'अर्ज फॉर्म नमुना उपलब्ध नाही'
                        )}
                      </h4>
                      <p className="leading-relaxed">
                        {editingSchema.message ||
                          pickText(
                            'This scheme does not have a verified application form mapping yet. Eligibility evaluation and document guidance remain available, while final form submission takes place directly on the official portal.',
                            'इस योजना के लिए सत्यापित आवेदन फ़ॉर्म मैपिंग उपलब्ध नहीं है। कृपया सीधे आधिकारिक पोर्टल पर आवेदन करें।',
                            'या योजनेसाठी पडताळलेला अर्ज फॉर्म नमुना उपलब्ध नाही. कृपया थेट अधिकृत पोर्टलवर अर्ज करा.'
                          )}
                      </p>
                    </div>
                  </div>
                  {(editingSchema.official_portal || editingApp.official_url) && (
                    <a
                      href={editingSchema.official_portal || editingApp.official_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-saffron hover:bg-saffron-dark text-white font-bold text-xs rounded-xl shadow-subtle"
                    >
                      <span>{pickText('Open Official Portal', 'आधिकारिक पोर्टल खोलें', 'अधिकृत पोर्टल उघडा')}</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  )}
                </div>
              ) : editingSchema?.sections && editingSchema.sections.length > 0 ? (
                editingSchema.sections.map((section) => {
                  const prefillSection = (editingApp.prefill_summary?.sections || []).find(
                    (ps: any) => ps.section_id === section.section_id
                  );
                  return (
                  <div key={section.section_id} className="p-4.5 rounded-2xl bg-ivory-50/70 border border-navy/8 space-y-3.5">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-navy flex items-center gap-1.5 pb-2 border-b border-navy/6">
                      <Layers className="w-3.5 h-3.5 text-saffron" />
                      <span>{section.title}</span>
                    </h4>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                      {section.fields.map((field) => {
                        const val = formValues[field.name] ?? '';
                        const hasError = !!formErrors[field.name];
                        const prefillMeta = (prefillSection?.fields || []).find((pf: any) => pf.name === field.name);
                        const conflict = !resolvedModalConflicts[field.name] ? prefillMeta?.conflict : null;

                        return (
                          <div key={field.name} className="space-y-1">
                            <label className="text-xs font-semibold text-navy flex items-center justify-between gap-1.5 flex-wrap">
                              <span className="flex items-center gap-1">
                                {field.label}
                                {field.required && <span className="text-rose-600 font-bold">*</span>}
                              </span>
                              {conflict ? (
                                <span className="text-[10px] text-rose-700 bg-rose-50 px-1.5 py-0.5 rounded border border-rose-200 font-semibold">
                                  {pickText('Conflict', 'विरोधाभास', 'तफावत')}
                                </span>
                              ) : prefillMeta?.source_label && String(val).trim() !== '' ? (
                                <span className="text-[10px] text-sage-dark bg-sage-light/70 px-1.5 py-0.5 rounded border border-sage/25 font-medium">
                                  {prefillMeta.source_label}
                                </span>
                              ) : !field.required ? (
                                <span className="text-[10px] text-navy/45 font-normal">
                                  {pickText('Optional', 'वैकल्पिक', 'ऐच्छिक')}
                                </span>
                              ) : (
                                <span className="text-[10px] text-amber-800 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200 font-medium">
                                  {pickText('Input Needed', 'प्रविष्टि आवश्यक', 'माहिती आवश्यक')}
                                </span>
                              )}
                            </label>

                            {field.type === 'select' && field.options ? (
                              <select
                                value={val}
                                onChange={(e) => handleFieldChange(field.name, e.target.value)}
                                className={`w-full px-3 py-2 text-xs rounded-xl bg-white border focus:outline-none focus:ring-1 transition-all ${
                                  hasError || conflict ? 'border-rose-400 focus:ring-rose-400' : 'border-navy/15 focus:ring-saffron'
                                }`}
                              >
                                <option value="">
                                  -- {pickText('Select option', 'विकल्प चुनें', 'पर्याय निवडा')} --
                                </option>
                                {field.options.map((opt) => (
                                  <option key={opt} value={opt}>
                                    {opt}
                                  </option>
                                ))}
                              </select>
                            ) : (
                              <input
                                type={field.type === 'number' ? 'number' : field.type === 'date' ? 'date' : 'text'}
                                value={val}
                                placeholder={
                                  field.placeholder ||
                                  (field.required
                                    ? pickText('Required', 'अनिवार्य', 'आवश्यक')
                                    : pickText('Optional', 'वैकल्पिक', 'ऐच्छिक'))
                                }
                                onChange={(e) => handleFieldChange(field.name, e.target.value, field.pattern)}
                                className={`w-full px-3 py-2 text-xs rounded-xl bg-white border focus:outline-none focus:ring-1 transition-all ${
                                  hasError || conflict ? 'border-rose-400 focus:ring-rose-400' : 'border-navy/15 focus:ring-saffron'
                                }`}
                              />
                            )}

                            {conflict && (
                              <div className="p-2 rounded-lg bg-amber-50/90 border border-amber-200 space-y-1 text-[10.5px]">
                                <p className="text-amber-950 font-medium">{conflict.message}</p>
                                <div className="flex flex-wrap gap-1">
                                  {conflict.candidates.map((cand: any, cIdx: number) => (
                                    <button
                                      key={cIdx}
                                      type="button"
                                      onClick={() => handleFieldChange(field.name, String(cand.value), field.pattern)}
                                      className="px-2 py-0.5 rounded bg-white border border-amber-300 hover:border-saffron text-navy font-semibold"
                                    >
                                      {cand.source_label}: {String(cand.value)}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            )}

                            {hasError && (
                              <p className="text-[10.5px] text-rose-600 font-medium leading-tight">
                                {formErrors[field.name]}
                              </p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                  );
                })
              ) : (
                <div className="p-4.5 rounded-2xl bg-ivory-50/70 border border-navy/8 space-y-3.5">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-navy pb-2 border-b border-navy/6">
                    {pickText('General Applicant Details', 'सामान्य आवेदक विवरण', 'सामान्य अर्जदार तपशील')}
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                    {Object.entries(formValues).map(([k, val]) => (
                      <div key={k} className="space-y-1">
                        <label className="text-xs font-semibold text-navy capitalize">
                          {k.replace(/_/g, ' ')}
                        </label>
                        <input
                          type="text"
                          value={val || ''}
                          onChange={(e) => handleFieldChange(k, e.target.value)}
                          className="w-full px-3 py-2 text-xs rounded-xl bg-white border border-navy/15 focus:ring-1 focus:ring-saffron focus:outline-none"
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </Modal>
      )}

      {/* Complete Application Review & Explicit Citizen Confirmation Modal */}
      {confirmingApp && (
        <Modal
          isOpen={!!confirmingApp}
          onClose={() => {
            setConfirmingApp(null);
            setConfirmReview(null);
            setConfirmConsentChecked(false);
          }}
          maxWidth="xl"
          title={
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-saffron" />
              <span>
                {pickText(
                  'Complete Application Review & Explicit Confirmation',
                  'पूर्ण आवेदन समीक्षा एवं स्पष्ट नागरिक पुष्टि',
                  'संपूर्ण अर्ज तपासणी व नागरिकाची स्पष्ट संमती'
                )}
              </span>
            </div>
          }
          footer={
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setConfirmingApp(null);
                  setConfirmReview(null);
                  setConfirmConsentChecked(false);
                }}
              >
                {pickText('Cancel', 'रद्द करें', 'रद्द करा')}
              </Button>
              <Button
                variant="saffron"
                size="sm"
                leftIcon={<CheckCircle2 className="w-4 h-4" />}
                onClick={handleConfirmOnly}
                disabled={!confirmConsentChecked || loadingReview}
                isLoading={submitting}
              >
                {pickText(
                  `I Authorize & Confirm Version v${confirmReview?.version ?? confirmingApp.version ?? 1}`,
                  `संस्करण v${confirmReview?.version ?? confirmingApp.version ?? 1} की पुष्टि करें`,
                  `आवृत्ती v${confirmReview?.version ?? confirmingApp.version ?? 1} अधिकृत व नक्की करा`
                )}
              </Button>
            </>
          }
        >
          {loadingReview ? (
            <div className="py-10">
              <Spinner label={pickText('Loading full application summary...', 'पूर्ण सारांश लोड हो रहा है...', 'संपूर्ण सारांश लोड होत आहे...')} />
            </div>
          ) : (
            <div className="space-y-4 text-sm text-navy max-h-[65vh] overflow-y-auto pr-1">
              <div className="flex items-center justify-between gap-2 flex-wrap bg-ivory-50 p-3 rounded-xl border border-navy/10 text-xs">
                <div>
                  <span className="font-bold text-navy block">
                    {confirmingApp.scheme_name || confirmingApp.scheme_code}
                  </span>
                  <span className="text-[11px] text-navy/60 font-mono">
                    ID: {confirmingApp.id} • v{confirmReview?.version ?? confirmingApp.version ?? 1}
                    {(confirmReview?.data_hash || confirmingApp.data_hash)
                      ? ` • ${(confirmReview?.data_hash || confirmingApp.data_hash || '').slice(0, 12)}`
                      : ''}
                  </span>
                </div>
                <span className="text-[10.5px] font-semibold px-2.5 py-1 rounded-full bg-amber-50 text-amber-900 border border-amber-200">
                  {confirmReview?.portal_integration?.submission_method_label ||
                    (confirmReview?.submission?.integration_supported
                      ? pickText('Official Portal Integration', 'आधिकारिक पोर्टल एकीकरण', 'अधिकृत पोर्टल जोडणी')
                      : pickText('Official Portal Required', 'आधिकारिक पोर्टल पर जमा', 'अधिकृत पोर्टल आवश्यक'))}
                </span>
              </div>

              {/* Official Portal Instructions & OTP/CAPTCHA Non-Bypass Notice */}
              {(confirmReview?.portal_integration || confirmReview?.submission?.official_portal_url) && (
                <div className="p-3.5 rounded-xl bg-white border border-navy/10 space-y-2 text-xs">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <span className="font-bold text-navy">
                      {confirmReview?.portal_integration?.portal_name ||
                        pickText('Official Portal Integration Details', 'आधिकारिक पोर्टल विवरण', 'अधिकृत पोर्टल तपशील')}
                    </span>
                    {confirmReview?.portal_integration?.application_availability_label && (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-ivory-100 text-navy/80 border border-navy/10">
                        {confirmReview.portal_integration.application_availability_label}
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-navy/75 space-y-1">
                    {(confirmReview?.portal_integration?.official_application_url ||
                      confirmReview?.submission?.official_portal_url) && (
                      <div className="break-all">
                        <span className="font-semibold text-navy">
                          {pickText('Official Application URL:', 'आधिकारिक आवेदन लिंक:', 'अधिकृत अर्ज लिंक:')}{' '}
                        </span>
                        <a
                          href={
                            confirmReview?.portal_integration?.official_application_url ||
                            confirmReview?.submission?.official_portal_url
                          }
                          target="_blank"
                          rel="noopener noreferrer"
                          className="underline text-saffron-dark"
                        >
                          {confirmReview?.portal_integration?.official_application_url ||
                            confirmReview?.submission?.official_portal_url}
                        </a>
                      </div>
                    )}
                    {confirmReview?.portal_integration?.tracking_url && (
                      <div className="break-all">
                        <span className="font-semibold text-navy">
                          {pickText('Tracking URL:', 'ट्रैकिंग लिंक:', 'स्थिती लिंक:')}{' '}
                        </span>
                        <a
                          href={confirmReview.portal_integration.tracking_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="underline text-saffron-dark"
                        >
                          {confirmReview.portal_integration.tracking_url}
                        </a>
                      </div>
                    )}
                  </div>
                  {Array.isArray(confirmReview?.portal_integration?.official_instructions?.online_steps) &&
                    confirmReview.portal_integration.official_instructions.online_steps.length > 0 && (
                      <ol className="list-decimal pl-4 space-y-1 text-[11px] text-navy/80">
                        {confirmReview.portal_integration.official_instructions.online_steps.map((s, idx) => (
                          <li key={idx}>{s}</li>
                        ))}
                      </ol>
                    )}
                  {confirmReview?.portal_integration?.security_controls_notice && (
                    <p className="text-[10.5px] text-amber-900 bg-amber-50/70 p-2 rounded-lg border border-amber-200">
                      {confirmReview.portal_integration.security_controls_notice}
                    </p>
                  )}
                </div>
              )}

              {/* Complete Section-by-Section Field Summary with Provenance */}
              {(confirmReview?.sections || []).length > 0 && (
                <div className="space-y-3">
                  {(confirmReview?.sections || []).map((sec) => (
                    <div key={sec.section_id} className="p-3.5 rounded-xl bg-ivory-50/70 border border-navy/8 space-y-2 text-xs">
                      <h4 className="font-bold text-navy/70 uppercase tracking-wider text-[10.5px] border-b border-navy/8 pb-1">
                        {sec.title}
                      </h4>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                        {sec.fields.map((f) => (
                          <div key={f.name} className="bg-white rounded-lg p-2 border border-navy/6 space-y-0.5">
                            <div className="flex items-center justify-between gap-1 text-[10.5px] text-navy/60">
                              <span className="truncate font-medium">{f.label}</span>
                              {f.source_badge && (
                                <span className="text-[9.5px] px-1.5 py-0.5 rounded bg-sage-light/60 text-sage-dark border border-sage/20 shrink-0">
                                  {f.source_badge}
                                </span>
                              )}
                            </div>
                            <div className="font-semibold text-navy truncate">{renderCleanValue(f.value)}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Explicit Authorization Disclosure & Checkbox */}
              <div className="p-3.5 rounded-xl bg-amber-50/60 border border-amber-200 space-y-2.5 text-xs">
                <p className="text-navy/85 leading-relaxed">
                  {confirmReview?.submission?.integration_supported
                    ? pickText(
                        `By confirming, you authorize submission of version v${confirmReview?.version ?? 1} to the verified external portal integration. Editing any detail later will invalidate this confirmation.`,
                        `पुष्टि करने पर आप संस्करण v${confirmReview?.version ?? 1} को आधिकारिक पोर्टल पर भेजने की अनुमति देते हैं। बाद में कोई भी बदलाव इस पुष्टि को अमान्य कर देगा।`,
                        `संमती दिल्यास तुम्ही आवृत्ती v${confirmReview?.version ?? 1} सादर करण्यास अधिकृत करता. नंतर कोणताही बदल केल्यास ही संमती रद्द होईल.`
                      )
                    : pickText(
                        `By confirming, you authorize this exact reviewed version v${confirmReview?.version ?? 1}. Because no automated government API submission integration is enabled for this scheme, manual submission must still be completed on the official portal. Editing any field later invalidates this confirmation.`,
                        `पुष्टि करने से इस समीक्षित संस्करण v${confirmReview?.version ?? 1} पर आपकी अनुमति दर्ज हो जाती है। इस योजना के लिए स्वचालित सरकारी पोर्टल API उपलब्ध न होने के कारण, अंतिम आवेदन आपको आधिकारिक पोर्टल पर स्वयं जमा करना होगा।`,
                        `संमती दिल्याने या तपासलेल्या आवृत्ती v${confirmReview?.version ?? 1} ला तुमची अधिकृत मान्यता नोंदवली जाते. स्वयंचलित शासकीय पोर्टल API नसल्याने अंतिम अर्ज तुम्हाला अधिकृत पोर्टलवर स्वतः सादर करावा लागेल. नंतर माहिती बदलल्यास ही संमती रद्द होईल.`
                      )}
                </p>

                <label className="flex items-start gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={confirmConsentChecked}
                    onChange={(e) => setConfirmConsentChecked(e.target.checked)}
                    className="mt-0.5 rounded text-saffron focus:ring-saffron w-4 h-4"
                  />
                  <span className="font-semibold text-navy leading-snug">
                    {pickText(
                      `I have reviewed every field and Vault document above and explicitly authorize confirmation for version v${confirmReview?.version ?? confirmingApp.version ?? 1}.`,
                      `मैंने ऊपर दिए गए सभी विवरण और वॉल्ट दस्तावेज़ जांच लिए हैं और संस्करण v${confirmReview?.version ?? confirmingApp.version ?? 1} की स्पष्ट पुष्टि करता/करती हूँ।`,
                      `मी वरील सर्व माहिती व व्हॉल्ट कागदपत्रे तपासली आहेत आणि आवृत्ती v${confirmReview?.version ?? confirmingApp.version ?? 1} साठी स्पष्ट संमती देत आहे.`
                    )}
                  </span>
                </label>
              </div>
            </div>
          )}
        </Modal>
      )}

      {/* Mode B Return: Record Official Government Portal Reference Number Modal */}
      {portalRefApp && (
        <Modal
          isOpen={!!portalRefApp}
          onClose={() => {
            setPortalRefApp(null);
            setPortalRefError(null);
          }}
          maxWidth="md"
          title={
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-saffron" />
              <span>
                {pickText(
                  'Record Official Portal Reference Number',
                  'आधिकारिक पोर्टल संदर्भ संख्या दर्ज करें',
                  'अधिकृत पोर्टल संदर्भ क्रमांक नोंदवा'
                )}
              </span>
            </div>
          }
          footer={
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setPortalRefApp(null);
                  setPortalRefError(null);
                }}
              >
                {pickText('Cancel', 'रद्द करें', 'रद्द करा')}
              </Button>
              <Button
                variant="saffron"
                size="sm"
                leftIcon={<CheckCircle2 className="w-4 h-4" />}
                onClick={handleSavePortalReference}
                isLoading={recordingPortalRef}
              >
                {pickText('Save Official Reference', 'आधिकारिक संदर्भ सहेजें', 'अधिकृत संदर्भ जतन करा')}
              </Button>
            </>
          }
        >
          <div className="space-y-3.5 text-xs text-navy">
            <div className="p-3 rounded-xl bg-ivory-50 border border-navy/10 space-y-1">
              <div className="font-bold text-navy">{portalRefApp.scheme_name || portalRefApp.scheme_code}</div>
              <div className="font-mono text-[11px] text-navy/65">
                {pickText('Internal Draft ID:', 'आंतरिक ड्राफ्ट ID:', 'अंतर्गत मसुदा आयडी:')} {portalRefApp.id}
              </div>
            </div>

            <div className="space-y-1">
              <label className="font-semibold text-navy block">
                {pickText(
                  'Official Government Portal Reference Number *',
                  'आधिकारिक सरकारी पोर्टल संदर्भ संख्या *',
                  'अधिकृत शासकीय पोर्टल संदर्भ क्रमांक *'
                )}
              </label>
              <input
                type="text"
                value={portalRefNumber}
                onChange={(e) => {
                  setPortalRefNumber(e.target.value);
                  if (portalRefError) setPortalRefError(null);
                }}
                placeholder="e.g. PMK-MH-2026-998812"
                className="w-full px-3 py-2 rounded-xl border border-navy/15 font-mono text-xs bg-white focus:outline-none focus:border-saffron"
              />
            </div>

            <div className="space-y-1">
              <label className="font-semibold text-navy block">
                {pickText(
                  'Submission Date (Optional)',
                  'सबमिशन तिथि (वैकल्पिक)',
                  'सादर केल्याची तारीख (ऐच्छिक)'
                )}
              </label>
              <input
                type="date"
                value={portalRefDate}
                onChange={(e) => setPortalRefDate(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-navy/15 text-xs bg-white focus:outline-none focus:border-saffron"
              />
            </div>

            <div className="space-y-1">
              <label className="font-semibold text-navy block">
                {pickText(
                  'Portal Acknowledgment Notes (Optional)',
                  'पोर्टल पावती टिप्पणी (वैकल्पिक)',
                  'पोर्टल पोचपावती टीप (ऐच्छिक)'
                )}
              </label>
              <input
                type="text"
                value={portalRefNotes}
                onChange={(e) => setPortalRefNotes(e.target.value)}
                placeholder={pickText(
                  'e.g. Submitted after Aadhaar OTP on official portal',
                  'उदा. आधिकारिक पोर्टल पर आधार OTP के बाद जमा',
                  'उदा. अधिकृत पोर्टलवर आधार OTP नंतर अर्ज सादर'
                )}
                className="w-full px-3 py-2 rounded-xl border border-navy/15 text-xs bg-white focus:outline-none focus:border-saffron"
              />
            </div>

            {portalRefError && (
              <div className="p-2.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-[11px] font-medium">
                {portalRefError}
              </div>
            )}

            <p className="text-[11px] text-amber-900 bg-amber-50/70 p-2.5 rounded-xl border border-amber-200">
              {pickText(
                'Enter only the official reference number generated after you completed portal login, OTP/CAPTCHA, and submission on the government portal. Your internal draft ID remains stored separately.',
                'सरकारी पोर्टल पर लॉगिन, OTP/कैप्चा और आवेदन पूरा करने के बाद मिली आधिकारिक संदर्भ संख्या ही दर्ज करें। आपका आंतरिक ड्राफ्ट ID अलग सुरक्षित रहेगा।',
                'शासकीय पोर्टलवर लॉगिन, OTP/कॅप्चा व अर्ज सादर केल्यानंतर मिळालेला अधिकृत संदर्भ क्रमांकच नोंदवा. तुमचा अंतर्गत मसुदा आयडी स्वतंत्रपणे जतन राहील.'
              )}
            </p>
          </div>
        </Modal>
      )}
    </div>
  );
};
