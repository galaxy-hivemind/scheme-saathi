import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { useLanguage } from '@/context/LanguageContext';
import { profileService } from '@/services/api/profileService';
import { UserProfile } from '@/types';
import { Card, CardHeader, CardContent, CardFooter } from '@/components/common/Card';
import { Button } from '@/components/common/Button';
import { Input } from '@/components/common/Input';
import { Select } from '@/components/common/Select';
import { StatusBanner } from '@/components/common/StatusBanner';
import { User, ShieldCheck, Check, AlertCircle } from 'lucide-react';

export const OnboardingPage: React.FC = () => {
  const { profile, updateProfileState } = useAuth();
  const { language } = useLanguage();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState<string>('');
  const [dob, setDob] = useState<string>('');
  const [gender, setGender] = useState<string>('male');
  const [stateName, setStateName] = useState<string>('');
  const [district, setDistrict] = useState<string>('');
  const [residenceType, setResidenceType] = useState<"rural" | "urban" | "semi_urban">('rural');
  const [occupation, setOccupation] = useState<string>('farmer');
  const [income, setIncome] = useState<string>('120000');
  const [isLandholdingFarmer, setIsLandholdingFarmer] = useState<boolean>(true);
  const [landHolding, setLandHolding] = useState<string>('1.5');
  const [casteCategory, setCasteCategory] = useState<string>('OBC');
  const [isTaxPayer, setIsTaxPayer] = useState<boolean>(false);

  const [saving, setSaving] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false);

  useEffect(() => {
    if (profile) {
      setFullName(profile.full_name || '');
      setDob(profile.date_of_birth || '');
      setGender(profile.gender || 'male');
      setStateName(profile.state || '');
      setDistrict(profile.district || '');
      setResidenceType(profile.residence_type || 'rural');
      setOccupation(profile.occupation || 'farmer');
      setIncome(profile.annual_family_income !== undefined && profile.annual_family_income !== null ? String(profile.annual_family_income) : '');
      if (profile.profile_data) {
        if (profile.profile_data.land_holding_acres !== undefined) {
          setLandHolding(String(profile.profile_data.land_holding_acres));
        }
        if (profile.profile_data.caste_category !== undefined) {
          setCasteCategory(String(profile.profile_data.caste_category));
        }
        if (profile.profile_data.is_landholding_farmer !== undefined) {
          setIsLandholdingFarmer(Boolean(profile.profile_data.is_landholding_farmer));
        }
        if (profile.profile_data.is_income_tax_payer !== undefined) {
          setIsTaxPayer(Boolean(profile.profile_data.is_income_tax_payer));
        }
      }
    }
  }, [profile]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setErrorMessage(null);
    setSavedSuccess(false);

    const acresNum = landHolding ? Number(landHolding) : 0;
    const hectaresNum = acresNum > 0 ? Number((acresNum * 0.404686).toFixed(2)) : 0;

    const updatedData: Partial<UserProfile> = {
      full_name: fullName.trim(),
      date_of_birth: dob || undefined,
      gender: gender,
      state: stateName.trim() || undefined,
      district: district.trim() || undefined,
      residence_type: residenceType,
      occupation: occupation || undefined,
      annual_family_income: income ? Number(income) : undefined,
      preferred_language: language,
      profile_data: {
        ...(profile?.profile_data || {}),
        occupation: occupation,
        caste_category: casteCategory.toLowerCase(),
        is_farmer: occupation === 'farmer',
        is_student: occupation === 'student',
        is_artisan: occupation === 'artisan',
        is_landholding_farmer: occupation === 'farmer' ? isLandholdingFarmer : false,
        land_holding_acres: occupation === 'farmer' ? acresNum : 0,
        land_size_hectares: occupation === 'farmer' ? hectaresNum : 0,
        is_income_tax_payer: isTaxPayer,
        is_institutional_landholder: false,
      },
    };

    try {
      const saved = await profileService.updateProfile(updatedData);
      updateProfileState(saved);
      setSavedSuccess(true);
      // Seamless direct transition to Dashboard upon successful completion
      setTimeout(() => {
        navigate('/dashboard');
      }, 800);
    } catch (err: any) {
      console.error('Failed to update profile:', err);
      setErrorMessage(err?.message || 'Failed to save profile. Please ensure you are logged in.');
    } finally {
      setSaving(false);
    }
  };

  const occupations = [
    { value: 'farmer', label: language === 'hi' ? 'किसान (Farmer)' : 'Farmer' },
    { value: 'student', label: language === 'hi' ? 'छात्र / छात्रा (Student)' : 'Student' },
    { value: 'artisan', label: language === 'hi' ? 'कारीगर / शिल्पी (Artisan / Craftsman)' : 'Artisan / Craftsman' },
    { value: 'daily_wager', label: language === 'hi' ? 'दैनिक मजदूर (Daily Wage Laborer)' : 'Daily Wage Laborer' },
    { value: 'self_employed', label: language === 'hi' ? 'स्व-व्यवसायी / दुकानदार (Self-Employed)' : 'Self-Employed' },
    { value: 'salaried', label: language === 'hi' ? 'वेतनभोगी (Salaried Employee)' : 'Salaried Employee' },
    { value: 'unemployed', label: language === 'hi' ? 'बेरोजगार (Unemployed Youth)' : 'Unemployed Youth' },
    { value: 'homemaker', label: language === 'hi' ? 'गृहिणी (Homemaker)' : 'Homemaker' },
  ];

  const casteCategories = [
    { value: 'General', label: 'General / सामान्य' },
    { value: 'OBC', label: 'OBC / अन्य पिछड़ा वर्ग' },
    { value: 'SC', label: 'SC / अनुसूचित जाति' },
    { value: 'ST', label: 'ST / अनुसूचित जनजाति' },
    { value: 'EWS', label: 'EWS / आर्थिक रूप से कमजोर' },
  ];

  const genderOptions = [
    { value: 'male', label: language === 'hi' ? 'पुरुष (Male)' : 'Male' },
    { value: 'female', label: language === 'hi' ? 'महिला (Female)' : 'Female' },
    { value: 'transgender', label: language === 'hi' ? 'ट्रांसजेंडर (Transgender)' : 'Transgender' },
    { value: 'other', label: language === 'hi' ? 'अन्य (Other)' : 'Other' },
  ];

  const missingFields: string[] = [];
  if (!fullName.trim()) missingFields.push(language === 'hi' ? 'पूरा नाम' : 'Full Name');
  if (!dob) missingFields.push(language === 'hi' ? 'जन्म तिथि' : 'Date of Birth');
  if (!gender) missingFields.push(language === 'hi' ? 'लिंग' : 'Gender');
  if (!stateName.trim()) missingFields.push(language === 'hi' ? 'राज्य' : 'State');
  if (!district.trim()) missingFields.push(language === 'hi' ? 'जिला' : 'District');
  if (!income) missingFields.push(language === 'hi' ? 'वार्षिक आय' : 'Annual Income');

  return (
    <div className="max-w-2xl mx-auto space-y-7">
      {/* Header */}
      <div className="space-y-1">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-saffron-light text-saffron-dark text-xs font-semibold border border-saffron/30">
          <User className="w-3.5 h-3.5 text-saffron-vibrant" />
          <span>{language === 'hi' ? 'नागरिक प्रोफ़ाइल' : 'Citizen Profile'}</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-bold font-editorial text-navy tracking-tight">
          {language === 'hi' ? 'नागरिक विवरण व पात्रता प्रोफाइल' : 'Citizen Profile & Scheme Criteria'}
        </h1>
        <p className="text-xs sm:text-sm text-navy/60 leading-relaxed">
          {language === 'hi'
            ? 'अपनी मूल जानकारी दर्ज करें। योजना साथी इसके आधार पर केंद्रीय एवं राज्य कल्याण योजनाओं की सटीक पात्रता जांचता है।'
            : 'Fill in your baseline details. Scheme Saathi uses this data to evaluate deterministic welfare eligibility under official guidelines.'}
        </p>
      </div>

      {missingFields.length > 0 && (
        <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 text-xs space-y-1">
          <div className="flex items-center gap-2 font-bold">
            <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>{language === 'hi' ? 'अधूरी जानकारी (पात्रता जांच हेतु आवश्यक)' : 'Incomplete Profile (Required for Scheme Matching)'}:</span>
          </div>
          <p className="opacity-80">
            {language === 'hi'
              ? `कृपया निम्नलिखित फ़ील्ड भरें: ${missingFields.join(', ')}`
              : `Please provide: ${missingFields.join(', ')}`}
          </p>
        </div>
      )}

      {errorMessage && (
        <StatusBanner
          type="danger"
          title="Error"
          message={errorMessage}
        />
      )}

      {savedSuccess && (
        <StatusBanner
          type="success"
          title="Profile Saved Successfully"
          message={language === 'hi' ? 'आपकी प्रोफ़ाइल सहेजी गई। डैशबोर्ड पर ले जाया जा रहा है...' : 'Your profile has been saved. Redirecting to dashboard...'}
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
            <p className="text-xs text-navy/50">Used to match welfare guidelines across central & state ministries</p>
          </CardHeader>

          <CardContent className="p-6 sm:p-8 space-y-5">
            {/* Full Name & DOB */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label={language === 'hi' ? 'पूरा नाम' : 'Full Name'}
                placeholder="e.g. Ramesh Kumar"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
              />

              <Input
                label={language === 'hi' ? 'जन्म तिथि (आयु हेतु)' : 'Date of Birth (for Age evaluation)'}
                type="date"
                value={dob}
                onChange={(e) => setDob(e.target.value)}
                required
              />
            </div>

            {/* Gender & Social Category */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Select
                label={language === 'hi' ? 'लिंग (Gender)' : 'Gender'}
                value={gender}
                onChange={(e) => setGender(e.target.value)}
                options={genderOptions}
              />

              <Select
                label={language === 'hi' ? 'सामाजिक श्रेणी' : 'Social Category / Caste'}
                value={casteCategory}
                onChange={(e) => setCasteCategory(e.target.value)}
                options={casteCategories}
              />
            </div>

            {/* State & District */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label={language === 'hi' ? 'राज्य (State)' : 'State of Residence'}
                placeholder="e.g. Uttar Pradesh or Maharashtra"
                value={stateName}
                onChange={(e) => setStateName(e.target.value)}
                required
              />

              <Input
                label={language === 'hi' ? 'जिला (District)' : 'District'}
                placeholder="e.g. Varanasi or Pune"
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

            {/* Occupation & Annual Income */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Select
                label={language === 'hi' ? 'व्यवसाय (Occupation)' : 'Primary Occupation'}
                value={occupation}
                onChange={(e) => setOccupation(e.target.value)}
                options={occupations}
              />

              <Input
                label={language === 'hi' ? 'वार्षिक पारिवारिक आय (₹)' : 'Annual Family Income (₹)'}
                type="number"
                placeholder="e.g. 120000"
                value={income}
                onChange={(e) => setIncome(e.target.value)}
                helperText="Total household annual earnings"
                required
              />
            </div>

            {/* Conditional Farmer Fields */}
            {occupation === 'farmer' && (
              <div className="p-4 rounded-2xl bg-sage-light/60 border border-sage/30 space-y-4">
                <span className="text-xs font-bold uppercase tracking-wider text-navy/70 block">
                  {language === 'hi' ? 'कृषि भूमि विवरण (Farmer Status & Landholding)' : 'Agricultural Landholding Details'}
                </span>

                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    id="is_landholder"
                    checked={isLandholdingFarmer}
                    onChange={(e) => setIsLandholdingFarmer(e.target.checked)}
                    className="w-4 h-4 rounded text-saffron focus:ring-saffron"
                  />
                  <label htmlFor="is_landholder" className="text-xs font-semibold text-navy">
                    {language === 'hi'
                      ? 'क्या आपके या आपके परिवार के नाम पर कृषि योग्य भूमि है?'
                      : 'Do you own cultivable agricultural land?'}
                  </label>
                </div>

                {isLandholdingFarmer && (
                  <Input
                    label={language === 'hi' ? 'कृषि भूमि का आकार (एकड़)' : 'Total Cultivable Land Owned (Acres)'}
                    type="number"
                    step="0.1"
                    placeholder="e.g. 1.5"
                    value={landHolding}
                    onChange={(e) => setLandHolding(e.target.value)}
                    helperText="1 acre ≈ 0.40 hectares (PM-KISAN/PM-KMY limit is 2.0 hectares / 5 acres)"
                  />
                )}
              </div>
            )}

            {/* Income Tax Payer Exclusion Checkbox */}
            <div className="flex items-center gap-3 pt-2">
              <input
                type="checkbox"
                id="is_taxpayer"
                checked={isTaxPayer}
                onChange={(e) => setIsTaxPayer(e.target.checked)}
                className="w-4 h-4 rounded text-saffron focus:ring-saffron"
              />
              <label htmlFor="is_taxpayer" className="text-xs text-navy/70">
                {language === 'hi'
                  ? 'क्या आपने या परिवार के किसी सदस्य ने पिछले वर्ष आयकर (Income Tax) का भुगतान किया?'
                  : 'Did you or any member of your household pay Income Tax in the last assessment year?'}
              </label>
            </div>
          </CardContent>

          <CardFooter className="p-6 bg-ivory/60 border-t border-navy/8 flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs text-navy/50">
              <ShieldCheck className="w-4 h-4 text-sage" />
              <span>Saved in Secure PostgreSQL Database</span>
            </div>

            <Button
              type="submit"
              variant="saffron"
              size="md"
              leftIcon={<Check className="w-4 h-4" />}
              isLoading={saving}
            >
              {language === 'hi' ? 'प्रोफ़ाइल सहेजें व आगे बढ़ें' : 'Save Profile & Continue'}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
};
