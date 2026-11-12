/**
 * Typed HTTP Client for the NOC Copilot Backend (`/api/v1/*`).
 */
import type {
  Connector,
  OtdrTraceData,
  OverviewResponse,
  StormBenchmarkResult,
} from '../types/api';

export const nocApi = {
  async getOverview(): Promise<OverviewResponse> {
    const r = await fetch('/api/v1/overview');
    if (!r.ok) throw new Error(`Failed to fetch overview (${r.status})`);
    return r.json();
  },

  async triggerScenario(scenarioId: string): Promise<void> {
    const r = await fetch('/api/v1/faults/trigger', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario_id: scenarioId }),
    });
    if (!r.ok) throw new Error(`Failed to trigger scenario ${scenarioId}`);
  },

  async triggerCableCut(cableId: string, cutRatio: number): Promise<void> {
    const r = await fetch('/api/v1/faults/trigger', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        fault_type: 'fibre_cut',
        target_id: cableId,
        cut_ratio: cutRatio,
      }),
    });
    if (!r.ok) throw new Error(`Failed to inject cut on ${cableId}`);
  },

  async resetNetwork(): Promise<void> {
    await fetch('/api/v1/faults/reset', { method: 'POST' });
  },

  async getCableOtdr(cableId: string): Promise<OtdrTraceData> {
    const r = await fetch(`/api/v1/otdr/cable/${cableId}`);
    if (!r.ok) throw new Error(`No OTDR trace found for ${cableId}`);
    return r.json();
  },

  async parseUploadedSor(file: File): Promise<OtdrTraceData> {
    const fd = new FormData();
    fd.append('file', file);
    const r = await fetch('/api/v1/otdr/parse-sor', { method: 'POST', body: fd });
    if (!r.ok) throw new Error(`Failed to parse SR-4731 .sor file ${file.name}`);
    return r.json();
  },

  async approveIncidentActions(incidentId: string, actionIds?: string[]): Promise<void> {
    const r = await fetch(`/api/v1/incidents/${incidentId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        approved_by: 'Lead NOC Engineer',
        action_ids: actionIds || null,
      }),
    });
    if (!r.ok) throw new Error('Failed to execute approved actions');
  },

  async runStormBenchmark(stormSize: number = 10000): Promise<StormBenchmarkResult> {
    const r = await fetch('/api/v1/benchmark/storm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ storm_size: stormSize }),
    });
    if (!r.ok) throw new Error('Benchmark failed');
    return r.json();
  },

  async get3gppXml(): Promise<string> {
    const r = await fetch('/api/v1/telemetry/3gpp-xml');
    if (!r.ok) return '';
    const data = await r.json();
    return data.xml || '';
  },

  async updateLlmSettings(
    provider: string,
    model: string,
    apiKey: string,
    activeIncidentId?: string
  ): Promise<void> {
    await fetch('/api/v1/settings/llm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, model, api_key: apiKey }),
    });
    if (activeIncidentId) {
      await fetch(`/api/v1/incidents/${activeIncidentId}/regenerate-ai`, {
        method: 'POST',
      });
    }
  },

  async updateConnector(
    connector: Connector,
    endpointUrl: string,
    mode: string
  ): Promise<void> {
    await fetch(`/api/v1/connectors/${connector.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        endpoint_url: endpointUrl,
        mode,
        enabled: true,
        config_json: connector.config_json || {},
      }),
    });
  },
};
