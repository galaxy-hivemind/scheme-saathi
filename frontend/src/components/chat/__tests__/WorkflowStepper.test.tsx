import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { WorkflowStepper } from '../WorkflowStepper';

describe('WorkflowStepper Component', () => {
  it('renders all 5 workflow stages in order: TALK -> MATCH -> CHECKLIST -> PRE-FILL -> CONFIRM', () => {
    const html = renderToStaticMarkup(
      <WorkflowStepper currentStep="TALK" />
    );

    expect(html).toContain('TALK');
    expect(html).toContain('संभाषण');
    expect(html).toContain('MATCH');
    expect(html).toContain('योजना पात्रता');
    expect(html).toContain('CHECKLIST');
    expect(html).toContain('कागदपत्रे');
    expect(html).toContain('PRE-FILL');
    expect(html).toContain('अर्ज मसुदा');
    expect(html).toContain('CONFIRM');
    expect(html).toContain('नक्की करा');
  });

  it('distinctly highlights active stage and marks completed stages', () => {
    // Current step is CHECKLIST (index 2)
    // Completed: TALK (0), MATCH (1)
    // Active: CHECKLIST (2)
    // Upcoming: PRE-FILL (3), CONFIRM (4)
    const html = renderToStaticMarkup(
      <WorkflowStepper currentStep="CHECKLIST" />
    );

    // Active stage receives saffron styling
    expect(html).toContain('bg-saffron-light');
    // Completed stages receive sage styling
    expect(html).toContain('bg-sage-green');
  });

  it('renders active scheme context bar when activeScheme is provided', () => {
    const html = renderToStaticMarkup(
      <WorkflowStepper
        currentStep="MATCH"
        activeScheme={{
          scheme_code: 'WIDOW-PENSION',
          scheme_name: 'Indira Gandhi National Widow Pension Scheme',
        }}
      />
    );

    expect(html).toContain('निवडलेली योजना (Active Scheme):');
    expect(html).toContain('Indira Gandhi National Widow Pension Scheme');
    expect(html).toContain('WIDOW-PENSION');
    expect(html).toContain('Grounded Rules');
  });

  it('hides active scheme bar when activeScheme is null', () => {
    const html = renderToStaticMarkup(
      <WorkflowStepper currentStep="TALK" activeScheme={null} />
    );

    expect(html).not.toContain('निवडलेली योजना (Active Scheme):');
    expect(html).not.toContain('Grounded Rules');
  });
});
