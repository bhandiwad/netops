import React, { Suspense, lazy, useEffect, useRef, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronRight,
  Copy,
  ExternalLink,
  FlaskConical,
  GitBranch,
  MapPin,
  Play,
  RotateCcw,
  ShieldCheck,
  Terminal,
  Upload,
} from '../components/icons';
import { MultiLayerGraph } from '../components/MultiLayerGraph';
import { OtdrTracePanel } from '../components/OtdrTracePanel';

const LazyOspMap = lazy(() =>
  import('../components/OspMap').then((m) => ({ default: m.OspMap }))
);
import type {
  FaultLocation,
  FaultScenario,
  Incident,
  OperatorProfile,
  OtdrTraceData,
  OverviewResponse,
  SrlgFinding,
  StageTabId,
  ThemeMode,
} from '../types/api';

function formatSharedRisk(srlg: SrlgFinding): string {
  const parts: string[] = [];
  if (srlg.shared_bridges?.length) parts.push(srlg.shared_bridges.join(', '));
  if (srlg.shared_ducts?.length) {
    parts.push(
      srlg.shared_ducts.length === 1
        ? `duct ${srlg.shared_ducts[0]}`
        : `${srlg.shared_ducts.length} ducts`
    );
  }
  if (srlg.shared_chambers?.length) {
    parts.push(
      srlg.shared_chambers.length === 1
        ? `chamber ${srlg.shared_chambers[0]}`
        : `${srlg.shared_chambers.length} chambers`
    );
  }
  if (parts.length > 0) {
    return `Primary and backup routes share ${parts.join(', ')}.`;
  }
  return srlg.risk_summary;
}

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
  selectedCableId: string | null;
  displayedOtdr: OtdrTraceData | null;
  displayedFaultLoc: FaultLocation | null;
  srlgViolationCount: number;
  theme: ThemeMode;
  busy: boolean;
  onTriggerScenario: (scenarioId?: string) => void;
  onResetNetwork: () => void;
  onSelectCable: (cableId: string) => void;
  onClearCable: () => void;
  onTriggerCutOnCable: (cableId: string, cutRatio: number) => void;
  onUploadSorFile: (file: File) => void;
  onOpenImportModal: () => void;
  onApproveActions: (incidentId: string, actionIds?: string[]) => void;
  onOpenRouteDiversity: () => void;
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
  selectedCableId,
  displayedOtdr,
  displayedFaultLoc,
  srlgViolationCount,
  theme,
  busy,
  onTriggerScenario,
  onResetNetwork,
  onSelectCable,
  onClearCable,
  onTriggerCutOnCable,
  onUploadSorFile,
  onOpenImportModal,
  onApproveActions,
  onOpenRouteDiversity,
}) => {
  const [alarmStreamMode, setAlarmStreamMode] = useState<'actionable' | 'suppressed'>('actionable');
  const [copiedWhatsApp, setCopiedWhatsApp] = useState<boolean>(false);
  const [cascadeStep, setCascadeStep] = useState<number>(3);
  const inlineSorRef = useRef<HTMLInputElement | null>(null);

  const totalAlarms = overview.alarms?.length || 0;
  const suppressedNoise = overview.background_noise;
  const suppressedTotal = suppressedNoise?.suppressed_total ?? 38;
  const hourlySlaRisk = activeIncident?.impact?.total_sla_penalty_per_hour_aed || 0;
  const currency =
    activeIncident?.impact?.currency ||
    (activeProfile as OperatorProfile)?.currency ||
    overview.currency ||
    'AED';

  useEffect(() => {
    if (!activeIncident?.incident_id) {
      setCascadeStep(3);
      return;
    }
    setCascadeStep(1);
    const t1 = window.setTimeout(() => setCascadeStep(2), 360);
    const t2 = window.setTimeout(() => setCascadeStep(3), 760);
    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
    };
  }, [activeIncident?.incident_id]);

  const handleCopyWhatsApp = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedWhatsApp(true);
      window.setTimeout(() => setCopiedWhatsApp(false), 2200);
    } catch {
      setCopiedWhatsApp(false);
    }
  };

  const roundedSavedM =
    displayedFaultLoc?.rounded_error_avoided_m ??
    (displayedFaultLoc?.dispatch_error_avoided_m
      ? Math.round(displayedFaultLoc.dispatch_error_avoided_m)
      : 0);
  const radM = displayedFaultLoc?.confidence_radius_m ?? 20;
  const protectionSummary = activeIncident?.impact?.protection_summary;
  const fl = activeIncident?.fault_location;
  const tiaPlan = fl?.tia598_splice_plan;

  return (
    <div className="space-y-4">
      {/* Operational NOC Posture Bar + Subtle Lab Replay / Data Import Controls */}
      <div className="bg-white dark:bg-[#111622] border border-slate-200/80 dark:border-slate-800/80 rounded-2xl px-4 py-3 flex flex-wrap items-center justify-between gap-4">
        {/* Live Operational Posture */}
        <div className="flex flex-wrap items-center gap-4 text-xs">
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                incidents.length > 0 ? 'bg-rose-500' : 'bg-emerald-500'
              }`}
            />
            <span className="font-semibold text-slate-900 dark:text-white">
              {incidents.length > 0
                ? `${totalAlarms} alarms → ${incidents.length} root cause${incidents.length > 1 ? 's' : ''}`
                : '0 P1/P2 Incidents'}
            </span>
            <button
              onClick={() => {
                setAlarmStreamMode('suppressed');
                onSelectStageTab('stream');
              }}
              className="px-2 py-0.5 rounded-full bg-slate-100 hover:bg-slate-200/80 dark:bg-slate-800/90 dark:hover:bg-slate-800 text-[11px] text-slate-600 dark:text-slate-300 transition"
              title="Inspect muted maintenance windows and dampened minor transceivers"
            >
              {suppressedTotal} minor/CRQ suppressed
            </button>
          </div>

          <div className="hidden sm:block h-4 w-px bg-slate-200 dark:bg-slate-800" />

          <div className="flex items-center gap-1.5">
            <span className="text-slate-500 dark:text-slate-400">Dig zone</span>
            <span className="font-mono font-semibold text-emerald-600 dark:text-emerald-400">
              {roundedSavedM > 0
                ? `±${radM} m (~${roundedSavedM} m saved)`
                : displayedFaultLoc?.dying_gasp_confirmed
                ? 'Trip saved'
                : '—'}
            </span>
          </div>

          <div className="hidden sm:block h-4 w-px bg-slate-200 dark:bg-slate-800" />

          <div className="flex items-center gap-1.5">
            <span className="text-slate-500 dark:text-slate-400">SLA exposure</span>
            <span
              className={`font-mono font-semibold ${
                hourlySlaRisk > 0
                  ? 'text-rose-600 dark:text-rose-400'
                  : 'text-slate-700 dark:text-slate-300'
              }`}
            >
              {currency} {hourlySlaRisk.toLocaleString()}/hr
            </span>
          </div>

          {srlgViolationCount > 0 && (
            <>
              <div className="hidden sm:block h-4 w-px bg-slate-200 dark:bg-slate-800" />
              <button
                onClick={onOpenRouteDiversity}
                className="flex items-center gap-1 text-amber-700 dark:text-amber-400 hover:underline font-medium"
              >
                <span>{srlgViolationCount} shared-duct risks</span>
                <ArrowRight className="w-3 h-3" />
              </button>
            </>
          )}
        </div>

        {/* Right Controls: Bring Your Own Data + Compact Lab Replay */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={onOpenImportModal}
            disabled={busy}
            className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/80 text-slate-700 dark:text-slate-200 text-xs font-medium flex items-center gap-1.5 transition"
            title="Import Google Earth .kml route, handheld .sor trace, or EMS alarm .csv"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Import KML / .sor / CSV</span>
          </button>

          <div className="flex items-center gap-1.5 bg-slate-50 dark:bg-slate-900/90 border border-slate-200/90 dark:border-slate-800 rounded-xl p-1">
            <span className="hidden xl:inline-flex items-center gap-1 pl-2 pr-1 text-[11px] font-medium text-slate-500 dark:text-slate-400">
              <FlaskConical className="w-3 h-3" />
              <span>Lab Replay</span>
            </span>
            <select
              value={selectedScenarioId}
              onChange={(e) => onSelectScenarioId(e.target.value)}
              aria-label="Select fault replay scenario"
              className="bg-white dark:bg-[#111622] border border-slate-200/80 dark:border-slate-800 rounded-lg px-2.5 py-1 text-xs font-medium text-slate-800 dark:text-slate-100 focus:outline-none max-w-[240px] truncate"
            >
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.title}
                </option>
              ))}
            </select>
            <button
              onClick={() => {
                setAlarmStreamMode('actionable');
                onTriggerScenario();
              }}
              disabled={busy}
              className="px-2.5 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 dark:bg-white dark:hover:bg-slate-100 disabled:opacity-50 text-white dark:text-slate-900 text-xs font-medium flex items-center gap-1 transition"
            >
              <Play className="w-3 h-3 fill-current" /> Replay
            </button>
            {(incidents.length > 0 || selectedCableId) && (
              <button
                onClick={onResetNetwork}
                disabled={busy}
                className="px-2 py-1 rounded-lg hover:bg-slate-200/70 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 text-xs font-medium flex items-center gap-1 transition"
                title="Clear active replay state"
              >
                <RotateCcw className="w-3 h-3" /> Reset
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Asynchronous Multi-Layer Telemetry Arrival Strip when Incident is Active */}
      {activeIncident && (
        <div className="bg-white/90 dark:bg-[#111622]/90 border border-slate-200/70 dark:border-slate-800/80 rounded-xl px-4 py-2 flex flex-wrap items-center justify-between gap-3 text-[11px]">
          <div className="flex flex-wrap items-center gap-2 text-slate-600 dark:text-slate-300">
            <span className="font-semibold text-slate-800 dark:text-slate-200">
              Telemetry Arrival Cascade:
            </span>
            <span
              className={`px-2 py-0.5 rounded-md font-mono transition-opacity duration-300 ${
                cascadeStep >= 1
                  ? 'bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 opacity-100'
                  : 'opacity-30'
              }`}
            >
              t+0ms · L1 Optical/OTDR
            </span>
            <span className="text-slate-400">→</span>
            <span
              className={`px-2 py-0.5 rounded-md font-mono transition-opacity duration-300 ${
                cascadeStep >= 2
                  ? 'bg-amber-50 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 opacity-100'
                  : 'opacity-25'
              }`}
            >
              t+180ms · L3 BFD/BGP Hold-down
            </span>
            <span className="text-slate-400">→</span>
            <span
              className={`px-2 py-0.5 rounded-md font-mono transition-opacity duration-300 ${
                cascadeStep >= 3
                  ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300 opacity-100'
                  : 'opacity-25'
              }`}
            >
              t+1.2s · L4 5G SCTP &amp; SLA Circuits
            </span>
          </div>
          <span className="font-medium text-emerald-700 dark:text-emerald-400">
            Collapsed {activeIncident.alarm_count} multi-vendor events → 1 root cause
          </span>
        </div>
      )}

      {/* Main 2-Column Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* LEFT STAGE (7 cols) */}
        <div className="lg:col-span-7 bg-white dark:bg-[#111622] border border-slate-200/80 dark:border-slate-800/80 rounded-2xl overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-slate-200/70 dark:border-slate-800/80 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-1 bg-slate-100/80 dark:bg-slate-900 p-1 rounded-lg">
              {[
                { id: 'map', label: 'Map', icon: MapPin },
                { id: 'otdr', label: 'OTDR Trace', icon: Activity },
                { id: 'graph', label: 'Dependencies', icon: GitBranch },
                {
                  id: 'stream',
                  label: totalAlarms > 0 ? `Alarms (${totalAlarms})` : `Alarms (${suppressedTotal} muted)`,
                  icon: Terminal,
                },
              ].map((st) => {
                const Icon = st.icon;
                const active = stageTab === st.id;
                return (
                  <button
                    key={st.id}
                    onClick={() => onSelectStageTab(st.id as StageTabId)}
                    className={`px-3 py-1 rounded-md text-xs font-medium flex items-center gap-1.5 transition ${
                      active
                        ? 'bg-white dark:bg-[#111622] text-slate-900 dark:text-white shadow-sm'
                        : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    <span>{st.label}</span>
                  </button>
                );
              })}
            </div>

            <span className="text-[11px] text-slate-400 dark:text-slate-500">
              {selectedCableId ? selectedCableId : 'Click any cable to inspect'}
            </span>
          </div>

          <div className="p-4">
            {stageTab === 'map' && (
              <div className="space-y-3">
                <div className="h-[540px] w-full">
                  <Suspense
                    fallback={
                      <div className="w-full h-full rounded-xl border border-slate-200/80 dark:border-slate-800 bg-slate-100/80 dark:bg-slate-900/60 flex items-center justify-center text-xs text-slate-500">
                        Loading GIS map…
                      </div>
                    }
                  >
                    <LazyOspMap
                      regionId={overview.active_region}
                      mapCenter={overview.map_center}
                      mapZoom={overview.map_zoom}
                      gis={overview.gis || { ducts: [], manholes: [], cables: [] }}
                      topology={overview.topology || {}}
                      activeIncident={activeIncident}
                      activeProfile={activeProfile}
                      selectedCableId={selectedCableId}
                      theme={theme}
                      onSelectCable={onSelectCable}
                      onClearCable={onClearCable}
                      onTriggerCutOnCable={onTriggerCutOnCable}
                    />
                  </Suspense>
                </div>

                {/* Compact 1-line OTDR summary strip when a cable or fault trace exists */}
                {displayedOtdr && (
                  <div className="rounded-xl bg-slate-50 dark:bg-slate-900/70 border border-slate-200/70 dark:border-slate-800 px-3.5 py-2.5 flex flex-wrap items-center justify-between gap-2 text-xs">
                    <div className="flex flex-wrap items-center gap-2 text-slate-600 dark:text-slate-300">
                      <span className="font-mono font-semibold text-slate-900 dark:text-white">
                        {displayedOtdr.cable_id}
                      </span>
                      <span>·</span>
                      {displayedFaultLoc?.corrected_trench_distance_m !== undefined ? (
                        <span>
                          Glass{' '}
                          <strong className="font-mono">
                            ~{Math.round(displayedFaultLoc.optical_distance_m || 0).toLocaleString()} m
                          </strong>{' '}
                          → Dig corridor{' '}
                          <strong className="font-mono text-slate-900 dark:text-white">
                            ~{(
                              displayedFaultLoc.rounded_trench_distance_m ??
                              Math.round(displayedFaultLoc.corrected_trench_distance_m)
                            ).toLocaleString()}{' '}
                            m (±{displayedFaultLoc.confidence_radius_m ?? 20} m)
                          </strong>{' '}
                          <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                            (~{roundedSavedM} m slack offset removed)
                          </span>
                        </span>
                      ) : (
                        <span>
                          {displayedFaultLoc?.dying_gasp_confirmed
                            ? 'OTDR confirms fibre continuity is intact (power loss only)'
                            : 'Span healthy — zero reflective breaks'}
                        </span>
                      )}
                    </div>
                    <button
                      onClick={() => onSelectStageTab('otdr')}
                      className="text-slate-900 dark:text-white font-medium hover:underline flex items-center gap-1 shrink-0"
                    >
                      <span>Open OTDR trace</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
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

                {displayedOtdr?.key_events && displayedOtdr.key_events.length > 0 && (
                  <details className="group border border-slate-200/80 dark:border-slate-800 rounded-xl overflow-hidden">
                    <summary className="px-4 py-2.5 bg-slate-50/70 dark:bg-slate-900/60 cursor-pointer list-none flex items-center justify-between text-xs font-medium text-slate-700 dark:text-slate-300">
                      <span>Splice &amp; reflection landmarks ({displayedOtdr.key_events.length})</span>
                      <ChevronRight className="w-4 h-4 text-slate-400 transition-transform group-open:rotate-90" />
                    </summary>
                    <div className="overflow-x-auto border-t border-slate-200/70 dark:border-slate-800">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-50/40 dark:bg-slate-900/40 text-slate-500 dark:text-slate-400 border-b border-slate-200/70 dark:border-slate-800">
                          <tr>
                            <th className="py-2 px-4 font-medium">#</th>
                            <th className="py-2 px-4 font-medium">Optical Dist</th>
                            <th className="py-2 px-4 font-medium">Loss</th>
                            <th className="py-2 px-4 font-medium">Chamber / Event</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-200/60 dark:divide-slate-800 font-mono">
                          {displayedOtdr.key_events.map((ev) => (
                            <tr key={ev.event_number}>
                              <td className="py-2 px-4 text-slate-500">{ev.event_number}</td>
                              <td className="py-2 px-4 font-medium text-slate-900 dark:text-white">
                                ~{Math.round(ev.distance_m).toLocaleString()} m
                              </td>
                              <td
                                className={`py-2 px-4 ${
                                  ev.splice_loss_db > 5
                                    ? 'text-rose-600 dark:text-rose-400 font-semibold'
                                    : 'text-slate-600 dark:text-slate-300'
                                }`}
                              >
                                {ev.splice_loss_db} dB
                              </td>
                              <td className="py-2 px-4 font-sans text-slate-600 dark:text-slate-300">
                                {ev.comment}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </details>
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
              <div className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-1 bg-slate-100/90 dark:bg-slate-900 p-1 rounded-lg text-xs">
                    <button
                      onClick={() => setAlarmStreamMode('actionable')}
                      className={`px-3 py-1 rounded-md font-medium transition ${
                        alarmStreamMode === 'actionable'
                          ? 'bg-white dark:bg-[#111622] text-slate-900 dark:text-white shadow-sm'
                          : 'text-slate-500 dark:text-slate-400'
                      }`}
                    >
                      Actionable Alarms ({totalAlarms})
                    </button>
                    <button
                      onClick={() => setAlarmStreamMode('suppressed')}
                      className={`px-3 py-1 rounded-md font-medium transition ${
                        alarmStreamMode === 'suppressed'
                          ? 'bg-white dark:bg-[#111622] text-slate-900 dark:text-white shadow-sm'
                          : 'text-slate-500 dark:text-slate-400'
                      }`}
                    >
                      Suppressed Chaff &amp; CRQs ({suppressedTotal})
                    </button>
                  </div>

                  {alarmStreamMode === 'suppressed' && suppressedNoise && (
                    <span className="text-[11px] text-slate-500 dark:text-slate-400">
                      {suppressedNoise.planned_maintenance_crq} CRQ windows ·{' '}
                      {suppressedNoise.flapping_transceivers} SFP/port flaps ·{' '}
                      {suppressedNoise.transient_ran_warnings} transient RAN
                    </span>
                  )}
                </div>

                {alarmStreamMode === 'actionable' ? (
                  <div className="max-h-[470px] overflow-y-auto border border-slate-200/80 dark:border-slate-800 rounded-xl divide-y divide-slate-200/60 dark:divide-slate-800">
                    {(overview.alarms || []).length === 0 ? (
                      <div className="p-10 text-center space-y-1.5 text-xs text-slate-500">
                        <div className="font-medium text-slate-700 dark:text-slate-300">
                          Zero actionable service-affecting alarms
                        </div>
                        <div>
                          {suppressedTotal} chronic minor/flapping &amp; scheduled CRQ events are actively suppressed.
                        </div>
                      </div>
                    ) : (
                      overview.alarms.map((alm) => (
                        <div
                          key={alm.alarm_id}
                          className="px-4 py-3 hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <span
                                className={`w-2 h-2 rounded-full ${
                                  alm.severity === 'CRITICAL'
                                    ? 'bg-rose-500'
                                    : alm.severity === 'MAJOR'
                                    ? 'bg-amber-500'
                                    : 'bg-slate-400'
                                }`}
                              />
                              <span className="text-xs font-semibold text-slate-900 dark:text-white">
                                {alm.specific_problem}
                              </span>
                              <span className="font-mono text-[11px] text-slate-500">
                                {alm.resource_id}
                              </span>
                            </div>
                            <span className="text-[11px] text-slate-400">{alm.source_oem}</span>
                          </div>
                          <div className="text-xs text-slate-500 dark:text-slate-400 mt-1 pl-4">
                            {alm.raw_text}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                ) : (
                  <div className="max-h-[470px] overflow-y-auto border border-slate-200/80 dark:border-slate-800 rounded-xl divide-y divide-slate-200/60 dark:divide-slate-800">
                    {(suppressedNoise?.events || []).map((ev) => (
                      <div
                        key={ev.id}
                        className="px-4 py-3 bg-slate-50/40 dark:bg-slate-900/30 space-y-1"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="px-1.5 py-0.5 rounded bg-slate-200/80 dark:bg-slate-800 text-[10px] font-mono font-medium text-slate-600 dark:text-slate-300">
                              MUTED · {ev.category}
                            </span>
                            <span className="font-mono text-xs font-medium text-slate-800 dark:text-slate-200">
                              {ev.resource_id}
                            </span>
                          </div>
                          <span className="text-[11px] text-slate-400">{ev.source_oem}</span>
                        </div>
                        <div className="text-xs text-slate-600 dark:text-slate-300">{ev.reason}</div>
                        <div className="text-[11px] font-mono text-slate-400">{ev.raw_text}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* RIGHT INCIDENT BRIEF (5 cols — Single Calm Vertical Flow, Zero Nested Sub-Tabs) */}
        <div className="lg:col-span-5 bg-white dark:bg-[#111622] border border-slate-200/80 dark:border-slate-800/80 rounded-2xl overflow-hidden flex flex-col">
          {!activeIncident ? (
            <div className="p-8 text-center space-y-5">
              <div className="w-11 h-11 rounded-2xl bg-emerald-50 dark:bg-emerald-950/50 border border-emerald-200/70 dark:border-emerald-800/60 mx-auto flex items-center justify-center text-emerald-600 dark:text-emerald-400">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div className="space-y-1.5">
                <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                  0 Actionable P1/P2 Incidents
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 max-w-sm mx-auto leading-relaxed">
                  {suppressedTotal} background maintenance CRQs and minor transceiver flaps are muted. Import a field <code className="font-mono">.kml</code> / <code className="font-mono">.sor</code> / <code className="font-mono">.csv</code> file—or replay a reference fault below.
                </p>
              </div>

              {scenarios.length > 0 && (
                <div className="pt-2 space-y-2 max-w-sm mx-auto text-left">
                  <div className="text-[11px] font-medium text-slate-400 uppercase tracking-wider text-center">
                    Reference Fault Replays
                  </div>
                  {scenarios.slice(0, 3).map((sc) => (
                    <button
                      key={sc.id}
                      onClick={() => {
                        onSelectScenarioId(sc.id);
                        onTriggerScenario(sc.id);
                      }}
                      disabled={busy}
                      className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200/80 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 hover:bg-slate-50/70 dark:hover:bg-slate-800/40 text-left flex items-center justify-between gap-3 transition group"
                    >
                      <span className="text-xs font-medium text-slate-700 dark:text-slate-200 group-hover:text-slate-900 dark:group-hover:text-white">
                        {sc.title}
                      </span>
                      <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:translate-x-0.5 transition-transform shrink-0" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="divide-y divide-slate-200/70 dark:divide-slate-800/80">
              {/* Incident Header, Monitoring Source & Hardware Protection Posture */}
              <div className="p-5 space-y-3">
                {incidents.length > 1 && (
                  <div className="flex flex-wrap gap-1.5 pb-1">
                    {incidents.map((inc) => (
                      <button
                        key={inc.incident_id}
                        onClick={() => onSelectIncidentId(inc.incident_id)}
                        className={`px-2.5 py-1 rounded-md text-[11px] font-mono font-medium border transition ${
                          inc.incident_id === activeIncident.incident_id
                            ? 'bg-slate-900 text-white border-slate-900 dark:bg-white dark:text-slate-900 dark:border-white'
                            : 'text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-800'
                        }`}
                      >
                        {inc.incident_id} ({inc.alarm_count})
                      </button>
                    ))}
                  </div>
                )}

                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-rose-500" />
                    <span className="text-xs font-semibold text-rose-600 dark:text-rose-400">
                      {activeIncident.severity}
                    </span>
                    <span className="text-xs text-slate-400 font-mono">
                      {activeIncident.incident_id}
                    </span>
                    {fl?.monitoring_label && (
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                          fl.monitoring_mode === 'IN_SERVICE_RFTS_1625NM'
                            ? 'bg-sky-50 text-sky-700 dark:bg-sky-950/70 dark:text-sky-300'
                            : 'bg-amber-50 text-amber-800 dark:bg-amber-950/70 dark:text-amber-300'
                        }`}
                      >
                        {fl.monitoring_label}
                      </span>
                    )}
                  </div>
                  <span className="text-[11px] text-slate-500 dark:text-slate-400">
                    {Math.round(activeIncident.confidence * 100)}% confidence
                  </span>
                </div>

                <h2 className="text-base font-semibold text-slate-900 dark:text-white leading-snug">
                  {activeIncident.title}
                </h2>

                <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                  {activeIncident.root_cause_summary}
                </p>

                {/* Day-1 Hardware Protection Status Banner */}
                {protectionSummary && (
                  <div
                    className={`px-3 py-2.5 rounded-xl border text-xs space-y-0.5 ${
                      protectionSummary.state === 'PROTECTION_FAILED_SRLG' ||
                      protectionSummary.state === 'UNPROTECTED_OUTAGE'
                        ? 'bg-rose-50/70 dark:bg-rose-950/30 border-rose-200/80 dark:border-rose-900/60 text-rose-900 dark:text-rose-200'
                        : 'bg-sky-50/70 dark:bg-sky-950/30 border-sky-200/80 dark:border-sky-900/60 text-sky-900 dark:text-sky-200'
                    }`}
                  >
                    <div className="font-semibold">{protectionSummary.badge}</div>
                    <div className="text-[11px] opacity-90 leading-relaxed">
                      {protectionSummary.detail}
                    </div>
                  </div>
                )}

                {fl?.dispatch_verdict && (
                  <div className="px-3 py-2 rounded-lg bg-emerald-50/80 dark:bg-emerald-950/40 border border-emerald-200/70 dark:border-emerald-900/60 text-xs font-medium text-emerald-800 dark:text-emerald-300">
                    {fl.dispatch_verdict}
                  </div>
                )}
              </div>

              {/* Field Splicer & WhatsApp Dispatch Pack (for Physical OSP / Splice Incidents) */}
              {fl?.landmark_anchor && !fl.dying_gasp_confirmed && (
                <div className="p-5 space-y-3 bg-slate-50/40 dark:bg-slate-900/25">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-xs font-semibold text-slate-900 dark:text-white">
                      Field Splicer &amp; WhatsApp Dispatch Pack
                    </h3>
                    {tiaPlan && (
                      <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400">
                        Est. ETR ~{tiaPlan.est_total_etr_hours}h
                      </span>
                    )}
                  </div>

                  <div className="p-3 rounded-xl bg-white dark:bg-slate-900/80 border border-slate-200/80 dark:border-slate-800 text-xs space-y-2.5">
                    <div className="text-slate-700 dark:text-slate-200 leading-relaxed">
                      <span className="font-semibold text-slate-900 dark:text-white">
                        Dig Corridor:{' '}
                      </span>
                      {fl.landmark_anchor}
                    </div>

                    <div className="flex flex-wrap items-center gap-2 pt-0.5">
                      {fl.whatsapp_dispatch_text && (
                        <button
                          onClick={() => handleCopyWhatsApp(fl.whatsapp_dispatch_text!)}
                          className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium flex items-center gap-1.5 transition"
                        >
                          {copiedWhatsApp ? (
                            <>
                              <Check className="w-3.5 h-3.5" />
                              <span>Copied for WhatsApp</span>
                            </>
                          ) : (
                            <>
                              <Copy className="w-3.5 h-3.5" />
                              <span>Copy WhatsApp Dispatch</span>
                            </>
                          )}
                        </button>
                      )}

                      {fl.google_maps_url && (
                        <a
                          href={fl.google_maps_url}
                          target="_blank"
                          rel="noreferrer"
                          className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs font-medium flex items-center gap-1.5 transition"
                        >
                          <MapPin className="w-3.5 h-3.5 text-rose-500" />
                          <span>Google Maps Pin</span>
                          <ExternalLink className="w-3 h-3 text-slate-400" />
                        </a>
                      )}

                      {fl.monitoring_mode === 'HANDHELD_OTDR_SOR' && (
                        <>
                          <input
                            ref={inlineSorRef}
                            type="file"
                            accept=".sor"
                            className="hidden"
                            onChange={(e) => {
                              if (e.target.files?.[0]) onUploadSorFile(e.target.files[0]);
                            }}
                          />
                          <button
                            onClick={() => inlineSorRef.current?.click()}
                            className="px-2.5 py-1.5 rounded-lg border border-amber-300 dark:border-amber-800 text-amber-800 dark:text-amber-300 text-xs font-medium flex items-center gap-1 transition"
                          >
                            <Upload className="w-3 h-3" /> Upload Field .sor
                          </button>
                        </>
                      )}
                    </div>

                    {tiaPlan && (
                      <details className="group pt-1 border-t border-slate-200/70 dark:border-slate-800">
                        <summary className="cursor-pointer list-none flex items-center justify-between text-[11px] font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white pt-1.5">
                          <span>
                            {tiaPlan.standard} Tube &amp; Core Plan ({tiaPlan.fibre_count}F ·{' '}
                            {tiaPlan.tube_color_range})
                          </span>
                          <ChevronRight className="w-3.5 h-3.5 transition-transform group-open:rotate-90" />
                        </summary>
                        <div className="mt-2 space-y-1.5 text-[11px]">
                          <p className="text-emerald-700 dark:text-emerald-400 font-medium">
                            {tiaPlan.priority_instruction}
                          </p>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 pt-1">
                            {tiaPlan.tubes.map((tb) => (
                              <div
                                key={tb.tube_number}
                                className="px-2.5 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-950/70 border border-slate-200/60 dark:border-slate-800"
                              >
                                <div className="font-mono font-semibold text-slate-800 dark:text-slate-200">
                                  Tube {tb.tube_number} ({tb.tube_color}) · Cores {tb.core_range}
                                </div>
                                <div className="text-slate-500 dark:text-slate-400 truncate">
                                  {tb.allocation}
                                </div>
                              </div>
                            ))}
                          </div>
                          <div className="text-slate-500 dark:text-slate-400 pt-1">
                            Repair breakdown: ~{tiaPlan.est_excavation_hours}h civil pit access + ~
                            {tiaPlan.est_fusion_splice_hours}h fusion splicing ={' '}
                            <strong className="text-slate-700 dark:text-slate-200">
                              ~{tiaPlan.est_total_etr_hours}h ETR
                            </strong>
                          </div>
                        </div>
                      </details>
                    )}
                  </div>
                </div>
              )}

              {/* Recommended Actions (Immediately Visible) */}
              <div className="p-5 space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-xs font-semibold text-slate-900 dark:text-white">
                    Engineering &amp; ITSM Work Orders
                  </h3>
                  {activeIncident.status !== 'APPROVED_EXECUTED' ? (
                    <button
                      onClick={() => onApproveActions(activeIncident.incident_id)}
                      disabled={busy}
                      className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-medium transition flex items-center gap-1.5"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" /> Approve all
                    </button>
                  ) : (
                    <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> Executed
                    </span>
                  )}
                </div>

                <div className="space-y-2">
                  {(activeIncident.proposed_actions || []).map((act) => {
                    const execRec = (activeIncident.executed_actions || []).find(
                      (e) => e.action_id === act.action_id
                    );
                    return (
                      <div
                        key={act.action_id}
                        className="p-3 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/40 flex items-start justify-between gap-3"
                      >
                        <div className="space-y-0.5 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
                              {act.target_system}
                            </span>
                          </div>
                          <div className="text-xs font-semibold text-slate-900 dark:text-white">
                            {act.title}
                          </div>
                          <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                            {act.description}
                          </p>
                        </div>
                        <div className="shrink-0">
                          {execRec ? (
                            <span className="font-mono text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
                              ✓ {execRec.result?.external_id || 'Done'}
                            </span>
                          ) : (
                            <button
                              onClick={() =>
                                onApproveActions(activeIncident.incident_id, [act.action_id])
                              }
                              disabled={busy}
                              className="px-2.5 py-1 rounded-md border border-slate-200 dark:border-slate-700 hover:bg-white dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs font-medium transition"
                            >
                              Approve
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Affected Customers & Shared-Duct Alerts */}
              <div className="p-5 space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <h3 className="font-semibold text-slate-900 dark:text-white">
                    Affected Customers ({activeIncident.impact?.impacted_service_count || 0})
                  </h3>
                  {hourlySlaRisk > 0 && (
                    <span className="font-mono text-rose-600 dark:text-rose-400 font-medium">
                      {currency} {hourlySlaRisk.toLocaleString()}/hr
                    </span>
                  )}
                </div>

                {(activeIncident.srlg_findings || []).map((srlg) => (
                  <div
                    key={srlg.service_id}
                    className="p-3 rounded-xl bg-amber-50/80 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/60 flex items-start gap-2.5 text-xs"
                  >
                    <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                    <div className="text-amber-900 dark:text-amber-200 leading-relaxed">
                      <strong>{srlg.customer_name}:</strong> {formatSharedRisk(srlg)}
                    </div>
                  </div>
                ))}

                {(activeIncident.impact?.impacted_services || []).length === 0 ? (
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    No enterprise SLA circuits are experiencing a hard outage.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {(activeIncident.impact?.impacted_services || []).map((svc) => (
                      <div
                        key={svc.service_id}
                        className="px-3 py-2.5 rounded-xl border border-slate-200/70 dark:border-slate-800 flex items-center justify-between gap-3 text-xs"
                      >
                        <div>
                          <div className="font-medium text-slate-900 dark:text-white">
                            {svc.customer_name}
                          </div>
                          <div className="text-[11px] text-slate-500 mt-0.5">
                            {svc.bandwidth} {svc.service_type} · {svc.sla_tier}
                          </div>
                        </div>
                        <div className="text-right">
                          <span
                            className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${
                              svc.outage_state === 'COMPLETE_OUTAGE'
                                ? 'bg-rose-50 text-rose-700 dark:bg-rose-950/70 dark:text-rose-300'
                                : 'bg-amber-50 text-amber-700 dark:bg-amber-950/70 dark:text-amber-300'
                            }`}
                          >
                            {svc.outage_state === 'COMPLETE_OUTAGE' ? 'Outage' : 'Single-leg'}
                          </span>
                          <div className="font-mono text-[11px] text-slate-500 mt-0.5">
                            {currency} {svc.penalty_per_hour_aed.toLocaleString()}/hr
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Collapsible Engineering Runbook & History */}
              {activeIncident.ai_copilot && (
                <details className="group">
                  <summary className="px-5 py-3.5 cursor-pointer list-none flex items-center justify-between text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white">
                    <span>
                      Runbook &amp; engineering notes ({activeIncident.ai_copilot.matched_runbook_id})
                    </span>
                    <ChevronRight className="w-4 h-4 text-slate-400 transition-transform group-open:rotate-90" />
                  </summary>
                  <div className="px-5 pb-5 space-y-3 text-xs">
                    <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200/70 dark:border-slate-800 text-slate-600 dark:text-slate-300 whitespace-pre-wrap leading-relaxed">
                      {activeIncident.ai_copilot.narrative_md}
                    </div>

                    {(activeIncident.ai_copilot.past_tickets || []).length > 0 && (
                      <div className="space-y-1.5">
                        <div className="text-[11px] font-medium text-slate-500">
                          Similar past incidents
                        </div>
                        {activeIncident.ai_copilot.past_tickets.map((pt) => (
                          <div
                            key={pt.ticket_id}
                            className="p-2.5 rounded-lg border border-slate-200/70 dark:border-slate-800 text-slate-600 dark:text-slate-300"
                          >
                            <div className="flex justify-between font-mono text-[11px] text-slate-400 mb-0.5">
                              <span>{pt.ticket_id}</span>
                              <span>
                                {pt.date} · {pt.mttr_hours}h repair
                              </span>
                            </div>
                            <p>{pt.summary}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </details>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
