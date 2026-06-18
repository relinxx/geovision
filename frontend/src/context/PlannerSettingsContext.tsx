import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import type { PlannerRuntimeSettings } from '../types';

const SETTINGS_STORAGE_KEY = 'geovision:planner-runtime-settings:v1';

function createDefaultPlannerSettings(): PlannerRuntimeSettings {
  return {
    userAccount: {
      fullName: 'Alex Planner',
      plannerRole: 'Senior Urban Planner',
      organization: 'City Planning Department',
      email: 'alex.planner@example.com',
    },
    scenarioGeneration: {
      basePopulationSize: 30,
      baseGenerations: 20,
      neighborhoodContinuity: true,
      boundaryRule: 'touches',
      smartScalingForLargeSelections: true,
      progressUpdateEvery: 10,
      interactiveRun: true,
      diagnosticsMode: true,
    },
    regulatoryGuidance: {
      autoFetchParcelGuidance: true,
      includeParcelContext: true,
      keepConversationContext: true,
      responseStyle: 'balanced',
      defaultQuestionTemplate:
        'What are the zoning regulations and requirements for this parcel? Please cover allowed uses, restrictions, height limits, lot size requirements, and any special conditions.',
      showParcelTagNotifications: true,
    },
    environmentalReview: {
      lowRiskMax: 10,
      moderateRiskMax: 20,
      elevatedRiskMax: 30,
      highRiskMax: 40,
      showHazardChecklist: true,
    },
    growthDemand: {
      defaultPlanAlternatives: 5,
      maxPlanAlternatives: 10,
    },
  };
}

export const DEFAULT_PLANNER_SETTINGS = createDefaultPlannerSettings();

interface PlannerSettingsContextValue {
  settings: PlannerRuntimeSettings;
  updateSettings: (updater: (prev: PlannerRuntimeSettings) => PlannerRuntimeSettings) => void;
  resetSettings: () => void;
}

const PlannerSettingsContext = createContext<PlannerSettingsContextValue | null>(null);

function isRecord(value: unknown): value is Record<string, any> {
  return typeof value === 'object' && value !== null;
}

function asString(value: unknown, fallback: string): string {
  return typeof value === 'string' ? value : fallback;
}

function asBoolean(value: unknown, fallback: boolean): boolean {
  return typeof value === 'boolean' ? value : fallback;
}

function asNumber(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.max(min, Math.min(max, value));
}

function normalizePlannerSettings(input: unknown): PlannerRuntimeSettings {
  const defaults = createDefaultPlannerSettings();
  if (!isRecord(input)) {
    return defaults;
  }

  const userAccount = isRecord(input.userAccount) ? input.userAccount : {};
  const scenarioGeneration = isRecord(input.scenarioGeneration) ? input.scenarioGeneration : {};
  const regulatoryGuidance = isRecord(input.regulatoryGuidance) ? input.regulatoryGuidance : {};
  const environmentalReview = isRecord(input.environmentalReview) ? input.environmentalReview : {};
  const growthDemand = isRecord(input.growthDemand) ? input.growthDemand : {};

  const lowRiskMax = clamp(
    Math.round(asNumber(environmentalReview.lowRiskMax, defaults.environmentalReview.lowRiskMax)),
    1,
    97
  );
  const moderateRiskMax = clamp(
    Math.round(
      asNumber(environmentalReview.moderateRiskMax, defaults.environmentalReview.moderateRiskMax)
    ),
    lowRiskMax + 1,
    98
  );
  const elevatedRiskMax = clamp(
    Math.round(
      asNumber(environmentalReview.elevatedRiskMax, defaults.environmentalReview.elevatedRiskMax)
    ),
    moderateRiskMax + 1,
    99
  );
  const highRiskMax = clamp(
    Math.round(asNumber(environmentalReview.highRiskMax, defaults.environmentalReview.highRiskMax)),
    elevatedRiskMax + 1,
    100
  );

  const maxPlanAlternatives = clamp(
    Math.round(asNumber(growthDemand.maxPlanAlternatives, defaults.growthDemand.maxPlanAlternatives)),
    1,
    20
  );
  const defaultPlanAlternatives = clamp(
    Math.round(
      asNumber(growthDemand.defaultPlanAlternatives, defaults.growthDemand.defaultPlanAlternatives)
    ),
    1,
    maxPlanAlternatives
  );

  const responseStyle = asString(
    regulatoryGuidance.responseStyle,
    defaults.regulatoryGuidance.responseStyle
  );
  const normalizedResponseStyle =
    responseStyle === 'concise' || responseStyle === 'balanced' || responseStyle === 'detailed'
      ? responseStyle
      : defaults.regulatoryGuidance.responseStyle;

  return {
    userAccount: {
      fullName: asString(userAccount.fullName, defaults.userAccount.fullName),
      plannerRole: asString(userAccount.plannerRole, defaults.userAccount.plannerRole),
      organization: asString(userAccount.organization, defaults.userAccount.organization),
      email: asString(userAccount.email, defaults.userAccount.email),
    },
    scenarioGeneration: {
      basePopulationSize: clamp(
        Math.round(
          asNumber(scenarioGeneration.basePopulationSize, defaults.scenarioGeneration.basePopulationSize)
        ),
        10,
        120
      ),
      baseGenerations: clamp(
        Math.round(asNumber(scenarioGeneration.baseGenerations, defaults.scenarioGeneration.baseGenerations)),
        5,
        100
      ),
      neighborhoodContinuity: asBoolean(
        scenarioGeneration.neighborhoodContinuity,
        defaults.scenarioGeneration.neighborhoodContinuity
      ),
      boundaryRule:
        asString(scenarioGeneration.boundaryRule, defaults.scenarioGeneration.boundaryRule) === 'intersects'
          ? 'intersects'
          : 'touches',
      smartScalingForLargeSelections: asBoolean(
        scenarioGeneration.smartScalingForLargeSelections,
        defaults.scenarioGeneration.smartScalingForLargeSelections
      ),
      progressUpdateEvery: clamp(
        Math.round(
          asNumber(scenarioGeneration.progressUpdateEvery, defaults.scenarioGeneration.progressUpdateEvery)
        ),
        1,
        50
      ),
      interactiveRun: asBoolean(scenarioGeneration.interactiveRun, defaults.scenarioGeneration.interactiveRun),
      diagnosticsMode: asBoolean(scenarioGeneration.diagnosticsMode, defaults.scenarioGeneration.diagnosticsMode),
    },
    regulatoryGuidance: {
      autoFetchParcelGuidance: asBoolean(
        regulatoryGuidance.autoFetchParcelGuidance,
        defaults.regulatoryGuidance.autoFetchParcelGuidance
      ),
      includeParcelContext: asBoolean(
        regulatoryGuidance.includeParcelContext,
        defaults.regulatoryGuidance.includeParcelContext
      ),
      keepConversationContext: asBoolean(
        regulatoryGuidance.keepConversationContext,
        defaults.regulatoryGuidance.keepConversationContext
      ),
      responseStyle: normalizedResponseStyle,
      defaultQuestionTemplate: asString(
        regulatoryGuidance.defaultQuestionTemplate,
        defaults.regulatoryGuidance.defaultQuestionTemplate
      ),
      showParcelTagNotifications: asBoolean(
        regulatoryGuidance.showParcelTagNotifications,
        defaults.regulatoryGuidance.showParcelTagNotifications
      ),
    },
    environmentalReview: {
      lowRiskMax,
      moderateRiskMax,
      elevatedRiskMax,
      highRiskMax,
      showHazardChecklist: asBoolean(
        environmentalReview.showHazardChecklist,
        defaults.environmentalReview.showHazardChecklist
      ),
    },
    growthDemand: {
      defaultPlanAlternatives,
      maxPlanAlternatives,
    },
  };
}

function readSettingsFromStorage(): PlannerRuntimeSettings {
  if (typeof window === 'undefined') {
    return createDefaultPlannerSettings();
  }

  try {
    const raw = window.localStorage.getItem(SETTINGS_STORAGE_KEY);
    if (!raw) {
      return createDefaultPlannerSettings();
    }
    return normalizePlannerSettings(JSON.parse(raw));
  } catch (error) {
    console.warn('[PlannerSettings] Failed to read settings from storage', error);
    return createDefaultPlannerSettings();
  }
}

export function PlannerSettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<PlannerRuntimeSettings>(() => readSettingsFromStorage());

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(settings));
    } catch (error) {
      console.warn('[PlannerSettings] Failed to persist settings', error);
    }
  }, [settings]);

  const updateSettings = useCallback(
    (updater: (prev: PlannerRuntimeSettings) => PlannerRuntimeSettings) => {
      setSettings((prev) => normalizePlannerSettings(updater(prev)));
    },
    []
  );

  const resetSettings = useCallback(() => {
    setSettings(createDefaultPlannerSettings());
  }, []);

  const value = useMemo<PlannerSettingsContextValue>(
    () => ({
      settings,
      updateSettings,
      resetSettings,
    }),
    [settings, updateSettings, resetSettings]
  );

  return <PlannerSettingsContext.Provider value={value}>{children}</PlannerSettingsContext.Provider>;
}

export function usePlannerSettings(): PlannerSettingsContextValue {
  const context = useContext(PlannerSettingsContext);
  if (!context) {
    throw new Error('usePlannerSettings must be used within PlannerSettingsProvider');
  }
  return context;
}
