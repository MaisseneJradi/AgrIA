// Dictation with the Web Speech API, when the browser has it (Chrome on Android does; Firefox does not): the button is
// shown only then. The text is put in the message field, the farmer can correct it before sending.
import type { Lang } from "./i18n";

interface Recognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
}
type RecognitionCtor = new () => Recognition;

export function speechCtor(): RecognitionCtor | null {
  const w = window as unknown as {
    SpeechRecognition?: RecognitionCtor;
    webkitSpeechRecognition?: RecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

// Tunisian Arabic first (the farmer speaks darija); French of France for French
export const SPEECH_LANG: Record<Lang, string> = { fr: "fr-FR", ar: "ar-TN" };

/** Starts listening; onText receives the recognised sentence; returns a function that stops. */
export function listen(lang: Lang, onText: (text: string) => void, onEnd: () => void): () => void {
  const Ctor = speechCtor();
  if (!Ctor) {
    onEnd();
    return () => undefined;
  }
  const r = new Ctor();
  r.lang = SPEECH_LANG[lang];
  r.interimResults = false;
  r.continuous = false;
  r.onresult = (e) => {
    const text = Array.from(e.results)
      .map((res) => res[0]?.transcript ?? "")
      .join(" ")
      .trim();
    if (text) onText(text);
  };
  r.onend = onEnd;
  r.onerror = onEnd;
  r.start();
  return () => r.stop();
}
