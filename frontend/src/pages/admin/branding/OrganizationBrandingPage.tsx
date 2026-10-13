import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Upload,
  X,
  Check,
  Info,
  Sliders,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Sparkles,
} from 'lucide-react';
import { useBranding } from '../../../contexts/BrandingContext';
import { useAuth } from '../../../contexts/AuthContext';
import { HueSpectrumSlider } from './HueSpectrumSlider';
import { BrandingLivePreview } from './BrandingLivePreview';
import {
  generateClientPalettes,
  hslToHex,
  rgbToHsl,
  hexToRgb,
  isValidHex,
} from '../../../utils/themeTokens';
import { type PaletteSuggestion, type BrandingConfig } from '../../../services/organization';

export const OrganizationBrandingPage: React.FC = () => {
  const navigate = useNavigate();
  const { branding, updateBranding, uploadLogo, removeLogo } = useBranding();
  const { user, hasPermission } = useAuth();
  const canManage = hasPermission('branding.manage');

  // Mode: 'default' (Mode A) or 'custom' (Mode B)
  const [brandingMode, setBrandingMode] = useState<'default' | 'custom'>('default');

  // Active logo state
  const [previewLogoUrl, setPreviewLogoUrl] = useState<string>('');
  const [pendingLogoFile, setPendingLogoFile] = useState<File | null>(null);

  // Palettes & Selection
  const [palettes, setPalettes] = useState<PaletteSuggestion[]>([]);
  const [selectedPaletteId, setSelectedPaletteId] = useState<string>('vibrant');

  // Custom Colors (Mode B)
  const [primaryColor, setPrimaryColor] = useState<string>('#166534');
  const [secondaryColor, setSecondaryColor] = useState<string>('#15803D');
  const [accentColor, setAccentColor] = useState<string>('#4ADE80');
  const [sidebarBgColor, setSidebarBgColor] = useState<string>('#FFFFFF');
  const [hue, setHue] = useState<number>(142);

  // Manual Overrides
  const [manualOverrides, setManualOverrides] = useState<Record<string, string>>({});
  const [showManualOverrides, setShowManualOverrides] = useState<boolean>(false);

  // Logo replacement notification
  const [newPalettesAvailable, setNewPalettesAvailable] = useState<PaletteSuggestion[] | null>(null);

  // Status & UI States
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDirty, setIsDirty] = useState<boolean>(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Initialize state from existing backend branding
  useEffect(() => {
    if (branding) {
      const mode = (branding.branding_mode as 'default' | 'custom') || 'default';
      setBrandingMode(mode);
      setPreviewLogoUrl(branding.logo_url || '');

      const initialPrimary = branding.primary_color || '#166534';
      setPrimaryColor(initialPrimary);
      setSecondaryColor(branding.secondary_color || '#15803D');
      setAccentColor(branding.accent_color || '#4ADE80');
      setSidebarBgColor(branding.sidebar_bg_color || '#FFFFFF');
      setManualOverrides(branding.manual_overrides || {});

      const [r, g, b] = hexToRgb(initialPrimary);
      const [h] = rgbToHsl(r, g, b);
      setHue(h);

      if (branding.palette_suggestions && branding.palette_suggestions.length > 0) {
        setPalettes(branding.palette_suggestions);
        setSelectedPaletteId(branding.selected_palette || branding.palette_suggestions[0].id);
      } else {
        const generated = generateClientPalettes(initialPrimary);
        setPalettes(generated);
        setSelectedPaletteId('vibrant');
      }
      setIsDirty(false);
    }
  }, [branding]);

  // Client-side deterministic color extraction from image via Canvas
  const extractDominantColorFromImage = useCallback((fileOrUrl: File | string): Promise<string> => {
    return new Promise((resolve) => {
      const img = new Image();
      img.crossOrigin = 'Anonymous';

      img.onload = () => {
        try {
          const canvas = document.createElement('canvas');
          const ctx = canvas.getContext('2d');
          if (!ctx) return resolve('#166534');

          canvas.width = 64;
          canvas.height = 64;
          ctx.drawImage(img, 0, 0, 64, 64);
          const imageData = ctx.getImageData(0, 0, 64, 64);
          const data = imageData.data;

          const colorCounts: Record<string, number> = {};
          for (let i = 0; i < data.length; i += 4) {
            const r = data[i];
            const g = data[i + 1];
            const b = data[i + 2];
            const a = data[i + 3];

            if (a < 40) continue; // transparent
            if (r > 240 && g > 240 && b > 240) continue; // near-white
            if (r < 20 && g < 20 && b < 20) continue; // near-black

            // Quantize
            const qr = Math.floor(r / 16) * 16;
            const qg = Math.floor(g / 16) * 16;
            const qb = Math.floor(b / 16) * 16;
            const key = `${qr},${qg},${qb}`;
            colorCounts[key] = (colorCounts[key] || 0) + 1;
          }

          let maxCount = 0;
          let dominantRgb = [22, 101, 52];
          for (const [key, count] of Object.entries(colorCounts)) {
            if (count > maxCount) {
              maxCount = count;
              dominantRgb = key.split(',').map(Number);
            }
          }

          const [r, g, b] = dominantRgb;
          const hex = `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`.toUpperCase();
          resolve(hex);
        } catch {
          resolve('#166534');
        }
      };

      img.onerror = () => resolve('#166534');

      if (typeof fileOrUrl === 'string') {
        img.src = fileOrUrl;
      } else {
        const reader = new FileReader();
        reader.onload = (e) => {
          img.src = (e.target?.result as string) || '';
        };
        reader.readAsDataURL(fileOrUrl);
      }
    });
  }, []);

  // Handle Logo File Upload (Mode A and Mode B)
  const handleLogoFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setErrorMessage(null);
    setSaveSuccess(null);

    // Validate size (2MB max)
    if (file.size > 2 * 1024 * 1024) {
      setErrorMessage('Logo file size must not exceed 2 MB.');
      return;
    }

    // Validate type
    const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp'];
    if (!validTypes.includes(file.type)) {
      setErrorMessage('Unsupported format. Please upload a PNG, JPEG, or WEBP image.');
      return;
    }

    const localPreviewUrl = URL.createObjectURL(file);
    setPreviewLogoUrl(localPreviewUrl);
    setPendingLogoFile(file);
    setIsDirty(true);

    if (brandingMode === 'custom') {
      // Deterministically analyze logo and generate new palette suggestions
      const dominantHex = await extractDominantColorFromImage(file);
      const newSuggestions = generateClientPalettes(dominantHex);
      setNewPalettesAvailable(newSuggestions);
    }
  };

  // Remove Logo
  const handleRemoveLogo = () => {
    setPreviewLogoUrl('');
    setPendingLogoFile(null);
    setIsDirty(true);
    setErrorMessage(null);
  };

  // Handle Palette Selection
  const handleSelectPalette = (palette: PaletteSuggestion) => {
    setSelectedPaletteId(palette.id);
    setPrimaryColor(palette.primary_color);
    setSecondaryColor(palette.secondary_color);
    setAccentColor(palette.accent_color);
    setSidebarBgColor(palette.sidebar_bg_color);

    const [r, g, b] = hexToRgb(palette.primary_color);
    const [h] = rgbToHsl(r, g, b);
    setHue(h);

    setManualOverrides({});
    setIsDirty(true);
  };

  // Handle Rainbow Hue Spectrum Slider change
  const handleHueChange = (newHue: number) => {
    setHue(newHue);
    const baseHex = hslToHex(newHue, 0.65, 0.32);
    const updatedPalettes = generateClientPalettes(baseHex);
    setPalettes(updatedPalettes);

    const matched = updatedPalettes.find((p) => p.id === selectedPaletteId) || updatedPalettes[0];
    setPrimaryColor(matched.primary_color);
    setSecondaryColor(matched.secondary_color);
    setAccentColor(matched.accent_color);
    setSidebarBgColor(matched.sidebar_bg_color);
    setIsDirty(true);
  };

  // Apply Newly Generated Palettes explicitly
  const handleApplyNewPalettes = () => {
    if (!newPalettesAvailable) return;
    setPalettes(newPalettesAvailable);
    const first = newPalettesAvailable[0];
    handleSelectPalette(first);
    setNewPalettesAvailable(null);
  };

  // Dismiss New Palette Suggestions Banner
  const handleDismissNewPalettes = () => {
    setNewPalettesAvailable(null);
  };

  // Save Branding
  const handleSave = async () => {
    if (!canManage) {
      setErrorMessage('You do not have permission to modify organization branding.');
      return;
    }

    setIsSaving(true);
    setErrorMessage(null);
    setSaveSuccess(null);

    try {
      // 1. If a new logo file was selected, upload it
      let activeLogoUrl = previewLogoUrl;
      if (pendingLogoFile) {
        const uploadResult = await uploadLogo(pendingLogoFile);
        activeLogoUrl = uploadResult.logo_url || '';
        setPendingLogoFile(null);
      } else if (!previewLogoUrl && branding?.logo_url) {
        // Logo was removed
        await removeLogo();
        activeLogoUrl = '';
      }

      // 2. Persist branding configuration
      const payload: Partial<BrandingConfig> = {
        branding_mode: brandingMode,
        logo_url: activeLogoUrl,
      };

      if (brandingMode === 'custom') {
        payload.primary_color = primaryColor;
        payload.secondary_color = secondaryColor;
        payload.accent_color = accentColor;
        payload.sidebar_bg_color = sidebarBgColor;
        payload.selected_palette = selectedPaletteId;
        payload.palette_suggestions = palettes;
        payload.manual_overrides = manualOverrides;
      }

      await updateBranding(payload);
      setSaveSuccess('Organization branding and live theme saved successfully!');
      setIsDirty(false);
      setNewPalettesAvailable(null);
    } catch (err: any) {
      console.error('Failed to save branding:', err);
      const detail = err?.data?.detail || err?.data?.file?.[0] || err?.message || 'Failed to save branding configuration.';
      setErrorMessage(detail);
    } finally {
      setIsSaving(false);
    }
  };

  // Revert / Cancel Changes
  const handleRevert = () => {
    if (branding) {
      setBrandingMode((branding.branding_mode as 'default' | 'custom') || 'default');
      setPreviewLogoUrl(branding.logo_url || '');
      setPendingLogoFile(null);
      setPrimaryColor(branding.primary_color || '#166534');
      setSecondaryColor(branding.secondary_color || '#15803D');
      setAccentColor(branding.accent_color || '#4ADE80');
      setSidebarBgColor(branding.sidebar_bg_color || '#FFFFFF');
      setManualOverrides(branding.manual_overrides || {});
      setPalettes(branding.palette_suggestions || generateClientPalettes(branding.primary_color || '#166534'));
      setSelectedPaletteId(branding.selected_palette || 'vibrant');
      setNewPalettesAvailable(null);
      setIsDirty(false);
      setErrorMessage(null);
      setSaveSuccess(null);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: '#FFFFFF',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Top Header Bar */}
      <header
        style={{
          borderBottom: '1px solid #E5E7EB',
          padding: '16px 32px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <button
          type="button"
          onClick={() => navigate('/admin/control-center')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            background: 'none',
            border: 'none',
            color: '#2563EB',
            fontSize: '14px',
            fontWeight: 600,
            cursor: 'pointer',
            padding: 0,
          }}
        >
          <ArrowLeft size={16} /> Back
        </button>

        {!canManage && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '12px',
              color: '#B45309',
              backgroundColor: '#FEF3C7',
              padding: '4px 12px',
              borderRadius: '9999px',
            }}
          >
            <Info size={14} /> Read-only mode: requires <code>branding.manage</code> permission.
          </div>
        )}
      </header>

      {/* Main Two-Column Layout matching Reference Image */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexWrap: 'wrap',
          minHeight: 'calc(100vh - 65px)',
        }}
      >
        {/* Left Column: Branding Controls */}
        <div
          style={{
            flex: '1 1 480px',
            maxWidth: '680px',
            padding: '40px 48px',
            boxSizing: 'border-box',
            display: 'flex',
            flexDirection: 'column',
            gap: '28px',
            overflowY: 'auto',
          }}
        >
          {/* Headline & Subtitle */}
          <div>
            <h1
              style={{
                fontSize: '32px',
                fontWeight: 800,
                color: '#14532D',
                fontFamily: 'serif',
                lineHeight: 1.2,
                margin: '0 0 12px 0',
              }}
            >
              Personalize the look &amp; feel
            </h1>
            <p
              style={{
                fontSize: '14px',
                color: '#4B5563',
                lineHeight: 1.5,
                margin: 0,
              }}
            >
              We take your snazzy brand color and generate a custom theme so that it's on-brand
              and optimized to make it easy for everyone to read.
            </p>
          </div>

          {/* Mode Selector (Mode A vs Mode B) */}
          <div
            style={{
              display: 'flex',
              backgroundColor: '#F3F4F6',
              padding: '4px',
              borderRadius: '12px',
              gap: '4px',
            }}
          >
            <button
              type="button"
              onClick={() => {
                setBrandingMode('default');
                setIsDirty(true);
              }}
              style={{
                flex: 1,
                padding: '8px 12px',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: brandingMode === 'default' ? '#FFFFFF' : 'transparent',
                color: brandingMode === 'default' ? '#111827' : '#6B7280',
                fontWeight: brandingMode === 'default' ? 600 : 500,
                fontSize: '13px',
                cursor: 'pointer',
                boxShadow: brandingMode === 'default' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                transition: 'all 0.15s ease',
              }}
            >
              Default Theme + Logo
            </button>
            <button
              type="button"
              onClick={() => {
                setBrandingMode('custom');
                setIsDirty(true);
              }}
              style={{
                flex: 1,
                padding: '8px 12px',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: brandingMode === 'custom' ? '#FFFFFF' : 'transparent',
                color: brandingMode === 'custom' ? '#14532D' : '#6B7280',
                fontWeight: brandingMode === 'custom' ? 600 : 500,
                fontSize: '13px',
                cursor: 'pointer',
                boxShadow: brandingMode === 'custom' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                transition: 'all 0.15s ease',
              }}
            >
              Custom Theme
            </button>
          </div>

          {/* Section: Logo */}
          <div>
            <h2
              style={{
                fontSize: '18px',
                fontWeight: 700,
                color: '#1F2937',
                marginBottom: '14px',
              }}
            >
              Logo
            </h2>

            <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
              {/* Active Logo Card */}
              {previewLogoUrl ? (
                <div
                  style={{
                    position: 'relative',
                    width: '120px',
                    height: '100px',
                    borderRadius: '14px',
                    border: '2px solid #86EFAC',
                    backgroundColor: '#FFFFFF',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: '12px',
                    boxSizing: 'border-box',
                    boxShadow: '0 2px 6px rgba(0,0,0,0.04)',
                  }}
                >
                  <img
                    src={previewLogoUrl}
                    alt="Organization Logo"
                    style={{
                      maxWidth: '100%',
                      maxHeight: '100%',
                      objectFit: 'contain',
                    }}
                  />
                  {canManage && (
                    <button
                      type="button"
                      onClick={handleRemoveLogo}
                      aria-label="Remove logo"
                      style={{
                        position: 'absolute',
                        top: '6px',
                        right: '6px',
                        width: '22px',
                        height: '22px',
                        borderRadius: '50%',
                        backgroundColor: '#FFFFFF',
                        border: '1px solid #D1D5DB',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#6B7280',
                        cursor: 'pointer',
                        padding: 0,
                        boxShadow: '0 1px 2px rgba(0,0,0,0.1)',
                      }}
                    >
                      <X size={14} />
                    </button>
                  )}
                </div>
              ) : null}

              {/* Upload Card */}
              <div
                onClick={() => canManage && fileInputRef.current?.click()}
                style={{
                  width: '140px',
                  height: '100px',
                  borderRadius: '14px',
                  border: '2px dashed #D1D5DB',
                  backgroundColor: '#FAFAFA',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  cursor: canManage ? 'pointer' : 'not-allowed',
                  transition: 'border-color 0.15s ease',
                  padding: '8px',
                  boxSizing: 'border-box',
                  textAlign: 'center',
                }}
              >
                <Upload size={20} color="#6B7280" />
                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 500,
                    color: '#4B5563',
                  }}
                >
                  {previewLogoUrl ? 'Upload a different logo' : 'Upload logo'}
                </span>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={handleLogoFileChange}
                  style={{ display: 'none' }}
                  disabled={!canManage}
                />
              </div>
            </div>
          </div>

          {/* New Palettes Available Banner (when logo replaced in Mode B) */}
          {newPalettesAvailable && brandingMode === 'custom' && (
            <div
              style={{
                backgroundColor: '#ECFDF5',
                border: '1px solid #A7F3D0',
                borderRadius: '12px',
                padding: '12px 16px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '12px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Sparkles size={18} color="#059669" />
                <span style={{ fontSize: '13px', color: '#065F46', fontWeight: 500 }}>
                  New color palettes generated from your uploaded logo!
                </span>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  onClick={handleApplyNewPalettes}
                  style={{
                    padding: '5px 12px',
                    backgroundColor: '#059669',
                    color: '#FFFFFF',
                    borderRadius: '8px',
                    border: 'none',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Apply New
                </button>
                <button
                  type="button"
                  onClick={handleDismissNewPalettes}
                  style={{
                    padding: '5px 8px',
                    backgroundColor: 'transparent',
                    color: '#6B7280',
                    borderRadius: '8px',
                    border: 'none',
                    fontSize: '12px',
                    cursor: 'pointer',
                  }}
                >
                  Keep Current
                </button>
              </div>
            </div>
          )}

          {/* Section: Color (Active in Mode B) */}
          {brandingMode === 'custom' ? (
            <div>
              <h2
                style={{
                  fontSize: '18px',
                  fontWeight: 700,
                  color: '#1F2937',
                  marginBottom: '16px',
                }}
              >
                Color
              </h2>

              <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
                {/* Large Dual-Tone Swatch with Checkmark Badge */}
                <div
                  style={{
                    width: '76px',
                    height: '76px',
                    borderRadius: '18px',
                    backgroundColor: primaryColor,
                    overflow: 'hidden',
                    position: 'relative',
                    boxShadow: '0 4px 10px rgba(0,0,0,0.15)',
                    display: 'flex',
                    flexDirection: 'column',
                    flexShrink: 0,
                  }}
                >
                  <div style={{ flex: 1, backgroundColor: primaryColor }} />
                  <div style={{ height: '24px', backgroundColor: accentColor }} />

                  {/* Centered White Circle with Checkmark */}
                  <div
                    style={{
                      position: 'absolute',
                      top: '50%',
                      left: '50%',
                      transform: 'translate(-50%, -50%)',
                      width: '26px',
                      height: '26px',
                      borderRadius: '50%',
                      backgroundColor: '#FFFFFF',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
                    }}
                  >
                    <Check size={16} color={primaryColor} strokeWidth={3} />
                  </div>
                </div>

                {/* Right controls: Slider + Info + 3 Swatches */}
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  {/* Rainbow Spectrum Slider */}
                  <HueSpectrumSlider hue={hue} onChange={handleHueChange} disabled={!canManage} />

                  {/* 3 Coordinated Palettes Swatches + Info icon */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div
                      title="Palettes are automatically generated to maintain WCAG contrast"
                      style={{
                        width: '32px',
                        height: '32px',
                        borderRadius: '8px',
                        backgroundColor: '#F3F4F6',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#6B7280',
                        cursor: 'help',
                      }}
                    >
                      <Info size={16} />
                    </div>

                    {palettes.map((palette) => {
                      const isSelected = selectedPaletteId === palette.id;
                      return (
                        <button
                          key={palette.id}
                          type="button"
                          onClick={() => handleSelectPalette(palette)}
                          title={`${palette.name}: ${palette.description}`}
                          style={{
                            width: '42px',
                            height: '42px',
                            borderRadius: '10px',
                            overflow: 'hidden',
                            position: 'relative',
                            padding: 0,
                            border: isSelected ? '2px solid #111827' : '1px solid #E5E7EB',
                            cursor: 'pointer',
                            display: 'flex',
                            flexDirection: 'column',
                            boxShadow: isSelected ? '0 2px 6px rgba(0,0,0,0.2)' : 'none',
                            transform: isSelected ? 'scale(1.05)' : 'scale(1)',
                            transition: 'all 0.15s ease',
                          }}
                        >
                          <div style={{ flex: 1, backgroundColor: palette.primary_color }} />
                          <div style={{ height: '14px', backgroundColor: palette.accent_color }} />

                          {isSelected && (
                            <div
                              style={{
                                position: 'absolute',
                                top: '50%',
                                left: '50%',
                                transform: 'translate(-50%, -50%)',
                                width: '18px',
                                height: '18px',
                                borderRadius: '50%',
                                backgroundColor: '#FFFFFF',
                                display: 'flex',
                                alignItems: 'center',
                                justifySelf: 'center',
                                justifyContent: 'center',
                              }}
                            >
                              <Check size={12} color={palette.primary_color} strokeWidth={3} />
                            </div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Manual Color Overrides Collapsible */}
              <div style={{ marginTop: '20px' }}>
                <button
                  type="button"
                  onClick={() => setShowManualOverrides(!showManualOverrides)}
                  style={{
                    background: 'none',
                    border: 'none',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    fontSize: '13px',
                    fontWeight: 600,
                    color: '#2563EB',
                    cursor: 'pointer',
                    padding: 0,
                  }}
                >
                  <Sliders size={14} />
                  {showManualOverrides ? 'Hide Manual Color Overrides' : 'Adjust Individual Colors Manually'}
                </button>

                {showManualOverrides && (
                  <div
                    style={{
                      marginTop: '12px',
                      padding: '16px',
                      backgroundColor: '#F9FAFB',
                      borderRadius: '12px',
                      border: '1px solid #E5E7EB',
                      display: 'grid',
                      gridTemplateColumns: '1fr 1fr',
                      gap: '12px',
                    }}
                  >
                    <div>
                      <label style={{ fontSize: '11px', fontWeight: 600, color: '#374151' }}>
                        Primary Color
                      </label>
                      <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
                        <input
                          type="color"
                          value={primaryColor}
                          onChange={(e) => {
                            setPrimaryColor(e.target.value);
                            setManualOverrides((prev) => ({ ...prev, primary_color: e.target.value }));
                            setIsDirty(true);
                          }}
                          style={{ width: '36px', height: '36px', border: 'none', cursor: 'pointer' }}
                        />
                        <input
                          type="text"
                          value={primaryColor}
                          onChange={(e) => {
                            setPrimaryColor(e.target.value);
                            if (isValidHex(e.target.value)) {
                              setManualOverrides((prev) => ({ ...prev, primary_color: e.target.value }));
                            }
                            setIsDirty(true);
                          }}
                          style={{
                            flex: 1,
                            padding: '6px 10px',
                            borderRadius: '8px',
                            border: '1px solid #D1D5DB',
                            fontSize: '13px',
                          }}
                        />
                      </div>
                    </div>

                    <div>
                      <label style={{ fontSize: '11px', fontWeight: 600, color: '#374151' }}>
                        Secondary Color
                      </label>
                      <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
                        <input
                          type="color"
                          value={secondaryColor}
                          onChange={(e) => {
                            setSecondaryColor(e.target.value);
                            setManualOverrides((prev) => ({ ...prev, secondary_color: e.target.value }));
                            setIsDirty(true);
                          }}
                          style={{ width: '36px', height: '36px', border: 'none', cursor: 'pointer' }}
                        />
                        <input
                          type="text"
                          value={secondaryColor}
                          onChange={(e) => {
                            setSecondaryColor(e.target.value);
                            if (isValidHex(e.target.value)) {
                              setManualOverrides((prev) => ({ ...prev, secondary_color: e.target.value }));
                            }
                            setIsDirty(true);
                          }}
                          style={{
                            flex: 1,
                            padding: '6px 10px',
                            borderRadius: '8px',
                            border: '1px solid #D1D5DB',
                            fontSize: '13px',
                          }}
                        />
                      </div>
                    </div>

                    <div>
                      <label style={{ fontSize: '11px', fontWeight: 600, color: '#374151' }}>
                        Accent Color
                      </label>
                      <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
                        <input
                          type="color"
                          value={accentColor}
                          onChange={(e) => {
                            setAccentColor(e.target.value);
                            setManualOverrides((prev) => ({ ...prev, accent_color: e.target.value }));
                            setIsDirty(true);
                          }}
                          style={{ width: '36px', height: '36px', border: 'none', cursor: 'pointer' }}
                        />
                        <input
                          type="text"
                          value={accentColor}
                          onChange={(e) => {
                            setAccentColor(e.target.value);
                            if (isValidHex(e.target.value)) {
                              setManualOverrides((prev) => ({ ...prev, accent_color: e.target.value }));
                            }
                            setIsDirty(true);
                          }}
                          style={{
                            flex: 1,
                            padding: '6px 10px',
                            borderRadius: '8px',
                            border: '1px solid #D1D5DB',
                            fontSize: '13px',
                          }}
                        />
                      </div>
                    </div>

                    <div>
                      <label style={{ fontSize: '11px', fontWeight: 600, color: '#374151' }}>
                        Sidebar Background
                      </label>
                      <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
                        <input
                          type="color"
                          value={sidebarBgColor}
                          onChange={(e) => {
                            setSidebarBgColor(e.target.value);
                            setManualOverrides((prev) => ({ ...prev, sidebar_bg_color: e.target.value }));
                            setIsDirty(true);
                          }}
                          style={{ width: '36px', height: '36px', border: 'none', cursor: 'pointer' }}
                        />
                        <input
                          type="text"
                          value={sidebarBgColor}
                          onChange={(e) => {
                            setSidebarBgColor(e.target.value);
                            if (isValidHex(e.target.value)) {
                              setManualOverrides((prev) => ({ ...prev, sidebar_bg_color: e.target.value }));
                            }
                            setIsDirty(true);
                          }}
                          style={{
                            flex: 1,
                            padding: '6px 10px',
                            borderRadius: '8px',
                            border: '1px solid #D1D5DB',
                            fontSize: '13px',
                          }}
                        />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div
              style={{
                padding: '16px',
                borderRadius: '12px',
                backgroundColor: '#F9FAFB',
                border: '1px solid #E5E7EB',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                fontSize: '13px',
                color: '#4B5563',
              }}
            >
              <Info size={18} color="#2563EB" />
              <span>
                Default theme is active. Platform colors, typography, buttons, and navigation are
                preserved. Switch to <strong>Custom Theme</strong> to generate coordinated palettes.
              </span>
            </div>
          )}

          {/* Feedback & Alert Banners */}
          {errorMessage && (
            <div
              style={{
                backgroundColor: '#FEF2F2',
                border: '1px solid #F87171',
                borderRadius: '10px',
                padding: '12px 16px',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                color: '#991B1B',
                fontSize: '13px',
              }}
            >
              <AlertCircle size={16} />
              <span>{errorMessage}</span>
            </div>
          )}

          {saveSuccess && (
            <div
              style={{
                backgroundColor: '#ECFDF5',
                border: '1px solid #6EE7B7',
                borderRadius: '10px',
                padding: '12px 16px',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                color: '#065F46',
                fontSize: '13px',
              }}
            >
              <CheckCircle2 size={16} />
              <span>{saveSuccess}</span>
            </div>
          )}

          {/* Bottom Actions Row matching Reference Image */}
          <div
            style={{
              marginTop: 'auto',
              paddingTop: '24px',
              borderTop: '1px solid #F3F4F6',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            {/* Horizontal Green Progress Bar Indicator on the left */}
            <div
              style={{
                width: '120px',
                height: '8px',
                borderRadius: '9999px',
                backgroundColor: '#E5E7EB',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  width: brandingMode === 'custom' ? '100%' : '50%',
                  height: '100%',
                  backgroundColor: '#166534',
                  borderRadius: '9999px',
                  transition: 'width 0.3s ease',
                }}
              />
            </div>

            {/* Right Buttons: Revert & Start Exploring! (Save) */}
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
              {isDirty && (
                <button
                  type="button"
                  onClick={handleRevert}
                  disabled={isSaving}
                  style={{
                    padding: '10px 16px',
                    borderRadius: '9999px',
                    border: '1px solid #D1D5DB',
                    backgroundColor: '#FFFFFF',
                    color: '#4B5563',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
              )}

              <button
                type="button"
                onClick={handleSave}
                disabled={isSaving || !canManage}
                style={{
                  padding: '12px 28px',
                  borderRadius: '9999px',
                  border: 'none',
                  backgroundColor: '#1E6B35',
                  color: '#FFFFFF',
                  fontSize: '14px',
                  fontWeight: 700,
                  cursor: isSaving || !canManage ? 'not-allowed' : 'pointer',
                  boxShadow: '0 4px 12px rgba(22, 101, 52, 0.3)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  opacity: isSaving || !canManage ? 0.7 : 1,
                  transition: 'background-color 0.15s ease',
                }}
              >
                {isSaving ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Saving...
                  </>
                ) : (
                  'Start Exploring!'
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Right Column: Live HRMS Desktop Application Preview */}
        <div
          style={{
            flex: '1 1 540px',
            backgroundColor: '#E5E7EB',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '40px 32px',
            boxSizing: 'border-box',
          }}
        >
          <BrandingLivePreview
            logoUrl={previewLogoUrl}
            primaryColor={primaryColor}
            secondaryColor={secondaryColor}
            accentColor={accentColor}
            sidebarBgColor={sidebarBgColor}
            brandingMode={brandingMode}
            userName={user ? `${user.firstName || 'Rudraksha'}` : 'Rudraksha'}
            isDirty={isDirty}
          />
        </div>
      </div>
    </div>
  );
};
