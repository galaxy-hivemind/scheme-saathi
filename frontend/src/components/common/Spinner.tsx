import React from 'react';
import { cn } from '@/utils/cn';

export interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  label?: string;
}

export const Spinner: React.FC<SpinnerProps> = ({ size = 'md', className, label }) => {
  const sizes = {
    sm: 'w-4 h-4 border-2',
    md: 'w-8 h-8 border-3',
    lg: 'w-12 h-12 border-4',
  };

  return (
    <div className="flex flex-col items-center justify-center p-8 gap-3.5">
      <div
        className={cn(
          'rounded-full border-navy/15 border-t-saffron animate-spin',
          sizes[size],
          className
        )}
      />
      {label && <p className="text-xs text-navy/60 font-medium animate-pulse tracking-wide">{label}</p>}
    </div>
  );
};

