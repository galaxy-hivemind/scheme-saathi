import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { useLanguage } from '@/context/LanguageContext';
import { applicationService } from '@/services/api/applicationService';
import { notificationService } from '@/services/api/notificationService';
import { eligibilityService } from '@/services/api/eligibilityService';
import { schemeService } from '@/services/api/schemeService';
import { documentService } from '@/services/api/documentService';
import { ApplicationDraft, Notification, Scheme, EligibilityResult, isProfileComplete } from '@/types';
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
  AlertTriangle,
  Award,
} from 'lucide-react';

interface RecommendedSchemeItem {
  scheme: Scheme;
  eligibility: EligibilityResult;
}

export const DashboardPage: React.FC = () => {
  const { profile, token } = useAuth();
  const { t, language } = useLanguage();

  const [applications, setApplications] = useState<ApplicationDraft[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [recommendedSchemes, setRecommendedSchemes] = useState<RecommendedSchemeItem[]>([]);
  const [eligibleCount, setEligibleCount] = useState<number>(0);
  const [vaultDocCount, setVaultDocCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const loadDashboardData = async () => {
      setLoading(true);
      try {
        const [apps, notifs, userDocs, evalRes, allSchemes] = await Promise.all([
          applicationService.getApplications().catch(() => []),
          notificationService.getNotifications().catch(() => []),
          documentService.getUserDocuments().catch(() => []),
          eligibilityService.evaluateAll({ include_pending: true }).catch(() => ({
            total_evaluated: 0,
            eligible_count: 0,
            ineligible_count: 0,
            unknown_count: 0,
            results: [],
          })),
          schemeService.getSchemes({ limit: 50, include_pending: true }).catch(() => []),
        ]);

        setApplications(apps);
        setNotifications(notifs);
        setVaultDocCount(userDocs.length);

        const schemeMap = new Map<string, Scheme>();
        allSchemes.forEach((s) => {
          schemeMap.set(s.id, s);
          if (s.scheme_code) {
            schemeMap.set(s.scheme_code.toUpperCase(), s);
            schemeMap.set(s.scheme_code.toLowerCase(), s);
          }
        });

        const matches: RecommendedSchemeItem[] = [];
        let count = 0;

        for (const res of evalRes.results) {
          if (res.result === 'eligible' || res.result === 'potentially_eligible') {
            count++;
            const s =
              schemeMap.get(res.scheme_id) ||
              (res.scheme_code ? schemeMap.get(res.scheme_code) : undefined) ||
              (res.scheme_code ? schemeMap.get(res.scheme_code.toUpperCase()) : undefined) ||
              allSchemes.find((item) => item.scheme_code?.toLowerCase() === res.scheme_code?.toLowerCase());

            if (s) {
              matches.push({ scheme: s, eligibility: res });
            }
          }
        }

        setEligibleCount(count);
        setRecommendedSchemes(matches.slice(0, 4));
      } catch (err) {
        console.error('Failed to load dashboard data:', err);
      } finally {
        setLoading(false);
      }
    };

    loadDashboardData();
  }, [profile, token]);

  if (loading) {
    return <Spinner size="lg" label={language === 'hi' ? 'डैशबोर्ड लोड हो रहा है...' : 'Loading citizen dashboard...'} />;
  }

  const awaitingCount = applications.filter((a) => a.lifecycle_state === 'awaiting_confirmation').length;
  const profileComplete = isProfileComplete(profile);

  return (
    <div className="space-y-8 max-w-5xl mx-auto pb-12">
      {/* Welcome Banner */}
      <div className="bg-white rounded-3xl border border-navy/8 p-6 sm:p-9 flex flex-col md:flex-row md:items-center justify-between gap-6 shadow-subtle relative overflow-hidden">
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
            {profile
              ? `${profile.district || 'District'}, ${profile.state || 'State'} • ${language === 'hi' ? 'व्यवसाय' : 'Occupation'}: ${profile.occupation || 'Citizen'} • ${language === 'hi' ? 'आय' : 'Income'}: ₹${(profile.annual_family_income || 0).toLocaleString('en-IN')}`
              : 'Sign in to access personalized scheme recommendations and applications.'}
          </p>
        </div>

        <div className="flex items-center gap-3 z-10 shrink-0">
          <Link to="/eligible">
            <Button variant="saffron" size="md" leftIcon={<Sparkles className="w-4 h-4" />}>
              {language === 'hi' ? 'पात्र योजनाएं' : 'View Eligible'}
            </Button>
          </Link>
          <Link to="/onboarding">
            <Button variant="outline" size="md">
              {t.actions.editProfile}
            </Button>
          </Link>
        </div>
      </div>

      {/* Incomplete Profile Alert Banner */}
      {!profileComplete && (
        <div className="p-4 sm:p-5 rounded-2xl bg-amber-50 border border-amber-200 shadow-subtle flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-xl bg-amber-100 flex items-center justify-center shrink-0 text-amber-800 mt-0.5">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div className="space-y-0.5">
              <h4 className="font-bold text-sm text-amber-950">
                {language === 'hi' ? 'आपकी प्रोफ़ाइल अधूरी है' : 'Your Profile is Incomplete'}
              </h4>
              <p className="text-xs text-amber-900/80 leading-relaxed">
                {language === 'hi'
                  ? 'सटीक योजना पात्रता सुनिश्चित करने के लिए अपनी प्रोफ़ाइल में छूटी हुई जानकारी भरें।'
                  : 'Complete your profile to unlock accurate, deterministic scheme matching against official government rules.'}
              </p>
            </div>
          </div>
          <Link to="/onboarding" className="shrink-0 w-full sm:w-auto">
            <Button variant="saffron" size="sm" className="w-full sm:w-auto">
              {language === 'hi' ? 'प्रोफ़ाइल पूर्ण करें' : 'Complete Profile'}
            </Button>
          </Link>
        </div>
      )}

      {/* Summary KPI Metrics (All Live Database / Evaluated Data) */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Eligible Schemes */}
        <Link to="/eligible" className="block group">
          <div className="bg-white p-5 rounded-2xl border border-navy/8 shadow-subtle hover:shadow-premium hover:-translate-y-0.5 transition-all duration-200">
            <div className="flex items-center justify-between text-navy/60 mb-2">
              <span className="text-xs font-semibold tracking-wide uppercase">{language === 'hi' ? 'पात्र योजनाएं' : 'Eligible Schemes'}</span>
              <div className="w-8 h-8 rounded-xl bg-sage-light flex items-center justify-center text-sage-green group-hover:scale-105 transition-transform">
                <Award className="w-4 h-4" />
              </div>
            </div>
            <p className="text-3xl font-bold font-editorial text-sage-green">{eligibleCount}</p>
            <span className="text-[11px] text-navy/50">Personalized matches</span>
          </div>
        </Link>

        {/* Card 2: Applications */}
        <Link to="/applications" className="block group">
          <div className="bg-white p-5 rounded-2xl border border-navy/8 shadow-subtle hover:shadow-premium hover:-translate-y-0.5 transition-all duration-200">
            <div className="flex items-center justify-between text-navy/60 mb-2">
              <span className="text-xs font-semibold tracking-wide uppercase">{language === 'hi' ? 'कुल आवेदन' : 'Applications'}</span>
              <div className="w-8 h-8 rounded-xl bg-ivory-100 flex items-center justify-center text-navy group-hover:scale-105 transition-transform">
                <FolderKanban className="w-4 h-4" />
              </div>
            </div>
            <p className="text-3xl font-bold font-editorial text-navy">{applications.length}</p>
            <span className="text-[11px] text-navy/50">Drafted & submitted</span>
          </div>
        </Link>

        {/* Card 3: Awaiting Review */}
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

        {/* Card 4: Verified Documents */}
        <Link to="/documents" className="block group">
          <div className="bg-white p-5 rounded-2xl border border-navy/8 shadow-subtle hover:shadow-premium hover:-translate-y-0.5 transition-all duration-200">
            <div className="flex items-center justify-between text-navy/60 mb-2">
              <span className="text-xs font-semibold tracking-wide uppercase">{language === 'hi' ? 'दस्तावेज़' : 'Documents Vault'}</span>
              <div className="w-8 h-8 rounded-xl bg-navy/5 flex items-center justify-center text-navy group-hover:scale-105 transition-transform">
                <FileCheck className="w-4 h-4" />
              </div>
            </div>
            <p className="text-3xl font-bold font-editorial text-navy">{vaultDocCount}</p>
            <span className="text-[11px] text-navy/50">Stored in citizen vault</span>
          </div>
        </Link>
      </div>

      {/* Recommended Schemes Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-sage-green" />
            <h2 className="font-bold font-editorial text-navy text-xl">
              {language === 'hi' ? 'आपके लिए अनुशंसित योजनाएं' : 'Top Scheme Matches for You'}
            </h2>
          </div>
          <Link to="/eligible" className="text-xs font-semibold text-saffron-dark hover:text-saffron flex items-center gap-1 group">
            <span>{language === 'hi' ? 'सभी पात्र योजनाएं देखें' : 'View all eligible schemes'}</span>
            <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>

        {recommendedSchemes.length === 0 ? (
          <div className="p-8 bg-white rounded-3xl border border-navy/8 text-center space-y-3">
            <p className="text-sm text-navy/60">
              {language === 'hi'
                ? 'अभी कोई अनुशंसित योजना नहीं है। संपूर्ण कैटलॉग देखें या अपनी प्रोफ़ाइल अपडेट करें।'
                : 'No personalized recommendations yet. Browse all schemes or update your citizen profile.'}
            </p>
            <div className="flex justify-center gap-3">
              <Link to="/schemes">
                <Button variant="outline" size="sm">
                  {language === 'hi' ? 'योजनाएं खोजें' : 'Browse Catalogue'}
                </Button>
              </Link>
              <Link to="/onboarding">
                <Button variant="saffron" size="sm">
                  {language === 'hi' ? 'प्रोफ़ाइल भरें' : 'Complete Profile'}
                </Button>
              </Link>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {recommendedSchemes.map(({ scheme, eligibility }) => (
              <Card key={scheme.id} hoverable className="flex flex-col justify-between border-navy/8">
                <CardContent className="p-5 space-y-3">
                  <div className="flex items-center justify-between gap-2">
                    <Badge variant="category">{scheme.category.replace(/_/g, ' ').toUpperCase()}</Badge>
                    <Badge variant={eligibility.result}>
                      {eligibility.result === 'eligible' ? '● ELIGIBLE' : '● POTENTIAL'}
                    </Badge>
                  </div>

                  <div>
                    <h3 className="font-bold text-navy text-base leading-snug line-clamp-1 font-editorial">
                      {scheme.name}
                    </h3>
                    <p className="text-xs text-navy/60 line-clamp-2 leading-relaxed mt-1">
                      {scheme.description}
                    </p>
                  </div>

                  <div className="p-2.5 rounded-xl bg-sage-light/50 border border-sage/20 text-xs text-navy/80 space-y-0.5">
                    <span className="text-[10px] uppercase font-bold text-sage-dark block">Benefits</span>
                    <p className="line-clamp-2">{scheme.benefits}</p>
                  </div>
                </CardContent>

                <div className="p-4 bg-ivory/50 border-t border-navy/6 flex items-center justify-between">
                  <Link
                    to={`/schemes/${scheme.id}`}
                    className="text-xs font-bold text-navy hover:text-saffron-dark flex items-center gap-1"
                  >
                    <span>{t.actions.viewDetails}</span>
                    <ArrowRight className="w-3 h-3" />
                  </Link>

                  <Link to="/applications">
                    <Button variant="saffron" size="sm">
                      {t.actions.applyNow}
                    </Button>
                  </Link>
                </div>
              </Card>
            ))}
          </div>
        )}
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
            {applications.length === 0 ? (
              <div className="p-6 bg-white rounded-2xl border border-navy/8 text-center text-xs text-navy/50">
                No active applications. Start by selecting an eligible scheme above.
              </div>
            ) : (
              applications.map((app) => (
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
                      {(() => {
                        const isOfficialSubmitted =
                          !app.legacy_synthetic_submission &&
                          app.lifecycle_state === 'submitted' &&
                          Boolean(app.external_reference_id) &&
                          !String(app.external_reference_id).toUpperCase().startsWith('SAATHI/') &&
                          app.submission_source === 'official_integration';
                        const badgeState = app.legacy_synthetic_submission
                          ? 'draft'
                          : app.lifecycle_state === 'submitted' && !isOfficialSubmitted
                          ? 'draft'
                          : app.lifecycle_state;
                        const label = app.legacy_synthetic_submission
                          ? language === 'hi'
                            ? 'असत्यापित पैकेट'
                            : 'UNVERIFIED PACKET'
                          : badgeState === 'submission_unknown'
                          ? 'SUBMISSION UNKNOWN'
                          : badgeState.toUpperCase().replace(/_/g, ' ');
                        return <Badge variant={badgeState as any}>{label}</Badge>;
                      })()}
                      <Link to="/applications">
                        <Button variant="outline" size="sm">
                          {language === 'hi' ? 'खोलें' : 'Open'}
                        </Button>
                      </Link>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
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
            {notifications.length === 0 ? (
              <div className="p-6 bg-white rounded-2xl border border-navy/8 text-center text-xs text-navy/50">
                No new notifications.
              </div>
            ) : (
              notifications.map((n) => (
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
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
