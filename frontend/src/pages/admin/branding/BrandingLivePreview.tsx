import React from 'react';
import {
  Home,
  Users,
  Briefcase,
  Calendar,
  PieChart,
  FileText,
  DollarSign,
  Settings,
  Palmtree,
  Pill,
  ChevronDown,
  Edit3,
  CalendarPlus,
  MessageSquare,
  Sparkles,
} from 'lucide-react';

interface BrandingLivePreviewProps {
  logoUrl?: string;
  primaryColor: string;
  secondaryColor?: string;
  accentColor?: string;
  sidebarBgColor?: string;
  brandingMode: 'default' | 'custom';
  userName?: string;
  isDirty?: boolean;
}

export const BrandingLivePreview: React.FC<BrandingLivePreviewProps> = ({
  logoUrl,
  primaryColor,
  secondaryColor,
  accentColor,
  sidebarBgColor,
  brandingMode,
  userName = 'Rudraksha',
  isDirty = false,
}) => {
  // If in default mode, use platform standard tokens
  const activePrimary = brandingMode === 'custom' ? primaryColor : '#3B82F6';
  const activeSecondary = brandingMode === 'custom' && secondaryColor ? secondaryColor : '#235E3A';
  const activeAccent = brandingMode === 'custom' && accentColor ? accentColor : '#47BFFF';
  const activeSidebarBg = brandingMode === 'custom' && sidebarBgColor ? sidebarBgColor : '#FFFFFF';

  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        maxWidth: '720px',
        backgroundColor: '#F3F4F6',
        borderRadius: '24px',
        padding: '32px 24px',
        boxSizing: 'border-box',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {/* Live Preview Status Badge */}
      <div
        style={{
          alignSelf: 'flex-start',
          marginBottom: '16px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: '12px',
          fontWeight: 600,
          color: isDirty ? '#D97706' : '#4B5563',
          backgroundColor: '#FFFFFF',
          padding: '4px 12px',
          borderRadius: '9999px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
        }}
      >
        <Sparkles size={14} color={isDirty ? '#D97706' : activePrimary} />
        {isDirty ? 'Live Preview (Unsaved Changes)' : 'Live Preview (Active Theme)'}
        <span
          style={{
            display: 'inline-block',
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            backgroundColor: isDirty ? '#F59E0B' : '#10B981',
          }}
        />
      </div>

      {/* Desktop Application Window Frame */}
      <div
        style={{
          width: '100%',
          backgroundColor: '#FFFFFF',
          borderRadius: '18px',
          boxShadow: '0 15px 35px -5px rgba(0, 0, 0, 0.12), 0 5px 15px rgba(0, 0, 0, 0.05)',
          border: '1px solid #E5E7EB',
          overflow: 'hidden',
          display: 'flex',
          minHeight: '380px',
        }}
      >
        {/* Mini Sidebar */}
        <div
          style={{
            width: '56px',
            backgroundColor: activeSidebarBg,
            borderRight: '1px solid #E5E7EB',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            padding: '16px 0',
            gap: '18px',
            flexShrink: 0,
            transition: 'background-color 0.2s ease',
          }}
        >
          {/* Home Icon in Brand Primary */}
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: activePrimary,
            }}
          >
            <Home size={20} strokeWidth={2.5} />
          </div>

          {/* Uploaded Logo or Brand Icon */}
          <div
            style={{
              width: '34px',
              height: '34px',
              borderRadius: '8px',
              backgroundColor: '#FFFFFF',
              border: '1px solid #E5E7EB',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              overflow: 'hidden',
              boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
            }}
          >
            {logoUrl ? (
              <img
                src={logoUrl}
                alt="Brand Logo"
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'contain',
                }}
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = 'none';
                }}
              />
            ) : (
              <div
                style={{
                  width: '18px',
                  height: '18px',
                  borderRadius: '4px',
                  backgroundColor: activePrimary,
                }}
              />
            )}
          </div>

          {/* Navigation Icons Stack */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
              marginTop: '4px',
              color: '#9CA3AF',
            }}
          >
            <Users size={17} />
            <Briefcase size={17} />
            <Calendar size={17} />
            <PieChart size={17} />
            <FileText size={17} />
            <DollarSign size={17} />
            <Settings size={17} />
          </div>
        </div>

        {/* Dashboard Main Workspace */}
        <div
          style={{
            flex: 1,
            backgroundColor: '#F9FAFB',
            padding: '20px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            overflow: 'hidden',
          }}
        >
          {/* Top Greeting Header */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div
                style={{
                  width: '42px',
                  height: '42px',
                  borderRadius: '10px',
                  backgroundColor: '#4B5563',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#FFFFFF',
                }}
              >
                <Users size={22} />
              </div>
              <div>
                <h3
                  style={{
                    margin: 0,
                    fontSize: '18px',
                    fontWeight: 700,
                    color: '#111827',
                  }}
                >
                  Hi, {userName}
                </h3>
                <p
                  style={{
                    margin: 0,
                    fontSize: '11px',
                    color: '#6B7280',
                    fontWeight: 500,
                  }}
                >
                  Director, Human Resources
                </p>
              </div>
            </div>

            {/* Quick Actions */}
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                type="button"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: '11px',
                  fontWeight: 500,
                  padding: '5px 10px',
                  borderRadius: '9999px',
                  border: '1px solid #D1D5DB',
                  backgroundColor: '#FFFFFF',
                  color: '#374151',
                  cursor: 'pointer',
                }}
              >
                New... <ChevronDown size={12} />
              </button>
              <button
                type="button"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: '11px',
                  fontWeight: 500,
                  padding: '5px 10px',
                  borderRadius: '9999px',
                  border: '1px solid #D1D5DB',
                  backgroundColor: '#FFFFFF',
                  color: '#374151',
                  cursor: 'pointer',
                }}
              >
                <Edit3 size={11} /> Edit
              </button>
            </div>
          </div>

          {/* Cards Row */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1.1fr 1.3fr',
              gap: '14px',
            }}
          >
            {/* Card 1: Time Off */}
            <div
              style={{
                backgroundColor: '#FFFFFF',
                borderRadius: '12px',
                border: '1px solid #E5E7EB',
                padding: '14px 16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: '#374151',
                }}
              >
                <Calendar size={14} color={activePrimary} />
                <span>Time off</span>
              </div>

              {/* Metrics */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  padding: '4px 0',
                }}
              >
                <div>
                  <span style={{ fontSize: '10px', color: '#6B7280' }}>Vacation</span>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      fontSize: '18px',
                      fontWeight: 700,
                      color: activePrimary,
                    }}
                  >
                    <Palmtree size={18} />
                    132.2
                  </div>
                </div>

                <div>
                  <span style={{ fontSize: '10px', color: '#6B7280' }}>Sick Leave</span>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      fontSize: '18px',
                      fontWeight: 700,
                      color: activeSecondary,
                    }}
                  >
                    <Pill size={16} />
                    8
                  </div>
                </div>
              </div>

              {/* Action Button styled in brand primary color */}
              <button
                type="button"
                style={{
                  marginTop: '4px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  width: '100%',
                  padding: '7px 12px',
                  borderRadius: '9999px',
                  border: `1.5px solid ${activePrimary}`,
                  backgroundColor: '#FFFFFF',
                  color: activePrimary,
                  fontSize: '11px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <CalendarPlus size={13} />
                Request Time Off
              </button>
            </div>

            {/* Card 2: Employee Community */}
            <div
              style={{
                backgroundColor: '#FFFFFF',
                borderRadius: '12px',
                border: '1px solid #E5E7EB',
                padding: '14px 16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  borderBottom: '1px solid #F3F4F6',
                  paddingBottom: '8px',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    fontSize: '11px',
                    fontWeight: 600,
                    color: activePrimary,
                  }}
                >
                  <MessageSquare size={13} color={activeAccent} />
                  Employee Community
                </div>
                <span style={{ fontSize: '10px', color: '#9CA3AF' }}>What's Happening</span>
              </div>

              <div style={{ display: 'flex', gap: '6px' }}>
                <span
                  style={{
                    fontSize: '10px',
                    fontWeight: 600,
                    padding: '3px 8px',
                    borderRadius: '9999px',
                    border: '1px solid #E5E7EB',
                    color: '#4B5563',
                  }}
                >
                  + New Post
                </span>
                <span
                  style={{
                    fontSize: '10px',
                    padding: '3px 8px',
                    borderRadius: '9999px',
                    border: '1px solid #E5E7EB',
                    color: '#9CA3AF',
                  }}
                >
                  Personalized ▾
                </span>
              </div>

              {/* Skeleton Activity Lines */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '4px' }}>
                <div
                  style={{
                    width: '90%',
                    height: '8px',
                    borderRadius: '4px',
                    backgroundColor: '#E5E7EB',
                  }}
                />
                <div
                  style={{
                    width: '75%',
                    height: '8px',
                    borderRadius: '4px',
                    backgroundColor: '#F3F4F6',
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
