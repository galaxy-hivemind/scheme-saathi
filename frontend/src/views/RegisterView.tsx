import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { Sparkles, Mail, Lock, User, AlertCircle, Loader2 } from 'lucide-react';

export const RegisterView: React.FC = () => {
  const { register } = useAuth();
  const { t, language } = useLanguage();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [preferredLang, setPreferredLang] = useState<'hi' | 'en'>(language);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await register({
        full_name: fullName.trim(),
        email: email.trim(),
        password,
        preferred_language: preferredLang,
      });
      navigate('/');
    } catch (err: any) {
      console.error('Registration error:', err);
      const detail = err.response?.data?.error?.message || err.response?.data?.detail || 'पंजीकरण विफल रहा / Registration failed';
      setError(detail);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center p-4 bg-gradient-to-b from-orange-50/50 via-slate-50 to-emerald-50/30">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl border border-slate-200/80 p-6 sm:p-8">
        <div className="flex flex-col items-center mb-6 text-center">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-amber-500 via-orange-600 to-green-600 flex items-center justify-center text-white shadow-lg shadow-orange-500/20 mb-3">
            <Sparkles className="w-7 h-7" />
          </div>
          <h1 className="text-xl font-extrabold text-slate-900 tracking-tight">
            {language === 'hi' ? 'नया नागरिक खाता बनाएं' : 'Create Citizen Account'}
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            {language === 'hi' ? 'सभी केंद्रीय सरकारी योजनाओं की जानकारी एक स्थान पर' : 'Access central welfare schemes in one place'}
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-start space-x-2 text-rose-700 text-xs">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              {t('auth.full_name')}
            </label>
            <div className="relative">
              <User className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="उदा. रमेश कुमार / Ramesh Kumar"
                className="w-full pl-9 pr-3.5 py-2.5 text-sm rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-600 transition-colors bg-slate-50/50"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              {t('auth.email')}
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="citizen@example.gov.in"
                className="w-full pl-9 pr-3.5 py-2.5 text-sm rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-600 transition-colors bg-slate-50/50"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              {t('auth.password')}
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="कम से कम 8 अक्षर / Min. 8 characters"
                className="w-full pl-9 pr-3.5 py-2.5 text-sm rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-600 transition-colors bg-slate-50/50"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              {t('auth.preferred_language')}
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setPreferredLang('hi')}
                className={`py-2 px-3 text-xs font-semibold rounded-xl border transition-all ${
                  preferredLang === 'hi'
                    ? 'border-orange-600 bg-orange-50 text-orange-700'
                    : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                }`}
              >
                हिन्दी (Hindi)
              </button>
              <button
                type="button"
                onClick={() => setPreferredLang('en')}
                className={`py-2 px-3 text-xs font-semibold rounded-xl border transition-all ${
                  preferredLang === 'en'
                    ? 'border-orange-600 bg-orange-50 text-orange-700'
                    : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                }`}
              >
                English
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-orange-600 to-orange-500 hover:from-orange-700 hover:to-orange-600 text-white font-semibold text-sm shadow-md shadow-orange-500/20 transition-all flex items-center justify-center space-x-2 disabled:opacity-50"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>खाता बनाया जा रहा है... / Creating account...</span>
              </>
            ) : (
              <span>{t('auth.btn_register')}</span>
            )}
          </button>
        </form>

        <div className="mt-6 pt-5 border-t border-slate-100 text-center">
          <Link
            to="/login"
            className="text-xs font-semibold text-orange-600 hover:text-orange-700 hover:underline"
          >
            {t('auth.has_account')}
          </Link>
        </div>
      </div>
    </div>
  );
};
