/**
 * Typed Domain & API Contracts for the Telco NOC Copilot Frontend.
 *
 * Mirrors the backend Pydantic v2 models in `backend/app/schemas/models.py`
 * so frontend engineers get full IDE autocomplete and compile-time safety.
 */

export type ThemeMode = 'light' | 'dark';
export type PrimaryNavId = 'workspace' | 'topology' | 'telemetry' | 'connectors';
export type StageTabId = 'map' | 'otdr' | 'graph' | 'stream';
export type CopilotTabId = 'diagnosis' | 'runbook' | 'actions';

export interface Connector {
  id: string;
  name: string;
  oem_vendor: string;
  category: string;
  protocol: string;
  endpoint_url: string;
  mode: 'emulator' | 'live' | 'live_listener' | string;
  enabled: boolean;
  status: string;
  latency_ms: number;
  records_synced: number;
  last_sync_at?: string;
  config_json?: Record<string, unknown>;
}

export interface OspDuct {
  id: string;
  node_a: string;
  node_b: string;
  bridge?: string | null;
  trench_length_m: number;
  coords_json: [number, number][];
}

export interface OspManhole {
  id: string;
  node_id: string;
  name: string;
  kind: string;
  lat: number;
  lon: number;
  slack_coil_m: number;
}

export interface OspSplice {
  manhole_id: string;
  node_id: string;
  name: string;
  lat: number;
  lon: number;
  trench_distance_m: number;
  optical_distance_m: number;
  slack_added_m: number;
}

export interface OspCable {
  id: string;
  path_nodes: string[];
  duct_ids: string[];
  bridges: string[];
  fibres: number;
  role: string;
  helix_factor: number;
  trench_length_m: number;
  optical_length_m: number;
  splices_json: OspSplice[];
  coords_json: [number, number][];
}

export interface OspGisBundle {
  ducts: OspDuct[];
  manholes: OspManhole[];
  cables: OspCable[];
}

export interface OtdrKeyEvent {
  event_number: number;
  distance_m: number;
  slope_db_per_km?: number;
  splice_loss_db: number;
  refl_loss_db?: number;
  refl_db?: number;
  event_code: string;
  comment: string;
}

export interface FaultLocation {
  cable_id?: string;
  cut_cables?: string[];
  launch_node?: string;
  optical_distance_m?: number;
  cable_optical_length_m?: number;
  cable_trench_length_m?: number;
  helix_factor?: number;
  slack_Coils_subtracted_m?: number;
  corrected_trench_distance_m?: number;
  naive_uncorrected_trench_m?: number;
  dispatch_error_avoided_m?: number;
  lat?: number;
  lon?: number;
  naive_lat?: number;
  naive_lon?: number;
  upstream_manhole?: OspSplice;
  downstream_manhole?: OspSplice;
  distance_from_upstream_manhole_m?: number;
  fiber_intact?: boolean;
  dying_gasp_confirmed?: boolean;
  dispatch_verdict?: string;
  [key: string]: unknown;
}

export interface OtdrTraceData {
  filename?: string;
  cable_id: string;
  wavelength_nm: number;
  supplier_name: string;
  unit_name: string;
  serial_number?: string;
  refractive_index?: number;
  pulse_width_ns?: number;
  range_m?: number;
  sample_spacing_m?: number;
  crc_valid: boolean;
  binary_size_bytes?: number;
  fault_distance_optical_m?: number | null;
  key_events: OtdrKeyEvent[];
  trace_points_db: number[];
  postgis_localization?: FaultLocation | null;
}

export interface SrlgFinding {
  service_id: string;
  service_type: string;
  bandwidth: string;
  customer_id: string;
  customer_name: string;
  sla_tier: string;
  ordered_diverse: boolean;
  diversity_compliant: boolean;
  leg_a_name: string;
  leg_b_name: string;
  shared_cables: string[];
  shared_ducts: string[];
  shared_chambers: string[];
  shared_bridges: string[];
  risk_summary: string;
}

export interface ImpactedService {
  service_id: string;
  service_type: string;
  bandwidth: string;
  customer_id: string;
  customer_name: string;
  segment: string;
  sla_tier: string;
  mttr_target_hours: number;
  penalty_per_hour_aed: number;
  ordered_diverse: boolean;
  outage_state: 'COMPLETE_OUTAGE' | 'DEGRADED_REDUNDANCY_LOST' | string;
  legs: { leg: string; status: string; cable?: string; och?: string }[];
}

export interface IncidentImpact {
  impacted_service_count: number;
  complete_outage_count: number;
  total_sla_penalty_per_hour_aed: number;
  four_hour_sla_exposure_aed: number;
  impacted_services: ImpactedService[];
  impacted_ran_sites: { site_id: string; problem: string; cells: string[]; is_cascaded_tail: boolean }[];
  impacted_5g_cell_count: number;
  alarm_collapse_ratio: string;
  alarms_by_oem: Record<string, number>;
  alarms_by_layer: Record<string, number>;
}

export interface ProposedAction {
  action_id: string;
  target_system: string;
  connector_id: string;
  action_type: string;
  title: string;
  description: string;
  payload: Record<string, unknown>;
  requires_approval: boolean;
}

export interface ExecutedAction extends ProposedAction {
  status: string;
  approved_by: string;
  executed_at: string;
  result?: { external_id?: string; url?: string; [key: string]: unknown };
}

export interface AlarmRecord {
  alarm_id: string;
  incident_id?: string;
  scenario_id?: string;
  source_oem: string;
  protocol: string;
  layer: string;
  resource_id: string;
  node_id: string;
  severity: 'CRITICAL' | 'MAJOR' | 'MINOR' | 'WARNING' | 'CLEARED' | string;
  specific_problem: string;
  probable_cause: string;
  raw_text: string;
  raised_at: string;
}

export interface AiCopilotAnalysis {
  model_used: string;
  matched_runbook_id: string;
  matched_runbook_title: string;
  pgvector_cosine_similarity: number;
  top_matched_runbooks: { id: string; title: string; cosine_similarity: number }[];
  past_tickets: { ticket_id: string; date: string; summary: string; mttr_hours: number }[];
  cited_alarm_ids: string[];
  narrative_md: string;
  generated_at: string;
}

export interface Incident {
  incident_id: string;
  title: string;
  status: 'PENDING_APPROVAL' | 'APPROVED_EXECUTED' | 'RESOLVED_VERIFIED' | string;
  severity: string;
  root_cause_type: string;
  root_cause_resource: string;
  root_cause_summary: string;
  confidence: number;
  alarm_count: number;
  fault_location: FaultLocation;
  impact: IncidentImpact;
  srlg_findings: SrlgFinding[];
  otdr_trace: OtdrTraceData | Record<string, never>;
  ai_copilot: AiCopilotAnalysis;
  proposed_actions: ProposedAction[];
  executed_actions: ExecutedAction[];
  alarms: AlarmRecord[];
  created_at?: string;
  updated_at?: string;
}

export interface DependencyGraphData {
  nodes: {
    id: string;
    label: string;
    layer_index: number;
    layer_name: string;
    subtitle: string;
    status: string;
  }[];
  edges: { source: string; target: string; status: string }[];
}

export interface RanSitePm {
  site_id: string;
  name: string;
  vendor: string;
  pop_anchor: string;
  backhaul_type: string;
  cells: string[];
  operational_state: string;
  dl_prb_util_pct: number;
  ul_prb_util_pct: number;
  rrc_conn_success_pct: number;
  erab_drop_rate_pct: number;
  ul_sinr_db: number;
  active_ues: number;
  ac_mains_status: string;
  dc_bus_voltage_v: number;
  lvd_disconnect_threshold_v: number;
  battery_remaining_mins: number;
  cabinet_temp_c: number;
  mw_link_id?: string | null;
  mw_rsl_dbm?: number | null;
  mw_snr_db?: number | null;
  mw_acm_modulation?: string | null;
  rain_rate_mm_hr?: number | null;
}

export interface SubseaSystem {
  id: string;
  name: string;
  cls_node: string;
  pfe_id: string;
  total_length_km: number;
  repeater_count: number;
  branching_unit?: string;
  design_capacity_tbps: number;
  operational_state: string;
  pfe_voltage_v: number;
  pfe_current_ma: number;
  earth_leakage_ma: number;
  shunt_fault_detected: boolean;
  cotdr_shunt_distance_km?: number | null;
  fault_span?: string | null;
  water_depth_m?: number | null;
}

export interface StormBenchmarkResult {
  storm_size: number;
  flaps_suppressed: number;
  duplicates_dropped: number;
  unique_signatures_evaluated: number;
  child_cascades_collapsed: number;
  root_causes_identified: number;
  root_cause_breakdown: Record<string, number>;
  noise_reduction_pct: number;
  processing_latency_ms: number;
  throughput_alarms_per_sec: number;
  precision_pct: number;
  recall_pct: number;
  executed_at: string;
}

export interface OperatorProfile {
  id: string;
  name: string;
  short_name: string;
  region: string;
  currency: string;
  active_packs: string[];
  active_oems: string[];
  description: string;
}

export interface FaultScenario {
  id: string;
  title: string;
  category: string;
  operators: string[];
  summary: string;
  fault_type: string;
}

export interface OverviewResponse {
  connectors: Connector[];
  gis: OspGisBundle;
  topology: Record<string, unknown>;
  bss: Record<string, unknown>;
  ciena_fres: Record<string, unknown>;
  nokia_optical: Record<string, unknown>;
  ran_telemetry: {
    pm_telemetry?: RanSitePm[];
    subsea_systems?: SubseaSystem[];
  };
  dependency_graph: DependencyGraphData;
  last_benchmark: StormBenchmarkResult | null;
  srlg_findings: SrlgFinding[];
  incidents: Incident[];
  alarms: AlarmRecord[];
  wire_packets: { protocol: string; port: number; source_ip: string; payload: string }[];
  scenarios: FaultScenario[];
  operator_profiles: Record<string, OperatorProfile>;
  external_tickets: {
    jira_issues: unknown[];
    servicenow_incidents: unknown[];
    servicenow_work_orders: unknown[];
  };
  llm_config: {
    provider: string;
    model: string;
    api_key_configured: boolean;
  };
}
