import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { useLanguage } from '@/context/LanguageContext';
import { Modal } from '@/components/common/Modal';
import { Button } from '@/components/common/Button';
import { Input } from '@/components/common/Input';
import { Badge } from '@/components/common/Badge';
import { isProfileComplete } from '@/types';
import { User, LogOut, CheckCircle2, ArrowRight, UserPlus, LogIn, AlertCircle } from 'lucide-react';
import { Link } from 'react-router-dom';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const LoginModal: React.FC<LoginModalProps> = ({ isOpen, onClose }) => {
  const { profile, isAuthenticated, login, register, logout } = useAuth();
  const { language } = useLanguage();
  const navigate = useNavigate();

  const [isRegisterMode, setIsRegisterMode] = useState<boolean>(false);
  const [fullName, setFullName] = useState<string>('');
  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState<string>('SecureCitizenPassword123!');
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const demoPersonas = [
    {
      name: 'Ramesh Kumar',
      email: 'ramesh.farmer@example.gov.in',
      role: language === 'hi' ? 'सीमांत किसान (वाराणसी, उ.प्र.)' : 'Marginal Farmer (Varanasi, UP)',
      category: 'OBC • Land 1.5 acres • Farmer',
      token: 'mock-ramesh-farmer-token',
    },
    {
      name: 'Priya Sharma',
      email: 'priya.student@example.gov.in',
      role: language === 'hi' ? 'कॉलेज छात्रा (जयपुर, राजस्थान)' : 'College Student (Jaipur, RJ)',
      category: 'General • NMMS / CSSS • Student',
      token: 'mock-priya-student-token',
    },
    {
      name: 'Anita Devi',
      email: 'anita.artisan@example.gov.in',
      role: language === 'hi' ? 'महिला उद्यमी / कारीगर (पटना, बिहार)' : 'Rural Artisan (Patna, BR)',
      category: 'SC • Vishwakarma • Artisan',
      token: 'mock-anita-artisan-token',
    },
  ];

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMessage(null);

    try {
      if (isRegisterMode) {
        const userEmail = email.includes('@') ? email : `citizen_${email}@example.gov.in`;
        await register({
          email: userEmail,
          password: password || 'SecureCitizenPassword123!',
          full_name: fullName || 'New Citizen',
        });
        onClose();
        // New user has incomplete profile -> redirect to onboarding
        navigate('/onboarding');
      } else {
        const userEmail = email.includes('@') ? email : (email ? `citizen_${email}@example.gov.in` : 'ramesh.farmer@example.gov.in');
        const p = await login({
          email: userEmail,
          password: password || 'SecureCitizenPassword123!',
        });
        onClose();
        if (!isProfileComplete(p)) {
          navigate('/onboarding');
        } else {
          navigate('/dashboard');
        }
      }
    } catch (err: any) {
      setErrorMessage(err?.message || (isRegisterMode ? 'Registration failed. User may already exist.' : 'Login failed. Please check credentials.'));
    } finally {
      setLoading(false);
    }
  };

  const handleQuickLogin = async (persona: typeof demoPersonas[0]) => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const p = await login({
        email: persona.email,
        password: 'SecureCitizenPassword123!',
        token: persona.token,
      });
      onClose();
      if (!isProfileComplete(p)) {
        navigate('/onboarding');
      } else {
        navigate('/dashboard');
      }
    } catch (err: any) {
      setErrorMessage(err?.message || 'Login failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-saffron-light flex items-center justify-center text-saffron-vibrant">
            <User className="w-4 h-4" />
          </div>
          <span>
            {isAuthenticated
              ? (language === 'hi' ? 'नागरिक खाता' : 'Citizen Account')
              : isRegisterMode
              ? (language === 'hi' ? 'नया नागरिक पंजीकरण (Register)' : 'New Citizen Registration')
              : (language === 'hi' ? 'नागरिक प्रवेश (Citizen Login)' : 'Citizen Access & Login')}
          </span>
        </div>
      }
    >
      {isAuthenticated && profile ? (
        <div className="space-y-5">
          <div className="p-4 rounded-2xl bg-ivory-100 border border-navy/10 flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-full bg-navy text-white flex items-center justify-center font-bold text-lg">
              {profile.full_name?.charAt(0) || 'C'}
            </div>
            <div className="space-y-0.5">
              <h4 className="font-bold text-navy text-base">{profile.full_name}</h4>
              <p className="text-xs text-navy/60">
                {profile.district || 'District'}, {profile.state || 'State'} • {profile.occupation || 'Citizen'}
              </p>
              <div className="pt-1">
                <Badge variant={isProfileComplete(profile) ? 'eligible' : 'category'}>
                  <CheckCircle2 className="w-3 h-3 mr-1" />
                  {isProfileComplete(profile)
                    ? (language === 'hi' ? 'सत्यापित पूर्ण प्रोफ़ाइल' : 'Complete Profile')
                    : (language === 'hi' ? 'अधूरी प्रोफ़ाइल' : 'Incomplete Profile')}
                </Badge>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="p-3 rounded-xl bg-white border border-navy/10 space-y-0.5">
              <span className="text-navy/50 uppercase tracking-wider text-[10px] font-semibold">
                {language === 'hi' ? 'वार्षिक आय' : 'Annual Income'}
              </span>
              <p className="font-bold text-navy">
                {profile.annual_family_income !== undefined && profile.annual_family_income !== null
                  ? `₹${Number(profile.annual_family_income).toLocaleString('en-IN')}`
                  : (language === 'hi' ? 'दर्ज नहीं' : 'Not set')}
              </p>
            </div>
            <div className="p-3 rounded-xl bg-white border border-navy/10 space-y-0.5">
              <span className="text-navy/50 uppercase tracking-wider text-[10px] font-semibold">
                {language === 'hi' ? 'आवास क्षेत्र' : 'Residence'}
              </span>
              <p className="font-bold text-navy capitalize">{profile.residence_type || (language === 'hi' ? 'दर्ज नहीं' : 'Not set')}</p>
            </div>
          </div>

          <div className="flex items-center gap-3 pt-2">
            <Link to="/onboarding" onClick={onClose} className="flex-1">
              <Button variant="primary" size="md" className="w-full" rightIcon={<ArrowRight className="w-4 h-4" />}>
                {language === 'hi' ? 'प्रोफ़ाइल संपादित करें' : 'Edit Full Profile'}
              </Button>
            </Link>

            <Button variant="outline" size="md" onClick={logout} leftIcon={<LogOut className="w-4 h-4" />}>
              {language === 'hi' ? 'लॉगआउट' : 'Logout'}
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Mode Switcher: Login vs Register */}
          <div className="flex rounded-xl bg-ivory-100 p-1 border border-navy/10">
            <button
              type="button"
              onClick={() => { setIsRegisterMode(false); setErrorMessage(null); }}
              className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-1.5 ${
                !isRegisterMode ? 'bg-navy text-white shadow-subtle' : 'text-navy/70 hover:text-navy'
              }`}
            >
              <LogIn className="w-3.5 h-3.5" />
              <span>{language === 'hi' ? 'लॉगिन (Login)' : 'Citizen Login'}</span>
            </button>
            <button
              type="button"
              onClick={() => { setIsRegisterMode(true); setErrorMessage(null); }}
              className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-1.5 ${
                isRegisterMode ? 'bg-navy text-white shadow-subtle' : 'text-navy/70 hover:text-navy'
              }`}
            >
              <UserPlus className="w-3.5 h-3.5" />
              <span>{language === 'hi' ? 'नया खाता (Register)' : 'New Registration'}</span>
            </button>
          </div>

          {errorMessage && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleFormSubmit} className="space-y-4">
            {isRegisterMode && (
              <Input
                label={language === 'hi' ? 'पूरा नाम' : 'Full Name'}
                placeholder="e.g. Ramesh Kumar"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
              />
            )}

            <Input
              label={language === 'hi' ? 'ईमेल या 10-अंकीय मोबाइल नंबर' : 'Email or 10-Digit Mobile Number'}
              placeholder="e.g. 9876543210 or citizen@example.gov.in"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />

            <Input
              label={language === 'hi' ? 'पासवर्ड' : 'Password'}
              type="password"
              placeholder="••••••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />

            <Button
              type="submit"
              variant="saffron"
              size="md"
              className="w-full mt-2"
              isLoading={loading}
              rightIcon={<ArrowRight className="w-4 h-4" />}
            >
              {isRegisterMode
                ? (language === 'hi' ? 'पंजीकरण करें और प्रोफ़ाइल बनाएं' : 'Register & Complete Profile')
                : (language === 'hi' ? 'सुरक्षित प्रवेश' : 'Secure Citizen Login')}
            </Button>
          </form>

          {/* Demo Personas for Instant Testing */}
          <div className="pt-2 border-t border-navy/8 space-y-3">
            <span className="text-[11px] font-bold uppercase tracking-wider text-navy/50 block">
              {language === 'hi' ? 'त्वरित डेमो परीक्षण प्रोफाइल' : 'Instant Demo Citizen Profiles'}
            </span>
            <div className="space-y-2">
              {demoPersonas.map((persona) => (
                <button
                  key={persona.email}
                  type="button"
                  onClick={() => handleQuickLogin(persona)}
                  disabled={loading}
                  className="w-full p-3 rounded-xl border border-navy/8 bg-ivory-50/70 hover:bg-white hover:border-saffron/40 hover:shadow-subtle transition-all duration-200 text-left flex items-center justify-between group"
                >
                  <div className="space-y-0.5">
                    <span className="font-bold text-xs text-navy group-hover:text-saffron-dark transition-colors block">
                      {persona.name}
                    </span>
                    <p className="text-[11px] text-navy/60">{persona.role}</p>
                    <span className="text-[10px] text-navy/40 font-medium">{persona.category}</span>
                  </div>
                  <ArrowRight className="w-4 h-4 text-navy/30 group-hover:text-saffron group-hover:translate-x-1 transition-all" />
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
};
