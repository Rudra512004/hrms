/**
 * BeyondSure HRMS — Phase 3F Theme Tokens and Color Utilities
 * Provides deterministic color manipulation, WCAG contrast calculation,
 * and CSS variable injection/removal for organization branding.
 */

import { type BrandingConfig } from '../services/organization';

export function hexToRgb(hex: string): [number, number, number] {
  let clean = hex.replace('#', '').trim();
  if (clean.length === 3) {
    clean = clean.split('').map(c => c + c).join('');
  }
  const num = parseInt(clean, 16);
  if (isNaN(num)) return [22, 101, 52]; // Default fallback green
  return [(num >> 16) & 255, (num >> 8) & 255, num & 255];
}

export function rgbToHex(r: number, g: number, b: number): string {
  const clamp = (v: number) => Math.max(0, Math.min(255, Math.round(v)));
  const toHex = (v: number) => clamp(v).toString(16).padStart(2, '0').toUpperCase();
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

export function rgbToHsl(r: number, g: number, b: number): [number, number, number] {
  r /= 255;
  g /= 255;
  b /= 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h = 0;
  let s = 0;
  const l = (max + min) / 2;

  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = (g - b) / d + (g < b ? 6 : 0); break;
      case g: h = (b - r) / d + 2; break;
      case b: h = (r - g) / d + 4; break;
    }
    h *= 60;
  }
  return [Math.round(h), s, l];
}

export function hslToHex(h: number, s: number, l: number): string {
  h = ((h % 360) + 360) % 360;
  s = Math.max(0, Math.min(1, s));
  l = Math.max(0, Math.min(1, l));

  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = l - c / 2;
  let r = 0, g = 0, b = 0;

  if (0 <= h && h < 60) { r = c; g = x; b = 0; }
  else if (60 <= h && h < 120) { r = x; g = c; b = 0; }
  else if (120 <= h && h < 180) { r = 0; g = c; b = x; }
  else if (180 <= h && h < 240) { r = 0; g = x; b = c; }
  else if (240 <= h && h < 300) { r = x; g = 0; b = c; }
  else if (300 <= h && h < 360) { r = c; g = 0; b = x; }

  return rgbToHex((r + m) * 255, (g + m) * 255, (b + m) * 255);
}

export function isValidHex(hex?: string): boolean {
  if (!hex) return false;
  return /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(hex.trim());
}

export function getRelativeLuminance(r: number, g: number, b: number): number {
  const channelLum = (val: number) => {
    const v = val / 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * channelLum(r) + 0.7152 * channelLum(g) + 0.0722 * channelLum(b);
}

export function getContrastRatio(hex1: string, hex2: string): number {
  const lum1 = getRelativeLuminance(...hexToRgb(hex1));
  const lum2 = getRelativeLuminance(...hexToRgb(hex2));
  const lighter = Math.max(lum1, lum2);
  const darker = Math.min(lum1, lum2);
  return (lighter + 0.05) / (darker + 0.05);
}

export function ensureAccessiblePrimary(h: number, s: number, l: number): string {
  let targetL = Math.min(l, 0.42);
  const targetS = Math.max(s, 0.40);
  let candidate = hslToHex(h, targetS, targetL);
  while (getContrastRatio(candidate, '#FFFFFF') < 4.5 && targetL > 0.12) {
    targetL -= 0.02;
    candidate = hslToHex(h, targetS, targetL);
  }
  return candidate;
}

/**
 * Generates 3 accessible coordinated palettes for a chosen hue or base hex color.
 */
export function generateClientPalettes(baseHex: string) {
  if (!isValidHex(baseHex)) baseHex = '#166534';
  const [r, g, b] = hexToRgb(baseHex);
  let [h, s, l] = rgbToHsl(r, g, b);

  if (s < 0.12) {
    h = 142;
    s = 0.65;
    l = 0.32;
  }

  return [
    {
      id: 'vibrant',
      name: 'Brand Vibrant',
      description: 'Lively and bold, highlighting your extracted dominant brand identity.',
      primary_color: ensureAccessiblePrimary(h, Math.max(s, 0.45), l),
      secondary_color: hslToHex(h + 25, Math.min(1, s * 0.9), 0.38),
      accent_color: hslToHex(h + 45, Math.min(1, s * 0.95), 0.55),
      sidebar_bg_color: hslToHex(h, 0.18, 0.97),
    },
    {
      id: 'professional',
      name: 'Modern Professional',
      description: 'Balanced, refined tones optimized for enterprise readability.',
      primary_color: ensureAccessiblePrimary(h, Math.max(0.40, s * 0.70), 0.34),
      secondary_color: hslToHex(h - 20, Math.max(0.35, s * 0.65), 0.42),
      accent_color: hslToHex(h + 30, 0.75, 0.50),
      sidebar_bg_color: '#F8FAFC',
    },
    {
      id: 'deep',
      name: 'Deep Focus',
      description: 'Rich deep primary shade paired with crisp, high-contrast interactive elements.',
      primary_color: ensureAccessiblePrimary(h, Math.max(0.55, s * 0.85), 0.22),
      secondary_color: hslToHex(h + 15, 0.80, 0.48),
      accent_color: hslToHex(h, 0.85, 0.60),
      sidebar_bg_color: hslToHex(h, 0.30, 0.14),
    },
  ];
}

const CUSTOM_CSS_PROPERTIES = [
  '--color-primary',
  '--color-primary-hover',
  '--color-primary-light',
  '--color-primary-border',
  '--color-primary-glow',
  '--color-secondary',
  '--color-secondary-hover',
  '--color-accent',
  '--sidebar-bg',
  '--color-bg-sidebar',
  '--font-family',
];

/**
 * Injects or removes CSS variables dynamically based on active branding configuration.
 */
export function applyThemeTokens(config: BrandingConfig | null) {
  const root = document.documentElement;

  if (!config || config.branding_mode === 'default' || !config.primary_color) {
    // Mode A (Default Theme) or unconfigured: restore platform defaults
    clearThemeTokens();
    return;
  }

  // Mode B (Custom Theme): apply tokens
  const primary = config.primary_color;
  const [r, g, b] = hexToRgb(primary);
  const [h, s, l] = rgbToHsl(r, g, b);

  root.style.setProperty('--color-primary', primary);
  root.style.setProperty('--color-primary-hover', hslToHex(h, s, Math.max(0.12, l - 0.08)));
  root.style.setProperty('--color-primary-light', hslToHex(h, Math.min(s, 0.50), 0.94));
  root.style.setProperty('--color-primary-border', hslToHex(h, Math.min(s, 0.60), 0.78));
  root.style.setProperty('--color-primary-glow', `rgba(${r}, ${g}, ${b}, 0.2)`);

  if (config.secondary_color) {
    root.style.setProperty('--color-secondary', config.secondary_color);
    const [sr, sg, sb] = hexToRgb(config.secondary_color);
    const [sh, ss, sl] = rgbToHsl(sr, sg, sb);
    root.style.setProperty('--color-secondary-hover', hslToHex(sh, ss, Math.max(0.10, sl - 0.08)));
  }

  if (config.accent_color) {
    root.style.setProperty('--color-accent', config.accent_color);
  }

  if (config.sidebar_bg_color) {
    root.style.setProperty('--sidebar-bg', config.sidebar_bg_color);
    root.style.setProperty('--color-bg-sidebar', config.sidebar_bg_color);
  }

  if (config.font_family) {
    root.style.setProperty('--font-family', config.font_family);
  }
}

/**
 * Removes all custom CSS variables, falling back to base styles.
 */
export function clearThemeTokens() {
  const root = document.documentElement;
  for (const prop of CUSTOM_CSS_PROPERTIES) {
    root.style.removeProperty(prop);
  }
}
