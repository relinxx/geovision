import React, { useState, useCallback } from 'react';
import { useCopilotStream } from '../../hooks/useCopilotStream';
import { CopilotChatPanel } from '../../components/copilot/CopilotChatPanel';
import { AgentTimeline } from '../../components/copilot/AgentTimeline';
import { ExplanationDrawer } from '../../components/copilot/ExplanationDrawer';
import { DeckGLMap } from '../../components/map/DeckGLMap/DeckGLMap';
import { BarChart3, Map as MapIcon } from 'lucide-react';
import type { LandUseAssignment, ParcelSuitabilityScores } from '../../types';
import '../../components/copilot/CopilotStyles.css';

const PARCEL_GEOJSON_URL = '/parcels_env_risk_clipped.geojson';
const FALLBACK_GEOJSON_URL = '/parcels_env_risk.geojson';

type RightPanelTab = 'map' | 'results';

export function CopilotPage() {
  const {
    messages,
    agentSteps,
    landUsePlan,
    explanations,
    isStreaming,
    error,
    sendQuery,
    reset,
  } = useCopilotStream();

  const [selectedParcelIds, setSelectedParcelIds] = useState<string[]>([]);
  const [allFeatures, setAllFeatures] = useState<any[]>([]);
  const [rightTab, setRightTab] = useState<RightPanelTab>('map');
  const [showExplanation, setShowExplanation] = useState(false);

  // Build scoresById from environment agent results (if any)
  const scoresById = React.useMemo<Map<string, ParcelSuitabilityScores>>(() => {
    const envStep = agentSteps.find(s => s.agent === 'analyze_environment');
    if (!envStep?.result?.results) return new Map();
    const map = new Map<string, ParcelSuitabilityScores>();
    for (const r of envStep.result.results) {
      if (r.parcel_id) {
        map.set(String(r.parcel_id), {
          residential:       r.residential       ?? 0,
          commercial:        r.commercial        ?? 0,
          industrial:        r.industrial        ?? 0,
          green:             r.green             ?? 0,
          environmental_risk: r.environmental_risk ?? 0,
        });
      }
    }
    return map;
  }, [agentSteps]);

  // Build landUsePlanByParcel from spatial optimization (if any)
  const landUsePlanByParcel = React.useMemo<Map<string, LandUseAssignment> | undefined>(() => {
    if (!landUsePlan || landUsePlan.length === 0) return undefined;
    const valid = new Set<LandUseAssignment>(['residential', 'commercial', 'industrial', 'green']);
    const map = new Map<string, LandUseAssignment>();
    for (const a of landUsePlan) {
      const use = a.use_label as LandUseAssignment;
      if (valid.has(use)) map.set(String(a.parcel_id), use);
    }
    return map.size > 0 ? map : undefined;
  }, [landUsePlan]);

  const colorMode = landUsePlanByParcel ? 'land_use_plan' : 'environmental_risk';

  const handleParcelSelect = useCallback((apn: string) => {
    setSelectedParcelIds(prev =>
      prev.includes(apn) ? prev.filter(id => id !== apn) : [...prev, apn]
    );
  }, []);

  const handleBulkSelect = useCallback(
    (parcelIds: string[]) => setSelectedParcelIds(parcelIds),
    []
  );

  const handleFeaturesLoaded = useCallback((features: any[]) => {
    setAllFeatures(features);
  }, []);

  // Gather properties of selected parcels for explanations
  const selectedParcelProps = React.useMemo(() => {
    if (!allFeatures.length || !selectedParcelIds.length) return {};
    const feat = allFeatures.find(f => {
      const props = f.properties ?? {};
      const id = props.APN || props.apn || props.parcel_id || props.PARCELID || props.id || '';
      return String(id) === selectedParcelIds[0];
    });
    return feat?.properties ?? {};
  }, [allFeatures, selectedParcelIds]);

  const handleSend = (query: string) => {
    // Gather feature properties for selected parcels
    const features = selectedParcelIds.slice(0, 20).map(pid => {
      const feat = allFeatures.find(f => {
        const props = f.properties ?? {};
        const id = props.APN || props.apn || props.parcel_id || props.PARCELID || props.id || '';
        return String(id) === pid;
      });
      return feat?.properties ?? {};
    });
    sendQuery(query, selectedParcelIds, features);
    setRightTab('results');
  };

  const hasExplanations = explanations.length > 0;

  return (
    <div className="copilot-page">
      {/* Left: Chat Panel */}
      <div className="copilot-left-panel">
        <CopilotChatPanel
          messages={messages}
          isStreaming={isStreaming}
          error={error}
          onSend={handleSend}
          onReset={reset}
        />
      </div>

      {/* Right: Map + Results */}
      <div className="copilot-right-panel">
        {/* Tab bar */}
        <div className="copilot-tab-bar">
          {([
            { id: 'map',     icon: MapIcon,  label: 'Live Map' },
            { id: 'results', icon: BarChart3, label: 'Agent Results' },
          ] as const).map(tab => (
            <button
              key={tab.id}
              onClick={() => setRightTab(tab.id)}
              className={`copilot-tab ${rightTab === tab.id ? 'active' : ''}`}
            >
              <tab.icon size={16} />
              {tab.label}
            </button>
          ))}

          {hasExplanations && (
            <button className="copilot-action-btn" onClick={() => setShowExplanation(true)}>
              View Risk Explanation
            </button>
          )}

          {selectedParcelIds.length > 0 && (
            <div className="copilot-selection-badge" style={{ marginLeft: hasExplanations ? 12 : 'auto' }}>
              {selectedParcelIds.length} parcel{selectedParcelIds.length !== 1 ? 's' : ''} selected
            </div>
          )}
        </div>

        {/* Content */}
        <div className="copilot-content">
          {/* Map tab */}
          <div className={`copilot-tab-content ${rightTab === 'map' ? '' : 'hidden'}`}>
            <div style={{ width: '100%', height: '100%', position: 'relative' }}>
              <DeckGLMap
                geoJsonUrl={PARCEL_GEOJSON_URL}
                fallbackGeoJsonUrl={FALLBACK_GEOJSON_URL}
                scoresById={scoresById}
                colorMode={colorMode}
                landUsePlanByParcel={landUsePlanByParcel}
                selectedParcelIds={selectedParcelIds}
                onParcelSelect={handleParcelSelect}
                onBulkParcelSelect={handleBulkSelect}
                onFeaturesLoaded={handleFeaturesLoaded}
                enableRightDragBulkSelect
                autoFitToData
              />
            </div>

            {/* Selection hint overlay */}
            {selectedParcelIds.length === 0 && !isStreaming && messages.length === 0 && (
              <div className="copilot-hint-overlay">
                <span className="copilot-hint-pulse" />
                Right-click drag to select parcels, then ask a question
              </div>
            )}
          </div>

          {/* Results tab */}
          {rightTab === 'results' && (
            <div className="copilot-results-panel">
              {agentSteps.length === 0 ? (
                <EmptyResultsState />
              ) : (
                <>
                  <AgentTimeline steps={agentSteps} />
                  {landUsePlan && <LandUseSummary plan={landUsePlan} />}
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Explanation Drawer */}
      {showExplanation && explanations.length > 0 && (
        <ExplanationDrawer
          explanations={explanations}
          originalProperties={selectedParcelProps}
          onClose={() => setShowExplanation(false)}
        />
      )}
    </div>
  );
}

function EmptyResultsState() {
  return (
    <div className="copilot-empty-results">
      <BarChart3 size={48} color="#1a2f4d" />
      <div className="copilot-empty-results-title">Agent results will appear here</div>
      <div className="copilot-empty-results-subtitle">Ask a question in the chat panel to get started</div>
    </div>
  );
}

function LandUseSummary({ plan }: { plan: Array<{ parcel_id: string; use_label: string }> }) {
  const counts: Record<string, number> = {};
  for (const a of plan) {
    counts[a.use_label] = (counts[a.use_label] ?? 0) + 1;
  }
  const colors: Record<string, string> = {
    residential: '#3BC7F5',
    commercial:  '#FFB86C',
    industrial:  '#ff6b6b',
    green:       '#4FFFA7',
  };

  return (
    <div className="copilot-land-use-card">
      <div className="copilot-land-use-title">Optimized Land-Use Plan</div>
      <div className="copilot-land-use-grid">
        {Object.entries(counts).map(([use, count]) => (
          <div key={use} className="copilot-land-use-item" style={{ background: `${colors[use] ?? '#888'}15`, border: `1px solid ${colors[use] ?? '#888'}30` }}>
            <div className="copilot-land-use-count" style={{ color: colors[use] ?? '#888' }}>{count}</div>
            <div className="copilot-land-use-label">{use}</div>
          </div>
        ))}
      </div>
      <div className="copilot-land-use-footer">Applied to map · switch to Live Map tab to view</div>
    </div>
  );
}
