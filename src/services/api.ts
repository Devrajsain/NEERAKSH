/**
 * SlickTrace API Client
 * 
 * Centralized service layer for all backend API interactions.
 * All endpoints are proxied through Vite's dev server to avoid CORS issues.
 */

const API_BASE = '/api/v1';

// ─── Types ──────────────────────────────────────────────────────────────────

export interface CaseResponse {
  id: string;
  name: string;
  status: string;
  location_name: string;
  center_latitude: number;
  center_longitude: number;
  summary_json: any;
  created_at: string;
}

export interface SpillResponse {
  id: string;
  case_id: string;
  confidence_score: number;
  confidence_label: string;
  area_km2: number;
  length_km: number;
  width_km: number;
  est_volume_bbl: number;
  detection_timestamp: string;
  satellite_source: string;
  polygon_geojson: any;
  origin_latitude: number;
  origin_longitude: number;
  origin_timestamp: string;
  drift_trajectory_json: any[];
}

export interface RawEvidenceMetrics {
  closest_approach_distance_km: number;
  closest_approach_time?: string | null;
  time_offset_minutes: number;
  inside_uncertainty_zone: boolean;
  position_at_origin?: { latitude: number; longitude: number; sog?: number; cog?: number; exact?: boolean } | null;
  sog_at_origin_kn?: number | null;
  baseline_median_sog_kn?: number | null;
  event_median_sog_kn?: number | null;
  speed_reduction_ratio?: number | null;
  minimum_sog_kn?: number | null;
  course_change_degrees?: number | null;
  dwell_minutes_inside_zone: number;
  dwell_minutes_near_zone: number;
  gap_duration_minutes?: number | null;
  gap_distance_to_origin_km?: number | null;
  gap_time_offset_minutes?: number | null;
  gap_relevance_score?: number | null;
  approach_bearing_deg?: number | null;
  departure_bearing_deg?: number | null;
  reverse_drift_bearing_deg?: number | null;
  approach_alignment_deg?: number | null;
  departure_alignment_deg?: number | null;
}

export interface VesselResponse {
  id: string;
  case_id: string;
  mmsi: string;
  name: string;
  type: string;
  flag: string;
  overall_score: number;
  proximity_score: number;
  trajectory_score: number;
  behavioral_score: number;
  warning_flags: string[];
  current_latitude: number;
  current_longitude: number;
  heading_deg: number;
  speed_kts?: number | null;

  // Feature 3 Extended Evidence Attributes
  composite_score?: number;
  risk_class?: 'VERY HIGH' | 'HIGH' | 'MODERATE' | 'LOW' | string;
  scoring_mode?: string;
  origin_presence_score?: number;
  behavior_anomaly_score?: number;
  dwell_time_score?: number;
  ais_gap_score?: number;
  approach_departure_score?: number | null;
  evidence_metrics?: RawEvidenceMetrics | any;
  quality_flags?: string[];
  trajectory_geojson?: any;
  explanation?: string;
  created_at?: string;
}

export interface Feature2ResultResponse {
  id: string;
  case_id: string;
  status: string;
  processing_mode: string;
  origin_latitude: number | null;
  origin_longitude: number | null;
  origin_timestamp: string | null;
  origin_confidence_score: number | null;
  origin_uncertainty_radius_km: number | null;
  release_window_start: string | null;
  release_window_end: string | null;
  forecast_json: any;
  geojson_feature_collection: any;
  pipeline_response_json: any;
  drift_trajectory?: any[];
  error_message: string | null;
  created_at: string;
}

export interface DashboardCaseData {
  case: CaseResponse;
  spill: SpillResponse | null;
  vessels: VesselResponse[];
  feature2: Feature2ResultResponse | null;
}

// ─── API Functions ──────────────────────────────────────────────────────────

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const errorBody = await res.text().catch(() => '');
    throw new Error(`API error ${res.status}: ${errorBody || res.statusText}`);
  }
  return res.json();
}

/** Create a new forensic case with file uploads. */
export async function createCase(
  name: string,
  locationName: string,
  centerLatitude?: number | null,
  centerLongitude?: number | null,
  imageFile?: File | null,
  csvFile?: File | null,
  testMode: boolean = false,
): Promise<CaseResponse> {
  const formData = new FormData();
  formData.append('name', name);
  formData.append('location_name', locationName);
  if (centerLatitude !== undefined && centerLatitude !== null && !isNaN(centerLatitude)) {
    formData.append('center_latitude', String(centerLatitude));
  }
  if (centerLongitude !== undefined && centerLongitude !== null && !isNaN(centerLongitude)) {
    formData.append('center_longitude', String(centerLongitude));
  }

  if (imageFile) {
    formData.append('image_file', imageFile);
  }
  if (csvFile) {
    formData.append('csv_file', csvFile);
  }
  if (testMode) {
    formData.append('test_mode', 'true');
  }

  const url = `${API_BASE}/cases/`;
  console.log("=== DEBUG REQUEST ===");
  console.log("URL:", url);
  console.log("FormData Keys:");
  for (let [key, value] of formData.entries()) {
    if (value instanceof File) {
      console.log(`- ${key}: File(name="${value.name}", type="${value.type}", size=${value.size})`);
    } else {
      console.log(`- ${key}: ${value}`);
    }
  }
  console.log("test_mode (raw boolean passed):", testMode);
  // observation_time is not being passed to this function or appended to FormData!
  console.log("observation_time: NOT PROVIDED IN FRONTEND CODE");
  console.log("=====================");

  const res = await fetch(url, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const errorBody = await res.text().catch(() => '');
    console.error("=== DEBUG RESPONSE ERROR ===");
    console.error("HTTP Status:", res.status, res.statusText);
    console.error("Raw Response Body:", errorBody);
    console.error("============================");
    throw new Error(`Failed to create case: ${res.status} ${errorBody}`);
  }

  return res.json();
}

/** Continues Feature 2 execution with user-entered coordinates. */
export async function continueCaseFeature2(
  caseId: string,
  latitude: number,
  longitude: number,
): Promise<CaseResponse> {
  const formData = new FormData();
  formData.append('latitude', String(latitude));
  formData.append('longitude', String(longitude));

  const res = await fetch(`${API_BASE}/cases/${caseId}/continue-feature2`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const errorBody = await res.text().catch(() => '');
    throw new Error(`Feature 2 execution failed: ${res.status} ${errorBody}`);
  }

  return res.json();
}

/** List all forensic cases. */
export async function listCases(): Promise<CaseResponse[]> {
  return fetchJSON<CaseResponse[]>(`${API_BASE}/cases/`);
}

/** Delete a case by ID. */
export async function deleteCase(caseId: string): Promise<{ message: string; id: string }> {
  const res = await fetch(`${API_BASE}/cases/${caseId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const errorBody = await res.text().catch(() => '');
    throw new Error(`Failed to delete case: ${res.status} ${errorBody}`);
  }
  return res.json();
}

/** Get a single case by ID. */
export async function getCase(caseId: string): Promise<CaseResponse> {
  return fetchJSON<CaseResponse>(`${API_BASE}/cases/${caseId}`);
}

/** Get spill detection data for a case. */
export async function getCaseSpill(caseId: string): Promise<SpillResponse> {
  return fetchJSON<SpillResponse>(`${API_BASE}/cases/${caseId}/spill`);
}

/** Get vessel attribution records for a case with deterministic sorting. */
export async function getCaseVessels(caseId: string, sort: string = 'score', limit?: number): Promise<VesselResponse[]> {
  const params = new URLSearchParams({ sort });
  if (limit) params.append('limit', String(limit));
  return fetchJSON<VesselResponse[]>(`${API_BASE}/cases/${caseId}/vessels?${params.toString()}`);
}

/** Get a single vessel attribution record including full forensic explanation and evidence metrics. */
export async function getCaseVesselByMmsi(caseId: string, mmsi: string): Promise<VesselResponse> {
  return fetchJSON<VesselResponse>(`${API_BASE}/cases/${caseId}/vessels/${mmsi}`);
}

/** Get Feature 2 results for a case. */
export async function getFeature2Results(caseId: string): Promise<Feature2ResultResponse> {
  return fetchJSON<Feature2ResultResponse>(`${API_BASE}/feature2-results/${caseId}`);
}

/** Get Feature 2 GeoJSON for map rendering. */
export async function getFeature2GeoJSON(caseId: string): Promise<any> {
  return fetchJSON<any>(`${API_BASE}/feature2-results/${caseId}/geojson`);
}

/** Get Feature 2 forecast horizons. */
export async function getFeature2Forecast(caseId: string): Promise<any> {
  return fetchJSON<any>(`${API_BASE}/feature2-results/${caseId}/forecast`);
}

/** 
 * Load all dashboard data for a case in parallel.
 * Gracefully handles missing sub-resources.
 */
export async function loadDashboardData(caseId: string): Promise<DashboardCaseData> {
  const [caseData, spill, vessels, feature2] = await Promise.all([
    getCase(caseId),
    getCaseSpill(caseId).catch(() => null),
    getCaseVessels(caseId).catch(() => []),
    getFeature2Results(caseId).catch(() => null),
  ]);

  return {
    case: caseData,
    spill,
    vessels,
    feature2,
  };
}

export interface ConfidenceDiagnostic {
  name: string;
  value: any;
  threshold?: any;
  status: 'PASS' | 'FAIL' | 'WARNING' | 'INDETERMINATE';
  message: string;
}

export interface ConfidenceFlag {
  flag: string;
  severity: 'INFO' | 'WARNING' | 'CRITICAL';
  description: string;
}

export interface SupplementalDeterministicEvidence {
  feature3_overall_score?: number | null;
  metrics: any;
  risk_class?: string | null;
}

export interface FinalCandidateRecord {
  candidate_id: string;
  mmsi: string;
  release_latitude: number;
  release_longitude: number;
  release_timestamp: string;
  
  evaluation_status: string;
  prior_probability: number;
  likelihood: number;
  posterior_probability: number;
  
  confidence_level: string;
  confidence_diagnostics: ConfidenceDiagnostic[];
  confidence_flags: ConfidenceFlag[];
  
  supplemental_deterministic_evidence?: SupplementalDeterministicEvidence;
}

export interface AttributionProvenance {
  environmental_data_provider?: string | null;
  simulation_engine?: string | null;
  bayesian_configuration: any;
  truncation_metadata: any;
}

export interface FinalAttributionReport {
  spill_id: string;
  report_timestamp: string;
  status: 'SUCCESS' | 'NO_POSITIVE_LIKELIHOOD' | 'VALIDATION_ERROR';
  
  hypothesis_space_truncated: boolean;
  candidate_limit?: number | null;
  total_valid_candidates?: number | null;
  returned_candidate_count: number;
  evaluated_candidate_count: number;
  unavailable_candidate_count: number;
  unavailable_candidate_ids: string[];
  prior_mode: string;
  
  normalization_constant: number;
  log_normalization_constant: number;
  posterior_sum: number;
  
  candidates: FinalCandidateRecord[];
  
  provenance: AttributionProvenance;
  limitations: string[];
  warnings: string[];
  errors: string[];
}

export interface BayesianPipelineRequest {
  spill_id: string;
  observation_timestamp: string;
  observation_geometry: any;
  candidate_limit?: number;
  include_feature3: boolean;
}

/** Execute production attribution pipeline. */
export async function executeAttributionPipeline(caseId: string): Promise<FinalAttributionReport> {
  const res = await fetch(`${API_BASE}/bayesian/attribution_pipeline_by_case/${caseId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });

  if (!res.ok) {
    const errorBody = await res.text().catch(() => '');
    throw new Error(`Attribution pipeline failed: ${res.status} ${errorBody}`);
  }

  return res.json();
}

/** Deterministic demo mock for frontend testing, strictly adhering to the schema. */
export async function executeAttributionPipelineDemo(request: BayesianPipelineRequest): Promise<FinalAttributionReport> {
  // Simulate network delay
  await new Promise(resolve => setTimeout(resolve, 2000));
  
  return {
    spill_id: request.spill_id || "demo-spill-001",
    report_timestamp: new Date().toISOString(),
    status: "SUCCESS",
    hypothesis_space_truncated: true,
    candidate_limit: request.candidate_limit || 10,
    total_valid_candidates: 45,
    returned_candidate_count: 3,
    evaluated_candidate_count: 2,
    unavailable_candidate_count: 1,
    unavailable_candidate_ids: ["cand_333333333_unavail"],
    prior_mode: "UNIFORM_OVER_RETURNED_CANDIDATES",
    normalization_constant: 1e-15,
    log_normalization_constant: -34.53,
    posterior_sum: 1.0,
    provenance: {
      environmental_data_provider: "Copernicus Marine / ERA5 (Demo Mock)",
      simulation_engine: "OpenDrift / OpenOil",
      bayesian_configuration: { sigma_km: 10, time_tolerance_hours: 2 },
      truncation_metadata: { strategy: "Proximity First" }
    },
    limitations: ["DEMO SYNTHETIC DATA ONLY. Do not use for real operations.", "Truncation applied to hypothesis space."],
    warnings: ["Environmental drift data simulated for demo mode."],
    errors: [],
    candidates: [
      {
        candidate_id: "cand_111111111_t1",
        mmsi: "111111111",
        release_latitude: 55.25,
        release_longitude: 4.10,
        release_timestamp: "2018-08-03T10:00:00Z",
        evaluation_status: "SUCCESS",
        prior_probability: 0.3333,
        likelihood: 1.5e-15,
        posterior_probability: 0.75,
        confidence_level: "INDETERMINATE",
        confidence_diagnostics: [
          { name: "particle_retention", value: 95.0, status: "PASS", message: "95% of ensemble retained." }
        ],
        confidence_flags: [],
        supplemental_deterministic_evidence: {
          feature3_overall_score: 82.5,
          metrics: { closest_approach_distance_km: 1.2 },
          risk_class: "HIGH"
        }
      },
      {
        candidate_id: "cand_111111111_t2",
        mmsi: "111111111",
        release_latitude: 55.20,
        release_longitude: 4.15,
        release_timestamp: "2018-08-03T08:30:00Z",
        evaluation_status: "SUCCESS",
        prior_probability: 0.3333,
        likelihood: 0.5e-15,
        posterior_probability: 0.25,
        confidence_level: "INDETERMINATE",
        confidence_diagnostics: [
          { name: "particle_retention", value: 45.0, status: "WARNING", message: "Only 45% of ensemble retained." }
        ],
        confidence_flags: [
          { flag: "HIGH_STRANDING", severity: "WARNING", description: "Significant particles hit coastline." }
        ],
        supplemental_deterministic_evidence: {
          feature3_overall_score: 45.0,
          metrics: { closest_approach_distance_km: 5.4 },
          risk_class: "MODERATE"
        }
      },
      {
        candidate_id: "cand_333333333_unavail",
        mmsi: "333333333",
        release_latitude: 55.40,
        release_longitude: 4.00,
        release_timestamp: "2018-08-03T11:00:00Z",
        evaluation_status: "EVALUATION_UNAVAILABLE",
        prior_probability: 0.3333,
        likelihood: 0.0,
        posterior_probability: 0.0,
        confidence_level: "INDETERMINATE",
        confidence_diagnostics: [],
        confidence_flags: [],
        supplemental_deterministic_evidence: {
          feature3_overall_score: null,
          metrics: {},
          risk_class: "UNAVAILABLE"
        }
      }
    ]
  };
}
