import { test, expect } from '@playwright/test';
import { setupApiMocks, injectAuthSession } from './fixtures/testHelper';
import { mockSchemesList } from './fixtures/mockData';

test.describe('Voice-First & Text-to-Speech Accessibility', () => {
  test.beforeEach(async ({ page }) => {
    // Inject mock SpeechSynthesis and SpeechRecognition APIs into browser context
    await page.addInitScript(() => {
      const spokenUtterances: string[] = [];
      (window as any).__spokenUtterances = spokenUtterances;
      (window as any).__cancelledCount = 0;

      const mockSynth = {
        speaking: false,
        paused: false,
        pending: false,
        onvoiceschanged: null,
        getVoices: () => [
          { name: 'Google हिन्दी', lang: 'hi-IN', default: true },
          { name: 'Google English (India)', lang: 'en-IN', default: false },
        ],
        speak: (utterance: any) => {
          mockSynth.speaking = true;
          if (!(window as any).__spokenUtterances) {
            (window as any).__spokenUtterances = [];
          }
          (window as any).__spokenUtterances.push(utterance.text);
          if (utterance.onstart) utterance.onstart();
          setTimeout(() => {
            mockSynth.speaking = false;
            if (utterance.onend) utterance.onend();
          }, 300);
        },
        cancel: () => {
          mockSynth.speaking = false;
          (window as any).__cancelledCount++;
        },
        pause: () => {
          mockSynth.paused = true;
        },
        resume: () => {
          mockSynth.paused = false;
        },
      };

      Object.defineProperty(window, 'speechSynthesis', {
        value: mockSynth,
        writable: true,
        configurable: true,
      });

      class MockSpeechSynthesisUtterance {
        text: string;
        lang = 'hi-IN';
        rate = 1.0;
        pitch = 1.0;
        voice = null;
        onstart: any = null;
        onend: any = null;
        onerror: any = null;
        constructor(text: string) {
          this.text = text;
        }
      }
      (window as any).SpeechSynthesisUtterance = MockSpeechSynthesisUtterance;

      class MockSpeechRecognition {
        lang = 'hi-IN';
        continuous = false;
        interimResults = true;
        maxAlternatives = 1;
        onstart: any = null;
        onresult: any = null;
        onerror: any = null;
        onend: any = null;

        start() {
          (window as any).__mockRecognizerInstance = this;
          setTimeout(() => {
            if (this.onstart) this.onstart();
          }, 50);
        }

        stop() {
          setTimeout(() => {
            if (this.onend) this.onend();
          }, 50);
        }

        abort() {
          setTimeout(() => {
            if (this.onend) this.onend();
          }, 50);
        }
      }

      (window as any).SpeechRecognition = MockSpeechRecognition;
      (window as any).webkitSpeechRecognition = MockSpeechRecognition;
    });

    await setupApiMocks(page);
    await injectAuthSession(page);
  });

  test('plays assistant message aloud using Text-to-Speech (TTS) on speaker click', async ({ page }) => {
    await page.goto('/');

    // Locate speaker button on initial welcome message
    const speakerBtn = page.getByRole('button', { name: /आवाज में सुनें|Listen aloud/i }).first();
    await expect(speakerBtn).toBeVisible();

    // Click speaker to trigger synthesis
    await speakerBtn.click();

    // Verify speech synthesis speak() was invoked with welcome text
    const spoken = await page.evaluate(() => (window as any).__spokenUtterances);
    expect(spoken.length).toBeGreaterThan(0);
    expect(spoken[0]).toContain('योजना साथी');

    // Click again to toggle stop
    await speakerBtn.click();
    const cancelledCount = await page.evaluate(() => (window as any).__cancelledCount);
    expect(cancelledCount).toBeGreaterThan(0);
  });

  test('auto-reads incoming assistant responses when Auto-Read mode is toggled on', async ({ page }) => {
    await page.goto('/');

    // Toggle Auto-Read in header
    const autoReadBtn = page.getByRole('button', { name: /ऑटो-रीड|Auto-Read/i });
    await expect(autoReadBtn).toBeVisible();
    await autoReadBtn.click();

    // Verify auto-read toggle activated
    await expect(page.getByRole('button', { name: /ऑटो-रीड चालू|Auto-Read On/i })).toBeVisible();

    // Clear previously spoken list
    await page.evaluate(() => {
      (window as any).__spokenUtterances = [];
    });

    // Click suggested question chip to trigger assistant response
    const chip = page.locator('text=पीएम किसान योजना की पात्रता क्या है?').first();
    await chip.click();

    // Wait for assistant response to appear
    await expect(page.locator('text=100% पात्र हैं').first()).toBeVisible();

    // Verify assistant reply was automatically read aloud
    const spoken = await page.evaluate(() => (window as any).__spokenUtterances);
    expect(spoken.length).toBeGreaterThan(0);
    expect(spoken[spoken.length - 1]).toContain('100% पात्र हैं');
  });

  test('opens voice visualizer modal upon mic click and submits transcribed speech', async ({ page }) => {
    await page.goto('/');

    // Click microphone button
    const micBtn = page.getByRole('button', { name: /Voice input/i });
    await expect(micBtn).toBeVisible();
    await micBtn.click();

    // Voice visualizer modal opens
    const modal = page.locator('div[role="dialog"][aria-label="Voice input visualizer"]');
    await expect(modal).toBeVisible();
    await expect(modal).toContainText(/आपकी आवाज सुनी जा रही है|Listening to your voice/i);

    // Simulate speech recognition result event from browser recognizer
    await page.evaluate(() => {
      const recognizer = (window as any).__mockRecognizerInstance;
      if (recognizer && recognizer.onresult) {
        recognizer.onresult({
          resultIndex: 0,
          results: [
            [
              { transcript: 'पीएम किसान योजना की पात्रता क्या है' },
            ],
          ],
        });
      }
    });

    // Confirm transcript appears in modal
    await expect(modal).toContainText('पीएम किसान योजना की पात्रता क्या है');

    // Click Done / Submit
    const doneBtn = modal.getByRole('button', { name: /पूरा हुआ|Done/i });
    await doneBtn.click();

    // Modal closes
    await expect(modal).not.toBeVisible();

    // Verify assistant responds to the voice query
    await expect(page.locator('text=100% पात्र हैं').first()).toBeVisible();
  });

  test('executes voice search in schemes discovery catalogue and filters cards', async ({ page }) => {
    await page.goto('/schemes');
    await expect(page.locator('text=Pradhan Mantri Kisan Samman Nidhi').first()).toBeVisible();

    // Click voice search mic button inside search bar
    const voiceSearchBtn = page.getByRole('button', { name: /Voice search schemes/i });
    await expect(voiceSearchBtn).toBeVisible();
    await voiceSearchBtn.click();

    // Simulate recognition of "Awas"
    await page.evaluate(() => {
      const recognizer = (window as any).__mockRecognizerInstance;
      if (recognizer && recognizer.onresult) {
        const item: any = [{ transcript: 'Awas' }];
        item.isFinal = true;
        recognizer.onresult({
          resultIndex: 0,
          results: [item],
        });
        if (recognizer.onend) recognizer.onend();
      }
    });

    // Verify search input populates and PMAY card is filtered
    const searchInput = page.locator('input[type="text"]').first();
    await expect(searchInput).toHaveValue('Awas');
    await expect(page.locator('text=Pradhan Mantri Awas Yojana').first()).toBeVisible();
  });

  test('plays scheme details and key benefits aloud on scheme detail page', async ({ page }) => {
    await page.goto(`/schemes/${mockSchemesList[0].id}`);

    // Verify scheme header has speaker button
    const speakerBtn = page.getByRole('button', { name: /आवाज में सुनें|Listen aloud/i }).first();
    await expect(speakerBtn).toBeVisible();

    // Clear spoken list
    await page.evaluate(() => {
      (window as any).__spokenUtterances = [];
    });

    // Click speaker
    await speakerBtn.click();

    // Verify speech synthesis received scheme information
    const spoken = await page.evaluate(() => (window as any).__spokenUtterances);
    expect(spoken.length).toBeGreaterThan(0);
    expect(spoken[0]).toContain('Pradhan Mantri Kisan Samman Nidhi');
  });

  test('gracefully handles unsupported speech recognition without application crash', async ({ page }) => {
    // Override window speech recognition to simulate unsupported browser
    await page.addInitScript(() => {
      delete (window as any).SpeechRecognition;
      delete (window as any).webkitSpeechRecognition;
    });

    await page.goto('/');

    const micBtn = page.getByRole('button', { name: /Voice input/i });
    await expect(micBtn).toBeVisible();
    await micBtn.click();

    // Verify non-blocking warning message appears
    await expect(page.locator('text=समर्थित नहीं है')).toBeVisible();

    // Verify standard text chat still functions
    const input = page.locator('input[placeholder*="पूछें"]');
    await input.fill('सहायता');
    const sendBtn = page.locator('button[type="submit"]');
    await expect(sendBtn).toBeEnabled();
  });
});
