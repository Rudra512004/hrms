import React, { useRef, useCallback } from 'react';

interface HueSpectrumSliderProps {
  hue: number;
  onChange: (hue: number) => void;
  disabled?: boolean;
}

export const HueSpectrumSlider: React.FC<HueSpectrumSliderProps> = ({
  hue,
  onChange,
  disabled = false,
}) => {
  const barRef = useRef<HTMLDivElement>(null);

  const calculateHueFromPointer = useCallback(
    (clientX: number) => {
      if (!barRef.current || disabled) return;
      const rect = barRef.current.getBoundingClientRect();
      const x = Math.max(0, Math.min(clientX - rect.left, rect.width));
      const percentage = rect.width > 0 ? x / rect.width : 0;
      const newHue = Math.round(percentage * 360);
      onChange(Math.min(360, Math.max(0, newHue)));
    },
    [disabled, onChange]
  );

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (disabled) return;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    calculateHueFromPointer(e.clientX);
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (disabled || e.buttons === 0) return;
    calculateHueFromPointer(e.clientX);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (disabled) return;
    if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
      e.preventDefault();
      onChange((hue + 5) % 360);
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
      e.preventDefault();
      onChange((hue - 5 + 360) % 360);
    }
  };

  const percentage = Math.min(100, Math.max(0, (hue / 360) * 100));

  return (
    <div
      ref={barRef}
      role="slider"
      tabIndex={disabled ? -1 : 0}
      aria-label="Brand Hue Spectrum Slider"
      aria-valuemin={0}
      aria-valuemax={360}
      aria-valuenow={hue}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onKeyDown={handleKeyDown}
      style={{
        position: 'relative',
        width: '100%',
        height: '14px',
        borderRadius: '9999px',
        background:
          'linear-gradient(to right, #FF2200 0%, #FF8800 12%, #FFE600 24%, #10B981 38%, #06B6D4 52%, #3B82F6 66%, #8B5CF6 80%, #EC4899 92%, #FF2200 100%)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        userSelect: 'none',
        touchAction: 'none',
        opacity: disabled ? 0.6 : 1,
      }}
    >
      {/* Draggable Indicator Thumb */}
      <div
        style={{
          position: 'absolute',
          top: '50%',
          left: `${percentage}%`,
          transform: 'translate(-50%, -50%)',
          width: '22px',
          height: '22px',
          borderRadius: '50%',
          backgroundColor: '#FFFFFF',
          border: '3px solid #10B981',
          boxShadow: '0 2px 6px rgba(0, 0, 0, 0.35)',
          transition: 'transform 0.1s ease, border-color 0.1s ease',
          pointerEvents: 'none',
        }}
      />
    </div>
  );
};
