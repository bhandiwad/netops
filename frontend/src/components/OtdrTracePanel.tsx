import React, { useRef } from 'react';
import { Activity, Download, Upload, AlertOctagon } from 'lucide-react';

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
      <div className="rounded-xl border border-dashed border-slate-200 dark:border-slate-800 p-8 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-600 dark:text-slate-300">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-slate-900 dark:text-white">
              No cable selected
            </h4>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Click any fibre cable on the map or upload an OTDR <code className="font-mono">.sor</code> file to view its trace and street distance.
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
            className="px-3.5 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 dark:bg-white dark:hover:bg-slate-100 text-white dark:text-slate-900 text-xs font-medium flex items-center gap-2 transition"
          >
            <Upload className="w-3.5 h-3.5" /> Upload .sor File
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
  const height = 190;
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
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="font-mono text-sm font-semibold text-slate-900 dark:text-white">
            {trace.cable_id}
          </span>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            {trace.supplier_name} · {trace.wavelength_nm} nm
          </span>
          {faultOpticalM ? (
            <span className="px-2 py-0.5 rounded-full bg-rose-50 dark:bg-rose-950/70 text-rose-700 dark:text-rose-300 text-[11px] font-medium flex items-center gap-1">
              <AlertOctagon className="w-3 h-3" /> Break at {faultOpticalM} m
            </span>
          ) : (
            <span className="px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/70 text-emerald-700 dark:text-emerald-300 text-[11px] font-medium">
              Fibre intact
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <a
            href={`/viavi-onmsi/api/v1/traces/${trace.cable_id}.sor`}
            download={`${trace.cable_id}.sor`}
            className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 flex items-center gap-1.5 text-xs font-medium transition"
          >
            <Download className="w-3.5 h-3.5" /> .sor
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
            className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 dark:bg-white dark:hover:bg-slate-100 text-white dark:text-slate-900 flex items-center gap-1.5 text-xs font-medium transition"
          >
            <Upload className="w-3.5 h-3.5" /> Upload .sor
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-stretch">
        <div className="lg:col-span-2 bg-slate-50/70 dark:bg-slate-950/60 border border-slate-200/70 dark:border-slate-800 rounded-xl p-3">
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
                    stroke={isBreak ? '#e11d48' : '#94a3b8'}
                    strokeWidth={isBreak ? 2 : 1}
                    strokeDasharray={isBreak ? 'none' : '3,3'}
                  />
                  <text
                    x={x}
                    y={isBreak ? padT + 10 : height - padB - 6}
                    textAnchor="middle"
                    fill={isBreak ? '#e11d48' : '#64748b'}
                    className={`text-[10px] font-mono ${isBreak ? 'font-semibold' : ''}`}
                  >
                    {isBreak ? `Break (${ev.distance_m} m)` : `E${ev.event_number}`}
                  </text>
                </g>
              );
            })}

            <path
              d={pathD}
              fill="none"
              stroke={isLight ? '#0f172a' : '#38bdf8'}
              strokeWidth={2}
            />

            {[0, 0.25, 0.5, 0.75, 1].map((f, idx) => {
              const dist = Math.round(maxDist * f);
              return (
                <text
                  key={idx}
                  x={toX(dist)}
                  y={height - 6}
                  textAnchor="middle"
                  fill={isLight ? '#64748b' : '#94a3b8'}
                  className="text-[10px] font-mono"
                >
                  {(dist / 1000).toFixed(2)} km
                </text>
              );
            })}
          </svg>
        </div>

        <div className="bg-slate-50/70 dark:bg-slate-950/60 border border-slate-200/70 dark:border-slate-800 rounded-xl p-4 flex flex-col justify-between">
          <div>
            <div className="text-xs font-semibold text-slate-900 dark:text-white mb-3">
              Glass-to-Street Distance
            </div>

            {faultLocation && faultLocation.corrected_trench_distance_m !== undefined ? (
              <div className="space-y-2 text-xs">
                <div className="flex justify-between text-slate-600 dark:text-slate-400">
                  <span>Raw OTDR glass</span>
                  <span className="font-mono font-medium text-slate-900 dark:text-white">
                    {faultLocation.optical_distance_m} m
                  </span>
                </div>
                <div className="flex justify-between text-slate-600 dark:text-slate-400">
                  <span>Manhole slack loops</span>
                  <span className="font-mono font-medium text-amber-600 dark:text-amber-400">
                    −{faultLocation.slack_Coils_subtracted_m} m
                  </span>
                </div>
                <div className="flex justify-between text-slate-600 dark:text-slate-400">
                  <span>Street trench spot</span>
                  <span className="font-mono font-semibold text-slate-900 dark:text-white">
                    {faultLocation.corrected_trench_distance_m} m
                  </span>
                </div>
                <div className="pt-2.5 border-t border-slate-200 dark:border-slate-800 flex justify-between text-emerald-700 dark:text-emerald-400 font-medium">
                  <span>Dig error avoided</span>
                  <span className="font-mono font-semibold">
                    {faultLocation.dispatch_error_avoided_m} m
                  </span>
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                {faultLocation?.dying_gasp_confirmed
                  ? 'OTDR confirms the fibre is unbroken end-to-end. Alarms are caused by a building power outage—no splice dispatch needed.'
                  : `Full span scanned (${((trace.range_m || 0) / 1000).toFixed(2)} km) across ${(trace.key_events || []).length} splice points with no physical break.`}
              </p>
            )}
          </div>

          {faultLocation?.upstream_manhole && (
            <div className="mt-3 pt-2.5 border-t border-slate-200/80 dark:border-slate-800 text-[11px] text-slate-500 dark:text-slate-400">
              Between{' '}
              <strong className="font-mono text-slate-800 dark:text-slate-200">
                {faultLocation.upstream_manhole?.manhole_id}
              </strong>{' '}
              (+{faultLocation.distance_from_upstream_manhole_m} m) and{' '}
              <strong className="font-mono text-slate-800 dark:text-slate-200">
                {faultLocation.downstream_manhole?.manhole_id}
              </strong>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
