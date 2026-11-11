import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { schemeService } from '@/services/api/schemeService';
import { eligibilityService } from '@/services/api/eligibilityService';
import { useAuth } from '@/context/AuthContext';
import { useLanguage } from '@/context/LanguageContext';
import { Scheme, SchemeCategory, EligibilityResult } from '@/types';
import { Card, CardContent, CardFooter } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Input } from '@/components/common/Input';
import { Spinner } from '@/components/common/Spinner';
import { EmptyState } from '@/components/common/EmptyState';
import { LoginModal } from '@/components/common/LoginModal';
import { EligibilityResultModal } from '@/components/common/EligibilityResultModal';
import {
  Search,
  ExternalLink,
  ArrowRight,
  ShieldCheck,
  Sparkles,
  Sprout,
  Home,
  GraduationCap,
  Heart,
  Users,
  Coins,
  CheckCircle2,
} from 'lucide-react';

export const SchemesPage: React.FC = () => {
  const { t, language } = useLanguage();
  const { profile, token, isAuthenticated } = useAuth();

  const [schemes, setSchemes] = useState<Scheme[]>([]);
  const [eligibilityMap, setEligibilityMap] = useState<Record<string, EligibilityResult>>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('');

  // Check Eligibility modal & execution state
  const [evaluatingSchemeId, setEvaluatingSchemeId] = useState<string | null>(null);
  const [modalScheme, setModalScheme] = useState<Scheme | null>(null);
  const [modalEligibility, setModalEligibility] = useState<EligibilityResult | null>(null);
  const [modalLoading, setModalLoading] = useState<boolean>(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [isLoginOpen, setIsLoginOpen] = useState<boolean>(false);

  const categories: { key: SchemeCategory | ''; labelEn: string; labelHi: string }[] = [
    { key: '', labelEn: 'All Schemes', labelHi: 'सभी योजनाएं' },
    { key: 'agriculture', labelEn: 'Agriculture', labelHi: 'कृषि' },
    { key: 'education', labelEn: 'Education', labelHi: 'शिक्षा' },
    { key: 'health', labelEn: 'Health', labelHi: 'स्वास्थ्य' },
    { key: 'housing', labelEn: 'Housing', labelHi: 'आवास' },
    { key: 'women_welfare', labelEn: 'Women Welfare', labelHi: 'महिला कल्याण' },
    { key: 'financial_inclusion', labelEn: 'Financial Inclusion', labelHi: 'वित्तीय समावेशन' },
    { key: 'social_security', labelEn: 'Social Security', labelHi: 'सामाजिक सुरक्षा' },
  ];

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'agriculture':
        return <Sprout className="w-5 h-5 text-emerald-600" />;
      case 'housing':
        return <Home className="w-5 h-5 text-blue-600" />;
      case 'education':
        return <GraduationCap className="w-5 h-5 text-indigo-600" />;
      case 'health':
        return <Heart className="w-5 h-5 text-rose-600" />;
      case 'women_welfare':
        return <Users className="w-5 h-5 text-amber-600" />;
      default:
        return <Coins className="w-5 h-5 text-saffron-vibrant" />;
    }
  };

  const fetchSchemes = async () => {
    setLoading(true);
    try {
      const data = await schemeService.getSchemes({
        q: search || undefined,
        category: selectedCategory || undefined,
        limit: 50,
        include_pending: true,
      });
      setSchemes(data);
    } catch (err) {
      console.error('Failed to load schemes:', err);
    } finally {
      setLoading(false);
    }
  };

  // Background fetch of eligibility evaluations if user is logged in
  useEffect(() => {
    const fetchEligibility = async () => {
      if (!token && !profile) return;
      try {
        const evalRes = await eligibilityService.evaluateAll({ include_pending: true });
        const map: Record<string, EligibilityResult> = {};
        for (const res of evalRes.results) {
          if (res.scheme_id) map[res.scheme_id] = res;
          if (res.scheme_code) {
            map[res.scheme_code] = res;
            map[res.scheme_code.toUpperCase()] = res;
            map[res.scheme_code.toLowerCase()] = res;
          }
        }
        setEligibilityMap(map);
      } catch (err) {
        console.warn('Could not load eligibility status badges:', err);
      }
    };

    fetchEligibility();
  }, [token, profile]);

  useEffect(() => {
    fetchSchemes();
  }, [selectedCategory]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchSchemes();
  };

  const handleCheckSchemeEligibility = async (scheme: Scheme) => {
    if (!token && !profile) {
      setIsLoginOpen(true);
      return;
    }

    setEvaluatingSchemeId(scheme.id);
    setModalScheme(scheme);
    setModalLoading(true);
    setModalError(null);
    setModalEligibility(null);

    try {
      const res = await eligibilityService.checkEligibility(scheme.id);
      setModalEligibility(res);
      // Update local badge cache with newest evaluation
      setEligibilityMap((prev) => ({
        ...prev,
        [scheme.id]: res,
        ...(scheme.scheme_code ? { [scheme.scheme_code]: res } : {}),
      }));
    } catch (err: any) {
      console.error('Check eligibility failed:', err);
      setModalError(err?.message || 'Failed to evaluate criteria against verified profile.');
    } finally {
      setModalLoading(false);
      setEvaluatingSchemeId(null);
    }
  };

  const renderEligibilityBadge = (scheme: Scheme) => {
    const evalResult =
      eligibilityMap[scheme.id] ||
      (scheme.scheme_code ? eligibilityMap[scheme.scheme_code] : undefined) ||
      (scheme.scheme_code ? eligibilityMap[scheme.scheme_code.toUpperCase()] : undefined);

    if (!evalResult) {
      return (
        <span className="text-[10px] font-semibold text-navy/60 bg-ivory-100 px-2.5 py-0.5 rounded-full flex items-center gap-1 border border-navy/10">
          <span className="w-1.5 h-1.5 rounded-full bg-navy/40" />
          {scheme.scheme_status}
        </span>
      );
    }

    if (evalResult.result === 'eligible') {
      return <Badge variant="eligible">● ELIGIBLE</Badge>;
    }
    if (evalResult.result === 'potentially_eligible') {
      return <Badge variant="potentially_eligible">● POTENTIAL</Badge>;
    }
    if (evalResult.result === 'insufficient_information') {
      return <Badge variant="insufficient_information">● INFO NEEDED</Badge>;
    }
    return <Badge variant="not_eligible">● NOT ELIGIBLE</Badge>;
  };

  return (
    <div className="space-y-7 max-w-6xl mx-auto pb-12">
      {/* Top Header Section */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div className="space-y-1">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-saffron-light text-saffron-dark text-xs font-semibold border border-saffron/30">
            <ShieldCheck className="w-3.5 h-3.5 text-saffron-vibrant" />
            <span>{language === 'hi' ? 'सत्यापित केंद्रीय कैटलॉग' : 'Complete Central & State Welfare Catalogue'}</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold font-editorial text-navy tracking-tight">
            {language === 'hi' ? 'संपूर्ण सरकारी योजनाएं' : 'All Government Schemes'}
          </h1>
          <p className="text-xs sm:text-sm text-navy/60 max-w-2xl leading-relaxed">
            {language === 'hi'
              ? 'केंद्रीय एवं राज्य कल्याणकारी योजनाओं की संपूर्ण अधिकृत सूची। अपनी पात्रता के अनुसार देखने के लिए "पात्रता" पृष्ठ पर जाएं।'
              : 'Explore the complete verified catalogue of Indian welfare schemes across all sectors, guidelines and ministries.'}
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          {isAuthenticated && (
            <Link to="/eligible">
              <Button variant="saffron" size="md" leftIcon={<CheckCircle2 className="w-4 h-4" />}>
                {language === 'hi' ? 'मेरी पात्र योजनाएं' : 'My Eligible Schemes'}
              </Button>
            </Link>
          )}
          <Link to="/chat">
            <Button variant="outline" size="md" leftIcon={<Sparkles className="w-4 h-4" />}>
              {language === 'hi' ? 'साथी से पूछें' : 'Ask AI Saathi'}
            </Button>
          </Link>
        </div>
      </div>

      {/* Banner linking to Eligible Page for evaluated citizens */}
      {isAuthenticated && (
        <div className="bg-sage-light/60 border border-sage/30 rounded-2xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-subtle">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-sage-green shrink-0" />
            <p className="text-xs text-navy/80 font-medium">
              {language === 'hi'
                ? 'यह पृष्ठ संपूर्ण कैटलॉग प्रदर्शित करता है। अपनी प्रोफ़ाइल के अनुसार मूल्यांकित योजनाएं देखने के लिए पात्र पृष्ठ खोलें।'
                : 'This page shows the entire available catalogue. To view only schemes tailored to your profile, visit your dedicated Eligible Schemes page.'}
            </p>
          </div>
          <Link to="/eligible" className="shrink-0 text-xs font-bold text-sage-dark hover:underline flex items-center gap-1">
            <span>{language === 'hi' ? 'पात्र योजनाएं खोलें' : 'View Matching Schemes'}</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      )}

      {/* Search & Category Filter Bar */}
      <div className="bg-white p-5 rounded-3xl border border-navy/8 shadow-subtle space-y-4">
        <form onSubmit={handleSearchSubmit} className="flex gap-2 sm:gap-3">
          <div className="flex-1">
            <Input
              placeholder={
                language === 'hi'
                  ? 'योजना खोजें (उदा. किसान, छात्रवृत्ति, आवास, महिला)...'
                  : 'Search schemes by keyword, ministry, benefits (e.g. farmer, housing, scholarship)...'
              }
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              leftIcon={<Search className="w-4 h-4 text-navy/40" />}
            />
          </div>
          <Button type="submit" variant="primary" size="md" className="shrink-0 px-6">
            {language === 'hi' ? 'खोजें' : 'Search'}
          </Button>
        </form>

        {/* Category Pill Filters */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none pt-1">
          {categories.map((cat) => {
            const isSelected = selectedCategory === cat.key;
            return (
              <button
                key={cat.key}
                onClick={() => setSelectedCategory(cat.key)}
                className={`text-xs px-3.5 py-1.5 rounded-full font-medium shrink-0 transition-all duration-200 border ${
                  isSelected
                    ? 'bg-navy text-white border-navy shadow-subtle'
                    : 'bg-ivory-100 text-navy/70 border-navy/10 hover:border-navy/25 hover:text-navy'
                }`}
              >
                {language === 'hi' ? cat.labelHi : cat.labelEn}
              </button>
            );
          })}
        </div>
      </div>

      {/* Schemes Grid */}
      {loading ? (
        <Spinner size="lg" label={language === 'hi' ? 'योजनाएं लोड हो रही हैं...' : 'Loading verified schemes catalogue...'} />
      ) : schemes.length === 0 ? (
        <EmptyState
          title={language === 'hi' ? 'कोई योजना नहीं मिली' : 'No Schemes Found'}
          description={language === 'hi' ? 'कृपया अपनी खोज शब्द बदलें या अन्य श्रेणी चुनें।' : 'Try adjusting your search keywords or selecting another category.'}
          actionLabel={language === 'hi' ? 'सभी योजनाएं देखें' : 'View All Schemes'}
          onAction={() => {
            setSearch('');
            setSelectedCategory('');
          }}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {schemes.map((scheme) => (
            <Card key={scheme.id} hoverable className="flex flex-col justify-between group">
              <CardContent className="space-y-3.5 p-6">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-xl bg-ivory-100 flex items-center justify-center shrink-0 border border-navy/8">
                      {getCategoryIcon(scheme.category)}
                    </div>
                    <Badge variant="category">{scheme.category.replace(/_/g, ' ').toUpperCase()}</Badge>
                  </div>
                  {renderEligibilityBadge(scheme)}
                </div>

                <div className="space-y-1">
                  <h3 className="font-bold text-navy text-base leading-snug line-clamp-2 font-editorial group-hover:text-saffron-dark transition-colors">
                    {scheme.name}
                  </h3>
                  <p className="text-xs text-navy/60 line-clamp-2 leading-relaxed">
                    {scheme.description}
                  </p>
                </div>

                <div className="p-3 rounded-xl bg-ivory-100/70 border border-navy/6 space-y-1">
                  <span className="text-[10px] uppercase font-bold text-navy/40 block tracking-wider">
                    {t.labels.benefits}
                  </span>
                  <p className="text-xs font-medium text-navy/80 line-clamp-2 leading-relaxed">
                    {scheme.benefits}
                  </p>
                </div>
              </CardContent>

              <CardFooter className="p-4 sm:p-5 bg-ivory/50 border-t border-navy/6 flex flex-col gap-2.5">
                <div className="flex items-center justify-between w-full">
                  <Button
                    variant="saffron"
                    size="sm"
                    onClick={() => handleCheckSchemeEligibility(scheme)}
                    isLoading={evaluatingSchemeId === scheme.id}
                    leftIcon={<Sparkles className="w-3.5 h-3.5" />}
                    className="text-xs"
                  >
                    {t.actions.checkEligibility}
                  </Button>

                  <Link
                    to={`/schemes/${scheme.id}`}
                    className="text-xs font-bold text-navy hover:text-saffron-dark flex items-center gap-1 transition-all duration-200 group/link"
                  >
                    <span>{t.actions.viewDetails}</span>
                    <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover/link:translate-x-1" />
                  </Link>
                </div>

                <div className="flex items-center justify-end w-full pt-1 border-t border-navy/5">
                  <a
                    href={scheme.official_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[11px] text-navy/50 hover:text-navy flex items-center gap-1 transition-colors"
                  >
                    <span>Official Portal</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}

      {/* Check Eligibility Result Modal */}
      <EligibilityResultModal
        isOpen={!!modalScheme}
        onClose={() => setModalScheme(null)}
        scheme={modalScheme}
        eligibility={modalEligibility}
        loading={modalLoading}
        error={modalError}
      />

      {/* Login Prompt Modal for unauthenticated users */}
      <LoginModal
        isOpen={isLoginOpen}
        onClose={() => setIsLoginOpen(false)}
      />
    </div>
  );
};
