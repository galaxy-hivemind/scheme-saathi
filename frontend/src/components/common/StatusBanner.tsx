import React from 'react';
import { cn } from '@/utils/cn';
import { AlertCircle, AlertTriangle, CheckCircle2, Info } from 'lucide-react';

export interface StatusBannerProps {
  type?: 'info' | 'warning' | 'success' | 'danger' | 'demo';
  title?: string;
  message: string;
  action?: React.ReactNode;
  className?: string;
}

export const StatusBanner: React.FC<StatusBannerProps> = ({
  type = 'info',
  title,
  message,
  action,
  className,
}) => {
  const configs = {
    info: {
      bg: 'bg-navy-50/70 border-navy/12 text-navy',
      icon: <Info className="w-5 h-5 text-navy shrink-0 mt-0.5" />,
    },
    warning: {
      bg: 'bg-saffron-light border-saffron/30 text-navy',
      icon: <AlertTriangle className="w-5 h-5 text-saffron-vibrant shrink-0 mt-0.5" />,
    },
    success: {
      bg: 'bg-sage-light border-sage/35 text-navy',
      icon: <CheckCircle2 className="w-5 h-5 text-sage-green shrink-0 mt-0.5" />,
    },
    danger: {
      bg: 'bg-rose-50 border-rose-200/90 text-rose-950',
      icon: <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />,
    },
    demo: {
      bg: 'bg-saffron-50 border-saffron/30 text-navy',
      icon: <Info className="w-5 h-5 text-saffron-vibrant shrink-0 mt-0.5" />,
    },
  };

  const { bg, icon } = configs[type];

  return (
    <div
      className={cn(
        'flex items-start justify-between gap-3 p-4 sm:p-5 rounded-2xl border text-sm shadow-subtle',
        bg,
        className
      )}
    >
      <div className="flex items-start gap-3">
        {icon}
        <div>
          {title && <h5 className="font-semibold text-xs tracking-wider uppercase mb-0.5 text-navy">{title}</h5>}
          <p className="leading-relaxed text-xs sm:text-sm opacity-90">{message}</p>
        </div>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
};

