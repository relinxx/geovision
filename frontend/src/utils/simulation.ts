// Simulation utilities and helpers
import { Metrics, LandUseZone } from '../types';

/**
 * Update metrics with realistic fluctuations during simulation
 */
export function updateMetrics(currentMetrics: Metrics): Metrics {
  return {
    population: Math.max(
      5000,
      currentMetrics.population + Math.floor(Math.random() * 100 - 30)
    ),
    traffic: Math.min(
      100,
      Math.max(50, currentMetrics.traffic + Math.floor(Math.random() * 10 - 5))
    ),
    zoning: Math.min(
      100,
      Math.max(80, currentMetrics.zoning + Math.floor(Math.random() * 4 - 2))
    ),
    environmental: Math.max(
      1,
      currentMetrics.environmental + (Math.random() * 0.2 - 0.1)
    ),
    greenArea: Math.min(
      100,
      Math.max(50, currentMetrics.greenArea + Math.floor(Math.random() * 3 - 1))
    ),
  };
}

/**
 * Update zone compliance during simulation
 */
export function updateZoneCompliance(zones: LandUseZone[]): LandUseZone[] {
  return zones.map((zone) => ({
    ...zone,
    compliance: Math.min(
      100,
      Math.max(70, zone.compliance + Math.floor(Math.random() * 6 - 3))
    ),
  }));
}

/**
 * Calculate overall compliance score
 */
export function calculateComplianceScore(zones: LandUseZone[]): number {
  if (zones.length === 0) return 0;
  const total = zones.reduce((sum, zone) => sum + zone.compliance, 0);
  return Math.round(total / zones.length);
}

/**
 * Generate initial zone data
 * TODO: Replace with data from backend/database
 */
export function generateInitialZones(): LandUseZone[] {
  return [
    {
      id: '1',
      type: 'residential',
      x: 25,
      y: 15,
      width: 120,
      height: 120,
      population: 1200,
      compliance: 95,
    },
    {
      id: '2',
      type: 'commercial',
      x: 180,
      y: 80,
      width: 150,
      height: 150,
      population: 800,
      compliance: 88,
    },
    {
      id: '3',
      type: 'industrial',
      x: 80,
      y: 240,
      width: 130,
      height: 130,
      population: 300,
      compliance: 92,
    },
    {
      id: '4',
      type: 'green',
      x: 260,
      y: 160,
      width: 100,
      height: 100,
      compliance: 100,
    },
    {
      id: '5',
      type: 'mixed',
      x: 200,
      y: 280,
      width: 160,
      height: 120,
      population: 950,
      compliance: 85,
    },
  ];
}
