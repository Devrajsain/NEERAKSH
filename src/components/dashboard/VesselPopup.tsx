import React from 'react';
import { VesselCandidate } from './types';
import { X, Flag, Navigation, Hash, Activity, Download, Anchor, MapPin, Clock } from 'lucide-react';
import { getShipImage } from './shipImages';

interface VesselPopupProps {
  vessel: VesselCandidate | null;
  vesselIndex?: number;
  onClose: () => void;
  onAuditEvidence: (vesselRaw: any) => void;
}

export const VesselPopup: React.FC<VesselPopupProps> = ({ vessel, vesselIndex = 0, onClose, onAuditEvidence }) => {
  if (!vessel) return null;

  const isBay = vessel.scoringMode === 'BAYESIAN_POSTERIOR';
  const pct = isBay ? Math.round((vessel.posterior_probability ?? 0) * 100) : (vessel.score ?? 0);
  const barColor = pct >= 65 ? '#DC2626' : pct >= 35 ? '#D97706' : '#8B5CF6';
  const ev = vessel.evidence || {};

  return (
    <aside className="w-full max-h-[calc(60vh)] context-panel vessel-popup-panel flex flex-col rounded-xl overflow-hidden shadow-2xl border border-slate-200">
      {/* Header */}
      <div className="bg-navy-800 text-white px-4 py-3 flex items-start justify-between">
        <div>
          <div className="text-[9px] uppercase tracking-widest text-slate-300 font-semibold mb-0.5">Possible Responsible Vessel</div>
          <h2 className="text-base font-black">{vessel.name || `Vessel ${vessel.mmsi}`}</h2>
          <div className="flex items-center gap-2 mt-1 text-[10px] text-slate-300">
            <Flag className="w-3 h-3" /> {vessel.flag || 'Unknown'}
            {vessel.type && vessel.type !== 'Unknown' && <><span className="text-slate-500">•</span>{vessel.type}</>}
          </div>
        </div>
        <button onClick={onClose} className="p-1 hover:bg-white/10 rounded transition-colors"><X className="w-4 h-4" /></button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Ship image + score */}
        <div className="flex items-center gap-4">
          <div className="w-20 h-20 bg-slate-100 border border-slate-200 rounded-lg flex items-center justify-center">
            <img src={getShipImage(vesselIndex)} alt="" className="w-16 h-16 object-contain" />
          </div>
          <div className="flex-1 flex flex-col items-center">
            <div className="relative w-16 h-16">
              <svg viewBox="0 0 36 36" className="w-full h-full transform -rotate-90">
                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#f1f5f9" strokeWidth="3" />
                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke={barColor} strokeWidth="3" strokeDasharray={`${pct}, 100`} />
              </svg>
              <span className="absolute inset-0 flex items-center justify-center text-sm font-black text-navy-800">{pct}%</span>
            </div>
            <span className="text-[9px] text-gov-muted uppercase font-bold mt-1 text-center">
              {isBay ? 'Bayesian Probability' : 'Attribution Score'}
            </span>
          </div>
        </div>

        {/* Vessel Info */}
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-0">
          <Row label="MMSI" value={vessel.mmsi} icon={<Hash className="w-3 h-3" />} />
          <Row label="IMO" value={vessel.raw?.imo || 'N/A'} icon={<Hash className="w-3 h-3" />} />
          <Row label="Type" value={vessel.type || 'Unknown'} icon={<Anchor className="w-3 h-3" />} />
          <Row label="Flag" value={vessel.flag || 'Unknown'} icon={<Flag className="w-3 h-3" />} />
          <Row label="Position" value={`${vessel.lat?.toFixed(4)}°N, ${vessel.lng?.toFixed(4)}°E`} icon={<MapPin className="w-3 h-3" />} />
          <Row label="Speed" value={`${vessel.speed?.toFixed(1) || 0} kts`} icon={<Navigation className="w-3 h-3" />} />
          <Row label="Heading" value={`${vessel.heading || 0}°`} icon={<Navigation className="w-3 h-3" />} />
        </div>

        {/* Evidence */}
        <div>
          <h4 className="text-[10px] font-black text-navy-800 uppercase tracking-wider border-b border-slate-200 pb-1 mb-2">
            Attribution Evidence
          </h4>
          {isBay ? (
            <div className="space-y-2">
              <EvidenceBar label="Bayesian Posterior" value={pct} color="#8B5CF6" />
              <EvidenceBar label="Prior Probability" value={Math.round((vessel.raw?.prior_probability || 0) * 100)} color="#94A3B8" />
              {vessel.raw?.release_latitude && (
                <div className="bg-blue-50 border border-blue-200 rounded p-2 mt-2 text-[10px]">
                  <div className="flex justify-between"><span className="text-blue-700">Release Origin</span><span className="font-mono font-bold text-blue-900">{vessel.raw.release_latitude.toFixed(4)}, {vessel.raw.release_longitude.toFixed(4)}</span></div>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              <EvidenceBar label="Origin Presence (45%)" value={Math.round(vessel.originPresence)} color="#1D4ED8" />
              <EvidenceBar label="Behavior Anomaly (20%)" value={Math.round(vessel.behaviorAnomaly)} color="#1D4ED8" />
              <EvidenceBar label="Dwell Duration (15%)" value={Math.round(vessel.dwellTime)} color="#1D4ED8" />
              <EvidenceBar label="Drift Match (10%)" value={Math.round(vessel.approachDeparture ?? 0)} color="#1D4ED8" />
              <EvidenceBar label="AIS Dark Gap (10%)" value={Math.round(vessel.aisGap)} color="#1D4ED8" />
            </div>
          )}
        </div>

        {/* Quick stats */}
        {ev.closest_approach_distance_km !== undefined && (
          <div className="grid grid-cols-4 gap-1.5">
            {[
              { label: 'Approach', val: `${ev.closest_approach_distance_km?.toFixed(1)} km` },
              { label: 'Offset', val: `${ev.time_offset_minutes?.toFixed(0)} m` },
              { label: 'Dwell', val: `${ev.dwell_minutes_inside_zone || 0} m` },
              { label: 'SOG', val: `${ev.sog_at_origin_kn ?? '—'} kn` },
            ].map((s, i) => (
              <div key={i} className="bg-slate-50 border border-slate-200 rounded p-1.5 text-center">
                <div className="text-[8px] text-slate-500 uppercase font-bold">{s.label}</div>
                <div className="font-mono font-bold text-navy-800 text-[10px]">{s.val}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="bg-slate-50 border-t border-slate-200 p-3 grid grid-cols-2 gap-2">
        <button onClick={() => onAuditEvidence(vessel.raw)} className="flex items-center justify-center gap-1.5 bg-white border border-slate-300 hover:border-navy-500 text-navy-800 rounded py-2 text-[10px] font-bold uppercase tracking-wider transition-colors">
          <Activity className="w-3.5 h-3.5" /> Audit Evidence
        </button>
        <button className="flex items-center justify-center gap-1.5 bg-navy-800 hover:bg-navy-700 text-white rounded py-2 text-[10px] font-bold uppercase tracking-wider transition-colors">
          <Download className="w-3.5 h-3.5" /> Export
        </button>
      </div>
    </aside>
  );
};

const Row: React.FC<{ label: string; value: string; icon?: React.ReactNode }> = ({ label, value, icon }) => (
  <div className="detail-row">
    <span className="detail-label flex items-center gap-1">{icon}{label}</span>
    <span className="detail-value">{value}</span>
  </div>
);

const EvidenceBar: React.FC<{ label: string; value: number; color: string }> = ({ label, value, color }) => (
  <div>
    <div className="flex justify-between text-[10px] mb-0.5">
      <span className="text-slate-600 font-medium">{label}</span>
      <span className="font-mono font-bold text-navy-800">{value}%</span>
    </div>
    <div className="conf-track"><div className="conf-fill" style={{ width: `${Math.min(100, value)}%`, background: color }} /></div>
  </div>
);
