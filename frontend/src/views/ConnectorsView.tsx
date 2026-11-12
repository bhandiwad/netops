import React from 'react';
import { Play, Settings2 } from 'lucide-react';
import type { Connector, StormBenchmarkResult } from '../types/api';

interface ConnectorsViewProps {
  connectors: Connector[];
  benchmarkResult: StormBenchmarkResult | null;
  busy: boolean;
  onRunStormBenchmark: (stormSize: number) => void;
  onEditConnector: (connector: Connector) => void;
}

export const ConnectorsView: React.FC<ConnectorsViewProps> = ({
  connectors,
  benchmarkResult,
  busy,
  onRunStormBenchmark,
  onEditConnector,
}) => {
  return (
    <div className="space-y-5">
      {/* Connected Systems */}
      <div className="bg-white dark:bg-[#111622] border border-slate-200/80 dark:border-slate-800/80 rounded-2xl p-5 space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
            Connected Network & IT Systems ({connectors.length})
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Read-only feeds for alarms, GIS, and OTDR, plus human-approved ticketing and optical routing.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
          {connectors.map((c) => (
            <div
              key={c.id}
              className="p-4 rounded-xl border border-slate-200/70 dark:border-slate-800 bg-slate-50/30 dark:bg-slate-900/30 flex flex-col justify-between gap-3"
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
                    {c.category}
                  </span>
                  <span className="flex items-center gap-1.5 text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                    {c.latency_ms} ms
                  </span>
                </div>
                <div className="text-xs font-semibold text-slate-900 dark:text-white">
                  {c.name}
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">{c.protocol}</div>
              </div>

              <div className="flex items-center justify-between pt-2.5 border-t border-slate-200/60 dark:border-slate-800 text-[11px]">
                <span className="text-slate-400 font-mono">{c.mode}</span>
                <button
                  onClick={() => onEditConnector(c)}
                  className="text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white font-medium flex items-center gap-1"
                >
                  <Settings2 className="w-3 h-3" /> Edit
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Alarm Storm Stress Test */}
      <div className="bg-white dark:bg-[#111622] border border-slate-200/80 dark:border-slate-800/80 rounded-2xl p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
              Alarm Storm Stress Test
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Measures how fast 10,000 raw alarms are deduplicated and grouped into root causes.
            </p>
          </div>
          <button
            onClick={() => onRunStormBenchmark(10000)}
            disabled={busy}
            className="px-3.5 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 dark:bg-white dark:hover:bg-slate-100 disabled:opacity-50 text-white dark:text-slate-900 text-xs font-medium flex items-center gap-1.5 transition"
          >
            <Play className="w-3 h-3 fill-current" /> Run 10,000-Alarm Test
          </button>
        </div>

        {benchmarkResult && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1">
            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-900/50 border border-slate-200/70 dark:border-slate-800">
              <div className="text-[11px] text-slate-500">Alarms processed</div>
              <div className="text-sm font-semibold font-mono text-slate-900 dark:text-white mt-0.5">
                {benchmarkResult.storm_size.toLocaleString()}
              </div>
            </div>
            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-900/50 border border-slate-200/70 dark:border-slate-800">
              <div className="text-[11px] text-slate-500">Root causes found</div>
              <div className="text-sm font-semibold font-mono text-emerald-600 dark:text-emerald-400 mt-0.5">
                {benchmarkResult.root_causes_identified} ({benchmarkResult.noise_reduction_pct}% noise cut)
              </div>
            </div>
            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-900/50 border border-slate-200/70 dark:border-slate-800">
              <div className="text-[11px] text-slate-500">Processing time</div>
              <div className="text-sm font-semibold font-mono text-slate-900 dark:text-white mt-0.5">
                {benchmarkResult.processing_latency_ms} ms
              </div>
            </div>
            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-900/50 border border-slate-200/70 dark:border-slate-800">
              <div className="text-[11px] text-slate-500">Throughput</div>
              <div className="text-sm font-semibold font-mono text-slate-900 dark:text-white mt-0.5">
                {benchmarkResult.throughput_alarms_per_sec.toLocaleString()}/sec
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
