import React, { useEffect, useState, useRef } from 'react';
import { documentService } from '@/services/api/documentService';
import { UserDocument } from '@/types';
import { useLanguage } from '@/context/LanguageContext';
import { Card, CardHeader, CardContent } from '@/components/common/Card';
import { Button } from '@/components/common/Button';
import { Spinner } from '@/components/common/Spinner';
import { StatusBanner } from '@/components/common/StatusBanner';
import { Upload, FileCheck, CheckCircle2, FileText, ShieldCheck, ArrowUpRight } from 'lucide-react';

export const DocumentsPage: React.FC = () => {
  const { t, language } = useLanguage();
  const [documents, setDocuments] = useState<UserDocument[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [uploading, setUploading] = useState<boolean>(false);
  const [selectedType, setSelectedType] = useState<string>('income_certificate');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const documentTypes = [
    { value: 'income_certificate', label: language === 'hi' ? 'आय प्रमाण पत्र (Income Certificate)' : 'Income Certificate' },
    { value: 'aadhaar_card', label: language === 'hi' ? 'आधार कार्ड (Aadhaar Card)' : 'Aadhaar Card' },
    { value: 'land_records', label: language === 'hi' ? 'भूमि अभिलेख / खतौनी (Land Records)' : 'Land Ownership Records (Khasra)' },
    { value: 'caste_certificate', label: language === 'hi' ? 'जाति प्रमाण पत्र (Caste Certificate)' : 'Caste Certificate' },
    { value: 'ration_card', label: language === 'hi' ? 'राशन कार्ड (Ration Card)' : 'Ration Card' },
    { value: 'bank_passbook', label: language === 'hi' ? 'बैंक पासबुक (Bank Passbook)' : 'Bank Passbook / Account' },
  ];

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
    fetchDocs();
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      const newDoc = await documentService.uploadDocument(selectedType, file);
      setDocuments((prev) => [newDoc, ...prev]);
    } catch (err) {
      console.error('Upload failed:', err);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  return (
    <div className="space-y-7 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div className="space-y-1">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-sage-light text-sage-dark text-xs font-semibold border border-sage/30">
            <ShieldCheck className="w-3.5 h-3.5 text-sage-green" />
            <span>{language === 'hi' ? 'सुरक्षित नागरिक वॉल्ट' : 'Encrypted Citizen Vault'}</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold font-editorial text-navy tracking-tight">
            {language === 'hi' ? 'दस्तावेज़ सहायक व वॉल्ट' : 'Document Assistant & Vault'}
          </h1>
          <p className="text-xs sm:text-sm text-navy/60 max-w-xl leading-relaxed">
            {language === 'hi'
              ? 'योजनाओं के लिए आवश्यक प्रमाणपत्र व पहचान पत्र सुरक्षित रूप से अपलोड व प्रबंधित करें।'
              : 'Upload and organize verified certificates to accelerate your scheme application drafting.'}
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

      {/* Privacy Guarantee Notice */}
      <StatusBanner
        type="info"
        title="Privacy & Verification Assurance"
        message={
          language === 'hi'
            ? 'अपलोड किए गए दस्तावेज़ केवल पात्रता और आवेदन सत्यापन के लिए उपयोग किए जाते हैं। OCR प्रक्रिया केवल आवश्यक डेटा पढ़ने के लिए है, इसे अंतिम सरकारी सत्यापन न समझें।'
            : 'Uploaded documents are securely processed to extract baseline attributes for deterministic eligibility evaluation. OCR extraction does not constitute final official government verification.'
        }
      />

      {/* Document Upload Selector Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <h3 className="font-bold font-editorial text-navy text-base">
              {language === 'hi' ? 'नया दस्तावेज़ अपलोड करें' : 'Select Document Category to Upload'}
            </h3>
            <span className="text-xs text-navy/50">PDF, PNG, JPG (max 10MB)</span>
          </div>
        </CardHeader>
        <CardContent className="p-6 space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
            {documentTypes.map((type) => {
              const isSelected = selectedType === type.value;
              return (
                <button
                  key={type.value}
                  type="button"
                  onClick={() => setSelectedType(type.value)}
                  className={`p-3 rounded-xl border text-xs font-semibold text-left transition-all duration-200 ${
                    isSelected
                      ? 'bg-navy text-white border-navy shadow-subtle'
                      : 'bg-ivory-100 text-navy/70 border-navy/10 hover:border-navy/25 hover:text-navy'
                  }`}
                >
                  {type.label}
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
              {language === 'hi' ? 'दस्तावेज़ फ़ाइल अपलोड करने के लिए क्लिक करें' : 'Click to select and upload document'}
            </p>
            <p className="text-xs text-navy/50 mt-1">
              Supports Aadhaar, Income Proof, Caste Certificate, Land Records (PDF/JPEG)
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Uploaded Documents List (Visual Match to Blueprint Documents Checklist) */}
      <Card>
        <CardHeader className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-ivory-100 flex items-center justify-center text-navy border border-navy/8">
              <FileCheck className="w-4 h-4 text-sage-green" />
            </div>
            <div>
              <h3 className="font-bold font-editorial text-navy text-base">
                {language === 'hi' ? 'सत्यापित दस्तावेज़ सूची' : 'Stored Documents in Vault'}
              </h3>
              <p className="text-xs text-navy/50">
                {documents.length} verified documents ready for scheme attachments
              </p>
            </div>
          </div>
          <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-sage-light text-sage-dark border border-sage/30">
            {documents.length} Available
          </span>
        </CardHeader>

        <CardContent className="p-6">
          {loading ? (
            <Spinner size="md" label="दस्तावेज़ सूची लोड हो रही है..." />
          ) : documents.length === 0 ? (
            <div className="text-center py-8 text-navy/60 text-sm">
              {language === 'hi' ? 'अभी कोई दस्तावेज़ अपलोड नहीं किया गया है।' : 'No documents uploaded yet.'}
            </div>
          ) : (
            <div className="space-y-3">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-2xl border border-navy/8 bg-white hover:border-navy/20 hover:shadow-subtle transition-all duration-200"
                >
                  <div className="flex items-start gap-3.5">
                    <div className="w-10 h-10 rounded-xl bg-ivory-100 flex items-center justify-center text-navy shrink-0 border border-navy/8 mt-0.5">
                      <FileText className="w-5 h-5 text-navy/70" />
                    </div>
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <h4 className="font-bold text-sm text-navy capitalize">
                          {doc.document_type.replace(/_/g, ' ')}
                        </h4>
                        <span className="text-[10px] font-semibold text-sage-green bg-sage-light px-2 py-0.5 rounded-full flex items-center gap-1 border border-sage/30">
                          <CheckCircle2 className="w-3 h-3" />
                          Verified
                        </span>
                      </div>
                      <p className="text-xs text-navy/50">
                        Doc Ref: {doc.id} • Review: {doc.review_status || 'verified'} • Uploaded {new Date(doc.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2.5 self-end sm:self-center">
                    <span className="text-xs font-medium text-navy/60">
                      OCR Status: <strong className="text-sage-green">Ready</strong>
                    </span>
                    <Button variant="outline" size="sm" rightIcon={<ArrowUpRight className="w-3 h-3" />}>
                      View
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
