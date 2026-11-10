import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { useLanguage } from '@/context/LanguageContext';
import { applicationService } from '@/services/api/applicationService';
import { notificationService } from '@/services/api/notificationService';
import { ApplicationDraft, Notification } from '@/types';
import { Card, CardContent } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Spinner } from '@/components/common/Spinner';
import {
  Sparkles,
  FolderKanban,
  FileCheck,
  Bell,
  ArrowRight,
  UserCheck,
  Clock,
  CheckCircle2,
  FileText,
} from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const { profile } = useAuth();
  const { t, language } = useLanguage();

  const [applications, setApplications] = useState<ApplicationDraft[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const [apps, notifs] = await Promise.all([
          applicationService.getApplications(),
          notificationService.getNotifications(),
        ]);
        setApplications(apps);
        setNotifications(notifs);
      } catch (err) {
        console.error('Failed to load dashboard:', err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) {
    return <Spinner size="lg" label={language === 'hi' ? 'डैशबोर्ड लोड हो रहा है...' : 'Loading citizen dashboard...'} />;
  }

  const awaitingCount = applications.filter((a) => a.lifecycle_state === 'awaiting_confirmation').length;
  const submittedCount = applications.filter((a) => a.lifecycle_state === 'submitted').length;

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Welcome Banner */}
      <div className="bg-white rounded-3xl border border-navy/8 p-6 sm:p-9 flex flex-col md:flex-row md:items-center justify-between gap-6 shadow-subtle relative overflow-hidden">
        {/* Subtle decorative background watermark */}
        <div className="absolute right-0 top-0 bottom-0 w-1/3 bg-linear-to-l from-ivory-100/50 to-transparent pointer-events-none rounded-r-3xl" />

        <div className="space-y-2.5 z-10">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-sage-light text-sage-dark text-xs font-semibold border border-sage/30">
            <UserCheck className="w-3.5 h-3.5" />
            <span>{language === 'hi' ? 'नागरिक खाता सक्रिय' : 'Citizen Account Active'}</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold font-editorial text-navy tracking-tight">
            {language === 'hi' ? `नमस्ते, ${profile?.full_name || 'नागरिक'}` : `Welcome, ${profile?.full_name || 'Citizen'}`}
          </h1>
          <p className="text-xs sm:text-sm text-navy/60 max-w-xl leading-relaxed">
            {language === 'hi'
              ? `${profile?.district || 'वाराणसी'}, ${profile?.state || 'उत्तर प्रदेश'} • व्यवसाय: ${profile?.occupation || 'किसान'} • आय: ₹${(profile?.annual_family_income || 120000).toLocaleString('en-IN')}`
              : `${profile?.district || 'Varanasi'}, ${profile?.state || 'Uttar Pradesh'} • Occupation: ${profile?.occupation || 'Farmer'} • Income: ₹${(profile?.annual_family_income || 120000).toLocaleString('en-IN')}`}
          </p>
        </div>

        <div className="flex items-center gap-3 z-10 shrink-0">
          <Link to="/chat">
            <Button variant="saffron" size="md" leftIcon={<Sparkles className="w-4 h-4" />}>
              {t.actions.startChat}
            </Button>
          </Link>
          <Link to="/onboarding">
            <Button variant="outline" size="md">
              {t.actions.editProfile}
            </Button>
          </Link>
        </div>
      </div>

      {/* Summary KPI Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1 */}
        <div className="bg-white p-5 rounded-2xl border border-navy/8 shadow-subtle hover:shadow-premium hover:-translate-y-0.5 transition-all duration-200">
          <div className="flex items-center justify-between text-navy/60 mb-2">
            <span className="text-xs font-semibold tracking-wide uppercase">{language === 'hi' ? 'कुल आवेदन' : 'Applications'}</span>
            <div className="w-8 h-8 rounded-xl bg-ivory-100 flex items-center justify-center text-navy">
              <FolderKanban className="w-4 h-4" />
            </div>
          </div>
          <p className="text-3xl font-bold font-editorial text-navy">{applications.length}</p>
          <span className="text-[11px] text-navy/50">Drafted & submitted</span>
        </div>

        {/* Card 2 */}
        <div className="bg-white p-5 rounded-2xl border border-navy/8 shadow-subtle hover:shadow-premium hover:-translate-y-0.5 transition-all duration-200">
          <div className="flex items-center justify-between text-navy/60 mb-2">
            <span className="text-xs font-semibold tracking-wide uppercase">{language === 'hi' ? 'पुष्टि प्रतीक्षित' : 'Awaiting Review'}</span>
            <div className="w-8 h-8 rounded-xl bg-saffron-light flex items-center justify-center text-saffron-vibrant">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <p className="text-3xl font-bold font-editorial text-saffron-vibrant">{awaitingCount}</p>
          <span className="text-[11px] text-navy/50">Requires confirmation</span>
        </div>

        {/* Card 3 */}
        <div className="bg-white p-5 rounded-2xl border border-navy/8 shadow-subtle hover:shadow-premium hover:-translate-y-0.5 transition-all duration-200">
          <div className="flex items-center justify-between text-navy/60 mb-2">
            <span className="text-xs font-semibold tracking-wide uppercase">{language === 'hi' ? 'स्वीकृत/जमा' : 'Submitted'}</span>
            <div className="w-8 h-8 rounded-xl bg-sage-light flex items-center justify-center text-sage-green">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <p className="text-3xl font-bold font-editorial text-sage-green">{submittedCount}</p>
          <span className="text-[11px] text-navy/50">Processed requests</span>
        </div>

        {/* Card 4 */}
        <div className="bg-white p-5 rounded-2xl border border-navy/8 shadow-subtle hover:shadow-premium hover:-translate-y-0.5 transition-all duration-200">
          <div className="flex items-center justify-between text-navy/60 mb-2">
            <span className="text-xs font-semibold tracking-wide uppercase">{language === 'hi' ? 'दस्तावेज़' : 'Documents'}</span>
            <div className="w-8 h-8 rounded-xl bg-navy/5 flex items-center justify-center text-navy">
              <FileCheck className="w-4 h-4" />
            </div>
          </div>
          <p className="text-3xl font-bold font-editorial text-navy">2</p>
          <span className="text-[11px] text-navy/50">Verified in vault</span>
        </div>
      </div>

      {/* Applications & Notifications Split View */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Active Applications */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-bold font-editorial text-navy text-xl">
              {language === 'hi' ? 'हाल के आवेदन' : 'Recent Applications'}
            </h2>
            <Link to="/applications" className="text-xs font-semibold text-saffron-dark hover:text-saffron flex items-center gap-1 group">
              <span>{language === 'hi' ? 'सभी देखें' : 'View all'}</span>
              <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
            </Link>
          </div>

          <div className="space-y-3">
            {applications.map((app) => (
              <Card key={app.id} hoverable>
                <CardContent className="p-4 sm:p-5 flex items-center justify-between gap-4">
                  <div className="flex items-start gap-3.5">
                    <div className="w-10 h-10 rounded-xl bg-ivory-100 flex items-center justify-center text-navy shrink-0 mt-0.5">
                      <FileText className="w-5 h-5 text-navy/70" />
                    </div>
                    <div className="space-y-1">
                      <h3 className="font-bold text-navy text-sm leading-snug">
                        {app.scheme_name || `Application: ${app.scheme_id}`}
                      </h3>
                      <p className="text-xs text-navy/50">
                        {language === 'hi' ? 'अंतिम अद्यतन' : 'Last updated'}: {new Date(app.updated_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2.5 shrink-0">
                    <Badge variant={app.lifecycle_state}>{app.lifecycle_state.toUpperCase()}</Badge>
                    <Link to="/applications">
                      <Button variant="outline" size="sm">
                        {language === 'hi' ? 'खोलें' : 'Open'}
                      </Button>
                    </Link>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Notifications Column */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-bold font-editorial text-navy text-xl flex items-center gap-2">
              <Bell className="w-4 h-4 text-saffron-vibrant" />
              <span>{language === 'hi' ? 'नवीनतम सूचनाएं' : 'Updates'}</span>
            </h2>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-navy/5 text-navy/60">
              {notifications.length}
            </span>
          </div>

          <div className="space-y-3">
            {notifications.map((n) => (
              <div
                key={n.id}
                className={`p-4 rounded-2xl border text-xs space-y-1.5 transition-all duration-200 ${
                  n.read_at
                    ? 'bg-white border-navy/8 shadow-subtle'
                    : 'bg-saffron-50/70 border-saffron/30 shadow-subtle'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <h4 className="font-bold text-navy line-clamp-1">{n.title}</h4>
                  <span className="text-[10px] text-navy/40 shrink-0 font-medium">
                    {new Date(n.created_at).toLocaleDateString()}
                  </span>
                </div>
                <p className="text-navy/70 leading-relaxed">{n.message}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
