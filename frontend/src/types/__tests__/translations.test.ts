import { describe, it, expect } from 'vitest';
import { translations } from '../translations';

describe('Trilingual Translations Dictionary (English, Hindi, Marathi)', () => {
  it('contains English, Hindi, and Marathi translations for all required keys', () => {
    expect(translations.en).toBeDefined();
    expect(translations.hi).toBeDefined();
    expect(translations.mr).toBeDefined();

    expect(translations.en.appName).toBe('Scheme Saathi');
    expect(translations.hi.appName).toBe('योजना साथी');
    expect(translations.mr.appName).toBe('योजना साथी');

    expect(translations.en.status.eligible).toBe('Eligible');
    expect(translations.hi.status.eligible).toContain('पात्र');
    expect(translations.mr.status.eligible).toContain('पात्र');

    expect(translations.en.status.awaitingConfirmation).toBe('Awaiting Confirmation');
    expect(translations.hi.status.awaitingConfirmation).toBe('पुष्टि प्रतीक्षित');
    expect(translations.mr.status.awaitingConfirmation).toBe('पुष्टी प्रलंबित');
  });

  it('matches all navigation and action items across all three languages', () => {
    const enNavKeys = Object.keys(translations.en.nav).sort();
    const hiNavKeys = Object.keys(translations.hi.nav).sort();
    const mrNavKeys = Object.keys(translations.mr.nav).sort();
    expect(enNavKeys).toEqual(hiNavKeys);
    expect(enNavKeys).toEqual(mrNavKeys);

    const enActionKeys = Object.keys(translations.en.actions).sort();
    const hiActionKeys = Object.keys(translations.hi.actions).sort();
    const mrActionKeys = Object.keys(translations.mr.actions).sort();
    expect(enActionKeys).toEqual(hiActionKeys);
    expect(enActionKeys).toEqual(mrActionKeys);
  });
});
