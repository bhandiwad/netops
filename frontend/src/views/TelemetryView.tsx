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
    <div className="space-y-6">
      {/* 3GPP RAN & Site Power Cards */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-white">
              3GPP TS 32.435 5G RAN Performance, Site Battery LVD & E-Band Microwave Telemetry
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Live telemetry from Ericsson ENM & Nokia NSP across gNodeB sectors, VRLA battery banks, and 80 GHz microwave backhaul.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onTriggerScenario('ran_site_battery_lvd_countdown')}
              className="px-3 py-1.5 rounded-xl bg-amber-500/15 hover:bg-amber-500/25 text-amber-800 dark:text-amber-300 border border-amber-400/50 text-xs font-semibold flex items-center gap-1.5"
            >
              <BatteryCharging className="w-3.5 h-3.5" /> Simulate Battery LVD Countdown
            </button>
            <button
              onClick={() => onTriggerScenario('eband_microwave_rain_fade')}
              className="px-3 py-1.5 rounded-xl bg-sky-500/15 hover:bg-sky-500/25 text-sky-800 dark:text-sky-300 border border-sky-400/50 text-xs font-semibold flex items-center gap-1.5"
            >
              <CloudRain className="w-3.5 h-3.5" /> Simulate 80GHz Rain Fade
            </button>
            <button
              onClick={onToggle3gppXml}
              className="px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 text-xs font-semibold flex items-center gap-1.5"
            >
              <FileCode2 className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
              <span>{xmlPreview ? 'Hide 3GPP XML' : 'Inspect 3GPP TS 32.435 XML'}</span>
            </button>
          </div>
        </div>

        {xmlPreview && (
          <pre className="p-4 rounded-xl bg-slate-950 text-emerald-300 font-mono text-xs overflow-x-auto max-h-64">
            {xmlPreview}
          </pre>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {ranSitesPm.map((site) => {
            const isCrit = site.operational_state !== 'ENABLED_NORMAL';
            return (
              <div
                key={site.site_id}
                className={`p-4 rounded-xl border space-y-2.5 ${
                  isCrit
                    ? 'border-rose-300 bg-rose-50/40 dark:border-rose-800 dark:bg-rose-950/30'
                    : 'border-slate-200/80 dark:border-slate-800 bg-slate-50/40 dark:bg-slate-800/30'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold text-indigo-600 dark:text-indigo-400">
                    {site.site_id}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                      isCrit
                        ? 'bg-rose-100 text-rose-700 dark:bg-rose-900 dark:text-rose-200'
                        : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                    }`}
                  >
                    {site.ac_mains_status === 'FAILED'
                      ? 'ON BATTERY'
                      : site.mw_rsl_dbm && site.mw_rsl_dbm < -55
                      ? 'RAIN FADE'
                      : 'NORMAL'}
                  </span>
                </div>
                <div className="text-xs font-semibold text-slate-900 dark:text-white truncate">
                  {site.name}
                </div>
                <div className="space-y-1 text-xs font-mono text-slate-600 dark:text-slate-400">
                  <div className="flex justify-between">
                    <span>DL PRB Load:</span>
                    <span className="font-semibold text-slate-900 dark:text-white">
                      {site.dl_prb_util_pct}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>DC Bus / LVD:</span>
                    <span
                      className={`font-semibold ${
                        site.dc_bus_voltage_v < 46
                          ? 'text-rose-600 dark:text-rose-400 font-bold'
                          : 'text-emerald-600 dark:text-emerald-400'
                      }`}
                    >
                      {site.dc_bus_voltage_v}V / {site.lvd_disconnect_threshold_v}V
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Battery Reserve:</span>
                    <span className="font-semibold text-slate-900 dark:text-white">
                      {site.battery_remaining_mins} mins
                    </span>
                  </div>
                  {site.mw_link_id && site.mw_acm_modulation && (
                    <div className="pt-1 border-t border-slate-200 dark:border-slate-700 flex justify-between text-[11px]">
                      <span>80GHz RSL:</span>
                      <span className="font-semibold text-indigo-600 dark:text-indigo-400">
                        {site.mw_rsl_dbm} dBm ({site.mw_acm_modulation.split(' ')[0]})
                      </span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Subsea Wet-Plant PFE & C-OTDR Supervisor Card */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <Waves className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                Subsea Cable Landing Station — PFE & Coherent OTDR Wet-Plant Supervisor
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Monitors Power Feed Equipment (PFE) high-voltage constant-current supply and submarine repeater spans.
              </p>
            </div>
          </div>
          <button
            onClick={() => onTriggerScenario('pccw_subsea_shunt_fault')}
            className="px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm"
          >
            <Waves className="w-3.5 h-3.5" /> Simulate Subsea Repeater Shunt Fault
          </button>
        </div>

        {subseaSystems.map((sub) => (
          <div
            key={sub.id}
            className="p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 grid grid-cols-1 md:grid-cols-4 gap-4"
          >
            <div>
              <div className="text-xs text-slate-500">Subsea System</div>
              <div className="text-sm font-bold font-mono text-slate-900 dark:text-white mt-0.5">
                {sub.id}
              </div>
              <div className="text-xs text-slate-500 mt-0.5">{sub.name}</div>
            </div>
            <div>
              <div className="text-xs text-slate-500">PFE Line Voltage / Current</div>
              <div
                className={`text-sm font-bold font-mono mt-0.5 ${
                  sub.shunt_fault_detected
                    ? 'text-rose-600 dark:text-rose-400'
                    : 'text-emerald-600 dark:text-emerald-400'
                }`}
              >
                +{sub.pfe_voltage_v} V @ {sub.pfe_current_ma} mA
              </div>
              <div className="text-xs font-mono text-slate-500 mt-0.5">
                Earth Leakage: {sub.earth_leakage_ma} mA
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500">Wet-Plant Repeaters</div>
              <div className="text-sm font-bold font-mono text-slate-900 dark:text-white mt-0.5">
                {sub.repeater_count} Repeaters ({sub.total_length_km} km)
              </div>
              <div className="text-xs text-slate-500 mt-0.5">
                Branching Unit: {sub.branching_unit || 'N/A'}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500">C-OTDR Fault Status</div>
              <div className="text-sm font-bold font-mono text-slate-900 dark:text-white mt-0.5">
                {sub.shunt_fault_detected
                  ? `SHUNT @ ${sub.cotdr_shunt_distance_km} km (${sub.water_depth_m}m depth)`
                  : `All ${sub.repeater_count} Repeater Spans Nominal`}
              </div>
              {sub.fault_span && (
                <div className="text-xs text-rose-600 dark:text-rose-400 font-semibold mt-0.5">
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
