import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import { Layers, Crosshair } from 'lucide-react';

interface OspMapProps {
  gis: {
    ducts: any[];
    manholes: any[];
    cables: any[];
  };
  topology: any;
  activeIncident: any | null;
  activeProfile: any;
  selectedCableId: string | null;
  theme?: 'light' | 'dark';
  onSelectCable: (cableId: string) => void;
  onTriggerCutOnCable: (cableId: string, cutRatio: number) => void;
}

export const OspMap: React.FC<OspMapProps> = ({
  gis,
  topology,
  activeIncident,
  activeProfile,
  selectedCableId,
  theme = 'light',
  onSelectCable,
  onTriggerCutOnCable,
}) => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);

  const [showDucts, setShowDucts] = useState(true);
  const [showManholes, setShowManholes] = useState(true);
  const [showRanSites, setShowRanSites] = useState(true);
  const [cutRatioSlider, setCutRatioSlider] = useState(0.62);

  const showMobilePack = activeProfile?.active_packs?.includes('mobile_ran') ?? true;
  const isLight = theme === 'light';

  // Initialize MapLibre GL map
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: {
        version: 8,
        sources: {
          'carto-light': {
            type: 'raster',
            tiles: [
              'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
              'https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
            ],
            tileSize: 256,
            attribution: '© OpenStreetMap, © CARTO | Lepton SmartInventory WFS + PostGIS',
          },
          'carto-dark': {
            type: 'raster',
            tiles: [
              'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
              'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
            ],
            tileSize: 256,
          },
        },
        layers: [
          {
            id: 'carto-light-layer',
            type: 'raster',
            source: 'carto-light',
            minzoom: 0,
            maxzoom: 20,
            layout: { visibility: isLight ? 'visible' : 'none' },
          },
          {
            id: 'carto-dark-layer',
            type: 'raster',
            source: 'carto-dark',
            minzoom: 0,
            maxzoom: 20,
            layout: { visibility: isLight ? 'none' : 'visible' },
          },
        ],
      },
      center: [55.245, 25.155],
      zoom: 10.9,
      pitch: 18,
    });

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'bottom-right');
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Switch basemap tiles when theme changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    if (map.getLayer('carto-light-layer')) {
      map.setLayoutProperty('carto-light-layer', 'visibility', isLight ? 'visible' : 'none');
    }
    if (map.getLayer('carto-dark-layer')) {
      map.setLayoutProperty('carto-dark-layer', 'visibility', isLight ? 'none' : 'visible');
    }
  }, [isLight]);

  // Update GeoJSON sources & HTML markers
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const renderLayers = () => {
      if (map.getLayer('carto-light-layer')) {
        map.setLayoutProperty('carto-light-layer', 'visibility', isLight ? 'visible' : 'none');
      }
      if (map.getLayer('carto-dark-layer')) {
        map.setLayoutProperty('carto-dark-layer', 'visibility', isLight ? 'none' : 'visible');
      }

      const cutCables = new Set<string>(
        activeIncident?.fault_location?.cut_cables ||
          (activeIncident?.fault_location?.cable_id ? [activeIncident.fault_location.cable_id] : [])
      );

      const ductsGeoJson: any = {
        type: 'FeatureCollection',
        features: (gis?.ducts || []).map((d) => ({
          type: 'Feature',
          geometry: { type: 'LineString', coordinates: d.coords_json },
          properties: {
            id: d.id,
            bridge: d.bridge || '',
            trench_length_m: d.trench_length_m,
          },
        })),
      };

      const cablesGeoJson: any = {
        type: 'FeatureCollection',
        features: (gis?.cables || []).map((c) => {
          const isFaulted = cutCables.has(c.id);
          const isSelected = selectedCableId === c.id;
          return {
            type: 'Feature',
            geometry: { type: 'LineString', coordinates: c.coords_json },
            properties: {
              id: c.id,
              role: c.role,
              fibres: c.fibres,
              trench_length_m: c.trench_length_m,
              optical_length_m: c.optical_length_m,
              faulted: isFaulted ? 1 : 0,
              selected: isSelected ? 1 : 0,
            },
          };
        }),
      };

      const fl = activeIncident?.fault_location;
      const offsetFeatures: any[] = [];
      if (fl && fl.lat && fl.lon && fl.naive_lat && fl.naive_lon) {
        offsetFeatures.push({
          type: 'Feature',
          geometry: {
            type: 'LineString',
            coordinates: [
              [fl.naive_lon, fl.naive_lat],
              [fl.lon, fl.lat],
            ],
          },
          properties: {
            error_m: fl.dispatch_error_avoided_m,
          },
        });
      }
      const offsetGeoJson: any = {
        type: 'FeatureCollection',
        features: offsetFeatures,
      };

      if (map.getSource('osp-ducts')) {
        (map.getSource('osp-ducts') as maplibregl.GeoJSONSource).setData(ductsGeoJson);
      } else {
        map.addSource('osp-ducts', { type: 'geojson', data: ductsGeoJson });
        map.addLayer({
          id: 'osp-ducts-line',
          type: 'line',
          source: 'osp-ducts',
          paint: {
            'line-color': ['case', ['!=', ['get', 'bridge'], ''], '#d97706', '#64748b'],
            'line-width': ['case', ['!=', ['get', 'bridge'], ''], 3.2, 1.4],
            'line-dasharray': [2, 2],
            'line-opacity': 0.6,
          },
        });
      }

      if (map.getSource('osp-cables')) {
        (map.getSource('osp-cables') as maplibregl.GeoJSONSource).setData(cablesGeoJson);
      } else {
        map.addSource('osp-cables', { type: 'geojson', data: cablesGeoJson });
        map.addLayer({
          id: 'osp-cables-halo',
          type: 'line',
          source: 'osp-cables',
          paint: {
            'line-color': [
              'case',
              ['==', ['get', 'faulted'], 1],
              '#e11d48',
              ['==', ['get', 'selected'], 1],
              '#4f46e5',
              'transparent',
            ],
            'line-width': ['case', ['==', ['get', 'faulted'], 1], 11, ['==', ['get', 'selected'], 1], 8, 0],
            'line-opacity': 0.3,
            'line-blur': 3,
          },
        });
        map.addLayer({
          id: 'osp-cables-line',
          type: 'line',
          source: 'osp-cables',
          paint: {
            'line-color': [
              'case',
              ['==', ['get', 'faulted'], 1],
              '#e11d48',
              ['==', ['get', 'role'], 'trunk'],
              '#0284c7',
              ['==', ['get', 'role'], 'dark'],
              '#7c3aed',
              ['==', ['get', 'role'], 'ran_backhaul'],
              '#2563eb',
              '#059669',
            ],
            'line-width': [
              'case',
              ['==', ['get', 'faulted'], 1],
              4.2,
              ['==', ['get', 'selected'], 1],
              3.8,
              ['==', ['get', 'role'], 'trunk'],
              2.8,
              2.2,
            ],
            'line-opacity': 0.9,
          },
        });

        map.on('click', 'osp-cables-line', (e) => {
          const feat = e.features?.[0];
          if (feat?.properties?.id) {
            onSelectCable(String(feat.properties.id));
          }
        });
        map.on('mouseenter', 'osp-cables-line', () => {
          map.getCanvas().style.cursor = 'pointer';
        });
        map.on('mouseleave', 'osp-cables-line', () => {
          map.getCanvas().style.cursor = '';
        });
      }

      if (map.getSource('slack-offset')) {
        (map.getSource('slack-offset') as maplibregl.GeoJSONSource).setData(offsetGeoJson);
      } else {
        map.addSource('slack-offset', { type: 'geojson', data: offsetGeoJson });
        map.addLayer({
          id: 'slack-offset-line',
          type: 'line',
          source: 'slack-offset',
          paint: {
            'line-color': '#d97706',
            'line-width': 2.5,
            'line-dasharray': [2, 1.5],
          },
        });
      }

      if (map.getLayer('osp-ducts-line')) {
        map.setLayoutProperty('osp-ducts-line', 'visibility', showDucts ? 'visible' : 'none');
      }

      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];

      const nodesObj = topology?.nodes || {};
      const impactedCustomerIds = new Set(
        (activeIncident?.impact?.impacted_services || []).map((s: any) => s.customer_id)
      );
      const impactedRanIds = new Set(
        (activeIncident?.impact?.impacted_ran_sites || []).map((r: any) => r.site_id)
      );

      // Manhole markers
      if (showManholes) {
        (gis?.manholes || []).forEach((mh) => {
          if (mh.kind !== 'junction') return;
          const el = document.createElement('div');
          el.className =
            'w-3 h-3 rounded-full bg-white dark:bg-slate-900 border-2 border-amber-500 hover:scale-150 transition-transform cursor-pointer shadow-sm';
          el.title = `${mh.id} (${mh.name}) — Slack coil: ${mh.slack_coil_m}m`;
          const marker = new maplibregl.Marker({ element: el })
            .setLngLat([mh.lon, mh.lat])
            .setPopup(
              new maplibregl.Popup({ offset: 10 }).setHTML(
                `<div class="text-slate-900 text-xs font-sans p-1.5">
                  <div class="font-bold">${mh.id}</div>
                  <div class="text-slate-600">${mh.name}</div>
                  <div class="text-amber-700 font-semibold mt-1">Splice Slack Loop: ${mh.slack_coil_m} m</div>
                </div>`
              )
            )
            .addTo(map);
          markersRef.current.push(marker);
        });
      }

      // POPs, Customer Nodes & 5G RAN Sites
      Object.entries(nodesObj).forEach(([nid, ninfo]: [string, any]) => {
        if (ninfo.kind === 'pop') {
          const el = document.createElement('div');
          el.className =
            'px-2 py-0.5 rounded-md bg-slate-900 text-white border border-sky-400 text-[10px] font-mono font-semibold shadow-md cursor-pointer';
          el.innerText = nid;
          el.title = `${ninfo.name} (POP / Optical ROADM + Core Router)`;
          const marker = new maplibregl.Marker({ element: el }).setLngLat([ninfo.lon, ninfo.lat]).addTo(map);
          markersRef.current.push(marker);
        } else if (ninfo.kind === 'customer') {
          const isHit =
            Array.from(impactedCustomerIds).some((cid) =>
              ninfo.name.toLowerCase().includes(cid.toLowerCase())
            ) ||
            (activeIncident &&
              activeIncident.impact?.impacted_services?.some((s: any) =>
                ninfo.name.toLowerCase().includes(s.customer_name.split(' ')[0].toLowerCase())
              ));
          const el = document.createElement('div');
          el.className = `px-2 py-0.5 rounded-md border text-[10px] font-medium shadow-sm ${
            isHit
              ? 'bg-rose-600 border-white text-white font-semibold animate-pulse'
              : 'bg-white/95 text-slate-800 border-emerald-500/80 dark:bg-slate-900/95 dark:text-emerald-200'
          }`;
          el.innerText = ninfo.name.split(' ').slice(0, 2).join(' ');
          el.title = `${ninfo.name} (Enterprise Customer Site)`;
          const marker = new maplibregl.Marker({ element: el }).setLngLat([ninfo.lon, ninfo.lat]).addTo(map);
          markersRef.current.push(marker);
        } else if (ninfo.kind === 'cellsite' && showMobilePack && showRanSites) {
          const isDown = impactedRanIds.has(nid);
          const el = document.createElement('div');
          el.className = `px-2 py-0.5 rounded-full border text-[10px] font-mono font-semibold shadow-sm ${
            isDown
              ? 'bg-rose-600 border-white text-white animate-bounce'
              : 'bg-indigo-600 text-white border-indigo-300'
          }`;
          el.innerText = `5G:${nid.replace('RAN_', '')}`;
          el.title = ninfo.name;
          const marker = new maplibregl.Marker({ element: el }).setLngLat([ninfo.lon, ninfo.lat]).addTo(map);
          markersRef.current.push(marker);
        }
      });

      // Fault Localization Pin
      if (fl && fl.lat && fl.lon) {
        if (fl.naive_lat && fl.naive_lon && fl.dispatch_error_avoided_m > 5) {
          const naiveEl = document.createElement('div');
          naiveEl.className =
            'px-2 py-0.5 rounded-md bg-amber-500 text-slate-950 border border-white text-[10px] font-mono font-semibold shadow-md';
          naiveEl.innerHTML = `Naive Uncorrected (+${fl.dispatch_error_avoided_m}m off)`;
          const naiveMarker = new maplibregl.Marker({ element: naiveEl })
            .setLngLat([fl.naive_lon, fl.naive_lat])
            .addTo(map);
          markersRef.current.push(naiveMarker);
        }

        let badgeLabel = `✂️ CUT @ ${fl.corrected_trench_distance_m ?? 0}m`;
        if (fl.dying_gasp_confirmed) badgeLabel = '⚡ AC MAINS BLACKOUT (NO CUT)';
        else if (fl.dc_bus_voltage_v) badgeLabel = `🔋 BATTERY LVD (${fl.dc_bus_voltage_v}V · ${fl.battery_remaining_mins}m left)`;
        else if (fl.mw_link_id) badgeLabel = `🌧️ 80GHz RAIN FADE (${fl.acm_state})`;
        else if (fl.subsea_cable_id) badgeLabel = `🌊 SUBSEA PFE SHUNT (${fl.cotdr_shunt_distance_km}km)`;

        const faultEl = document.createElement('div');
        faultEl.className = 'relative flex items-center justify-center';
        faultEl.innerHTML = `
          <div class="w-10 h-10 rounded-full bg-rose-500/40 fault-pulse-ring absolute"></div>
          <div class="px-2.5 py-1 rounded-lg bg-rose-600 border-2 border-white text-white text-[11px] font-mono font-semibold shadow-xl relative z-10 whitespace-nowrap">
            ${badgeLabel}
          </div>
        `;
        const faultMarker = new maplibregl.Marker({ element: faultEl })
          .setLngLat([fl.lon, fl.lat])
          .addTo(map);
        markersRef.current.push(faultMarker);

        map.flyTo({ center: [fl.lon, fl.lat], zoom: 12.4, duration: 1000 });
      }
    };

    if (map.isStyleLoaded()) {
      renderLayers();
    } else {
      map.once('load', renderLayers);
    }
  }, [gis, topology, activeIncident, selectedCableId, showDucts, showManholes, showRanSites, showMobilePack, isLight]);

  return (
    <div className="relative w-full h-full rounded-xl overflow-hidden border border-slate-200/80 dark:border-slate-800 bg-slate-100 dark:bg-slate-950">
      <div ref={mapContainerRef} className="w-full h-full" />

      {/* Clean Floating Layer Filter Bar */}
      <div className="absolute top-3 left-3 z-10 flex flex-wrap items-center gap-1.5 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md border border-slate-200/80 dark:border-slate-700/80 rounded-xl px-3 py-1.5 text-xs shadow-sm">
        <span className="text-slate-600 dark:text-slate-300 font-semibold flex items-center gap-1.5 mr-1">
          <Layers className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" /> Layers:
        </span>
        <button
          onClick={() => setShowDucts(!showDucts)}
          className={`px-2.5 py-0.5 rounded-lg font-medium transition ${
            showDucts
              ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
              : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          Ducts
        </button>
        <button
          onClick={() => setShowManholes(!showManholes)}
          className={`px-2.5 py-0.5 rounded-lg font-medium transition ${
            showManholes
              ? 'bg-amber-500/15 text-amber-800 dark:text-amber-300 border border-amber-400/50'
              : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          Slack Chambers
        </button>
        {showMobilePack && (
          <button
            onClick={() => setShowRanSites(!showRanSites)}
            className={`px-2.5 py-0.5 rounded-lg font-medium transition ${
              showRanSites
                ? 'bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 border border-indigo-400/50'
                : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800'
            }`}
          >
            5G Sites
          </button>
        )}
      </div>

      {/* Selected Cable Cut Bar */}
      {selectedCableId && (
        <div className="absolute bottom-3 left-3 right-12 z-10 bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border border-indigo-200 dark:border-indigo-800 rounded-xl px-4 py-2.5 flex flex-wrap items-center justify-between gap-3 text-xs shadow-lg">
          <div className="flex items-center gap-2">
            <Crosshair className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            <span className="font-mono font-semibold text-indigo-700 dark:text-indigo-300">{selectedCableId}</span>
            <span className="text-slate-600 dark:text-slate-400">
              Simulate cut at <strong className="font-mono text-slate-900 dark:text-white">{Math.round(cutRatioSlider * 100)}%</strong> along route:
            </span>
          </div>
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={0.15}
              max={0.88}
              step={0.01}
              value={cutRatioSlider}
              onChange={(e) => setCutRatioSlider(parseFloat(e.target.value))}
              className="w-28 accent-rose-600 cursor-pointer"
            />
            <button
              onClick={() => onTriggerCutOnCable(selectedCableId, cutRatioSlider)}
              className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-semibold shadow-sm transition"
            >
              Simulate Fibre Cut
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
