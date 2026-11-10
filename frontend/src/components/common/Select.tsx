import React, { forwardRef } from 'react';
import { cn } from '@/utils/cn';

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  helperText?: string;
  error?: string;
  options: SelectOption[];
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, label, helperText, error, options, id, ...props }, ref) => {
    const selectId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

    return (
      <div className="w-full space-y-1.5">
        {label && (
          <label htmlFor={selectId} className="block text-xs font-semibold text-navy/70 tracking-wide">
            {label} {props.required && <span className="text-saffron-vibrant font-bold">*</span>}
          </label>
        )}
        <select
          id={selectId}
          ref={ref}
          className={cn(
            'w-full rounded-xl border bg-white px-4 py-2.5 text-sm text-navy shadow-subtle',
            'transition duration-200 ease-out',
            'focus:outline-none focus:ring-2 focus:ring-navy/15 focus:border-navy',
            'disabled:bg-ivory-100 disabled:text-navy/40',
            error
              ? 'border-rose-400 focus:border-rose-500 focus:ring-rose-500/20 text-rose-950'
              : 'border-navy/15 hover:border-navy/30',
            className
          )}
          {...props}
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        {error && <p className="text-xs text-rose-600 font-medium">{error}</p>}
        {helperText && !error && <p className="text-xs text-navy/50">{helperText}</p>}
      </div>
    );
  }
);

Select.displayName = 'Select';

