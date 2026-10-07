import React from 'react';
import { useBranding } from '../contexts/BrandingContext';

export const GlobalWatermark: React.FC = () => {
  const { branding } = useBranding();

  if (!branding?.watermark_url) return null;

  return (
    <div className="global-bg-watermark" aria-hidden="true" style={{ opacity: branding.watermark_opacity ? Number(branding.watermark_opacity) : 0.08 }}>
      <div className="global-bg-watermark-glow" />
      <div 
        className="global-bg-watermark-logo" 
        style={{ backgroundImage: `url(${branding.watermark_url})` }}
      />
    </div>
  );
};
