import React, { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { api } from '../api/client';
import { useLanguage } from '../context/LanguageContext';
import { ApplicationDraft, ApplicationTimelineResponse } from '../types';
import {
  Clock,
  RefreshCw,
  ExternalLink,
  CheckCircle2,
  Hash,
  Loader2,
  Calendar,
  Check,
} from 'lucide-react';

const PROGRESS_STEPS = [
  { key: 'DRAFT', labelEn: 'Drafted', labelHi: 'ड्राफ्ट' },
  { key: 'SUBMITTED', labelEn: 'Submitted', labelHi: 'जमा किया गया' },
  { key: 'IN_REVIEW', labelEn: 'In Review', labelHi: 'समीक्षाधीन' },
  { key: 'APPROVED', labelEn: 'Approved', labelHi: 'स्वीकृत' },
  { key: 'DISBURSED', labelEn: 'Disbursed', labelHi: 'वितरित' },
];

export const TrackingView: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const urlAppId = searchParams.get('application_id') || '';
  const { t, language } = useLanguage();

  const [applications, setApplications] = useState<ApplicationDraft[]>([]);
  const [selectedAppId, setSelectedAppId] = useState<string>(urlAppId);
  const [timeline, setTimeline] = useState<ApplicationTimelineResponse | null>(null);

  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Manual transition state
  const [manualStatus, setManualStatus] = useState<string>('IN_REVIEW');
  const [manualNotes, setManualNotes] = useState<string>('');
  const [updatingStatus, setUpdatingStatus] = useState(false);

  useEffect(() => {
    loadApplications();
  }, []);

  useEffect(() => {
    if (selectedAppId) {
      loadTimeline(selectedAppId);
      setSearchParams({ application_id: selectedAppId });
    } else {
      setTimeline(null);
    }
  }, [selectedAppId]);

  const loadApplications = async () => {
    try {
      const res = await api.applications.list();
      setApplications(res.items);
      if (!selectedAppId && res.items.length > 0) {
        setSelectedAppId(res.items[0].id);
      }
    } catch {
      // Non-blocking
    }
  };

  const loadTimeline = async (appId: string) => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.tracking.getTimeline(appId);
      setTimeline(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load timeline');
    } finally {
      setLoading(false);
    }
  };

  const handleSyncPortal = async () => {
    if (!selectedAppId) return;
    try {
      setSyncing(true);
      setError(null);
      const updated = await api.tracking.syncStatus(selectedAppId);
      setTimeline(updated);
      await loadApplications();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to sync with official portal');
    } finally {
      setSyncing(false);
    }
  };

  const handleManualStatusUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAppId) return;

    try {
      setUpdatingStatus(true);
      const updated = await api.tracking.updateStatus(
        selectedAppId,
        manualStatus,
        manualNotes.trim() || undefined
      );
      setTimeline(updated);
      setManualNotes('');
      await loadApplications();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to record status update');
    } finally {
      setUpdatingStatus(false);
    }
  };

  const getStepIndex = (currentStatus: string): number => {
    const s = currentStatus.toUpperCase();
    if (s === 'REJECTED') return -1;
    const idx = PROGRESS_STEPS.findIndex((step) => step.key === s);
    if (idx >= 0) return idx;
    if (s === 'READY') return 0;
    return 0;
  };

  const currentStepIdx = timeline ? getStepIndex(timeline.current_status) : 0;
  const isRejected = timeline?.current_status.toUpperCase() === 'REJECTED';

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 pb-24 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900">{t('tracking.title')}</h1>
        <p className="text-slate-500 text-sm mt-1">
          {language === 'hi'
            ? 'आधिकारिक विभागीय स्थिति और समय-सीमा का सत्यापन करें'
            : 'Track official departmental lifecycle events and verify state transitions'}
        </p>
      </div>

      {/* Application Selector */}
      <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
        <label className="block text-xs font-semibold text-slate-700 mb-1">
          {language === 'hi' ? 'आवेदन चुनें' : 'Select Tracked Application'}
        </label>
        {applications.length === 0 ? (
          <p className="text-xs text-slate-500 py-2">
            {language === 'hi' ? 'कोई आवेदन उपलब्ध नहीं है।' : 'No applications available.'}{' '}
            <Link to="/schemes" className="text-emerald-600 font-semibold underline">
              {language === 'hi' ? 'योजनाएं देखें' : 'Browse schemes'}
            </Link>
          </p>
        ) : (
          <select
            value={selectedAppId}
            onChange={(e) => setSelectedAppId(e.target.value)}
            className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2.5 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          >
            {applications.map((app) => (
              <option key={app.id} value={app.id}>
                {app.scheme_name} — {app.target_name} ({app.status})
                {app.external_reference_number ? ` [${app.external_reference_number}]` : ''}
              </option>
            ))}
          </select>
        )}
      </div>

      {loading ? (
        <div className="py-20 flex justify-center">
          <Loader2 className="w-8 h-8 text-emerald-600 animate-spin" />
        </div>
      ) : error ? (
        <div className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm">
          {error}
        </div>
      ) : timeline ? (
        <>
          {/* Status Header Card */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <div className="flex items-center space-x-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                    {timeline.scheme_code || 'SCHEME'}
                  </span>
                  <span className="text-xs text-slate-500">•</span>
                  <span className="text-xs text-slate-600 font-medium">
                    {language === 'hi' ? 'आवेदक: ' : 'Applicant: '}
                    <strong className="text-slate-800">{timeline.target_name}</strong>
                  </span>
                </div>
                <h2 className="text-xl font-extrabold text-slate-900 mt-1">
                  {timeline.scheme_name}
                </h2>
              </div>

              <div className="flex items-center space-x-2">
                <button
                  onClick={handleSyncPortal}
                  disabled={syncing}
                  className="inline-flex items-center px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold shadow-sm transition disabled:opacity-50"
                >
                  <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${syncing ? 'animate-spin' : ''}`} />
                  {t('tracking.btn_sync')}
                </button>
                <a
                  href={timeline.official_portal_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-2 border border-slate-200 text-slate-600 hover:text-slate-900 rounded-xl transition"
                  title={t('schemes.official_portal')}
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              </div>
            </div>

            {/* External reference row */}
            {timeline.external_reference_number && (
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between text-xs">
                <div className="flex items-center space-x-2">
                  <Hash className="w-4 h-4 text-emerald-600" />
                  <span className="font-semibold text-slate-700">
                    {language === 'hi' ? 'स्वीकृति संदर्भ संख्या:' : 'Official Reference / Ack ID:'}
                  </span>
                  <span className="font-mono font-bold text-slate-900">
                    {timeline.external_reference_number}
                  </span>
                </div>
                {timeline.submitted_at && (
                  <span className="text-slate-500">
                    {new Date(timeline.submitted_at).toLocaleDateString()}
                  </span>
                )}
              </div>
            )}

            {/* Horizontal Progress Bar */}
            <div className="pt-4 pb-2">
              {isRejected ? (
                <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-center text-red-800 font-bold text-sm">
                  {language === 'hi' ? 'आवेदन अस्वीकृत (Rejected)' : 'Application Rejected'}
                </div>
              ) : (
                <div className="relative">
                  {/* Progress Line */}
                  <div className="absolute top-4 left-6 right-6 h-0.5 bg-slate-200 -z-0" />
                  <div
                    className="absolute top-4 left-6 h-0.5 bg-emerald-600 -z-0 transition-all duration-500"
                    style={{
                      width: `${(currentStepIdx / (PROGRESS_STEPS.length - 1)) * 88}%`,
                    }}
                  />

                  {/* Step Circles */}
                  <div className="relative z-10 flex justify-between">
                    {PROGRESS_STEPS.map((step, idx) => {
                      const isCompleted = idx < currentStepIdx;
                      const isCurrent = idx === currentStepIdx;

                      return (
                        <div key={step.key} className="flex flex-col items-center">
                          <div
                            className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs transition ${
                              isCompleted
                                ? 'bg-emerald-600 text-white'
                                : isCurrent
                                ? 'bg-emerald-500 text-white ring-4 ring-emerald-100'
                                : 'bg-slate-200 text-slate-500'
                            }`}
                          >
                            {isCompleted ? <Check className="w-4 h-4" /> : idx + 1}
                          </div>
                          <span
                            className={`text-[11px] font-semibold mt-1.5 whitespace-nowrap ${
                              isCurrent
                                ? 'text-emerald-800 font-bold'
                                : isCompleted
                                ? 'text-slate-800'
                                : 'text-slate-400'
                            }`}
                          >
                            {language === 'hi' ? step.labelHi : step.labelEn}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Audit Trail Timeline */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
            <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center">
              <Clock className="w-5 h-5 mr-2 text-emerald-600" />
              {t('tracking.timeline')}
            </h3>

            <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
              {timeline.history.map((event, idx) => (
                <div key={event.id || idx} className="relative group">
                  <div className="absolute -left-6 top-1 w-3 h-3 rounded-full bg-emerald-600 ring-4 ring-white" />
                  <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold uppercase tracking-wide px-2 py-0.5 rounded bg-emerald-100 text-emerald-800">
                        {event.status}
                      </span>
                      <span className="text-[11px] text-slate-500 flex items-center">
                        <Calendar className="w-3 h-3 mr-1 text-slate-400" />
                        {new Date(event.created_at).toLocaleString()}
                      </span>
                    </div>

                    <div className="text-xs text-slate-600 font-medium pt-1">
                      <span className="font-semibold text-slate-800">
                        {language === 'hi' ? 'स्रोत: ' : 'Source: '}
                      </span>
                      {event.source_type.replace(/_/g, ' ')}
                      {event.source_reference && ` (${event.source_reference})`}
                    </div>

                    {event.notes && (
                      <p className="text-xs text-slate-700 bg-white p-2 rounded border border-slate-100 mt-1">
                        {event.notes}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Manual Status Transition Form (For Testing / Citizen update) */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
            <h3 className="text-sm font-bold text-slate-900 mb-2">
              {language === 'hi' ? 'विभागीय स्थिति अद्यतन दर्ज करें' : 'Record Official Departmental Status Update'}
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              {language === 'hi'
                ? 'यदि आपको एसएमएस या ईमेल द्वारा नया स्थिति अपडेट प्राप्त हुआ है, तो इसे यहाँ रिकॉर्ड करें।'
                : 'If you received an SMS or departmental letter updating your status, log the verification event here.'}
            </p>

            <form onSubmit={handleManualStatusUpdate} className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    {language === 'hi' ? 'नई स्थिति' : 'New Status'}
                  </label>
                  <select
                    value={manualStatus}
                    onChange={(e) => setManualStatus(e.target.value)}
                    className="w-full text-xs bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500 font-medium"
                  >
                    <option value="SUBMITTED">SUBMITTED</option>
                    <option value="IN_REVIEW">IN_REVIEW</option>
                    <option value="APPROVED">APPROVED</option>
                    <option value="DISBURSED">DISBURSED</option>
                    <option value="REJECTED">REJECTED</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    {language === 'hi' ? 'टिप्पणी / संदर्भ' : 'Notes / Official Reference'}
                  </label>
                  <input
                    type="text"
                    value={manualNotes}
                    onChange={(e) => setManualNotes(e.target.value)}
                    placeholder={
                      language === 'hi'
                        ? 'उदा. एसएमएस से सूचना प्राप्त...'
                        : 'e.g. Field verification completed...'
                    }
                    className="w-full text-xs bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
              </div>

              <div className="flex justify-end pt-1">
                <button
                  type="submit"
                  disabled={updatingStatus}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-900 text-white rounded-xl text-xs font-semibold transition disabled:opacity-50 flex items-center"
                >
                  {updatingStatus ? (
                    <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                  ) : (
                    <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
                  )}
                  {language === 'hi' ? 'स्थिति अद्यतन करें' : 'Update Status'}
                </button>
              </div>
            </form>
          </div>
        </>
      ) : null}
    </div>
  );
};
