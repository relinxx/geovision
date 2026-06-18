import type { SpatialOverlayLayerKey } from '../types';

export const FALLBACK_OVERLAY_PLAN_ID = 'plan_2';

const DEFAULT_VALIDATION_LAYER: SpatialOverlayLayerKey = 'roads';
const MAX_COORDINATE_SAMPLES = 200;

export interface OverlayPlanResolution {
  planId: string;
  usedFallback: boolean;
  validationLayerKey: SpatialOverlayLayerKey;
  fallbackReason?: string;
}

interface ResolveOverlayPlanIdOptions {
  candidatePlanId: string;
  visibleLayers: SpatialOverlayLayerKey[];
  getLayerData: (planId: string, layerKey: SpatialOverlayLayerKey) => Promise<any | null>;
  fallbackPlanId?: string;
}

function collectCoordinateSamples(
  coordinates: unknown,
  samples: Array<[number, number]>,
  limit: number
): void {
  if (!coordinates || samples.length >= limit || !Array.isArray(coordinates)) {
    return;
  }

  if (
    coordinates.length >= 2 &&
    typeof coordinates[0] === 'number' &&
    typeof coordinates[1] === 'number'
  ) {
    samples.push([coordinates[0], coordinates[1]]);
    return;
  }

  for (const entry of coordinates) {
    collectCoordinateSamples(entry, samples, limit);
    if (samples.length >= limit) {
      return;
    }
  }
}

export function isGeoJsonLikelyWgs84(payload: any): boolean {
  if (!payload?.features || !Array.isArray(payload.features) || payload.features.length === 0) {
    return false;
  }

  const samples: Array<[number, number]> = [];
  for (const feature of payload.features) {
    collectCoordinateSamples(feature?.geometry?.coordinates, samples, MAX_COORDINATE_SAMPLES);
    if (samples.length >= MAX_COORDINATE_SAMPLES) {
      break;
    }
  }

  if (samples.length === 0) {
    return false;
  }

  return samples.every(([lon, lat]) => {
    return (
      Number.isFinite(lon) &&
      Number.isFinite(lat) &&
      Math.abs(lon) <= 180 &&
      Math.abs(lat) <= 90
    );
  });
}

export function getOverlayCandidatePlanId(activePlanIndex: number): string {
  const normalizedPlanIndex = Number.isFinite(activePlanIndex)
    ? Math.max(0, Math.floor(activePlanIndex))
    : 0;
  return `plan_${(normalizedPlanIndex % 2) + 1}`;
}

export async function resolveOverlayPlanId({
  candidatePlanId,
  visibleLayers,
  getLayerData,
  fallbackPlanId = FALLBACK_OVERLAY_PLAN_ID,
}: ResolveOverlayPlanIdOptions): Promise<OverlayPlanResolution> {
  const validationLayerKey =
    visibleLayers.find((layerKey) => layerKey === DEFAULT_VALIDATION_LAYER) ??
    visibleLayers[0] ??
    DEFAULT_VALIDATION_LAYER;

  const candidateLayer = await getLayerData(candidatePlanId, validationLayerKey);
  if (isGeoJsonLikelyWgs84(candidateLayer)) {
    return {
      planId: candidatePlanId,
      usedFallback: false,
      validationLayerKey,
    };
  }

  if (candidatePlanId === fallbackPlanId) {
    return {
      planId: candidatePlanId,
      usedFallback: false,
      validationLayerKey,
      fallbackReason:
        `Overlay dataset for ${candidatePlanId}/${validationLayerKey}` +
        ' failed WGS84 plausibility checks and no alternate plan is configured.',
    };
  }

  const fallbackLayer = await getLayerData(fallbackPlanId, validationLayerKey);
  if (isGeoJsonLikelyWgs84(fallbackLayer)) {
    return {
      planId: fallbackPlanId,
      usedFallback: true,
      validationLayerKey,
      fallbackReason:
        `Overlay dataset for ${candidatePlanId}/${validationLayerKey}` +
        ` failed WGS84 plausibility checks; using ${fallbackPlanId} instead.`,
    };
  }

  return {
    planId: candidatePlanId,
    usedFallback: false,
    validationLayerKey,
    fallbackReason:
      `Overlay datasets for both ${candidatePlanId}/${validationLayerKey}` +
      ` and ${fallbackPlanId}/${validationLayerKey} failed WGS84 plausibility checks.`,
  };
}
