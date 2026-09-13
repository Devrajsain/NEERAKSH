import React from 'react';
import { VesselCandidate } from './types';
import { X, Map, Activity, Download, Flag, Navigation, Clock, Hash } from 'lucide-react';

interface VesselPopupProps {
  vessel: VesselCandidate | null;
  onClose: () => void;
  onAuditEvidence: (vesselRaw: any) => void;
}

export const VesselPopup: React.FC<VesselPopupProps> = ({ vessel, onClose, onAuditEvidence }) => {
  if (!vessel) return null;

  const ev = vessel.evidence || {};
  const isHighRisk = vessel.riskClass === 'VERY HIGH' || vessel.riskClass === 'HIGH';

  return (
    <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-40 w-full max-w-[400px] sm:max-w-[450px] bg-white rounded-lg shadow-[0_10px_40px_rgba(0,0,0,0.3)] border border-gov-border flex flex-col overflow-hidden transition-all duration-200 animate-in fade-in zoom-in-95">
      {/* Header */}
      <div className="bg-navy-900 text-white p-3 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-black font-sans truncate">{vessel.name}</h2>
            {isHighRisk && (
              <span className="px-1.5 py-0.5 bg-red-600 text-white text-[9px] font-bold uppercase rounded flex-shrink-0 shadow-sm border border-red-500">
                Primary Suspect
              </span>
            )}
          </div>
          <p className="text-xs text-slate-300 font-mono mt-0.5 flex items-center gap-1.5">
            <Flag className="w-3 h-3" /> {vessel.flag || 'Unknown Flag'}
          </p>
        </div>
        <button 
          onClick={onClose}
          className="text-slate-400 hover:text-white bg-navy-800 hover:bg-navy-700 rounded p-1 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="p-4 overflow-y-auto max-h-[70vh]">
        
        {/* Main Stats Row: Photo Placeholder + Attribution Score */}
        <div className="flex items-center gap-4 mb-4">
          <div className="w-24 h-24 bg-slate-100 border border-slate-200 rounded flex items-center justify-center text-slate-400 shrink-0">
            {/* Photo Placeholder */}
            <div className="text-center">
              <span className="block text-2xl">🚢</span>
              <span className="text-[9px] uppercase font-semibold">No Image</span>
            </div>
          </div>
          
          <div className="flex-1 flex flex-col items-center justify-center bg-slate-50 border border-slate-100 rounded p-2">
             <div className="relative flex items-center justify-center w-16 h-16 rounded-full bg-gov-light shadow-inner mb-1">
               {/* Faux circular progress background */}
               <svg className="w-full h-full transform -rotate-90 absolute inset-0 text-slate-200" viewBox="0 0 36 36">
                 <path className="stroke-current stroke-2" fill="none" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
                 <path className={`stroke-2 ${isHighRisk ? 'stroke-red-600' : 'stroke-navy-800'}`} fill="none" strokeDasharray={`${vessel.score}, 100`} d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
               </svg>
               <span className="text-lg font-black text-navy-900 font-mono absolute">{vessel.score}%</span>
             </div>
             <span className="text-[10px] text-gov-muted uppercase font-bold text-center tracking-wider">
               Attribution<br/>Probability
             </span>
          </div>
        </div>

        {/* Vessel Info Grid */}
        <div className="grid grid-cols-2 gap-2 mb-4 text-xs">
          <div className="bg-gov-light p-2 rounded flex flex-col border border-gov-border">
            <span className="text-[9px] uppercase text-gov-muted font-bold flex items-center gap-1"><Hash className="w-3 h-3"/> MMSI / IMO</span>
            <span className="font-mono font-semibold text-navy-800">{vessel.mmsi} / {vessel.raw?.imo || 'N/A'}</span>
          </div>
          <div className="bg-gov-light p-2 rounded flex flex-col border border-gov-border">
            <span className="text-[9px] uppercase text-gov-muted font-bold flex items-center gap-1"><Navigation className="w-3 h-3"/> Type & Size</span>
            <span className="font-mono font-semibold text-navy-800 truncate">{vessel.type} • {vessel.raw?.length_m || '?'}x{vessel.raw?.width_m || '?'}m</span>
          </div>
        </div>

        {/* Evidence Breakdown */}
        <div className="space-y-2.5 mb-5">
          <h4 className="text-[11px] font-bold text-navy-800 uppercase border-b border-slate-200 pb-1">
            Evidence Breakdown
          </h4>
          
          <div className="space-y-2">
            <div>
              <div className="flex justify-between text-[10px] mb-0.5">
                <span className="text-slate-600 font-medium">Origin Presence (45%)</span>
                <span className="font-mono font-bold text-navy-800">{Math.round(vessel.originPresence)}%</span>
              </div>
              <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden border border-slate-200/50">
                <div className="h-full bg-navy-700 transition-all duration-500" style={{ width: `${Math.min(100, vessel.originPresence)}%` }}></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-[10px] mb-0.5">
                <span className="text-slate-600 font-medium">Behavior Anomaly (20%)</span>
                <span className="font-mono font-bold text-navy-800">{Math.round(vessel.behaviorAnomaly)}%</span>
              </div>
              <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden border border-slate-200/50">
                <div className="h-full bg-navy-700 transition-all duration-500" style={{ width: `${Math.min(100, vessel.behaviorAnomaly)}%` }}></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-[10px] mb-0.5">
                <span className="text-slate-600 font-medium">Dwell Duration (15%)</span>
                <span className="font-mono font-bold text-navy-800">{Math.round(vessel.dwellTime)}%</span>
              </div>
              <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden border border-slate-200/50">
                <div className="h-full bg-navy-700 transition-all duration-500" style={{ width: `${Math.min(100, vessel.dwellTime)}%` }}></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-[10px] mb-0.5">
                <span className="text-slate-600 font-medium">Drift Match (10%)</span>
                <span className="font-mono font-bold text-navy-800">{vessel.approachDeparture != null ? Math.round(vessel.approachDeparture) : 0}%</span>
              </div>
              <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden border border-slate-200/50">
                <div className="h-full bg-navy-700 transition-all duration-500" style={{ width: `${vessel.approachDeparture != null ? Math.min(100, vessel.approachDeparture) : 0}%` }}></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-[10px] mb-0.5">
                <span className="text-slate-600 font-medium">AIS Dark Gap (10%)</span>
                <span className="font-mono font-bold text-navy-800">{Math.round(vessel.aisGap)}%</span>
              </div>
              <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden border border-slate-200/50">
                <div className="h-full bg-navy-700 transition-all duration-500" style={{ width: `${Math.min(100, vessel.aisGap)}%` }}></div>
              </div>
            </div>
          </div>
        </div>

        {/* Quick Stats Cards */}
        {ev.closest_approach_distance_km !== undefined && (
          <div className="grid grid-cols-4 gap-1.5 mb-4">
             <div className="bg-slate-50 border border-slate-200 rounded p-1.5 text-center flex flex-col justify-center">
               <span className="text-[8px] text-slate-500 uppercase font-bold">Approach</span>
               <span className="font-mono font-bold text-navy-900 text-[11px]">{ev.closest_approach_distance_km.toFixed(1)} km</span>
             </div>
             <div className="bg-slate-50 border border-slate-200 rounded p-1.5 text-center flex flex-col justify-center">
               <span className="text-[8px] text-slate-500 uppercase font-bold">Offset</span>
               <span className="font-mono font-bold text-navy-900 text-[11px]">{ev.time_offset_minutes.toFixed(0)} m</span>
             </div>
             <div className="bg-slate-50 border border-slate-200 rounded p-1.5 text-center flex flex-col justify-center">
               <span className="text-[8px] text-slate-500 uppercase font-bold">Dwell</span>
               <span className="font-mono font-bold text-navy-900 text-[11px]">{ev.dwell_minutes_inside_zone || 0} m</span>
             </div>
             <div className="bg-slate-50 border border-slate-200 rounded p-1.5 text-center flex flex-col justify-center">
               <span className="text-[8px] text-slate-500 uppercase font-bold">SOG (Org)</span>
               <span className="font-mono font-bold text-navy-900 text-[11px]">{ev.sog_at_origin_kn || '—'} kn</span>
             </div>
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="bg-slate-50 border-t border-slate-200 p-3 grid grid-cols-2 gap-2">
        <button 
          onClick={() => onAuditEvidence(vessel.raw)}
          className="flex items-center justify-center gap-1.5 bg-white border border-slate-300 hover:border-navy-500 hover:bg-slate-50 text-navy-800 rounded py-2 px-2 text-[10px] font-bold uppercase tracking-wider transition-colors shadow-sm"
        >
          <Activity className="w-3.5 h-3.5" />
          Audit Evidence
        </button>
        <button className="flex items-center justify-center gap-1.5 bg-navy-800 hover:bg-navy-900 text-white rounded py-2 px-2 text-[10px] font-bold uppercase tracking-wider transition-colors shadow-sm">
          <Download className="w-3.5 h-3.5" />
          Export Report
        </button>
      </div>
    </div>
  );
};
