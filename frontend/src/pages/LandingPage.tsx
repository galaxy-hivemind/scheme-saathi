import React from 'react';
import { Link } from 'react-router-dom';
import { useLanguage } from '@/context/LanguageContext';
import {
  Search,
  Check,
  CheckCircle2,
  Users,
  ShieldCheck,
  Zap,
  GraduationCap,
  Home,
  Sprout,
  FileText,
  Rocket,
  ArrowRight,
  Sparkles,
} from 'lucide-react';

export const LandingPage: React.FC = () => {
  const { language } = useLanguage();

  return (
    <div className="space-y-10 sm:space-y-14 py-1 sm:py-3">
      {/* =========================================================================
          HERO SECTION — EXACT BLUEPRINT REPLICATION OF APPROVED REFERENCE IMAGE
      ========================================================================== */}
      <section className="relative overflow-hidden pt-2 pb-4 sm:pb-6 flex flex-col justify-center">
        {/* =======================================================================
            DECORATIVE BACKGROUND — EXACT REPLICATION FROM APPROVED REFERENCE:
            1. Warm Ambient Background (Soft Ivory base with Saffron/Amber radial halo)
            2. Large Deep-Navy Circular Element with Golden Rim & Star Sparkles
            3. Delicate Light-Saffron 24-spoke Ashoka Chakra Watermark
            4. Subtle Warm-Golden Indian Heritage Silhouette (Taj Mahal)
            5. Flowing Indian Tricolour Ribbons (Saffron, White, Deep Green)
        ======================================================================== */}
        <div className="hidden lg:block absolute right-0 top-0 bottom-0 w-[58%] pointer-events-none overflow-hidden select-none z-0">
          {/* 1. Warm Ambient Background: Soft Ivory base with Saffron / Orange radial lighting */}
          <div className="absolute right-0 -top-10 w-[540px] h-[540px] rounded-full bg-[radial-gradient(ellipse_at_70%_25%,rgba(245,210,165,0.7)_0%,rgba(248,235,215,0.38)_40%,rgba(248,246,240,0)_70%)] pointer-events-none opacity-85" />

          {/* 2. Ashoka Chakra: Large, delicate, light-saffron watermark in upper-right background */}
          <div className="absolute -right-10 -top-10 sm:-right-12 sm:-top-12 w-84 h-84 sm:w-96 sm:h-96 pointer-events-none opacity-[0.38] text-[#DF9145]">
            <svg
              className="w-full h-full animate-chakra-spin"
              viewBox="0 0 200 200"
              fill="none"
              stroke="currentColor"
            >
              {/* Outer decorative rim with 24 dots */}
              <circle cx="100" cy="100" r="95" strokeWidth="1.2" strokeDasharray="3 3" />
              <circle cx="100" cy="100" r="90" strokeWidth="2" />
              <circle cx="100" cy="100" r="85" strokeWidth="0.8" />
              {/* Inner Hub */}
              <circle cx="100" cy="100" r="22" strokeWidth="1.8" />
              <circle cx="100" cy="100" r="14" fill="currentColor" fillOpacity="0.22" strokeWidth="0.8" />
              <circle cx="100" cy="100" r="5" fill="currentColor" />
              {/* 24 Evenly Spaced Radiating Spokes */}
              {Array.from({ length: 24 }).map((_, i) => {
                const angle = (i * 15 * Math.PI) / 180;
                return (
                  <g key={i}>
                    <line
                      x1={100 + 22 * Math.cos(angle)}
                      y1={100 + 22 * Math.sin(angle)}
                      x2={100 + 85 * Math.cos(angle)}
                      y2={100 + 85 * Math.sin(angle)}
                      strokeWidth="1.3"
                    />
                    <circle
                      cx={100 + 88 * Math.cos(angle + 0.13)}
                      cy={100 + 88 * Math.sin(angle + 0.13)}
                      r="1.2"
                      fill="currentColor"
                    />
                  </g>
                );
              })}
            </svg>
          </div>

          {/* 3. Indian Heritage Silhouette: Warm-golden Taj Mahal architectural silhouette on far right */}
          <div className="absolute right-0 top-24 w-80 h-56 pointer-events-none opacity-45 text-[#DF9145]">
            <svg
              className="w-full h-full"
              viewBox="0 0 420 240"
              fill="currentColor"
            >
              {/* Central Bulbous Onion Dome with Finial */}
              <path d="M210 28 L210 12 M207 20 L213 20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              <circle cx="210" cy="24" r="3.5" />
              <path d="M185 88 C 185 46, 210 32, 210 32 C 210 32, 235 46, 235 88 Z" opacity="0.9" />
              <rect x="187" y="88" width="46" height="12" rx="1" opacity="0.8" />
              
              {/* Main Central Grand Iwan */}
              <path d="M148 100 L 272 100 L 272 205 L 148 205 Z" opacity="0.45" />
              <path d="M182 205 L 182 145 C 182 125, 210 115, 210 115 C 210 115, 238 125, 238 145 L 238 205 Z" fill="#F8F6F0" opacity="0.95" />
              <path d="M188 205 L 188 152 C 188 138, 210 128, 210 128 C 210 128, 232 138, 232 152 L 232 205 Z" opacity="0.6" />

              {/* Side Wings and Chhatris */}
              <path d="M162 76 C 162 60, 172 52, 172 52 C 172 52, 182 60, 182 76 Z" opacity="0.8" />
              <rect x="165" y="76" width="14" height="18" opacity="0.6" />
              <path d="M238 76 C 238 60, 248 52, 248 52 C 248 52, 258 60, 258 76 Z" opacity="0.8" />
              <rect x="241" y="76" width="14" height="18" opacity="0.6" />

              {/* Outer Minarets */}
              <rect x="86" y="82" width="10" height="123" opacity="0.55" />
              <rect x="83" y="122" width="16" height="4" rx="1" opacity="0.75" />
              <path d="M85 82 C 85 70, 91 64, 91 64 C 91 64, 97 70, 97 82 Z" opacity="0.85" />
              <rect x="324" y="82" width="10" height="123" opacity="0.55" />
              <rect x="321" y="122" width="16" height="4" rx="1" opacity="0.75" />
              <path d="M323 82 C 323 70, 329 64, 329 64 C 329 64, 335 70, 335 82 Z" opacity="0.85" />
              <rect x="25" y="205" width="370" height="15" rx="2" opacity="0.5" />
            </svg>
          </div>

          {/* 4. Flowing Indian Tricolour Ribbons: Saffron (top), White (middle), Deep Green (bottom) */}
          {/* Enters from lower central area and sweeps smoothly towards the right edge */}
          <div className="absolute left-0 right-0 bottom-0 w-full h-[220px] pointer-events-none z-0 animate-ribbon-flow">
            <svg
              className="w-full h-full"
              viewBox="0 0 580 220"
              fill="none"
              preserveAspectRatio="none"
            >
              <defs>
                {/* Indian Saffron Gradient with smooth entrance fade */}
                <linearGradient id="saffronGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#FFA726" stopOpacity="0" />
                  <stop offset="6%" stopColor="#FFA726" stopOpacity="0.85" />
                  <stop offset="25%" stopColor="#FB8C00" stopOpacity="1" />
                  <stop offset="100%" stopColor="#E65100" stopOpacity="0.95" />
                </linearGradient>

                {/* Central White Ribbon Gradient */}
                <linearGradient id="whiteGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0" />
                  <stop offset="6%" stopColor="#FFFFFF" stopOpacity="0.9" />
                  <stop offset="25%" stopColor="#FFFFFF" stopOpacity="1" />
                  <stop offset="100%" stopColor="#F8F6F0" stopOpacity="0.98" />
                </linearGradient>

                {/* India Green Gradient */}
                <linearGradient id="greenGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#43A047" stopOpacity="0" />
                  <stop offset="6%" stopColor="#43A047" stopOpacity="0.85" />
                  <stop offset="25%" stopColor="#2E7D32" stopOpacity="1" />
                  <stop offset="100%" stopColor="#1B5E20" stopOpacity="0.95" />
                </linearGradient>

                {/* Soft depth shadow filter */}
                <filter id="ribbonDepthShadow" x="-5%" y="-5%" width="110%" height="110%">
                  <feDropShadow dx="0" dy="3" stdDeviation="4" floodColor="#172B45" floodOpacity="0.10" />
                </filter>
              </defs>

              {/* Saffron Ribbon (Top) */}
              <path
                d="M 0 150 C 45 138, 125 128, 275 142 C 365 137, 455 62, 580 -5 L 580 15 C 455 82, 365 157, 275 162 C 145 163, 55 153, 0 152 Z"
                fill="url(#saffronGradient)"
                filter="url(#ribbonDepthShadow)"
              />

              {/* White Ribbon (Middle) */}
              <path
                d="M 0 152 C 55 153, 145 163, 275 162 C 365 157, 455 82, 580 15 L 580 34 C 455 101, 365 176, 275 181 C 145 182, 55 153, 0 152 Z"
                fill="url(#whiteGradient)"
                filter="url(#ribbonDepthShadow)"
              />

              {/* India Green Ribbon (Bottom) */}
              <path
                d="M 0 152 C 55 153, 145 182, 275 181 C 365 176, 455 101, 580 34 L 580 60 C 455 127, 365 202, 275 207 C 135 208, 45 166, 0 154 Z"
                fill="url(#greenGradient)"
                filter="url(#ribbonDepthShadow)"
              />
            </svg>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-6 items-center w-full">
          {/* ===================================================================
              LEFT HERO COLUMN: Badge, Headline, Subtitle, Dual CTAs, Stats
          ==================================================================== */}
          <div className="lg:col-span-6 space-y-6 sm:space-y-6.5 animate-fade-in-up">
            {/* 1. Pill Badge */}
            <div className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-[#FDF3E7] border border-[#F5D8B8] text-[#D99548] text-xs font-semibold shadow-2xs">
              <span className="text-[#E67E22] text-sm">✦</span>
              <span>
                {language === 'hi' ? 'आपकी भलाई, हमारी प्राथमिकता' : 'Your Welfare, Our Priority'}
              </span>
            </div>

            {/* 2. Main Headline: Exact 3-line Serif Display */}
            <h1 className="font-editorial text-4xl sm:text-5xl lg:text-[3.5rem] font-bold tracking-tight text-[#172B45] leading-[1.08]">
              {language === 'hi' ? (
                <>
                  योजना खोज से लेकर <br />
                  <span className="text-[#E08528]">आवेदन की तैयारी तक.</span>
                </>
              ) : (
                <>
                  From Scheme <br />
                  Discovery to <br />
                  <span className="text-[#E08528]">Application Readiness.</span>
                </>
              )}
            </h1>

            {/* 3. Supporting Text */}
            <p className="text-base sm:text-lg text-[#172B45]/80 max-w-lg leading-relaxed font-normal">
              {language === 'hi' ? (
                <>
                  सरकारी योजनाओं की खोज करें, अपनी पात्रता समझें और अपने{' '}
                  <strong className="text-[#172B45] font-bold">आवेदन तैयार करें</strong> — सब कुछ एक
                  ही सरल स्थान पर।
                </>
              ) : (
                <>
                  Discover government schemes, understand your eligibility and{' '}
                  <strong className="text-[#172B45] font-bold">prepare your applications</strong> —
                  all in one simple place.
                </>
              )}
            </p>

            {/* 4. Dual CTA Buttons */}
            <div className="flex flex-wrap items-center gap-4 pt-1">
              {/* Primary CTA: Warm Saffron-Orange Pill Button */}
              <Link to="/schemes" className="group">
                <button className="bg-[#E67E22] hover:bg-[#D35400] text-white rounded-full px-7 py-3.5 font-bold text-sm shadow-[0_4px_16px_rgba(230,126,34,0.35)] hover:shadow-[0_6px_22px_rgba(230,126,34,0.45)] transition-all duration-200 flex items-center gap-2.5 active:scale-98 cursor-pointer">
                  <Search className="w-4 h-4 text-white" />
                  <span>{language === 'hi' ? 'योजनाएं खोजें →' : 'Explore Schemes →'}</span>
                </button>
              </Link>

              {/* Secondary CTA: White Pill with Navy Border */}
              <Link to="/schemes">
                <button className="bg-white hover:bg-[#F8F6F0] text-[#172B45] border-2 border-[#172B45] rounded-full px-6 py-3.5 font-bold text-sm transition-all duration-200 flex items-center gap-2 active:scale-98 cursor-pointer shadow-subtle">
                  <Check className="w-4 h-4 text-[#172B45] stroke-[3]" />
                  <span>{language === 'hi' ? 'पात्रता जांचें' : 'Check Eligibility'}</span>
                </button>
              </Link>
            </div>

            {/* 5. Statistics Section */}
            <div className="pt-6 border-t border-[#172B45]/10 flex flex-wrap items-center gap-7 sm:gap-9 text-xs">
              {/* Stat 1: 10Cr+ */}
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-[#172B45]/5 text-[#172B45] flex items-center justify-center shrink-0">
                  <Users className="w-5 h-5 text-[#172B45]" />
                </div>
                <div>
                  <div className="font-extrabold text-[#172B45] text-sm leading-none">10Cr+</div>
                  <span className="text-[#172B45]/60 text-[11px]">
                    {language === 'hi' ? 'सहायता प्राप्त नागरिक' : 'Citizens Helped'}
                  </span>
                </div>
              </div>

              {/* Stat 2: 100+ Schemes */}
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-[#172B45]/5 text-[#172B45] flex items-center justify-center shrink-0">
                  <ShieldCheck className="w-5 h-5 text-[#172B45]" />
                </div>
                <div>
                  <div className="font-extrabold text-[#172B45] text-sm leading-none">100+</div>
                  <span className="text-[#172B45]/60 text-[11px]">
                    {language === 'hi' ? 'सरकारी योजनाएं' : 'Schemes'}
                  </span>
                </div>
              </div>

              {/* Stat 3: Fast & Easy */}
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-[#172B45]/5 text-[#172B45] flex items-center justify-center shrink-0">
                  <Zap className="w-5 h-5 text-[#172B45]" />
                </div>
                <div>
                  <div className="font-extrabold text-[#172B45] text-sm leading-none">
                    {language === 'hi' ? 'तेज़ व सरल' : 'Fast & Easy'}
                  </div>
                  <span className="text-[#172B45]/60 text-[11px]">
                    {language === 'hi' ? 'कुछ ही मिनटों में' : 'in Just Minutes'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* ===================================================================
              RIGHT HERO COLUMN: Layered Floating Scheme Cards & Readiness Panel
              (Exact Blueprint Replication from Approved Reference Image)
          ==================================================================== */}
          <div className="lg:col-span-6 relative pt-4 lg:pt-0">
            {/* Desktop View: Exact pixel-matched layered composition */}
            <div className="hidden lg:block relative w-full h-[400px] max-w-[500px] ml-auto">
              {/* 1. PM-KISAN Card */}
              <div className="absolute left-8 top-1 w-[310px] h-[72px] z-10 bg-white rounded-2xl px-4 py-3 border border-[#172B45]/8 shadow-[0_10px_28px_rgba(23,43,69,0.07)] hover:shadow-float transition-all duration-300 flex items-center justify-between gap-3 transform -rotate-[2deg] hover:rotate-0 hover:-translate-y-1">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-11 h-11 rounded-xl bg-[#E8F5E9] text-[#2E7D32] flex items-center justify-center shrink-0">
                    <Sprout className="w-5.5 h-5.5 text-[#2E7D32]" />
                  </div>
                  <div className="min-w-0">
                    <h4 className="font-bold text-[#172B45] text-sm sm:text-[15px] leading-snug truncate">PM-KISAN</h4>
                    <p className="text-xs text-[#172B45]/60 truncate">Income Support for Farmers</p>
                  </div>
                </div>
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#E8F5E9] text-[#2E7D32] border border-[#C8E6C9] text-xs font-bold shrink-0">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#2E7D32]" />
                  Eligible
                </span>
              </div>

              {/* 2. PMAY-G Card (Exact 2mm / 8px vertical gap below Card 1) */}
              <div className="absolute left-4 top-[95px] w-[310px] h-[72px] z-10 bg-white rounded-2xl px-4 py-3 border border-[#172B45]/8 shadow-[0_10px_28px_rgba(23,43,69,0.07)] hover:shadow-float transition-all duration-300 flex items-center justify-between gap-3 transform -rotate-[2deg] hover:rotate-0 hover:-translate-y-1">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-11 h-11 rounded-xl bg-blue-50 text-blue-700 flex items-center justify-center shrink-0">
                    <Home className="w-5.5 h-5.5 text-blue-700" />
                  </div>
                  <div className="min-w-0">
                    <h4 className="font-bold text-[#172B45] text-sm sm:text-[15px] leading-snug truncate">PMAY-G</h4>
                    <p className="text-xs text-[#172B45]/60 truncate">Housing for All</p>
                  </div>
                </div>
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#E8F5E9] text-[#2E7D32] border border-[#C8E6C9] text-xs font-bold shrink-0">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#2E7D32]" />
                  Eligible
                </span>
              </div>

              {/* 3. National Scholarship Card (Exact 2mm / 8px vertical gap below Card 2) */}
              <div className="absolute left-0 top-[186px] w-[310px] h-[72px] z-10 bg-white rounded-2xl px-4 py-3 border border-[#172B45]/8 shadow-[0_10px_28px_rgba(23,43,69,0.07)] hover:shadow-float transition-all duration-300 flex items-center justify-between gap-3 transform -rotate-[2deg] hover:rotate-0 hover:-translate-y-1">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-11 h-11 rounded-xl bg-slate-100 text-[#172B45] flex items-center justify-center shrink-0">
                    <GraduationCap className="w-5.5 h-5.5 text-[#172B45]" />
                  </div>
                  <div className="min-w-0">
                    <h4 className="font-bold text-[#172B45] text-sm sm:text-[15px] leading-snug truncate">National Scholarship</h4>
                    <p className="text-xs text-[#172B45]/60 truncate">Support for Students</p>
                  </div>
                </div>
                <Link
                  to="/schemes"
                  className="text-xs font-bold text-[#172B45] hover:text-[#D99548] transition-colors flex items-center gap-1 shrink-0"
                >
                  <span>Check Now</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>

              {/* 4. Overlapping "Your Eligibility" Card (Sits at left-[225px] top-[74px]) */}
              <div className="absolute left-[225px] top-[74px] w-[240px] z-20 animate-fade-in-right delay-200">
                <div className="bg-white rounded-3xl p-5 border border-[#172B45]/10 shadow-[0_24px_50px_rgba(23,43,69,0.14)] space-y-3.5 hover:-translate-y-1 transition-all duration-300 transform rotate-[1.5deg] hover:rotate-0">
                  <h3 className="font-bold text-[#172B45] text-base tracking-tight">Your Eligibility</h3>

                  <div className="flex items-center gap-2.5 p-2.5 rounded-xl bg-[#E8F5E9]/80 border border-[#C8E6C9]">
                    <div className="w-6.5 h-6.5 rounded-full bg-[#2E7D32] text-white flex items-center justify-center shrink-0 shadow-2xs">
                      <Check className="w-3.5 h-3.5 stroke-[3]" />
                    </div>
                    <span className="font-extrabold text-[#2E7D32] text-xs sm:text-sm leading-tight">
                      You are eligible!
                    </span>
                  </div>

                  <div className="space-y-2 text-xs text-[#172B45] pt-0.5">
                    <div className="flex items-center gap-2 font-medium">
                      <CheckCircle2 className="w-4 h-4 text-[#2E7D32] shrink-0" />
                      <span>Basic Criteria</span>
                    </div>
                    <div className="flex items-center gap-2 font-medium">
                      <CheckCircle2 className="w-4 h-4 text-[#2E7D32] shrink-0" />
                      <span>Income Limit</span>
                    </div>
                    <div className="flex items-center gap-2 font-medium">
                      <CheckCircle2 className="w-4 h-4 text-[#2E7D32] shrink-0" />
                      <span>Residential Status</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* 5. Overlapping "Documents Checklist" Card (Sits at left-[170px] top-[268px]) */}
              <div className="absolute left-[170px] top-[268px] w-[310px] z-30 animate-fade-in-up delay-300">
                <div className="bg-white rounded-2xl p-4 border border-[#172B45]/8 shadow-[0_18px_44px_rgba(23,43,69,0.11)] flex items-center gap-3.5 hover:shadow-float transition-all duration-300 transform -rotate-[1deg] hover:rotate-0 hover:-translate-y-1">
                  <div className="w-11 h-11 rounded-xl bg-blue-500 text-white flex items-center justify-center shrink-0 shadow-2xs">
                    <FileText className="w-5.5 h-5.5" />
                  </div>
                  <div className="flex-1 space-y-1.5 min-w-0">
                    <div className="flex items-center justify-between">
                      <h4 className="font-bold text-[#172B45] text-xs sm:text-sm truncate">Documents Checklist</h4>
                      <span className="text-xs font-semibold text-[#172B45]/65 shrink-0">3 of 5 Required</span>
                    </div>
                    {/* Progress Bar (60% filled) */}
                    <div className="w-full h-2 rounded-full bg-slate-100 overflow-hidden">
                      <div className="h-full rounded-full bg-blue-600 w-3/5 transition-all duration-1000 ease-out" />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Mobile / Tablet Responsive Fallback */}
            <div className="lg:hidden space-y-3.5 max-w-xl mx-auto">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 items-start">
                {/* Left Column: 3 Scheme Cards with exactly 2mm / 8px gap */}
                <div className="space-y-2">
                  {/* PM-KISAN */}
                  <div className="bg-white rounded-2xl p-3.5 sm:p-4 border border-[#172B45]/8 shadow-subtle hover:shadow-premium transition-all duration-300 flex items-center justify-between gap-3 md:-rotate-[1deg]">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-10 h-10 rounded-xl bg-[#E8F5E9] text-[#2E7D32] flex items-center justify-center shrink-0">
                        <Sprout className="w-5 h-5 text-[#2E7D32]" />
                      </div>
                      <div className="min-w-0">
                        <h4 className="font-bold text-[#172B45] text-sm truncate">PM-KISAN</h4>
                        <p className="text-xs text-[#172B45]/60 truncate">Income Support for Farmers</p>
                      </div>
                    </div>
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-[#E8F5E9] text-[#2E7D32] border border-[#C8E6C9] text-xs font-bold shrink-0">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#2E7D32]" />
                      Eligible
                    </span>
                  </div>

                  {/* PMAY-G */}
                  <div className="bg-white rounded-2xl p-3.5 sm:p-4 border border-[#172B45]/8 shadow-subtle hover:shadow-premium transition-all duration-300 flex items-center justify-between gap-3 md:-rotate-[1deg]">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-700 flex items-center justify-center shrink-0">
                        <Home className="w-5 h-5 text-blue-700" />
                      </div>
                      <div className="min-w-0">
                        <h4 className="font-bold text-[#172B45] text-sm truncate">PMAY-G</h4>
                        <p className="text-xs text-[#172B45]/60 truncate">Housing for All</p>
                      </div>
                    </div>
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-[#E8F5E9] text-[#2E7D32] border border-[#C8E6C9] text-xs font-bold shrink-0">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#2E7D32]" />
                      Eligible
                    </span>
                  </div>

                  {/* National Scholarship */}
                  <div className="bg-white rounded-2xl p-3.5 sm:p-4 border border-[#172B45]/8 shadow-subtle hover:shadow-premium transition-all duration-300 flex items-center justify-between gap-3 md:-rotate-[1deg]">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-10 h-10 rounded-xl bg-slate-100 text-[#172B45] flex items-center justify-center shrink-0">
                        <GraduationCap className="w-5 h-5 text-[#172B45]" />
                      </div>
                      <div className="min-w-0">
                        <h4 className="font-bold text-[#172B45] text-sm truncate">National Scholarship</h4>
                        <p className="text-xs text-[#172B45]/60 truncate">Support for Students</p>
                      </div>
                    </div>
                    <Link to="/schemes" className="text-xs font-bold text-[#172B45] hover:text-[#D99548] flex items-center gap-1 shrink-0">
                      <span>Check Now</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                </div>

                {/* Right Column: Your Eligibility + Documents Checklist */}
                <div className="space-y-3">
                  {/* Your Eligibility Card */}
                  <div className="bg-white rounded-2xl p-4.5 border border-[#172B45]/10 shadow-subtle space-y-3 md:rotate-[1deg]">
                    <div className="flex items-center justify-between">
                      <h3 className="font-bold text-[#172B45] text-sm sm:text-base">Your Eligibility</h3>
                      <span className="font-bold text-xs text-[#2E7D32] flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Eligible
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-2 text-xs text-[#172B45]/80">
                      <span className="px-2.5 py-0.5 rounded-md bg-[#E8F5E9] text-[#2E7D32] font-semibold">✓ Basic Criteria</span>
                      <span className="px-2.5 py-0.5 rounded-md bg-[#E8F5E9] text-[#2E7D32] font-semibold">✓ Income Limit</span>
                      <span className="px-2.5 py-0.5 rounded-md bg-[#E8F5E9] text-[#2E7D32] font-semibold">✓ Residential Status</span>
                    </div>
                  </div>

                  {/* Documents Checklist Card */}
                  <div className="bg-white rounded-2xl p-3.5 sm:p-4 border border-[#172B45]/8 shadow-subtle flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-blue-500 text-white flex items-center justify-center shrink-0 shadow-2xs">
                      <FileText className="w-5 h-5" />
                    </div>
                    <div className="flex-1 space-y-1 min-w-0">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-bold text-[#172B45] truncate">Documents Checklist</span>
                        <span className="font-semibold text-[#172B45]/65 shrink-0">3 of 5</span>
                      </div>
                      <div className="w-full h-1.5 rounded-full bg-slate-100 overflow-hidden">
                        <div className="h-full rounded-full bg-blue-600 w-3/5" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* =========================================================================
          THE 4 FEATURE CARDS RIBBON — EXACT 1:1 REPLICATION FROM REFERENCE
      ========================================================================== */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-1">
        {/* Card 1: Search Schemes */}
        <div className="bg-white rounded-2xl p-5 border border-[#172B45]/8 shadow-subtle hover:shadow-premium hover:-translate-y-1 transition-all duration-300 flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-[#F8F6F0] text-[#172B45] flex items-center justify-center shrink-0 border border-[#172B45]/6">
            <Search className="w-6 h-6 text-[#172B45]" />
          </div>
          <div>
            <h3 className="font-bold text-[#172B45] text-sm">
              {language === 'hi' ? 'योजनाएं खोजें' : 'Search Schemes'}
            </h3>
            <p className="text-xs text-[#172B45]/60 mt-0.5">
              {language === 'hi' ? 'अपने लिए उपयुक्त योजनाएं पाएं' : 'Find the right schemes for you'}
            </p>
          </div>
        </div>

        {/* Card 2: Check Eligibility */}
        <div className="bg-white rounded-2xl p-5 border border-[#172B45]/8 shadow-subtle hover:shadow-premium hover:-translate-y-1 transition-all duration-300 flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-[#F8F6F0] text-[#172B45] flex items-center justify-center shrink-0 border border-[#172B45]/6">
            <ShieldCheck className="w-6 h-6 text-[#172B45]" />
          </div>
          <div>
            <h3 className="font-bold text-[#172B45] text-sm">
              {language === 'hi' ? 'पात्रता जांचें' : 'Check Eligibility'}
            </h3>
            <p className="text-xs text-[#172B45]/60 mt-0.5">
              {language === 'hi' ? 'पात्रता तुरंत स्पष्ट जानें' : 'Know your eligibility instantly'}
            </p>
          </div>
        </div>

        {/* Card 3: Prepare Documents */}
        <div className="bg-white rounded-2xl p-5 border border-[#172B45]/8 shadow-subtle hover:shadow-premium hover:-translate-y-1 transition-all duration-300 flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-[#F8F6F0] text-[#172B45] flex items-center justify-center shrink-0 border border-[#172B45]/6">
            <FileText className="w-6 h-6 text-[#172B45]" />
          </div>
          <div>
            <h3 className="font-bold text-[#172B45] text-sm">
              {language === 'hi' ? 'दस्तावेज़ तैयार करें' : 'Prepare Documents'}
            </h3>
            <p className="text-xs text-[#172B45]/60 mt-0.5">
              {language === 'hi' ? 'पूरी चेकलिस्ट प्राप्त करें' : 'Get a complete checklist'}
            </p>
          </div>
        </div>

        {/* Card 4: Apply with Confidence */}
        <div className="bg-white rounded-2xl p-5 border border-[#172B45]/8 shadow-subtle hover:shadow-premium hover:-translate-y-1 transition-all duration-300 flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-[#F8F6F0] text-[#172B45] flex items-center justify-center shrink-0 border border-[#172B45]/6">
            <Rocket className="w-6 h-6 text-[#172B45]" />
          </div>
          <div>
            <h3 className="font-bold text-[#172B45] text-sm">
              {language === 'hi' ? 'विश्वास के साथ आवेदन' : 'Apply with Confidence'}
            </h3>
            <p className="text-xs text-[#172B45]/60 mt-0.5">
              {language === 'hi' ? 'आवेदन आसानी से ट्रैक करें' : 'Track your application easily'}
            </p>
          </div>
        </div>
      </section>

      {/* =========================================================================
          CURATED WELFARE CATALOGUE
      ========================================================================== */}
      <section className="space-y-6 pt-2">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-[#D99548]">
              {language === 'hi' ? 'सत्यापित योजनाएं' : 'Curated Welfare Catalog'}
            </span>
            <h2 className="text-2xl sm:text-3xl font-editorial font-bold text-[#172B45] tracking-tight mt-1">
              {language === 'hi' ? 'प्रमुख सरकारी कल्याण योजनाएं' : 'Featured Central Welfare Schemes'}
            </h2>
          </div>
          <Link
            to="/schemes"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#172B45] hover:text-[#E67E22] transition-colors"
          >
            <span>{language === 'hi' ? 'सभी योजनाएं देखें' : 'View all schemes'}</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Scheme Card 1 */}
          <div className="bg-white rounded-2xl p-6 border border-[#172B45]/8 shadow-subtle hover:shadow-premium hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-extrabold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-[#FDF3E7] text-[#D99548] border border-[#F5D8B8]">
                  AGRICULTURE
                </span>
                <span className="text-xs font-semibold text-[#172B45]/40">PM-KISAN</span>
              </div>
              <h3 className="font-bold text-[#172B45] text-base leading-snug">
                PM Kisan Samman Nidhi
              </h3>
              <p className="text-xs text-[#172B45]/65 leading-relaxed">
                Direct income support of ₹6,000 per year in three quarterly installments for small and marginal landholder farmer families.
              </p>
            </div>
            <div className="pt-5 mt-5 border-t border-[#172B45]/6 flex items-center justify-between text-xs">
              <span className="font-bold text-[#172B45]">₹6,000 / yr</span>
              <Link
                to="/schemes/scheme-pm-kisan-01"
                className="font-semibold text-[#E67E22] hover:underline flex items-center gap-1"
              >
                <span>Details</span>
                <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
          </div>

          {/* Scheme Card 2 */}
          <div className="bg-white rounded-2xl p-6 border border-[#172B45]/8 shadow-subtle hover:shadow-premium hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-extrabold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-[#E8F5E9] text-[#2E7D32] border border-[#C8E6C9]">
                  HEALTHCARE
                </span>
                <span className="text-xs font-semibold text-[#172B45]/40">PM-JAY</span>
              </div>
              <h3 className="font-bold text-[#172B45] text-base leading-snug">
                Ayushman Bharat PM-JAY
              </h3>
              <p className="text-xs text-[#172B45]/65 leading-relaxed">
                Hospitalization coverage of ₹5,00,000 per family per year for secondary and tertiary healthcare across empanelled hospitals.
              </p>
            </div>
            <div className="pt-5 mt-5 border-t border-[#172B45]/6 flex items-center justify-between text-xs">
              <span className="font-bold text-[#172B45]">₹5,00,000 / yr</span>
              <Link
                to="/schemes/scheme-pmjay-03"
                className="font-semibold text-[#E67E22] hover:underline flex items-center gap-1"
              >
                <span>Details</span>
                <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
          </div>

          {/* Scheme Card 3 */}
          <div className="bg-white rounded-2xl p-6 border border-[#172B45]/8 shadow-subtle hover:shadow-premium hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-extrabold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-[#F2EFE8] text-[#172B45]/80 border border-[#172B45]/10">
                  EDUCATION
                </span>
                <span className="text-xs font-semibold text-[#172B45]/40">NMMSS</span>
              </div>
              <h3 className="font-bold text-[#172B45] text-base leading-snug">
                National Means-cum-Merit Scholarship
              </h3>
              <p className="text-xs text-[#172B45]/65 leading-relaxed">
                Scholarship of ₹12,000 per annum for meritorious students of economically weaker sections from Class IX to XII.
              </p>
            </div>
            <div className="pt-5 mt-5 border-t border-[#172B45]/6 flex items-center justify-between text-xs">
              <span className="font-bold text-[#172B45]">₹12,000 / yr</span>
              <Link
                to="/schemes/scheme-nmms-04"
                className="font-semibold text-[#E67E22] hover:underline flex items-center gap-1"
              >
                <span>Details</span>
                <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* =========================================================================
          BOTTOM INTERACTION BANNER
      ========================================================================== */}
      <section className="bg-white rounded-3xl p-8 sm:p-10 border border-[#172B45]/8 shadow-subtle flex flex-col sm:flex-row items-center justify-between gap-6">
        <div className="space-y-1 text-center sm:text-left">
          <h3 className="font-editorial text-xl sm:text-2xl font-bold text-[#172B45]">
            {language === 'hi' ? 'क्या आप सहायता चाहते हैं?' : 'Need Guidance on Welfare Schemes?'}
          </h3>
          <p className="text-xs sm:text-sm text-[#172B45]/60">
            {language === 'hi'
              ? 'योजना साथी से अपनी भाषा में खुलकर बात करें और अपनी पात्रता जानें।'
              : 'Interact with Scheme Saathi in Hindi or English to evaluate deterministic eligibility.'}
          </p>
        </div>
        <Link to="/chat">
          <button className="bg-[#172B45] hover:bg-[#112033] text-white rounded-full px-6 py-3 font-semibold text-sm transition-all duration-200 flex items-center gap-2 shadow-subtle hover:shadow-premium active:scale-98 cursor-pointer shrink-0">
            <Sparkles className="w-4 h-4 text-[#D99548]" />
            <span>{language === 'hi' ? 'साथी से पूछें' : 'Ask AI Saathi'}</span>
          </button>
        </Link>
      </section>
    </div>
  );
};
