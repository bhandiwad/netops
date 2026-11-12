import React from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  GitBranch,
  MapPin,
  Play,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Terminal,
  Zap,
} from 'lucide-react';
import { MultiLayerGraph } from '../components/MultiLayerGraph';
import { OspMap } from '../components/OspMap';
import { OtdrTracePanel } from '../components/OtdrTracePanel';
import type {
  CopilotTabId,
  FaultLocation,
  FaultScenario,
  Incident,
  OperatorProfile,
  OtdrTraceData,
  OverviewResponse,
  StageTabId,
  ThemeMode,
} from '../types/api';

interface WorkspaceViewProps {
  overview: OverviewResponse;
  incidents: Incident[];
  activeIncident: Incident | null;
  onSelectIncidentId: (incidentId: string) => void;
  activeProfile: OperatorProfile | Record<string, unknown>;
  scenarios: FaultScenario[];
  selectedScenarioId: string;
  onSelectScenarioId: (scenarioId: string) => void;
  stageTab: StageTabId;
  onSelectStageTab: (tab: StageTabId) => void;
  copilotTab: CopilotTabId;
  onSelectCopilotTab: (tab: CopilotTabId) => void;
  selectedCableId: string | null;
  displayedOtdr: OtdrTraceData | null;
  displayedFaultLoc: FaultLocation | null;
  srlgViolationCount: number;
  theme: ThemeMode;
  busy: boolean;
  onTriggerScenario: () => void;
  onResetNetwork: () => void;
  onSelectCable: (cableId: string) => void;
  onTriggerCutOnCable: (cableId: string, cutRatio: number) => void;
  onUploadSorFile: (file: File) => void;
  onApproveActions: (incidentId: string, actionIds?: string[]) => void;
}

export const WorkspaceView: React.FC<WorkspaceViewProps> = ({
  overview,
  incidents,
  activeIncident,
  onSelectIncidentId,
  activeProfile,
  scenarios,
  selectedScenarioId,
  onSelectScenarioId,
  stageTab,
  onSelectStageTab,
  copilotTab,
  onSelectCopilotTab,
  selectedCableId,
  displayedOtdr,
  displayedFaultLoc,
  srlgViolationCount,
  theme,
  busy,
  onTriggerScenario,
  onResetNetwork,
  onSelectCable,
  onTriggerCutOnCable,
  onUploadSorFile,
  onApproveActions,
}) => {
  const totalAlarms = overview.alarms?.length || 0;
  const totalSlaExposure = activeIncident?.impact?.four_hour_sla_exposure_aed || 0;

  return (
    <>
      {/* Scenario Bar + 4 Clean Summary KPIs */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-4 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
            <Zap className="w-4 h-4 text-rose-500" /> Fault Scenario:
          </span>
          <select
            value={selectedScenarioId}
            onChange={(e) => onSelectScenarioId(e.target.value)}
            className="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 text-xs font-medium text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 min-w-[300px]"
          >
            {scenarios.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title}
              </option>
            ))}
          </select>
          <button
            onClick={onTriggerScenario}
            disabled={busy}
            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm transition"
          >
            <Play className="w-3.5 h-3.5 fill-current" /> Simulate Fault
          </button>
          <button
            onClick={onResetNetwork}
            disabled={busy}
            className="px-3 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-medium flex items-center gap-1.5 transition"
          >
            <RotateCcw className="w-3.5 h-3.5" /> Reset
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-6">
          <div>
            <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
              Noise Compression
            </div>
            <div className="text-sm font-bold font-mono text-slate-900 dark:text-white">
              {incidents.length > 0
                ? `${totalAlarms} Alarms → ${incidents.length} Root Cause${incidents.length > 1 ? 's' : ''}`
                : '0 Active Faults'}
            </div>
          </div>
          <div className="h-7 w-px bg-slate-200 dark:bg-slate-800" />
          <div>
            <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
              Dig Error Avoided
            </div>
            <div className="text-sm font-bold font-mono text-emerald-600 dark:text-emerald-400">
              {displayedFaultLoc?.dispatch_error_avoided_m
                ? `${displayedFaultLoc.dispatch_error_avoided_m} m saved`
                : displayedFaultLoc?.dying_gasp_confirmed
                ? 'Truck Roll Saved'
                : '—'}
            </div>
          </div>
          <div className="h-7 w-px bg-slate-200 dark:bg-slate-800" />
          <div>
            <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
              4-Hr SLA Exposure
            </div>
            <div className="text-sm font-bold font-mono text-rose-600 dark:text-rose-400">
              AED {totalSlaExposure.toLocaleString()}
            </div>
          </div>
          <div className="h-7 w-px bg-slate-200 dark:bg-slate-800" />
          <div>
            <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
              SRLG Violations
            </div>
            <div className="text-sm font-bold font-mono text-amber-600 dark:text-amber-400">
              {srlgViolationCount} Detected
            </div>
          </div>
        </div>
      </div>

      {/* 2-Column Workspace: Stage (7 cols) + Copilot Drawer (5 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        <div className="lg:col-span-7 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl shadow-sm overflow-hidden flex flex-col">
          <div className="px-5 py-3.5 border-b border-slate-200/80 dark:border-slate-800 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-1.5 bg-slate-100 dark:bg-slate-800 p-1 rounded-xl">
              {[
                { id: 'map', label: 'GIS Fibre & RAN Map', icon: MapPin },
                { id: 'otdr', label: 'OTDR Trace (.sor)', icon: Activity },
                { id: 'graph', label: 'Blast Radius Graph', icon: GitBranch },
                { id: 'stream', label: `Telemetry Stream (${totalAlarms})`, icon: Terminal },
              ].map((st) => {
                const Icon = st.icon;
                const active = stageTab === st.id;
                return (
                  <button
                    key={st.id}
                    onClick={() => onSelectStageTab(st.id as StageTabId)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${
                      active
                        ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-sm'
                        : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    <span>{st.label}</span>
                  </button>
                );
              })}
            </div>

            <span className="text-xs text-slate-500 dark:text-slate-400 font-mono">
              {selectedCableId ? `Inspecting ${selectedCableId}` : 'Click any cable to inspect OTDR'}
            </span>
          </div>

          <div className="p-4">
            {stageTab === 'map' && (
              <div className="space-y-4">
                <div className="h-[500px] w-full">
                  <OspMap
                    gis={overview.gis || { ducts: [], manholes: [], cables: [] }}
                    topology={overview.topology || {}}
                    activeIncident={activeIncident}
                    activeProfile={activeProfile}
                    selectedCableId={selectedCableId}
                    theme={theme}
                    onSelectCable={onSelectCable}
                    onTriggerCutOnCable={onTriggerCutOnCable}
                  />
                </div>
                <OtdrTracePanel
                  trace={displayedOtdr}
                  faultLocation={displayedFaultLoc}
                  theme={theme}
                  onUploadSorFile={onUploadSorFile}
                />
              </div>
            )}

            {stageTab === 'otdr' && (
              <div className="space-y-4">
                <OtdrTracePanel
                  trace={displayedOtdr}
                  faultLocation={displayedFaultLoc}
                  theme={theme}
                  onUploadSorFile={onUploadSorFile}
                />
                {displayedOtdr?.key_events && (
                  <div className="border border-slate-200/80 dark:border-slate-800 rounded-xl overflow-hidden">
                    <div className="px-4 py-2.5 bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800 text-xs font-semibold text-slate-700 dark:text-slate-200">
                      Telcordia SR-4731 KeyEvents Table (Parsed from Binary .sor)
                    </div>
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-50/50 dark:bg-slate-900/50 text-slate-500 dark:text-slate-400 border-b border-slate-200/70 dark:border-slate-800">
                        <tr>
                          <th className="py-2.5 px-4">Event #</th>
                          <th className="py-2.5 px-4">Optical Distance</th>
                          <th className="py-2.5 px-4">Splice Loss</th>
                          <th className="py-2.5 px-4">Reflectance</th>
                          <th className="py-2.5 px-4">SR-4731 Code</th>
                          <th className="py-2.5 px-4">Comment / Chamber</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200/60 dark:divide-slate-800 font-mono">
                        {displayedOtdr.key_events.map((ev) => (
                          <tr key={ev.event_number} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40">
                            <td className="py-2.5 px-4 font-semibold">#{ev.event_number}</td>
                            <td className="py-2.5 px-4 text-indigo-600 dark:text-indigo-400 font-semibold">
                              {ev.distance_m} m
                            </td>
                            <td className="py-2.5 px-4">
                              <span
                                className={
                                  ev.splice_loss_db > 5
                                    ? 'text-rose-600 dark:text-rose-400 font-bold'
                                    : 'text-slate-700 dark:text-slate-300'
                                }
                              >
                                {ev.splice_loss_db} dB
                              </span>
                            </td>
                            <td className="py-2.5 px-4 text-slate-600 dark:text-slate-400">
                              {ev.refl_loss_db ?? ev.refl_db ?? 0} dB
                            </td>
                            <td className="py-2.5 px-4 text-slate-500">{ev.event_code}</td>
                            <td className="py-2.5 px-4 font-sans text-slate-700 dark:text-slate-300">
                              {ev.comment}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {stageTab === 'graph' && (
              <MultiLayerGraph
                graph={overview.dependency_graph || { nodes: [], edges: [] }}
                theme={theme}
                onSelectCable={(cid) => {
                  onSelectCable(cid);
                  onSelectStageTab('otdr');
                }}
              />
            )}

            {stageTab === 'stream' && (
              <div className="space-y-4">
                <div className="max-h-[460px] overflow-y-auto border border-slate-200/80 dark:border-slate-800 rounded-xl divide-y divide-slate-200/70 dark:divide-slate-800">
                  {(overview.alarms || []).length === 0 ? (
                    <div className="p-8 text-center text-sm text-slate-500">
                      No active alarms. Select a fault scenario above and click <strong>Simulate Fault</strong>.
                    </div>
                  ) : (
                    overview.alarms.map((alm) => (
                      <div key={alm.alarm_id} className="p-3.5 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition">
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <div className="flex items-center gap-2">
                            <span
                              className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase ${
                                alm.severity === 'CRITICAL'
                                  ? 'bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300'
                                  : alm.severity === 'MAJOR'
                                  ? 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                                  : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                              }`}
                            >
                              {alm.severity}
                            </span>
                            <span className="font-mono text-xs font-semibold text-indigo-600 dark:text-indigo-400">
                              {alm.source_oem}
                            </span>
                            <span className="text-xs font-mono text-slate-500">[{alm.protocol}]</span>
                          </div>
                          <span className="font-mono text-[11px] text-slate-400">{alm.alarm_id}</span>
                        </div>
                        <div className="text-xs font-semibold text-slate-900 dark:text-white">
                          {alm.specific_problem} — <span className="font-mono">{alm.resource_id}</span>
                        </div>
                        <div className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
                          {alm.raw_text}
                        </div>
                      </div>
                    ))
                  )}
                </div>

                {(overview.wire_packets || []).length > 0 && (
                  <div className="border border-slate-200/80 dark:border-slate-800 rounded-xl p-3.5 bg-slate-50 dark:bg-slate-950">
                    <div className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-2">
                      Live Wire Listeners (UDP Syslog :15514 · SNMPv2c Trap :15162 · Redpanda Kafka :19092)
                    </div>
                    <div className="space-y-1.5 max-h-40 overflow-y-auto font-mono text-[11px]">
                      {overview.wire_packets.map((pkt, i) => (
                        <div key={i} className="text-slate-600 dark:text-slate-400 truncate">
                          <span className="text-indigo-600 dark:text-indigo-400 font-semibold">
                            [{pkt.protocol}]
                          </span>{' '}
                          {pkt.payload}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* RIGHT: AI COPILOT & INCIDENT INVESTIGATION PANEL */}
        <div className="lg:col-span-5 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl shadow-sm overflow-hidden flex flex-col">
          {!activeIncident ? (
            <div className="p-8 text-center space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800 mx-auto flex items-center justify-center text-emerald-600 dark:text-emerald-400">
                <ShieldCheck className="w-6 h-6" />
              </div>
              <h3 className="text-base font-bold text-slate-900 dark:text-white">
                All Network Layers Nominal
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 max-w-md mx-auto leading-relaxed">
                12 OEM connectors are streaming healthy telemetry. Choose any telco fault scenario above (or click any fibre cable on the map) to watch the Copilot isolate root cause in seconds.
              </p>
            </div>
          ) : (
            <>
              <div className="p-5 border-b border-slate-200/80 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/30">
                {/* Multi-incident switcher when 2+ independent causal subgraphs are active simultaneously */}
                {incidents.length > 1 && (
                  <div className="flex flex-wrap gap-1.5 mb-3">
                    {incidents.map((inc) => (
                      <button
                        key={inc.incident_id}
                        onClick={() => onSelectIncidentId(inc.incident_id)}
                        className={`px-2.5 py-1 rounded-lg text-[11px] font-mono font-semibold border transition ${
                          inc.incident_id === activeIncident.incident_id
                            ? 'bg-indigo-600 text-white border-indigo-600'
                            : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700'
                        }`}
                      >
                        {inc.incident_id} ({inc.alarm_count})
                      </button>
                    ))}
                  </div>
                )}

                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="px-2.5 py-0.5 rounded-full bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300 text-xs font-bold">
                    {activeIncident.severity} · {activeIncident.incident_id}
                  </span>
                  <span className="px-2.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300 text-xs font-semibold">
                    Confidence: {Math.round(activeIncident.confidence * 100)}%
                  </span>
                </div>
                <h2 className="text-base font-bold text-slate-900 dark:text-white leading-snug">
                  {activeIncident.title}
                </h2>

                <div className="flex items-center gap-1.5 bg-slate-200/70 dark:bg-slate-800 p-1 rounded-xl mt-4">
                  {[
                    { id: 'diagnosis', label: 'Diagnosis & SLAs' },
                    { id: 'runbook', label: 'Copilot & Runbook' },
                    {
                      id: 'actions',
                      label: `Remediation (${activeIncident.proposed_actions?.length || 0})`,
                    },
                  ].map((ct) => (
                    <button
                      key={ct.id}
                      onClick={() => onSelectCopilotTab(ct.id as CopilotTabId)}
                      className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition ${
                        copilotTab === ct.id
                          ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-sm'
                          : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                      }`}
                    >
                      {ct.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="p-5 space-y-4 max-h-[640px] overflow-y-auto">
                {copilotTab === 'diagnosis' && (
                  <>
                    <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/80 dark:border-slate-800 space-y-2">
                      <div className="text-xs font-semibold uppercase tracking-wider text-indigo-600 dark:text-indigo-400">
                        Root Cause Isolation ({activeIncident.root_cause_type})
                      </div>
                      <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
                        {activeIncident.root_cause_summary}
                      </p>
                      {activeIncident.fault_location?.dispatch_verdict && (
                        <div className="mt-2 pt-2 border-t border-slate-200 dark:border-slate-700 text-xs font-bold text-emerald-700 dark:text-emerald-400">
                          ✓ {activeIncident.fault_location.dispatch_verdict}
                        </div>
                      )}
                    </div>

                    {(activeIncident.srlg_findings || []).map((srlg) => (
                      <div
                        key={srlg.service_id}
                        className="p-4 rounded-xl bg-amber-50/90 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 space-y-1.5"
                      >
                        <div className="flex items-center gap-2 text-xs font-bold text-amber-900 dark:text-amber-300">
                          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                          <span>Hidden SRLG Route-Diversity Violation Exposed</span>
                        </div>
                        <p className="text-xs text-amber-800 dark:text-amber-200/90 leading-relaxed">
                          <strong>{srlg.customer_name}</strong> ({srlg.service_id}) ordered physical diversity, but{' '}
                          {srlg.risk_summary}.
                        </p>
                      </div>
                    ))}

                    <div className="space-y-2.5">
                      <div className="flex items-center justify-between text-xs font-semibold text-slate-700 dark:text-slate-300">
                        <span>
                          Impacted Enterprise SLAs ({activeIncident.impact?.impacted_service_count || 0})
                        </span>
                        <span className="font-mono text-rose-600 dark:text-rose-400">
                          AED {activeIncident.impact?.total_sla_penalty_per_hour_aed?.toLocaleString() || 0}/hr risk
                        </span>
                      </div>
                      {(activeIncident.impact?.impacted_services || []).map((svc) => (
                        <div
                          key={svc.service_id}
                          className="p-3.5 rounded-xl border border-slate-200/80 dark:border-slate-800 flex items-center justify-between gap-3"
                        >
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-bold text-slate-900 dark:text-white">
                                {svc.customer_name}
                              </span>
                              <span className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[10px] font-semibold text-slate-600 dark:text-slate-300">
                                {svc.sla_tier}
                              </span>
                            </div>
                            <div className="text-xs font-mono text-slate-500 mt-0.5">
                              {svc.service_id} · {svc.bandwidth} {svc.service_type}
                            </div>
                          </div>
                          <div className="text-right">
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                svc.outage_state === 'COMPLETE_OUTAGE'
                                  ? 'bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300'
                                  : 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                              }`}
                            >
                              {svc.outage_state === 'COMPLETE_OUTAGE' ? 'OUTAGE' : 'DEGRADED'}
                            </span>
                            <div className="text-xs font-mono font-semibold text-slate-700 dark:text-slate-300 mt-1">
                              AED {svc.penalty_per_hour_aed.toLocaleString()}/hr
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                )}

                {copilotTab === 'runbook' && (
                  <div className="space-y-4">
                    <div className="p-3.5 rounded-xl bg-indigo-50/70 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800/70 flex items-center justify-between gap-2">
                      <div>
                        <div className="text-[11px] font-semibold text-indigo-600 dark:text-indigo-400 flex items-center gap-1.5">
                          <Sparkles className="w-3.5 h-3.5" /> pgvector Semantic Runbook Retrieval
                        </div>
                        <div className="text-xs font-bold text-slate-900 dark:text-white mt-0.5">
                          {activeIncident.ai_copilot?.matched_runbook_id}:{' '}
                          {activeIncident.ai_copilot?.matched_runbook_title}
                        </div>
                      </div>
                      <span className="px-2.5 py-1 rounded-lg bg-white dark:bg-slate-900 border border-indigo-200 dark:border-indigo-800 font-mono text-xs font-bold text-indigo-600 dark:text-indigo-400">
                        sim={activeIncident.ai_copilot?.pgvector_cosine_similarity ?? 0.96}
                      </span>
                    </div>

                    <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/80 dark:border-slate-800 text-xs text-slate-700 dark:text-slate-300 whitespace-pre-wrap leading-relaxed font-sans">
                      {activeIncident.ai_copilot?.narrative_md}
                    </div>

                    {(activeIncident.ai_copilot?.past_tickets || []).length > 0 && (
                      <div className="space-y-2">
                        <div className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                          Similar Historical Incidents Retrieved from Vector Memory
                        </div>
                        {activeIncident.ai_copilot.past_tickets.map((pt) => (
                          <div
                            key={pt.ticket_id}
                            className="p-3 rounded-xl border border-slate-200/80 dark:border-slate-800 text-xs space-y-1"
                          >
                            <div className="flex justify-between font-mono text-[11px] text-indigo-600 dark:text-indigo-400 font-semibold">
                              <span>{pt.ticket_id}</span>
                              <span>
                                {pt.date} · MTTR {pt.mttr_hours}h
                              </span>
                            </div>
                            <p className="text-slate-600 dark:text-slate-300">{pt.summary}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {copilotTab === 'actions' && (
                  <div className="space-y-3.5">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                        Human-Gated Northbound Actions
                      </span>
                      {activeIncident.status !== 'APPROVED_EXECUTED' ? (
                        <button
                          onClick={() => onApproveActions(activeIncident.incident_id)}
                          disabled={busy}
                          className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-semibold shadow-sm transition flex items-center gap-1.5"
                        >
                          <CheckCircle2 className="w-4 h-4" /> Approve & Execute All
                        </button>
                      ) : (
                        <span className="px-3 py-1 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 text-xs font-bold flex items-center gap-1">
                          <CheckCircle2 className="w-3.5 h-3.5" /> Executed Across Systems
                        </span>
                      )}
                    </div>

                    {(activeIncident.proposed_actions || []).map((act) => {
                      const execRec = (activeIncident.executed_actions || []).find(
                        (e) => e.action_id === act.action_id
                      );
                      return (
                        <div
                          key={act.action_id}
                          className="p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 space-y-2"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 text-[11px] font-semibold">
                              {act.target_system}
                            </span>
                            {execRec ? (
                              <span className="font-mono text-xs font-bold text-emerald-600 dark:text-emerald-400">
                                ✓ {execRec.result?.external_id || 'DONE'}
                              </span>
                            ) : (
                              <button
                                onClick={() =>
                                  onApproveActions(activeIncident.incident_id, [act.action_id])
                                }
                                className="px-2.5 py-1 rounded-lg bg-slate-900 hover:bg-slate-700 dark:bg-slate-100 dark:hover:bg-white text-white dark:text-slate-900 text-xs font-semibold transition"
                              >
                                Approve & Run
                              </button>
                            )}
                          </div>
                          <div className="text-xs font-bold text-slate-900 dark:text-white">
                            {act.title}
                          </div>
                          <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                            {act.description}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
};
