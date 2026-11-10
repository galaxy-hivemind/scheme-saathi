import React from 'react';
import { cn } from '@/utils/cn';
import { Loader2 } from 'lucide-react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger' | 'saffron' | 'sage' | 'green';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  className,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  leftIcon,
  rightIcon,
  disabled,
  ...props
}) => {
  const baseStyles = 'inline-flex items-center justify-center font-medium rounded-xl transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100';

  const variants = {
    primary: 'bg-navy text-white hover:bg-navy-800 focus:ring-navy shadow-subtle hover:shadow-premium',
    secondary: 'bg-ivory-100 text-navy hover:bg-ivory-200 focus:ring-navy/20',
    outline: 'border border-navy/15 text-navy bg-white hover:bg-ivory-50 hover:border-navy/30 focus:ring-navy/20 shadow-subtle',
    ghost: 'text-navy/70 hover:bg-navy/5 hover:text-navy focus:ring-navy/20',
    danger: 'bg-rose-600 text-white hover:bg-rose-700 focus:ring-rose-500 shadow-subtle',
    saffron: 'bg-saffron text-white hover:bg-saffron-dark focus:ring-saffron shadow-subtle hover:shadow-glow-saffron font-semibold',
    sage: 'bg-sage text-white hover:bg-sage-dark focus:ring-sage shadow-subtle hover:shadow-glow-sage font-semibold',
    green: 'bg-sage text-white hover:bg-sage-dark focus:ring-sage shadow-subtle hover:shadow-glow-sage font-semibold',
  };

  const sizes = {
    sm: 'text-xs px-3.5 py-1.5 gap-1.5 min-h-[34px]',
    md: 'text-sm px-5 py-2.5 gap-2 min-h-[42px]',
    lg: 'text-base px-6 py-3.5 gap-2.5 min-h-[48px]',
  };

  return (
    <button
      className={cn(baseStyles, variants[variant], sizes[size], className)}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <Loader2 className="w-4 h-4 animate-spin shrink-0" />
      ) : (
        leftIcon && <span className="shrink-0 transition-transform duration-200 group-hover:-translate-x-0.5">{leftIcon}</span>
      )}
      <span>{children}</span>
      {!isLoading && rightIcon && <span className="shrink-0 transition-transform duration-200 group-hover:translate-x-0.5">{rightIcon}</span>}
    </button>
  );
};
