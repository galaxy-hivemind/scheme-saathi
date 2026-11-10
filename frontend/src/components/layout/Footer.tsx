import React from 'react';
import { useLanguage } from '@/context/LanguageContext';
import { ShieldCheck, Info } from 'lucide-react';

export const Footer: React.FC = () => {
  const { language } = useLanguage();

  return (
    <footer className="bg-navy text-ivory/70 text-xs py-14 mt-20 border-t border-navy-800 pb-28 md:pb-14">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
        {/* Important Disclaimer Card */}
        <div className="bg-navy-900/80 rounded-2xl p-6 border border-white/8 flex flex-col sm:flex-row items-start gap-4">
          <div className="p-2 rounded-xl bg-saffron/15 text-saffron shrink-0">
            <Info className="w-5 h-5" />
          </div>
          <div className="space-y-1.5">
            <h5 className="font-semibold text-white text-sm">
              {language === 'hi' ? 'नागरिक सूचना व निष्पक्षता गारंटी' : 'Citizen Transparency & Independence Notice'}
            </h5>
            <p className="leading-relaxed text-ivory/70 text-xs max-w-4xl">
              {language === 'hi'
                ? 'योजना साथी एक स्वतंत्र व निष्पक्ष AI-मार्गदर्शक मंच है, जिसे भारतीय नागरिकों को सरकारी योजनाओं की खोज व आवेदन प्रक्रिया में सहायता देने हेतु तैयार किया गया है। यह मंच किसी सरकारी मंत्रालय का आधिकारिक पोर्टल नहीं है। सभी पात्रता मानदंड व प्रक्रियाएं आधिकारिक सरकारी स्रोतों (जैसे myscheme.gov.in) पर आधारित हैं।'
                : 'Scheme Saathi is an independent welfare assistance platform designed to guide Indian citizens through discovery, deterministic eligibility evaluation, and application drafting. It is not an official government portal. All eligibility outcomes are evaluated via deterministic rules derived from published scheme guidelines.'}
            </p>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-6 border-t border-white/8 text-ivory/55">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-sage" />
            <span>Deterministic Rule Verification • Strict Citizen Privacy</span>
          </div>
          <p>© {new Date().getFullYear()} Scheme Saathi (योजना साथी) • Built with care for Indian Citizens</p>
        </div>
      </div>
    </footer>
  );
};
