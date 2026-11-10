import { describe, it, expect } from 'vitest';
import { translations } from '../translations';

describe('Bilingual Translations Dictionary', () => {
  it('contains English and Hindi translations for all required keys', () => {
    expect(translations.en).toBeDefined();
    expect(translations.hi).toBeDefined();

    expect(translations.en.appName).toBe('Scheme Saathi');
    expect(translations.hi.appName).toBe('योजना साथी');

    expect(translations.en.status.eligible).toBe('Eligible');
    expect(translations.hi.status.eligible).toContain('पात्र');

    expect(translations.en.status.awaitingConfirmation).toBe('Awaiting Confirmation');
    expect(translations.hi.status.awaitingConfirmation).toBe('पुष्टि प्रतीक्षित');
  });

  it('matches all navigation items across languages', () => {
    const enKeys = Object.keys(translations.en.nav).sort();
    const hiKeys = Object.keys(translations.hi.nav).sort();
    expect(enKeys).toEqual(hiKeys);
  });
});
