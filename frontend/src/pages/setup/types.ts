import React from 'react';
import {
  Building2,
  MapPin,
  Network,
  CalendarDays,
  Clock,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';

export interface StepInfo {
  number: number;
  title: string;
  shortTitle: string;
  description: string;
  icon: React.ComponentType<{ size?: number; className?: string; style?: React.CSSProperties }>;
}

export const WIZARD_STEPS: StepInfo[] = [
  {
    number: 1,
    title: 'Organization Details',
    shortTitle: 'Details',
    description: 'Name, code, currency & timezone',
    icon: Building2,
  },
  {
    number: 2,
    title: 'Head Office Branch',
    shortTitle: 'Location',
    description: 'Primary location & geofence',
    icon: MapPin,
  },
  {
    number: 3,
    title: 'Organizational Structure',
    shortTitle: 'Structure',
    description: 'Departments & designations',
    icon: Network,
  },
  {
    number: 4,
    title: 'Working Calendar & Holidays',
    shortTitle: 'Calendar',
    description: 'Work days, rules & holidays',
    icon: CalendarDays,
  },
  {
    number: 5,
    title: 'Shifts & Attendance Policy',
    shortTitle: 'Shifts',
    description: 'Working shift & clock-in policies',
    icon: Clock,
  },
  {
    number: 6,
    title: 'Administrator & RBAC',
    shortTitle: 'Admin',
    description: 'Initial Super-Admin governance',
    icon: ShieldCheck,
  },
  {
    number: 7,
    title: 'Review & Activation',
    shortTitle: 'Launch',
    description: 'Readiness check & launch',
    icon: Sparkles,
  },
];
