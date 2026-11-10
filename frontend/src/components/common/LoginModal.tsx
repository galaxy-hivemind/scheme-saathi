import React, { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useLanguage } from '@/context/LanguageContext';
import { Modal } from '@/components/common/Modal';
import { Button } from '@/components/common/Button';
import { Input } from '@/components/common/Input';
import { Badge } from '@/components/common/Badge';
import { User, Phone, ShieldCheck, LogOut, CheckCircle2, Sparkles, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const LoginModal: React.FC<LoginModalProps> = ({ isOpen, onClose }) => {
  const { profile, isAuthenticated, login, logout } = useAuth();
  const { language } = useLanguage();
  const [mobile, setMobile] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);

  const demoPersonas = [
    {
      name: 'Ramesh Kumar',
      role: language === 'hi' ? 'सीमांत किसान (वाराणसी, उ.प्र.)' : 'Marginal Farmer (Varanasi, UP)',
      category: 'OBC • Land 1.5 acres',
      token: 'mock-ramesh-farmer-token',
    },
    {
      name: 'Priya Sharma',
      role: language === 'hi' ? 'कॉलेज छात्रा (जयपुर, राजस्थान)' : 'College Student (Jaipur, RJ)',
      category: 'General • NMMS Eligible',
      token: 'mock-priya-student-token',
    },
    {
      name: 'Anita Devi',
      role: language === 'hi' ? 'महिला उद्यमी / कारीगर (पटना, बिहार)' : 'Rural Artisan (Patna, BR)',
      category: 'SC • PMAY-G Candidate',
      token: 'mock-anita-artisan-token',
    },
  ];

  const handlePhoneSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!otpSent) {
      if (mobile.length >= 10) {
        setOtpSent(true);
      }
    } else {
      setLoading(true);
      await login();
      setLoading(false);
      onClose();
    }
  };

  const handleQuickLogin = async (token: string) => {
    setLoading(true);
    await login(token);
    setLoading(false);
    onClose();
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
          <span>{isAuthenticated ? (language === 'hi' ? 'नागरिक खाता' : 'Citizen Account') : (language === 'hi' ? 'नागरिक प्रवेश (Citizen Login)' : 'Citizen Access & Login')}</span>
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
                {profile.district}, {profile.state} • {profile.occupation}
              </p>
              <div className="pt-1">
                <Badge variant="eligible">
                  <CheckCircle2 className="w-3 h-3 mr-1" />
                  {language === 'hi' ? 'सत्यापित नागरिक' : 'Active Citizen'}
                </Badge>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="p-3 rounded-xl bg-white border border-navy/10 space-y-0.5">
              <span className="text-navy/50 uppercase tracking-wider text-[10px] font-semibold">
                {language === 'hi' ? 'वार्षिक आय' : 'Annual Income'}
              </span>
              <p className="font-bold text-navy">₹{profile.annual_family_income?.toLocaleString('en-IN') || '1,20,000'}</p>
            </div>
            <div className="p-3 rounded-xl bg-white border border-navy/10 space-y-0.5">
              <span className="text-navy/50 uppercase tracking-wider text-[10px] font-semibold">
                {language === 'hi' ? 'आवास क्षेत्र' : 'Residence'}
              </span>
              <p className="font-bold text-navy capitalize">{profile.residence_type || 'Rural'}</p>
            </div>
          </div>

          <div className="flex items-center gap-3 pt-2">
            <Link to="/onboarding" onClick={onClose} className="flex-1">
              <Button variant="primary" size="md" className="w-full" rightIcon={<ArrowRight className="w-4 h-4" />}>
                {language === 'hi' ? 'प्रोफ़ाइल संपादित करें' : 'Edit Full Profile'}
              </Button>
            </Link>
            <Button
              variant="outline"
              size="md"
              onClick={() => {
                logout();
                onClose();
              }}
              leftIcon={<LogOut className="w-4 h-4 text-rose-600" />}
            >
              {language === 'hi' ? 'लॉगआउट' : 'Logout'}
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-5">
          <p className="text-xs text-navy/60 leading-relaxed">
            {language === 'hi'
              ? 'अपने मोबाइल नंबर से सुरक्षित प्रवेश करें या तुरंत परीक्षण हेतु डेमो नागरिक प्रोफ़ाइल चुनें।'
              : 'Sign in securely with your mobile number or select a pre-configured demo citizen persona.'}
          </p>

          <form onSubmit={handlePhoneSubmit} className="space-y-3">
            <Input
              label={language === 'hi' ? 'मोबाइल नंबर (Mobile Number)' : 'Mobile Phone Number'}
              placeholder="e.g. 9876543210"
              value={mobile}
              onChange={(e) => setMobile(e.target.value)}
              leftIcon={<Phone className="w-4 h-4" />}
              maxLength={10}
              required
            />
            {otpSent && (
              <Input
                label={language === 'hi' ? 'ओटीपी दर्ज करें (Enter OTP)' : 'One-Time Password (OTP)'}
                placeholder="Enter 123456"
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                helperText="Demo mode: Enter any 6 digits (e.g. 123456)"
                required
              />
            )}
            <Button
              type="submit"
              variant="saffron"
              size="md"
              className="w-full"
              isLoading={loading}
            >
              {otpSent
                ? (language === 'hi' ? 'सत्यापित करें व प्रवेश करें' : 'Verify & Sign In')
                : (language === 'hi' ? 'ओटीपी प्राप्त करें' : 'Send OTP')}
            </Button>
          </form>

          <div className="relative flex py-1 items-center">
            <div className="flex-grow border-t border-navy/10"></div>
            <span className="flex-shrink mx-3 text-[11px] text-navy/40 uppercase font-semibold">
              {language === 'hi' ? 'या डेमो प्रोफाइल चुनें' : 'Or quick demo login'}
            </span>
            <div className="flex-grow border-t border-navy/10"></div>
          </div>

          <div className="space-y-2">
            {demoPersonas.map((persona, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleQuickLogin(persona.token)}
                className="w-full text-left p-3 rounded-xl bg-ivory-50 hover:bg-white border border-navy/10 hover:border-saffron/40 hover:shadow-subtle transition-all duration-200 flex items-center justify-between group"
              >
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-xs text-navy group-hover:text-saffron-vibrant transition-colors">
                      {persona.name}
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-navy/5 text-navy/70">
                      {persona.category}
                    </span>
                  </div>
                  <p className="text-[11px] text-navy/60">{persona.role}</p>
                </div>
                <Sparkles className="w-4 h-4 text-navy/30 group-hover:text-saffron-vibrant transition-colors shrink-0" />
              </button>
            ))}
          </div>

          <div className="pt-2 text-center">
            <p className="text-[11px] text-navy/40 flex items-center justify-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5 text-sage" />
              <span>Strict Citizen Privacy • No spam or data disclosure</span>
            </p>
          </div>
        </div>
      )}
    </Modal>
  );
};
