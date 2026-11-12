import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import { Crosshair, X } from 'lucide-react';

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
  onClearCable?: () => void;
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
  onClearCable,
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

  const [mapError, setMapError] = useState<string | null>(null);

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    let map: maplibregl.Map;
    try {
      map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: {
        version: 8,
        sources: {
          'esri-light-base': {
            type: 'raster',
            tiles: [
              'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
            ],
            tileSize: 256,
            attribution: '© Esri, HERE, Garmin, OpenStreetMap',
          },
          'esri-light-ref': {
            type: 'raster',
            tiles: [
              'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}',
            ],
            tileSize: 256,
          },
          'esri-dark-base': {
            type: 'raster',
            tiles: [
              'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
            ],
            tileSize: 256,
          },
          'esri-dark-ref': {
            type: 'raster',
            tiles: [
              'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}',
            ],
            tileSize: 256,
          },
        },
        layers: [
          {
            id: 'carto-light-layer',
            type: 'raster',
            source: 'esri-light-base',
            minzoom: 0,
            maxzoom: 19,
            layout: { visibility: isLight ? 'visible' : 'none' },
          },
          {
            id: 'carto-light-labels',
            type: 'raster',
            source: 'esri-light-ref',
            minzoom: 0,
            maxzoom: 19,
            layout: { visibility: isLight ? 'visible' : 'none' },
          },
          {
            id: 'carto-dark-layer',
            type: 'raster',
            source: 'esri-dark-base',
            minzoom: 0,
            maxzoom: 19,
            layout: { visibility: isLight ? 'none' : 'visible' },
          },
          {
            id: 'carto-dark-labels',
            type: 'raster',
            source: 'esri-dark-ref',
            minzoom: 0,
            maxzoom: 19,
            layout: { visibility: isLight ? 'none' : 'visible' },
          },
        ],
      },
      center: [55.245, 25.155],
      zoom: 10.9,
      pitch: 12,
    });
    } catch (err) {
      console.warn('WebGL map unavailable in this browser environment:', err);
      setMapError('Interactive WebGL map requires hardware acceleration.');
      return;
    }

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), 'bottom-right');
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    ['carto-light-layer', 'carto-light-labels'].forEach((lid) => {
      if (map.getLayer(lid)) {
        map.setLayoutProperty(lid, 'visibility', isLight ? 'visible' : 'none');
      }
    });
    ['carto-dark-layer', 'carto-dark-labels'].forEach((lid) => {
      if (map.getLayer(lid)) {
        map.setLayoutProperty(lid, 'visibility', isLight ? 'none' : 'visible');
      }
    });
  }, [isLight]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const renderLayers = () => {
      ['carto-light-layer', 'carto-light-labels'].forEach((lid) => {
        if (map.getLayer(lid)) {
          map.setLayoutProperty(lid, 'visibility', isLight ? 'visible' : 'none');
        }
      });
      ['carto-dark-layer', 'carto-dark-labels'].forEach((lid) => {
        if (map.getLayer(lid)) {
          map.setLayoutProperty(lid, 'visibility', isLight ? 'none' : 'visible');
        }
      });

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
            'line-color': ['case', ['!=', ['get', 'bridge'], ''], '#d97706', '#94a3b8'],
            'line-width': ['case', ['!=', ['get', 'bridge'], ''], 2.5, 1.2],
            'line-dasharray': [2, 2],
            'line-opacity': 0.55,
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
            'line-width': [
              'case',
              ['==', ['get', 'faulted'], 1],
              10,
              ['==', ['get', 'selected'], 1],
              8,
              0,
            ],
            'line-opacity': 0.25,
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
              ['==', ['get', 'selected'], 1],
              '#4f46e5',
              ['==', ['get', 'role'], 'trunk'],
              '#0284c7',
              ['==', ['get', 'role'], 'dark'],
              '#7c3aed',
              '#0d9488',
            ],
            'line-width': [
              'case',
              ['==', ['get', 'faulted'], 1],
              4,
              ['==', ['get', 'selected'], 1],
              3.5,
              ['==', ['get', 'role'], 'trunk'],
              2.6,
              2,
            ],
            'line-opacity': 0.88,
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
            'line-width': 2,
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
      const impactedCustomerIds = new Set<string>(
        (activeIncident?.impact?.impacted_services || []).map((s: any) => String(s.customer_id || ''))
      );
      const impactedRanIds = new Set<string>(
        (activeIncident?.impact?.impacted_ran_sites || []).map((r: any) => String(r.site_id || ''))
      );

      // Subtle manhole dots
      if (showManholes) {
        (gis?.manholes || []).forEach((mh) => {
          if (mh.kind !== 'junction') return;
          const el = document.createElement('div');
          el.className =
            'w-2.5 h-2.5 rounded-full bg-white dark:bg-slate-900 border-2 border-amber-500 hover:scale-150 transition-transform cursor-pointer shadow-sm';
          el.title = `${mh.name} (${mh.id}) · Slack loop: ${mh.slack_coil_m} m`;
          const marker = new maplibregl.Marker({ element: el })
            .setLngLat([mh.lon, mh.lat])
            .setPopup(
              new maplibregl.Popup({ offset: 8, closeButton: false }).setHTML(
                `<div class="text-slate-900 text-xs font-sans px-1 py-0.5">
                  <div class="font-semibold">${mh.name}</div>
                  <div class="text-slate-500 font-mono text-[11px]">${mh.id} · ${mh.slack_coil_m} m slack</div>
                </div>`
              )
            )
            .addTo(map);
          markersRef.current.push(marker);
        });
      }

      // Clean minimal markers for POPs, Customers & 5G Sites (labels only expand when impacted!)
      Object.entries(nodesObj).forEach(([nid, ninfo]: [string, any]) => {
        if (ninfo.kind === 'pop') {
          const el = document.createElement('div');
          el.className =
            'w-3.5 h-3.5 rounded-full bg-slate-900 dark:bg-sky-400 border-2 border-white dark:border-slate-950 shadow-md hover:scale-125 transition-transform cursor-pointer';
          el.title = `${ninfo.name} (${nid})`;
          const marker = new maplibregl.Marker({ element: el })
            .setLngLat([ninfo.lon, ninfo.lat])
            .setPopup(
              new maplibregl.Popup({ offset: 8, closeButton: false }).setHTML(
                `<div class="text-slate-900 text-xs font-sans px-1 py-0.5">
                  <div class="font-semibold">${ninfo.name}</div>
                  <div class="text-slate-500 font-mono text-[11px]">Core POP · ${nid}</div>
                </div>`
              )
            )
            .addTo(map);
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
          if (isHit) {
            el.className =
              'px-2 py-0.5 rounded-full bg-rose-600 border-2 border-white text-white text-[10px] font-semibold shadow-md cursor-pointer';
            el.innerText = ninfo.name.split(' ').slice(0, 2).join(' ');
          } else {
            el.className =
              'w-3 h-3 rounded-full bg-emerald-500 border-2 border-white dark:border-slate-950 shadow-sm hover:scale-125 transition-transform cursor-pointer';
          }
          el.title = `${ninfo.name} (Customer Site)`;
          const marker = new maplibregl.Marker({ element: el })
            .setLngLat([ninfo.lon, ninfo.lat])
            .setPopup(
              new maplibregl.Popup({ offset: 8, closeButton: false }).setHTML(
                `<div class="text-slate-900 text-xs font-sans px-1 py-0.5">
                  <div class="font-semibold">${ninfo.name}</div>
                  <div class="text-slate-500 text-[11px]">Enterprise Site</div>
                </div>`
              )
            )
            .addTo(map);
          markersRef.current.push(marker);
        } else if (ninfo.kind === 'cellsite' && showMobilePack && showRanSites) {
          const isDown = impactedRanIds.has(nid);
          const el = document.createElement('div');
          if (isDown) {
            el.className =
              'px-2 py-0.5 rounded-full bg-rose-600 border-2 border-white text-white text-[10px] font-mono font-semibold shadow-md cursor-pointer';
            el.innerText = `5G · ${nid.replace('RAN_', '')}`;
          } else {
            el.className =
              'w-2.5 h-2.5 rounded-full bg-indigo-500 border border-white dark:border-slate-950 shadow-sm hover:scale-125 transition-transform cursor-pointer';
          }
          el.title = `${ninfo.name} (5G Site)`;
          const marker = new maplibregl.Marker({ element: el })
            .setLngLat([ninfo.lon, ninfo.lat])
            .setPopup(
              new maplibregl.Popup({ offset: 8, closeButton: false }).setHTML(
                `<div class="text-slate-900 text-xs font-sans px-1 py-0.5">
                  <div class="font-semibold">${ninfo.name}</div>
                  <div class="text-slate-500 font-mono text-[11px]">5G Site · ${nid}</div>
                </div>`
              )
            )
            .addTo(map);
          markersRef.current.push(marker);
        }
      });

      // Active Fault Pin
      if (fl && fl.lat && fl.lon) {
        if (fl.naive_lat && fl.naive_lon && fl.dispatch_error_avoided_m > 5) {
          const naiveEl = document.createElement('div');
          naiveEl.className =
            'px-2 py-0.5 rounded-md bg-amber-500 text-slate-950 border border-white text-[10px] font-medium shadow-sm whitespace-nowrap';
          naiveEl.innerHTML = `Raw OTDR (+${fl.dispatch_error_avoided_m}m off)`;
          const naiveMarker = new maplibregl.Marker({ element: naiveEl, offset: [0, -18] })
            .setLngLat([fl.naive_lon, fl.naive_lat])
            .addTo(map);
          markersRef.current.push(naiveMarker);
        }

        let badgeLabel = `Fibre Cut · ${fl.corrected_trench_distance_m ?? 0} m`;
        if (fl.dying_gasp_confirmed) badgeLabel = 'Power Outage · Cable Intact';
        else if (fl.dc_bus_voltage_v)
          badgeLabel = `Site Battery Low (${fl.battery_remaining_mins}m left)`;
        else if (fl.mw_link_id) badgeLabel = 'Microwave Rain Fade';
        else if (fl.subsea_cable_id) badgeLabel = `Subsea Fault · ${fl.cotdr_shunt_distance_km} km`;

        const faultEl = document.createElement('div');
        faultEl.className = 'relative flex items-center justify-center';
        faultEl.innerHTML = `
          <div class="w-9 h-9 rounded-full bg-rose-500/35 fault-pulse-ring absolute"></div>
          <div class="px-2.5 py-1 rounded-full bg-rose-600 border-2 border-white text-white text-[11px] font-semibold shadow-lg relative z-10 whitespace-nowrap">
            ${badgeLabel}
          </div>
        `;
        const faultMarker = new maplibregl.Marker({ element: faultEl, offset: [0, 18] })
          .setLngLat([fl.lon, fl.lat])
          .addTo(map);
        markersRef.current.push(faultMarker);

        map.flyTo({ center: [fl.lon, fl.lat], zoom: 12.8, duration: 900 });
      }
    };

    if (map.isStyleLoaded()) {
      renderLayers();
    } else {
      map.once('load', renderLayers);
    }
  }, [
    gis,
    topology,
    activeIncident,
    selectedCableId,
    showDucts,
    showManholes,
    showRanSites,
    showMobilePack,
    isLight,
  ]);

  return (
    <div className="relative w-full h-full rounded-xl overflow-hidden border border-slate-200/80 dark:border-slate-800 bg-slate-100 dark:bg-slate-950">
      <div ref={mapContainerRef} className="w-full h-full" />
      {mapError && (
        <div className="absolute inset-0 flex items-center justify-center text-xs text-slate-500 p-4 text-center">
          {mapError}
        </div>
      )}

      {/* Minimal Layer Pills */}
      <div className="absolute top-3 left-3 z-10 flex items-center gap-1 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md border border-slate-200/80 dark:border-slate-800 rounded-lg p-1 text-[11px] shadow-sm">
        <button
          onClick={() => setShowDucts(!showDucts)}
          className={`px-2.5 py-1 rounded-md font-medium transition ${
            showDucts
              ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900'
              : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
          }`}
        >
          Ducts
        </button>
        <button
          onClick={() => setShowManholes(!showManholes)}
          className={`px-2.5 py-1 rounded-md font-medium transition ${
            showManholes
              ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900'
              : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
          }`}
        >
          Chambers
        </button>
        {showMobilePack && (
          <button
            onClick={() => setShowRanSites(!showRanSites)}
            className={`px-2.5 py-1 rounded-md font-medium transition ${
              showRanSites
                ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900'
                : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
            }`}
          >
            5G Sites
          </button>
        )}
      </div>

      {/* Subtle Map Key */}
      <div className="absolute top-3 right-3 z-10 hidden sm:flex items-center gap-3 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md border border-slate-200/80 dark:border-slate-800 rounded-lg px-3 py-1.5 text-[11px] text-slate-600 dark:text-slate-300 shadow-sm">
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-slate-900 dark:bg-sky-400" /> POP
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-500" /> Customer
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-amber-500" /> Chamber
        </span>
        {showMobilePack && (
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-indigo-500" /> 5G
          </span>
        )}
      </div>

      {/* Selected Cable Cut Bar */}
      {selectedCableId && (
        <div className="absolute bottom-3 left-3 right-12 z-10 bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border border-slate-200 dark:border-slate-700 rounded-xl px-3.5 py-2 flex flex-wrap items-center justify-between gap-3 text-xs shadow-md">
          <div className="flex items-center gap-2">
            <Crosshair className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
            <span className="font-mono font-semibold text-slate-900 dark:text-white">
              {selectedCableId}
            </span>
            <span className="text-slate-500 dark:text-slate-400">
              Cut at{' '}
              <strong className="font-mono text-slate-900 dark:text-white">
                {Math.round(cutRatioSlider * 100)}%
              </strong>
            </span>
          </div>
          <div className="flex items-center gap-2.5">
            <input
              type="range"
              min={0.15}
              max={0.88}
              step={0.01}
              value={cutRatioSlider}
              onChange={(e) => setCutRatioSlider(parseFloat(e.target.value))}
              className="w-24 accent-rose-600 cursor-pointer"
            />
            <button
              onClick={() => onTriggerCutOnCable(selectedCableId, cutRatioSlider)}
              className="px-3 py-1 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-medium transition"
            >
              Simulate Cut
            </button>
            {onClearCable && (
              <button
                onClick={onClearCable}
                className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                title="Clear selection"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
