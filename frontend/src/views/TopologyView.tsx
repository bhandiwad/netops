import React from 'react';
import { MultiLayerGraph } from '../components/MultiLayerGraph';
import type { DependencyGraphData, SrlgFinding, ThemeMode } from '../types/api';

interface TopologyViewProps {
  graph: DependencyGraphData;
  srlgFindings: SrlgFinding[];
  theme: ThemeMode;
  onInspectCableInWorkspace: (cableId: string) => void;
}

export const TopologyView: React.FC<TopologyViewProps> = ({
  graph,
  srlgFindings,
  theme,
  onInspectCableInWorkspace,
}) => {
  return (
    <div className="space-y-6">
      <MultiLayerGraph
        graph={graph}
        theme={theme}
        onSelectCable={onInspectCableInWorkspace}
      />

      <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
        <div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-white">
            Continuous Physical Route-Diversity (SRLG) Compliance Audit
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Audits every dual-homed / 1+1 protected enterprise circuit in BSS against actual OSP GIS duct & manhole chamber geometry.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {srlgFindings.map((f) => (
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
  );
};
