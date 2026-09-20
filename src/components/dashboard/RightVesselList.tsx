import React, { useState } from 'react';
import { VesselCandidate } from './types';
import { Anchor, ChevronDown } from 'lucide-react';

interface RightVesselListProps {
  vessels: VesselCandidate[];
  onSelectVessel: (mmsi: string) => void;
  selectedVesselMmsi: string | null;
}

export const RightVesselList: React.FC<RightVesselListProps> = ({ vessels, onSelectVessel, selectedVesselMmsi }) => {
  const [isCollapsed, setIsCollapsed] = useState(false);

  const getRiskBadgeStyle = (riskClass: string) => {
    switch (riskClass?.toUpperCase()) {
      case 'VERY HIGH':
        return 'bg-red-700 text-white';
      case 'HIGH':
        return 'bg-amber-600 text-white';
      case 'MODERATE':
        return 'bg-blue-600 text-white';
      case 'LOW':
      default:
        return 'bg-slate-600 text-white';
    }
  };

  const getConfidenceLevel = (score: number) => {
    if (score >= 70) return 'High';
    if (score >= 40) return 'Moderate';
    return 'Low';
  };

  return (
    <aside className="absolute top-4 right-4 z-20 w-80 max-w-[calc(100vw-2rem)] bg-white/95 backdrop-blur-xs border border-gov-border rounded-gov shadow-md flex flex-col pointer-events-auto overflow-hidden transition-all duration-200">
      {/* Header */}
      <div 
        className="p-2.5 border-b border-gov-border bg-gov-light flex justify-between items-center cursor-pointer select-none"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <div className="flex items-center gap-1.5">
          <Anchor className="w-3.5 h-3.5 text-navy-800" />
          <h3 className="text-xs font-bold text-navy-800 uppercase tracking-wider">
            Vessel Candidates
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono font-bold text-navy-800 bg-white px-1.5 py-0.5 border border-gov-border rounded shadow-xs">
            {vessels.length}
          </span>
          <button 
            type="button"
            className="text-gov-muted hover:text-navy-800 transition-colors p-0.5"
            aria-label={isCollapsed ? "Expand vessel candidates" : "Collapse vessel candidates"}
          >
            <ChevronDown className={`w-3.5 h-3.5 transform transition-transform ${isCollapsed ? '-rotate-90' : ''}`} />
          </button>
        </div>
      </div>

      {/* Body: only shown when not collapsed, limited height with scroll if needed */}
      {!isCollapsed && (
        <div className="overflow-y-auto max-h-[calc(100vh-160px)] sm:max-h-[420px] p-2 space-y-1.5">
          {vessels.map((vessel, idx) => {
            const isBayesian = vessel.scoringMode === 'BAYESIAN_POSTERIOR';
            const vesselId = isBayesian && vessel.candidate_id ? vessel.candidate_id : vessel.mmsi;
            const isSelected = selectedVesselMmsi === vesselId;
            const riskBadgeStyle = getRiskBadgeStyle(vessel.riskClass || 'LOW');
            
            // For Bayesian, use posterior probability. For Legacy, use score.
            const displayPercentage = isBayesian && vessel.posterior_probability !== undefined
              ? (vessel.posterior_probability * 100).toFixed(1)
              : vessel.score;

            const confidenceLabel = isBayesian
              ? (vessel.confidence_level ?? "INDETERMINATE")
              : (vessel.confidence_level || getConfidenceLevel(vessel.score || 0));

            return (
              <div 
                key={vesselId}
                onClick={() => onSelectVessel(vesselId)}
                className={`p-2 rounded-gov border cursor-pointer transition-all ${
                  isSelected
                    ? 'border-navy-800 bg-navy-800/10 ring-1 ring-navy-800 shadow-sm'
                    : 'border-gov-border bg-white hover:border-navy-800/40 hover:bg-slate-50 shadow-xs'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  {/* Color swatch (no rank if Bayesian) */}
                  <span 
                    className="w-5 h-5 flex-shrink-0 rounded flex items-center justify-center text-[10px] font-bold text-white shadow-xs"
                    style={{ background: vessel.color }}
                  >
                    {!isBayesian && `#${idx + 1}`}
                  </span>
                  
                  {/* Vessel info */}
                  <div className="flex-1 min-w-0">
                    <h4 className="text-[11px] font-bold text-navy-800 truncate" title={vessel.name}>
                      {vessel.name || `Candidate ${vessel.mmsi}`}
                    </h4>
                    <p className="text-[9px] text-gov-muted font-mono truncate">
                      MMSI {vessel.mmsi} {isBayesian && <span className="ml-1 text-slate-400">ID: {vessel.candidate_id?.substring(0, 8)}...</span>}
                    </p>
                  </div>

                  {/* Confidence & Risk */}
                  <div className="flex flex-col items-end flex-shrink-0">
                    {isBayesian ? (
                      <>
                        <div className="flex items-center gap-1">
                          <span className="text-[8px] text-gov-muted uppercase font-semibold">Posterior:</span>
                          <span className="text-xs font-mono font-bold text-navy-800 leading-none">
                            {displayPercentage}%
                          </span>
                        </div>
                        <div className="flex items-center gap-1 mt-0.5">
                          <span className="text-[8px] text-gov-muted uppercase font-semibold">Conf:</span>
                          <span className="text-[8px] font-bold text-navy-800 leading-none">
                            {confidenceLabel}
                          </span>
                        </div>
                      </>
                    ) : (
                      <div className="flex items-baseline gap-1">
                        <span className="text-xs font-mono font-bold text-navy-800 leading-none">
                          {displayPercentage}%
                        </span>
                        <span className="text-[8px] font-medium text-gov-muted leading-none">
                          {confidenceLabel}
                        </span>
                      </div>
                    )}
                    {!isBayesian && vessel.riskClass && (
                      <span className={`px-1.5 py-0.5 mt-1 rounded text-[7px] font-bold uppercase tracking-wider leading-none ${riskBadgeStyle}`}>
                        {vessel.riskClass}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}

          {vessels.length === 0 && (
            <div className="text-center py-4 text-gov-muted text-[10px]">
              No vessel attribution data available.
            </div>
          )}
        </div>
      )}
    </aside>
  );
};
