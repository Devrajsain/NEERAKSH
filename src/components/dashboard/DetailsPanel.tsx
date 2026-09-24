import React from 'react';
import { CurrentDashboardData, DashboardEntityState } from './types';
import { X, MapPin, Calendar, Shield, Droplets, Wind, Waves, Navigation, FileText, Target } from 'lucide-react';

interface DetailsPanelProps {
  selectedEntity: DashboardEntityState;
  currentData: CurrentDashboardData;
  onGenerateReport: () => void;
  onClose: () => void;
}

export const DetailsPanel: React.FC<DetailsPanelProps> = ({ selectedEntity, currentData, onGenerateReport, onClose }) => {
  const isVisible = selectedEntity.type === 'origin' || selectedEntity.type === 'spill';
  if (!isVisible) return null;

  return (
    <aside className="absolute left-0 top-0 bottom-0 z-30 w-80 context-panel slide-in-left flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-slate-50">
        <div className="flex items-center gap-2">
          {selectedEntity.type === 'origin' ? <Target className="w-4 h-4 text-red-600" /> : <Droplets className="w-4 h-4 text-red-600" />}
          <h2 className="text-xs font-black uppercase tracking-wider text-navy-800">
            {selectedEntity.type === 'origin' ? 'Origin Point Details' : 'Spill Detection Details'}
          </h2>
        </div>
        <button onClick={onClose} className="p-1 hover:bg-slate-200 rounded transition-colors"><X className="w-4 h-4 text-slate-500" /></button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {selectedEntity.type === 'origin' && <OriginPanel data={currentData} />}
        {selectedEntity.type === 'spill' && <SpillPanel data={currentData} />}
      </div>

      <div className="p-3 border-t border-slate-200 bg-slate-50">
        <button onClick={onGenerateReport} className="w-full py-2 bg-navy-800 hover:bg-navy-700 text-white rounded text-[10px] font-bold uppercase tracking-wider flex items-center justify-center gap-2 transition-colors">
          <FileText className="w-3.5 h-3.5" /> View Full Analysis
        </button>
      </div>
    </aside>
  );
};

const Row: React.FC<{ label: string; value: string | React.ReactNode }> = ({ label, value }) => (
  <div className="detail-row"><span className="detail-label">{label}</span><span className="detail-value">{value}</span></div>
);

const OriginPanel: React.FC<{ data: CurrentDashboardData }> = ({ data }) => {
  const f2 = data.feature2Data;
  const conf = f2?.origin_confidence_score ? (f2.origin_confidence_score * 100).toFixed(1) : '—';
  const uncert = f2?.origin_uncertainty_radius_km?.toFixed(2) || '2.50';
  return (
    <div className="space-y-4">
      <div className="bg-red-50 border border-red-200 rounded-lg p-3 space-y-0">
        <Row label="Spill ID" value={data.activeCase || '—'} />
        <Row label="Origin Latitude" value={`${f2?.origin_latitude?.toFixed(5) || '—'}°N`} />
        <Row label="Origin Longitude" value={`${f2?.origin_longitude?.toFixed(5) || '—'}°E`} />
        <Row label="Est. Origin Time" value={data.originTime || '—'} />
        <Row label="Detection Time" value={data.detectionTime || '—'} />
        <Row label="Spill Area" value={data.area || '—'} />
      </div>

      <div>
        <div className="flex justify-between items-center text-[10px] mb-1">
          <span className="font-bold text-navy-800 uppercase">Origin Confidence</span>
          <span className="font-black text-blue-700">{conf}%</span>
        </div>
        <div className="conf-track"><div className="conf-fill bg-blue-600" style={{ width: `${conf}%` }} /></div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {[
          { icon: <Shield className="w-3 h-3" />, label: 'Uncertainty', val: `±${uncert} km` },
          { icon: <Waves className="w-3 h-3" />, label: 'Sea State', val: 'Moderate (~3)' },
          { icon: <Wind className="w-3 h-3" />, label: 'Wind', val: '12 kts NW' },
          { icon: <Navigation className="w-3 h-3" />, label: 'Current', val: '1.2 kts E' },
        ].map((item, i) => (
          <div key={i} className="bg-blue-50 border border-blue-200 rounded p-2">
            <div className="flex items-center gap-1 text-[9px] text-blue-700 font-semibold uppercase mb-0.5">{item.icon}{item.label}</div>
            <div className="text-[12px] font-extrabold text-blue-900">{item.val}</div>
          </div>
        ))}
      </div>

      <div className="bg-slate-50 border border-slate-200 rounded p-2.5 flex justify-between items-center text-[10px]">
        <span className="text-slate-600 font-semibold flex items-center gap-1"><MapPin className="w-3 h-3" /> Detection Source</span>
        <span className="font-mono text-navy-800 font-bold truncate max-w-[120px]">{data.source || 'Sentinel-1'}</span>
      </div>
    </div>
  );
};

const SpillPanel: React.FC<{ data: CurrentDashboardData }> = ({ data }) => (
  <div className="space-y-4">
    <div className="grid grid-cols-2 gap-2">
      {[
        { label: 'Area', val: data.area },
        { label: 'Volume', val: data.estVolume },
        { label: 'Length', val: data.length },
        { label: 'Width', val: data.width },
      ].map((item, i) => (
        <div key={i} className="bg-red-50 border border-red-200 rounded p-2.5">
          <div className="text-[9px] text-red-700 font-semibold uppercase">{item.label}</div>
          <div className="text-sm font-extrabold text-red-900">{item.val || '—'}</div>
        </div>
      ))}
    </div>

    <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-0">
      <Row label="Centroid" value={`${data.center[0]?.toFixed(4)}°N, ${data.center[1]?.toFixed(4)}°E`} />
      <Row label="Detection Time" value={data.detectionTime || '—'} />
      <Row label="Satellite" value={data.source || '—'} />
      <Row label="Confidence" value={data.confidence || '—'} />
      <Row label="SAR Detection" value={<span className="text-green-700 font-bold">Confirmed</span>} />
    </div>

    <div className="bg-amber-50 border border-amber-200 rounded p-3 text-[10px] space-y-1">
      <div className="flex justify-between font-semibold text-amber-900 border-b border-amber-200 pb-1">
        <span>Classification</span><span className="px-1.5 py-0.5 bg-amber-200 rounded text-[9px] uppercase">Category B</span>
      </div>
      <div className="flex justify-between text-amber-800"><span>Environmental Risk</span><span className="font-bold">Moderate</span></div>
      <div className="flex justify-between text-amber-800"><span>Forecast Duration</span><span className="font-bold font-mono">48h</span></div>
    </div>
  </div>
);
