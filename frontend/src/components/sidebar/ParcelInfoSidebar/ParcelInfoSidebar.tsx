/**
 * ParcelInfoSidebar Component
 * ============================
 * Right sidebar displaying detailed information about the selected parcel.
 * Shows risk scores, environmental hazards, and parcel properties.
 * 
 * @component
 * @example
 * ```tsx
 * <ParcelInfoSidebar 
 *   apn="123-456-789" 
 *   properties={{ has_flood: true, xgb_risk_score: 85.5 }} 
 * />
 * ```
 */

import { useMemo } from 'react';
import {
  MapPin,
  AlertTriangle,
  Droplets,
  Activity,
  Mountain,
  Flame,
  TreePine,
  Shield,
  TrendingUp,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import type { SpatialAssignmentExplanation } from '../../../types';
import { usePlannerSettings } from '../../../context/PlannerSettingsContext';
import './ParcelInfoSidebar.css';

/** Props for the ParcelInfoSidebar component */
interface ParcelInfoSidebarProps {
  /** Assessor's Parcel Number (APN) identifier */
  apn: string | null;
  /** Parcel property data from GeoJSON */
  properties: any | null;
  /** Whether to show generated-plan assignment explanation UI */
  showAssignmentExplanation?: boolean;
  /** Rule-based explanation of the active generated assignment */
  assignmentExplanation?: SpatialAssignmentExplanation | null;
  /** Loading state for parcel-level assignment explanation */
  isLoadingAssignmentExplanation?: boolean;
  /** Fetch error for parcel-level assignment explanation */
  assignmentExplanationError?: string | null;
}

/** Parcel information derived from properties */
interface ParcelInfo {
  apn: string;
  ruleRisk: number | null;
  xgbRisk: number | null;
  flood: boolean;
  fault: boolean;
  liquefaction: boolean;
  steepSlope: boolean;
  fireZone: boolean;
  esa: boolean;
  mscp: boolean;
}

/**
 * Determines CSS class for risk text color.
 * @param value - Risk score value
 * @param thresholds - Risk threshold settings
 * @returns CSS class name for the risk level
 */
function getRiskColorClass(
  value: number | null,
  thresholds: { lowRiskMax: number; moderateRiskMax: number; elevatedRiskMax: number; highRiskMax: number }
): string {
  if (value === null) return 'unknown-state';
  if (value <= thresholds.lowRiskMax) return 'risk-low';
  if (value <= thresholds.moderateRiskMax) return 'risk-moderate';
  if (value <= thresholds.elevatedRiskMax) return 'risk-elevated';
  if (value <= thresholds.highRiskMax) return 'risk-high';
  return 'risk-critical';
}

function formatAssignmentUseLabel(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatPercentScore(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '—';
  }
  return `${(value * 100).toFixed(0)}%`;
}

/**
 * ParcelInfoSidebar component.
 * Displays detailed parcel information, risk scores, and environmental hazards.
 */
export function ParcelInfoSidebar({
  apn,
  properties,
  showAssignmentExplanation = true,
  assignmentExplanation = null,
  isLoadingAssignmentExplanation = false,
  assignmentExplanationError = null,
}: ParcelInfoSidebarProps) {
  const { settings } = usePlannerSettings();

  /** Derived parcel information */
  const parcelInfo = useMemo<ParcelInfo | null>(() => {
    if (!apn || !properties) return null;

    return {
      apn,
      ruleRisk: properties.rule_risk_score ?? null,
      xgbRisk: properties.xgb_risk_score ?? null,
      flood: properties.has_flood ?? false,
      fault: properties.has_fault ?? false,
      liquefaction: properties.has_liquefaction ?? false,
      steepSlope: properties.is_steep ?? false,
      fireZone: properties.is_fire_zone ?? false,
      esa: properties.in_esa ?? false,
      mscp: properties.in_mscp ?? false,
    };
  }, [apn, properties]);

  // Empty state when no parcel is selected
  if (!parcelInfo) {
    return (
      <aside className="parcel-info-sidebar">
        <div className="empty-state">
          <div className="empty-state__content">
            <div className="empty-state__icon-container">
              <MapPin className="empty-state__icon" />
            </div>
            <p className="empty-state__title">No parcel selected</p>
            <p className="empty-state__description">
              Click on a parcel on the map to view details
            </p>
          </div>
        </div>
      </aside>
    );
  }

  const riskThresholds = settings.environmentalReview;

  return (
    <aside className="parcel-info-sidebar custom-scrollbar">
      <div className="parcel-info-sidebar__content">
        {/* Header Tile */}
        <section className="sidebar-section">
          <div className="header-tile">
            <div className="header-tile__glow" aria-hidden="true" />
            <div className="header-tile__content">
              <div className="header-tile__row">
                <div className="header-tile__icon-container">
                  <MapPin className="header-tile__icon" />
                </div>
                <div className="header-tile__title-group">
                  <h2 className="header-tile__title">Selected Parcel</h2>
                  <p className="header-tile__subtitle">Parcel Information</p>
                </div>
              </div>
              <div className="apn-box">
                <div className="apn-box__label">APN</div>
                <div className="apn-box__value">{parcelInfo.apn}</div>
              </div>
            </div>
          </div>
        </section>

        {/* Risk Scores Section */}
        <section className="sidebar-section">
          <div className="section-header">
            <TrendingUp className="section-header__icon" />
            <h3 className="section-header__title">Risk Scores</h3>
          </div>
          <div className="risk-tiles-grid">
            {parcelInfo.ruleRisk !== null && (
              <div
                className={`risk-tile ${getRiskColorClass(parcelInfo.ruleRisk, riskThresholds)}`}
              >
                <div className="risk-tile__header">
                  <AlertTriangle className="risk-tile__icon" />
                  <div className="risk-tile__value">
                    {parcelInfo.ruleRisk.toFixed(1)}
                  </div>
                </div>
                <div className="risk-tile__label">Rule Risk</div>
                <div className="risk-bar">
                  <div
                    className="risk-bar__fill"
                    style={{ width: `${Math.min(parcelInfo.ruleRisk, 100)}%` }}
                  />
                </div>
              </div>
            )}

            {parcelInfo.xgbRisk !== null && (
              <div
                className={`risk-tile ${getRiskColorClass(parcelInfo.xgbRisk, riskThresholds)}`}
              >
                <div className="risk-tile__header">
                  <AlertTriangle className="risk-tile__icon" />
                  <div className="risk-tile__value">
                    {parcelInfo.xgbRisk.toFixed(1)}
                  </div>
                </div>
                <div className="risk-tile__label">XGB Risk</div>
                <div className="risk-bar">
                  <div
                    className="risk-bar__fill"
                    style={{ width: `${Math.min(parcelInfo.xgbRisk, 100)}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        </section>

        {showAssignmentExplanation && (
          <section className="sidebar-section">
            <div className="section-header">
              <CheckCircle2 className="section-header__icon" />
              <h3 className="section-header__title">Assignment Explanation</h3>
            </div>

            <div className="assignment-explanation-card">
              {isLoadingAssignmentExplanation ? (
                <p className="assignment-explanation-card__state">
                  Loading parcel-level assignment explanation...
                </p>
              ) : assignmentExplanationError ? (
                <div className="assignment-explanation-card__warning">
                  {assignmentExplanationError}
                </div>
              ) : assignmentExplanation ? (
                <>
                  <div className="assignment-explanation-card__header">
                    <span className="assignment-explanation-badge">
                      {formatAssignmentUseLabel(assignmentExplanation.assigned_use)}
                    </span>
                    <span className="assignment-explanation-risk">
                      Risk: {assignmentExplanation.risk_level}
                    </span>
                  </div>

                  <p className="assignment-explanation-card__headline">
                    {assignmentExplanation.headline}
                  </p>

                  <div className="assignment-score-grid">
                    <div className="assignment-score-item">
                      <span className="assignment-score-item__label">Best Suitability Use</span>
                      <span className="assignment-score-item__value">
                        {formatAssignmentUseLabel(assignmentExplanation.best_suitability_use)}
                      </span>
                    </div>
                    <div className="assignment-score-item">
                      <span className="assignment-score-item__label">Environmental Risk</span>
                      <span className="assignment-score-item__value">
                        {formatPercentScore(assignmentExplanation.scores.environmental_risk)}
                      </span>
                    </div>
                  </div>

                  <div className="assignment-score-list">
                    {(
                      ['residential', 'commercial', 'industrial', 'green'] as const
                    ).map((label) => (
                      <div key={label} className="assignment-score-row">
                        <span className="assignment-score-row__label">
                          {formatAssignmentUseLabel(label)}
                        </span>
                        <span className="assignment-score-row__value">
                          {formatPercentScore(assignmentExplanation.scores.suitability[label])}
                        </span>
                      </div>
                    ))}
                  </div>

                  {assignmentExplanation.reasons.length > 0 && (
                    <div className="assignment-detail-group">
                      <div className="assignment-detail-group__title">Reasons</div>
                      <ul className="assignment-detail-list">
                        {assignmentExplanation.reasons.map((reason) => (
                          <li key={reason}>{reason}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {assignmentExplanation.warnings.length > 0 && (
                    <div className="assignment-detail-group">
                      <div className="assignment-detail-group__title assignment-detail-group__title--warning">
                        Warnings
                      </div>
                      <ul className="assignment-detail-list assignment-detail-list--warning">
                        {assignmentExplanation.warnings.map((warning) => (
                          <li key={warning}>{warning}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              ) : (
                <p className="assignment-explanation-card__state">
                  Click a parcel after generating a plan to load its assignment explanation.
                </p>
              )}
            </div>
          </section>
        )}

        {/* Environmental Hazards Section */}
        {settings.environmentalReview.showHazardChecklist && (
          <section className="sidebar-section">
            <div className="section-header">
              <Shield className="section-header__icon" />
              <h3 className="section-header__title">Environmental Hazards</h3>
            </div>
            <div className="hazards-grid">
              {/* Flood Hazard */}
              <div
                className={`hazard-tile ${
                  parcelInfo.flood ? 'hazard-tile--negative' : ''
                }`}
              >
                <div className="hazard-tile__header">
                  <Droplets
                    className={`hazard-tile__icon ${
                      parcelInfo.flood ? 'hazard-tile__icon--negative' : 'hazard-tile__icon--muted'
                    }`}
                  />
                  {parcelInfo.flood ? (
                    <XCircle className="hazard-tile__status-icon hazard-tile__icon--negative" />
                  ) : (
                    <CheckCircle2 className="hazard-tile__status-icon hazard-tile__icon--positive" />
                  )}
                </div>
                <div className="hazard-tile__label">Flood</div>
                <div
                  className={`hazard-tile__value ${
                    parcelInfo.flood
                      ? 'hazard-tile__value--negative'
                      : 'hazard-tile__value--positive'
                  }`}
                >
                  {parcelInfo.flood ? 'Yes' : 'No'}
                </div>
              </div>

              {/* Fault Hazard */}
              <div
                className={`hazard-tile ${
                  parcelInfo.fault ? 'hazard-tile--negative' : ''
                }`}
              >
                <div className="hazard-tile__header">
                  <Activity
                    className={`hazard-tile__icon ${
                      parcelInfo.fault ? 'hazard-tile__icon--negative' : 'hazard-tile__icon--muted'
                    }`}
                  />
                  {parcelInfo.fault ? (
                    <XCircle className="hazard-tile__status-icon hazard-tile__icon--negative" />
                  ) : (
                    <CheckCircle2 className="hazard-tile__status-icon hazard-tile__icon--positive" />
                  )}
                </div>
                <div className="hazard-tile__label">Fault</div>
                <div
                  className={`hazard-tile__value ${
                    parcelInfo.fault
                      ? 'hazard-tile__value--negative'
                      : 'hazard-tile__value--positive'
                  }`}
                >
                  {parcelInfo.fault ? 'Yes' : 'No'}
                </div>
              </div>

              {/* Liquefaction Hazard */}
              <div
                className={`hazard-tile ${
                  parcelInfo.liquefaction ? 'hazard-tile--negative' : ''
                }`}
              >
                <div className="hazard-tile__header">
                  <Mountain
                    className={`hazard-tile__icon ${
                      parcelInfo.liquefaction
                        ? 'hazard-tile__icon--negative'
                        : 'hazard-tile__icon--muted'
                    }`}
                  />
                  {parcelInfo.liquefaction ? (
                    <XCircle className="hazard-tile__status-icon hazard-tile__icon--negative" />
                  ) : (
                    <CheckCircle2 className="hazard-tile__status-icon hazard-tile__icon--positive" />
                  )}
                </div>
                <div className="hazard-tile__label">Liquefaction</div>
                <div
                  className={`hazard-tile__value ${
                    parcelInfo.liquefaction
                      ? 'hazard-tile__value--negative'
                      : 'hazard-tile__value--positive'
                  }`}
                >
                  {parcelInfo.liquefaction ? 'Yes' : 'No'}
                </div>
              </div>

              {/* Steep Slope Hazard */}
              <div
                className={`hazard-tile ${
                  parcelInfo.steepSlope ? 'hazard-tile--negative' : ''
                }`}
              >
                <div className="hazard-tile__header">
                  <Mountain
                    className={`hazard-tile__icon ${
                      parcelInfo.steepSlope
                        ? 'hazard-tile__icon--negative'
                        : 'hazard-tile__icon--muted'
                    }`}
                  />
                  {parcelInfo.steepSlope ? (
                    <XCircle className="hazard-tile__status-icon hazard-tile__icon--negative" />
                  ) : (
                    <CheckCircle2 className="hazard-tile__status-icon hazard-tile__icon--positive" />
                  )}
                </div>
                <div className="hazard-tile__label">Steep Slope</div>
                <div
                  className={`hazard-tile__value ${
                    parcelInfo.steepSlope
                      ? 'hazard-tile__value--negative'
                      : 'hazard-tile__value--positive'
                  }`}
                >
                  {parcelInfo.steepSlope ? 'Yes' : 'No'}
                </div>
              </div>

              {/* Fire Zone Hazard */}
              <div
                className={`hazard-tile ${
                  parcelInfo.fireZone ? 'hazard-tile--negative' : ''
                }`}
              >
                <div className="hazard-tile__header">
                  <Flame
                    className={`hazard-tile__icon ${
                      parcelInfo.fireZone
                        ? 'hazard-tile__icon--negative'
                        : 'hazard-tile__icon--muted'
                    }`}
                  />
                  {parcelInfo.fireZone ? (
                    <XCircle className="hazard-tile__status-icon hazard-tile__icon--negative" />
                  ) : (
                    <CheckCircle2 className="hazard-tile__status-icon hazard-tile__icon--positive" />
                  )}
                </div>
                <div className="hazard-tile__label">Fire Zone</div>
                <div
                  className={`hazard-tile__value ${
                    parcelInfo.fireZone
                      ? 'hazard-tile__value--negative'
                      : 'hazard-tile__value--positive'
                  }`}
                >
                  {parcelInfo.fireZone ? 'Yes' : 'No'}
                </div>
              </div>

              {/* ESA (Endangered Species Act) */}
              <div
                className={`hazard-tile ${
                  parcelInfo.esa ? 'hazard-tile--positive' : ''
                }`}
              >
                <div className="hazard-tile__header">
                  <TreePine
                    className={`hazard-tile__icon ${
                      parcelInfo.esa
                        ? 'hazard-tile__icon--positive'
                        : 'hazard-tile__icon--muted'
                    }`}
                  />
                  {parcelInfo.esa ? (
                    <CheckCircle2 className="hazard-tile__status-icon hazard-tile__icon--positive" />
                  ) : (
                    <XCircle className="hazard-tile__status-icon hazard-tile__icon--muted" />
                  )}
                </div>
                <div className="hazard-tile__label">ESA</div>
                <div
                  className={`hazard-tile__value ${
                    parcelInfo.esa
                      ? 'hazard-tile__value--positive'
                      : 'hazard-tile__value--muted'
                  }`}
                >
                  {parcelInfo.esa ? 'Yes' : 'No'}
                </div>
              </div>
            </div>
          </section>
        )}
      </div>
    </aside>
  );
}
