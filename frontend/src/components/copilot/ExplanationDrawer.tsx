import React, { useState } from 'react';
import { X } from 'lucide-react';
import { RiskExplanation, RiskContribution } from '../../types';
import { apiClient } from '../../utils/api';
import './CopilotStyles.css';

const HAZARD_FLAGS = [
  { key: 'has_flood',        label: '100-yr Floodplain' },
  { key: 'has_fault',        label: 'Active Fault' },
  { key: 'has_liquefaction', label: 'Liquefaction' },
  { key: 'is_steep',         label: 'Steep Slope' },
  { key: 'is_fire_zone',     label: 'Fire Hazard' },
  { key: 'in_esa',           label: 'ESA' },
  { key: 'in_mscp',          label: 'MSCP Habitat' },
];

interface ExplanationDrawerProps {
  explanations: RiskExplanation[];
  originalProperties?: Record<string, any>;
  onClose: () => void;
}

export function ExplanationDrawer({
  explanations,
  originalProperties = {},
  onClose,
}: ExplanationDrawerProps) {
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [whatIf, setWhatIf] = useState<Record<string, number>>({});
  const [cfResult, setCfResult] = useState<{
    original_score: number;
    counterfactual_score: number;
    delta: number;
  } | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const explanation = explanations[selectedIdx];
  if (!explanation) return null;

  const handleToggle = (flagKey: string, current: boolean) => {
    setWhatIf(prev => ({ ...prev, [flagKey]: current ? 0 : 1 }));
    setCfResult(null);
  };

  const handleRunCounterfactual = async () => {
    if (Object.keys(whatIf).length === 0) return;
    setIsLoading(true);
    try {
      const result = await apiClient.riskCounterfactual({
        parcel_id: explanation.parcel_id,
        parcel_properties: {
          ...originalProperties,
          ...Object.fromEntries(
            explanation.contributions.map(c => [c.factor, c.active ? 1 : 0])
          ),
        },
        changes: whatIf,
      });
      setCfResult(result);
    } catch (err) {
      console.error('Counterfactual error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const effectiveFlags = Object.fromEntries(
    explanation.contributions.map(c => [c.factor, c.active ? 1 : 0])
  );
  const mergedFlags = { ...effectiveFlags, ...whatIf };

  return (
    <div className="copilot-drawer">
      {/* Header */}
      <div className="copilot-drawer-header">
        <div>
          <div className="copilot-drawer-title">Risk Explanation</div>
          <div className="copilot-drawer-subtitle">
            Factor attribution · What-if analysis
          </div>
        </div>
        <button className="copilot-drawer-close" onClick={onClose}>
          <X size={20} />
        </button>
      </div>

      {/* Parcel selector */}
      {explanations.length > 1 && (
        <div className="copilot-drawer-selector">
          <select
            value={selectedIdx}
            onChange={e => { setSelectedIdx(Number(e.target.value)); setWhatIf({}); setCfResult(null); }}
            className="copilot-drawer-select"
          >
            {explanations.map((ex, i) => (
              <option key={ex.parcel_id} value={i}>Parcel {ex.parcel_id}</option>
            ))}
          </select>
        </div>
      )}

      <div className="copilot-drawer-content">
        {/* Score summary */}
        <div className="copilot-score-card">
          <div className="copilot-score-label">Risk Score</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
            <span className="copilot-score-value" style={{ color: riskColor(explanation.total_rule_score) }}>
              {explanation.total_rule_score.toFixed(0)}
            </span>
            <span className="copilot-score-divider">/100</span>
            {explanation.xgb_risk_score !== undefined && explanation.xgb_risk_score !== null && (
              <span className="copilot-score-xgb">
                XGBoost: {Number(explanation.xgb_risk_score).toFixed(1)}
              </span>
            )}
          </div>
          <RiskBar value={explanation.total_rule_score} />
        </div>

        {/* Factor breakdown */}
        <div>
          <div className="copilot-score-label">Factor Attribution</div>
          <div className="copilot-factor-list">
            {explanation.contributions.map(c => (
              <FactorRow key={c.factor} contribution={c} />
            ))}
          </div>
        </div>

        {/* What-if toggles */}
        <div>
          <div className="copilot-score-label">What-If Scenario</div>
          <div className="copilot-whatif-list">
            {HAZARD_FLAGS.map(({ key, label }) => {
              const currentVal = mergedFlags[key] ?? 0;
              const isActive = currentVal === 1;
              const changed = whatIf[key] !== undefined;
              return (
                <div
                  key={key}
                  className={`copilot-whatif-item ${changed ? 'changed' : 'default'}`}
                  onClick={() => handleToggle(key, isActive)}
                >
                  <span className="copilot-whatif-label">{label}</span>
                  <ToggleSwitch active={isActive} changed={changed} />
                </div>
              );
            })}
          </div>

          {Object.keys(whatIf).length > 0 && (
            <button
              className={`copilot-whatif-btn ${isLoading ? 'disabled' : 'enabled'}`}
              onClick={handleRunCounterfactual}
              disabled={isLoading}
            >
              {isLoading ? 'Computing…' : 'Run What-If Analysis'}
            </button>
          )}

          {cfResult && (
            <div className="copilot-cf-result">
              <div className="copilot-cf-title">Counterfactual Result</div>
              <div className="copilot-cf-grid">
                <div className="copilot-cf-item">
                  <div className="copilot-cf-label">Original</div>
                  <div className="copilot-cf-value" style={{ color: riskColor(cfResult.original_score) }}>
                    {cfResult.original_score.toFixed(0)}
                  </div>
                </div>
                <div className="copilot-cf-arrow">→</div>
                <div className="copilot-cf-item">
                  <div className="copilot-cf-label">Counterfactual</div>
                  <div className="copilot-cf-value" style={{ color: riskColor(cfResult.counterfactual_score) }}>
                    {cfResult.counterfactual_score.toFixed(0)}
                  </div>
                </div>
                <div className="copilot-cf-item">
                  <div className="copilot-cf-label">Change</div>
                  <div className={`copilot-cf-change ${cfResult.delta < 0 ? 'positive' : 'negative'}`}>
                    {cfResult.delta > 0 ? '+' : ''}{cfResult.delta.toFixed(0)}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function FactorRow({ contribution }: { contribution: RiskContribution }) {
  return (
    <div className={`copilot-factor-item ${contribution.active ? '' : 'inactive'}`}>
      <div
        className="copilot-factor-dot"
        style={{ background: contribution.active ? riskColor(contribution.contribution_pct * 4) : '#3A4A6C' }}
      />
      <div className="copilot-factor-label">
        {contribution.label}
      </div>
      <div className="copilot-factor-weight">
        {contribution.weight * 100}%
      </div>
      <div className="copilot-factor-bar">
        {contribution.active && (
          <div
            className="copilot-factor-bar-fill"
            style={{
              width: `${contribution.contribution_pct / 25 * 100}%`,
              background: riskColor(contribution.contribution_pct * 4),
            }}
          />
        )}
      </div>
    </div>
  );
}

function RiskBar({ value }: { value: number }) {
  return (
    <div className="copilot-score-bar">
      <div
        className="copilot-score-bar-fill"
        style={{
          width: `${Math.min(value, 100)}%`,
          background: riskColor(value),
        }}
      />
    </div>
  );
}

function ToggleSwitch({ active, changed }: { active: boolean; changed: boolean }) {
  return (
    <div
      className={`copilot-toggle ${
        active ? (changed ? 'active-changed' : 'active-default') : 'inactive'
      }`}
    >
      <div
        className={`copilot-toggle-knob ${active ? 'active' : 'inactive'}`}
      />
    </div>
  );
}

function riskColor(score: number): string {
  if (score < 20) return '#4FFFA7';
  if (score < 40) return '#a8e063';
  if (score < 60) return '#FFB86C';
  if (score < 80) return '#ff8c42';
  return '#ff6b6b';
}
