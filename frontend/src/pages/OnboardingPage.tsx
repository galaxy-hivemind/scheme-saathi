import React, { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useLanguage } from '@/context/LanguageContext';
import { profileService } from '@/services/api/profileService';
import { UserProfile } from '@/types';
import { Card, CardHeader, CardContent, CardFooter } from '@/components/common/Card';
import { Button } from '@/components/common/Button';
import { Input } from '@/components/common/Input';
import { Select } from '@/components/common/Select';
import { StatusBanner } from '@/components/common/StatusBanner';
import { User, ShieldCheck, Check } from 'lucide-react';
import { Link } from 'react-router-dom';

export const OnboardingPage: React.FC = () => {
  const { profile, updateProfileState } = useAuth();
  const { language } = useLanguage();

  const [fullName, setFullName] = useState<string>('');
  const [dob, setDob] = useState<string>('');
  const [stateName, setStateName] = useState<string>('');
  const [district, setDistrict] = useState<string>('');
  const [residenceType, setResidenceType] = useState<"rural" | "urban" | "semi_urban">('rural');
  const [occupation, setOccupation] = useState<string>('farmer');
  const [income, setIncome] = useState<string>('120000');
  const [landHolding, setLandHolding] = useState<string>('1.5');
  const [casteCategory, setCasteCategory] = useState<string>('OBC');

  const [saving, setSaving] = useState<boolean>(false);
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false);

  useEffect(() => {
    if (profile) {
      setFullName(profile.full_name || '');
      setDob(profile.date_of_birth || '');
      setStateName(profile.state || '');
      setDistrict(profile.district || '');
      setResidenceType(profile.residence_type || 'rural');
      setOccupation(profile.occupation || 'farmer');
      setIncome(profile.annual_family_income ? String(profile.annual_family_income) : '');
      if (profile.profile_data) {
        setLandHolding(String(profile.profile_data.land_holding_acres || ''));
        setCasteCategory(String(profile.profile_data.caste_category || 'General'));
      }
    }
  }, [profile]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSavedSuccess(false);

    const updatedData: Partial<UserProfile> = {
      full_name: fullName,
      date_of_birth: dob || undefined,
      state: stateName || undefined,
      district: district || undefined,
      residence_type: residenceType,
      occupation: occupation || undefined,
      annual_family_income: income ? Number(income) : undefined,
      preferred_language: language,
      profile_data: {
        land_holding_acres: landHolding ? Number(landHolding) : undefined,
        caste_category: casteCategory,
      },
    };

    try {
      const saved = await profileService.updateProfile(updatedData);
      updateProfileState(saved);
      setSavedSuccess(true);
    } catch (err) {
      console.error('Failed to update profile:', err);
    } finally {
      setSaving(false);
    }
  };

  const occupations = [
    { value: 'farmer', label: language === 'hi' ? 'किसान (Farmer)' : 'Farmer' },
    { value: 'student', label: language === 'hi' ? 'छात्र / छात्रा (Student)' : 'Student' },
    { value: 'daily_wager', label: language === 'hi' ? 'दैनिक मजदूर (Daily Wage Laborer)' : 'Daily Wage Laborer' },
    { value: 'artisan', label: language === 'hi' ? 'कारीगर / शिल्पी (Artisan / Craftsman)' : 'Artisan / Craftsman' },
    { value: 'unemployed', label: language === 'hi' ? 'बेरोजगार (Unemployed Youth)' : 'Unemployed Youth' },
    { value: 'self_employed', label: language === 'hi' ? 'स्व-व्यवसायी (Self-Employed / Shopkeeper)' : 'Self-Employed / Shopkeeper' },
    { value: 'salaried', label: language === 'hi' ? 'वेतनभोगी (Salaried Employee)' : 'Salaried Employee' },
    { value: 'homemaker', label: language === 'hi' ? 'गृहिणी (Homemaker)' : 'Homemaker' },
  ];

  const casteCategories = [
    { value: 'General', label: 'General / सामान्य' },
    { value: 'OBC', label: 'OBC / अन्य पिछड़ा वर्ग' },
    { value: 'SC', label: 'SC / अनुसूचित जाति' },
    { value: 'ST', label: 'ST / अनुसूचित जनजाति' },
    { value: 'EWS', label: 'EWS / आर्थिक रूप से कमजोर वर्ग' },
  ];

  return (
    <div className="max-w-2xl mx-auto space-y-7">
      {/* Header */}
      <div className="space-y-1">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-saffron-light text-saffron-dark text-xs font-semibold border border-saffron/30">
          <User className="w-3.5 h-3.5 text-saffron-vibrant" />
          <span>{language === 'hi' ? 'नागरिक प्रोफ़ाइल' : 'Citizen Profile'}</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-bold font-editorial text-navy tracking-tight">
          {language === 'hi' ? 'नागरिक विवरण व प्राथमिकताएं' : 'Citizen Profile & Preferences'}
        </h1>
        <p className="text-xs sm:text-sm text-navy/60 leading-relaxed">
          {language === 'hi'
            ? 'अपनी जानकारी दर्ज करें ताकि योजना साथी आपकी सटीक पात्रता जांच सके।'
            : 'Fill in your baseline details so Scheme Saathi can evaluate deterministic welfare eligibility.'}
        </p>
      </div>

      <StatusBanner
        type="info"
        title="Data Minimization & Privacy Guarantee"
        message={
          language === 'hi'
            ? 'हम केवल वही जानकारी एकत्र करते हैं जो सरकारी योजनाओं की पात्रता निर्धारित करने के लिए आवश्यक है।'
            : 'We collect only the baseline attributes needed to evaluate welfare criteria under Indian central scheme rules.'
        }
      />

      {savedSuccess && (
        <StatusBanner
          type="success"
          title="Profile Updated Successfully"
          message={language === 'hi' ? 'आपकी प्रोफ़ाइल सफलतापूर्वक सहेज ली गई है।' : 'Your profile has been saved. Your scheme recommendations and eligibility checks are now updated.'}
          action={
            <Link to="/dashboard">
              <Button size="sm" variant="outline">
                Dashboard
              </Button>
            </Link>
          }
        />
      )}

      {/* Main Profile Form Card */}
      <Card>
        <form onSubmit={handleSubmit}>
          <CardHeader>
            <h3 className="font-bold font-editorial text-navy text-lg">
              {language === 'hi' ? 'मूल नागरिक विवरण' : 'Baseline Citizen Attributes'}
            </h3>
            <p className="text-xs text-navy/50">Used to match welfare guidelines across ministries</p>
          </CardHeader>

          <CardContent className="p-6 sm:p-8 space-y-5">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label={language === 'hi' ? 'पूरा नाम' : 'Full Name'}
                placeholder="e.g. Ramesh Kumar"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
              />

              <Input
                label={language === 'hi' ? 'जन्म तिथि' : 'Date of Birth'}
                type="date"
                value={dob}
                onChange={(e) => setDob(e.target.value)}
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label={language === 'hi' ? 'राज्य' : 'State'}
                placeholder="e.g. Uttar Pradesh"
                value={stateName}
                onChange={(e) => setStateName(e.target.value)}
                required
              />

              <Input
                label={language === 'hi' ? 'जिला' : 'District'}
                placeholder="e.g. Varanasi"
                value={district}
                onChange={(e) => setDistrict(e.target.value)}
                required
              />
            </div>

            {/* Residence Type Radio Buttons */}
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-navy/70 tracking-wide">
                {language === 'hi' ? 'आवास क्षेत्र (Residence Type)' : 'Residence Type'}
              </label>
              <div className="grid grid-cols-3 gap-2.5">
                {(['rural', 'semi_urban', 'urban'] as const).map((type) => (
                  <button
                    key={type}
                    type="button"
                    onClick={() => setResidenceType(type)}
                    className={`py-2.5 px-3 rounded-xl border text-xs font-semibold capitalize transition-all duration-200 ${
                      residenceType === type
                        ? 'bg-navy text-white border-navy shadow-subtle'
                        : 'bg-ivory-100 text-navy/70 border-navy/10 hover:border-navy/25 hover:text-navy'
                    }`}
                  >
                    {type.replace('_', ' ')}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Select
                label={language === 'hi' ? 'व्यवसाय' : 'Occupation'}
                value={occupation}
                onChange={(e) => setOccupation(e.target.value)}
                options={occupations}
              />

              <Select
                label={language === 'hi' ? 'सामाजिक श्रेणी' : 'Social Category / Caste'}
                value={casteCategory}
                onChange={(e) => setCasteCategory(e.target.value)}
                options={casteCategories}
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label={language === 'hi' ? 'वार्षिक पारिवारिक आय (₹)' : 'Annual Family Income (₹)'}
                type="number"
                placeholder="e.g. 120000"
                value={income}
                onChange={(e) => setIncome(e.target.value)}
                helperText="Total household annual earnings"
              />

              <Input
                label={language === 'hi' ? 'कृषि भूमि (एकड़)' : 'Land Holding (Acres)'}
                type="number"
                step="0.1"
                placeholder="e.g. 1.5"
                value={landHolding}
                onChange={(e) => setLandHolding(e.target.value)}
                helperText="Total cultivable land owned"
              />
            </div>
          </CardContent>

          <CardFooter className="p-6 bg-ivory/60 border-t border-navy/8 flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs text-navy/50">
              <ShieldCheck className="w-4 h-4 text-sage" />
              <span>Encrypted on Device</span>
            </div>

            <Button
              type="submit"
              variant="saffron"
              size="md"
              leftIcon={<Check className="w-4 h-4" />}
              isLoading={saving}
            >
              {language === 'hi' ? 'प्रोफ़ाइल सहेजें' : 'Save Citizen Profile'}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
};
