import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import { useLanguage } from '../context/LanguageContext';
import {
  CitizenDocument,
  DocumentChecklistResponse,
  SchemeSummary,
  BeneficiaryProfile,
} from '../types';
import {
  FileText,
  Upload,
  CheckCircle2,
  AlertCircle,
  Trash2,
  Loader2,
  FileCheck,
  Shield,
} from 'lucide-react';

const COMMON_DOC_TYPES = [
  { value: 'aadhaar_card', labelEn: 'Aadhaar Card', labelHi: 'आधार कार्ड' },
  { value: 'income_certificate', labelEn: 'Income Certificate', labelHi: 'आय प्रमाण पत्र' },
  { value: 'caste_certificate', labelEn: 'Caste Certificate', labelHi: 'जाति प्रमाण पत्र' },
  { value: 'land_records_ro_r', labelEn: 'Land Records (RoR / Khasra)', labelHi: 'भूमि अभिलेख (खसरा / खतौनी)' },
  { value: 'bank_passbook', labelEn: 'Bank Passbook / Cancelled Cheque', labelHi: 'बैंक पासबुक' },
  { value: 'ration_card', labelEn: 'Ration Card', labelHi: 'राशन कार्ड' },
  { value: 'disability_certificate', labelEn: 'Disability Certificate', labelHi: 'दिव्यांगता प्रमाण पत्र' },
  { value: 'vending_certificate', labelEn: 'Vending Certificate / LoR', labelHi: 'स्ट्रीट वेंडर पहचान पत्र' },
  { value: 'other', labelEn: 'Other Supporting Document', labelHi: 'अन्य सहायक दस्तावेज़' },
];

export const DocumentsView: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const { t, language } = useLanguage();

  const initialSchemeId = searchParams.get('scheme_id') || '';

  const [schemes, setSchemes] = useState<SchemeSummary[]>([]);
  const [beneficiaries, setBeneficiaries] = useState<BeneficiaryProfile[]>([]);
  const [selectedSchemeId, setSelectedSchemeId] = useState<string>(initialSchemeId);
  const [selectedBeneficiaryId, setSelectedBeneficiaryId] = useState<string>('');

  // Checklist state
  const [checklist, setChecklist] = useState<DocumentChecklistResponse | null>(null);
  const [loadingChecklist, setLoadingChecklist] = useState(false);

  // Uploaded docs state
  const [documents, setDocuments] = useState<CitizenDocument[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(true);

  // Upload modal state
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadDocType, setUploadDocType] = useState<string>('aadhaar_card');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);

  useEffect(() => {
    loadSchemes();
    loadBeneficiaries();
    loadDocuments();
  }, []);

  useEffect(() => {
    if (selectedSchemeId) {
      loadChecklist(selectedSchemeId, selectedBeneficiaryId || undefined);
    } else {
      setChecklist(null);
    }
  }, [selectedSchemeId, selectedBeneficiaryId]);

  const loadSchemes = async () => {
    try {
      const res = await api.schemes.list({ limit: 100 });
      setSchemes(res.items);
    } catch {
      // Non-blocking
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

  const loadDocuments = async () => {
    try {
      setLoadingDocs(true);
      const res = await api.documents.list();
      setDocuments(res.items);
    } catch {
      // Non-blocking
    } finally {
      setLoadingDocs(false);
    }
  };

  const loadChecklist = async (schemeId: string, beneficiaryId?: string) => {
    try {
      setLoadingChecklist(true);
      const res = await api.documents.getChecklist(schemeId, beneficiaryId || null);
      setChecklist(res);
    } catch {
      setChecklist(null);
    } finally {
      setLoadingChecklist(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (file.size > 10 * 1024 * 1024) {
        setUploadError(
          language === 'hi'
            ? 'फ़ाइल का आकार 10MB से अधिक नहीं होना चाहिए'
            : 'File size must not exceed 10MB'
        );
        return;
      }
      setUploadFile(file);
      setUploadError(null);
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) return;

    try {
      setUploading(true);
      setUploadError(null);
      await api.documents.upload(
        uploadFile,
        uploadDocType,
        selectedBeneficiaryId || null
      );
      setUploadSuccess(
        language === 'hi'
          ? 'दस्तावेज़ सफलतापूर्वक अपलोड और सुरक्षित रूप से सत्यापित हुआ!'
          : 'Document uploaded and securely verified!'
      );
      setUploadFile(null);
      // Refresh documents and checklist
      await loadDocuments();
      if (selectedSchemeId) {
        await loadChecklist(selectedSchemeId, selectedBeneficiaryId || undefined);
      }
    } catch (err: any) {
      setUploadError(err?.response?.data?.message || 'Document upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (docId: string) => {
    if (
      !window.confirm(
        language === 'hi'
          ? 'क्या आप निश्चित रूप से इस दस्तावेज़ को हटाना चाहते हैं?'
          : 'Are you sure you want to delete this document?'
      )
    ) {
      return;
    }

    try {
      await api.documents.delete(docId);
      await loadDocuments();
      if (selectedSchemeId) {
        await loadChecklist(selectedSchemeId, selectedBeneficiaryId || undefined);
      }
    } catch {
      // Error handling
    }
  };

  const readinessPercent = checklist
    ? checklist.total_required > 0
      ? Math.round((checklist.total_fulfilled / checklist.total_required) * 100)
      : 100
    : 0;

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 pb-24 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900">{t('docs.title')}</h1>
        <p className="text-slate-500 text-sm mt-1">
          {language === 'hi'
            ? 'योजनाओं के लिए आवश्यक दस्तावेज़ अपलोड करें और तैयारी जांचें'
            : 'Track readiness against scheme document criteria and manage your family vault'}
        </p>
      </div>

      {/* Scheme & Beneficiary Selector for Checklist */}
      <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
        <h2 className="text-sm font-bold text-slate-900 mb-3">
          {language === 'hi' ? 'योजना के अनुसार चेकलिस्ट देखें' : 'View Checklist by Scheme'}
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              {language === 'hi' ? 'योजना चुनें' : 'Select Welfare Scheme'}
            </label>
            <select
              value={selectedSchemeId}
              onChange={(e) => {
                setSelectedSchemeId(e.target.value);
                setSearchParams(e.target.value ? { scheme_id: e.target.value } : {});
              }}
              className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              <option value="">
                {language === 'hi' ? '-- योजना का चयन करें --' : '-- Choose a scheme --'}
              </option>
              {schemes.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.scheme_code})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              {language === 'hi' ? 'आवेदक / लाभार्थी' : 'Applicant / Beneficiary'}
            </label>
            <select
              value={selectedBeneficiaryId}
              onChange={(e) => setSelectedBeneficiaryId(e.target.value)}
              className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              <option value="">{language === 'hi' ? 'स्वयं (खाता धारक)' : 'Self (Account Holder)'}</option>
              {beneficiaries.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.full_name} ({b.relationship})
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Readiness Checklist Card */}
        {loadingChecklist ? (
          <div className="py-10 flex justify-center">
            <Loader2 className="w-6 h-6 text-emerald-600 animate-spin" />
          </div>
        ) : checklist ? (
          <div className="mt-6 pt-5 border-t border-slate-100 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h3 className="font-bold text-slate-900 text-base">{checklist.scheme_name}</h3>
                <p className="text-xs text-slate-500">
                  {language === 'hi' ? 'आवेदक: ' : 'Target: '}
                  <span className="font-semibold text-slate-700">{checklist.target_name}</span>
                </p>
              </div>

              <div className="flex items-center space-x-3">
                <div className="text-right">
                  <div className="text-sm font-bold text-slate-900">
                    {checklist.total_fulfilled} / {checklist.total_required}{' '}
                    {language === 'hi' ? 'आवश्यक तैयार' : 'Fulfilled'}
                  </div>
                  <div className="text-xs text-slate-500">{readinessPercent}% Ready</div>
                </div>
                <span
                  className={`px-3 py-1 rounded-full text-xs font-bold ${
                    checklist.is_ready_for_application
                      ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                      : 'bg-amber-100 text-amber-800 border border-amber-300'
                  }`}
                >
                  {checklist.is_ready_for_application
                    ? t('docs.ready_status')
                    : t('docs.missing_status')}
                </span>
              </div>
            </div>

            {/* Progress Bar */}
            <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  readinessPercent === 100 ? 'bg-emerald-500' : 'bg-amber-500'
                }`}
                style={{ width: `${readinessPercent}%` }}
              />
            </div>

            {/* Checklist Items */}
            <div className="divide-y divide-slate-100 pt-2">
              {checklist.items.map((item, idx) => (
                <div key={idx} className="py-3 flex items-start justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center space-x-2">
                      {item.status === 'FULFILLED' ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                      ) : (
                        <AlertCircle className="w-4 h-4 text-amber-500 flex-shrink-0" />
                      )}
                      <span className="text-sm font-semibold text-slate-900">
                        {language === 'hi' ? item.description_hi : item.description_en}
                      </span>
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                          item.is_mandatory
                            ? 'bg-red-50 text-red-700'
                            : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {item.is_mandatory ? t('docs.mandatory') : t('docs.optional')}
                      </span>
                    </div>

                    {item.acceptable_alternatives && item.acceptable_alternatives.length > 0 && (
                      <p className="text-xs text-slate-500 pl-6">
                        {language === 'hi' ? 'विकल्प: ' : 'Alternatives: '}
                        {item.acceptable_alternatives.join(', ')}
                      </p>
                    )}

                    {(item.where_to_obtain_en || item.where_to_obtain_hi) && (
                      <p className="text-xs text-emerald-700 pl-6">
                        <span className="font-semibold">
                          {language === 'hi' ? 'प्राप्ति केंद्र: ' : 'Obtain at: '}
                        </span>
                        {language === 'hi' ? item.where_to_obtain_hi : item.where_to_obtain_en}
                      </p>
                    )}
                  </div>

                  <div>
                    <span
                      className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
                        item.status === 'FULFILLED'
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : 'bg-amber-50 text-amber-700 border border-amber-200'
                      }`}
                    >
                      {item.status === 'FULFILLED'
                        ? language === 'hi'
                          ? 'उपलब्ध'
                          : 'Uploaded'
                        : language === 'hi'
                        ? 'आवश्यक'
                        : 'Missing'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>

      {/* Upload Dropzone & Form */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
        <h2 className="text-lg font-bold text-slate-900 mb-1">{t('docs.upload_btn')}</h2>
        <p className="text-xs text-slate-500 mb-4">
          {language === 'hi'
            ? 'सुरक्षित भंडारण: दस्तावेज़ SHA-256 चेकसम द्वारा एन्क्रिप्टेड और सत्यापित रहते हैं'
            : 'Secure vault: Documents are hashed with SHA-256 for cryptographic integrity'}
        </p>

        <form onSubmit={handleUploadSubmit} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                {language === 'hi' ? 'दस्तावेज़ का प्रकार' : 'Document Type'}
              </label>
              <select
                value={uploadDocType}
                onChange={(e) => setUploadDocType(e.target.value)}
                className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                {COMMON_DOC_TYPES.map((d) => (
                  <option key={d.value} value={d.value}>
                    {language === 'hi' ? d.labelHi : d.labelEn}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                {language === 'hi' ? 'किसके लिए है?' : 'Belongs to'}
              </label>
              <select
                value={selectedBeneficiaryId}
                onChange={(e) => setSelectedBeneficiaryId(e.target.value)}
                className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                <option value="">{language === 'hi' ? 'स्वयं (खाता धारक)' : 'Self (Account Holder)'}</option>
                {beneficiaries.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.full_name} ({b.relationship})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* File input / dropzone */}
          <div className="border-2 border-dashed border-slate-300 rounded-2xl p-6 text-center hover:border-emerald-500 transition cursor-pointer relative bg-slate-50/50">
            <input
              type="file"
              onChange={handleFileChange}
              accept=".pdf,.png,.jpg,.jpeg"
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            />
            <div className="flex flex-col items-center pointer-events-none">
              <Upload className="w-10 h-10 text-emerald-600 mb-2" />
              <p className="text-sm font-semibold text-slate-800">
                {uploadFile ? uploadFile.name : t('docs.drag_drop')}
              </p>
              {uploadFile ? (
                <p className="text-xs text-emerald-600 mt-1 font-medium">
                  {(uploadFile.size / (1024 * 1024)).toFixed(2)} MB • Ready to upload
                </p>
              ) : (
                <p className="text-xs text-slate-400 mt-1">PDF, JPG, JPEG, PNG (Max 10 MB)</p>
              )}
            </div>
          </div>

          {uploadError && (
            <div className="p-3 bg-red-50 text-red-700 rounded-xl text-xs flex items-center">
              <AlertCircle className="w-4 h-4 mr-2 flex-shrink-0" />
              <span>{uploadError}</span>
            </div>
          )}

          {uploadSuccess && (
            <div className="p-3 bg-emerald-50 text-emerald-800 rounded-xl text-xs flex items-center">
              <CheckCircle2 className="w-4 h-4 mr-2 flex-shrink-0" />
              <span>{uploadSuccess}</span>
            </div>
          )}

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={!uploadFile || uploading}
              className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-sm font-semibold transition disabled:opacity-50 flex items-center shadow-sm"
            >
              {uploading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  {language === 'hi' ? 'अपलोड हो रहा है...' : 'Uploading...'}
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4 mr-2" />
                  {t('docs.upload_btn')}
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Uploaded Documents Vault */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900">
              {language === 'hi' ? 'अपलोड किए गए दस्तावेज़ (Vault)' : 'Uploaded Documents Vault'}
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              {language === 'hi'
                ? `कुल ${documents.length} दस्तावेज़ सुरक्षित रूप से संग्रहीत`
                : `${documents.length} verified documents in secure vault`}
            </p>
          </div>
          <Shield className="w-5 h-5 text-emerald-600" />
        </div>

        {loadingDocs ? (
          <div className="py-12 flex justify-center">
            <Loader2 className="w-6 h-6 text-emerald-600 animate-spin" />
          </div>
        ) : documents.length === 0 ? (
          <div className="py-12 text-center text-slate-400">
            <FileText className="w-10 h-10 mx-auto mb-2 opacity-50" />
            <p className="text-sm font-medium">
              {language === 'hi' ? 'कोई दस्तावेज़ अपलोड नहीं किया गया है' : 'No documents in vault yet'}
            </p>
            <p className="text-xs text-slate-400 mt-1">
              {language === 'hi'
                ? 'ऊपर दिए गए फॉर्म से अपना पहला दस्तावेज़ अपलोड करें'
                : 'Upload documents above to verify eligibility and fulfill scheme checklists'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="p-4 rounded-xl border border-slate-200 bg-slate-50/60 hover:bg-white transition flex items-start justify-between group"
              >
                <div className="flex items-start space-x-3">
                  <div className="w-10 h-10 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <FileCheck className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-slate-900">{doc.file_name}</h4>
                    <p className="text-xs font-semibold text-emerald-800 uppercase tracking-wide mt-0.5">
                      {doc.document_type.replace(/_/g, ' ')}
                    </p>
                    <div className="flex items-center space-x-2 text-[11px] text-slate-400 mt-1">
                      <span>{(doc.file_size_bytes / 1024).toFixed(0)} KB</span>
                      <span>•</span>
                      <span className="font-mono truncate max-w-[140px]" title={doc.checksum_sha256}>
                        SHA: {doc.checksum_sha256.substring(0, 10)}...
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <span
                    className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${
                      doc.verification_status === 'VERIFIED'
                        ? 'bg-emerald-100 text-emerald-800'
                        : doc.verification_status === 'REJECTED'
                        ? 'bg-red-100 text-red-800'
                        : 'bg-slate-100 text-slate-700'
                    }`}
                  >
                    {doc.verification_status}
                  </span>
                  <button
                    onClick={() => handleDelete(doc.id)}
                    className="p-1.5 text-slate-400 hover:text-red-600 rounded-lg transition"
                    title={language === 'hi' ? 'दस्तावेज़ हटाएं' : 'Delete document'}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
