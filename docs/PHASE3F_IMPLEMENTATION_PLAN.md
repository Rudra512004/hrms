# BEYONDSURE HRMS — PHASE 3F IMPLEMENTATION PLAN
## Organization-Specific Branding & Live Theme Customization

**Document Version:** 1.0.0  
**Phase:** Phase 3F (Organization Branding & Live Theme Customization)  
**Author / Role:** Dev1 Only  
**Branch:** `dev1` | **HEAD:** `8203b224b86b0b3cf7261a6f4c63a4ddb0685193`  

---

## 1. Reference Image Analysis

### 1.1 Visual Hierarchy & Layout
- **Two-Column Split Layout:**
  - **Left Pane (Configuration Controls, ~45% width):**
    - Navigation header: `< Back` navigation action to exit setup/branding.
    - Large Title: **"Personalize the look & feel"** in dark forest green (`#14532d`).
    - Subtitle: *"We take your snazzy brand color and generate a custom theme so that it's on-brand and optimized to make it easy for everyone to read."*
    - **Section 1 — Logo:**
      - **Selected Logo Card:** Rounded rectangle with subtle light green border (`#86efac`), white interior, centered logo image, and top-right circular remove button `(x)`.
      - **Upload Alternative Card:** Dashed border container (`#cbd5e1`), upload icon (`↑`), label *"Upload a different logo"*.
    - **Section 2 — Color:**
      - **Large Active Swatch:** Rounded square (`border-radius: 14px`) displaying dual-tone split (upper 65% primary brand color, lower 35% accent color) with a centered white circular checkmark (`✓`).
      - **Hue Spectrum Slider:** Continuous horizontal rainbow spectrum gradient bar (`red -> yellow -> green -> cyan -> blue -> purple -> red`) with draggable circular thumb.
      - **Coordinated Palette Suggestions:** Tooltip info icon `(i)` followed by 3 dual-tone palette suggestion pills (`#166534 / #86efac`, `#2e7d32 / #a5d6a7`, `#1b5e20 / #81c784`), showing checkmark on the active palette.
    - **Bottom Action Area:**
      - Progress indicator bar (horizontal green bar).
      - Primary call-to-action button: **"Start Exploring!"** (pill-shaped, deep green background `#166534`, white bold text).
  - **Right Pane (Live Preview Panel, ~55% width):**
    - Neutral light gray/slate canvas (`#f1f5f9` / `#e2e8f0`).
    - Elevated application mock window (`border-radius: 18px`, ambient drop shadow).
    - Mini sidebar with organization logo, navigation icons (dashboard, employees, calendar, attendance, reports, documents).
    - Top profile greeting: *"Hi, Rudraksha / Director, Human Resources"* with user avatar silhouette and header action buttons (`+ New...`, `Edit`).
    - Dashboard content cards:
      - **"Time off" Card:** Vacation (`132.2`), Sick leave (`8`), and green primary button *"Request Time Off"*.
      - **"Employee Community" / "What's Happening" Card:** Tabbed card with post creation input and feed items.
    - Live theming: Primary buttons, active sidebar icons, greeting header, and badge accents immediately reflect the brand color in real time.

---

## 2. Functional Modes Specification

### Mode A: Default Theme + Organization Logo
1. Upload, replace, and remove organization logo.
2. Maintain standard BeyondSure HRMS blue/green platform tokens (`--color-primary: #3B82F6`).
3. Logo changes render in preview and sidebar immediately.
4. Colors are not extracted or overridden.
5. Removing the logo restores default BeyondSure logo.
6. Switching to Mode A preserves uploaded logo and any custom palette settings in storage.

### Mode B: Custom Theme
1. Upload or select organization logo.
2. Deterministic color extraction via Pillow (backend) and HTML5 Canvas (frontend).
3. Generate 3 coordinated color palettes ensuring WCAG AA contrast (>= 4.5:1 against text/backgrounds):
   - **Vibrant Brand:** Extracted dominant hue with complementary accents.
   - **Modern Professional:** Balanced saturation and refined slate harmony.
   - **Deep Focus:** Rich deep tones with crisp high-contrast interactive elements.
4. Interactive hue spectrum slider allowing fine-tuning (0° to 360°).
5. Manual color overrides for Primary, Secondary, Accent, and Sidebar BG.
6. Real-time live preview of all dashboard elements.
7. Save action persists `branding_mode: "custom"`, selected palette, and overrides.

---

## 3. Database Schema & Migration Changes

Target Model: `TenantBrandingAndConfig` in [`backend/apps/organization/models.py`](file:///d:/hrms/hrms/backend/apps/organization/models.py).

```python
class BrandingMode(models.TextChoices):
    DEFAULT = 'default', 'Default Theme'
    CUSTOM = 'custom', 'Custom Theme'

# Added fields:
branding_mode = models.CharField(
    max_length=20,
    choices=BrandingMode.choices,
    default=BrandingMode.DEFAULT,
    help_text="Active theming mode: 'default' (platform tokens + logo) or 'custom' (brand palette).",
)
selected_palette = models.CharField(
    max_length=50,
    blank=True,
    default='',
    help_text="Identifier of the currently selected generated palette (e.g. 'vibrant', 'professional', 'deep').",
)
palette_suggestions = models.JSONField(
    default=list,
    blank=True,
    help_text="Deterministic color palette suggestions generated from the logo.",
)
manual_overrides = models.JSONField(
    default=dict,
    blank=True,
    help_text="User-specified manual color overrides (e.g. {'primary_color': '#166534'}).",
)
logo_file = models.FileField(
    upload_to=organization_logo_upload_path,
    null=True,
    blank=True,
    help_text="Uploaded logo file stored in secure tenant media directory.",
)
```

Migration: `0016_tenantbrandingandconfig_phase3f.py`.

---

## 4. API Endpoints & Contract

### 4.1 `GET /api/v1/organization/organizations/{id}/branding/`
- **Permission:** `organization.view` (or tenant membership)
- **Response:** Current `TenantBrandingAndConfig` data including `branding_mode`, `logo_url`, `primary_color`, `secondary_color`, `selected_palette`, `palette_suggestions`, and `manual_overrides`.

### 4.2 `PATCH /api/v1/organization/organizations/{id}/branding/`
- **Permission:** `branding.manage` (evaluated via dynamic RBAC)
- **Payload:** Partial updates for `branding_mode`, `primary_color`, `secondary_color`, `accent_color`, `sidebar_bg_color`, `selected_palette`, `manual_overrides`.
- **Validation:** Hex color regex `#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})`.

### 4.3 `POST /api/v1/organization/organizations/{id}/branding/logo/`
- **Permission:** `branding.manage`
- **Request:** `multipart/form-data` with `file`.
- **Validation:** Max size 2 MB, formats: PNG, JPEG, WebP, SVG. Safe image validation via Pillow.
- **Processing:** Saves to `organization_logos/<org_id>_<uuid>.<ext>`, analyzes image, extracts dominant colors, generates 3 accessible palettes, updates `logo_url`, and returns updated branding config.

### 4.4 `DELETE /api/v1/organization/organizations/{id}/branding/logo/`
- **Permission:** `branding.manage`
- **Behavior:** Removes `logo_file`, clears `logo_url`, reverts to default platform logo, and logs audit record.

---

## 5. Dynamic RBAC & Tenant Isolation
- Permissions required: `branding.manage` for mutation, `organization.view` for read.
- `OrganizationViewSet` filters queryset strictly by user primary organization via `_get_request_user_org(self.request)`. Cross-tenant requests (`?org_id=other`) return HTTP 404/403.
- Audit logging: Records `organization_logo_uploaded`, `organization_logo_removed`, and `tenant_branding_updated` via `AuditService.log()`.
