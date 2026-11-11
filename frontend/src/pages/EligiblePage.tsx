import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { useLanguage } from '@/context/LanguageContext';
import { eligibilityService } from '@/services/api/eligibilityService';
import { schemeService } from '@/services/api/schemeService';
import { Scheme, EligibilityResult, isProfileComplete, SchemeCategory } from '@/types';
import { Card, CardContent, CardFooter } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Spinner } from '@/components/common/Spinner';
import { EligibilityResultModal } from '@/components/common/EligibilityResultModal';
import {
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  ExternalLink,
  ShieldCheck,
  UserCheck,
  Sparkles,
  Sprout,
  Home,
  GraduationCap,
  Heart,
  Users,
  Coins,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

interface MergedSchemeResult {
  scheme: Scheme;
  eligibility: EligibilityResult;
}

export const EligiblePage: React.FC = () => {
  const { profile, isAuthenticated, token } = useAuth();
  const { t, language } = useLanguage();
  const navigate = useNavigate();

  const [loading, setLoading] = useState<boolean>(true);
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [eligibleList, setEligibleList] = useState<MergedSchemeResult[]>([]);
  const [potentialList, setPotentialList] = useState<MergedSchemeResult[]>([]);
  const [insufficientList, setInsufficientList] = useState<MergedSchemeResult[]>([]);
  const [ineligibleList, setIneligibleList] = useState<MergedSchemeResult[]>([]);
  const [showIneligible, setShowIneligible] = useState<boolean>(false);

  // Check Eligibility inspect modal
  const [modalScheme, setModalScheme] = useState<Scheme | null>(null);
  const [modalEligibility, setModalEligibility] = useState<EligibilityResult | null>(null);
  const [modalLoading, setModalLoading] = useState<boolean>(false);

  const handleInspectScheme = async (scheme: Scheme, precomputed?: EligibilityResult) => {
    setModalScheme(scheme);
    if (precomputed) {
      setModalEligibility(precomputed);
    } else {
      setModalLoading(true);
      try {
        const res = await eligibilityService.checkEligibility(scheme.id);
        setModalEligibility(res);
      } catch (err) {
        console.error('Check eligibility failed:', err);
      } finally {
        setModalLoading(false);
      }
    }
  };

  const categories: { key: SchemeCategory | ''; labelEn: string; labelHi: string }[] = [
    { key: '', labelEn: 'All Categories', labelHi: 'सभी श्रेणियां' },
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
        return <Sprout className="w-4 h-4 text-emerald-600" />;
      case 'housing':
        return <Home className="w-4 h-4 text-blue-600" />;
      case 'education':
        return <GraduationCap className="w-4 h-4 text-indigo-600" />;
      case 'health':
        return <Heart className="w-4 h-4 text-rose-600" />;
      case 'women_welfare':
        return <Users className="w-4 h-4 text-amber-600" />;
      default:
        return <Coins className="w-4 h-4 text-saffron-vibrant" />;
    }
  };

  const loadEvaluatedSchemes = async () => {
    if (!token && !profile) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [evalRes, allSchemes] = await Promise.all([
        eligibilityService.evaluateAll({ include_pending: true }),
        schemeService.getSchemes({ limit: 50, include_pending: true }),
      ]);

      const schemeMap = new Map<string, Scheme>();
      allSchemes.forEach((s) => {
        schemeMap.set(s.id, s);
        if (s.scheme_code) {
          schemeMap.set(s.scheme_code.toUpperCase(), s);
          schemeMap.set(s.scheme_code.toLowerCase(), s);
        }
      });

      const eligible: MergedSchemeResult[] = [];
      const potential: MergedSchemeResult[] = [];
      const insufficient: MergedSchemeResult[] = [];
      const ineligible: MergedSchemeResult[] = [];

      for (const res of evalRes.results) {
        // Find matching scheme metadata
        const matched =
          schemeMap.get(res.scheme_id) ||
          (res.scheme_code ? schemeMap.get(res.scheme_code) : undefined) ||
          (res.scheme_code ? schemeMap.get(res.scheme_code.toUpperCase()) : undefined) ||
          allSchemes.find((s) => s.scheme_code?.toLowerCase() === res.scheme_code?.toLowerCase());

        if (!matched) continue;

        const item: MergedSchemeResult = { scheme: matched, eligibility: res };
        if (res.result === 'eligible') {
          eligible.push(item);
        } else if (res.result === 'potentially_eligible') {
          potential.push(item);
        } else if (res.result === 'insufficient_information') {
          insufficient.push(item);
        } else if (res.result === 'not_eligible') {
          ineligible.push(item);
        }
      }

      setEligibleList(eligible);
      setPotentialList(potential);
      setInsufficientList(insufficient);
      setIneligibleList(ineligible);
    } catch (err) {
      console.error('Failed to load eligible schemes:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEvaluatedSchemes();
  }, [profile, token]);

  const profileComplete = isProfileComplete(profile);

  const filterByCategory = (list: MergedSchemeResult[]) => {
    if (!selectedCategory) return list;
    return list.filter((item) => item.scheme.category === selectedCategory);
  };

  const filteredEligible = filterByCategory(eligibleList);
  const filteredPotential = filterByCategory(potentialList);
  const filteredInsufficient = filterByCategory(insufficientList);
  const filteredIneligible = filterByCategory(ineligibleList);

  if (!isAuthenticated && !profile) {
    return (
      <div className="max-w-4xl mx-auto py-12 px-4 space-y-6">
        <div className="bg-white rounded-3xl border border-navy/8 p-8 sm:p-12 text-center space-y-4 shadow-subtle">
          <div className="w-16 h-16 rounded-3xl bg-saffron-light text-saffron-dark flex items-center justify-center mx-auto border border-saffron/30">
            <UserCheck className="w-8 h-8" />
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold font-editorial text-navy">
            {language === 'hi' ? 'अपनी व्यक्तिगत पात्रता जांचें' : 'Personalized Scheme Eligibility'}
          </h2>
          <p className="text-sm text-navy/65 max-w-lg mx-auto leading-relaxed">
            {language === 'hi'
              ? 'अपनी व्यक्तिगत प्रोफ़ाइल के आधार पर सीधे आधिकारिक सरकारी मानदंडों के विरुद्ध मूल्यांकन प्राप्त करने के लिए कृपया साइन इन करें।'
              : 'Sign in or create a citizen account to automatically evaluate all central and state schemes against your verified profile attributes.'}
          </p>
          <div className="pt-2 flex justify-center gap-3">
            <Button variant="saffron" size="md" onClick={() => navigate('/onboarding')}>
              {language === 'hi' ? 'खाता बनाएं / ऑनबोर्डिंग' : 'Get Started / Register'}
            </Button>
            <Link to="/schemes">
              <Button variant="outline" size="md">
                {language === 'hi' ? 'संपूर्ण कैटलॉग देखें' : 'Browse All Schemes'}
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-6xl mx-auto pb-12">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div className="space-y-1.5">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-sage-light text-sage-dark text-xs font-semibold border border-sage/30">
            <ShieldCheck className="w-3.5 h-3.5 text-sage-green" />
            <span>{language === 'hi' ? 'सटीक पात्रता मूल्यांकन' : 'Deterministic Eligibility Evaluator'}</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold font-editorial text-navy tracking-tight">
            {language === 'hi' ? 'आपकी पात्र योजनाएं' : 'Your Eligible Schemes'}
          </h1>
          <p className="text-xs sm:text-sm text-navy/60 max-w-2xl leading-relaxed">
            {language === 'hi'
              ? `नागरिक: ${profile?.full_name || 'नागरिक'} (${profile?.district || 'जिला'}, ${profile?.state || 'राज्य'}) के लिए नियमों के अनुसार मूल्यांकित योजनाएं।`
              : `Schemes evaluated directly against the verified profile of ${profile?.full_name || 'Citizen'} (${profile?.district || 'District'}, ${profile?.state || 'State'}) using official statutory rules.`}
          </p>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          <Link to="/schemes">
            <Button variant="outline" size="sm">
              {language === 'hi' ? 'संपूर्ण कैटलॉग' : 'View Full Catalogue'}
            </Button>
          </Link>
          <Link to="/onboarding">
            <Button variant="outline" size="sm">
              {language === 'hi' ? 'प्रोफ़ाइल बदलें' : 'Update Profile'}
            </Button>
          </Link>
        </div>
      </div>

      {/* Incomplete Profile Alert Banner */}
      {!profileComplete && (
        <div className="p-4 sm:p-5 rounded-2xl bg-amber-50 border border-amber-200/80 shadow-subtle flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-xl bg-amber-100 flex items-center justify-center shrink-0 text-amber-800 mt-0.5">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div className="space-y-0.5">
              <h4 className="font-bold text-sm text-amber-950">
                {language === 'hi' ? 'आपकी नागरिक प्रोफ़ाइल अधूरी है' : 'Your Citizen Profile is Incomplete'}
              </h4>
              <p className="text-xs text-amber-900/80 leading-relaxed max-w-2xl">
                {language === 'hi'
                  ? 'सटीक मूल्यांकन के लिए जन्म तिथि, लिंग, पारिवारिक आय या भूमि स्वामित्व जैसी आवश्यक जानकारी दर्ज करें ताकि सभी योजनाएं सही ढंग से मूल्यांकित हों।'
                  : 'Some schemes require specific attributes (e.g. landholding, gender, residence type) for definitive evaluation. Complete your profile to unlock accurate recommendations.'}
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

      {/* Category Filter Pills */}
      <div className="bg-white p-4 rounded-2xl border border-navy/8 shadow-subtle flex items-center gap-2 overflow-x-auto scrollbar-none">
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

      {loading ? (
        <Spinner size="lg" label={language === 'hi' ? 'आपकी पात्रता का मूल्यांकन किया जा रहा है...' : 'Evaluating schemes against your verified profile in PostgreSQL...'} />
      ) : (
        <div className="space-y-10">
          {/* SECTION 1: FULLY ELIGIBLE SCHEMES */}
          <section className="space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-navy/8">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-sage-light flex items-center justify-center text-sage-green border border-sage/30">
                  <CheckCircle2 className="w-4 h-4" />
                </div>
                <div>
                  <h2 className="text-lg sm:text-xl font-bold font-editorial text-navy">
                    {language === 'hi' ? 'पात्र योजनाएं (पूर्णतः योग्य)' : 'Eligible Schemes'}
                  </h2>
                  <p className="text-xs text-navy/50">
                    {language === 'hi' ? 'सभी अनिवार्य शर्तें पूर्ण हैं' : 'All evaluated criteria matched your profile'}
                  </p>
                </div>
              </div>
              <Badge variant="eligible">
                {filteredEligible.length} {language === 'hi' ? 'योजनाएं' : 'Schemes'}
              </Badge>
            </div>

            {filteredEligible.length === 0 ? (
              <div className="p-6 bg-white rounded-2xl border border-navy/8 text-center text-xs text-navy/60">
                {selectedCategory
                  ? `No fully eligible schemes found in category '${selectedCategory}'.`
                  : 'No schemes currently marked as fully eligible for your baseline attributes. Check Potentially Eligible schemes below.'}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredEligible.map(({ scheme, eligibility }) => (
                  <Card key={scheme.id} hoverable className="flex flex-col justify-between border-sage/40 shadow-subtle">
                    <CardContent className="p-6 space-y-3.5">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <div className="w-8 h-8 rounded-xl bg-ivory-100 flex items-center justify-center shrink-0 border border-navy/8">
                            {getCategoryIcon(scheme.category)}
                          </div>
                          <Badge variant="category">{scheme.category.replace(/_/g, ' ').toUpperCase()}</Badge>
                        </div>
                        <Badge variant="eligible">● ELIGIBLE</Badge>
                      </div>

                      <div className="space-y-1">
                        <h3 className="font-bold text-navy text-base leading-snug line-clamp-2 font-editorial">
                          {scheme.name}
                        </h3>
                        <p className="text-xs text-navy/60 line-clamp-2 leading-relaxed">
                          {scheme.description}
                        </p>
                      </div>

                      {/* Benefits box */}
                      <div className="p-3 rounded-xl bg-sage-light/50 border border-sage/25 space-y-1">
                        <span className="text-[10px] uppercase font-bold text-sage-dark block tracking-wider">
                          {t.labels.benefits}
                        </span>
                        <p className="text-xs font-medium text-navy/80 line-clamp-2 leading-relaxed">
                          {scheme.benefits}
                        </p>
                      </div>

                      {/* Criteria verified summary */}
                      <div className="text-[11px] text-sage-dark font-medium flex items-center gap-1.5 pt-1">
                        <CheckCircle2 className="w-3.5 h-3.5 text-sage-green shrink-0" />
                        <span>{eligibility.condition_results.filter((c) => c.passed === true).length} statutory conditions passed</span>
                      </div>
                    </CardContent>

                    <CardFooter className="p-4 sm:p-5 bg-ivory/50 border-t border-navy/6 flex items-center justify-between gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleInspectScheme(scheme, eligibility)}
                        leftIcon={<Sparkles className="w-3.5 h-3.5 text-saffron" />}
                        className="text-xs"
                      >
                        {t.actions.checkEligibility}
                      </Button>

                      <Link to="/applications">
                        <Button variant="saffron" size="sm">
                          {t.actions.applyNow}
                        </Button>
                      </Link>
                    </CardFooter>
                  </Card>
                ))}
              </div>
            )}
          </section>

          {/* SECTION 2: POTENTIALLY ELIGIBLE SCHEMES */}
          <section className="space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-navy/8">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-saffron-light flex items-center justify-center text-saffron-dark border border-saffron/30">
                  <Sparkles className="w-4 h-4 text-saffron-vibrant" />
                </div>
                <div>
                  <h2 className="text-lg sm:text-xl font-bold font-editorial text-navy">
                    {language === 'hi' ? 'संभावित पात्र योजनाएं' : 'Potentially Eligible Schemes'}
                  </h2>
                  <p className="text-xs text-navy/50">
                    {language === 'hi' ? 'प्राथमिक शर्तें पूर्ण, आवश्यक दस्तावेज या सत्यापन बाकी' : 'Baseline conditions match; requires supporting documents or verification'}
                  </p>
                </div>
              </div>
              <Badge variant="potentially_eligible">
                {filteredPotential.length} {language === 'hi' ? 'योजनाएं' : 'Schemes'}
              </Badge>
            </div>

            {filteredPotential.length === 0 ? (
              <div className="p-6 bg-white rounded-2xl border border-navy/8 text-center text-xs text-navy/60">
                No potentially eligible schemes found.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredPotential.map(({ scheme, eligibility }) => (
                  <Card key={scheme.id} hoverable className="flex flex-col justify-between border-saffron/30 shadow-subtle">
                    <CardContent className="p-6 space-y-3.5">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <div className="w-8 h-8 rounded-xl bg-ivory-100 flex items-center justify-center shrink-0 border border-navy/8">
                            {getCategoryIcon(scheme.category)}
                          </div>
                          <Badge variant="category">{scheme.category.replace(/_/g, ' ').toUpperCase()}</Badge>
                        </div>
                        <Badge variant="potentially_eligible">● POTENTIALLY ELIGIBLE</Badge>
                      </div>

                      <div className="space-y-1">
                        <h3 className="font-bold text-navy text-base leading-snug line-clamp-2 font-editorial">
                          {scheme.name}
                        </h3>
                        <p className="text-xs text-navy/60 line-clamp-2 leading-relaxed">
                          {scheme.description}
                        </p>
                      </div>

                      <div className="p-3 rounded-xl bg-saffron-light/40 border border-saffron/20 space-y-1">
                        <span className="text-[10px] uppercase font-bold text-saffron-dark block tracking-wider">
                          Evaluation Note
                        </span>
                        <p className="text-xs font-medium text-navy/80 line-clamp-2 leading-relaxed">
                          {eligibility.explanation}
                        </p>
                      </div>

                      {eligibility.limitations && (
                        <p className="text-[11px] text-navy/55 italic">
                          *{eligibility.limitations}
                        </p>
                      )}
                    </CardContent>

                    <CardFooter className="p-4 sm:p-5 bg-ivory/50 border-t border-navy/6 flex items-center justify-between gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleInspectScheme(scheme, eligibility)}
                        leftIcon={<Sparkles className="w-3.5 h-3.5 text-saffron" />}
                        className="text-xs"
                      >
                        {t.actions.checkEligibility}
                      </Button>

                      <a
                        href={scheme.official_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[11px] text-navy/50 hover:text-navy flex items-center gap-1"
                      >
                        <span>Portal</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </CardFooter>
                  </Card>
                ))}
              </div>
            )}
          </section>

          {/* SECTION 3: INSUFFICIENT INFORMATION SCHEMES */}
          {filteredInsufficient.length > 0 && (
            <section className="space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-navy/8">
                <div className="flex items-center gap-2.5">
                  <div className="w-7 h-7 rounded-lg bg-amber-100 flex items-center justify-center text-amber-800 border border-amber-300">
                    <HelpCircle className="w-4 h-4" />
                  </div>
                  <div>
                    <h2 className="text-lg sm:text-xl font-bold font-editorial text-navy">
                      {language === 'hi' ? 'अधूरी जानकारी वाली योजनाएं (अधिक विवरण आवश्यक)' : 'Information Required for Evaluation'}
                    </h2>
                    <p className="text-xs text-navy/50">
                      {language === 'hi' ? 'इन योजनाओं का मूल्यांकन करने के लिए प्रोफ़ाइल में कुछ फ़ील्ड छूटे हुए हैं' : 'Missing profile attributes prevent complete determination'}
                    </p>
                  </div>
                </div>
                <Badge variant="insufficient_information">
                  {filteredInsufficient.length} {language === 'hi' ? 'योजनाएं' : 'Schemes'}
                </Badge>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredInsufficient.map(({ scheme, eligibility }) => (
                  <Card key={scheme.id} className="flex flex-col justify-between border-amber-200 bg-amber-50/20">
                    <CardContent className="p-6 space-y-3.5">
                      <div className="flex items-center justify-between gap-2">
                        <Badge variant="category">{scheme.category.replace(/_/g, ' ').toUpperCase()}</Badge>
                        <Badge variant="insufficient_information">● INFO NEEDED</Badge>
                      </div>

                      <h3 className="font-bold text-navy text-base leading-snug line-clamp-2 font-editorial">
                        {scheme.name}
                      </h3>

                      <div className="space-y-2 p-3 bg-white rounded-xl border border-amber-200">
                        <span className="text-[10px] uppercase font-bold text-amber-900 block tracking-wider">
                          Missing Profile Fields:
                        </span>
                        <div className="flex flex-wrap gap-1.5">
                          {eligibility.missing_fields.map((f, i) => (
                            <span key={i} className="px-2 py-0.5 rounded bg-amber-100 text-amber-900 text-[10px] font-mono font-semibold">
                              {f.replace(/_/g, ' ')}
                            </span>
                          ))}
                        </div>
                      </div>
                    </CardContent>

                    <CardFooter className="p-4 sm:p-5 bg-white border-t border-amber-100 flex items-center justify-between">
                      <Link to="/onboarding" className="text-xs font-bold text-amber-900 hover:text-amber-950 underline underline-offset-2">
                        Update Profile to Check
                      </Link>
                      <Link to={`/schemes/${scheme.id}`} className="text-xs text-navy/60 hover:text-navy">
                        View Scheme
                      </Link>
                    </CardFooter>
                  </Card>
                ))}
              </div>
            </section>
          )}

          {/* SECTION 4: INELIGIBLE SCHEMES (COLLAPSIBLE - NOT RECOMMENDED) */}
          <section className="space-y-4 pt-4 border-t border-navy/8">
            <button
              onClick={() => setShowIneligible(!showIneligible)}
              className="w-full flex items-center justify-between p-4 rounded-2xl bg-ivory-100 border border-navy/8 hover:border-navy/20 transition-all text-left"
            >
              <div className="flex items-center gap-2.5">
                <AlertTriangle className="w-4 h-4 text-navy/50" />
                <div>
                  <span className="text-sm font-bold text-navy">
                    {language === 'hi' ? 'वर्तमान में अपात्र योजनाएं देखें' : 'Schemes Not Eligible Based on Current Profile'}
                  </span>
                  <span className="text-xs text-navy/50 block">
                    {filteredIneligible.length} schemes where criteria did not match
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="not_eligible">{filteredIneligible.length}</Badge>
                {showIneligible ? <ChevronUp className="w-4 h-4 text-navy/60" /> : <ChevronDown className="w-4 h-4 text-navy/60" />}
              </div>
            </button>

            {showIneligible && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 pt-2">
                {filteredIneligible.map(({ scheme, eligibility }) => (
                  <Card key={scheme.id} className="opacity-75 hover:opacity-100 transition-opacity border-navy/10 bg-gray-50/50">
                    <CardContent className="p-6 space-y-3">
                      <div className="flex items-center justify-between gap-2">
                        <Badge variant="category">{scheme.category.replace(/_/g, ' ').toUpperCase()}</Badge>
                        <Badge variant="not_eligible">● NOT ELIGIBLE</Badge>
                      </div>

                      <h3 className="font-bold text-navy text-sm line-clamp-1">{scheme.name}</h3>

                      <div className="p-2.5 rounded-xl bg-rose-50/80 border border-rose-200 text-xs text-rose-950 space-y-1">
                        <span className="font-semibold block text-[10px] uppercase tracking-wide text-rose-800">
                          Disqualification Reason:
                        </span>
                        <p className="leading-relaxed">
                          {eligibility.failed_conditions?.[0]?.explanation || eligibility.explanation}
                        </p>
                      </div>
                    </CardContent>

                    <CardFooter className="p-4 bg-white border-t border-navy/6 flex items-center justify-between">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleInspectScheme(scheme, eligibility)}
                        className="text-xs text-rose-900 border-rose-200 hover:bg-rose-50"
                      >
                        Inspect Disqualification Rules
                      </Button>
                      <Link to={`/schemes/${scheme.id}`} className="text-xs text-navy/60 hover:text-navy">
                        Full Details
                      </Link>
                    </CardFooter>
                  </Card>
                ))}
              </div>
            )}
          </section>
        </div>
      )}

      {/* Deterministic Criteria AST Inspection Modal */}
      <EligibilityResultModal
        isOpen={!!modalScheme}
        onClose={() => setModalScheme(null)}
        scheme={modalScheme}
        eligibility={modalEligibility}
        loading={modalLoading}
      />
    </div>
  );
};
