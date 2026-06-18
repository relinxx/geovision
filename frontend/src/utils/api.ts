// API service layer for backend communication
import {
  LandUseZone,
  Metrics,
  GeoJSONExport,
  ParcelGeoJSONExport,
  ParcelSuitabilityScore,
  SpatialOptimizeRequest,
  SpatialOptimizationResponse,
  ExplainSpatialAssignmentRequest,
  SpatialAssignmentExplanation,
  SavedMapCreatePayload,
  SavedMapListResponse,
  SavedMapResponse,
  SavedMapUpdatePayload,
} from '../types';

// Use Vite env variable pattern instead of Node's `process.env`.
// Cast to `any` so we don't depend on Node typings in the frontend.
const API_BASE_URL =
  (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';
const IS_DEV = Boolean((import.meta as any).env?.DEV);

/**
 * API client for backend communication
 */
class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = String(baseUrl || '').replace(/\/+$/, '');
  }

  private buildBaseCandidates(): string[] {
    const candidates: string[] = [];
    const pushCandidate = (value: string) => {
      const normalized = String(value || '').replace(/\/+$/, '');
      if (!normalized) return;
      if (!candidates.includes(normalized)) {
        candidates.push(normalized);
      }
    };

    if (typeof window !== 'undefined' && window.location?.origin) {
      const origin = window.location.origin.replace(/\/+$/, '');
      if (IS_DEV && origin) {
        pushCandidate(origin);
        pushCandidate(`${origin}/api`);
      }
    }

    pushCandidate(this.baseUrl);
    if (this.baseUrl.endsWith('/api')) {
      pushCandidate(this.baseUrl.slice(0, -4));
    } else {
      pushCandidate(`${this.baseUrl}/api`);
    }

    if (typeof window !== 'undefined' && window.location?.origin) {
      const origin = window.location.origin.replace(/\/+$/, '');
      if (!IS_DEV) {
        pushCandidate(origin);
        pushCandidate(`${origin}/api`);
      }
    }

    pushCandidate('http://localhost:8000');
    pushCandidate('http://localhost:8000/api');
    pushCandidate('http://127.0.0.1:8000');
    pushCandidate('http://127.0.0.1:8000/api');
    pushCandidate('http://localhost:8001');
    pushCandidate('http://localhost:8001/api');
    pushCandidate('http://127.0.0.1:8001');
    pushCandidate('http://127.0.0.1:8001/api');

    return candidates;
  }

  private getAuthToken(): string | null {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('access_token');
    }
    return null;
  }

  private async request<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<T> {
    const baseCandidates = this.buildBaseCandidates();
    let lastError: Error | null = null;
    let lastStatus: number | null = null;
    let lastResponseText = '';

    // Get auth token
    const token = this.getAuthToken();
    const authHeaders: Record<string, string> = token 
      ? { 'Authorization': `Bearer ${token}` }
      : {};

    for (let index = 0; index < baseCandidates.length; index += 1) {
      const base = baseCandidates[index];
      const url = `${base}${endpoint}`;

      try {
        const response = await fetch(url, {
          ...options,
          headers: {
            'Content-Type': 'application/json',
            ...authHeaders,
            ...options?.headers,
          },
        });
        const responseText = await response.text();

        if (!response.ok) {
          lastStatus = response.status;
          lastResponseText = responseText;

          const shouldRetry =
            (response.status === 404 || response.status === 405) &&
            index < baseCandidates.length - 1;

          if (shouldRetry) {
            console.warn(
              `[API] ${response.status} on ${url}; retrying with alternate base URL`
            );
            continue;
          }

          console.error(`API Error [${response.status}] at ${url}:`, responseText);
          throw new Error(
            `API request failed at ${url}: ${response.status} ${response.statusText} - ${responseText}`
          );
        }

        try {
          if (!responseText.trim()) {
            return undefined as T;
          }
          return JSON.parse(responseText) as T;
        } catch (parseError: any) {
          const shouldRetry = index < baseCandidates.length - 1;
          if (shouldRetry) {
            console.warn(
              `[API] Invalid JSON from ${url}; retrying with alternate base URL`
            );
            continue;
          }
          const preview = responseText.slice(0, 280);
          throw new Error(
            `Invalid JSON response from ${url}: ${parseError?.message || parseError}. Response preview: ${preview}`
          );
        }
      } catch (error: any) {
        lastError = error instanceof Error ? error : new Error(String(error));

        const isNetworkError =
          error instanceof TypeError && error.message.includes('fetch');
        const hasMoreCandidates = index < baseCandidates.length - 1;

        if (isNetworkError && hasMoreCandidates) {
          console.warn(`[API] Network error on ${url}; trying next base URL`);
          continue;
        }

        if (!hasMoreCandidates) {
          if (isNetworkError) {
            throw new Error(
              `Failed to connect to backend. Tried: ${baseCandidates.join(', ')}`
            );
          }
          throw lastError;
        }
      }
    }

    if (lastError) {
      throw lastError;
    }
    throw new Error(
      `API request failed for ${endpoint}${lastStatus ? ` (status ${lastStatus})` : ''}${lastResponseText ? `: ${lastResponseText}` : ''}`
    );
  }

  // TODO: Integrate with FastAPI backend
  async fetchMetrics(): Promise<Metrics> {
    return this.request<Metrics>('/metrics');
  }

  // TODO: Integrate with FastAPI backend
  async fetchZones(region: string): Promise<LandUseZone[]> {
    return this.request<LandUseZone[]>(`/zones?region=${region}`);
  }

  // TODO: Integrate with FastAPI backend
  async runOptimization(zones: LandUseZone[]): Promise<LandUseZone[]> {
    return this.request<LandUseZone[]>('/optimize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ zones }),
    });
  }

  // TODO: Integrate with AI agents
  async runZoningAgent(input: unknown): Promise<unknown> {
    return this.request('/agents/zoning', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    });
  }

  // RAG: Ask zoning question (placeholder endpoint)
  async zoningRagAsk(payload: {
    question: string;
    apn?: string | null;
    context?: Record<string, any>;
    session_id?: string | null;
  }): Promise<{ answer: string; session_id?: string; citations?: any[] } | any> {
    // Endpoint name is a placeholder; update when backend is ready
    return this.request('/api/rag/zoning/ask', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  // TODO: Integrate with AI agents
  async runEnvironmentalAgent(input: unknown): Promise<unknown> {
    return this.request('/agents/environmental', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    });
  }

  // TODO: Integrate with AI agents
  async runPopulationAgent(input: unknown): Promise<unknown> {
    return this.request('/agents/population', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    });
  }

  /**
   * D2 - Task A4/D1: Send parcel GeoJSON to backend and receive suitability scores.
   *
   * Calls the /predict_suitability endpoint which:
   * 1. Accepts parcels (GeoJSON Feature array)
   * 2. Extracts/generates features (B2)
   * 3. Calls agent.predict(df) (C5)
   * 4. Returns GeoJSON with scores in properties
   */
  async getSuitabilityScores(
    geojson: ParcelGeoJSONExport
  ): Promise<ParcelGeoJSONExport> {
    // D2: Call the actual backend endpoint
    // Backend expects: { "parcels": geojson.features }
    // Backend returns: GeoJSON FeatureCollection with scores in properties
    return this.request<ParcelGeoJSONExport>('/api/predict_suitability', {
      method: 'POST',
      body: JSON.stringify({ parcels: geojson.features }),
    });
  }

  /**
   * Run Spatial Agent NSGA-II optimization and return K Pareto plans.
   */
  async optimizeSpatialPlans(
    payload: SpatialOptimizeRequest
  ): Promise<SpatialOptimizationResponse> {
    return this.request<SpatialOptimizationResponse>('/api/spatial/optimize', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async explainSpatialAssignment(
    payload: ExplainSpatialAssignmentRequest
  ): Promise<SpatialAssignmentExplanation> {
    return this.request<SpatialAssignmentExplanation>('/api/spatial/explain-assignment', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async saveGeneratedMap(payload: SavedMapCreatePayload): Promise<SavedMapResponse> {
    return this.request<SavedMapResponse>('/api/saved-maps', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async listSavedMaps(params?: { limit?: number; offset?: number }): Promise<SavedMapListResponse> {
    const query = new URLSearchParams();
    if (typeof params?.limit === 'number') {
      query.set('limit', String(params.limit));
    }
    if (typeof params?.offset === 'number') {
      query.set('offset', String(params.offset));
    }
    const suffix = query.toString().length > 0 ? `?${query.toString()}` : '';
    return this.request<SavedMapListResponse>(`/api/saved-maps${suffix}`);
  }

  async getSavedMap(savedMapId: number): Promise<SavedMapResponse> {
    return this.request<SavedMapResponse>(`/saved-maps/${savedMapId}`);
  }

  async updateSavedMap(
    savedMapId: number,
    payload: SavedMapUpdatePayload
  ): Promise<SavedMapResponse> {
    return this.request<SavedMapResponse>(`/saved-maps/${savedMapId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  }

  async deleteSavedMap(savedMapId: number): Promise<void> {
    await this.request<void>(`/saved-maps/${savedMapId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Stream Copilot query as SSE. Returns raw Response for streaming.
   * Caller reads response.body as ReadableStream.
   */
  async copilotStream(payload: {
    query: string;
    parcel_ids: string[];
    parcel_features: Record<string, any>[];
    history: { role: string; content: string }[];
  }): Promise<Response> {
    const token = this.getAuthToken();
    const candidates = this.buildBaseCandidates();
    let lastError: Error | null = null;

    for (const base of candidates) {
      const url = `${base}/api/copilot/query`;
      try {
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify(payload),
        });
        if (response.ok) return response;
        if (response.status !== 404 && response.status !== 405) {
          throw new Error(`Copilot endpoint returned ${response.status}`);
        }
      } catch (err: any) {
        lastError = err instanceof Error ? err : new Error(String(err));
        const isNetwork = err instanceof TypeError && err.message.includes('fetch');
        if (!isNetwork) throw lastError;
      }
    }
    throw lastError ?? new Error('Could not reach copilot endpoint');
  }

  /**
   * Compute counterfactual risk score by toggling hazard flags.
   */
  async riskCounterfactual(payload: {
    parcel_id: string;
    parcel_properties: Record<string, any>;
    changes: Record<string, any>;
  }): Promise<{
    parcel_id: string;
    original_score: number;
    counterfactual_score: number;
    delta: number;
    applied_changes: Record<string, { from: number; to: number }>;
  }> {
    return this.request('/api/risk/counterfactual', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }
}

export const apiClient = new ApiClient(API_BASE_URL);

/**
 * D2 - Convenience function for front-end usage
 */
export function getSuitabilityScores(geojson: ParcelGeoJSONExport) {
  return apiClient.getSuitabilityScores(geojson);
}
