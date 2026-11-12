import React from 'react';
import {
  MessageSquare,
  Sparkles,
  FileCheck2,
  FileEdit,
  CheckCircle2,
  ShieldCheck,
} from 'lucide-react';

export type WorkflowStage = 'TALK' | 'MATCH' | 'CHECKLIST' | 'PRE-FILL' | 'CONFIRM';

interface WorkflowStepperProps {
  currentStep: WorkflowStage | string;
  activeScheme?: {
    scheme_code?: string;
    scheme_name?: string;
  } | null;
  onStepClick?: (step: WorkflowStage) => void;
}

const STAGES: {
  key: WorkflowStage;
  label: string;
  labelLocal: string;
  icon: React.FC<{ className?: string }>;
}[] = [
  { key: 'TALK', label: 'TALK', labelLocal: 'संभाषण', icon: MessageSquare },
  { key: 'MATCH', label: 'MATCH', labelLocal: 'योजना पात्रता', icon: Sparkles },
  { key: 'CHECKLIST', label: 'CHECKLIST', labelLocal: 'कागदपत्रे', icon: FileCheck2 },
  { key: 'PRE-FILL', label: 'PRE-FILL', labelLocal: 'अर्ज मसुदा', icon: FileEdit },
  { key: 'CONFIRM', label: 'CONFIRM', labelLocal: 'नक्की करा', icon: CheckCircle2 },
];

export const WorkflowStepper: React.FC<WorkflowStepperProps> = ({
  currentStep,
  activeScheme,
  onStepClick,
}) => {
  const normalizedStep = (currentStep || 'TALK').toUpperCase() as WorkflowStage;
  const currentIdx = STAGES.findIndex((s) => s.key === normalizedStep);
  const activeIdx = currentIdx >= 0 ? currentIdx : 0;

  return (
    <div className="w-full bg-gradient-to-r from-ivory-50 via-white to-ivory-50 border-b border-navy/8 px-4 py-2.5 shadow-xs">
      <div className="max-w-4xl mx-auto flex flex-col gap-2">
        {/* Horizontal Stepper Row */}
        <div className="flex items-center justify-between gap-1 sm:gap-2">
          {STAGES.map((stage, idx) => {
            const Icon = stage.icon;
            const isCompleted = idx < activeIdx;
            const isCurrent = idx === activeIdx;

            return (
              <React.Fragment key={stage.key}>
                <button
                  type="button"
                  onClick={() => onStepClick && onStepClick(stage.key)}
                  disabled={!onStepClick}
                  className={`group flex items-center gap-1 sm:gap-2 px-2 sm:px-2.5 py-1 rounded-xl transition-all duration-200 text-left ${
                    isCurrent
                      ? 'bg-saffron-light text-navy shadow-subtle border border-saffron/40 font-bold scale-[1.02]'
                      : isCompleted
                      ? 'bg-sage-light/60 text-navy/90 hover:bg-sage-light border border-sage/20'
                      : 'bg-transparent text-navy/40 hover:text-navy/70 border border-transparent'
                  }`}
                  title={`${stage.label}: ${stage.labelLocal}`}
                >
                  {/* Step Icon / Circle */}
                  <div
                    className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 text-xs font-bold transition-all ${
                      isCurrent
                        ? 'bg-saffron text-white shadow-xs'
                        : isCompleted
                        ? 'bg-sage-green text-white'
                        : 'bg-navy/10 text-navy/50'
                    }`}
                  >
                    {isCompleted ? (
                      <CheckCircle2 className="w-3.5 h-3.5 stroke-[2.5]" />
                    ) : (
                      <Icon className="w-3.5 h-3.5" />
                    )}
                  </div>

                  {/* Step Labels */}
                  <div className="flex flex-col leading-tight">
                    <span
                      className={`text-[11px] font-bold tracking-tight uppercase ${
                        isCurrent
                          ? 'text-navy'
                          : isCompleted
                          ? 'text-navy/80'
                          : 'text-navy/40'
                      }`}
                    >
                      {stage.label}
                    </span>
                    <span
                      className={`text-[9.5px] hidden md:inline-block ${
                        isCurrent
                          ? 'text-saffron-dark font-semibold'
                          : isCompleted
                          ? 'text-sage-green font-medium'
                          : 'text-navy/30'
                      }`}
                    >
                      {stage.labelLocal}
                    </span>
                  </div>
                </button>

                {/* Connecting arrow separator between steps */}
                {idx < STAGES.length - 1 && (
                  <div className="flex-1 flex items-center justify-center px-0.5 sm:px-1">
                    <div
                      className={`h-0.5 w-full rounded-full transition-all ${
                        idx < activeIdx ? 'bg-sage-green/60' : 'bg-navy/10'
                      }`}
                    />
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>

        {/* Active Scheme Context Bar if available */}
        {activeScheme && (activeScheme.scheme_code || activeScheme.scheme_name) && (
          <div className="flex items-center justify-between text-xs bg-white/90 border border-navy/8 rounded-xl px-3 py-1 text-navy shadow-xs mt-0.5">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="w-2 h-2 rounded-full bg-saffron animate-pulse shrink-0" />
              <span className="font-semibold text-navy/70 text-[11px] shrink-0">
                निवडलेली योजना (Active Scheme):
              </span>
              <span className="font-bold text-navy truncate text-[11.5px] font-editorial">
                {activeScheme.scheme_name || activeScheme.scheme_code}
              </span>
              {activeScheme.scheme_code && (
                <span className="text-[10px] bg-saffron-light text-saffron-dark font-mono font-bold px-1.5 py-0.2 rounded border border-saffron/20 shrink-0">
                  {activeScheme.scheme_code}
                </span>
              )}
            </div>

            <div className="hidden sm:flex items-center gap-1 text-[10.5px] text-sage-green font-semibold shrink-0">
              <ShieldCheck className="w-3.5 h-3.5 text-sage-green" />
              <span>Grounded Rules</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
