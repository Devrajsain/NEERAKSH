import React, { useState } from 'react';
import { VesselCandidate } from './types';
import { Ship, ChevronDown, ChevronUp } from 'lucide-react';
import { getShipImage } from './shipImages';

interface RightVesselListProps {
  vessels: VesselCandidate[];
  onSelectVessel: (mmsi: string) => void;
  selectedVesselMmsi?: string | null;
}

export const RightVesselList: React.FC<RightVesselListProps> = ({ vessels, onSelectVessel, selectedVesselMmsi }) => {
  const [collapsed, setCollapsed] = useState(false);
  const [showHighRisk, setShowHighRisk] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  const isBayesianMode = vessels.some(v => v.scoringMode === 'BAYESIAN_POSTERIOR');
  if (vessels.length === 0) return null;

  return (
    <aside className={`w-full flex flex-col pointer-events-auto vessel-list-panel rounded-lg overflow-hidden transition-all duration-300`}>
      {/* Header */}
      <div
        className="flex items-center justify-between px-3 py-2 bg-navy-800 text-white cursor-pointer select-none"
        onClick={() => setCollapsed(v => !v)}
      >
        <div className="flex items-center gap-2">
          <Ship className="w-3.5 h-3.5" />
          <span className="text-[10px] font-bold uppercase tracking-widest">Vessel Candidates</span>
          <span className="text-[9px] bg-white/20 px-1.5 py-0.5 rounded font-bold">{vessels.length}</span>
        </div>
        {collapsed ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
      </div>

      {!collapsed && (
        <div className="overflow-y-auto max-h-[50vh]">
          {vessels.map((v, idx) => {
            const isBay = v.scoringMode === 'BAYESIAN_POSTERIOR';
            const vid = isBay && v.candidate_id ? v.candidate_id : v.mmsi;
            const sel = selectedVesselMmsi === vid;
            const pct = isBay ? Math.round((v.posterior_probability ?? 0) * 100) : (v.score ?? 0);
            const barColor = pct >= 65 ? '#DC2626' : pct >= 35 ? '#D97706' : '#8B5CF6';

            return (
              <div
                key={vid}
                onClick={() => onSelectVessel(vid)}
                className={`flex items-center gap-2.5 px-3 py-2 cursor-pointer border-b border-slate-100 transition-colors ${
                  sel ? 'bg-blue-50 border-l-2 border-l-blue-600' : 'hover:bg-slate-50'
                }`}
              >
                {/* Ship image */}
                <div className="w-8 h-8 rounded bg-slate-100 flex items-center justify-center flex-shrink-0 border border-slate-200 overflow-hidden">
                  <img src={getShipImage(idx)} alt="" className="w-7 h-7 object-contain" />
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-navy-800 truncate">{v.name || v.mmsi}</span>
                    <span className="text-[10px] font-black ml-1 flex-shrink-0" style={{ color: barColor }}>{pct}%</span>
                  </div>
                  <div className="text-[9px] text-gov-muted font-mono">MMSI {v.mmsi}</div>
                  {/* Bar */}
                  <div className="conf-track mt-1">
                    <div className="conf-fill" style={{ width: `${pct}%`, background: barColor }} />
                  </div>
                  <div className="text-[8px] text-slate-400 mt-0.5">{isBay ? 'Posterior Probability' : 'Attribution Score'}</div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </aside>
  );
};
