import React from 'react';
import { BatteryCharging, CloudRain, FileCode2, Waves } from 'lucide-react';
import type { RanSitePm, SubseaSystem } from '../types/api';

interface TelemetryViewProps {
  ranSitesPm: RanSitePm[];
  subseaSystems: SubseaSystem[];
  xmlPreview: string | null;
  onTriggerScenario: (scenarioId: string) => void;
  onToggle3gppXml: () => void;
}

export const TelemetryView: React.FC<TelemetryViewProps> = ({
  ranSitesPm,
  subseaSystems,
  xmlPreview,
  onTriggerScenario,
  onToggle3gppXml,
}) => {
  return (
    <div className="space-y-5">
      {/* 5G Sites, Power & Microwave */}
      <div className="bg-white dark:bg-[#111622] border border-slate-200/80 dark:border-slate-800/80 rounded-2xl p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
              5G Sites, Backup Power & Microwave
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Separates tower battery drain and heavy-rain radio fade from physical fibre cuts.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => onTriggerScenario('ran_site_battery_lvd_countdown')}
              className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs font-medium flex items-center gap-1.5 transition"
            >
              <BatteryCharging className="w-3.5 h-3.5 text-amber-500" /> Test Battery Drain
            </button>
            <button
              onClick={() => onTriggerScenario('eband_microwave_rain_fade')}
              className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs font-medium flex items-center gap-1.5 transition"
            >
              <CloudRain className="w-3.5 h-3.5 text-sky-500" /> Test Rain Fade
            </button>
            <button
              onClick={onToggle3gppXml}
              className="px-3 py-1.5 rounded-lg text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 text-xs font-medium flex items-center gap-1.5 transition"
            >
              <FileCode2 className="w-3.5 h-3.5" />
              <span>{xmlPreview ? 'Hide XML' : 'Raw XML'}</span>
            </button>
          </div>
        </div>

        {xmlPreview && (
          <pre className="p-4 rounded-xl bg-slate-950 text-slate-200 font-mono text-xs overflow-x-auto max-h-56">
            {xmlPreview}
          </pre>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
          {ranSitesPm.map((site) => {
            const isCrit = site.operational_state !== 'ENABLED_NORMAL';
            const statusText =
              site.ac_mains_status === 'FAILED'
                ? 'On Battery'
                : site.mw_rsl_dbm && site.mw_rsl_dbm < -55
                ? 'Rain Fade'
                : 'Healthy';

            return (
              <div
                key={site.site_id}
                className={`p-4 rounded-xl border space-y-3 ${
                  isCrit
                    ? 'border-rose-200 bg-rose-50/40 dark:border-rose-900/70 dark:bg-rose-950/20'
                    : 'border-slate-200/70 dark:border-slate-800 bg-slate-50/40 dark:bg-slate-900/30'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-slate-900 dark:text-white truncate">
                    {site.name}
                  </span>
                  <span
                    className={`w-2 h-2 rounded-full shrink-0 ${
                      isCrit ? 'bg-rose-500' : 'bg-emerald-500'
                    }`}
                    title={statusText}
                  />
                </div>

                <div className="space-y-1.5 text-xs text-slate-500 dark:text-slate-400">
                  <div className="flex justify-between">
                    <span>Status</span>
                    <span
                      className={`font-medium ${
                        isCrit
                          ? 'text-rose-600 dark:text-rose-400'
                          : 'text-emerald-600 dark:text-emerald-400'
                      }`}
                    >
                      {statusText}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Traffic load</span>
                    <span className="font-mono text-slate-900 dark:text-white">
                      {site.dl_prb_util_pct}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>DC power</span>
                    <span
                      className={`font-mono ${
                        site.dc_bus_voltage_v < 46
                          ? 'text-rose-600 dark:text-rose-400 font-semibold'
                          : 'text-slate-900 dark:text-white'
                      }`}
                    >
                      {site.dc_bus_voltage_v} V
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Battery left</span>
                    <span className="font-mono text-slate-900 dark:text-white">
                      {site.battery_remaining_mins} min
                    </span>
                  </div>
                  {site.mw_link_id && site.mw_acm_modulation && (
                    <div className="pt-1.5 border-t border-slate-200/70 dark:border-slate-800 flex justify-between">
                      <span>Microwave</span>
                      <span className="font-mono text-slate-700 dark:text-slate-300">
                        {site.mw_rsl_dbm} dBm
                      </span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Subsea Cable Landings */}
      <div className="bg-white dark:bg-[#111622] border border-slate-200/80 dark:border-slate-800/80 rounded-2xl p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
              Subsea Cable Landing Stations
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Monitors submarine power feed voltage and repeater spans to separate sea faults from land cuts.
            </p>
          </div>
          <button
            onClick={() => onTriggerScenario('pccw_subsea_shunt_fault')}
            className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs font-medium flex items-center gap-1.5 transition"
          >
            <Waves className="w-3.5 h-3.5 text-indigo-500" /> Test Subsea Fault
          </button>
        </div>

        {subseaSystems.map((sub) => (
          <div
            key={sub.id}
            className="p-4 rounded-xl border border-slate-200/70 dark:border-slate-800 bg-slate-50/40 dark:bg-slate-900/30 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs"
          >
            <div>
              <div className="text-slate-500">Cable System</div>
              <div className="text-sm font-semibold text-slate-900 dark:text-white mt-0.5">
                {sub.name}
              </div>
              <div className="font-mono text-[11px] text-slate-400 mt-0.5">{sub.id}</div>
            </div>
            <div>
              <div className="text-slate-500">Power Feed</div>
              <div
                className={`text-sm font-mono font-semibold mt-0.5 ${
                  sub.shunt_fault_detected
                    ? 'text-rose-600 dark:text-rose-400'
                    : 'text-emerald-600 dark:text-emerald-400'
                }`}
              >
                +{sub.pfe_voltage_v} V · {sub.pfe_current_ma} mA
              </div>
              <div className="text-[11px] text-slate-400 mt-0.5">
                Leakage: {sub.earth_leakage_ma} mA
              </div>
            </div>
            <div>
              <div className="text-slate-500">Subsea Span</div>
              <div className="text-sm font-mono font-semibold text-slate-900 dark:text-white mt-0.5">
                {sub.total_length_km} km · {sub.repeater_count} repeaters
              </div>
              <div className="text-[11px] text-slate-400 mt-0.5">
                Landing: {sub.cls_node}
              </div>
            </div>
            <div>
              <div className="text-slate-500">Status</div>
              <div className="text-sm font-semibold text-slate-900 dark:text-white mt-0.5">
                {sub.shunt_fault_detected
                  ? `Shunt at ${sub.cotdr_shunt_distance_km} km (${sub.water_depth_m} m depth)`
                  : 'All spans healthy'}
              </div>
              {sub.fault_span && (
                <div className="text-[11px] text-rose-600 dark:text-rose-400 font-medium mt-0.5">
                  {sub.fault_span}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
