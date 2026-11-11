import React, { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { api } from '../api/client';
import { useLanguage } from '../context/LanguageContext';
import { ApplicationDraft } from '../types';
import {
  FileText,
  ExternalLink,
  CheckCircle2,
  Clock,
  Send,
  Trash2,
  Loader2,
  AlertCircle,
  User,
  Hash,
  ChevronRight,
} from 'lucide-react';

export const ApplicationsView: React.FC = () => {
  const [searchParams] = useSearchParams();
  const highlightedId = searchParams.get('id');
  const { t, language } = useLanguage();

  const [applications, setApplications] = useState<ApplicationDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter state
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  // Submit modal state
  const [submittingApp, setSubmittingApp] = useState<ApplicationDraft | null>(null);
  const [refNumber, setRefNumber] = useState('');
  const [submitNotes, setSubmitNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    loadApplications();
  }, []);

  const loadApplications = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.applications.list();
      setApplications(res.items);
    } catch (err: any) {
      if (!navigator.onLine) {
        setApplications([]);
      } else {
        setError(err?.response?.data?.message || 'Failed to load applications');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitPortalAck = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!submittingApp || !refNumber.trim()) return;

    try {
      setIsSubmitting(true);
      setSubmitError(null);
      await api.applications.submit(submittingApp.id, refNumber.trim(), submitNotes.trim() || undefined);
      setSubmittingApp(null);
      setRefNumber('');
      setSubmitNotes('');
      await loadApplications();
    } catch (err: any) {
      setSubmitError(err?.response?.data?.message || 'Failed to record portal submission');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteDraft = async (id: string) => {
    if (
      !window.confirm(
        language === 'hi'
          ? 'क्या आप इस आवेदन ड्राफ्ट को हटाना चाहते हैं?'
          : 'Are you sure you want to delete this application draft?'
      )
    ) {
      return;
    }

    try {
      await api.applications.delete(id);
      await loadApplications();
    } catch {
      // Error handling
    }
  };

  const filteredApps = applications.filter((app) => {
    if (statusFilter === 'ALL') return true;
    if (statusFilter === 'DRAFT') return app.status === 'DRAFT' || app.status === 'READY';
    return app.status === statusFilter;
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'DRAFT':
        return {
          label: t('apps.status_draft'),
          bg: 'bg-slate-100 text-slate-700 border-slate-200',
        };
      case 'READY':
        return {
          label: t('apps.status_ready'),
          bg: 'bg-emerald-100 text-emerald-800 border-emerald-300',
        };
      case 'SUBMITTED':
        return {
          label: t('apps.status_submitted'),
          bg: 'bg-blue-100 text-blue-800 border-blue-300',
        };
      case 'IN_REVIEW':
        return {
          label: t('apps.status_in_review'),
          bg: 'bg-amber-100 text-amber-800 border-amber-300',
        };
      case 'APPROVED':
        return {
          label: t('apps.status_approved'),
          bg: 'bg-green-100 text-green-800 border-green-300',
        };
      case 'DISBURSED':
        return {
          label: t('apps.status_disbursed'),
          bg: 'bg-purple-100 text-purple-800 border-purple-300',
        };
      case 'REJECTED':
        return {
          label: language === 'hi' ? 'अस्वीकृत' : 'Rejected',
          bg: 'bg-red-100 text-red-800 border-red-300',
        };
      default:
        return {
          label: status,
          bg: 'bg-slate-100 text-slate-700 border-slate-200',
        };
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 pb-24 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900">{t('apps.title')}</h1>
          <p className="text-slate-500 text-sm mt-1">
            {language === 'hi'
              ? 'योजना आवेदनों के ड्राफ्ट तैयार करें, सरकारी पोर्टल पर जमा करें और संदर्भ संख्या दर्ज करें'
              : 'Prefill application packages, hand off to official ministry portals, and track outcomes'}
          </p>
        </div>

        <Link
          to="/schemes"
          className="inline-flex items-center px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold shadow-sm transition"
        >
          {language === 'hi' ? '+ नई योजना के लिए आवेदन' : '+ Apply for New Scheme'}
        </Link>
      </div>

      {/* Filter Tabs */}
      <div className="flex overflow-x-auto space-x-2 pb-1 text-xs font-semibold">
        {[
          { key: 'ALL', labelEn: 'All Applications', labelHi: 'सभी आवेदन' },
          { key: 'DRAFT', labelEn: 'Drafts & Ready', labelHi: 'ड्राफ्ट व तैयार' },
          { key: 'SUBMITTED', labelEn: 'Submitted', labelHi: 'जमा किए गए' },
          { key: 'IN_REVIEW', labelEn: 'In Review', labelHi: 'समीक्षाधीन' },
          { key: 'APPROVED', labelEn: 'Approved / Disbursed', labelHi: 'स्वीकृत / वितरित' },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setStatusFilter(tab.key)}
            className={`px-3.5 py-2 rounded-xl whitespace-nowrap transition ${
              statusFilter === tab.key
                ? 'bg-emerald-600 text-white shadow-sm'
                : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-50'
            }`}
          >
            {language === 'hi' ? tab.labelHi : tab.labelEn}
          </button>
        ))}
      </div>

      {/* Applications List */}
      {loading ? (
        <div className="py-20 flex justify-center">
          <Loader2 className="w-8 h-8 text-emerald-600 animate-spin" />
        </div>
      ) : error ? (
        <div className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm">
          {error}
        </div>
      ) : filteredApps.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center text-slate-400 shadow-sm">
          <FileText className="w-12 h-12 mx-auto mb-3 opacity-40" />
          <h3 className="text-base font-bold text-slate-800">
            {language === 'hi' ? 'कोई आवेदन नहीं मिला' : 'No applications found'}
          </h3>
          <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
            {language === 'hi'
              ? 'योजनाओं की सूची में जाएं और किसी भी पात्र योजना के लिए आवेदन ड्राफ्ट तैयार करें।'
              : 'Browse verified schemes and click "Create Application Draft" to assemble your official submission package.'}
          </p>
          <Link
            to="/schemes"
            className="mt-4 inline-flex items-center px-4 py-2 bg-emerald-600 text-white text-xs font-semibold rounded-xl hover:bg-emerald-700 transition"
          >
            {language === 'hi' ? 'योजनाएं देखें' : 'Browse Schemes'}
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredApps.map((app) => {
            const badge = getStatusBadge(app.status);
            const isHighlighted = app.id === highlightedId;

            return (
              <div
                key={app.id}
                className={`bg-white rounded-2xl border transition shadow-sm p-6 space-y-4 ${
                  isHighlighted ? 'border-emerald-500 ring-2 ring-emerald-200' : 'border-slate-200'
                }`}
              >
                {/* Header row */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-bold uppercase tracking-wider text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                        {app.scheme_code || 'SCHEME'}
                      </span>
                      <span
                        className={`text-xs font-bold px-2.5 py-0.5 rounded-full border ${badge.bg}`}
                      >
                        {badge.label}
                      </span>
                    </div>
                    <h3 className="text-lg font-bold text-slate-900 mt-1">{app.scheme_name}</h3>
                  </div>

                  <div className="text-xs text-slate-500 flex items-center space-x-1">
                    <User className="w-3.5 h-3.5 text-slate-400" />
                    <span className="font-semibold text-slate-700">{app.target_name}</span>
                  </div>
                </div>

                {/* Reference Number if present */}
                {app.external_reference_number && (
                  <div className="p-3 bg-blue-50/70 border border-blue-200 rounded-xl flex items-center justify-between text-xs">
                    <div className="flex items-center space-x-2">
                      <Hash className="w-4 h-4 text-blue-600" />
                      <span className="font-semibold text-blue-900">
                        {language === 'hi' ? 'स्वीकृति संदर्भ संख्या: ' : 'Acknowledgement ID: '}
                      </span>
                      <span className="font-mono font-bold text-blue-950">
                        {app.external_reference_number}
                      </span>
                    </div>
                    {app.submitted_at && (
                      <span className="text-slate-500">
                        {new Date(app.submitted_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                )}

                {/* Attached documents list */}
                {app.attached_documents && app.attached_documents.length > 0 && (
                  <div className="text-xs">
                    <span className="font-semibold text-slate-700">
                      {language === 'hi' ? 'संलग्न दस्तावेज़ पैकेज: ' : 'Attached Document Package: '}
                    </span>
                    <span className="text-slate-600">
                      {app.attached_documents.map((d) => d.file_name).join(', ')}
                    </span>
                  </div>
                )}

                {/* Actions row */}
                <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    {/* External portal button */}
                    <a
                      href={app.official_portal_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center px-3.5 py-2 rounded-xl border border-slate-300 text-slate-700 bg-white hover:bg-slate-50 text-xs font-semibold transition shadow-sm"
                    >
                      <span>{t('apps.btn_apply_portal')}</span>
                      <ExternalLink className="w-3.5 h-3.5 ml-1.5 text-slate-400" />
                    </a>

                    {/* Record Ack Number Modal trigger */}
                    {(app.status === 'DRAFT' || app.status === 'READY') && (
                      <button
                        onClick={() => {
                          setSubmittingApp(app);
                          setRefNumber('');
                          setSubmitNotes('');
                          setSubmitError(null);
                        }}
                        className="inline-flex items-center px-3.5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold transition shadow-sm"
                      >
                        <Send className="w-3.5 h-3.5 mr-1.5" />
                        {t('apps.btn_log_submission')}
                      </button>
                    )}

                    {/* View Tracking Timeline */}
                    <Link
                      to={`/tracking?application_id=${app.id}`}
                      className="inline-flex items-center px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold transition"
                    >
                      <Clock className="w-3.5 h-3.5 mr-1.5 text-slate-600" />
                      {language === 'hi' ? 'समय-सीमा देखें' : 'View Timeline'}
                      <ChevronRight className="w-3.5 h-3.5 ml-1" />
                    </Link>
                  </div>

                  {app.status === 'DRAFT' && (
                    <button
                      onClick={() => handleDeleteDraft(app.id)}
                      className="text-slate-400 hover:text-red-600 p-2 rounded-lg transition"
                      title={language === 'hi' ? 'ड्राफ्ट हटाएं' : 'Delete draft'}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Record Submission Modal */}
      {submittingApp && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl space-y-4">
            <h3 className="text-lg font-bold text-slate-900">{t('apps.btn_log_submission')}</h3>
            <p className="text-xs text-slate-500">
              {language === 'hi'
                ? `योजना "${submittingApp.scheme_name}" के लिए आधिकारिक सरकारी पोर्टल से प्राप्त स्वीकृति संदर्भ संख्या दर्ज करें:`
                : `Enter the official acknowledgement / application reference number received from the government portal for "${submittingApp.scheme_name}":`}
            </p>

            <form onSubmit={handleSubmitPortalAck} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  {language === 'hi' ? 'स्वीकृति संदर्भ संख्या (Acknowledgement Number)' : 'Reference / Ack Number'} *
                </label>
                <input
                  type="text"
                  required
                  placeholder={t('apps.ref_placeholder')}
                  value={refNumber}
                  onChange={(e) => setRefNumber(e.target.value)}
                  className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  {language === 'hi' ? 'टिप्पणी (वैकल्पिक)' : 'Notes / Submission Details (Optional)'}
                </label>
                <textarea
                  rows={2}
                  value={submitNotes}
                  onChange={(e) => setSubmitNotes(e.target.value)}
                  placeholder={
                    language === 'hi'
                      ? 'उदा. सीएससी केंद्र पर ऑनलाइन फॉर्म भरा गया...'
                      : 'e.g. Submitted online via CSC kiosk...'
                  }
                  className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              {submitError && (
                <div className="p-3 bg-red-50 text-red-700 rounded-xl text-xs flex items-center">
                  <AlertCircle className="w-4 h-4 mr-2 flex-shrink-0" />
                  <span>{submitError}</span>
                </div>
              )}

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setSubmittingApp(null)}
                  disabled={isSubmitting}
                  className="px-4 py-2 border border-slate-300 text-slate-700 rounded-xl text-xs font-semibold hover:bg-slate-50 transition"
                >
                  {language === 'hi' ? 'रद्द करें' : 'Cancel'}
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || !refNumber.trim()}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold transition disabled:opacity-50 flex items-center shadow-sm"
                >
                  {isSubmitting ? (
                    <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                  ) : (
                    <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
                  )}
                  {t('apps.btn_save_ref')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
