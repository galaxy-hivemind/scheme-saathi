import React, { useEffect, useState, useRef } from 'react';
import { documentService } from '@/services/api/documentService';
import { UserDocument } from '@/types';
import { useLanguage } from '@/context/LanguageContext';
import { useAuth } from '@/context/AuthContext';
import { Card, CardHeader, CardContent } from '@/components/common/Card';
import { Button } from '@/components/common/Button';
import { Spinner } from '@/components/common/Spinner';
import { Modal } from '@/components/common/Modal';
import { StatusBanner } from '@/components/common/StatusBanner';
import {
  Upload,
  FileCheck,
  CheckCircle2,
  FileText,
  ShieldCheck,
  Eye,
  AlertTriangle,
  Clock,
  XCircle,
  Trash2,
  ShieldAlert,
  Sparkles,
} from 'lucide-react';

interface CategoryOption {
  value: string;
  en: string;
  hi: string;
  mr: string;
}

const DOCUMENT_CATEGORIES: CategoryOption[] = [
  { value: 'aadhaar_card', en: 'Aadhaar Card', hi: 'आधार कार्ड', mr: 'आधार कार्ड' },
  { value: 'bank_passbook', en: 'Bank Passbook', hi: 'बैंक पासबुक', mr: 'बँक पासबुक' },
  { value: 'income_certificate', en: 'Income Certificate', hi: 'आय प्रमाण पत्र', mr: 'उत्पन्न प्रमाणपत्र' },
  { value: 'land_records', en: 'Land Ownership Records', hi: 'भूमि स्वामित्व रिकॉर्ड', mr: 'शेतजमिनीचा उतारा' },
  { value: 'land_possession', en: 'Homestead Land / Allotment Proof', hi: 'आवासीय भूमि / पट्टा प्रमाण', mr: 'निवासी जागा / वाटप प्रमाणपत्र' },
  { value: 'job_card', en: 'MGNREGA Job Card', hi: 'मनरेगा जॉब कार्ड', mr: 'मनरेगा जॉब कार्ड' },
  { value: 'caste_certificate', en: 'Caste Certificate', hi: 'जाति प्रमाण पत्र', mr: 'जात प्रमाणपत्र' },
  { value: 'domicile_certificate', en: 'Domicile Certificate', hi: 'निवास प्रमाण पत्र', mr: 'अधिवास प्रमाणपत्र' },
  { value: 'ration_card', en: 'Ration Card', hi: 'राशन कार्ड', mr: 'रेशन कार्ड' },
  { value: 'death_certificate', en: "Husband's Death Certificate", hi: 'पति का मृत्यु प्रमाण पत्र', mr: 'पतीचे मृत्यू प्रमाणपत्र' },
  { value: 'mcp_card', en: 'Mother & Child Protection Card', hi: 'मातृ एवं शिशु सुरक्षा कार्ड', mr: 'माता व बाल संरक्षण कार्ड' },
  { value: 'vending_certificate', en: 'Certificate of Vending', hi: 'विक्रय प्रमाण पत्र', mr: 'विक्रेता प्रमाणपत्र' },
  { value: 'marksheet_12th', en: 'Class 12 Marksheet', hi: 'कक्षा 12 अंकसूची', mr: 'इयत्ता १२ वी गुणपत्रक' },
  { value: 'pan_card', en: 'PAN Card', hi: 'पैन कार्ड', mr: 'पॅन कार्ड' },
];

export const DocumentsPage: React.FC<{ initialDocuments?: UserDocument[] }> = ({
  initialDocuments,
}) => {
  const { t, language } = useLanguage();
  const { profile } = useAuth();
  const [documents, setDocuments] = useState<UserDocument[]>(initialDocuments ?? []);
  const [loading, setLoading] = useState<boolean>(initialDocuments === undefined);
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [selectedType, setSelectedType] = useState<string>('aadhaar_card');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Inspection & Citizen Review Modal state
  const [inspectDoc, setInspectDoc] = useState<UserDocument | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [reviewFields, setReviewFields] = useState<Record<string, string>>({});
  const [confirmedAccurate, setConfirmedAccurate] = useState<boolean>(false);
  const [savingReview, setSavingReview] = useState<boolean>(false);
  const [verifyingDoc, setVerifyingDoc] = useState<boolean>(false);
  const [modalNotice, setModalNotice] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const pickText = (en: string, hi: string, mr: string) => {
    if (language === 'hi') return hi;
    if (language === 'mr') return mr;
    return en;
  };

  const getCategoryLabel = (docType: string): string => {
    const norm = (docType || '').toLowerCase().replace(/-/g, '_');
    const found = DOCUMENT_CATEGORIES.find((c) => c.value === norm || (norm === 'aadhaar' && c.value === 'aadhaar_card'));
    if (found) return pickText(found.en, found.hi, found.mr);
    return docType.replace(/_/g, ' ');
  };

  const getDocLifecycle = (doc: UserDocument): string => {
    return doc.lifecycle_status || doc.verification_status || (doc.review_status === 'verified' ? 'verified' : 'awaiting_citizen_review');
  };

  const fetchDocs = async () => {
    setLoading(true);
    try {
      const data = await documentService.getUserDocuments();
      setDocuments(data);
    } catch (err) {
      console.error('Failed to load user documents:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (initialDocuments === undefined) {
      fetchDocs();
    }
  }, []);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadError(null);
    try {
      const newDoc = await documentService.uploadDocument(selectedType, file);
      setDocuments((prev) => [newDoc, ...prev]);
      handleOpenInspect(newDoc);
    } catch (err: any) {
      setUploadError(
        err?.message ||
          pickText(
            'Upload rejected. Please ensure file is a valid PDF, PNG, or JPEG under 10 MB.',
            'दस्तावेज़ अस्वीकार किया गया। कृपया सुनिश्चित करें कि फ़ाइल मान्य PDF, PNG या JPEG (10 MB से कम) है।',
            'दस्तऐवज अपलोड नाकारले गेले. कृपया १० MB पेक्षा लहान वैध PDF, PNG किंवा JPEG फाईल निवडा.'
          )
      );
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleOpenInspect = async (doc: UserDocument) => {
    setInspectDoc(doc);
    setModalNotice(null);
    setPreviewError(null);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    }

    const initialFields = doc.reviewed_fields && Object.keys(doc.reviewed_fields).length > 0
      ? doc.reviewed_fields
      : doc.extracted_fields || {};

    setReviewFields({
      full_name_on_document: String(initialFields.full_name_on_document || ''),
      document_number: String(initialFields.document_number || ''),
      ifsc_code: String(initialFields.ifsc_code || ''),
      issuing_authority: String(initialFields.issuing_authority || ''),
      issue_date: String(initialFields.issue_date || ''),
      expiry_date: String(initialFields.expiry_date || ''),
    });
    setConfirmedAccurate(Boolean(doc.citizen_confirmed_accurate));

    try {
      const url = await documentService.fetchDocumentPreviewUrl(doc.id);
      setPreviewUrl(url);
    } catch {
      setPreviewError(
        pickText(
          'Binary file preview unavailable for legacy record. Re-upload file to inspect pixels/PDF.',
          'इस पुराने रिकॉर्ड के लिए फ़ाइल प्रीव्यू उपलब्ध नहीं है। जांचने के लिए फ़ाइल पुनः अपलोड करें।',
          'या जुन्या नोंदीसाठी फाईल पूर्वावलोकन उपलब्ध नाही. पाहण्यासाठी दस्तऐवज पुन्हा अपलोड करा.'
        )
      );
    }
  };

  const handleSaveReview = async () => {
    if (!inspectDoc) return;
    setSavingReview(true);
    setModalNotice(null);
    try {
      const updated = await documentService.reviewDocument(inspectDoc.id, reviewFields, confirmedAccurate);
      setInspectDoc(updated);
      setDocuments((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
      setModalNotice({
        type: 'success',
        text: confirmedAccurate
          ? pickText(
              'Citizen review saved. You can now run deterministic verification below.',
              'नागरिक समीक्षा सहेजी गई। अब आप नीचे सत्यापन चला सकते हैं।',
              'नागरिक तपासणी जतन केली आहे. आता आपण खालील पडताळणी प्रक्रिया चालवू शकता.'
            )
          : pickText(
              'Draft corrections saved; confirm the accuracy checkbox before verifying.',
              'सुधार सहेजे गए; सत्यापन से पहले सटीकता की पुष्टि करें।',
              'दुरुस्ती जतन केली; पडताळणीपूर्वी माहिती अचूक असल्याची खात्री करा.'
            ),
      });
    } catch (err: any) {
      setModalNotice({ type: 'error', text: err?.message || 'Failed to save review.' });
    } finally {
      setSavingReview(false);
    }
  };

  const handleRunVerification = async () => {
    if (!inspectDoc) return;
    setVerifyingDoc(true);
    setModalNotice(null);
    try {
      const updated = await documentService.verifyDocument(inspectDoc.id);
      setInspectDoc(updated);
      setDocuments((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
      const state = getDocLifecycle(updated);
      if (state === 'verified') {
        setModalNotice({
          type: 'success',
          text: pickText(
            'Document passed deterministic integrity and profile consistency checks.',
            'दस्तावेज़ प्रारूप और प्रोफ़ाइल मिलान जांच में सत्यापित हो गया है।',
            'दस्तऐवज नमुना आणि प्रोफाईल पडताळणीत यशस्वीरित्या प्रमाणित झाले आहे.'
          ),
        });
      } else {
        setModalNotice({
          type: 'error',
          text: updated.rejection_reason || pickText('Verification checks failed.', 'सत्यापन असफल रहा।', 'पडताळणी अयशस्वी ठरली.'),
        });
      }
    } catch (err: any) {
      setModalNotice({ type: 'error', text: err?.message || 'Verification failed.' });
    } finally {
      setVerifyingDoc(false);
    }
  };

  const handleDeleteDocument = async (docId: string) => {
    try {
      await documentService.deleteDocument(docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
      if (inspectDoc?.id === docId) setInspectDoc(null);
    } catch (err: any) {
      setUploadError(err?.message || 'Unable to delete document.');
    }
  };

  const renderStatusBadge = (doc: UserDocument) => {
    const state = getDocLifecycle(doc);
    if (state === 'verified') {
      return (
        <span className="text-[10.5px] font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full inline-flex items-center gap-1 border border-emerald-200">
          <CheckCircle2 className="w-3 h-3" />
          {pickText('Verified', 'सत्यापित', 'पडताळलेले')}
        </span>
      );
    }
    if (state === 'reviewed') {
      return (
        <span className="text-[10.5px] font-semibold text-blue-700 bg-blue-50 px-2.5 py-0.5 rounded-full inline-flex items-center gap-1 border border-blue-200">
          <FileCheck className="w-3 h-3" />
          {pickText('Reviewed (Pending Verification)', 'समीक्षित (सत्यापन शेष)', 'तपासलेले (पडताळणी बाकी)')}
        </span>
      );
    }
    if (state === 'rejected') {
      return (
        <span className="text-[10.5px] font-semibold text-rose-700 bg-rose-50 px-2.5 py-0.5 rounded-full inline-flex items-center gap-1 border border-rose-200">
          <XCircle className="w-3 h-3" />
          {pickText('Rejected', 'अस्वीकृत', 'नाकारलेले')}
        </span>
      );
    }
    return (
      <span className="text-[10.5px] font-semibold text-amber-800 bg-amber-50 px-2.5 py-0.5 rounded-full inline-flex items-center gap-1 border border-amber-200">
        <Clock className="w-3 h-3" />
        {pickText('Awaiting Citizen Review', 'नागरिक समीक्षा लंबित', 'नागरिक तपासणी प्रलंबित')}
      </span>
    );
  };

  const verifiedCount = documents.filter((d) => getDocLifecycle(d) === 'verified').length;
  const pendingCount = documents.filter((d) => !['verified', 'rejected'].includes(getDocLifecycle(d))).length;
  const rejectedCount = documents.filter((d) => getDocLifecycle(d) === 'rejected').length;

  return (
    <div className="space-y-7 max-w-4xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div className="space-y-1">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-sage-light text-sage-dark text-xs font-semibold border border-sage/30">
            <ShieldCheck className="w-3.5 h-3.5 text-sage-green" />
            <span>{pickText('Citizen Document Vault', 'सुरक्षित नागरिक दस्तावेज़ वॉल्ट', 'सुरक्षित नागरिक दस्तऐवज व्हॉल्ट')}</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold font-editorial text-navy tracking-tight">
            {pickText('Document Assistant & Vault', 'दस्तावेज़ सहायक एवं वॉल्ट', 'दस्तऐवज सहाय्यक व व्हॉल्ट')}
          </h1>
          <p className="text-xs sm:text-sm text-navy/60 max-w-xl leading-relaxed">
            {pickText(
              'Upload documents, inspect OCR findings, confirm details, and complete verification checks before applying.',
              'दस्तावेज़ अपलोड करें, OCR विवरण जांचें, जानकारी की पुष्टि करें और आवेदन से पहले सत्यापन पूरा करें।',
              'दस्तऐवज अपलोड करा, OCR माहिती तपासा, तपशील निश्चित करा आणि अर्जापूर्वी पडताळणी पूर्ण करा.'
            )}
          </p>
        </div>

        <Button
          variant="saffron"
          size="md"
          leftIcon={<Upload className="w-4 h-4" />}
          onClick={() => fileInputRef.current?.click()}
          isLoading={uploading}
          className="shrink-0"
        >
          {t.actions.uploadDocument}
        </Button>
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileUpload}
          className="hidden"
          accept=".pdf,.png,.jpg,.jpeg"
        />
      </div>

      {/* Integrity & Non-Auto-Verification Assurance */}
      <StatusBanner
        type="info"
        title={pickText(
          'Document Verification Lifecycle',
          'दस्तावेज़ सत्यापन प्रक्रिया',
          'दस्तऐवज पडताळणी प्रक्रिया'
        )}
        message={pickText(
          'Uploading a file never marks it verified automatically. Every upload goes through format validation, OCR inspection, your explicit citizen review, and verification checks.',
          'फ़ाइल अपलोड करने से दस्तावेज़ स्वतः सत्यापित नहीं होता। प्रत्येक दस्तावेज़ की जांच, नागरिक समीक्षा और प्रारूप सत्यापन के बाद ही पुष्टि की जाती है।',
          'फाईल अपलोड केल्यावर दस्तऐवज आपोआप प्रमाणित होत नाही. प्रत्येक दस्तऐवजाची तपासणी, नागरिक पडताळणी व नमुना तपासणीनंतरच अंतिम मान्यता दिली जाते.'
        )}
      />

      {uploadError && (
        <StatusBanner
          type="danger"
          title={pickText('Document Upload Rejected', 'दस्तावेज़ अपलोड अस्वीकृत', 'दस्तऐवज अपलोड नाकारले')}
          message={uploadError}
        />
      )}

      {/* Document Upload Selector Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <h3 className="font-bold font-editorial text-navy text-base">
              {pickText('Select Document Category to Upload', 'अपलोड के लिए दस्तावेज़ श्रेणी चुनें', 'अपलोड करण्यासाठी दस्तऐवज प्रकार निवडा')}
            </h3>
            <span className="text-xs text-navy/50">PDF, PNG, JPG (max 10MB)</span>
          </div>
        </CardHeader>
        <CardContent className="p-6 space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2.5">
            {DOCUMENT_CATEGORIES.map((type) => {
              const isSelected = selectedType === type.value;
              return (
                <button
                  key={type.value}
                  type="button"
                  onClick={() => setSelectedType(type.value)}
                  className={`p-2.5 rounded-xl border text-xs font-semibold text-left transition-all duration-200 ${
                    isSelected
                      ? 'bg-navy text-white border-navy shadow-subtle'
                      : 'bg-ivory-100 text-navy/75 border-navy/10 hover:border-navy/25 hover:text-navy'
                  }`}
                >
                  {pickText(type.en, type.hi, type.mr)}
                </button>
              );
            })}
          </div>

          <div
            onClick={() => fileInputRef.current?.click()}
            className="border-2 border-dashed border-navy/20 hover:border-saffron/60 bg-ivory-50/50 hover:bg-white rounded-2xl p-8 text-center cursor-pointer transition-all duration-200 group"
          >
            <div className="w-12 h-12 rounded-2xl bg-white group-hover:bg-saffron-light text-navy group-hover:text-saffron-vibrant flex items-center justify-center mx-auto mb-3 shadow-subtle border border-navy/8 transition-colors">
              <Upload className="w-5 h-5" />
            </div>
            <p className="text-sm font-bold text-navy group-hover:text-saffron-dark transition-colors">
              {pickText(
                'Click to select and upload document',
                'दस्तावेज़ फ़ाइल चुनने और अपलोड करने के लिए क्लिक करें',
                'दस्तऐवज फाईल निवडण्यासाठी आणि अपलोड करण्यासाठी क्लिक करा'
              )}
            </p>
            <p className="text-xs text-navy/50 mt-1">
              {pickText(
                'Validates file structure and extracts text for your review',
                'फ़ाइल प्रारूप की जांच करता है और आपकी समीक्षा के लिए विवरण निकालता है',
                'फाईलची रचना तपासते आणि आपल्या पुनरावलोकनासाठी तपशील काढते'
              )}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Vault List Card */}
      <Card>
        <CardHeader className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-ivory-100 flex items-center justify-center text-navy border border-navy/8">
              <FileCheck className="w-4 h-4 text-sage-green" />
            </div>
            <div>
              <h3 className="font-bold font-editorial text-navy text-base">
                {pickText('Stored Documents in Vault', 'वॉल्ट में संग्रहीत दस्तावेज़', 'व्हॉल्टमध्ये संग्रहीत दस्तऐवज')}
              </h3>
              <p className="text-xs text-navy/55">
                {pickText(
                  `${verifiedCount} verified • ${pendingCount} awaiting review/verification • ${rejectedCount} rejected`,
                  `${verifiedCount} सत्यापित • ${pendingCount} समीक्षा लंबित • ${rejectedCount} अस्वीकृत`,
                  `${verifiedCount} पडताळलेले • ${pendingCount} तपासणी प्रलंबित • ${rejectedCount} नाकारलेले`
                )}
              </p>
            </div>
          </div>
          <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-ivory-100 text-navy border border-navy/15">
            {documents.length} {pickText('Total', 'कुल', 'एकूण')}
          </span>
        </CardHeader>

        <CardContent className="p-6">
          {loading ? (
            <Spinner
              size="md"
              label={pickText('Loading vault documents...', 'दस्तावेज़ सूची लोड हो रही है...', 'दस्तऐवज यादी लोड होत आहे...')}
            />
          ) : documents.length === 0 ? (
            <div className="text-center py-8 text-navy/60 text-sm">
              {pickText(
                'No documents uploaded yet.',
                'अभी कोई दस्तावेज़ अपलोड नहीं किया गया है।',
                'अद्याप कोणताही दस्तऐवज अपलोड केलेला नाही.'
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {documents.map((doc) => {
                const state = getDocLifecycle(doc);
                return (
                  <div
                    key={doc.id}
                    className={`flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-2xl border transition-all duration-200 ${
                      state === 'rejected'
                        ? 'border-rose-200 bg-rose-50/30'
                        : state === 'verified'
                        ? 'border-emerald-200/80 bg-white'
                        : 'border-amber-200/70 bg-amber-50/20'
                    }`}
                  >
                    <div className="flex items-start gap-3.5 min-w-0">
                      <div className="w-10 h-10 rounded-xl bg-ivory-100 flex items-center justify-center text-navy shrink-0 border border-navy/8 mt-0.5">
                        <FileText className="w-5 h-5 text-navy/70" />
                      </div>
                      <div className="space-y-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h4 className="font-bold text-sm text-navy">
                            {getCategoryLabel(doc.document_type)}
                          </h4>
                          {renderStatusBadge(doc)}
                        </div>
                        <p className="text-xs text-navy/55 truncate">
                          {doc.file_name || doc.id} • {pickText('OCR:', 'OCR:', 'OCR:')} {doc.ocr_status || 'limited'} •{' '}
                          {new Date(doc.created_at).toLocaleDateString()}
                        </p>
                        {state === 'rejected' && doc.rejection_reason && (
                          <p className="text-xs text-rose-700 font-medium flex items-center gap-1">
                            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                            <span>{doc.rejection_reason}</span>
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
                      <Button
                        variant={state === 'verified' ? 'outline' : 'saffron'}
                        size="sm"
                        leftIcon={<Eye className="w-3.5 h-3.5" />}
                        onClick={() => handleOpenInspect(doc)}
                      >
                        {state === 'verified'
                          ? pickText('Inspect', 'देखें', 'तपासा')
                          : pickText('Review & Verify', 'समीक्षा व सत्यापन', 'तपासा व प्रमाणित करा')}
                      </Button>
                      <button
                        type="button"
                        onClick={() => handleDeleteDocument(doc.id)}
                        className="p-2 rounded-xl text-navy/40 hover:text-rose-600 hover:bg-rose-50 border border-transparent hover:border-rose-200 transition-colors"
                        title={pickText('Delete document', 'दस्तावेज़ हटाएं', 'दस्तऐवज काढून टाका')}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Citizen Document Inspection, OCR Review & Verification Modal */}
      {inspectDoc && (
        <Modal
          isOpen={!!inspectDoc}
          onClose={() => setInspectDoc(null)}
          maxWidth="xl"
          title={
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-saffron-light flex items-center justify-center text-saffron-dark shrink-0">
                <Eye className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-base font-bold text-navy font-editorial leading-tight">
                  {getCategoryLabel(inspectDoc.document_type)}
                </h3>
                <p className="text-[11px] text-navy/55 font-normal">
                  {inspectDoc.file_name || inspectDoc.id} • {renderStatusBadge(inspectDoc)}
                </p>
              </div>
            </div>
          }
          footer={
            <div className="flex items-center justify-between w-full flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => setInspectDoc(null)}>
                {pickText('Close', 'बंद करें', 'बंद करा')}
              </Button>
              <div className="flex items-center gap-2">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleSaveReview}
                  isLoading={savingReview}
                >
                  {pickText('Save Citizen Review', 'समीक्षा सहेजें', 'तपासणी जतन करा')}
                </Button>
                <Button
                  variant="saffron"
                  size="sm"
                  leftIcon={<Sparkles className="w-3.5 h-3.5" />}
                  onClick={handleRunVerification}
                  isLoading={verifyingDoc}
                  disabled={!['reviewed', 'verified', 'rejected'].includes(getDocLifecycle(inspectDoc))}
                >
                  {pickText('Run Verification Check', 'सत्यापन जांच चलाएं', 'पडताळणी करा')}
                </Button>
              </div>
            </div>
          }
        >
          <div className="space-y-4 max-h-[68vh] overflow-y-auto pr-1 text-xs">
            {modalNotice && (
              <div
                className={`p-3 rounded-xl border flex items-start gap-2 font-medium ${
                  modalNotice.type === 'success'
                    ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                    : 'bg-rose-50 border-rose-200 text-rose-800'
                }`}
              >
                {modalNotice.type === 'success' ? (
                  <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
                ) : (
                  <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
                )}
                <span>{modalNotice.text}</span>
              </div>
            )}

            {/* Honest OCR Extraction Info */}
            <div className="p-3.5 rounded-xl bg-ivory-50 border border-navy/10 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="font-bold text-navy">
                  {pickText('OCR & File Inspection Result', 'OCR एवं फ़ाइल जांच परिणाम', 'OCR व फाईल तपासणी तपशील')}
                </span>
                <span className="text-[11px] font-mono text-navy/60">
                  status: {inspectDoc.ocr_status || 'limited'}
                </span>
              </div>
              {inspectDoc.ocr_note && <p className="text-navy/70">{inspectDoc.ocr_note}</p>}
              {inspectDoc.extracted_fields?.raw_text_preview && (
                <div className="mt-2 p-2 rounded-lg bg-white border border-navy/8 font-mono text-[11px] text-navy/80 max-h-24 overflow-y-auto">
                  {inspectDoc.extracted_fields.raw_text_preview}
                </div>
              )}
            </div>

            {/* File Preview */}
            <div className="rounded-xl border border-navy/10 bg-ivory-50/50 p-3 space-y-2">
              <span className="font-bold text-navy block">
                {pickText('Uploaded File Preview', 'अपलोड फ़ाइल प्रीव्यू', 'अपलोड केलेल्या फाईलचे पूर्वावलोकन')}
              </span>
              {previewUrl ? (
                inspectDoc.content_type?.includes('pdf') ? (
                  <iframe
                    src={previewUrl}
                    title={inspectDoc.file_name || 'Document Preview'}
                    className="w-full h-48 rounded-lg border border-navy/10 bg-white"
                  />
                ) : (
                  <img
                    src={previewUrl}
                    alt={inspectDoc.file_name || 'Document Preview'}
                    className="max-h-52 mx-auto rounded-lg border border-navy/10 object-contain bg-white"
                  />
                )
              ) : (
                <p className="text-navy/55 italic">
                  {previewError || pickText('Loading preview...', 'प्रीव्यू लोड हो रहा है...', 'पूर्वावलोकन लोड होत आहे...')}
                </p>
              )}
            </div>

            {/* Citizen Review & Correction Form */}
            <div className="p-4 rounded-xl bg-white border border-navy/12 space-y-3">
              <h4 className="font-bold text-navy text-xs uppercase tracking-wider">
                {pickText(
                  'Citizen Review & Attribute Confirmation',
                  'नागरिक समीक्षा एवं विवरण पुष्टि',
                  'नागरिक तपासणी व तपशील पडताळणी'
                )}
              </h4>
              <p className="text-[11px] text-navy/60">
                {pickText(
                  `Profile Name: ${profile?.full_name || 'Not set'}. Enter or correct the printed details exactly as shown on your uploaded document.`,
                  `प्रोफ़ाइल नाम: ${profile?.full_name || 'सेट नहीं'}। अपलोड दस्तावेज़ पर मुद्रित विवरण सटीक रूप से दर्ज या सुधारें।`,
                  `प्रोफाईल नाव: ${profile?.full_name || 'नोंदवलेले नाही'}. अपलोड केलेल्या कागदपत्रावरील अचूक माहिती नोंदवा किंवा सुधारा.`
                )}
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="font-semibold text-navy block">
                    {pickText('Name on Document *', 'दस्तावेज़ पर मुद्रित नाम *', 'दस्तऐवजावरील नाव *')}
                  </label>
                  <input
                    type="text"
                    value={reviewFields.full_name_on_document || ''}
                    onChange={(e) => setReviewFields((p) => ({ ...p, full_name_on_document: e.target.value }))}
                    placeholder={profile?.full_name || 'Full Name'}
                    className="w-full px-3 py-1.5 rounded-lg border border-navy/15 focus:outline-none focus:ring-1 focus:ring-saffron"
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-semibold text-navy block">
                    {pickText('Document / Reference Number *', 'दस्तावेज़ / पंजीकरण संख्या *', 'दस्तऐवज / नोंदणी क्रमांक *')}
                  </label>
                  <input
                    type="text"
                    value={reviewFields.document_number || ''}
                    onChange={(e) => setReviewFields((p) => ({ ...p, document_number: e.target.value }))}
                    placeholder="e.g. 234567890123 / Cert No."
                    className="w-full px-3 py-1.5 rounded-lg border border-navy/15 focus:outline-none focus:ring-1 focus:ring-saffron"
                  />
                </div>

                {inspectDoc.document_type === 'bank_passbook' && (
                  <div className="space-y-1">
                    <label className="font-semibold text-navy block">IFSC *</label>
                    <input
                      type="text"
                      value={reviewFields.ifsc_code || ''}
                      onChange={(e) => setReviewFields((p) => ({ ...p, ifsc_code: e.target.value.toUpperCase() }))}
                      placeholder="SBIN0001234"
                      className="w-full px-3 py-1.5 rounded-lg border border-navy/15 focus:outline-none focus:ring-1 focus:ring-saffron"
                    />
                  </div>
                )}

                <div className="space-y-1">
                  <label className="font-semibold text-navy block">
                    {pickText('Issuing Authority', 'जारीकर्ता प्राधिकरण', 'सक्षम प्राधिकरण')}
                  </label>
                  <input
                    type="text"
                    value={reviewFields.issuing_authority || ''}
                    onChange={(e) => setReviewFields((p) => ({ ...p, issuing_authority: e.target.value }))}
                    placeholder="e.g. UIDAI / Tahsildar / SBI"
                    className="w-full px-3 py-1.5 rounded-lg border border-navy/15 focus:outline-none focus:ring-1 focus:ring-saffron"
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-semibold text-navy block">
                    {pickText('Expiry Date (if applicable)', 'समाप्ति तिथि (यदि लागू हो)', 'कालबाह्यता तारीख (असल्यास)')}
                  </label>
                  <input
                    type="date"
                    value={reviewFields.expiry_date || ''}
                    onChange={(e) => setReviewFields((p) => ({ ...p, expiry_date: e.target.value }))}
                    className="w-full px-3 py-1.5 rounded-lg border border-navy/15 focus:outline-none focus:ring-1 focus:ring-saffron"
                  />
                </div>
              </div>

              <label className="flex items-start gap-2 pt-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={confirmedAccurate}
                  onChange={(e) => setConfirmedAccurate(e.target.checked)}
                  className="mt-0.5 rounded border-navy/30 text-saffron focus:ring-saffron"
                />
                <span className="text-[11.5px] text-navy font-medium">
                  {pickText(
                    'I have inspected this uploaded file and confirm that the entered details match the document accurately.',
                    'मैंने अपलोड की गई फ़ाइल की जांच कर ली है और पुष्टि करता/करती हूँ कि दर्ज विवरण दस्तावेज़ से सटीक मेल खाते हैं।',
                    'मी अपलोड केलेली फाईल तपासली असून नोंदवलेले तपशील मूळ दस्तऐवजाशी अचूक जुळतात याची खात्री देतो.'
                  )}
                </span>
              </label>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
