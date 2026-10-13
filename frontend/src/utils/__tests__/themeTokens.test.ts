import { describe, it, expect, beforeEach } from 'vitest';
import {
  hexToRgb,
  rgbToHex,
  rgbToHsl,
  hslToHex,
  isValidHex,
  generateClientPalettes,
  applyThemeTokens,
  clearThemeTokens,
  getContrastRatio,
} from '../themeTokens';

describe('themeTokens utility', () => {
  beforeEach(() => {
    clearThemeTokens();
  });

  it('converts hex to rgb and rgb to hex accurately', () => {
    const rgb = hexToRgb('#166534');
    expect(rgb).toEqual([22, 101, 52]);

    const hex = rgbToHex(22, 101, 52);
    expect(hex).toBe('#166534');
  });

  it('validates hex codes correctly', () => {
    expect(isValidHex('#166534')).toBe(true);
    expect(isValidHex('#FFF')).toBe(true);
    expect(isValidHex('166534')).toBe(false);
    expect(isValidHex('#ZZZ')).toBe(false);
    expect(isValidHex('')).toBe(false);
  });

  it('converts between RGB and HSL', () => {
    const [h, s, l] = rgbToHsl(22, 101, 52);
    expect(h).toBeGreaterThan(130);
    expect(h).toBeLessThan(150);
    expect(s).toBeGreaterThan(0.5);
    expect(l).toBeGreaterThan(0.2);

    const reconstructedHex = hslToHex(h, s, l);
    expect(isValidHex(reconstructedHex)).toBe(true);
  });

  it('generates 3 accessible coordinated palettes', () => {
    const palettes = generateClientPalettes('#166534');
    expect(palettes).toHaveLength(3);
    expect(palettes[0].id).toBe('vibrant');
    expect(palettes[1].id).toBe('professional');
    expect(palettes[2].id).toBe('deep');

    for (const pal of palettes) {
      expect(isValidHex(pal.primary_color)).toBe(true);
      expect(isValidHex(pal.secondary_color)).toBe(true);
      expect(isValidHex(pal.accent_color)).toBe(true);
      expect(isValidHex(pal.sidebar_bg_color)).toBe(true);
    }
  });

  it('applies and clears CSS variables dynamically', () => {
    const root = document.documentElement;

    applyThemeTokens({
      branding_mode: 'custom',
      primary_color: '#166534',
      secondary_color: '#15803D',
      accent_color: '#4ADE80',
      sidebar_bg_color: '#F0FDF4',
    });

    expect(root.style.getPropertyValue('--color-primary')).toBe('#166534');
    expect(root.style.getPropertyValue('--color-secondary')).toBe('#15803D');
    expect(root.style.getPropertyValue('--color-accent')).toBe('#4ADE80');
    expect(root.style.getPropertyValue('--sidebar-bg')).toBe('#F0FDF4');

    // In Mode A (default), variables must be removed
    applyThemeTokens({
      branding_mode: 'default',
      primary_color: '#166534',
    });

    expect(root.style.getPropertyValue('--color-primary')).toBe('');
    expect(root.style.getPropertyValue('--color-secondary')).toBe('');
  });

  it('guarantees WCAG AA accessible contrast (>= 4.5:1 against white) across challenging hues', () => {
    const challengingHexes = ['#F59E0B', '#EAB308', '#84CC16', '#06B6D4', '#EC4899'];
    for (const hex of challengingHexes) {
      const palettes = generateClientPalettes(hex);
      for (const pal of palettes) {
        const ratio = getContrastRatio(pal.primary_color, '#FFFFFF');
        expect(ratio).toBeGreaterThanOrEqual(4.5);
      }
    }
  });
});
