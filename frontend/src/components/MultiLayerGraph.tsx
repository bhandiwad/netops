import React, { useState } from 'react';

interface MultiLayerGraphProps {
  graph: {
    nodes: any[];
    edges: any[];
  };
  theme: 'light' | 'dark';
  onSelectCable?: (cableId: string) => void;
}

const LAYER_TITLES = [
  'Ducts',
  'Fibre Cables',
  'Optical Channels',
  'IP & 5G Sites',
  'Customer Circuits',
];

export const MultiLayerGraph: React.FC<MultiLayerGraphProps> = ({
  graph,
  theme,
  onSelectCable,
}) => {
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

  const nodes = graph?.nodes || [];
  const edges = graph?.edges || [];

  const layers: Record<number, any[]> = { 0: [], 1: [], 2: [], 3: [], 4: [] };
  nodes.forEach((n) => {
    const idx = Math.min(4, Math.max(0, Number(n.layer_index ?? 0)));
    layers[idx].push(n);
  });

  const svgWidth = 1040;
  const svgHeight = 440;
  const colPositions = [105, 310, 520, 730, 935];

  const posMap: Record<string, { x: number; y: number; node: any }> = {};
  Object.entries(layers).forEach(([lIdxStr, list]) => {
    const lIdx = Number(lIdxStr);
    const x = colPositions[lIdx];
    const count = list.length || 1;
    const usableH = svgHeight - 76;
    list.forEach((n, i) => {
      const y = 56 + ((i + 0.5) / count) * usableH;
      posMap[n.id] = { x, y, node: n };
    });
  });

  const isLight = theme === 'light';

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
            Duct-to-Customer Dependency Map
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Hover any item to trace impact across ducts, cables, optical links, and customer SLAs.
          </p>
        </div>

        <div className="flex items-center gap-4 text-xs text-slate-600 dark:text-slate-400">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500" /> Healthy
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-amber-500" /> Degraded
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-rose-500" /> Outage
          </span>
        </div>
      </div>

      <div className="w-full overflow-x-auto rounded-xl border border-slate-200/70 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 p-2">
        <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="w-full min-w-[760px] h-[400px]">
          {LAYER_TITLES.map((title, idx) => (
            <g key={title}>
              <line
                x1={colPositions[idx]}
                y1={32}
                x2={colPositions[idx]}
                y2={svgHeight - 14}
                stroke={isLight ? '#e2e8f0' : '#1e293b'}
                strokeDasharray="3,3"
              />
              <text
                x={colPositions[idx]}
                y={20}
                textAnchor="middle"
                className="text-[11px] font-semibold"
                fill={isLight ? '#475569' : '#94a3b8'}
              >
                {title}
              </text>
            </g>
          ))}

          {edges.map((e, idx) => {
            const src = posMap[e.source];
            const dst = posMap[e.target];
            if (!src || !dst) return null;
            const isDown = e.status === 'DOWN';
            const isDegraded = e.status === 'DEGRADED';
            const isHighlighted = hoveredNodeId === e.source || hoveredNodeId === e.target;

            const strokeColor = isDown
              ? '#e11d48'
              : isDegraded
              ? '#d97706'
              : isHighlighted
              ? '#4f46e5'
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
                strokeWidth={isDown || isHighlighted ? 2.2 : 1.3}
                strokeDasharray={isDown ? '4,3' : 'none'}
                opacity={hoveredNodeId && !isHighlighted ? 0.2 : 0.9}
              />
            );
          })}

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
              ? '#4f46e5'
              : isLight
              ? '#e2e8f0'
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
                transform={`translate(${x - 68}, ${y - 19})`}
                onMouseEnter={() => setHoveredNodeId(node.id)}
                onMouseLeave={() => setHoveredNodeId(null)}
                onClick={() => {
                  if (node.layer_index === 1 && onSelectCable) {
                    onSelectCable(node.id);
                  }
                }}
                className="cursor-pointer transition-opacity"
              >
                <rect
                  width={136}
                  height={38}
                  rx={8}
                  fill={fillBg}
                  stroke={borderStroke}
                  strokeWidth={isDown || isHovered ? 1.8 : 1}
                />
                <circle
                  cx={12}
                  cy={14}
                  r={3.5}
                  fill={isDown ? '#f43f5e' : isDegraded ? '#f59e0b' : '#10b981'}
                />
                <text
                  x={21}
                  y={17}
                  className="text-[10px] font-mono font-medium"
                  fill={titleColor}
                >
                  {node.label.length > 15 ? node.label.slice(0, 15) + '…' : node.label}
                </text>
                <text x={12} y={30} className="text-[9.5px]" fill={subColor}>
                  {node.subtitle?.length > 21 ? node.subtitle.slice(0, 21) + '…' : node.subtitle}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
};
