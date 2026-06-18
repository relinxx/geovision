/**
 * SettingsPage Component
 * =======================
 * User preferences and application settings page.
 * Provides configuration options for scenario generation,
 * regulatory guidance, and environmental review settings.
 * 
 * @component
 */

import { useEffect } from 'react';
import { DashboardLayout } from '../../layouts/DashboardLayout/DashboardLayout';
import { usePlannerSettings } from '../../context/PlannerSettingsContext';
import { useAuth } from '../../context/AuthContext';
import { Metrics, LandUseZone } from '../../types';
import { RotateCcw, Save, UserCircle } from 'lucide-react';
import { toast } from 'sonner';
import './SettingsPage.css';

/** Props for the SettingsPage component */
interface SettingsPageProps {
  metrics: Metrics;
  simulationTime: number;
  zones: LandUseZone[];
  selectedRegion: string;
}

/**
 * Parses an integer from string input with fallback.
 * @param value - String value to parse
 * @param fallback - Default value if parsing fails
 * @returns Parsed integer or fallback
 */
function parseInteger(value: string, fallback: number): number {
  const next = Number(value);
  return Number.isFinite(next) ? Math.round(next) : fallback;
}

/**
 * SettingsPage component.
 * Provides user preferences and application configuration UI.
 */
export function SettingsPage({
  metrics,
  simulationTime,
  zones,
  selectedRegion,
}: SettingsPageProps) {
  const { settings, updateSettings, resetSettings } = usePlannerSettings();
  const { user } = useAuth();

  // Sync username with fullName when user data is available and fullName is still default
  useEffect(() => {
    if (user && settings.userAccount.fullName === 'Alex Planner') {
      updateUserAccount({ fullName: user.username });
    }
  }, [user, settings.userAccount.fullName]);

  /** Updates user account settings */
  const updateUserAccount = (patch: Partial<typeof settings.userAccount>) => {
    updateSettings((prev) => ({
      ...prev,
      userAccount: {
        ...prev.userAccount,
        ...patch,
      },
    }));
  };

  /** Updates scenario generation settings */
  const updateScenarioGeneration = (patch: Partial<typeof settings.scenarioGeneration>) => {
    updateSettings((prev) => ({
      ...prev,
      scenarioGeneration: {
        ...prev.scenarioGeneration,
        ...patch,
      },
    }));
  };

  /** Updates regulatory guidance settings */
  const updateRegulatoryGuidance = (patch: Partial<typeof settings.regulatoryGuidance>) => {
    updateSettings((prev) => ({
      ...prev,
      regulatoryGuidance: {
        ...prev.regulatoryGuidance,
        ...patch,
      },
    }));
  };

  /** Updates environmental review settings */
  const updateEnvironmentalReview = (patch: Partial<typeof settings.environmentalReview>) => {
    updateSettings((prev) => ({
      ...prev,
      environmentalReview: {
        ...prev.environmentalReview,
        ...patch,
      },
    }));
  };

  /** Updates growth demand settings */
  const updateGrowthDemand = (patch: Partial<typeof settings.growthDemand>) => {
    updateSettings((prev) => ({
      ...prev,
      growthDemand: {
        ...prev.growthDemand,
        ...patch,
      },
    }));
  };

  /** Handles reset to defaults */
  const handleReset = () => {
    resetSettings();
    toast.success('Settings reset to defaults.');
  };

  return (
    <DashboardLayout
      metrics={metrics}
      simulationTime={simulationTime}
      zones={zones}
      selectedRegion={selectedRegion}
    >
      <main className="settings-page custom-scrollbar">
        {/* Page Header */}
        <header className="settings-header">
          <div className="settings-header__content">
            <div className="settings-header__title-group">
              <h1 className="settings-header__title">Planner Settings</h1>
              <p className="settings-header__description">
                Update profile and planning workflow preferences. Changes apply immediately at runtime.
              </p>
            </div>
            <button type="button" onClick={handleReset} className="reset-btn">
              <RotateCcw className="reset-btn__icon" />
              Reset Defaults
            </button>
          </div>
        </header>

        {/* Settings Grid */}
        <div className="settings-grid">
          {/* User Profile Section */}
          <section className="settings-section">
            <h2 className="settings-section__title">User Profile</h2>
            <p className="settings-section__description">
              Your account information from the database. Contact an administrator to make changes.
            </p>

            {user ? (
              <div className="user-profile-display" style={{
                background: 'rgba(79, 255, 167, 0.05)',
                border: '1px solid rgba(79, 255, 167, 0.2)',
                borderRadius: '12px',
                padding: '1.25rem',
                marginBottom: '1rem'
              }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '1rem',
                  marginBottom: '1rem'
                }}>
                  <div style={{
                    width: '48px',
                    height: '48px',
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, #4fffa7 0%, #3bc7f5 100%)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '1.5rem',
                    fontWeight: '700',
                    color: '#06213e'
                  }}>
                    {user.username.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <div style={{
                      fontSize: '1.1rem',
                      fontWeight: 600,
                      color: 'var(--color-text-primary, #e8f4ff)'
                    }}>
                      {user.username}
                    </div>
                    <div style={{
                      fontSize: '0.85rem',
                      color: 'var(--color-text-secondary, rgba(216, 226, 240, 0.7))'
                    }}>
                      @{user.username}
                    </div>
                  </div>
                </div>

                <div className="form-field" style={{ marginBottom: '0.75rem' }}>
                  <label className="form-field__label">Username</label>
                  <input
                    type="text"
                    value={user.username}
                    readOnly
                    className="form-field__input"
                    style={{ 
                      backgroundColor: 'rgba(6, 18, 42, 0.5)',
                      cursor: 'not-allowed'
                    }}
                  />
                </div>

                <div className="form-field" style={{ marginBottom: '0.75rem' }}>
                  <label className="form-field__label">Email</label>
                  <input
                    type="email"
                    value={user.email}
                    readOnly
                    className="form-field__input"
                    style={{ 
                      backgroundColor: 'rgba(6, 18, 42, 0.5)',
                      cursor: 'not-allowed'
                    }}
                  />
                </div>

                <div className="form-field">
                  <label className="form-field__label">Account Status</label>
                  <div style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    padding: '0.4rem 0.8rem',
                    background: user.is_active ? 'rgba(79, 255, 167, 0.15)' : 'rgba(255, 107, 107, 0.15)',
                    border: `1px solid ${user.is_active ? 'rgba(79, 255, 167, 0.4)' : 'rgba(255, 107, 107, 0.4)'}`,
                    borderRadius: '20px',
                    color: user.is_active ? '#4fffa7' : '#ff6b6b',
                    fontSize: '0.85rem',
                    fontWeight: 500
                  }}>
                    <span style={{
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      background: user.is_active ? '#4fffa7' : '#ff6b6b'
                    }} />
                    {user.is_active ? 'Active' : 'Inactive'}
                  </div>
                </div>
              </div>
            ) : (
              <div style={{
                padding: '1rem',
                background: 'rgba(255, 107, 107, 0.1)',
                border: '1px solid rgba(255, 107, 107, 0.3)',
                borderRadius: '8px',
                color: '#ff6b6b'
              }}>
                User information not available. Please log in again.
              </div>
            )}

            <div className="form-field">
              <label className="form-field__label" htmlFor="fullName">
                Full Name (Report Header)
              </label>
              <input
                id="fullName"
                type="text"
                value={settings.userAccount.fullName}
                onChange={(e) => updateUserAccount({ fullName: e.target.value })}
                className="form-field__input"
                placeholder={user?.username || 'Enter your full name'}
              />
            </div>

            <div className="form-field">
              <label className="form-field__label" htmlFor="plannerRole">
                Planning Role
              </label>
              <input
                id="plannerRole"
                type="text"
                value={settings.userAccount.plannerRole}
                onChange={(e) => updateUserAccount({ plannerRole: e.target.value })}
                className="form-field__input"
              />
            </div>

            <div className="form-field">
              <label className="form-field__label" htmlFor="organization">
                Organization
              </label>
              <input
                id="organization"
                type="text"
                value={settings.userAccount.organization}
                onChange={(e) => updateUserAccount({ organization: e.target.value })}
                className="form-field__input"
              />
            </div>
          </section>

          {/* Scenario Generation Section */}
          <section className="settings-section">
            <h2 className="settings-section__title">Scenario Generation</h2>
            <p className="settings-section__description">
              Controls for how quickly and deeply alternative land-use plans are explored.
            </p>

            <div className="form-grid-2">
              <div className="form-field">
                <label className="form-field__label" htmlFor="basePopulationSize">
                  Search Width
                </label>
                <input
                  id="basePopulationSize"
                  type="number"
                  min={10}
                  max={120}
                  value={settings.scenarioGeneration.basePopulationSize}
                  onChange={(e) =>
                    updateScenarioGeneration({
                      basePopulationSize: parseInteger(
                        e.target.value,
                        settings.scenarioGeneration.basePopulationSize
                      ),
                    })
                  }
                  className="form-field__input"
                />
              </div>

              <div className="form-field">
                <label className="form-field__label" htmlFor="baseGenerations">
                  Optimization Rounds
                </label>
                <input
                  id="baseGenerations"
                  type="number"
                  min={5}
                  max={100}
                  value={settings.scenarioGeneration.baseGenerations}
                  onChange={(e) =>
                    updateScenarioGeneration({
                      baseGenerations: parseInteger(
                        e.target.value,
                        settings.scenarioGeneration.baseGenerations
                      ),
                    })
                  }
                  className="form-field__input"
                />
              </div>
            </div>

            <div className="form-field">
              <label className="form-field__label" htmlFor="boundaryRule">
                Parcel Connectivity Rule
              </label>
              <select
                id="boundaryRule"
                value={settings.scenarioGeneration.boundaryRule}
                onChange={(e) =>
                  updateScenarioGeneration({
                    boundaryRule: e.target.value === 'intersects' ? 'intersects' : 'touches',
                  })
                }
                className="form-field__input"
              >
                <option value="touches">Shared Boundary (touches)</option>
                <option value="intersects">Any Overlap (intersects)</option>
              </select>
            </div>

            {/* Checkbox fields with left alignment */}
            <label className="form-field form-field--inline form-field--checkbox">
              <input
                type="checkbox"
                checked={settings.scenarioGeneration.smartScalingForLargeSelections}
                onChange={(e) =>
                  updateScenarioGeneration({ smartScalingForLargeSelections: e.target.checked })
                }
                className="form-field__checkbox"
              />
              <span className="form-field__label form-field__label--inline">
                Smart Scaling for Large Selections
              </span>
            </label>

            <label className="form-field form-field--inline form-field--checkbox">
              <input
                type="checkbox"
                checked={settings.scenarioGeneration.neighborhoodContinuity}
                onChange={(e) =>
                  updateScenarioGeneration({ neighborhoodContinuity: e.target.checked })
                }
                className="form-field__checkbox"
              />
              <span className="form-field__label form-field__label--inline">
                Favor Connected Neighborhoods
              </span>
            </label>

            <div className="form-field">
              <label className="form-field__label" htmlFor="progressUpdateEvery">
                Progress Update Interval (rounds)
              </label>
              <input
                id="progressUpdateEvery"
                type="number"
                min={1}
                max={50}
                value={settings.scenarioGeneration.progressUpdateEvery}
                onChange={(e) =>
                  updateScenarioGeneration({
                    progressUpdateEvery: parseInteger(
                      e.target.value,
                      settings.scenarioGeneration.progressUpdateEvery
                    ),
                  })
                }
                className="form-field__input"
              />
            </div>

            <div className="form-grid-2">
              <label className="form-field form-field--inline form-field--checkbox">
                <input
                  type="checkbox"
                  checked={settings.scenarioGeneration.interactiveRun}
                  onChange={(e) => updateScenarioGeneration({ interactiveRun: e.target.checked })}
                  className="form-field__checkbox"
                />
                <span className="form-field__label form-field__label--inline">Interactive Mode</span>
              </label>

              <label className="form-field form-field--inline form-field--checkbox">
                <input
                  type="checkbox"
                  checked={settings.scenarioGeneration.diagnosticsMode}
                  onChange={(e) =>
                    updateScenarioGeneration({ diagnosticsMode: e.target.checked })
                  }
                  className="form-field__checkbox"
                />
                <span className="form-field__label form-field__label--inline">Diagnostics Logs</span>
              </label>
            </div>
          </section>

          {/* Regulatory Guidance Section */}
          <section className="settings-section">
            <h2 className="settings-section__title settings-section__title--cyan">
              Regulatory Guidance
            </h2>
            <p className="settings-section__description">
              Controls for parcel-by-parcel zoning guidance in the Layers workspace.
            </p>

            {/* Regulatory Guidance checkboxes with left alignment */}
            <label className="form-field form-field--inline form-field--checkbox">
              <input
                type="checkbox"
                checked={settings.regulatoryGuidance.autoFetchParcelGuidance}
                onChange={(e) =>
                  updateRegulatoryGuidance({ autoFetchParcelGuidance: e.target.checked })
                }
                className="form-field__checkbox form-field__checkbox--cyan"
              />
              <span className="form-field__label form-field__label--inline">
                Auto-fetch guidance after parcel click
              </span>
            </label>

            <label className="form-field form-field--inline form-field--checkbox">
              <input
                type="checkbox"
                checked={settings.regulatoryGuidance.includeParcelContext}
                onChange={(e) =>
                  updateRegulatoryGuidance({ includeParcelContext: e.target.checked })
                }
                className="form-field__checkbox form-field__checkbox--cyan"
              />
              <span className="form-field__label form-field__label--inline">
                Attach selected parcel details
              </span>
            </label>

            <label className="form-field form-field--inline form-field--checkbox">
              <input
                type="checkbox"
                checked={settings.regulatoryGuidance.keepConversationContext}
                onChange={(e) =>
                  updateRegulatoryGuidance({ keepConversationContext: e.target.checked })
                }
                className="form-field__checkbox form-field__checkbox--cyan"
              />
              <span className="form-field__label form-field__label--inline">
                Keep conversation history per parcel
              </span>
            </label>

            <div className="form-field">
              <label className="form-field__label" htmlFor="responseStyle">
                Response Detail Level
              </label>
              <select
                id="responseStyle"
                value={settings.regulatoryGuidance.responseStyle}
                onChange={(e) =>
                  updateRegulatoryGuidance({
                    responseStyle:
                      e.target.value === 'concise' || e.target.value === 'detailed'
                        ? e.target.value
                        : 'balanced',
                  })
                }
                className="form-field__input"
              >
                <option value="concise">Concise</option>
                <option value="balanced">Balanced</option>
                <option value="detailed">Detailed</option>
              </select>
            </div>

            <div className="form-field">
              <label className="form-field__label" htmlFor="defaultQuestionTemplate">
                Default Parcel Guidance Prompt
              </label>
              <textarea
                id="defaultQuestionTemplate"
                rows={4}
                value={settings.regulatoryGuidance.defaultQuestionTemplate}
                onChange={(e) =>
                  updateRegulatoryGuidance({ defaultQuestionTemplate: e.target.value })
                }
                className="form-field__input form-field__input--textarea"
              />
            </div>

            <label className="form-field form-field--inline form-field--checkbox">
              <input
                type="checkbox"
                checked={settings.regulatoryGuidance.showParcelTagNotifications}
                onChange={(e) =>
                  updateRegulatoryGuidance({ showParcelTagNotifications: e.target.checked })
                }
                className="form-field__checkbox form-field__checkbox--cyan"
              />
              <span className="form-field__label form-field__label--inline">
                Show parcel tag notifications
              </span>
            </label>
          </section>

          {/* Environmental Review Section */}
          <section className="settings-section">
            <h2 className="settings-section__title settings-section__title--orange">
              Environmental Review
            </h2>
            <p className="settings-section__description">
              Defines risk score breakpoints used in parcel-level environmental screening.
            </p>

            <div className="form-grid-2">
              <div className="form-field">
                <label className="form-field__label" htmlFor="lowRiskMax">
                  Low Risk up to
                </label>
                <input
                  id="lowRiskMax"
                  type="number"
                  min={1}
                  max={99}
                  value={settings.environmentalReview.lowRiskMax}
                  onChange={(e) =>
                    updateEnvironmentalReview({
                      lowRiskMax: parseInteger(
                        e.target.value,
                        settings.environmentalReview.lowRiskMax
                      ),
                    })
                  }
                  className="form-field__input"
                />
              </div>

              <div className="form-field">
                <label className="form-field__label" htmlFor="moderateRiskMax">
                  Moderate Risk up to
                </label>
                <input
                  id="moderateRiskMax"
                  type="number"
                  min={1}
                  max={100}
                  value={settings.environmentalReview.moderateRiskMax}
                  onChange={(e) =>
                    updateEnvironmentalReview({
                      moderateRiskMax: parseInteger(
                        e.target.value,
                        settings.environmentalReview.moderateRiskMax
                      ),
                    })
                  }
                  className="form-field__input"
                />
              </div>

              <div className="form-field">
                <label className="form-field__label" htmlFor="elevatedRiskMax">
                  Elevated Risk up to
                </label>
                <input
                  id="elevatedRiskMax"
                  type="number"
                  min={1}
                  max={100}
                  value={settings.environmentalReview.elevatedRiskMax}
                  onChange={(e) =>
                    updateEnvironmentalReview({
                      elevatedRiskMax: parseInteger(
                        e.target.value,
                        settings.environmentalReview.elevatedRiskMax
                      ),
                    })
                  }
                  className="form-field__input"
                />
              </div>

              <div className="form-field">
                <label className="form-field__label" htmlFor="highRiskMax">
                  High Risk up to
                </label>
                <input
                  id="highRiskMax"
                  type="number"
                  min={1}
                  max={100}
                  value={settings.environmentalReview.highRiskMax}
                  onChange={(e) =>
                    updateEnvironmentalReview({
                      highRiskMax: parseInteger(
                        e.target.value,
                        settings.environmentalReview.highRiskMax
                      ),
                    })
                  }
                  className="form-field__input"
                />
              </div>
            </div>

            {/* Environmental Review checkbox with left alignment */}
            <label className="form-field form-field--inline form-field--checkbox">
              <input
                type="checkbox"
                checked={settings.environmentalReview.showHazardChecklist}
                onChange={(e) =>
                  updateEnvironmentalReview({ showHazardChecklist: e.target.checked })
                }
                className="form-field__checkbox form-field__checkbox--orange"
              />
              <span className="form-field__label form-field__label--inline">
                Show hazard checklist in parcel details
              </span>
            </label>
          </section>

          {/* Growth & Demand Section */}
          <section className="settings-section settings-section--full-width">
            <h2 className="settings-section__title">Growth & Demand</h2>
            <p className="settings-section__description">
              Controls how many alternatives are generated and browsed by default in the planning workflow.
            </p>

            <div className="form-grid-2">
              <div className="form-field">
                <label className="form-field__label" htmlFor="defaultPlanAlternatives">
                  Default Alternatives to Generate
                </label>
                <input
                  id="defaultPlanAlternatives"
                  type="number"
                  min={1}
                  max={20}
                  value={settings.growthDemand.defaultPlanAlternatives}
                  onChange={(e) =>
                    updateGrowthDemand({
                      defaultPlanAlternatives: parseInteger(
                        e.target.value,
                        settings.growthDemand.defaultPlanAlternatives
                      ),
                    })
                  }
                  className="form-field__input"
                />
              </div>

              <div className="form-field">
                <label className="form-field__label" htmlFor="maxPlanAlternatives">
                  Maximum Alternatives Slider Limit
                </label>
                <input
                  id="maxPlanAlternatives"
                  type="number"
                  min={1}
                  max={20}
                  value={settings.growthDemand.maxPlanAlternatives}
                  onChange={(e) =>
                    updateGrowthDemand({
                      maxPlanAlternatives: parseInteger(
                        e.target.value,
                        settings.growthDemand.maxPlanAlternatives
                      ),
                    })
                  }
                  className="form-field__input"
                />
              </div>
            </div>

            <div className="info-notice">
              <Save className="info-notice__icon" />
              Settings are saved automatically and applied immediately.
            </div>
          </section>
        </div>
      </main>
    </DashboardLayout>
  );
}
