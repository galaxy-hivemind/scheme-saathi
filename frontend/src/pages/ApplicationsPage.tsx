import React, { useEffect, useState } from 'react';
import { applicationService } from '@/services/api/applicationService';
import { ApplicationDraft } from '@/types';
import { useLanguage } from '@/context/LanguageContext';
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
} from 'lucide-react';
import { Link } from 'react-router-dom';

export const ApplicationsPage: React.FC = () => {
  const { language } = useLanguage();
  const [applications, setApplications] = useState<ApplicationDraft[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [confirmingApp, setConfirmingApp] = useState<ApplicationDraft | null>(null);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [successInfo, setSuccessInfo] = useState<{ id: string; ref: string } | null>(null);

  const fetchApps = async () => {
    setLoading(true);
    try {
      const data = await applicationService.getApplications();
      setApplications(data);
    } catch (err) {
      console.error('Failed to load applications:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApps();
  }, []);

  const handleConfirmAndSubmit = async () => {
    if (!confirmingApp) return;
    setSubmitting(true);
    try {
      await applicationService.confirmApplication(confirmingApp.id);
      const res = await applicationService.submitApplication(confirmingApp.id);
      setSuccessInfo({ id: confirmingApp.id, ref: res.reference_number || 'SAATHI-SUBMITTED' });
      setConfirmingApp(null);
      await fetchApps();
    } catch (err) {
      console.error('Submission failed:', err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-7 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div className="space-y-1">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-saffron-light text-saffron-dark text-xs font-semibold border border-saffron/30">
            <FolderKanban className="w-3.5 h-3.5 text-saffron-vibrant" />
            <span>{language === 'hi' ? 'आवेदन ड्राफ्ट व ट्रैकिंग' : 'Application Tracking'}</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold font-editorial text-navy tracking-tight">
            {language === 'hi' ? 'आवेदन एवं ट्रैकिंग' : 'Applications & Tracking'}
          </h1>
          <p className="text-xs sm:text-sm text-navy/60 max-w-xl leading-relaxed">
            {language === 'hi'
              ? 'तैयार किए गए ड्राफ्ट, सत्यापन स्थिति और आधिकारिक प्रस्तुतीकरण।'
              : 'Review your application drafts, validate form details, and track submitted requests.'}
          </p>
        </div>

        <Link to="/schemes">
          <Button variant="saffron" size="md">
            {language === 'hi' ? '+ नया आवेदन शुरू करें' : '+ Start New Application'}
          </Button>
        </Link>
      </div>

      {/* Safety Policy Notice */}
      <StatusBanner
        type="demo"
        title="Citizen Explicit Consent & Safety Policy"
        message={
          language === 'hi'
            ? 'योजना साथी कभी भी नागरिक की स्पष्ट सहमति के बिना कोई आवेदन जमा नहीं करता है। किसी भी प्रस्तुतीकरण से पूर्व पूर्ण पूर्वावलोकन और आपकी पुष्टि अनिवार्य है।'
            : 'Applications are NEVER submitted silently. Every draft requires explicit user confirmation and preview before submission or official portal handoff.'
        }
      />

      {successInfo && (
        <StatusBanner
          type="success"
          title="Application Submitted Successfully"
          message={`Application reference number: ${successInfo.ref}. You can track updates in real-time below.`}
          action={
            <Button size="sm" variant="outline" onClick={() => setSuccessInfo(null)}>
              Dismiss
            </Button>
          }
        />
      )}

      {/* Applications List */}
      {loading ? (
        <Spinner size="lg" label="आवेदन लोड हो रहे हैं..." />
      ) : applications.length === 0 ? (
        <EmptyState
          title={language === 'hi' ? 'कोई सक्रिय आवेदन नहीं है' : 'No Active Applications'}
          description={
            language === 'hi'
              ? 'आपने अभी तक कोई आवेदन तैयार नहीं किया है। अपनी पात्रता जांचें और आवेदन प्रारंभ करें।'
              : 'You have not drafted any scheme applications yet. Browse schemes to get started.'
          }
          actionLabel={language === 'hi' ? 'योजनाएं खोजें' : 'Browse Schemes'}
          onAction={() => (window.location.href = '/schemes')}
        />
      ) : (
        <div className="space-y-4">
          {applications.map((app) => (
            <Card key={app.id} hoverable className="overflow-hidden">
              <CardContent className="p-6 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-navy/6">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-2xl bg-ivory-100 flex items-center justify-center text-navy shrink-0 border border-navy/8">
                      <FileText className="w-5 h-5 text-navy/70" />
                    </div>
                    <div>
                      <h3 className="font-bold font-editorial text-navy text-lg">
                        {app.scheme_name || `Application: ${app.scheme_id}`}
                      </h3>
                      <p className="text-xs text-navy/50">
                        Draft ID: {app.id} • Created {new Date(app.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <Badge variant={app.lifecycle_state}>{app.lifecycle_state.toUpperCase()}</Badge>
                  </div>
                </div>

                {/* Form Data Snapshot */}
                <div className="p-4 rounded-2xl bg-ivory-50/70 border border-navy/6 text-xs space-y-2">
                  <span className="font-bold text-navy/50 uppercase tracking-wider text-[10px] block">
                    Form Data Payload Snapshot
                  </span>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    {Object.entries(app.form_data || {}).map(([key, val]) => (
                      <div key={key} className="space-y-0.5">
                        <span className="text-navy/50 capitalize text-[11px] block">{key.replace(/_/g, ' ')}:</span>
                        <span className="font-semibold text-navy truncate block">{String(val)}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Application Actions */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2">
                  <div className="flex items-center gap-2 text-xs text-navy/60">
                    <Clock className="w-4 h-4 text-navy/40" />
                    <span>Last modified: {new Date(app.updated_at).toLocaleDateString()}</span>
                  </div>

                  <div className="flex items-center gap-3">
                    {app.lifecycle_state === 'awaiting_confirmation' && (
                      <Button
                        variant="saffron"
                        size="sm"
                        leftIcon={<CheckCircle2 className="w-4 h-4" />}
                        onClick={() => setConfirmingApp(app)}
                      >
                        {language === 'hi' ? 'समीक्षा व अंतिम पुष्टि करें' : 'Review & Confirm Submission'}
                      </Button>
                    )}

                    {app.lifecycle_state === 'submitted' && (
                      <span className="text-xs font-semibold text-sage-green bg-sage-light px-3 py-1.5 rounded-full border border-sage/30 flex items-center gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Submitted & Reference Generated
                      </span>
                    )}

                    <Link to={`/schemes/${app.scheme_id}`}>
                      <Button variant="outline" size="sm">
                        Scheme Details
                      </Button>
                    </Link>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Confirmation & Final Submission Modal */}
      {confirmingApp && (
        <Modal
          isOpen={!!confirmingApp}
          onClose={() => setConfirmingApp(null)}
          title={
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-saffron" />
              <span>{language === 'hi' ? 'नागरिक अंतिम पुष्टि' : 'Explicit Citizen Confirmation'}</span>
            </div>
          }
          footer={
            <>
              <Button variant="outline" size="sm" onClick={() => setConfirmingApp(null)}>
                {language === 'hi' ? 'रद्द करें' : 'Cancel'}
              </Button>
              <Button
                variant="saffron"
                size="sm"
                leftIcon={<Send className="w-4 h-4" />}
                onClick={handleConfirmAndSubmit}
                isLoading={submitting}
              >
                {language === 'hi' ? 'सहमति है - आवेदन जमा करें' : 'I Confirm - Submit Application'}
              </Button>
            </>
          }
        >
          <div className="space-y-4 text-sm text-navy">
            <p className="leading-relaxed text-xs sm:text-sm text-navy/80">
              {language === 'hi'
                ? `आप ${confirmingApp.scheme_name || confirmingApp.scheme_id} के लिए अपना आवेदन जमा करने जा रहे हैं। कृपया पुष्टि करें कि प्रस्तुत सभी विवरण सत्य और सटीक हैं।`
                : `You are about to submit an application for ${confirmingApp.scheme_name || confirmingApp.scheme_id}. Please review and confirm your consent below.`}
            </p>

            <div className="p-4 rounded-2xl bg-ivory-100 border border-navy/8 space-y-2 text-xs">
              <span className="font-bold text-navy">Pre-Submission Verification:</span>
              <ul className="space-y-1.5 text-navy/70">
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-sage-green shrink-0" />
                  <span>Applicant baseline identity and eligibility conditions validated</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-sage-green shrink-0" />
                  <span>Mandatory certificate copies attached from citizen vault</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-sage-green shrink-0" />
                  <span>Direct submission to official API integration endpoint</span>
                </li>
              </ul>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
