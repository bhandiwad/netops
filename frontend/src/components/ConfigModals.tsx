import React, { useRef } from 'react';
import { Activity, FileCode2, FileSpreadsheet, MapPin, Upload } from './icons';
import type { Connector, OspCable } from '../types/api';

interface LlmModalProps {
  open: boolean;
  provider: string;
  model: string;
  apiKey: string;
  onChangeProvider: (provider: string, defaultModel: string) => void;
  onChangeModel: (model: string) => void;
  onChangeApiKey: (key: string) => void;
  onClose: () => void;
  onSave: () => void;
}

export const LlmSettingsModal: React.FC<LlmModalProps> = ({
  open,
  provider,
  model,
  apiKey,
  onChangeProvider,
  onChangeModel,
  onChangeApiKey,
  onClose,
  onSave,
}) => {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-slate-900 dark:text-white">
            Report & Summary Model
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-sm">
            ✕
          </button>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
          Fault pinpointing, slack math, and backup routing run deterministically on network inventory. Add an optional API key to generate live LLM executive narratives.
        </p>
        <div className="space-y-3 text-xs">
          <div>
            <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
              Provider
            </label>
            <select
              value={provider}
              onChange={(e) => {
                const next = e.target.value;
                onChangeProvider(
                  next,
                  next === 'anthropic' ? 'claude-sonnet-4-20250514' : 'gpt-4o'
                );
              }}
              className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2"
            >
              <option value="anthropic">Anthropic Claude</option>
              <option value="openai">OpenAI GPT</option>
            </select>
          </div>
          <div>
            <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
              Model
            </label>
            <input
              type="text"
              value={model}
              onChange={(e) => onChangeModel(e.target.value)}
              className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2 font-mono"
            />
          </div>
          <div>
            <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
              API Key
            </label>
            <input
              type="password"
              placeholder="sk-ant-... or sk-..."
              value={apiKey}
              onChange={(e) => onChangeApiKey(e.target.value)}
              className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2 font-mono"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button
            onClick={onClose}
            className="px-3.5 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-xs font-medium"
          >
            Cancel
          </button>
          <button
            onClick={onSave}
            className="px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 dark:bg-white dark:hover:bg-slate-100 text-white dark:text-slate-900 text-xs font-medium"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
};

interface ConnectorEditorModalProps {
  connector: Connector | null;
  endpointUrl: string;
  mode: string;
  onChangeEndpointUrl: (url: string) => void;
  onChangeMode: (mode: string) => void;
  onClose: () => void;
  onSave: () => void;
}

export const ConnectorEditorModal: React.FC<ConnectorEditorModalProps> = ({
  connector,
  endpointUrl,
  mode,
  onChangeEndpointUrl,
  onChangeMode,
  onClose,
  onSave,
}) => {
  if (!connector) return null;
  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-xl space-y-4">
        <h3 className="text-base font-semibold text-slate-900 dark:text-white">
          {connector.name}
        </h3>
        <div className="space-y-3 text-xs">
          <div>
            <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
              Source Mode
            </label>
            <select
              value={mode}
              onChange={(e) => onChangeMode(e.target.value)}
              className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2"
            >
              <option value="emulator">Local Emulator</option>
              <option value="live">Live Network Endpoint</option>
            </select>
          </div>
          <div>
            <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
              Endpoint URL
            </label>
            <input
              type="text"
              value={endpointUrl}
              onChange={(e) => onChangeEndpointUrl(e.target.value)}
              className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2 font-mono"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button
            onClick={onClose}
            className="px-3.5 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-xs font-medium"
          >
            Cancel
          </button>
          <button
            onClick={onSave}
            className="px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 dark:bg-white dark:hover:bg-slate-100 text-white dark:text-slate-900 text-xs font-medium"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
};

interface ImportDataModalProps {
  open: boolean;
  mapCenter?: [number, number];
  cables?: OspCable[];
  busy: boolean;
  onClose: () => void;
  onImportKml: (file: File) => void;
  onUploadSor: (file: File) => void;
  onImportCsv: (file: File) => void;
}

export const ImportDataModal: React.FC<ImportDataModalProps> = ({
  open,
  mapCenter = [55.245, 25.155],
  cables = [],
  busy,
  onClose,
  onImportKml,
  onUploadSor,
  onImportCsv,
}) => {
  const kmlRef = useRef<HTMLInputElement | null>(null);
  const sorRef = useRef<HTMLInputElement | null>(null);
  const csvRef = useRef<HTMLInputElement | null>(null);

  if (!open) return null;

  const handleLoadSampleKml = () => {
    const [lon, lat] = mapCenter;
    const sampleKml = `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Customer Field OSP Route</name>
    <Placemark>
      <name>East Industrial Chamber #1</name>
      <Point><coordinates>${(lon + 0.012).toFixed(5)},${(lat + 0.008).toFixed(5)},0</coordinates></Point>
    </Placemark>
    <Placemark>
      <name>Metro Spur 96F Feeder</name>
      <description>Imported Google Earth OSP Fibre Route</description>
      <LineString>
        <coordinates>
          ${(lon - 0.004).toFixed(5)},${(lat + 0.002).toFixed(5)},0
          ${(lon + 0.006).toFixed(5)},${(lat + 0.006).toFixed(5)},0
          ${(lon + 0.016).toFixed(5)},${(lat + 0.010).toFixed(5)},0
          ${(lon + 0.028).toFixed(5)},${(lat + 0.015).toFixed(5)},0
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>`;
    const file = new File([sampleKml], 'metro_spur_96f_route.kml', {
      type: 'application/vnd.google-earth.kml+xml',
    });
    onImportKml(file);
  };

  const handleLoadSampleCsv = () => {
    const targetCable = cables.find((c) => c.role === 'trunk') || cables[0];
    const cid = targetCable?.id || 'SPAN-01';
    const launchPop = targetCable?.path_nodes?.[0] || 'POP-A';
    const peerPop = targetCable?.path_nodes?.[targetCable.path_nodes.length - 1] || 'POP-B';
    const optDist = Math.round((targetCable?.optical_length_m || 6800) * 0.58);
    const sampleCsv = [
      'alarm_id,source_oem,layer,resource_id,node_id,severity,specific_problem,optical_distance_m,raw_text',
      `CSV-OTDR-01,viavi_onmsi,fibre_osp,${cid},${launchPop},CRITICAL,OTDR_REFLECTIVE_FIBER_BREAK,${optDist},"[CSV Export] 1625nm reflective fiber break on ${cid} at ${optDist}m"`,
      `CSV-DWDM-02,ciena_mcp,dwdm_optical,OMS-${launchPop}-${peerPop},${launchPop},CRITICAL,OTS_LOS_LINE_FAIL,,"[CSV Export] ROADM degree ${launchPop}->${peerPop} OTS-LOS RxPower=-40.0dBm"`,
      `CSV-IP-03,cisco_syslog,ip_mpls,RTR-${launchPop}:Hu0/1/0/${peerPop},${launchPop},MAJOR,INTERFACE_LINK_BFD_DOWN,,"[CSV Export] BFD 3x50ms session timeout on HundredGigE0/1/0/${peerPop}"`,
    ].join('\n');
    const file = new File([sampleCsv], 'ems_alarm_export.csv', { type: 'text/csv' });
    onImportCsv(file);
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/45 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-xl w-full p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-slate-900 dark:text-white">
              Import Plant & Field Telemetry
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Ingest standard Day-1 operator artifacts directly into PostGIS and the correlation engine.
            </p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-sm">
            ✕
          </button>
        </div>

        <div className="space-y-3 text-xs">
          {/* 1. Google Earth KML */}
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-950/50 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-sky-100 dark:bg-sky-950/70 text-sky-700 dark:text-sky-300 flex items-center justify-center shrink-0">
                <MapPin className="w-4 h-4" />
              </div>
              <div>
                <div className="font-semibold text-slate-900 dark:text-white">
                  Google Earth OSP Fibre Route (<code>.kml</code>)
                </div>
                <p className="text-slate-500 dark:text-slate-400 mt-0.5 leading-relaxed">
                  Parses <code>&lt;LineString&gt;</code> &amp; chamber <code>&lt;Point&gt;</code> placemarks into PostGIS with 25 m splice slack coils and 1.015x helix math.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              <input
                ref={kmlRef}
                type="file"
                accept=".kml,.xml"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files?.[0]) onImportKml(e.target.files[0]);
                }}
              />
              <button
                onClick={handleLoadSampleKml}
                disabled={busy}
                className="px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-white dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 font-medium transition"
              >
                Sample .kml
              </button>
              <button
                onClick={() => kmlRef.current?.click()}
                disabled={busy}
                className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 dark:bg-white dark:hover:bg-slate-100 text-white dark:text-slate-900 font-medium flex items-center gap-1.5 transition"
              >
                <Upload className="w-3.5 h-3.5" /> Upload .kml
              </button>
            </div>
          </div>

          {/* 2. Handheld OTDR .sor */}
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-950/50 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-indigo-100 dark:bg-indigo-950/70 text-indigo-700 dark:text-indigo-300 flex items-center justify-center shrink-0">
                <Activity className="w-4 h-4" />
              </div>
              <div>
                <div className="font-semibold text-slate-900 dark:text-white">
                  Handheld / RFTS OTDR Trace (<code>.sor</code>)
                </div>
                <p className="text-slate-500 dark:text-slate-400 mt-0.5 leading-relaxed">
                  Decodes binary Telcordia SR-4731 Rev 2 blocks (VIAVI / EXFO / Yokogawa), verifies CRC-16, and maps breaks to street GPS.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              <input
                ref={sorRef}
                type="file"
                accept=".sor"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files?.[0]) onUploadSor(e.target.files[0]);
                }}
              />
              <button
                onClick={() => sorRef.current?.click()}
                disabled={busy}
                className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 dark:bg-white dark:hover:bg-slate-100 text-white dark:text-slate-900 font-medium flex items-center gap-1.5 transition"
              >
                <FileCode2 className="w-3.5 h-3.5" /> Upload .sor
              </button>
            </div>
          </div>

          {/* 3. Vendor Alarm CSV */}
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-950/50 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-emerald-100 dark:bg-emerald-950/70 text-emerald-700 dark:text-emerald-300 flex items-center justify-center shrink-0">
                <FileSpreadsheet className="w-4 h-4" />
              </div>
              <div>
                <div className="font-semibold text-slate-900 dark:text-white">
                  EMS / NMS Alarm Export (<code>.csv</code>)
                </div>
                <p className="text-slate-500 dark:text-slate-400 mt-0.5 leading-relaxed">
                  Correlates batch alarm dumps from Nokia NSP, Ciena MCP, Ericsson ENM, Huawei NCE, or Netcool into root-cause incidents.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              <input
                ref={csvRef}
                type="file"
                accept=".csv"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files?.[0]) onImportCsv(e.target.files[0]);
                }}
              />
              <button
                onClick={handleLoadSampleCsv}
                disabled={busy}
                className="px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-white dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 font-medium transition"
              >
                Sample .csv
              </button>
              <button
                onClick={() => csvRef.current?.click()}
                disabled={busy}
                className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 dark:bg-white dark:hover:bg-slate-100 text-white dark:text-slate-900 font-medium flex items-center gap-1.5 transition"
              >
                <Upload className="w-3.5 h-3.5" /> Upload .csv
              </button>
            </div>
          </div>
        </div>

        <div className="flex justify-end pt-1">
          <button
            onClick={onClose}
            className="px-3.5 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-xs font-medium"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
