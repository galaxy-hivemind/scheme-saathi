import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { schemeService } from '@/services/api/schemeService';
import { Scheme, SchemeCategory } from '@/types';
import { useLanguage } from '@/context/LanguageContext';
import { Card, CardContent, CardFooter } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Input } from '@/components/common/Input';
import { Spinner } from '@/components/common/Spinner';
import { EmptyState } from '@/components/common/EmptyState';
import { Search, ExternalLink, ArrowRight, ShieldCheck, Sparkles, Sprout, Home, GraduationCap, Heart, Users, Coins } from 'lucide-react';

export const SchemesPage: React.FC = () => {
  const { t, language } = useLanguage();
  const [schemes, setSchemes] = useState<Scheme[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('');

  const categories: { key: SchemeCategory | ''; labelEn: string; labelHi: string }[] = [
    { key: '', labelEn: 'All Schemes', labelHi: 'सभी योजनाएं' },
    { key: 'agriculture', labelEn: 'Agriculture', labelHi: 'कृषि' },
    { key: 'education', labelEn: 'Education', labelHi: 'शिक्षा' },
    { key: 'health', labelEn: 'Health', labelHi: 'स्वास्थ्य' },
    { key: 'housing', labelEn: 'Housing', labelHi: 'आवास' },
    { key: 'women_welfare', labelEn: 'Women Welfare', labelHi: 'महिला कल्याण' },
    { key: 'financial_inclusion', labelEn: 'Financial Inclusion', labelHi: 'वित्तीय समावेशन' },
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
      });
      setSchemes(data);
    } catch (err) {
      console.error('Failed to load schemes:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSchemes();
  }, [selectedCategory]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchSchemes();
  };

  return (
    <div className="space-y-7 max-w-6xl mx-auto">
      {/* Top Header Section */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div className="space-y-1">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-saffron-light text-saffron-dark text-xs font-semibold border border-saffron/30">
            <ShieldCheck className="w-3.5 h-3.5 text-saffron-vibrant" />
            <span>{language === 'hi' ? 'सत्यापित सरकारी स्रोत' : 'Official Central Catalog'}</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold font-editorial text-navy tracking-tight">
            {language === 'hi' ? 'केंद्रीय सरकारी योजनाएं' : 'Central Government Schemes'}
          </h1>
          <p className="text-xs sm:text-sm text-navy/60 max-w-2xl leading-relaxed">
            {language === 'hi'
              ? 'सत्यापित विवरण, स्पष्ट पात्रता शर्तों एवं आधिकारिक दिशानिर्देशों के साथ अधिकृत योजनाएं।'
              : 'Discover authentic central schemes verified against official guidelines with deterministic eligibility.'}
          </p>
        </div>

        <Link to="/chat" className="shrink-0">
          <Button variant="saffron" size="md" leftIcon={<Sparkles className="w-4 h-4" />}>
            {language === 'hi' ? 'साथी से पूछें' : 'Ask AI Saathi'}
          </Button>
        </Link>
      </div>

      {/* Search & Category Filter Bar */}
      <div className="bg-white p-5 rounded-3xl border border-navy/8 shadow-subtle space-y-4">
        <form onSubmit={handleSearchSubmit} className="flex gap-2 sm:gap-3">
          <div className="flex-1">
            <Input
              placeholder={language === 'hi' ? 'योजना खोजें (उदा. किसान, छात्रवृत्ति, आवास)...' : 'Search schemes by keyword (e.g. farmer, housing, scholarship)...'}
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
        <Spinner size="lg" label={language === 'hi' ? 'योजनाएं लोड हो रही हैं...' : 'Loading verified schemes...'} />
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
                  <span className="text-[10px] font-semibold text-sage-green bg-sage-light px-2.5 py-0.5 rounded-full flex items-center gap-1 border border-sage/30">
                    <span className="w-1.5 h-1.5 rounded-full bg-sage-green" />
                    {scheme.scheme_status}
                  </span>
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

              <CardFooter className="p-4 sm:p-5 bg-ivory/50 border-t border-navy/6 flex items-center justify-between">
                <Link
                  to={`/schemes/${scheme.id}`}
                  className="text-xs font-bold text-saffron-dark hover:text-saffron flex items-center gap-1 transition-all duration-200 group/link"
                >
                  <span>{t.actions.viewDetails}</span>
                  <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover/link:translate-x-1" />
                </Link>

                <a
                  href={scheme.official_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[11px] text-navy/50 hover:text-navy flex items-center gap-1 transition-colors"
                >
                  <span>Official Portal</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};
