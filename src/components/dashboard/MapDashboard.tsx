import React, { useState, useEffect } from 'react';
import { loadDashboardData, listCases, deleteCase, CaseResponse, VesselResponse } from '../../services/api';
import { ExplainabilityModal } from '../ExplainabilityModal';
import { RefreshCw, AlertTriangle, Anchor, Play, Pause, X, Database } from 'lucide-react';

import { TopNavbar } from './TopNavbar';
import { DetailsPanel } from './DetailsPanel';
import { RightVesselList } from './RightVesselList';
import { VesselPopup } from './VesselPopup';
import { MapCanvas } from './MapCanvas';
import { LayerControl } from './LayerControl';
import { CurrentDashboardData, DashboardEntityState, VesselCandidate } from './types';
import { IncidentsModule } from './IncidentsModule';
import { DriftPhysicsModule } from './DriftPhysicsModule';
import { ForensicAnalyticsModule } from './ForensicAnalyticsModule';
import { AttributionDashboard } from './AttributionDashboard';
import { SarSatellitePage } from './SarSatellitePage';

const VESSEL_TRACK_COLORS = [
  '#EF4444', '#F59E0B', '#7C3AED', '#0D9488', '#EC4899',
  '#10B981', '#9333EA', '#059669', '#EA580C', '#64748B',
];

// ═══════════════════════════════════════════
// DUMMY DATA — Used when API is unavailable
// ═══════════════════════════════════════════
const DUMMY_DATA: CurrentDashboardData = {
  title: 'SLK-A58D',
  location: 'Arabian Sea, Gujarat Coast',
  confidence: 'HIGH (92%)',
  area: '284 km²',
  length: '28.4 km',
  width: '10.2 km',
  estVolume: '12,400 bbl',
  estAge: '~18h',
  originTime: '2026-09-22T01:30:00Z',
  detectionTime: '2026-09-22T06:45:00Z',
  source: 'Sentinel-1 SAR',
  center: [22.17, 68.81],
  zoom: 9,
  spillPolygon: [
    [22.20, 68.75], [22.22, 68.78], [22.23, 68.82], [22.21, 68.86],
    [22.18, 68.88], [22.15, 68.87], [22.13, 68.84], [22.12, 68.80],
    [22.13, 68.77], [22.16, 68.74], [22.19, 68.74], [22.20, 68.75],
  ],
  driftPath: [
    { label: 'Origin', lat: 22.25, lng: 68.72, text: 'Origin' },
    { label: '+6h', lat: 22.22, lng: 68.75, text: '+6h' },
    { label: '+12h', lat: 22.19, lng: 68.79, text: '+12h' },
  ],
  vessels: [
    {
      raw: { imo: '9234567', length_m: 274, width_m: 48 }, name: 'MT OCEAN VOYAGER', mmsi: '538006789',
      type: 'Crude Oil Tanker', flag: 'Marshall Islands', score: 78, compositeScore: 78,
      riskClass: 'HIGH', scoringMode: 'UNCERTAINTY_AWARE_5_FACTOR',
      originPresence: 85, behaviorAnomaly: 72, dwellTime: 65, aisGap: 45, approachDeparture: 58,
      proximity: 82, trajectory: 70, behavioral: 72, flags: [], qualityFlags: [],
      evidence: { closest_approach_distance_km: 1.8, time_offset_minutes: 42, dwell_minutes_inside_zone: 95, sog_at_origin_kn: 2.1 },
      explanation: 'High proximity and behavioral anomaly', trajectoryGeojson: null,
      color: '#EF4444', lat: 22.218, lng: 68.748, heading: 135, speed: 3.2,
    },
    {
      raw: { imo: '9345678' }, name: 'CAPE GUARDIAN', mmsi: '636012345',
      type: 'Bulk Carrier', flag: 'Liberia', score: 45, compositeScore: 45,
      riskClass: 'MODERATE', scoringMode: 'UNCERTAINTY_AWARE_5_FACTOR',
      originPresence: 42, behaviorAnomaly: 38, dwellTime: 55, aisGap: 62, approachDeparture: 30,
      proximity: 40, trajectory: 45, behavioral: 38, flags: [], qualityFlags: [],
      evidence: { closest_approach_distance_km: 5.4, time_offset_minutes: 120, dwell_minutes_inside_zone: 22, sog_at_origin_kn: 8.5 },
      explanation: 'Moderate proximity', trajectoryGeojson: null,
      color: '#F59E0B', lat: 22.165, lng: 68.735, heading: 70, speed: 11.5,
    },
    {
      raw: { imo: '9456789' }, name: 'FISHING VESSEL 7', mmsi: '419000123',
      type: 'Fishing Vessel', flag: 'India', score: 22, compositeScore: 22,
      riskClass: 'LOW', scoringMode: 'UNCERTAINTY_AWARE_5_FACTOR',
      originPresence: 18, behaviorAnomaly: 25, dwellTime: 30, aisGap: 15, approachDeparture: 20,
      proximity: 20, trajectory: 22, behavioral: 25, flags: [], qualityFlags: [],
      evidence: {}, explanation: 'Low risk', trajectoryGeojson: null,
      color: '#8B5CF6', lat: 22.135, lng: 68.865, heading: 315, speed: 5.0,
    },
  ],
  feature2Data: {
    origin_latitude: 22.25, origin_longitude: 68.72,
    origin_confidence_score: 0.87, origin_uncertainty_radius_km: 3.2,
    origin_timestamp: '2026-09-22T01:30:00Z',
    forecast_json: {
      '6h':  { centroid_latitude: 22.22, centroid_longitude: 68.76, spread_radius_km: 2.5 },
      '12h': { centroid_latitude: 22.19, centroid_longitude: 68.80, spread_radius_km: 4.0 },
      '24h': { centroid_latitude: 22.14, centroid_longitude: 68.86, spread_radius_km: 6.5 },
      '48h': { centroid_latitude: 22.08, centroid_longitude: 68.94, spread_radius_km: 10.0 },
    },
  },
  spillInfo: { spill_latitude: 22.17, spill_longitude: 68.81, detection_timestamp: '2026-09-22T06:45:00Z', satellite_source: 'Sentinel-1' },
  activeCase: 'SLK-A58D',
  bayesianUnavailable: false,
  bayesianReport: null,
};

interface MapDashboardProps {
  onNavigate: (view: 'home' | 'dashboard' | 'workflow') => void;
  onOpenUpload: () => void;
  selectedCaseId?: string;
}

export const MapDashboard: React.FC<MapDashboardProps> = ({ onNavigate, onOpenUpload, selectedCaseId = '' }) => {
  const [activeCase, setActiveCase] = useState<string>(selectedCaseId);
  const [availableCases, setAvailableCases] = useState<CaseResponse[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [usingDummy, setUsingDummy] = useState(false);

  const [dashboardData, setDashboardData] = useState<any>(null);
  const [currentData, setCurrentData] = useState<CurrentDashboardData | null>(null);

  const [activeModule, setActiveModule] = useState<string>('dashboard');

  const [layers, setLayers] = useState({ spill: true, drift: true, ais: true, satTile: 'carto' });
  const [showLayers, setShowLayers] = useState<boolean>(true);

  const [selectedEntity, setSelectedEntity] = useState<DashboardEntityState>({ type: null, id: null });

  const [explainVessel, setExplainVessel] = useState<VesselResponse | null>(null);
  const [showExplainModal, setShowExplainModal] = useState<boolean>(false);

  const [showAttributionDashboard, setShowAttributionDashboard] = useState<boolean>(false);

  // Close attribution modal on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && showAttributionDashboard) {
        setShowAttributionDashboard(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [showAttributionDashboard]);

  const [isPlayingScrubber, setIsPlayingScrubber] = useState<boolean>(false);
  const [scrubberTime, setScrubberTime] = useState<number>(0);

  useEffect(() => { if (selectedCaseId && selectedCaseId !== activeCase) setActiveCase(selectedCaseId); }, [selectedCaseId]);

  useEffect(() => {
    listCases().then(cases => {
      setAvailableCases(cases);
      if (cases.length > 0) {
        if (selectedCaseId && cases.some(c => c.id === selectedCaseId)) setActiveCase(selectedCaseId);
        else if (activeCase && cases.some(c => c.id === activeCase)) setActiveCase(activeCase);
        else setActiveCase(cases[0].id);
      } else {
        setActiveCase('');
        // Fallback to dummy data
        setCurrentData(DUMMY_DATA);
        setUsingDummy(true);
        setIsLoading(false);
      }
    }).catch(() => {
      setAvailableCases([]);
      setCurrentData(DUMMY_DATA);
      setUsingDummy(true);
      setIsLoading(false);
    });
  }, [selectedCaseId]);

  useEffect(() => {
    if (!activeCase) {
      if (!usingDummy) {
        setCurrentData(DUMMY_DATA);
        setUsingDummy(true);
      }
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setLoadError(null);
    setSelectedEntity({ type: null, id: null });

    loadDashboardData(activeCase)
      .then(data => {
        setDashboardData(data);
        setUsingDummy(false);

        const summary = data.case?.summary_json;
        const spillInfo = summary?.spill || data.spill;
        const feature2Data = data.feature2;
        const driftInfo = summary?.drift || (feature2Data ? {
          origin_latitude: feature2Data.origin_latitude,
          origin_longitude: feature2Data.origin_longitude,
          origin_timestamp: feature2Data.origin_timestamp,
          drift_trajectory: feature2Data.drift_trajectory || []
        } : null);

        const bayesianReport = summary?.bayesian_report;
        let mappedVessels: VesselCandidate[] = [];
        let bayesianUnavailable = false;

        const isBayesianCase = summary?.attribution_mode === 'BAYESIAN';

        const safeParseJSON = (data: any) => {
          if (typeof data === 'string') { try { return JSON.parse(data); } catch (e) { return data; } }
          return data;
        };

        if (isBayesianCase) {
          if (bayesianReport?.candidates?.length > 0) {
            mappedVessels = bayesianReport.candidates.map((c: any, idx: number) => {
              const feature3 = c.supplemental_deterministic_evidence || {};
              const legacyVessel = (data.vessels || []).find((v: any) => v.mmsi === c.mmsi);
              return {
                raw: c, name: legacyVessel?.name || c.mmsi, mmsi: c.mmsi,
                type: legacyVessel?.type || 'Unknown', flag: legacyVessel?.flag || 'Unknown',
                posterior_probability: c.posterior_probability, confidence_level: c.confidence_level,
                supplemental_feature3: feature3, candidate_id: c.candidate_id,
                scoringMode: 'BAYESIAN_POSTERIOR', originPresence: 0, behaviorAnomaly: 0,
                dwellTime: 0, aisGap: 0, approachDeparture: null, proximity: 0,
                trajectory: 0, behavioral: 0, flags: [], qualityFlags: [],
                evidence: feature3.metrics, explanation: "Bayesian posterior probability.",
                trajectoryGeojson: legacyVessel ? safeParseJSON(legacyVessel.trajectory_geojson) : null,
                color: VESSEL_TRACK_COLORS[idx % VESSEL_TRACK_COLORS.length],
                lat: legacyVessel ? legacyVessel.current_latitude : c.release_latitude,
                lng: legacyVessel ? legacyVessel.current_longitude : c.release_longitude,
                heading: legacyVessel ? legacyVessel.heading_deg : 0,
                speed: legacyVessel?.speed_kts ?? 0,
              };
            });
          } else { bayesianUnavailable = true; }
        } else {
          mappedVessels = (data.vessels || []).map((v: any, idx: number) => ({
            raw: v, name: v.name, mmsi: v.mmsi, type: v.type, flag: v.flag,
            score: Math.round(v.composite_score ?? v.overall_score),
            compositeScore: v.composite_score ?? v.overall_score,
            riskClass: v.risk_class || (v.overall_score >= 80 ? 'VERY HIGH' : v.overall_score >= 60 ? 'HIGH' : v.overall_score >= 30 ? 'MODERATE' : 'LOW'),
            scoringMode: v.scoring_mode || 'UNCERTAINTY_AWARE_5_FACTOR',
            originPresence: v.origin_presence_score ?? v.proximity_score,
            behaviorAnomaly: v.behavior_anomaly_score ?? v.behavioral_score,
            dwellTime: v.dwell_time_score ?? 0, aisGap: v.ais_gap_score ?? 0,
            approachDeparture: v.approach_departure_score, proximity: v.proximity_score,
            trajectory: v.trajectory_score, behavioral: v.behavioral_score,
            flags: safeParseJSON(v.warning_flags) || [], qualityFlags: safeParseJSON(v.quality_flags) || [],
            evidence: safeParseJSON(v.evidence_metrics), explanation: v.explanation,
            trajectoryGeojson: safeParseJSON(v.trajectory_geojson),
            color: VESSEL_TRACK_COLORS[idx % VESSEL_TRACK_COLORS.length],
            lat: v.current_latitude, lng: v.current_longitude, heading: v.heading_deg, speed: v.speed_kts ?? 0,
          }));
        }

        const parsedData: CurrentDashboardData = {
          title: data.case?.name || activeCase, location: data.case?.location_name || '',
          confidence: spillInfo?.confidence_label || 'PENDING',
          area: spillInfo?.area_km2 > 0 ? `${spillInfo.area_km2} km²` : '—',
          length: spillInfo?.length_km > 0 ? `${spillInfo.length_km} km` : '—',
          width: spillInfo?.width_km > 0 ? `${spillInfo.width_km} km` : '—',
          estVolume: spillInfo?.est_volume_bbl > 0 ? `${spillInfo.est_volume_bbl.toLocaleString()} bbl` : '—',
          estAge: '—',
          originTime: driftInfo?.origin_timestamp || feature2Data?.origin_timestamp || '—',
          detectionTime: spillInfo?.detection_timestamp || '—',
          source: spillInfo?.satellite_source || '—',
          center: [
            (spillInfo?.spill_latitude && spillInfo.spill_latitude !== 0) ? spillInfo.spill_latitude : (data.case?.center_latitude || 22.47),
            (spillInfo?.spill_longitude && spillInfo.spill_longitude !== 0) ? spillInfo.spill_longitude : (data.case?.center_longitude || 69.21),
          ],
          zoom: 9,
          spillPolygon: safeParseJSON(spillInfo?.polygon_geojson)?.coordinates?.[0]?.map((c: number[]) => [c[1], c[0]]) || [],
          driftPath: (safeParseJSON(driftInfo?.drift_trajectory) || []).map((pt: any) => ({ label: pt.time, lat: pt.lat, lng: pt.lon, text: pt.time })),
          vessels: mappedVessels, feature2Data, spillInfo, activeCase, bayesianUnavailable, bayesianReport,
        };

        setCurrentData(parsedData);
        setIsLoading(false);
      })
      .catch(err => {
        // Fallback to dummy data on error
        console.warn('Dashboard load failed, using dummy data:', err.message);
        setCurrentData(DUMMY_DATA);
        setUsingDummy(true);
        setIsLoading(false);
      });
  }, [activeCase]);

  // Timeline auto-play
  useEffect(() => {
    let timer: any;
    if (isPlayingScrubber) { timer = setInterval(() => setScrubberTime(p => p >= 48 ? 0 : p + 6), 1500); }
    return () => clearInterval(timer);
  }, [isPlayingScrubber]);

  const handleDeleteCase = async (id: string) => {
    if (!window.confirm(`Delete incident ${id}?`)) return;
    try {
      await deleteCase(id);
      const updated = await listCases();
      setAvailableCases(updated);
      if (updated.length > 0) setActiveCase(updated[0].id);
      else { setActiveCase(''); setDashboardData(null); setCurrentData(DUMMY_DATA); setUsingDummy(true); }
    } catch (err: any) { alert(`Failed: ${err.message}`); }
  };

  const handleSelectEntity = (entity: DashboardEntityState) => setSelectedEntity(entity);

  // Loading state
  if (isLoading && !currentData) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-center space-y-3">
          <RefreshCw className="w-8 h-8 animate-spin text-navy-800 mx-auto" />
          <p className="text-xs font-bold text-navy-800">Loading Maritime Intelligence…</p>
        </div>
      </div>
    );
  }

  const data = currentData || DUMMY_DATA;

  const selectedVesselObj = data.vessels.find(v => {
    const vId = v.scoringMode === 'BAYESIAN_POSTERIOR' ? v.candidate_id : v.mmsi;
    return vId === selectedEntity.id;
  }) || null;

  const selectedVesselIdx = selectedVesselObj ? data.vessels.indexOf(selectedVesselObj) : 0;

  return (
    <div className="h-screen bg-slate-100 text-gov-text font-sans flex flex-col overflow-hidden">
      {/* Top Navbar */}
      <TopNavbar
        onNavigate={onNavigate}
        activeModule={activeModule}
        setActiveModule={setActiveModule}
        onOpenUpload={onOpenUpload}
        availableCases={availableCases} activeCase={activeCase}
        setActiveCase={setActiveCase} handleDeleteCase={handleDeleteCase}
        showAttributionDashboard={showAttributionDashboard}
        setShowAttributionDashboard={setShowAttributionDashboard}
      />

      {/* Incident Strip */}
      <div className="incident-strip px-4 py-1.5 flex items-center gap-4 text-[10px] overflow-x-auto flex-shrink-0">
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
          <span className="font-black uppercase tracking-widest text-red-400">Active Incident</span>
        </div>
        <span className="font-black text-white">{data.title || data.activeCase || 'SLK-A58D'}</span>
        <span className="text-slate-400">|</span>
        <span className="text-slate-300">Detected: {data.detectionTime ? new Date(data.detectionTime).toLocaleDateString() : '22 Sep 2026'}</span>
        <span className="text-slate-400">|</span>
        <span className="text-slate-300">Area: <strong className="text-white">{data.area}</strong></span>
        <span className="text-slate-400">|</span>
        <span className="text-slate-300">Forecast: <strong className="text-cyan-400">48h</strong></span>
        <span className="text-slate-400">|</span>
        <span className="text-slate-300">Vessels: <strong className="text-white">{data.vessels.length}</strong></span>
        <span className="text-slate-400">|</span>
        <span className="text-slate-300">Confidence: <strong className="text-amber-400">{data.confidence}</strong></span>

      </div>

      {/* Main Area */}
      <main className="flex-1 relative overflow-hidden flex flex-col md:flex-row bg-slate-100">
        
        {activeModule === 'incidents' && (
          <div className="absolute inset-0 z-50 bg-white">
            <IncidentsModule
              activeCase={activeCase}
              setActiveCase={setActiveCase}
              availableCases={availableCases}
              currentData={data}
              onOpenUpload={onOpenUpload}
              setActiveModule={setActiveModule}
            />
          </div>
        )}

        {activeModule === 'sar' && (
          <div className="absolute inset-0 z-50">
            <SarSatellitePage currentData={data} />
          </div>
        )}

        {activeModule === 'drift' && (
          <div className="absolute inset-0 z-50 bg-white">
             <DriftPhysicsModule currentData={data} />
          </div>
        )}

        {activeModule === 'forensic' && (
          <div className="absolute inset-0 z-50 bg-white">
             <ForensicAnalyticsModule currentData={data} setActiveModule={setActiveModule} />
          </div>
        )}

        {/* Dashboard View */}
        <div className={`relative flex-1 transition-all duration-300 ${activeModule === 'dashboard' ? 'block' : 'hidden'} w-full`}>
          {/* Map */}
          <MapCanvas
            currentData={data}
            layers={layers}
            selectedEntity={selectedEntity}
            onSelectEntity={handleSelectEntity}
            isLoading={isLoading}
          />

          {/* Top-Left: Map Layers + Floating Legend */}
          <div className="absolute top-4 left-4 z-20 flex flex-col gap-2 pointer-events-auto transition-all duration-300" style={{ width: 175 }}>
            <LayerControl showLayers={showLayers} setShowLayers={setShowLayers} layers={layers} setLayers={setLayers} />

            {/* Floating Legend */}
            <div className="bg-[#0a1426]/90 backdrop-blur-sm border border-slate-700/60 rounded-lg p-2.5 text-white shadow-2xl space-y-1.5 select-none w-full">
              <div className="flex items-center gap-2 text-[10px] font-medium text-slate-200">
                <div className="w-4 flex items-center justify-center flex-shrink-0">
                  <div className="w-2.5 h-2.5 rounded-full bg-red-600 border border-white shadow-sm" />
                </div>
                <span>Detected Spill</span>
              </div>
              <div className="flex items-center gap-2 text-[10px] font-medium text-slate-200">
                <div className="w-4 flex items-center justify-center flex-shrink-0">
                  <div className="w-2.5 h-2.5 rounded-full bg-orange-500 border border-white shadow-sm" />
                </div>
                <span>Origin Point</span>
              </div>
              <div className="flex items-center gap-2 text-[10px] font-medium text-slate-200">
                <div className="w-4 flex items-center justify-center flex-shrink-0 relative">
                  <div className="w-full border-t-2 border-dashed border-sky-500" />
                  <svg className="absolute left-1/2 -top-1 -translate-x-1/2" width="7" height="7" viewBox="0 0 10 10">
                    <polygon points="5,0.5 9,8.5 5,6.5 1,8.5" fill="#0284c7" stroke="#ffffff" strokeWidth="0.8" transform="rotate(-90 5 5)" />
                  </svg>
                </div>
                <span>Hindcast Track (Origin)</span>
              </div>
              <div className="flex items-center gap-2 text-[10px] font-medium text-slate-200">
                <div className="w-4 flex items-center justify-center flex-shrink-0 relative">
                  <div className="w-full border-t-2 border-dashed border-sky-500" />
                  <svg className="absolute left-1/2 -top-1 -translate-x-1/2" width="7" height="7" viewBox="0 0 10 10">
                    <polygon points="5,0.5 9,8.5 5,6.5 1,8.5" fill="#0284c7" stroke="#ffffff" strokeWidth="0.8" transform="rotate(90 5 5)" />
                  </svg>
                </div>
                <span>Forecast Track</span>
              </div>
              <div className="flex items-center gap-2 text-[10px] font-medium text-slate-200">
                <div className="w-4 flex items-center justify-center flex-shrink-0">
                  <div className="w-2 h-2 rounded-full bg-sky-600 border border-white shadow-sm" />
                </div>
                <span>Forecast Points</span>
              </div>
            </div>
          </div>

          {/* Right-side context panel for spill/origin */}
          {data && !showAttributionDashboard && (selectedEntity.type === 'origin' || selectedEntity.type === 'spill') && (
            <DetailsPanel
              selectedEntity={selectedEntity}
              currentData={data}
              onGenerateReport={() => {}}
              onClose={() => handleSelectEntity({ type: null, id: null })}
            />
          )}

          {/* Vessel Detail Panel */}
          {!showAttributionDashboard && selectedEntity.type === 'vessel' && selectedVesselObj && (
            <VesselPopup
              vessel={selectedVesselObj}
              vesselIndex={selectedVesselIdx}
              onClose={() => handleSelectEntity({ type: null, id: null })}
              onAuditEvidence={(raw) => { setExplainVessel(raw); setShowExplainModal(true); }}
            />
          )}

          {/* Right vessel list */}
          {data && data.vessels.length > 0 && !showAttributionDashboard && (
            <RightVesselList
              vessels={data.vessels}
              onSelectVessel={(id) => handleSelectEntity({ type: 'vessel', id })}
              selectedVesselMmsi={selectedEntity.type === 'vessel' ? selectedEntity.id : null}
            />
          )}

          {/* Bayesian unavailable banner */}
          {data && data.bayesianUnavailable && !showAttributionDashboard && (
            <div className="absolute right-4 top-20 w-72 bg-white shadow-lg rounded-lg border-l-4 border-red-500 p-3 z-[400]">
              <h3 className="text-xs font-bold text-red-700 mb-1 flex items-center gap-1.5"><AlertTriangle className="h-3.5 w-3.5" />Attribution Unavailable</h3>
              <p className="text-[10px] text-gray-600">Bayesian attribution could not be completed.</p>
            </div>
          )}


        </div>

        {/* Attribution Window Modal with Backdrop Blur */}
        {showAttributionDashboard && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 md:p-6 bg-slate-950/65 backdrop-blur-md transition-all duration-300"
            onClick={(e) => {
              if (e.target === e.currentTarget) {
                setShowAttributionDashboard(false);
              }
            }}
          >
            <div
              className="relative w-full max-w-5xl h-[88vh] bg-white rounded-xl shadow-2xl border border-slate-200/80 flex flex-col overflow-hidden animate-in zoom-in-95 duration-200"
              role="dialog"
              aria-modal="true"
            >
              {/* Window Header */}
              <div className="flex items-center justify-between px-5 py-3.5 bg-navy-800 text-white border-b border-navy-700/60 flex-shrink-0">
                {/* Header Title & Case Identifier on Left */}
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-blue-500/20 border border-blue-400/30 flex items-center justify-center text-blue-300 flex-shrink-0">
                    <Database className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-sm font-bold tracking-wide">
                        Bayesian Attribution & Vessel Forensic Dossier
                      </h2>
                      <span className="text-[10px] font-mono bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded border border-blue-400/30 font-semibold">
                        {data.activeCase || 'SLK-A58D'}
                      </span>
                    </div>
                    <p className="text-[10px] text-slate-300 hidden sm:block">National Maritime Intelligence • Trajectory Correlation</p>
                  </div>
                </div>

                {/* Right controls: Status indicator + TOP-RIGHT Close Button */}
                <div className="flex items-center gap-3">
                  <div className="text-[11px] text-slate-300 font-medium hidden md:flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                    <span>Intelligence Active</span>
                  </div>

                  {/* TOP RIGHT: Close Cross Button */}
                  <button
                    type="button"
                    onClick={() => setShowAttributionDashboard(false)}
                    className="p-1.5 rounded-lg bg-white/10 hover:bg-red-600/90 text-slate-300 hover:text-white transition-all flex items-center justify-center focus:outline-none focus:ring-2 focus:ring-blue-400"
                    title="Close Attribution Window (Esc)"
                    aria-label="Close Attribution Window"
                  >
                    <X className="w-4 h-4 stroke-[2.5]" />
                  </button>
                </div>
              </div>

              {/* Window Body: Scrollable Attribution Content */}
              <div className="flex-1 overflow-y-auto bg-slate-100/75 flex flex-col">
                <AttributionDashboard
                  spillId={data.activeCase || 'SLK-A58D'}
                  isDemoMode={usingDummy}
                  existingReport={data.bayesianReport}
                />
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Explainability Modal */}
      {showExplainModal && explainVessel && (
        <ExplainabilityModal
          vessel={explainVessel}
          caseId={activeCase || 'SLK-A58D'}
          onClose={() => setShowExplainModal(false)}
        />
      )}
    </div>
  );
};
