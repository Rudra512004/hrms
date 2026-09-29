import React from 'react';

export const GlobalWatermark: React.FC = () => {
  return (
    <div className="global-bg-watermark" aria-hidden="true">
      <div className="global-bg-watermark-glow" />
      <div className="global-bg-watermark-logo" />
    </div>
  );
};
