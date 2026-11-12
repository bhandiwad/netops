import React from 'react';
import { Cpu, Wrench, Zap } from 'lucide-react';
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
    <div className="space-y-6">
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
            onClick={() => onRunStormBenchmark(10000)}
            disabled={busy}
            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold flex items-center gap-2 shadow-sm transition"
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
          {connectors.map((c) => (
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
                <div className="text-sm font-bold text-slate-900 dark:text-white">{c.name}</div>
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
                  onClick={() => onEditConnector(c)}
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
  );
};
