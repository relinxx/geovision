import { useState, useCallback, useRef } from 'react';
import { apiClient } from '../utils/api';
import {
  CopilotMessage,
  CopilotSSEEvent,
  AgentStepStatus,
  RiskExplanation,
} from '../types';

const AGENT_LABELS: Record<string, string> = {
  orchestrator:        'Orchestrator',
  analyze_environment: 'Environment Agent',
  query_zoning:        'Zoning RAG',
  optimize_land_use:   'Spatial Optimizer',
  explain_risk:        'Risk Explainer',
};

function makeStep(agent: string): AgentStepStatus {
  return {
    agent,
    label: AGENT_LABELS[agent] ?? agent,
    status: 'pending',
  };
}

export interface CopilotStreamState {
  messages: CopilotMessage[];
  agentSteps: AgentStepStatus[];
  landUsePlan: Array<{ parcel_id: string; use_label: string }> | null;
  explanations: RiskExplanation[];
  isStreaming: boolean;
  error: string | null;
}

export interface UseCopilotStream extends CopilotStreamState {
  sendQuery: (
    query: string,
    parcelIds: string[],
    parcelFeatures: Record<string, any>[],
  ) => Promise<void>;
  reset: () => void;
}

const INITIAL_STATE: CopilotStreamState = {
  messages: [],
  agentSteps: [],
  landUsePlan: null,
  explanations: [],
  isStreaming: false,
  error: null,
};

export function useCopilotStream(): UseCopilotStream {
  const [state, setState] = useState<CopilotStreamState>(INITIAL_STATE);
  const historyRef = useRef<{ role: string; content: string }[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    historyRef.current = [];
    setState(INITIAL_STATE);
  }, []);

  const sendQuery = useCallback(async (
    query: string,
    parcelIds: string[],
    parcelFeatures: Record<string, any>[],
  ) => {
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    // Append user message
    const userMsg: CopilotMessage = { role: 'user', content: query };
    setState(prev => ({
      ...prev,
      messages: [...prev.messages, userMsg],
      agentSteps: [],
      isStreaming: true,
      error: null,
    }));

    // Placeholder assistant message (will be filled as chunks arrive)
    const assistantMsg: CopilotMessage = { role: 'assistant', content: '', isStreaming: true };
    setState(prev => ({ ...prev, messages: [...prev.messages, assistantMsg] }));

    try {
      const response = await apiClient.copilotStream({
        query,
        parcel_ids: parcelIds,
        parcel_features: parcelFeatures,
        history: historyRef.current,
      });

      if (!response.body) throw new Error('No response body from copilot endpoint');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let fullAnswer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data:')) continue;
          const jsonStr = line.slice(5).trim();
          if (!jsonStr) continue;

          let event: CopilotSSEEvent;
          try {
            event = JSON.parse(jsonStr);
          } catch {
            continue;
          }

          switch (event.type) {
            case 'agent_start':
              setState(prev => {
                const agent = event.agent!;
                const exists = prev.agentSteps.find(s => s.agent === agent);
                const steps = exists
                  ? prev.agentSteps.map(s =>
                      s.agent === agent ? { ...s, status: 'running' as const } : s
                    )
                  : [...prev.agentSteps, { ...makeStep(agent), status: 'running' as const }];
                return { ...prev, agentSteps: steps };
              });
              break;

            case 'agent_complete':
              setState(prev => ({
                ...prev,
                agentSteps: prev.agentSteps.map(s =>
                  s.agent === event.agent
                    ? { ...s, status: 'done', result: event.result }
                    : s
                ),
                // Extract explanations if risk explainer ran
                explanations:
                  event.agent === 'explain_risk' && event.result?.explanations
                    ? event.result.explanations
                    : prev.explanations,
              }));
              break;

            case 'text_chunk':
              if (event.text) {
                fullAnswer += event.text;
                setState(prev => {
                  const msgs = [...prev.messages];
                  const last = msgs[msgs.length - 1];
                  if (last?.role === 'assistant') {
                    msgs[msgs.length - 1] = { ...last, content: fullAnswer };
                  }
                  return { ...prev, messages: msgs };
                });
              }
              break;

            case 'final':
              setState(prev => {
                const msgs = [...prev.messages];
                const last = msgs[msgs.length - 1];
                const finalText = event.summary || fullAnswer || 'Analysis complete.';
                if (last?.role === 'assistant') {
                  msgs[msgs.length - 1] = { ...last, content: finalText, isStreaming: false };
                }
                return {
                  ...prev,
                  messages: msgs,
                  landUsePlan: event.land_use_plan ?? prev.landUsePlan,
                  isStreaming: false,
                };
              });
              historyRef.current = [
                ...historyRef.current,
                { role: 'user', content: query },
                { role: 'assistant', content: fullAnswer || event.summary || '' },
              ];
              break;

            case 'error':
              setState(prev => ({
                ...prev,
                isStreaming: false,
                error: event.message ?? 'An error occurred.',
                messages: prev.messages.map((m, i) =>
                  i === prev.messages.length - 1 && m.role === 'assistant'
                    ? { ...m, content: 'An error occurred. Please try again.', isStreaming: false }
                    : m
                ),
              }));
              break;
          }
        }
      }
    } catch (err: any) {
      if (err?.name === 'AbortError') return;
      const msg = err instanceof Error ? err.message : String(err);
      setState(prev => ({
        ...prev,
        isStreaming: false,
        error: msg,
        messages: prev.messages.map((m, i) =>
          i === prev.messages.length - 1 && m.role === 'assistant'
            ? { ...m, content: 'Failed to connect to the Copilot. Is the backend running?', isStreaming: false }
            : m
        ),
      }));
    }
  }, []);

  return { ...state, sendQuery, reset };
}
