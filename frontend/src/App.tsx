import React, { useEffect, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  BatteryCharging,
  CheckCircle2,
  CloudRain,
  Cpu,
  Database,
  FileCode2,
  GitBranch,
  Globe,
  KeyRound,
  Layers,
  MapPin,
  Moon,
  Network,
  Play,
  PlugZap,
  Radio,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Sun,
  Terminal,
  TicketCheck,
  Waves,
  Wrench,
  Zap,
} from 'lucide-react';
import { OspMap } from './components/OspMap';
import { OtdrTracePanel } from './components/OtdrTracePanel';
import { MultiLayerGraph } from './components/MultiLayerGraph';

type PrimaryNavId = 'workspace' | 'topology' | 'telemetry' | 'connectors';
type StageTabId = 'map' | 'otdr' | 'graph' | 'stream';
type CopilotTabId = 'diagnosis' | 'runbook' | 'actions';

export const App: React.FC = () => {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem('noc_theme');
    return saved === 'dark' ? 'dark' : 'light';
  });

  const [overview, setOverview] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [busyAction, setBusyAction] = useState<string | null>(null);

  const [primaryNav, setPrimaryNav] = useState<PrimaryNavId>('workspace');
  const [stageTab, setStageTab] = useState<StageTabId>('map');
  const [copilotTab, setCopilotTab] = useState<CopilotTabId>('diagnosis');

  const [selectedProfileId, setSelectedProfileId] = useState<string>('du_converged');
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('szr_canal_fibre_cut');
  const [selectedCableId, setSelectedCableId] = useState<string | null>(null);
  const [inspectedOtdr, setInspectedOtdr] = useState<any | null>(null);

  // 3GPP XML Preview & Storm Benchmark state
  const [xmlPreview, setXmlPreview] = useState<string | null>(null);
  const [benchmarkResult, setBenchmarkResult] = useState<any | null>(null);

  // LLM API Key Modal State
  const [showLlmModal, setShowLlmModal] = useState<boolean>(false);
  const [llmProvider, setLlmProvider] = useState<string>('anthropic');
  const [llmModel, setLlmModel] = useState<string>('claude-sonnet-4-20250514');
  const [llmApiKey, setLlmApiKey] = useState<string>('');

  // Connector Editor Modal State
  const [editingConnector, setEditingConnector] = useState<any | null>(null);
  const [editEndpointUrl, setEditEndpointUrl] = useState<string>('');
  const [editMode, setEditMode] = useState<string>('emulator');

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    localStorage.setItem('noc_theme', theme);
  }, [theme]);

  const fetchOverview = async () => {
    try {
      const r = await fetch('/api/v1/overview');
      if (r.ok) {
        const data = await r.json();
        setOverview(data);
        if (data.last_benchmark && !benchmarkResult) {
          setBenchmarkResult(data.last_benchmark);
        }
      }
    } catch (e) {
      console.error('Failed to load overview:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOverview();
  }, []);

  const activeIncident = overview?.incidents?.[0] || null;
  const profiles = overview?.operator_profiles || {};
  const activeProfile = profiles[selectedProfileId] || Object.values(profiles)[0] || {};
  const scenarios: any[] = overview?.scenarios || [];

  const handleTriggerScenario = async (scenarioId?: string) => {
    const sid = scenarioId || selectedScenarioId;
    setBusyAction(`Simulating ${sid}...`);
    try {
      const r = await fetch('/api/v1/faults/trigger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: sid }),
      });
      if (r.ok) {
        await fetchOverview();
        setInspectedOtdr(null);
        setPrimaryNav('workspace');
        setCopilotTab('diagnosis');
      }
    } finally {
      setBusyAction(null);
    }
  };

  const handleTriggerCutOnCable = async (cableId: string, cutRatio: number) => {
    setBusyAction(`Cutting ${cableId} at ${Math.round(cutRatio * 100)}%...`);
    try {
      const r = await fetch('/api/v1/faults/trigger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          fault_type: 'fibre_cut',
          target_id: cableId,
          cut_ratio: cutRatio,
        }),
      });
      if (r.ok) {
        await fetchOverview();
        setInspectedOtdr(null);
      }
    } finally {
      setBusyAction(null);
    }
  };

  const handleResetNetwork = async () => {
    setBusyAction('Resetting network state...');
    try {
      await fetch('/api/v1/faults/reset', { method: 'POST' });
      setInspectedOtdr(null);
      setSelectedCableId(null);
      await fetchOverview();
    } finally {
      setBusyAction(null);
    }
  };

  const handleSelectCable = async (cableId: string) => {
    setSelectedCableId(cableId);
    try {
      const r = await fetch(`/api/v1/otdr/cable/${cableId}`);
      if (r.ok) {
        const data = await r.json();
        setInspectedOtdr(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleUploadSorFile = async (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    setBusyAction(`Parsing SR-4731 ${file.name}...`);
    try {
      const r = await fetch('/api/v1/otdr/parse-sor', { method: 'POST', body: fd });
      if (r.ok) {
        const data = await r.json();
        setInspectedOtdr(data);
        setStageTab('otdr');
      }
    } finally {
      setBusyAction(null);
    }
  };

  const handleApproveActions = async (incidentId: string, actionIds?: string[]) => {
    setBusyAction('Executing approved remediation actions...');
    try {
      const r = await fetch(`/api/v1/incidents/${incidentId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          approved_by: 'Lead NOC Engineer',
          action_ids: actionIds || null,
        }),
      });
      if (r.ok) {
        await fetchOverview();
      }
    } finally {
      setBusyAction(null);
    }
  };

  const handleRunStormBenchmark = async (stormSize: number = 10000) => {
    setBusyAction(`Running ${stormSize.toLocaleString()}-alarm storm benchmark...`);
    try {
      const r = await fetch('/api/v1/benchmark/storm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ storm_size: stormSize }),
      });
      if (r.ok) {
        const data = await r.json();
        setBenchmarkResult(data);
      }
    } finally {
      setBusyAction(null);
    }
  };

  const handleFetch3gppXml = async () => {
    if (xmlPreview) {
      setXmlPreview(null);
      return;
    }
    setBusyAction('Fetching 3GPP TS 32.435 XML PM counters...');
    try {
      const r = await fetch('/api/v1/telemetry/3gpp-xml');
      if (r.ok) {
        const data = await r.json();
        setXmlPreview(data.xml || '');
      }
    } finally {
      setBusyAction(null);
    }
  };

  const handleSaveLlmSettings = async () => {
    setBusyAction('Updating AI model settings...');
    try {
      await fetch('/api/v1/settings/llm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: llmProvider,
          model: llmModel,
          api_key: llmApiKey,
        }),
      });
      if (activeIncident) {
        await fetch(`/api/v1/incidents/${activeIncident.incident_id}/regenerate-ai`, {
          method: 'POST',
        });
      }
      setShowLlmModal(false);
      await fetchOverview();
    } finally {
      setBusyAction(null);
    }
  };

  const handleSaveConnector = async () => {
    if (!editingConnector) return;
    setBusyAction(`Updating ${editingConnector.name}...`);
    try {
      await fetch(`/api/v1/connectors/${editingConnector.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          endpoint_url: editEndpointUrl,
          mode: editMode,
          enabled: true,
          config_json: editingConnector.config_json || {},
        }),
      });
      setEditingConnector(null);
      await fetchOverview();
    } finally {
      setBusyAction(null);
    }
  };

  if (loading && !overview) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-[#0B0F17] text-slate-900 dark:text-slate-100 flex items-center justify-center">
        <div className="flex items-center gap-3 text-sm font-medium text-indigo-600 dark:text-indigo-400">
          <RefreshCw className="w-5 h-5 animate-spin" />
          <span>Synchronizing 12 Telco OEM Connectors & PostGIS Digital Twin...</span>
        </div>
      </div>
    );
  }

  const displayedOtdr =
    inspectedOtdr ||
    (activeIncident?.otdr_trace && Object.keys(activeIncident.otdr_trace).length > 0
      ? activeIncident.otdr_trace
      : null);

  const displayedFaultLoc =
    inspectedOtdr?.postgis_localization || activeIncident?.fault_location || null;

  const totalAlarms = overview?.alarms?.length || 0;
  const totalSlaExposure = activeIncident?.impact?.four_hour_sla_exposure_aed || 0;
  const srlgViolations = (overview?.srlg_findings || []).filter((s: any) => !s.diversity_compliant);
  const ranSitesPm: any[] = overview?.ran_telemetry?.pm_telemetry || [];
  const subseaSystems: any[] = overview?.ran_telemetry?.subsea_systems || [];

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#0B0F17] text-slate-900 dark:text-slate-100 flex flex-col transition-colors duration-200">
      {/* ==================== CLEAN MODERN HEADER ==================== */}
      <header className="sticky top-0 z-30 bg-white/85 dark:bg-slate-900/85 backdrop-blur-md border-b border-slate-200/80 dark:border-slate-800/80 px-6 py-3">
        <div className="max-w-[1600px] mx-auto flex flex-wrap items-center justify-between gap-4">
          {/* Brand */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center text-white shadow-sm">
              <Network className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold tracking-tight text-indigo-600 dark:text-indigo-400">
                  PANDITA AI
                </span>
                <span className="text-slate-300 dark:text-slate-700">•</span>
                <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
                   Autonomous NOC & Fibre Assurance Copilot
                </span>
              </div>
              <h1 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
                Multi-Layer Fault Correlation, OTDR Physics & SRLG Resilience
              </h1>
            </div>
          </div>

          {/* Primary Navigation Pills */}
          <nav className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800/80 p-1 rounded-xl border border-slate-200/60 dark:border-slate-700/60">
            {[
              { id: 'workspace', label: 'Operations Workspace', icon: Layers },
              {
                id: 'topology',
                label: `Topology & SRLG (${srlgViolations.length})`,
                icon: GitBranch,
              },
              { id: 'telemetry', label: '5G RAN, Optical & Subsea', icon: Radio },
              { id: 'connectors', label: '12 OEMs & Storm Benchmark', icon: PlugZap },
            ].map((item) => {
              const Icon = item.icon;
              const isActive = primaryNav === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setPrimaryNav(item.id as PrimaryNavId)}
                  className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
                    isActive
                      ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-sm'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>

          {/* Right Controls: Operator Archetype + Theme Toggle + AI Key */}
          <div className="flex items-center gap-2.5">
            <div className="flex items-center gap-2 bg-slate-100 dark:bg-slate-800/90 border border-slate-200/70 dark:border-slate-700 rounded-xl px-3 py-1.5 text-xs">
              <Globe className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
              <select
                value={selectedProfileId}
                onChange={(e) => setSelectedProfileId(e.target.value)}
                className="bg-transparent text-slate-800 dark:text-slate-100 font-semibold focus:outline-none cursor-pointer"
              >
                {Object.values(profiles).map((p: any) => (
                  <option key={p.id} value={p.id} className="bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100">
                    {p.short_name}
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={() => setShowLlmModal(true)}
              className="px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200/70 dark:bg-slate-800 dark:hover:bg-slate-700 border border-slate-200/70 dark:border-slate-700 text-xs font-medium text-slate-700 dark:text-slate-200 flex items-center gap-1.5 transition"
              title="Configure Anthropic Claude or OpenAI API Key"
            >
              <KeyRound className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
              <span>{overview?.llm_config?.api_key_configured ? 'LLM Live' : 'AI Key'}</span>
            </button>

            <button
              onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
              className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200/70 dark:bg-slate-800 dark:hover:bg-slate-700 border border-slate-200/70 dark:border-slate-700 text-slate-700 dark:text-slate-200 transition"
              title={`Switch to ${theme === 'light' ? 'Dark' : 'Light'} Mode`}
            >
              {theme === 'light' ? (
                <Moon className="w-4 h-4 text-slate-700" />
              ) : (
                <Sun className="w-4 h-4 text-amber-400" />
              )}
            </button>
          </div>
        </div>
      </header>

      {/* ==================== MAIN CONTENT CONTAINER ==================== */}
      <main className="flex-1 max-w-[1600px] w-full mx-auto px-6 py-5 space-y-5">
        {/* Busy Status Banner */}
        {busyAction && (
          <div className="bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-200 dark:border-indigo-800 rounded-xl px-4 py-2.5 flex items-center gap-2.5 text-xs font-medium text-indigo-700 dark:text-indigo-300">
            <RefreshCw className="w-4 h-4 animate-spin" />
            <span>{busyAction}</span>
          </div>
        )}

        {/* ==================== VIEW 1: OPERATIONS WORKSPACE ==================== */}
        {primaryNav === 'workspace' && (
          <>
            {/* Scenario Bar + 4 Clean Summary KPIs */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-4 shadow-sm flex flex-wrap items-center justify-between gap-4">
              {/* Left: Scenario Injector */}
              <div className="flex flex-wrap items-center gap-2.5">
                <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                  <Zap className="w-4 h-4 text-rose-500" /> Fault Scenario:
                </span>
                <select
                  value={selectedScenarioId}
                  onChange={(e) => setSelectedScenarioId(e.target.value)}
                  className="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 text-xs font-medium text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 min-w-[300px]"
                >
                  {scenarios.map((s: any) => (
                    <option key={s.id} value={s.id}>
                      {s.title}
                    </option>
                  ))}
                </select>
                <button
                  onClick={() => handleTriggerScenario()}
                  disabled={!!busyAction}
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm transition"
                >
                  <Play className="w-3.5 h-3.5 fill-current" /> Simulate Fault
                </button>
                <button
                  onClick={handleResetNetwork}
                  disabled={!!busyAction}
                  className="px-3 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-medium flex items-center gap-1.5 transition"
                >
                  <RotateCcw className="w-3.5 h-3.5" /> Reset
                </button>
              </div>

              {/* Right: 4 Crisp KPI Pills */}
              <div className="flex flex-wrap items-center gap-6">
                <div>
                  <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
                    Noise Compression
                  </div>
                  <div className="text-sm font-bold font-mono text-slate-900 dark:text-white">
                    {activeIncident ? `${totalAlarms} Alarms → 1 Root Cause` : '0 Active Faults'}
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
                    {srlgViolations.length} Detected
                  </div>
                </div>
              </div>
            </div>

            {/* Spacious 2-Column Workspace: Stage (7 cols) + Copilot Drawer (5 cols) */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
              {/* LEFT / CENTER STAGE (7 columns) */}
              <div className="lg:col-span-7 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl shadow-sm overflow-hidden flex flex-col">
                {/* Stage Sub-Navigation Header */}
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
                          onClick={() => setStageTab(st.id as StageTabId)}
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

                {/* Stage Body */}
                <div className="p-4">
                  {stageTab === 'map' && (
                    <div className="space-y-4">
                      <div className="h-[500px] w-full">
                        <OspMap
                          gis={overview?.gis || { ducts: [], manholes: [], cables: [] }}
                          topology={overview?.topology || {}}
                          activeIncident={activeIncident}
                          activeProfile={activeProfile}
                          selectedCableId={selectedCableId}
                          theme={theme}
                          onSelectCable={(cid) => {
                            handleSelectCable(cid);
                          }}
                          onTriggerCutOnCable={handleTriggerCutOnCable}
                        />
                      </div>
                      {/* Compact OTDR bar below map when a trace is active */}
                      <OtdrTracePanel
                        trace={displayedOtdr}
                        faultLocation={displayedFaultLoc}
                        theme={theme}
                        onUploadSorFile={handleUploadSorFile}
                      />
                    </div>
                  )}

                  {stageTab === 'otdr' && (
                    <div className="space-y-4">
                      <OtdrTracePanel
                        trace={displayedOtdr}
                        faultLocation={displayedFaultLoc}
                        theme={theme}
                        onUploadSorFile={handleUploadSorFile}
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
                              {displayedOtdr.key_events.map((ev: any) => (
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
                                    {ev.refl_db} dB
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
                      graph={overview?.dependency_graph || { nodes: [], edges: [] }}
                      theme={theme}
                      onSelectCable={(cid) => {
                        handleSelectCable(cid);
                        setStageTab('otdr');
                      }}
                    />
                  )}

                  {stageTab === 'stream' && (
                    <div className="space-y-4">
                      <div className="max-h-[460px] overflow-y-auto border border-slate-200/80 dark:border-slate-800 rounded-xl divide-y divide-slate-200/70 dark:divide-slate-800">
                        {(overview?.alarms || []).length === 0 ? (
                          <div className="p-8 text-center text-sm text-slate-500">
                            No active alarms. Select a fault scenario above and click <strong>Simulate Fault</strong>.
                          </div>
                        ) : (
                          (overview?.alarms || []).map((alm: any) => (
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
                                  <span className="text-xs font-mono text-slate-500">
                                    [{alm.protocol}]
                                  </span>
                                </div>
                                <span className="font-mono text-[11px] text-slate-400">
                                  {alm.alarm_id}
                                </span>
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

                      {/* Wire-Level UDP Syslog / SNMP / Kafka Packets */}
                      {(overview?.wire_packets || []).length > 0 && (
                        <div className="border border-slate-200/80 dark:border-slate-800 rounded-xl p-3.5 bg-slate-50 dark:bg-slate-950">
                          <div className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-2">
                            Live Wire Listeners (UDP Syslog :15514 · SNMPv2c Trap :15162 · Redpanda Kafka :19092)
                          </div>
                          <div className="space-y-1.5 max-h-40 overflow-y-auto font-mono text-[11px]">
                            {overview.wire_packets.map((pkt: any, i: number) => (
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

              {/* RIGHT: AI COPILOT & INCIDENT INVESTIGATION PANEL (5 columns) */}
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
                      12 OEM connectors are streaming healthy telemetry. Choose any of the 7 real-world telco fault scenarios above (or click any fibre cable on the map) to watch the Copilot isolate root cause in seconds.
                    </p>
                  </div>
                ) : (
                  <>
                    {/* Incident Header */}
                    <div className="p-5 border-b border-slate-200/80 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/30">
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

                      {/* Copilot Inner Tabs */}
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
                            onClick={() => setCopilotTab(ct.id as CopilotTabId)}
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

                    {/* Copilot Tab Content */}
                    <div className="p-5 space-y-4 max-h-[640px] overflow-y-auto">
                      {copilotTab === 'diagnosis' && (
                        <>
                          {/* Root Cause Summary Box */}
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

                          {/* SRLG Violation Alert if present */}
                          {(activeIncident.srlg_findings || []).map((srlg: any) => (
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

                          {/* Impacted Enterprise Customer SLAs */}
                          <div className="space-y-2.5">
                            <div className="flex items-center justify-between text-xs font-semibold text-slate-700 dark:text-slate-300">
                              <span>
                                Impacted Enterprise SLAs ({activeIncident.impact?.impacted_service_count || 0})
                              </span>
                              <span className="font-mono text-rose-600 dark:text-rose-400">
                                AED {activeIncident.impact?.total_sla_penalty_per_hour_aed?.toLocaleString() || 0}/hr risk
                              </span>
                            </div>
                            {(activeIncident.impact?.impacted_services || []).map((svc: any) => (
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
                          {/* pgvector Semantic Match Badge */}
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

                          {/* MOP Narrative */}
                          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/80 dark:border-slate-800 text-xs text-slate-700 dark:text-slate-300 whitespace-pre-wrap leading-relaxed font-sans">
                            {activeIncident.ai_copilot?.narrative_md}
                          </div>

                          {/* Past Resolved Tickets */}
                          {(activeIncident.ai_copilot?.past_tickets || []).length > 0 && (
                            <div className="space-y-2">
                              <div className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                Similar Historical Incidents Retrieved from Vector Memory
                              </div>
                              {activeIncident.ai_copilot.past_tickets.map((pt: any) => (
                                <div
                                  key={pt.ticket_id}
                                  className="p-3 rounded-xl border border-slate-200/80 dark:border-slate-800 text-xs space-y-1"
                                >
                                  <div className="flex justify-between font-mono text-[11px] text-indigo-600 dark:text-indigo-400 font-semibold">
                                    <span>{pt.ticket_id}</span>
                                    <span>{pt.date} · MTTR {pt.mttr_hours}h</span>
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
                                onClick={() => handleApproveActions(activeIncident.incident_id)}
                                disabled={!!busyAction}
                                className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-sm transition flex items-center gap-1.5"
                              >
                                <CheckCircle2 className="w-4 h-4" /> Approve & Execute All
                              </button>
                            ) : (
                              <span className="px-3 py-1 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 text-xs font-bold flex items-center gap-1">
                                <CheckCircle2 className="w-3.5 h-3.5" /> Executed Across Systems
                              </span>
                            )}
                          </div>

                          {(activeIncident.proposed_actions || []).map((act: any) => {
                            const execRec = (activeIncident.executed_actions || []).find(
                              (e: any) => e.action_id === act.action_id
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
                                        handleApproveActions(activeIncident.incident_id, [act.action_id])
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
        )}

        {/* ==================== VIEW 2: TOPOLOGY & SRLG AUDIT ==================== */}
        {primaryNav === 'topology' && (
          <div className="space-y-6">
            <MultiLayerGraph
              graph={overview?.dependency_graph || { nodes: [], edges: [] }}
              theme={theme}
              onSelectCable={(cid) => {
                handleSelectCable(cid);
                setPrimaryNav('workspace');
                setStageTab('otdr');
              }}
            />

            {/* SRLG Diversity Audit Cards */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
              <div>
                <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                  Continuous Physical Route-Diversity (SRLG) Compliance Audit
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  Audits every dual-homed / 1+1 protected enterprise circuit in Comviva BSS against actual Lepton GIS duct & manhole chamber geometry.
                </p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {(overview?.srlg_findings || []).map((f: any) => (
                  <div
                    key={f.service_id}
                    className={`p-4 rounded-xl border ${
                      f.diversity_compliant
                        ? 'border-emerald-200 bg-emerald-50/40 dark:border-emerald-900 dark:bg-emerald-950/20'
                        : 'border-rose-200 bg-rose-50/50 dark:border-rose-900/80 dark:bg-rose-950/30'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-mono text-xs font-bold text-slate-900 dark:text-white">
                        {f.service_id} · {f.customer_name}
                      </span>
                      <span
                        className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold ${
                          f.diversity_compliant
                            ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200'
                            : 'bg-rose-100 text-rose-700 dark:bg-rose-900 dark:text-rose-200'
                        }`}
                      >
                        {f.diversity_compliant ? 'DIVERSITY COMPLIANT' : 'SRLG VIOLATION'}
                      </span>
                    </div>
                    <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
                      {f.risk_summary}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ==================== VIEW 3: 5G RAN, OPTICAL & SUBSEA TELEMETRY ==================== */}
        {primaryNav === 'telemetry' && (
          <div className="space-y-6">
            {/* 3GPP RAN & Site Power Cards */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                    3GPP TS 32.435 5G RAN Performance, Site Battery LVD & E-Band Microwave Telemetry
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Live telemetry from Ericsson ENM & Nokia NSP across gNodeB sectors, VRLA battery banks, and 80 GHz microwave backhaul.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleTriggerScenario('ran_site_battery_lvd_countdown')}
                    className="px-3 py-1.5 rounded-xl bg-amber-500/15 hover:bg-amber-500/25 text-amber-800 dark:text-amber-300 border border-amber-400/50 text-xs font-semibold flex items-center gap-1.5"
                  >
                    <BatteryCharging className="w-3.5 h-3.5" /> Simulate Battery LVD Countdown
                  </button>
                  <button
                    onClick={() => handleTriggerScenario('eband_microwave_rain_fade')}
                    className="px-3 py-1.5 rounded-xl bg-sky-500/15 hover:bg-sky-500/25 text-sky-800 dark:text-sky-300 border border-sky-400/50 text-xs font-semibold flex items-center gap-1.5"
                  >
                    <CloudRain className="w-3.5 h-3.5" /> Simulate 80GHz Rain Fade
                  </button>
                  <button
                    onClick={handleFetch3gppXml}
                    className="px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 text-xs font-semibold flex items-center gap-1.5"
                  >
                    <FileCode2 className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
                    <span>{xmlPreview ? 'Hide 3GPP XML' : 'Inspect 3GPP TS 32.435 XML'}</span>
                  </button>
                </div>
              </div>

              {xmlPreview && (
                <pre className="p-4 rounded-xl bg-slate-950 text-emerald-300 font-mono text-xs overflow-x-auto max-h-64">
                  {xmlPreview}
                </pre>
              )}

              <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
                {ranSitesPm.map((site: any) => {
                  const isCrit = site.operational_state !== 'ENABLED_NORMAL';
                  return (
                    <div
                      key={site.site_id}
                      className={`p-4 rounded-xl border space-y-2.5 ${
                        isCrit
                          ? 'border-rose-300 bg-rose-50/40 dark:border-rose-800 dark:bg-rose-950/30'
                          : 'border-slate-200/80 dark:border-slate-800 bg-slate-50/40 dark:bg-slate-800/30'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-bold text-indigo-600 dark:text-indigo-400">
                          {site.site_id}
                        </span>
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            isCrit
                              ? 'bg-rose-100 text-rose-700 dark:bg-rose-900 dark:text-rose-200'
                              : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                          }`}
                        >
                          {site.ac_mains_status === 'FAILED'
                            ? 'ON BATTERY'
                            : site.mw_rsl_dbm && site.mw_rsl_dbm < -55
                            ? 'RAIN FADE'
                            : 'NORMAL'}
                        </span>
                      </div>
                      <div className="text-xs font-semibold text-slate-900 dark:text-white truncate">
                        {site.name}
                      </div>
                      <div className="space-y-1 text-xs font-mono text-slate-600 dark:text-slate-400">
                        <div className="flex justify-between">
                          <span>DL PRB Load:</span>
                          <span className="font-semibold text-slate-900 dark:text-white">
                            {site.dl_prb_util_pct}%
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span>DC Bus / LVD:</span>
                          <span
                            className={`font-semibold ${
                              site.dc_bus_voltage_v < 46
                                ? 'text-rose-600 dark:text-rose-400 font-bold'
                                : 'text-emerald-600 dark:text-emerald-400'
                            }`}
                          >
                            {site.dc_bus_voltage_v}V / {site.lvd_disconnect_threshold_v}V
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span>Battery Reserve:</span>
                          <span className="font-semibold text-slate-900 dark:text-white">
                            {site.battery_remaining_mins} mins
                          </span>
                        </div>
                        {site.mw_link_id && (
                          <div className="pt-1 border-t border-slate-200 dark:border-slate-700 flex justify-between text-[11px]">
                            <span>80GHz RSL:</span>
                            <span className="font-semibold text-indigo-600 dark:text-indigo-400">
                              {site.mw_rsl_dbm} dBm ({site.mw_acm_modulation.split(' ')[0]})
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Subsea Wet-Plant PFE & C-OTDR Supervisor Card */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <Waves className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                  <div>
                    <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                      Subsea Cable Landing Station (Jebel Ali CLS) — PFE & Coherent OTDR Wet-Plant Supervisor
                    </h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Monitors Power Feed Equipment (PFE) high-voltage constant-current supply and submarine repeater spans.
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => handleTriggerScenario('pccw_subsea_shunt_fault')}
                  className="px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm"
                >
                  <Waves className="w-3.5 h-3.5" /> Simulate Subsea Repeater Shunt Fault
                </button>
              </div>

              {subseaSystems.map((sub: any) => (
                <div
                  key={sub.id}
                  className="p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 grid grid-cols-1 md:grid-cols-4 gap-4"
                >
                  <div>
                    <div className="text-xs text-slate-500">Subsea System</div>
                    <div className="text-sm font-bold font-mono text-slate-900 dark:text-white mt-0.5">
                      {sub.id}
                    </div>
                    <div className="text-xs text-slate-500 mt-0.5">{sub.name}</div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">PFE Line Voltage / Current</div>
                    <div
                      className={`text-sm font-bold font-mono mt-0.5 ${
                        sub.shunt_fault_detected
                          ? 'text-rose-600 dark:text-rose-400'
                          : 'text-emerald-600 dark:text-emerald-400'
                      }`}
                    >
                      +{sub.pfe_voltage_v} V @ {sub.pfe_current_ma} mA
                    </div>
                    <div className="text-xs font-mono text-slate-500 mt-0.5">
                      Earth Leakage: {sub.earth_leakage_ma} mA
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">Wet-Plant Repeaters</div>
                    <div className="text-sm font-bold font-mono text-slate-900 dark:text-white mt-0.5">
                      {sub.repeater_count} Repeaters ({sub.total_length_km} km)
                    </div>
                    <div className="text-xs text-slate-500 mt-0.5">Branching Unit: {sub.branching_unit}</div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">C-OTDR Fault Status</div>
                    <div className="text-sm font-bold font-mono text-slate-900 dark:text-white mt-0.5">
                      {sub.shunt_fault_detected
                        ? `SHUNT @ ${sub.cotdr_shunt_distance_km} km (${sub.water_depth_m}m depth)`
                        : 'All 28 Repeater Spans Nominal'}
                    </div>
                    {sub.fault_span && (
                      <div className="text-xs text-rose-600 dark:text-rose-400 font-semibold mt-0.5">
                        {sub.fault_span}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ==================== VIEW 4: 12 OEM CONNECTORS & 10K BENCHMARK ==================== */}
        {primaryNav === 'connectors' && (
          <div className="space-y-6">
            {/* Phase 7: 10,000-Alarm Storm Benchmark Card */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                    <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                      High-Throughput Alarm Storm Stress Test & Deduplication Benchmark
                    </h3>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Simulates a 10,000-alarm multi-vendor storm burst (BGP/BFD link flaps, duplicate SNMP traps, and child RAN/CPE cascades) to verify real-time noise suppression.
                  </p>
                </div>
                <button
                  onClick={() => handleRunStormBenchmark(10000)}
                  disabled={!!busyAction}
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-2 shadow-sm transition"
                >
                  <Zap className="w-4 h-4" /> Run 10,000-Alarm Storm Benchmark
                </button>
              </div>

              {benchmarkResult && (
                <div className="grid grid-cols-2 md:grid-cols-6 gap-3 pt-2">
                  <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/70 dark:border-slate-800">
                    <div className="text-[11px] text-slate-500">Raw Storm Ingested</div>
                    <div className="text-base font-bold font-mono text-slate-900 dark:text-white mt-0.5">
                      {benchmarkResult.storm_size.toLocaleString()} alarms
                    </div>
                  </div>
                  <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/70 dark:border-slate-800">
                    <div className="text-[11px] text-slate-500">Flaps Suppressed</div>
                    <div className="text-base font-bold font-mono text-amber-600 dark:text-amber-400 mt-0.5">
                      {benchmarkResult.flaps_suppressed.toLocaleString()}
                    </div>
                  </div>
                  <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/70 dark:border-slate-800">
                    <div className="text-[11px] text-slate-500">Duplicates Dropped</div>
                    <div className="text-base font-bold font-mono text-indigo-600 dark:text-indigo-400 mt-0.5">
                      {benchmarkResult.duplicates_dropped.toLocaleString()}
                    </div>
                  </div>
                  <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/70 dark:border-slate-800">
                    <div className="text-[11px] text-slate-500">Root Causes Isolated</div>
                    <div className="text-base font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-0.5">
                      {benchmarkResult.root_causes_identified} ({benchmarkResult.noise_reduction_pct}% reduction)
                    </div>
                  </div>
                  <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/70 dark:border-slate-800">
                    <div className="text-[11px] text-slate-500">Processing Latency</div>
                    <div className="text-base font-bold font-mono text-slate-900 dark:text-white mt-0.5">
                      {benchmarkResult.processing_latency_ms} ms
                    </div>
                  </div>
                  <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/70 dark:border-slate-800">
                    <div className="text-[11px] text-slate-500">Throughput</div>
                    <div className="text-base font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-0.5">
                      {benchmarkResult.throughput_alarms_per_sec.toLocaleString()}/sec
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* 12 OEM Connectors Grid */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                    12 Telco OSS / BSS / GIS / DWDM / OTDR / RAN / ITSM Connectors
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Click any connector to switch its endpoint between the local protocol-authentic emulator and a live customer instance.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {(overview?.connectors || []).map((c: any) => (
                  <div
                    key={c.id}
                    className="p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 hover:border-indigo-300 dark:hover:border-indigo-700 transition flex flex-col justify-between gap-3"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2 mb-1.5">
                        <span className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[10px] font-semibold text-slate-600 dark:text-slate-300">
                          {c.category}
                        </span>
                        <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300 text-[10px] font-mono font-semibold">
                          ● {c.status} ({c.latency_ms}ms)
                        </span>
                      </div>
                      <div className="text-sm font-bold text-slate-900 dark:text-white">
                        {c.name}
                      </div>
                      <div className="text-xs text-slate-500 mt-0.5">{c.protocol}</div>
                      <div className="text-[11px] font-mono text-slate-400 truncate mt-2">
                        {c.endpoint_url}
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-slate-800 text-xs">
                      <span className="text-slate-500 font-mono text-[11px]">
                        Mode: <strong className="text-slate-700 dark:text-slate-300">{c.mode}</strong>
                      </span>
                      <button
                        onClick={() => {
                          setEditingConnector(c);
                          setEditEndpointUrl(c.endpoint_url);
                          setEditMode(c.mode);
                        }}
                        className="text-indigo-600 dark:text-indigo-400 font-semibold hover:underline flex items-center gap-1"
                      >
                        <Wrench className="w-3 h-3" /> Configure
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>

      {/* ==================== MODAL: LLM API KEY CONFIGURATION ==================== */}
      {showLlmModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900 dark:text-white">
                Configure AI Copilot Model & API Key
              </h3>
              <button
                onClick={() => setShowLlmModal(false)}
                className="text-slate-400 hover:text-slate-600 text-sm"
              >
                ✕
              </button>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              All physical fault localization, OTDR binary parsing, and SRLG graph audits run deterministically. Provide an Anthropic or OpenAI key to enable live LLM narrative generation on top of the verified evidence bundle.
            </p>
            <div className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold mb-1">Provider</label>
                <select
                  value={llmProvider}
                  onChange={(e) => {
                    setLlmProvider(e.target.value);
                    setLlmModel(
                      e.target.value === 'anthropic' ? 'claude-sonnet-4-20250514' : 'gpt-4o'
                    );
                  }}
                  className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2"
                >
                  <option value="anthropic">Anthropic Claude</option>
                  <option value="openai">OpenAI GPT</option>
                </select>
              </div>
              <div>
                <label className="block font-semibold mb-1">Model Name</label>
                <input
                  type="text"
                  value={llmModel}
                  onChange={(e) => setLlmModel(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2 font-mono"
                />
              </div>
              <div>
                <label className="block font-semibold mb-1">API Key</label>
                <input
                  type="password"
                  placeholder="sk-ant-... or sk-..."
                  value={llmApiKey}
                  onChange={(e) => setLlmApiKey(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2 font-mono"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowLlmModal(false)}
                className="px-4 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-xs font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveLlmSettings}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold"
              >
                Save & Regenerate Brief
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ==================== MODAL: CONNECTOR ENDPOINT EDITOR ==================== */}
      {editingConnector && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-xl space-y-4">
            <h3 className="text-base font-bold text-slate-900 dark:text-white">
              Configure {editingConnector.name}
            </h3>
            <div className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold mb-1">Connection Mode</label>
                <select
                  value={editMode}
                  onChange={(e) => setEditMode(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2"
                >
                  <option value="emulator">Protocol-Authentic Local Emulator</option>
                  <option value="live">Live Customer Production / Lab Endpoint</option>
                </select>
              </div>
              <div>
                <label className="block font-semibold mb-1">Endpoint Base URL</label>
                <input
                  type="text"
                  value={editEndpointUrl}
                  onChange={(e) => setEditEndpointUrl(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2 font-mono"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setEditingConnector(null)}
                className="px-4 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-xs font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveConnector}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold"
              >
                Save & Sync Connector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
