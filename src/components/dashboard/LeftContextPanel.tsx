import React from 'react';
import { CurrentDashboardData, DashboardEntityState } from './types';
import { Shield, MapPin, Target, Droplets, Calendar, FileText, CheckCircle } from 'lucide-react';

interface LeftContextPanelProps {
  selectedEntity: DashboardEntityState;
  currentData: CurrentDashboardData;
  onGenerateReport: () => void;
}

export const LeftContextPanel: React.FC<LeftContextPanelProps> = ({ selectedEntity, currentData, onGenerateReport }) => {
  const isVisible = selectedEntity.type === 'origin' || selectedEntity.type === 'spill';

  if (!isVisible) return null;

  return (
    <aside className="absolute left-0 top-0 bottom-0 z-30 w-full sm:w-80 bg-white border-r border-gov-border shadow-2xl flex flex-col transform transition-transform duration-250 ease-in-out">
      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        {selectedEntity.type === 'origin' && <OriginDetails currentData={currentData} />}
        {selectedEntity.type === 'spill' && <SpillDetails currentData={currentData} />}
      </div>
      
      {/* Footer Action */}
      <div className="p-4 bg-gov-light border-t border-gov-border">
        <button 
          onClick={onGenerateReport}
          className="w-full py-2.5 px-3 bg-navy-800 hover:bg-navy-900 text-white rounded-gov text-xs font-semibold uppercase tracking-wider shadow-xs transition-colors flex items-center justify-center gap-2"
        >
          <FileText className="w-4 h-4" />
          <span>Generate Official Report</span>
        </button>
      </div>
    </aside>
  );
};

const OriginDetails: React.FC<{ currentData: CurrentDashboardData }> = ({ currentData }) => {
  const feature2Data = currentData.feature2Data;
  const confidence = feature2Data?.origin_confidence_score ? (feature2Data.origin_confidence_score * 100).toFixed(1) : 'N/A';
  const uncertainty = feature2Data?.origin_uncertainty_radius_km ? (feature2Data.origin_uncertainty_radius_km).toFixed(2) : '2.50';

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between border-b border-gov-border pb-3">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-wider text-gov-muted">ESTIMATED ORIGIN</span>
          <h2 className="text-lg font-extrabold text-navy-800 font-mono">Discharge Source</h2>
        </div>
        <span className="px-2 py-0.5 text-[10px] font-extrabold uppercase border rounded-gov bg-blue-100 text-blue-800 border-blue-300 flex items-center gap-1">
          <CheckCircle className="w-3 h-3" /> Confirmed
        </span>
      </div>

      <div className="bg-gov-light p-3 rounded-gov border border-gov-border space-y-2 text-xs">
        <div className="flex justify-between border-b border-gov-border pb-1.5">
          <span className="text-gov-muted flex items-center gap-1"><MapPin className="w-3 h-3"/> Coordinates:</span>
          <span className="font-mono font-bold text-navy-800">
            {feature2Data?.origin_latitude?.toFixed(4) || '—'}°N, {feature2Data?.origin_longitude?.toFixed(4) || '—'}°E
          </span>
        </div>
        <div className="flex justify-between border-b border-gov-border pb-1.5">
          <span className="text-gov-muted flex items-center gap-1"><Calendar className="w-3 h-3"/> Est. Origin Time:</span>
          <span className="font-mono font-bold text-gov-blue">{currentData.originTime}</span>
        </div>
        <div className="flex justify-between border-b border-gov-border pb-1.5">
          <span className="text-gov-muted">Detection Time:</span>
          <span className="font-mono font-bold text-navy-800">{currentData.detectionTime}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gov-muted">Backtracked:</span>
          <span className="font-mono text-navy-800 font-bold">Yes (Feature 2)</span>
        </div>
      </div>

      <div className="space-y-1">
        <div className="flex justify-between text-xs text-gov-muted mb-1">
          <span>Origin Confidence</span>
          <span className="font-mono font-bold text-blue-700">{confidence}%</span>
        </div>
        <div className="w-full h-1.5 bg-gov-light rounded-full overflow-hidden border border-gov-border">
          <div className="h-full bg-blue-600 rounded-full" style={{ width: `${confidence}%` }}></div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="bg-blue-50 p-2.5 rounded-gov border border-blue-200">
          <span className="text-[10px] text-blue-800 uppercase font-semibold">Uncertainty Radius</span>
          <p className="text-sm font-extrabold text-blue-900">±{uncertainty} km</p>
        </div>
        <div className="bg-blue-50 p-2.5 rounded-gov border border-blue-200">
          <span className="text-[10px] text-blue-800 uppercase font-semibold">Sea State</span>
          <p className="text-sm font-extrabold text-blue-900">Moderate (~3)</p>
        </div>
        <div className="bg-blue-50 p-2.5 rounded-gov border border-blue-200">
          <span className="text-[10px] text-blue-800 uppercase font-semibold">Wind</span>
          <p className="text-sm font-extrabold text-blue-900">12 kts NW</p>
        </div>
        <div className="bg-blue-50 p-2.5 rounded-gov border border-blue-200">
          <span className="text-[10px] text-blue-800 uppercase font-semibold">Current</span>
          <p className="text-sm font-extrabold text-blue-900">1.2 kts E</p>
        </div>
      </div>

      <div className="flex items-center justify-between bg-slate-100 p-2 rounded border border-slate-200 text-xs">
         <span className="text-slate-600 font-semibold flex items-center gap-1">
           <Shield className="w-3.5 h-3.5"/> Satellite Source:
         </span>
         <span className="font-mono text-slate-800 truncate max-w-[120px]" title={currentData.source}>{currentData.source}</span>
      </div>
    </div>
  );
};

const SpillDetails: React.FC<{ currentData: CurrentDashboardData }> = ({ currentData }) => {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between border-b border-gov-border pb-3">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-wider text-gov-muted">SAR DETECTED SLICK</span>
          <h2 className="text-lg font-extrabold text-navy-800 font-mono">Oil Spill Details</h2>
        </div>
        <span className={`px-2 py-0.5 text-[10px] font-extrabold uppercase border rounded-gov ${
          currentData.confidence.includes('HIGH') 
            ? 'bg-red-100 text-red-800 border-red-300'
            : currentData.confidence.includes('MEDIUM')
            ? 'bg-amber-100 text-amber-800 border-amber-300'
            : 'bg-gray-100 text-gray-800 border-gray-300'
        }`}>
          {currentData.confidence}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="bg-gov-light p-2.5 rounded-gov border border-gov-border">
          <span className="text-[10px] text-gov-muted uppercase font-semibold flex items-center gap-1"><Droplets className="w-3 h-3"/> AREA</span>
          <p className="text-sm font-extrabold text-navy-800">{currentData.area}</p>
        </div>
        <div className="bg-gov-light p-2.5 rounded-gov border border-gov-border">
          <span className="text-[10px] text-gov-muted uppercase font-semibold">EST. VOLUME</span>
          <p className="text-sm font-extrabold text-navy-800">{currentData.estVolume}</p>
        </div>
        <div className="bg-gov-light p-2.5 rounded-gov border border-gov-border">
          <span className="text-[10px] text-gov-muted uppercase font-semibold">SLICK LENGTH</span>
          <p className="text-sm font-extrabold text-navy-800">{currentData.length}</p>
        </div>
        <div className="bg-gov-light p-2.5 rounded-gov border border-gov-border">
          <span className="text-[10px] text-gov-muted uppercase font-semibold">SLICK WIDTH</span>
          <p className="text-sm font-extrabold text-navy-800">{currentData.width}</p>
        </div>
      </div>

      <div className="bg-gov-light p-3 rounded-gov border border-gov-border space-y-2 text-xs">
        <div className="flex justify-between border-b border-gov-border pb-1.5">
          <span className="text-gov-muted">Centroid:</span>
          <span className="font-mono font-bold text-navy-800">
             {currentData.spillInfo?.spill_latitude != null ? currentData.spillInfo.spill_latitude.toFixed(4) : (currentData.center[0] || 0).toFixed(4)}°N,{' '}
             {currentData.spillInfo?.spill_longitude != null ? currentData.spillInfo.spill_longitude.toFixed(4) : (currentData.center[1] || 0).toFixed(4)}°E
          </span>
        </div>
        <div className="flex justify-between border-b border-gov-border pb-1.5">
          <span className="text-gov-muted">Detection Time:</span>
          <span className="font-mono font-bold text-navy-800">{currentData.detectionTime}</span>
        </div>
        <div className="flex justify-between border-b border-gov-border pb-1.5">
          <span className="text-gov-muted">Satellite:</span>
          <span className="font-mono text-navy-800 max-w-[140px] truncate">{currentData.source}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gov-muted">SAR Detection:</span>
          <span className="font-mono text-emerald-700 font-bold">Confirmed</span>
        </div>
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded p-3 text-xs space-y-2">
        <div className="flex justify-between items-center text-amber-900 font-semibold border-b border-amber-200 pb-1">
           <span>Spill Classification</span>
           <span className="uppercase text-[10px] px-1.5 py-0.5 bg-amber-200 rounded">Category B</span>
        </div>
        <div className="flex justify-between text-amber-800">
          <span>Environmental Risk</span>
          <span className="font-bold">Moderate</span>
        </div>
        <div className="flex justify-between text-amber-800">
          <span>Forecast Duration</span>
          <span className="font-bold font-mono">48h Hydrodynamic</span>
        </div>
      </div>
    </div>
  );
};
