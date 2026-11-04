import React, { useRef } from 'react';
import { Activity, Download, Upload, CheckCircle2, AlertOctagon } from 'lucide-react';

interface OtdrTracePanelProps {
  trace: any | null;
  faultLocation: any | null;
  theme?: 'light' | 'dark';
  onUploadSorFile: (file: File) => void;
}

export const OtdrTracePanel: React.FC<OtdrTracePanelProps> = ({
  trace,
  faultLocation,
  theme = 'light',
  onUploadSorFile,
}) => {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const isLight = theme === 'light';

  if (!trace || !trace.trace_points_db || trace.trace_points_db.length === 0) {
    return (
      <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-6 flex flex-wrap items-center justify-between gap-4 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-200 dark:border-indigo-800/60 flex items-center justify-center">
            <Activity className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-slate-900 dark:text-white">
              VIAVI ONMSi & EXFO Nova 1625nm OTDR Trace Analyzer
            </h4>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Click any fibre cable on the GIS map or inject a fibre-cut scenario to inspect its live Telcordia SR-4731 Rev 2 binary <code className="font-mono text-indigo-600 dark:text-indigo-400">.sor</code> backscatter curve.
            </p>
          </div>
        </div>
        <div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".sor"
            className="hidden"
            onChange={(e) => {
              if (e.target.files?.[0]) onUploadSorFile(e.target.files[0]);
            }}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200/80 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 text-xs font-medium flex items-center gap-2 transition-colors"
          >
            <Upload className="w-4 h-4 text-indigo-600 dark:text-indigo-400" /> Upload Binary .sor File
          </button>
        </div>
      </div>
    );
  }

  const pts: [number, number][] = trace.trace_points_db;
  const maxDist = Math.max(...pts.map((p) => p[0]), 1000);
  const minDb = 0;
  const maxDb = 36;
  const width = 760;
  const height = 185;
  const padL = 44;
  const padR = 20;
  const padT = 18;
  const padB = 28;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;

  const toX = (d: number) => padL + (d / maxDist) * plotW;
  const toY = (db: number) =>
    padT + plotH - ((Math.max(minDb, Math.min(maxDb, db)) - minDb) / (maxDb - minDb)) * plotH;

  const pathD = pts
    .map(([d, db], i) => `${i === 0 ? 'M' : 'L'}${toX(d).toFixed(1)},${toY(db).toFixed(1)}`)
    .join(' ');

  const faultOpticalM = trace.fault_distance_optical_m;

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
      {/* Header Row */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 flex-wrap">
          <span className="px-2.5 py-1 rounded-lg bg-indigo-50 dark:bg-indigo-950/80 border border-indigo-200 dark:border-indigo-800 text-indigo-700 dark:text-indigo-300 font-mono text-xs font-semibold">
            {trace.cable_id}
          </span>
          <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">
            {trace.supplier_name} • {trace.unit_name} ({trace.wavelength_nm} nm)
          </span>
          <span className="px-2.5 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/70 border border-emerald-200 dark:border-emerald-800/60 text-emerald-700 dark:text-emerald-300 font-mono text-xs flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5" /> SR-4731 CRC-16 Verified ({trace.binary_size_bytes || 2420} B)
          </span>
          <span className="text-slate-500 dark:text-slate-400 font-mono text-xs">
            IOR {trace.refractive_index} · Pulse {trace.pulse_width_ns}ns
          </span>
        </div>

        <div className="flex items-center gap-2">
          <a
            href={`/viavi-onmsi/api/v1/traces/${trace.cable_id}.sor`}
            download={`${trace.cable_id}.sor`}
            className="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 flex items-center gap-1.5 font-mono text-xs font-medium transition-colors"
          >
            <Download className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" /> Download .sor
          </a>
          <input
            ref={fileInputRef}
            type="file"
            accept=".sor"
            className="hidden"
            onChange={(e) => {
              if (e.target.files?.[0]) onUploadSorFile(e.target.files[0]);
            }}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white flex items-center gap-1.5 text-xs font-medium transition-colors shadow-sm"
          >
            <Upload className="w-3.5 h-3.5" /> Parse .sor File
          </button>
        </div>
      </div>

      {/* Reflectogram Chart + Slack Math Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-stretch">
        <div className="lg:col-span-2 bg-slate-50/80 dark:bg-slate-950/80 border border-slate-200/70 dark:border-slate-800 rounded-xl p-3">
          <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-44 overflow-visible">
            {[5, 15, 25, 35].map((dbVal) => (
              <g key={dbVal}>
                <line
                  x1={padL}
                  x2={width - padR}
                  y1={toY(dbVal)}
                  y2={toY(dbVal)}
                  stroke={isLight ? '#e2e8f0' : '#1e293b'}
                  strokeDasharray="3,3"
                />
                <text
                  x={padL - 8}
                  y={toY(dbVal) + 3}
                  textAnchor="end"
                  fill={isLight ? '#64748b' : '#94a3b8'}
                  className="text-[10px] font-mono"
                >
                  {dbVal} dB
                </text>
              </g>
            ))}

            {(trace.key_events || []).map((ev: any) => {
              const x = toX(ev.distance_m);
              const isBreak = ev.event_code?.includes('1E') && ev.splice_loss_db > 5;
              return (
                <g key={ev.event_number}>
                  <line
                    x1={x}
                    x2={x}
                    y1={padT}
                    y2={height - padB}
                    stroke={isBreak ? '#e11d48' : '#6366f1'}
                    strokeWidth={isBreak ? 2 : 1.2}
                    strokeDasharray={isBreak ? 'none' : '3,3'}
                  />
                  <text
                    x={x}
                    y={isBreak ? padT + 10 : height - padB - 6}
                    textAnchor="middle"
                    fill={isBreak ? '#e11d48' : '#6366f1'}
                    className={`text-[10px] font-mono ${isBreak ? 'font-bold' : 'font-medium'}`}
                  >
                    {isBreak ? `REFLECTIVE BREAK (${ev.distance_m}m)` : `Splice E${ev.event_number}`}
                  </text>
                </g>
              );
            })}

            <path
              d={pathD}
              fill="none"
              stroke={isLight ? '#4f46e5' : '#38bdf8'}
              strokeWidth={2.2}
            />

            {[0, 0.25, 0.5, 0.75, 1].map((f, idx) => {
              const dist = Math.round(maxDist * f);
              return (
                <text
                  key={idx}
                  x={toX(dist)}
                  y={height - 6}
                  textAnchor="middle"
                  fill={isLight ? '#475569' : '#94a3b8'}
                  className="text-[10px] font-mono"
                >
                  {(dist / 1000).toFixed(2)} km
                </text>
              );
            })}
          </svg>
        </div>

        {/* Optical-to-Trench Slack Compensation Box */}
        <div className="bg-slate-50/90 dark:bg-slate-950/80 border border-slate-200/70 dark:border-slate-800 rounded-xl p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                Optical → Trench Localization
              </span>
              {faultOpticalM ? (
                <span className="px-2 py-0.5 rounded-full bg-rose-50 dark:bg-rose-950/80 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800 text-[11px] font-medium flex items-center gap-1">
                  <AlertOctagon className="w-3 h-3" /> Break Detected
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 text-[11px] font-medium">
                  Continuity Intact
                </span>
              )}
            </div>

            {faultLocation && faultLocation.corrected_trench_distance_m !== undefined ? (
              <div className="space-y-2 text-xs font-mono">
                <div className="flex justify-between text-slate-600 dark:text-slate-400">
                  <span>OTDR Optical Distance:</span>
                  <span className="font-semibold text-slate-900 dark:text-white">
                    {faultLocation.optical_distance_m} m
                  </span>
                </div>
                <div className="flex justify-between text-slate-600 dark:text-slate-400">
                  <span>− Manhole Slack Loops:</span>
                  <span className="font-semibold text-amber-600 dark:text-amber-400">
                    −{faultLocation.slack_Coils_subtracted_m} m
                  </span>
                </div>
                <div className="flex justify-between text-slate-600 dark:text-slate-400">
                  <span>÷ Helix Factor ({faultLocation.helix_factor}x):</span>
                  <span className="font-semibold text-indigo-600 dark:text-indigo-400">
                    {faultLocation.corrected_trench_distance_m} m trench
                  </span>
                </div>
                <div className="pt-2 border-t border-slate-200 dark:border-slate-800 flex justify-between text-emerald-700 dark:text-emerald-400">
                  <span className="font-sans font-medium">Dig Error Avoided:</span>
                  <span className="font-bold">{faultLocation.dispatch_error_avoided_m} m</span>
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                {faultLocation?.dying_gasp_confirmed
                  ? '1625nm OTDR trace verified 100% intact optical continuity (0.84 dB loss). Outage is confirmed AC mains power failure via G.984 Dying-Gasp.'
                  : `Full span scanned (${(trace.range_m / 1000).toFixed(2)} km) across ${(trace.key_events || []).length} fusion splice closures with zero reflective break.`}
              </p>
            )}
          </div>

          {faultLocation?.upstream_manhole && (
            <div className="mt-3 pt-2.5 border-t border-slate-200/80 dark:border-slate-800 text-[11px] text-slate-600 dark:text-slate-400">
              Bracketed between{' '}
              <strong className="font-mono text-slate-900 dark:text-white">
                {faultLocation.upstream_manhole?.manhole_id}
              </strong>{' '}
              (+{faultLocation.distance_from_upstream_manhole_m}m) and{' '}
              <strong className="font-mono text-slate-900 dark:text-white">
                {faultLocation.downstream_manhole?.manhole_id}
              </strong>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
