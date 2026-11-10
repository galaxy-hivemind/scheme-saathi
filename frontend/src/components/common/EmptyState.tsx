import React from 'react';
import { cn } from '@/utils/cn';
import { FolderSearch } from 'lucide-react';
import { Button } from './Button';

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  actionLabel,
  onAction,
  className,
}) => {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center text-center p-8 sm:p-14 bg-white rounded-3xl border border-dashed border-navy/20 shadow-subtle',
        className
      )}
    >
      <div className="w-14 h-14 rounded-2xl bg-ivory-100 text-navy flex items-center justify-center mb-4 shadow-subtle border border-navy/8">
        {icon || <FolderSearch className="w-7 h-7 text-saffron" />}
      </div>
      <h3 className="text-lg font-bold text-navy font-editorial mb-1.5">{title}</h3>
      <p className="text-sm text-navy/60 max-w-sm mb-6 leading-relaxed">{description}</p>
      {actionLabel && onAction && (
        <Button variant="outline" size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
};

