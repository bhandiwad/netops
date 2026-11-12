import React, { useEffect, useState } from 'react';
import {
  GitBranch,
  Globe,
  KeyRound,
  Layers,
  Moon,
  Network,
  PlugZap,
  Radio,
  RefreshCw,
  Sun,
} from 'lucide-react';
import { nocApi } from './api/client';
import { ConnectorEditorModal, LlmSettingsModal } from './components/ConfigModals';
import type {
  Connector,
  CopilotTabId,
  OtdrTraceData,
  OverviewResponse,
  PrimaryNavId,
  StageTabId,
  StormBenchmarkResult,
  ThemeMode,
} from './types/api';
import { ConnectorsView } from './views/ConnectorsView';
import { TelemetryView } from './views/TelemetryView';
import { TopologyView } from './views/TopologyView';
import { WorkspaceView } from './views/WorkspaceView';

export const App: React.FC = () => {
  const [theme, setTheme] = useState<ThemeMode>(() =>
    localStorage.getItem('noc_theme') === 'dark' ? 'dark' : 'light'
  );

  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [busyAction, setBusyAction] = useState<string | null>(null);

  const [primaryNav, setPrimaryNav] = useState<PrimaryNavId>('workspace');
  const [stageTab, setStageTab] = useState<StageTabId>('map');
  const [copilotTab, setCopilotTab] = useState<CopilotTabId>('diagnosis');

  const [selectedProfileId, setSelectedProfileId] = useState<string>('du_converged');
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('szr_canal_fibre_cut');
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(null);
  const [selectedCableId, setSelectedCableId] = useState<string | null>(null);
  const [inspectedOtdr, setInspectedOtdr] = useState<OtdrTraceData | null>(null);

  const [xmlPreview, setXmlPreview] = useState<string | null>(null);
  const [benchmarkResult, setBenchmarkResult] = useState<StormBenchmarkResult | null>(null);

  const [showLlmModal, setShowLlmModal] = useState<boolean>(false);
  const [llmProvider, setLlmProvider] = useState<string>('anthropic');
  const [llmModel, setLlmModel] = useState<string>('claude-sonnet-4-20250514');
  const [llmApiKey, setLlmApiKey] = useState<string>('');

  const [editingConnector, setEditingConnector] = useState<Connector | null>(null);
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

  const refreshOverview = async () => {
    try {
      const data = await nocApi.getOverview();
      setOverview(data);
      if (data.last_benchmark && !benchmarkResult) {
        setBenchmarkResult(data.last_benchmark);
      }
    } catch (e) {
      console.error('Failed to load overview:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshOverview();
  }, []);

  const incidents = overview?.incidents || [];
  const activeIncident =
    incidents.find((i) => i.incident_id === selectedIncidentId) || incidents[0] || null;

  const profiles = overview?.operator_profiles || {};
  const activeProfile = profiles[selectedProfileId] || Object.values(profiles)[0] || {};
  const scenarios = overview?.scenarios || [];

  const handleTriggerScenario = async (scenarioId?: string) => {
    const sid = scenarioId || selectedScenarioId;
    setBusyAction(`Simulating ${sid}...`);
    try {
      await nocApi.triggerScenario(sid);
      await refreshOverview();
      setSelectedIncidentId(null);
      setInspectedOtdr(null);
      setPrimaryNav('workspace');
      setCopilotTab('diagnosis');
    } finally {
      setBusyAction(null);
    }
  };

  const handleTriggerCutOnCable = async (cableId: string, cutRatio: number) => {
    setBusyAction(`Cutting ${cableId} at ${Math.round(cutRatio * 100)}%...`);
    try {
      await nocApi.triggerCableCut(cableId, cutRatio);
      await refreshOverview();
      setSelectedIncidentId(null);
      setInspectedOtdr(null);
    } finally {
      setBusyAction(null);
    }
  };

  const handleResetNetwork = async () => {
    setBusyAction('Resetting network state...');
    try {
      await nocApi.resetNetwork();
      setSelectedIncidentId(null);
      setInspectedOtdr(null);
      setSelectedCableId(null);
      await refreshOverview();
    } finally {
      setBusyAction(null);
    }
  };

  const handleSelectCable = async (cableId: string) => {
    setSelectedCableId(cableId);
    try {
      const data = await nocApi.getCableOtdr(cableId);
      setInspectedOtdr(data);
    } catch (e) {
      console.error(e);
    }
  };

  const handleUploadSorFile = async (file: File) => {
    setBusyAction(`Parsing SR-4731 ${file.name}...`);
    try {
      const data = await nocApi.parseUploadedSor(file);
      setInspectedOtdr(data);
      setStageTab('otdr');
    } finally {
      setBusyAction(null);
    }
  };

  const handleApproveActions = async (incidentId: string, actionIds?: string[]) => {
    setBusyAction('Executing approved remediation actions...');
    try {
      await nocApi.approveIncidentActions(incidentId, actionIds);
      await refreshOverview();
    } finally {
      setBusyAction(null);
    }
  };

  const handleRunStormBenchmark = async (stormSize: number = 10000) => {
    setBusyAction(`Running ${stormSize.toLocaleString()}-alarm storm benchmark...`);
    try {
      const data = await nocApi.runStormBenchmark(stormSize);
      setBenchmarkResult(data);
    } finally {
      setBusyAction(null);
    }
  };

  const handleToggle3gppXml = async () => {
    if (xmlPreview) {
      setXmlPreview(null);
      return;
    }
    setBusyAction('Fetching 3GPP TS 32.435 XML PM counters...');
    try {
      const xml = await nocApi.get3gppXml();
      setXmlPreview(xml);
    } finally {
      setBusyAction(null);
    }
  };

  const handleSaveLlmSettings = async () => {
    setBusyAction('Updating AI model settings...');
    try {
      await nocApi.updateLlmSettings(
        llmProvider,
        llmModel,
        llmApiKey,
        activeIncident?.incident_id
      );
      setShowLlmModal(false);
      await refreshOverview();
    } finally {
      setBusyAction(null);
    }
  };

  const handleSaveConnector = async () => {
    if (!editingConnector) return;
    setBusyAction(`Updating ${editingConnector.name}...`);
    try {
      await nocApi.updateConnector(editingConnector, editEndpointUrl, editMode);
      setEditingConnector(null);
      await refreshOverview();
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

  if (!overview) return null;

  const activeOtdr =
    activeIncident?.otdr_trace && 'cable_id' in activeIncident.otdr_trace
      ? (activeIncident.otdr_trace as OtdrTraceData)
      : null;
  const displayedOtdr = inspectedOtdr || activeOtdr;
  const displayedFaultLoc =
    inspectedOtdr?.postgis_localization || activeIncident?.fault_location || null;

  const srlgViolations = (overview.srlg_findings || []).filter((s) => !s.diversity_compliant);
  const ranSitesPm = overview.ran_telemetry?.pm_telemetry || [];
  const subseaSystems = overview.ran_telemetry?.subsea_systems || [];

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#0B0F17] text-slate-900 dark:text-slate-100 flex flex-col transition-colors duration-200">
      <header className="sticky top-0 z-30 bg-white/85 dark:bg-slate-900/85 backdrop-blur-md border-b border-slate-200/80 dark:border-slate-800/80 px-6 py-3">
        <div className="max-w-[1600px] mx-auto flex flex-wrap items-center justify-between gap-4">
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

          <div className="flex items-center gap-2.5">
            <div className="flex items-center gap-2 bg-slate-100 dark:bg-slate-800/90 border border-slate-200/70 dark:border-slate-700 rounded-xl px-3 py-1.5 text-xs">
              <Globe className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
              <select
                value={selectedProfileId}
                onChange={(e) => setSelectedProfileId(e.target.value)}
                className="bg-transparent text-slate-800 dark:text-slate-100 font-semibold focus:outline-none cursor-pointer"
              >
                {Object.values(profiles).map((p) => (
                  <option
                    key={p.id}
                    value={p.id}
                    className="bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100"
                  >
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
              <span>{overview.llm_config?.api_key_configured ? 'LLM Live' : 'AI Key'}</span>
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

      <main className="flex-1 max-w-[1600px] w-full mx-auto px-6 py-5 space-y-5">
        {busyAction && (
          <div className="bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-200 dark:border-indigo-800 rounded-xl px-4 py-2.5 flex items-center gap-2.5 text-xs font-medium text-indigo-700 dark:text-indigo-300">
            <RefreshCw className="w-4 h-4 animate-spin" />
            <span>{busyAction}</span>
          </div>
        )}

        {primaryNav === 'workspace' && (
          <WorkspaceView
            overview={overview}
            incidents={incidents}
            activeIncident={activeIncident}
            onSelectIncidentId={setSelectedIncidentId}
            activeProfile={activeProfile}
            scenarios={scenarios}
            selectedScenarioId={selectedScenarioId}
            onSelectScenarioId={setSelectedScenarioId}
            stageTab={stageTab}
            onSelectStageTab={setStageTab}
            copilotTab={copilotTab}
            onSelectCopilotTab={setCopilotTab}
            selectedCableId={selectedCableId}
            displayedOtdr={displayedOtdr}
            displayedFaultLoc={displayedFaultLoc}
            srlgViolationCount={srlgViolations.length}
            theme={theme}
            busy={!!busyAction}
            onTriggerScenario={() => handleTriggerScenario()}
            onResetNetwork={handleResetNetwork}
            onSelectCable={handleSelectCable}
            onTriggerCutOnCable={handleTriggerCutOnCable}
            onUploadSorFile={handleUploadSorFile}
            onApproveActions={handleApproveActions}
          />
        )}

        {primaryNav === 'topology' && (
          <TopologyView
            graph={overview.dependency_graph || { nodes: [], edges: [] }}
            srlgFindings={overview.srlg_findings || []}
            theme={theme}
            onInspectCableInWorkspace={(cid) => {
              handleSelectCable(cid);
              setPrimaryNav('workspace');
              setStageTab('otdr');
            }}
          />
        )}

        {primaryNav === 'telemetry' && (
          <TelemetryView
            ranSitesPm={ranSitesPm}
            subseaSystems={subseaSystems}
            xmlPreview={xmlPreview}
            onTriggerScenario={(sid) => handleTriggerScenario(sid)}
            onToggle3gppXml={handleToggle3gppXml}
          />
        )}

        {primaryNav === 'connectors' && (
          <ConnectorsView
            connectors={overview.connectors || []}
            benchmarkResult={benchmarkResult}
            busy={!!busyAction}
            onRunStormBenchmark={handleRunStormBenchmark}
            onEditConnector={(c) => {
              setEditingConnector(c);
              setEditEndpointUrl(c.endpoint_url);
              setEditMode(c.mode);
            }}
          />
        )}
      </main>

      <LlmSettingsModal
        open={showLlmModal}
        provider={llmProvider}
        model={llmModel}
        apiKey={llmApiKey}
        onChangeProvider={(prov, defModel) => {
          setLlmProvider(prov);
          setLlmModel(defModel);
        }}
        onChangeModel={setLlmModel}
        onChangeApiKey={setLlmApiKey}
        onClose={() => setShowLlmModal(false)}
        onSave={handleSaveLlmSettings}
      />

      <ConnectorEditorModal
        connector={editingConnector}
        endpointUrl={editEndpointUrl}
        mode={editMode}
        onChangeEndpointUrl={setEditEndpointUrl}
        onChangeMode={setEditMode}
        onClose={() => setEditingConnector(null)}
        onSave={handleSaveConnector}
      />
    </div>
  );
};
