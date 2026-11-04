import React, { useState } from 'react';
import { GitBranch, CheckCircle2, AlertTriangle, XCircle } from 'lucide-react';

interface MultiLayerGraphProps {
  graph: {
    nodes: any[];
    edges: any[];
  };
  theme: 'light' | 'dark';
  onSelectCable?: (cableId: string) => void;
}

const LAYER_TITLES = [
  '1. OSP Ducts (Lepton GIS)',
  '2. Fibre & Subsea Cables',
  '3. DWDM Optical (Ciena/Nokia)',
  '4. 5G RAN & IP Backhaul',
  '5. Enterprise Customer SLAs',
];

export const MultiLayerGraph: React.FC<MultiLayerGraphProps> = ({
  graph,
  theme,
  onSelectCable,
}) => {
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

  const nodes = graph?.nodes || [];
  const edges = graph?.edges || [];

  // Group nodes by layer_index (0..4)
  const layers: Record<number, any[]> = { 0: [], 1: [], 2: [], 3: [], 4: [] };
  nodes.forEach((n) => {
    const idx = Math.min(4, Math.max(0, Number(n.layer_index ?? 0)));
    layers[idx].push(n);
  });

  const svgWidth = 1040;
  const svgHeight = 460;
  const colPositions = [110, 310, 520, 730, 930];

  const posMap: Record<string, { x: number; y: number; node: any }> = {};
  Object.entries(layers).forEach(([lIdxStr, list]) => {
    const lIdx = Number(lIdxStr);
    const x = colPositions[lIdx];
    const count = list.length || 1;
    const usableH = svgHeight - 85;
    list.forEach((n, i) => {
      const y = 62 + ((i + 0.5) / count) * usableH;
      posMap[n.id] = { x, y, node: n };
    });
  });

  const isLight = theme === 'light';

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <GitBranch className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
              Cross-Layer Physical-to-Service Dependency Graph
            </h3>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Live topological binding across Lepton GIS ducts, fibre cables, Ciena/Nokia DWDM wavelengths, Ericsson 5G RAN sites, and Comviva BSS enterprise SLAs.
          </p>
        </div>

        <div className="flex items-center gap-4 text-xs">
          <span className="flex items-center gap-1.5 text-emerald-700 dark:text-emerald-400 font-medium">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" /> Healthy (UP)
          </span>
          <span className="flex items-center gap-1.5 text-amber-700 dark:text-amber-400 font-medium">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500" /> Degraded / Single-Leg
          </span>
          <span className="flex items-center gap-1.5 text-rose-700 dark:text-rose-400 font-medium">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500" /> Faulted / Outage (DOWN)
          </span>
        </div>
      </div>

      <div className="w-full overflow-x-auto rounded-xl border border-slate-100 dark:border-slate-800/80 bg-slate-50/70 dark:bg-slate-950/60 p-2">
        <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="w-full min-w-[780px] h-[420px]">
          {/* Column Header Pills */}
          {LAYER_TITLES.map((title, idx) => (
            <g key={title}>
              <line
                x1={colPositions[idx]}
                y1={36}
                x2={colPositions[idx]}
                y2={svgHeight - 16}
                stroke={isLight ? '#e2e8f0' : '#1e293b'}
                strokeDasharray="4,4"
              />
              <rect
                x={colPositions[idx] - 84}
                y={8}
                width={168}
                height={24}
                rx={6}
                fill={isLight ? '#f1f5f9' : '#0f172a'}
                stroke={isLight ? '#cbd5e1' : '#334155'}
              />
              <text
                x={colPositions[idx]}
                y={24}
                textAnchor="middle"
                className="text-[10px] font-semibold"
                fill={isLight ? '#334155' : '#cbd5e1'}
              >
                {title}
              </text>
            </g>
          ))}

          {/* Edges */}
          {edges.map((e, idx) => {
            const src = posMap[e.source];
            const dst = posMap[e.target];
            if (!src || !dst) return null;
            const isDown = e.status === 'DOWN';
            const isDegraded = e.status === 'DEGRADED';
            const isHighlighted =
              hoveredNodeId === e.source || hoveredNodeId === e.target;

            const strokeColor = isDown
              ? '#f43f5e'
              : isDegraded
              ? '#f59e0b'
              : isHighlighted
              ? '#6366f1'
              : isLight
              ? '#cbd5e1'
              : '#334155';

            const midX = (src.x + dst.x) / 2;
            const d = `M ${src.x + 68} ${src.y} C ${midX} ${src.y}, ${midX} ${dst.y}, ${dst.x - 68} ${dst.y}`;

            return (
              <path
                key={idx}
                d={d}
                fill="none"
                stroke={strokeColor}
                strokeWidth={isDown || isHighlighted ? 2.4 : 1.5}
                strokeDasharray={isDown ? '5,3' : 'none'}
                opacity={
                  hoveredNodeId && !isHighlighted ? 0.25 : 0.9
                }
              />
            );
          })}

          {/* Nodes */}
          {Object.values(posMap).map(({ x, y, node }) => {
            const isDown = node.status === 'DOWN';
            const isDegraded = node.status === 'DEGRADED';
            const isHovered = hoveredNodeId === node.id;

            const fillBg = isDown
              ? isLight
                ? '#fff1f2'
                : '#4c0519'
              : isDegraded
              ? isLight
                ? '#fffbeb'
                : '#451a03'
              : isLight
              ? '#ffffff'
              : '#0f172a';

            const borderStroke = isDown
              ? '#f43f5e'
              : isDegraded
              ? '#f59e0b'
              : isHovered
              ? '#6366f1'
              : isLight
              ? '#cbd5e1'
              : '#334155';

            const titleColor = isDown
              ? isLight
                ? '#be123c'
                : '#fda4af'
              : isDegraded
              ? isLight
                ? '#b45309'
                : '#fcd34d'
              : isLight
              ? '#0f172a'
              : '#f8fafc';

            const subColor = isLight ? '#64748b' : '#94a3b8';

            return (
              <g
                key={node.id}
                transform={`translate(${x - 68}, ${y - 20})`}
                onMouseEnter={() => setHoveredNodeId(node.id)}
                onMouseLeave={() => setHoveredNodeId(null)}
                onClick={() => {
                  if (node.id.startsWith('CBL-') && onSelectCable) {
                    onSelectCable(node.id);
                  }
                }}
                className="cursor-pointer transition-opacity"
              >
                <rect
                  width={136}
                  height={40}
                  rx={8}
                  fill={fillBg}
                  stroke={borderStroke}
                  strokeWidth={isDown || isHovered ? 2 : 1.2}
                />
                <circle
                  cx={12}
                  cy={14}
                  r={4}
                  fill={isDown ? '#f43f5e' : isDegraded ? '#f59e0b' : '#10b981'}
                />
                <text
                  x={22}
                  y={17}
                  className="text-[10px] font-mono font-semibold"
                  fill={titleColor}
                >
                  {node.label.length > 15 ? node.label.slice(0, 15) + '…' : node.label}
                </text>
                <text
                  x={12}
                  y={31}
                  className="text-[9.5px]"
                  fill={subColor}
                >
                  {node.subtitle?.length > 21
                    ? node.subtitle.slice(0, 21) + '…'
                    : node.subtitle}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
};
