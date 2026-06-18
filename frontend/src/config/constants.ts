// Application constants and configuration

export const APP_CONFIG = {
  name: 'GeoVision AI',
  version: '1.0.0',
  description: 'AI-Powered Land-Use Planning Platform',
} as const;

export const COLORS = {
  primary: '#4FFFA7',
  secondary: '#3BC7F5',
  accent: '#9D4EDD',
  warning: '#FFB86C',
  danger: '#FF6B9D',
  background: {
    primary: '#0A1630',
    secondary: '#0F1F3D',
    tertiary: '#0B1E39',
  },
  border: '#1a2f4d',
  text: {
    primary: '#D8E2F0',
    secondary: '#D8E2F0',
    muted: 'rgba(216, 226, 240, 0.6)',
  },
} as const;

export const SIMULATION_SPEEDS = {
  slow: 2000,
  medium: 1000,
  fast: 500,
} as const;

export const MAP_STYLES = ['satellite', 'street', 'landuse'] as const;

export const ZONE_TYPES = {
  residential: { label: 'Residential', color: COLORS.primary },
  commercial: { label: 'Commercial', color: COLORS.secondary },
  industrial: { label: 'Industrial', color: COLORS.accent },
  mixed: { label: 'Mixed Use', color: COLORS.warning },
  green: { label: 'Green Space', color: COLORS.primary },
} as const;

export const CONSTRAINT_LAYERS = [
  { id: 'flood', label: 'Flood Zones' },
  { id: 'soil', label: 'Soil Data' },
  { id: 'zoning', label: 'Zoning Laws' },
  { id: 'population', label: 'Population Targets' },
] as const;

export const AI_AGENTS = [
  {
    id: 'environmental',
    name: 'Environmental Agent',
    color: COLORS.primary,
    description: 'Constraint heatmaps & risk zones',
  },
  {
    id: 'zoning',
    name: 'Zoning Agent',
    color: COLORS.secondary,
    description: 'Allowed vs restricted land-type grids',
  },
  {
    id: 'population',
    name: 'Population Agent',
    color: COLORS.accent,
    description: 'Population distribution & density optimization',
  },
] as const;
