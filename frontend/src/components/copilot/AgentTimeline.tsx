import React from 'react';
import { AgentStepStatus } from '../../types';
import { CheckCircle, Circle, Loader, AlertCircle, Leaf, Building2, Map, Brain } from 'lucide-react';
import './CopilotStyles.css';

interface AgentTimelineProps {
  steps: AgentStepStatus[];
}

const AGENT_ICONS: Record<string, React.ElementType> = {
  orchestrator:        Brain,
  analyze_environment: Leaf,
  query_zoning:        Building2,
  optimize_land_use:   Map,
  explain_risk:        Brain,
};

const AGENT_COLORS: Record<string, string> = {
  orchestrator:        '#4FFFA7',
  analyze_environment: '#4FFFA7',
  query_zoning:        '#3BC7F5',
  optimize_land_use:   '#FFB86C',
  explain_risk:        '#B48EFF',
};

function StatusIcon({ status }: { status: AgentStepStatus['status'] }) {
  const size = 16;
  if (status === 'done')    return <CheckCircle size={size} color="#4FFFA7" />;
  if (status === 'running') return <Loader size={size} color="#FFB86C" style={{ animation: 'spin 1s linear infinite' }} />;
  if (status === 'skipped') return <AlertCircle size={size} color="#6B7A9C" />;
  return <Circle size={size} color="#3A4A6C" />;
}

export function AgentTimeline({ steps }: AgentTimelineProps) {
  if (steps.length === 0) return null;

  return (
    <div className="copilot-timeline">
      <div className="copilot-timeline-title">Agent Pipeline</div>
      {steps.map((step, idx) => {
        const Icon = AGENT_ICONS[step.agent] ?? Brain;
        const color = AGENT_COLORS[step.agent] ?? '#4FFFA7';
        const isLast = idx === steps.length - 1;

        return (
          <div key={step.agent} className="copilot-timeline-item">
            {/* Timeline line */}
            <div className="copilot-timeline-connector">
              <div
                className="copilot-timeline-icon"
                style={{
                  background: step.status === 'pending' ? 'rgba(255,255,255,0.05)' : `${color}20`,
                  border: `1.5px solid ${step.status === 'pending' ? '#333' : color}`,
                }}
              >
                <Icon size={12} color={step.status === 'pending' ? '#555' : color} />
              </div>
              {!isLast && (
                <div
                  className="copilot-timeline-line"
                  style={{
                    background: step.status === 'done' ? `${color}60` : 'rgba(255,255,255,0.08)',
                  }}
                />
              )}
            </div>

            {/* Content */}
            <div className="copilot-timeline-content" style={{ paddingBottom: isLast ? 0 : 16 }}>
              <div className="copilot-timeline-header">
                <span className={`copilot-timeline-label ${step.status === 'pending' ? 'pending' : 'active'}`}>
                  {step.label}
                </span>
                <StatusIcon status={step.status} />
              </div>

              {step.status === 'running' && (
                <div className="copilot-timeline-status">Running…</div>
              )}

              {step.status === 'done' && step.result && (
                <StepResult agent={step.agent} result={step.result} />
              )}
            </div>
          </div>
        );
      })}

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}

function StepResult({ agent, result }: { agent: string; result: Record<string, any> }) {
  if (agent === 'analyze_environment' && result.results) {
    const risks: number[] = result.results.map((r: any) => r.environmental_risk ?? 0);
    const avg = risks.reduce((a, b) => a + b, 0) / (risks.length || 1);
    return (
      <div className="copilot-timeline-result success">
        {risks.length} parcels · avg risk {(avg * 100).toFixed(0)}%
      </div>
    );
  }
  if (agent === 'query_zoning' && result.chunks_retrieved !== undefined) {
    return (
      <div className="copilot-timeline-result info">
        {result.chunks_retrieved} regulation chunks retrieved
      </div>
    );
  }
  if (agent === 'optimize_land_use' && result.plans) {
    return (
      <div className="copilot-timeline-result warning">
        {result.plans.length} Pareto-optimal plans generated
      </div>
    );
  }
  if (agent === 'explain_risk' && result.explanations) {
    return (
      <div className="copilot-timeline-result" style={{ color: '#B48EFF' }}>
        {result.explanations.length} parcel(s) explained
      </div>
    );
  }
  if (result.error) {
    return <div className="copilot-timeline-result error">{result.error}</div>;
  }
  return null;
}
