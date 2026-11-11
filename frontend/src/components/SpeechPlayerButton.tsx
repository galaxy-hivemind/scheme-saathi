import React, { useState, useEffect } from 'react';
import { Volume2, VolumeX } from 'lucide-react';
import { speechSynthesizer, isSpeechSynthesisSupported } from '../utils/speechSynthesis';
import { useLanguage } from '../context/LanguageContext';

interface SpeechPlayerButtonProps {
  text: string;
  lang?: 'hi-IN' | 'en-IN' | string;
  className?: string;
  size?: 'sm' | 'md';
}

export const SpeechPlayerButton: React.FC<SpeechPlayerButtonProps> = ({
  text,
  lang,
  className = '',
  size = 'sm',
}) => {
  const { language } = useLanguage();
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [isSupported] = useState<boolean>(() => isSpeechSynthesisSupported());

  const targetLang = lang || (language === 'hi' ? 'hi-IN' : 'en-IN');

  useEffect(() => {
    return () => {
      // If unmounted while speaking this text, stop
      if (isPlaying) {
        speechSynthesizer.stop();
      }
    };
  }, [isPlaying]);

  if (!isSupported || !text || text.trim().length === 0) {
    return null;
  }

  const handleTogglePlay = (e: React.MouseEvent) => {
    e.stopPropagation();

    if (isPlaying) {
      speechSynthesizer.stop();
      setIsPlaying(false);
    } else {
      setIsPlaying(true);
      speechSynthesizer.speak(text, {
        lang: targetLang,
        onStart: () => setIsPlaying(true),
        onEnd: () => setIsPlaying(false),
        onError: () => setIsPlaying(false),
      });
    }
  };

  const buttonTitle = isPlaying
    ? language === 'hi'
      ? 'आवाज बंद करें / Stop audio'
      : 'Stop audio'
    : language === 'hi'
    ? 'आवाज में सुनें / Listen aloud'
    : 'Listen aloud';

  const iconSize = size === 'sm' ? 'w-4 h-4' : 'w-5 h-5';
  const padding = size === 'sm' ? 'p-1.5' : 'p-2';

  return (
    <button
      type="button"
      onClick={handleTogglePlay}
      className={`rounded-xl transition-all flex items-center justify-center ${padding} ${
        isPlaying
          ? 'bg-orange-100 text-orange-700 ring-2 ring-orange-500/40 animate-pulse'
          : 'text-slate-400 hover:text-orange-600 hover:bg-orange-50'
      } ${className}`}
      title={buttonTitle}
      aria-label={buttonTitle}
    >
      {isPlaying ? (
        <VolumeX className={`${iconSize} text-orange-600`} />
      ) : (
        <Volume2 className={iconSize} />
      )}
    </button>
  );
};
