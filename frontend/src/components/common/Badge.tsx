import React from 'react';
import { cn } from '@/utils/cn';
import { ApplicationLifecycleState } from '@/types';

export type BadgeVariant =
  | 'default'
  | 'eligible'
  | 'not_eligible'
  | 'potentially_eligible'
  | 'insufficient_information'
  | 'category'
  | 'saffron'
  | 'sage'
  | 'green'
  | 'navy'
  | ApplicationLifecycleState;

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  children: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  className,
  ...props
}) => {
  const styles: Record<string, string> = {
    default: 'bg-ivory-100 text-navy/80 border-navy/10',
    category: 'bg-navy/5 text-navy/90 border-navy/10 font-medium',
    saffron: 'bg-saffron-light text-saffron-dark border-saffron/30 font-medium',
    sage: 'bg-sage-light text-sage-dark border-sage/30 font-medium',
    green: 'bg-sage-light text-sage-dark border-sage/30 font-medium',
    navy: 'bg-navy text-white border-navy',

    // Eligibility Outcomes
    eligible: 'bg-sage-light text-sage-dark border-sage/35 font-semibold',
    not_eligible: 'bg-rose-50 text-rose-800 border-rose-200/80 font-semibold',
    potentially_eligible: 'bg-saffron-light text-saffron-dark border-saffron/35 font-semibold',
    insufficient_information: 'bg-sky-50 text-sky-800 border-sky-200 font-semibold',

    // Application Lifecycle
    draft: 'bg-ivory-100 text-navy/70 border-navy/15',
    validated: 'bg-sage-light text-sage-dark border-sage/30',
    awaiting_confirmation: 'bg-saffron-light text-saffron-dark border-saffron/30 animate-pulse',
    submitted: 'bg-sage-light text-sage-dark border-sage/35 font-semibold',
    validation_failed: 'bg-saffron-light text-saffron-dark border-saffron/20',
    submission_failed: 'bg-rose-50 text-rose-800 border-rose-200',
    cancelled: 'bg-ivory-100 text-navy/40 border-navy/10 line-through',
  };

  const currentStyle = styles[variant] || styles.default;

  return (
    <span
      className={cn(
        'inline-flex items-center px-2.5 py-1 rounded-full text-[11px] border tracking-wide transition-all duration-200',
        currentStyle,
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
};
