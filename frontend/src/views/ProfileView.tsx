import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { useLanguage } from '../context/LanguageContext';
import { useAuth } from '../context/AuthContext';
import { UserProfile, BeneficiaryProfile } from '../types';
import {
  User,
  Users,
  Plus,
  Trash2,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from 'lucide-react';

export const ProfileView: React.FC = () => {
  const { t, language, setLanguage } = useLanguage();
  const { user } = useAuth();

  const [, setProfile] = useState<UserProfile | null>(null);
  const [beneficiaries, setBeneficiaries] = useState<BeneficiaryProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileSuccess, setProfileSuccess] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);

  // Beneficiary modal
  const [showAddBenModal, setShowAddBenModal] = useState(false);
  const [benFullName, setBenFullName] = useState('');
  const [benRelationship, setBenRelationship] = useState<string>('spouse');
  const [benDob, setBenDob] = useState('');
  const [benGender, setBenGender] = useState('female');
  const [benState, setBenState] = useState('');
  const [benDistrict, setBenDistrict] = useState('');
  const [benResidenceType, setBenResidenceType] = useState('rural');
  const [benOccupation, setBenOccupation] = useState('');
  const [benIncome, setBenIncome] = useState('');
  const [savingBen, setSavingBen] = useState(false);
  const [benError, setBenError] = useState<string | null>(null);

  // Profile form state
  const [fullName, setFullName] = useState('');
  const [dob, setDob] = useState('');
  const [gender, setGender] = useState('');
  const [stateName, setStateName] = useState('');
  const [district, setDistrict] = useState('');
  const [residenceType, setResidenceType] = useState<string>('rural');
  const [occupation, setOccupation] = useState('');
  const [income, setIncome] = useState('');
  const [preferredLang, setPreferredLang] = useState<'hi' | 'en'>('hi');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [profData, benList] = await Promise.all([
        api.profile.get().catch(() => null),
        api.beneficiaries.list().catch(() => []),
      ]);

      if (profData) {
        setProfile(profData);
        setFullName(profData.full_name || '');
        setDob(profData.date_of_birth || '');
        setGender(profData.gender || '');
        setStateName(profData.state || '');
        setDistrict(profData.district || '');
        setResidenceType(profData.residence_type || 'rural');
        setOccupation(profData.occupation || '');
        setIncome(profData.annual_family_income ? String(profData.annual_family_income) : '');
        setPreferredLang(profData.preferred_language || 'hi');
      }
      setBeneficiaries(benList);
    } finally {
      setLoading(false);
    }
  };

  const handleProfileSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSavingProfile(true);
      setProfileError(null);
      setProfileSuccess(null);

      const updated = await api.profile.update({
        full_name: fullName.trim(),
        date_of_birth: dob || null,
        gender: gender || null,
        state: stateName.trim() || null,
        district: district.trim() || null,
        residence_type: (residenceType as any) || null,
        occupation: occupation.trim() || null,
        annual_family_income: income ? Number(income) : null,
        preferred_language: preferredLang,
      });

      setProfile(updated);
      setLanguage(preferredLang);
      setProfileSuccess(
        language === 'hi'
          ? 'प्रोफ़ाइल सफलतापूर्वक अपडेट हो गई!'
          : 'Profile updated successfully!'
      );
    } catch (err: any) {
      setProfileError(err?.response?.data?.message || 'Failed to update profile');
    } finally {
      setSavingProfile(false);
    }
  };

  const handleAddBeneficiary = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!benFullName.trim()) return;

    try {
      setSavingBen(true);
      setBenError(null);

      await api.beneficiaries.create({
        full_name: benFullName.trim(),
        relationship: benRelationship as any,
        date_of_birth: benDob || null,
        gender: benGender || null,
        state: benState.trim() || null,
        district: benDistrict.trim() || null,
        residence_type: (benResidenceType as any) || null,
        occupation: benOccupation.trim() || null,
        annual_family_income: benIncome ? Number(benIncome) : null,
      });

      setShowAddBenModal(false);
      setBenFullName('');
      setBenDob('');
      setBenOccupation('');
      setBenIncome('');

      const list = await api.beneficiaries.list();
      setBeneficiaries(list);
    } catch (err: any) {
      setBenError(err?.response?.data?.message || 'Failed to add family beneficiary');
    } finally {
      setSavingBen(false);
    }
  };

  const handleDeleteBeneficiary = async (benId: string) => {
    if (
      !window.confirm(
        language === 'hi'
          ? 'क्या आप इस परिवार के सदस्य को हटाना चाहते हैं?'
          : 'Are you sure you want to remove this family member?'
      )
    ) {
      return;
    }

    try {
      await api.beneficiaries.delete(benId);
      const list = await api.beneficiaries.list();
      setBeneficiaries(list);
    } catch {
      // Error handling
    }
  };

  if (loading) {
    return (
      <div className="py-20 flex justify-center">
        <Loader2 className="w-8 h-8 text-emerald-600 animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 pb-24 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900">{t('nav.profile')}</h1>
        <p className="text-slate-500 text-sm mt-1">
          {language === 'hi'
            ? 'अपनी और अपने परिवार के सदस्यों की सामाजिक-आर्थिक जानकारी प्रबंधित करें'
            : 'Manage socio-demographic criteria used by the transparent statutory eligibility engine'}
        </p>
      </div>

      {/* Account Holder Profile Form */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
        <div className="flex items-center space-x-3 pb-4 border-b border-slate-100">
          <div className="w-10 h-10 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold">
            <User className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-900">
              {language === 'hi' ? 'नागरिक खाता धारक प्रोफ़ाइल' : 'Account Holder Profile'}
            </h2>
            <p className="text-xs text-slate-500">{user?.email}</p>
          </div>
        </div>

        <form onSubmit={handleProfileSave} className="mt-6 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                {language === 'hi' ? 'पूरा नाम' : 'Full Name'} *
              </label>
              <input
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                {language === 'hi' ? 'जन्म तिथि' : 'Date of Birth (YYYY-MM-DD)'}
              </label>
              <input
                type="date"
                value={dob}
                onChange={(e) => setDob(e.target.value)}
                className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                {language === 'hi' ? 'लिंग' : 'Gender'}
              </label>
              <select
                value={gender}
                onChange={(e) => setGender(e.target.value)}
                className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                <option value="">{language === 'hi' ? '-- चयन करें --' : '-- Select --'}</option>
                <option value="male">{language === 'hi' ? 'पुरुष (Male)' : 'Male'}</option>
                <option value="female">{language === 'hi' ? 'महिला (Female)' : 'Female'}</option>
                <option value="transgender">{language === 'hi' ? 'ट्रांसजेंडर (Other)' : 'Transgender / Other'}</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                {language === 'hi' ? 'निवास क्षेत्र' : 'Residence Type'}
              </label>
              <select
                value={residenceType}
                onChange={(e) => setResidenceType(e.target.value)}
                className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                <option value="rural">{language === 'hi' ? 'ग्रामीण (Rural)' : 'Rural'}</option>
                <option value="urban">{language === 'hi' ? 'शहरी (Urban)' : 'Urban'}</option>
                <option value="semi_urban">{language === 'hi' ? 'अर्ध-शहरी (Semi-Urban)' : 'Semi-Urban'}</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                {language === 'hi' ? 'राज्य' : 'State'}
              </label>
              <input
                type="text"
                value={stateName}
                placeholder="e.g. Maharashtra, Uttar Pradesh"
                onChange={(e) => setStateName(e.target.value)}
                className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                {language === 'hi' ? 'ज़िला' : 'District'}
              </label>
              <input
                type="text"
                value={district}
                placeholder="e.g. Nagpur, Varanasi"
                onChange={(e) => setDistrict(e.target.value)}
                className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                {language === 'hi' ? 'व्यवसाय' : 'Occupation'}
              </label>
              <input
                type="text"
                value={occupation}
                placeholder="e.g. Small Farmer, Street Vendor, Laborer"
                onChange={(e) => setOccupation(e.target.value)}
                className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                {language === 'hi' ? 'वार्षिक पारिवारिक आय (₹)' : 'Annual Family Income (₹)'}
              </label>
              <input
                type="number"
                value={income}
                placeholder="e.g. 150000"
                onChange={(e) => setIncome(e.target.value)}
                className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                {language === 'hi' ? 'पसंदीदा भाषा' : 'Preferred Language'}
              </label>
              <select
                value={preferredLang}
                onChange={(e) => setPreferredLang(e.target.value as 'hi' | 'en')}
                className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                <option value="hi">हिंदी (Hindi)</option>
                <option value="en">English</option>
              </select>
            </div>
          </div>

          {profileError && (
            <div className="p-3 bg-red-50 text-red-700 rounded-xl text-xs flex items-center">
              <AlertCircle className="w-4 h-4 mr-2 flex-shrink-0" />
              <span>{profileError}</span>
            </div>
          )}

          {profileSuccess && (
            <div className="p-3 bg-emerald-50 text-emerald-800 rounded-xl text-xs flex items-center">
              <CheckCircle2 className="w-4 h-4 mr-2 flex-shrink-0" />
              <span>{profileSuccess}</span>
            </div>
          )}

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={savingProfile}
              className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-sm font-semibold transition disabled:opacity-50 flex items-center shadow-sm"
            >
              {savingProfile ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <CheckCircle2 className="w-4 h-4 mr-2" />
              )}
              {language === 'hi' ? 'प्रोफ़ाइल सहेजें' : 'Save Profile'}
            </button>
          </div>
        </form>
      </div>

      {/* Family Beneficiaries Section */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center font-bold">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">
                {language === 'hi' ? 'परिवार के सदस्य (Beneficiaries)' : 'Family Members & Beneficiaries'}
              </h2>
              <p className="text-xs text-slate-500">
                {language === 'hi'
                  ? 'परिवार के सदस्यों को जोड़ें ताकि उनके नाम पर योजनाओं की पात्रता जांची जा सके'
                  : 'Add family members to check scheme eligibility on their behalf without mixing criteria'}
              </p>
            </div>
          </div>

          <button
            onClick={() => setShowAddBenModal(true)}
            className="inline-flex items-center px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold transition shadow-sm"
          >
            <Plus className="w-4 h-4 mr-1.5" />
            {language === 'hi' ? 'सदस्य जोड़ें' : 'Add Member'}
          </button>
        </div>

        {beneficiaries.length === 0 ? (
          <div className="py-8 text-center text-slate-400">
            <Users className="w-10 h-10 mx-auto mb-2 opacity-50" />
            <p className="text-sm font-medium">
              {language === 'hi'
                ? 'कोई परिवार सदस्य नहीं जोड़ा गया है'
                : 'No family beneficiaries added yet'}
            </p>
            <p className="text-xs text-slate-400 mt-1">
              {language === 'hi'
                ? 'माता-पिता, जीवनसाथी या बच्चों को जोड़ने के लिए ऊपर दिए बटन पर क्लिक करें'
                : 'Add family members to evaluate pensions, scholarships, or maternal welfare schemes'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {beneficiaries.map((b) => (
              <div
                key={b.id}
                className="p-4 rounded-xl border border-slate-200 bg-slate-50/60 hover:bg-white transition flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <h4 className="text-base font-bold text-slate-900">{b.full_name}</h4>
                    <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-blue-100 text-blue-800 capitalize">
                      {b.relationship}
                    </span>
                  </div>

                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600">
                    <div>
                      <span className="font-semibold text-slate-800">
                        {language === 'hi' ? 'जन्म तिथि: ' : 'DOB: '}
                      </span>
                      {b.date_of_birth || (language === 'hi' ? 'दर्ज नहीं' : 'Not recorded')}
                    </div>
                    <div>
                      <span className="font-semibold text-slate-800">
                        {language === 'hi' ? 'लिंग: ' : 'Gender: '}
                      </span>
                      {b.gender || '—'}
                    </div>
                    <div>
                      <span className="font-semibold text-slate-800">
                        {language === 'hi' ? 'राज्य: ' : 'State: '}
                      </span>
                      {b.state || '—'}
                    </div>
                    <div>
                      <span className="font-semibold text-slate-800">
                        {language === 'hi' ? 'व्यवसाय: ' : 'Occupation: '}
                      </span>
                      {b.occupation || '—'}
                    </div>
                  </div>
                </div>

                <div className="pt-3 mt-3 border-t border-slate-200 flex justify-end">
                  <button
                    onClick={() => handleDeleteBeneficiary(b.id)}
                    className="text-xs font-semibold text-red-600 hover:text-red-700 flex items-center"
                  >
                    <Trash2 className="w-3.5 h-3.5 mr-1" />
                    {language === 'hi' ? 'सदस्य हटाएं' : 'Remove Member'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add Beneficiary Modal */}
      {showAddBenModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl space-y-4 max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-bold text-slate-900">
              {language === 'hi' ? 'परिवार के सदस्य को जोड़ें' : 'Add Family Beneficiary'}
            </h3>

            <form onSubmit={handleAddBeneficiary} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  {language === 'hi' ? 'पूरा नाम' : 'Full Name'} *
                </label>
                <input
                  type="text"
                  required
                  value={benFullName}
                  onChange={(e) => setBenFullName(e.target.value)}
                  className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    {language === 'hi' ? 'संबंध' : 'Relationship'} *
                  </label>
                  <select
                    value={benRelationship}
                    onChange={(e) => setBenRelationship(e.target.value)}
                    className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  >
                    <option value="father">{language === 'hi' ? 'पिता (Father)' : 'Father'}</option>
                    <option value="mother">{language === 'hi' ? 'माता (Mother)' : 'Mother'}</option>
                    <option value="spouse">{language === 'hi' ? 'जीवनसाथी (Spouse)' : 'Spouse'}</option>
                    <option value="son">{language === 'hi' ? 'बेटा (Son)' : 'Son'}</option>
                    <option value="daughter">{language === 'hi' ? 'बेटी (Daughter)' : 'Daughter'}</option>
                    <option value="sibling">{language === 'hi' ? 'भाई / बहन (Sibling)' : 'Sibling'}</option>
                    <option value="guardian">{language === 'hi' ? 'अभिभावक (Guardian)' : 'Guardian'}</option>
                    <option value="other">{language === 'hi' ? 'अन्य (Other)' : 'Other'}</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    {language === 'hi' ? 'जन्म तिथि' : 'Date of Birth'}
                  </label>
                  <input
                    type="date"
                    value={benDob}
                    onChange={(e) => setBenDob(e.target.value)}
                    className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    {language === 'hi' ? 'लिंग' : 'Gender'}
                  </label>
                  <select
                    value={benGender}
                    onChange={(e) => setBenGender(e.target.value)}
                    className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  >
                    <option value="male">{language === 'hi' ? 'पुरुष (Male)' : 'Male'}</option>
                    <option value="female">{language === 'hi' ? 'महिला (Female)' : 'Female'}</option>
                    <option value="transgender">{language === 'hi' ? 'अन्य (Other)' : 'Other'}</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    {language === 'hi' ? 'निवास क्षेत्र' : 'Residence Type'}
                  </label>
                  <select
                    value={benResidenceType}
                    onChange={(e) => setBenResidenceType(e.target.value)}
                    className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  >
                    <option value="rural">{language === 'hi' ? 'ग्रामीण (Rural)' : 'Rural'}</option>
                    <option value="urban">{language === 'hi' ? 'शहरी (Urban)' : 'Urban'}</option>
                    <option value="semi_urban">{language === 'hi' ? 'अर्ध-शहरी (Semi-Urban)' : 'Semi-Urban'}</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    {language === 'hi' ? 'राज्य' : 'State'}
                  </label>
                  <input
                    type="text"
                    value={benState}
                    onChange={(e) => setBenState(e.target.value)}
                    className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    {language === 'hi' ? 'ज़िला' : 'District'}
                  </label>
                  <input
                    type="text"
                    value={benDistrict}
                    onChange={(e) => setBenDistrict(e.target.value)}
                    className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    {language === 'hi' ? 'व्यवसाय' : 'Occupation'}
                  </label>
                  <input
                    type="text"
                    value={benOccupation}
                    onChange={(e) => setBenOccupation(e.target.value)}
                    className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    {language === 'hi' ? 'वार्षिक आय (₹)' : 'Annual Income (₹)'}
                  </label>
                  <input
                    type="number"
                    value={benIncome}
                    onChange={(e) => setBenIncome(e.target.value)}
                    className="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
              </div>

              {benError && (
                <div className="p-3 bg-red-50 text-red-700 rounded-xl text-xs flex items-center">
                  <AlertCircle className="w-4 h-4 mr-2 flex-shrink-0" />
                  <span>{benError}</span>
                </div>
              )}

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddBenModal(false)}
                  disabled={savingBen}
                  className="px-4 py-2 border border-slate-300 text-slate-700 rounded-xl text-xs font-semibold hover:bg-slate-50 transition"
                >
                  {language === 'hi' ? 'रद्द करें' : 'Cancel'}
                </button>
                <button
                  type="submit"
                  disabled={savingBen}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold transition disabled:opacity-50 flex items-center shadow-sm"
                >
                  {savingBen ? (
                    <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                  ) : (
                    <Plus className="w-3.5 h-3.5 mr-1.5" />
                  )}
                  {language === 'hi' ? 'जोड़ें' : 'Add Beneficiary'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
