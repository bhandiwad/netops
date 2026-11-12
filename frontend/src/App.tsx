import React, { useEffect, useState } from 'react';
import {
  GitBranch,
  Layers,
  Moon,
  PlugZap,
  Radio,
  RefreshCw,
  SlidersHorizontal,
  Sun,
} from 'lucide-react';
import { nocApi } from './api/client';
import { ConnectorEditorModal, LlmSettingsModal } from './components/ConfigModals';
import type {
  Connector,
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
    setBusyAction('Simulating scenario...');
    try {
      await nocApi.triggerScenario(sid);
      await refreshOverview();
      setSelectedIncidentId(null);
      setInspectedOtdr(null);
      setPrimaryNav('workspace');
    } finally {
      setBusyAction(null);
    }
  };

  const handleTriggerCutOnCable = async (cableId: string, cutRatio: number) => {
    setBusyAction(`Simulating cut on ${cableId}...`);
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
    setBusyAction('Resetting network...');
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

  const handleClearCable = () => {
    setSelectedCableId(null);
    setInspectedOtdr(null);
  };

  const handleUploadSorFile = async (file: File) => {
    setBusyAction(`Reading ${file.name}...`);
    try {
      const data = await nocApi.parseUploadedSor(file);
      setInspectedOtdr(data);
      setStageTab('otdr');
    } finally {
      setBusyAction(null);
    }
  };

  const handleApproveActions = async (incidentId: string, actionIds?: string[]) => {
    setBusyAction('Running approved actions...');
    try {
      await nocApi.approveIncidentActions(incidentId, actionIds);
      await refreshOverview();
    } finally {
      setBusyAction(null);
    }
  };

  const handleRunStormBenchmark = async (stormSize: number = 10000) => {
    setBusyAction(`Running ${stormSize.toLocaleString()}-alarm test...`);
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
    setBusyAction('Loading XML telemetry...');
    try {
      const xml = await nocApi.get3gppXml();
      setXmlPreview(xml);
    } finally {
      setBusyAction(null);
    }
  };

  const handleSaveLlmSettings = async () => {
    setBusyAction('Saving model settings...');
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
      <div className="min-h-screen bg-[#F8F9FB] dark:bg-[#0A0D14] text-slate-900 dark:text-slate-100 flex items-center justify-center">
        <div className="flex items-center gap-2.5 text-xs font-medium text-slate-500 dark:text-slate-400">
          <RefreshCw className="w-4 h-4 animate-spin" />
          <span>Loading network workspace...</span>
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
    <div className="min-h-screen bg-[#F8F9FB] dark:bg-[#0A0D14] text-slate-900 dark:text-slate-100 flex flex-col transition-colors duration-200">
      <header className="sticky top-0 z-30 bg-white/90 dark:bg-[#0A0D14]/90 backdrop-blur-md border-b border-slate-200/80 dark:border-slate-800/80 px-6 h-14 flex items-center">
        <div className="max-w-[1520px] w-full mx-auto flex items-center justify-between gap-4">
          {/* Minimal Brand */}
          <div className="flex items-center gap-2.5">
            <div className="w-2.5 h-2.5 rounded-full bg-slate-900 dark:bg-white" />
            <span className="text-sm font-semibold tracking-tight text-slate-900 dark:text-white">
              Pandita
            </span>
            <span className="text-slate-300 dark:text-slate-700">/</span>
            <span className="text-sm text-slate-500 dark:text-slate-400 hidden sm:inline">
              Fibre Assurance
            </span>
          </div>

          {/* Clean 4-Item Navigation */}
          <nav className="flex items-center gap-1 bg-slate-100/90 dark:bg-[#111622] p-1 rounded-lg border border-slate-200/60 dark:border-slate-800/80">
            {[
              { id: 'workspace', label: 'Operations', icon: Layers, badge: incidents.length || 0 },
              {
                id: 'topology',
                label: 'Route Diversity',
                icon: GitBranch,
                badge: srlgViolations.length,
              },
              { id: 'telemetry', label: 'Sites & Subsea', icon: Radio, badge: 0 },
              { id: 'connectors', label: 'Integrations', icon: PlugZap, badge: 0 },
            ].map((item) => {
              const Icon = item.icon;
              const isActive = primaryNav === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setPrimaryNav(item.id as PrimaryNavId)}
                  className={`px-3 py-1 rounded-md text-xs font-medium flex items-center gap-1.5 transition ${
                    isActive
                      ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm'
                      : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{item.label}</span>
                  {item.badge > 0 && (
                    <span
                      className={`px-1.5 py-0.2 rounded-full text-[10px] font-semibold ${
                        item.id === 'workspace'
                          ? 'bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300'
                          : 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          {/* Compact Right Controls */}
          <div className="flex items-center gap-2">
            {busyAction && (
              <span className="hidden md:flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400 mr-1">
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>{busyAction}</span>
              </span>
            )}

            <select
              value={selectedProfileId}
              onChange={(e) => setSelectedProfileId(e.target.value)}
              aria-label="Operator profile"
              className="bg-slate-100/90 dark:bg-[#111622] border border-slate-200/70 dark:border-slate-800 rounded-lg px-2.5 py-1 text-xs font-medium text-slate-700 dark:text-slate-200 focus:outline-none cursor-pointer"
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

            <button
              onClick={() => setShowLlmModal(true)}
              className="p-1.5 rounded-lg border border-slate-200/70 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 transition"
              title="Model settings"
            >
              <SlidersHorizontal className="w-3.5 h-3.5" />
            </button>

            <button
              onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
              className="p-1.5 rounded-lg border border-slate-200/70 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 transition"
              title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
            >
              {theme === 'light' ? (
                <Moon className="w-3.5 h-3.5" />
              ) : (
                <Sun className="w-3.5 h-3.5 text-amber-400" />
              )}
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-[1520px] w-full mx-auto px-6 py-5">
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
            selectedCableId={selectedCableId}
            displayedOtdr={displayedOtdr}
            displayedFaultLoc={displayedFaultLoc}
            srlgViolationCount={srlgViolations.length}
            theme={theme}
            busy={!!busyAction}
            onTriggerScenario={(sid) => handleTriggerScenario(sid)}
            onResetNetwork={handleResetNetwork}
            onSelectCable={handleSelectCable}
            onClearCable={handleClearCable}
            onTriggerCutOnCable={handleTriggerCutOnCable}
            onUploadSorFile={handleUploadSorFile}
            onApproveActions={handleApproveActions}
            onOpenRouteDiversity={() => setPrimaryNav('topology')}
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
