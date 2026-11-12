import React from 'react';
import { MultiLayerGraph } from '../components/MultiLayerGraph';
import type { DependencyGraphData, SrlgFinding, ThemeMode } from '../types/api';

interface TopologyViewProps {
  graph: DependencyGraphData;
  srlgFindings: SrlgFinding[];
  theme: ThemeMode;
  onInspectCableInWorkspace: (cableId: string) => void;
}

function formatAuditNote(f: SrlgFinding): string {
  if (f.diversity_compliant) {
    return 'Primary and backup routes run in separate ducts, chambers, and bridges end-to-end.';
  }
  const parts: string[] = [];
  if (f.shared_bridges?.length) parts.push(f.shared_bridges.join(', '));
  if (f.shared_ducts?.length) {
    parts.push(
      f.shared_ducts.length === 1
        ? `duct ${f.shared_ducts[0]}`
        : `${f.shared_ducts.length} ducts (${f.shared_ducts.slice(0, 2).join(', ')}${f.shared_ducts.length > 2 ? '…' : ''})`
    );
  }
  if (f.shared_chambers?.length) {
    parts.push(
      f.shared_chambers.length === 1
        ? `chamber ${f.shared_chambers[0]}`
        : `${f.shared_chambers.length} chambers`
    );
  }
  return parts.length > 0
    ? `Ordered diverse, but primary and backup routes share ${parts.join(', ')}.`
    : f.risk_summary;
}

export const TopologyView: React.FC<TopologyViewProps> = ({
  graph,
  srlgFindings,
  theme,
  onInspectCableInWorkspace,
}) => {
  const violations = srlgFindings.filter((f) => !f.diversity_compliant).length;
  const compliant = srlgFindings.length - violations;

  return (
    <div className="space-y-5">
      {/* Backup Route Diversity Audit first so commercial/engineering value is front and center */}
      <div className="bg-white dark:bg-[#111622] border border-slate-200/80 dark:border-slate-800/80 rounded-2xl p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
              Backup Route Diversity Audit
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Checks dual-homed customer circuits against street ducts, chambers, and bridges to spot hidden single points of failure.
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs">
            <span className="text-emerald-600 dark:text-emerald-400 font-medium">
              {compliant} diverse
            </span>
            <span className="text-slate-300 dark:text-slate-700">·</span>
            <span className="text-rose-600 dark:text-rose-400 font-medium">
              {violations} shared-duct risk{violations === 1 ? '' : 's'}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {srlgFindings.map((f) => (
            <div
              key={f.service_id}
              className={`p-4 rounded-xl border ${
                f.diversity_compliant
                  ? 'border-slate-200/80 dark:border-slate-800 bg-slate-50/40 dark:bg-slate-900/30'
                  : 'border-amber-200 dark:border-amber-900/70 bg-amber-50/40 dark:bg-amber-950/20'
              }`}
            >
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <div>
                  <span className="text-xs font-semibold text-slate-900 dark:text-white">
                    {f.customer_name}
                  </span>
                  <span className="text-[11px] font-mono text-slate-400 ml-2">
                    {f.service_id}
                  </span>
                </div>
                <span
                  className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${
                    f.diversity_compliant
                      ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/70 dark:text-emerald-300'
                      : 'bg-amber-100 text-amber-800 dark:bg-amber-900/60 dark:text-amber-200'
                  }`}
                >
                  {f.diversity_compliant ? 'Fully diverse' : 'Shared duct risk'}
                </span>
              </div>
              <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                {formatAuditNote(f)}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Multi-Layer Dependency Map */}
      <div className="bg-white dark:bg-[#111622] border border-slate-200/80 dark:border-slate-800/80 rounded-2xl p-5">
        <MultiLayerGraph
          graph={graph}
          theme={theme}
          onSelectCable={onInspectCableInWorkspace}
        />
      </div>
    </div>
  );
};
