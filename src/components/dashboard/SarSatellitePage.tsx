import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  Satellite, Layers, Activity, Download, FileText, Map, Shield,
  Clock, CheckCircle,
  Target, Ruler, Navigation, BarChart3, Zap, Eye,
  FileDown, RefreshCw, Globe, Database, Cpu, Info
} from 'lucide-react';

interface SarSatellitePageProps {
  currentData?: any;
}

interface LayerState {
  sar: boolean;
  spillBoundary: boolean;
  detectionMask: boolean;
  confidenceHeatmap: boolean;
  aisOverlay: boolean;
}

const BeforeAfterSlider: React.FC<{ layers: LayerState }> = ({ layers }) => {
  const [sliderPos, setSliderPos] = useState(50);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const updateSlider = useCallback((clientX: number) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(clientX - rect.left, rect.width));
    setSliderPos((x / rect.width) * 100);
  }, []);

  const onMouseDown = (e: React.MouseEvent) => { setIsDragging(true); updateSlider(e.clientX); };
  const onMouseMove = useCallback((e: MouseEvent) => { if (isDragging) updateSlider(e.clientX); }, [isDragging, updateSlider]);
  const onMouseUp = useCallback(() => setIsDragging(false), []);
  const onTouchMove = useCallback((e: TouchEvent) => { if (isDragging) updateSlider(e.touches[0].clientX); }, [isDragging, updateSlider]);

  useEffect(() => {
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    window.addEventListener('touchmove', onTouchMove);
    window.addEventListener('touchend', onMouseUp);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      window.removeEventListener('touchmove', onTouchMove);
      window.removeEventListener('touchend', onMouseUp);
    };
  }, [onMouseMove, onMouseUp, onTouchMove]);

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full overflow-hidden select-none cursor-col-resize"
      onMouseDown={onMouseDown}
      onTouchStart={(e) => { setIsDragging(true); updateSlider(e.touches[0].clientX); }}
    >
      <div className="absolute inset-0">
        <img src="/sar_detected.jpg" alt="AI-Detected Spill" className="w-full h-full object-cover" draggable={false} />
        {layers.spillBoundary && (
          <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 100 100" preserveAspectRatio="none">
            <polygon points="28,22 40,18 55,20 65,32 68,48 62,62 48,70 33,68 24,55 22,38" fill="rgba(239,68,68,0.08)" stroke="#ef4444" strokeWidth="0.4" strokeDasharray="2,1" />
          </svg>
        )}
        {layers.detectionMask && (
          <div className="absolute inset-0 pointer-events-none" style={{ background: 'radial-gradient(ellipse 30% 28% at 45% 44%, rgba(239,68,68,0.22) 0%, rgba(239,68,68,0.08) 60%, transparent 100%)' }} />
        )}
        {layers.aisOverlay && (
          <div className="absolute top-[20%] left-[62%] pointer-events-none">
            <div className="w-0 h-0 border-l-[4px] border-r-[4px] border-b-[7px] border-l-transparent border-r-transparent border-b-white opacity-90" />
            <div className="text-[7px] text-white font-mono mt-0.5 bg-black/50 px-1 rounded">MT OCEAN V.</div>
          </div>
        )}
        <div className="absolute bottom-3 right-3 bg-red-600/90 backdrop-blur-sm text-white text-[9px] font-black uppercase tracking-widest px-2.5 py-1 rounded border border-red-400/40">AI DETECTED</div>
      </div>

      <div className="absolute inset-0 overflow-hidden" style={{ width: `${sliderPos}%` }}>
        <div className="absolute inset-0" style={{ width: `${(100 / Math.max(sliderPos, 0.1)) * 100}%` }}>
          <img src="/sar_original.jpg" alt="Original SAR" className="w-full h-full object-cover" draggable={false} />
        </div>
        <div className="absolute bottom-3 left-3 bg-slate-800/90 backdrop-blur-sm text-cyan-300 text-[9px] font-black uppercase tracking-widest px-2.5 py-1 rounded border border-cyan-400/30">ORIGINAL SAR</div>
      </div>

      <div className="absolute top-0 bottom-0 z-10 pointer-events-none" style={{ left: `${sliderPos}%`, transform: 'translateX(-50%)' }}>
        <div className="absolute inset-0 w-[2px] mx-auto bg-cyan-400 shadow-[0_0_12px_rgba(34,211,238,0.8)]" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-[#0a1a30] border-2 border-cyan-400 flex items-center justify-center shadow-[0_0_20px_rgba(34,211,238,0.6)] pointer-events-auto cursor-col-resize">
          <div className="flex gap-0.5">
            <div className="w-0.5 h-4 bg-cyan-400 rounded" />
            <div className="w-0.5 h-4 bg-cyan-400 rounded" />
          </div>
        </div>
      </div>

      <div className="absolute inset-0 pointer-events-none opacity-10" style={{ backgroundImage: 'linear-gradient(rgba(34,211,238,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(34,211,238,0.3) 1px, transparent 1px)', backgroundSize: '50px 50px' }} />
      <div className="absolute top-2 left-2 text-[7px] font-mono text-cyan-300/60 bg-black/40 px-1.5 py-0.5 rounded">22 deg 28 N 69 deg 12 E</div>
      <div className="absolute top-2 right-2 text-[7px] font-mono text-cyan-300/60 bg-black/40 px-1.5 py-0.5 rounded">22 deg 32 N 69 deg 18 E</div>
    </div>
  );
};

const ConfidenceHeatmap: React.FC = () => (
  <div className="relative w-full h-full">
    <img src="/sar_original.jpg" alt="SAR base" className="absolute inset-0 w-full h-full object-cover opacity-60" />
    <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
      <defs>
        <filter id="heatBlur2"><feGaussianBlur stdDeviation="2.5" /></filter>
      </defs>
      <ellipse cx="45" cy="44" rx="28" ry="24" fill="#ef4444" fillOpacity="0.15" filter="url(#heatBlur2)" />
      <ellipse cx="45" cy="44" rx="20" ry="17" fill="#f97316" fillOpacity="0.2" filter="url(#heatBlur2)" />
      <ellipse cx="45" cy="44" rx="13" ry="11" fill="#eab308" fillOpacity="0.28" filter="url(#heatBlur2)" />
      <ellipse cx="45" cy="44" rx="7" ry="6" fill="#22d3ee" fillOpacity="0.4" filter="url(#heatBlur2)" />
      <ellipse cx="45" cy="44" rx="3" ry="2.5" fill="#ffffff" fillOpacity="0.7" filter="url(#heatBlur2)" />
      <ellipse cx="45" cy="44" rx="28" ry="24" fill="none" stroke="#ef4444" strokeWidth="0.3" strokeDasharray="2,1" opacity="0.5" />
      <ellipse cx="45" cy="44" rx="20" ry="17" fill="none" stroke="#f97316" strokeWidth="0.3" strokeDasharray="1.5,1" opacity="0.5" />
      <ellipse cx="45" cy="44" rx="13" ry="11" fill="none" stroke="#eab308" strokeWidth="0.3" opacity="0.5" />
      <ellipse cx="45" cy="44" rx="7" ry="6" fill="none" stroke="#22d3ee" strokeWidth="0.3" opacity="0.7" />
    </svg>
    <div className="absolute right-2 top-1/2 -translate-y-1/2 flex flex-col items-center gap-0">
      <span className="text-[7px] font-mono text-white mb-1">HIGH</span>
      <div className="w-2 h-20 rounded-sm" style={{ background: 'linear-gradient(to bottom, #ffffff, #22d3ee, #eab308, #f97316, #ef4444, #1e1e2e)' }} />
      <span className="text-[7px] font-mono text-white/50 mt-1">LOW</span>
    </div>
  </div>
);

const TimelineStep: React.FC<{ step: number; label: string; subLabel: string; time: string; status: 'done' | 'active' | 'pending'; isLast?: boolean }> = ({ step, label, subLabel, time, status, isLast }) => (
  <div className="flex gap-3 min-w-0">
    <div className="flex flex-col items-center flex-shrink-0">
      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-black border-2 transition-all ${status === 'done' ? 'bg-emerald-500 border-emerald-400 text-white shadow-[0_0_10px_rgba(16,185,129,0.5)]' : status === 'active' ? 'bg-cyan-500 border-cyan-400 text-white shadow-[0_0_12px_rgba(34,211,238,0.6)] animate-pulse' : 'bg-slate-700 border-slate-600 text-slate-400'}`}>
        {status === 'done' ? <CheckCircle className="w-3.5 h-3.5" /> : status === 'active' ? <Zap className="w-3.5 h-3.5" /> : step}
      </div>
      {!isLast && <div className={`w-0.5 flex-1 mt-1 min-h-[28px] ${status === 'done' ? 'bg-emerald-500/50' : 'bg-slate-700'}`} />}
    </div>
    <div className="pb-5 min-w-0 flex-1">
      <div className="flex items-center justify-between gap-2">
        <span className={`text-[11px] font-bold ${status === 'done' ? 'text-emerald-400' : status === 'active' ? 'text-cyan-300' : 'text-slate-500'}`}>{label}</span>
        <span className={`text-[9px] font-mono flex-shrink-0 ${status === 'pending' ? 'text-slate-600' : 'text-slate-400'}`}>{time}</span>
      </div>
      <p className="text-[9px] text-slate-500 mt-0.5 leading-tight">{subLabel}</p>
    </div>
  </div>
);

export const SarSatellitePage: React.FC<SarSatellitePageProps> = ({ currentData }) => {
  const [layers, setLayers] = useState<LayerState>({ sar: true, spillBoundary: true, detectionMask: true, confidenceHeatmap: false, aisOverlay: true });
  const [activeTab, setActiveTab] = useState<'heatmap' | 'timeline' | 'metadata'>('heatmap');
  const toggleLayer = (key: keyof LayerState) => setLayers(prev => ({ ...prev, [key]: !prev[key] }));

  const detectionCards = [
    { label: 'Spill Area', value: currentData?.area || '284 km2', unit: '', icon: <Map className="w-4 h-4" />, color: '#ef4444', glow: 'rgba(239,68,68,0.3)' },
    { label: 'Confidence', value: '92%', unit: 'HIGH', icon: <Activity className="w-4 h-4" />, color: '#22d3ee', glow: 'rgba(34,211,238,0.3)' },
    { label: 'Acquisition', value: '06:45 UTC', unit: '22 SEP 2026', icon: <Clock className="w-4 h-4" />, color: '#a78bfa', glow: 'rgba(167,139,250,0.3)' },
    { label: 'Satellite', value: 'SENTINEL-1A', unit: 'ESA / ISRO', icon: <Satellite className="w-4 h-4" />, color: '#34d399', glow: 'rgba(52,211,153,0.3)' },
  ];

  const layerConfig = [
    { key: 'sar' as keyof LayerState, label: 'SAR Imagery', color: '#22d3ee', icon: <Globe className="w-3 h-3" /> },
    { key: 'spillBoundary' as keyof LayerState, label: 'Spill Boundary', color: '#ef4444', icon: <Target className="w-3 h-3" /> },
    { key: 'detectionMask' as keyof LayerState, label: 'Detection Mask', color: '#f97316', icon: <Layers className="w-3 h-3" /> },
    { key: 'confidenceHeatmap' as keyof LayerState, label: 'Confidence Heatmap', color: '#eab308', icon: <Activity className="w-3 h-3" /> },
    { key: 'aisOverlay' as keyof LayerState, label: 'AIS Overlay', color: '#a78bfa', icon: <Navigation className="w-3 h-3" /> },
  ];

  const geometryMetrics = [
    { label: 'Spill Area', value: '284.3', unit: 'km2', icon: <Target className="w-2.5 h-2.5" /> },
    { label: 'Perimeter', value: '89.7', unit: 'km', icon: <Ruler className="w-2.5 h-2.5" /> },
    { label: 'Max Length', value: '28.4', unit: 'km', icon: <Ruler className="w-2.5 h-2.5" /> },
    { label: 'Max Width', value: '10.2', unit: 'km', icon: <Ruler className="w-2.5 h-2.5" /> },
    { label: 'Centroid Lat', value: '22.47 N', unit: '', icon: <Navigation className="w-2.5 h-2.5" /> },
    { label: 'Centroid Lon', value: '69.21 E', unit: '', icon: <Navigation className="w-2.5 h-2.5" /> },
  ];

  const satMetadata = [
    { label: 'Mission', value: 'Sentinel-1A' },
    { label: 'Sensor', value: 'C-Band SAR' },
    { label: 'Polarization', value: 'VV / VH' },
    { label: 'Resolution', value: '10 m/px' },
    { label: 'Orbit', value: 'Ascending #78' },
    { label: 'Incidence Angle', value: '36.4 deg' },
    { label: 'Pass Time', value: '06:45:12 UTC' },
    { label: 'Coverage', value: '250 x 250 km' },
  ];

  const timelineSteps = [
    { step: 1, label: 'Upload & Ingest', subLabel: 'SAR GeoTIFF ingested into processing queue', time: '06:45:12', status: 'done' as const },
    { step: 2, label: 'Preprocessing', subLabel: 'Radiometric calibration, speckle filtering, land masking', time: '06:45:48', status: 'done' as const },
    { step: 3, label: 'AI Detection', subLabel: 'U-Net segmentation model (F1=0.91), threshold @ 0.5', time: '06:46:22', status: 'done' as const },
    { step: 4, label: 'Boundary Extraction', subLabel: 'GeoJSON polygon generation, centroid computation', time: '06:46:55', status: 'done' as const },
    { step: 5, label: 'Report Generation', subLabel: 'PDF report and metadata XML export', time: '06:47:10', status: 'active' as const },
  ];

  return (
    <div className="absolute inset-0 bg-slate-100 flex flex-col overflow-hidden text-slate-800" style={{ fontFamily: "'Inter', system-ui, sans-serif" }}>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden min-h-0">

        {/* Left Column */}
        <div className="w-52 flex-shrink-0 bg-white border-r border-slate-200 flex flex-col overflow-y-auto">
          {/* Layer Toggles */}
          <div className="p-3 border-b border-slate-200">
            <div className="flex items-center gap-2 mb-2.5">
              <Layers className="w-3.5 h-3.5 text-cyan-700" />
              <span className="text-[10px] font-black uppercase tracking-widest text-slate-800">Layer Control</span>
            </div>
            <div className="space-y-1.5">
              {layerConfig.map((lyr) => {
                const isOn = layers[lyr.key];
                return (
                  <button key={lyr.key} onClick={() => toggleLayer(lyr.key)} className="w-full flex items-center gap-2 px-2.5 py-2 rounded-md transition-all text-left" style={{ background: isOn ? `${lyr.color}12` : '#f8fafc', border: `1px solid ${isOn ? lyr.color + '60' : '#e2e8f0'}` }}>
                    <div className="flex-shrink-0" style={{ color: isOn ? lyr.color : '#64748b' }}>{lyr.icon}</div>
                    <span className="text-[10px] font-bold flex-1 min-w-0 truncate" style={{ color: isOn ? '#0f172a' : '#64748b' }}>{lyr.label}</span>
                    <div className="flex-shrink-0 w-7 h-4 rounded-full relative" style={{ background: isOn ? lyr.color : '#cbd5e1' }}>
                      <div className={`absolute top-0.5 w-3 h-3 rounded-full bg-white shadow-sm transition-all ${isOn ? 'right-0.5' : 'left-0.5'}`} />
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Geometry */}
          <div className="p-3 border-b border-slate-200">
            <div className="flex items-center gap-2 mb-2.5">
              <Ruler className="w-3.5 h-3.5 text-cyan-700" />
              <span className="text-[10px] font-black uppercase tracking-widest text-slate-800">Geometry</span>
            </div>
            <div className="space-y-0">
              {geometryMetrics.map((m) => (
                <div key={m.label} className="flex items-center justify-between gap-2 py-1.5 border-b border-slate-200 last:border-0">
                  <div className="flex items-center gap-1.5 text-slate-700">{m.icon}<span className="text-[9px] font-bold text-slate-800 uppercase tracking-wider">{m.label}</span></div>
                  <span className="text-[10px] font-black text-cyan-700 font-mono">{m.value}<span className="text-[8px] text-slate-600 font-bold ml-0.5">{m.unit}</span></span>
                </div>
              ))}
            </div>
          </div>

          {/* Export */}
          <div className="p-3">
            <div className="flex items-center gap-2 mb-2.5">
              <Download className="w-3.5 h-3.5 text-cyan-700" />
              <span className="text-[10px] font-black uppercase tracking-widest text-slate-800">Export</span>
            </div>
            <div className="space-y-1.5">
              {[
                { label: 'GeoJSON', icon: <Globe className="w-3 h-3" />, color: '#22d3ee' },
                { label: 'Detection Mask', icon: <Map className="w-3 h-3" />, color: '#f97316' },
                { label: 'Detection Report', icon: <FileText className="w-3 h-3" />, color: '#a78bfa' },
              ].map((exp) => (
                <button key={exp.label} className="w-full flex items-center gap-2 px-2.5 py-2 rounded-md text-left transition-all hover:scale-[1.02] active:scale-[0.98]" style={{ background: `${exp.color}15`, border: `1px solid ${exp.color}50`, color: '#0f172a' }} onClick={() => alert(`Exporting ${exp.label}...`)}>
                  <div style={{ color: exp.color }}>{exp.icon}</div>
                  <span className="text-[9px] font-black uppercase tracking-wider flex-1">{exp.label}</span>
                  <FileDown className="w-3 h-3 opacity-60" />
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Center: Image Viewer */}
        <div className="flex-1 flex flex-col min-w-0 min-h-0">
          <div className="flex-shrink-0 bg-white border-b border-slate-200 px-4 py-2 flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-[10px] text-slate-500">
              <Eye className="w-3 h-3 text-cyan-600" />
              <span className="font-semibold text-slate-800">SAR Image Viewer</span>
              <span className="text-slate-500">-- Drag slider to compare Before / After</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[9px] font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">C-SAR - VV - 10m</span>
              <span className="text-[9px] font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">GRD - IW</span>
            </div>
          </div>
          <div className="flex-1 relative min-h-0 bg-black">
            <BeforeAfterSlider layers={layers} />
            <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-0.5 pointer-events-none">
              <div className="flex">
                <div className="w-16 h-1.5 border-b border-l border-r border-white/50" />
                <div className="w-16 h-1.5 border-b border-r border-white/50 bg-white/20" />
              </div>
              <span className="text-[7px] text-white/50 font-mono">0 --- 10 km</span>
            </div>
            <div className="absolute bottom-8 right-4 pointer-events-none">
              <svg viewBox="0 0 32 32" className="w-8 h-8">
                <circle cx="16" cy="16" r="15" fill="rgba(0,0,0,0.5)" stroke="rgba(255,255,255,0.2)" strokeWidth="0.5" />
                <polygon points="16,4 19,16 16,14 13,16" fill="#ef4444" />
                <polygon points="16,28 19,16 16,18 13,16" fill="rgba(255,255,255,0.5)" />
                <circle cx="16" cy="16" r="2" fill="white" />
                <text x="16" y="3" textAnchor="middle" fill="white" fontSize="4" fontFamily="monospace" fontWeight="bold">N</text>
              </svg>
            </div>
            <div className="absolute top-2 left-1/2 -translate-x-1/2 bg-[#060f20]/80 backdrop-blur-sm border border-slate-700/40 rounded px-3 py-1 flex items-center gap-2 pointer-events-none">
              <span className="text-[8px] text-slate-500 uppercase tracking-widest">Arabian Sea, Gujarat Coast</span>
              <span className="text-[8px] text-slate-700">|</span>
              <span className="text-[8px] text-cyan-400 font-mono">22.47 N / 69.21 E</span>
            </div>
          </div>
        </div>

        {/* Right Column */}
        <div className="w-64 flex-shrink-0 bg-white border-l border-slate-200 flex flex-col overflow-hidden">
          <div className="flex-shrink-0 border-b border-slate-200">
            <div className="flex">
              {[
                { id: 'heatmap', label: 'Heatmap', icon: <BarChart3 className="w-3 h-3" /> },
                { id: 'timeline', label: 'Timeline', icon: <Clock className="w-3 h-3" /> },
                { id: 'metadata', label: 'Metadata', icon: <Database className="w-3 h-3" /> },
              ].map(tab => (
                <button key={tab.id} onClick={() => setActiveTab(tab.id as any)} className={`flex-1 flex items-center justify-center gap-1 py-2.5 text-[9px] font-black uppercase tracking-wider transition-all border-b-2 ${activeTab === tab.id ? 'text-cyan-700 border-cyan-600 bg-cyan-50' : 'text-slate-500 border-transparent hover:text-slate-800'}`}>
                  {tab.icon}<span>{tab.label}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-3">
            {activeTab === 'heatmap' && (
              <div className="space-y-3">
                <div className="text-[9px] text-slate-800 uppercase tracking-wider font-bold flex items-center gap-1.5"><Activity className="w-3 h-3 text-cyan-600" />Detection Confidence Heatmap</div>
                <div className="relative w-full aspect-video rounded-lg overflow-hidden border border-slate-300"><ConfidenceHeatmap /></div>
                <div className="space-y-1">
                  {[
                    { color: '#ffffff', label: 'Core (>=90%)', value: '94%' },
                    { color: '#22d3ee', label: 'High (75-89%)', value: '82%' },
                    { color: '#eab308', label: 'Medium (60-74%)', value: '71%' },
                    { color: '#f97316', label: 'Low (45-59%)', value: '58%' },
                    { color: '#ef4444', label: 'Uncertain (<45%)', value: '37%' },
                  ].map(item => (
                    <div key={item.label} className="flex items-center gap-2 bg-slate-50 p-1.5 rounded">
                      <div className="w-2.5 h-2.5 rounded-sm flex-shrink-0 border border-slate-200" style={{ background: item.color, opacity: 0.85 }} />
                      <span className="text-[9px] font-bold text-slate-800 flex-1">{item.label}</span>
                      <span className="text-[9px] font-black font-mono text-slate-900">{item.value}</span>
                    </div>
                  ))}
                </div>
                <div className="bg-slate-50 rounded-lg border border-slate-200 p-3 shadow-sm">
                  <div className="text-[8px] text-slate-700 font-bold uppercase tracking-wider mb-1.5">Overall Detection Confidence</div>
                  <div className="text-[28px] font-black text-cyan-700 leading-none">92<span className="text-[14px] text-slate-600 font-bold">%</span></div>
                  <div className="mt-2 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                    <div className="h-full rounded-full bg-gradient-to-r from-cyan-600 to-cyan-400" style={{ width: '92%' }} />
                  </div>
                  <div className="text-[8px] text-emerald-700 font-black mt-1.5 flex items-center gap-1"><CheckCircle className="w-2.5 h-2.5" />HIGH CONFIDENCE - CONFIRMED SPILL</div>
                </div>
              </div>
            )}

            {activeTab === 'timeline' && (
              <div className="space-y-1">
                <div className="text-[9px] text-slate-800 uppercase tracking-wider font-bold flex items-center gap-1.5 mb-3"><Clock className="w-3 h-3 text-cyan-600" />Processing Pipeline</div>
                {timelineSteps.map((step, idx) => (
                  <TimelineStep key={step.step} {...step} isLast={idx === timelineSteps.length - 1} />
                ))}
                <div className="mt-3 bg-slate-50 rounded-lg border border-slate-200 p-3 space-y-2 shadow-sm">
                  <div className="text-[8px] text-slate-800 uppercase tracking-wider font-black">Pipeline Stats</div>
                  {[
                    { label: 'Total Time', value: '1m 58s', color: '#0369a1' }, // cyan-700
                    { label: 'AI Inference', value: '34s', color: '#6d28d9' }, // violet-700
                    { label: 'Model F1 Score', value: '0.912', color: '#047857' }, // emerald-700
                    { label: 'Segments Found', value: '3', color: '#c2410c' }, // orange-700
                  ].map(stat => (
                    <div key={stat.label} className="flex justify-between items-center">
                      <span className="text-[9px] font-bold text-slate-700">{stat.label}</span>
                      <span className="text-[10px] font-black font-mono" style={{ color: stat.color }}>{stat.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === 'metadata' && (
              <div className="space-y-3">
                <div className="text-[9px] text-slate-800 uppercase tracking-wider font-bold flex items-center gap-1.5"><Satellite className="w-3 h-3 text-cyan-600" />Satellite Metadata</div>
                <div className="bg-slate-50 rounded-lg border border-slate-200 shadow-sm p-3 flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#FF671F] via-white to-[#06752B] p-0.5 flex-shrink-0">
                    <div className="w-full h-full rounded-full bg-white flex items-center justify-center">
                      <Satellite className="w-5 h-5 text-cyan-600" />
                    </div>
                  </div>
                  <div>
                    <div className="text-[12px] font-black text-slate-900">Sentinel-1A</div>
                    <div className="text-[9px] font-bold text-slate-700">ESA Copernicus - C-Band SAR</div>
                    <div className="text-[8px] text-emerald-700 font-black flex items-center gap-1 mt-0.5"><span className="w-1.5 h-1.5 rounded-full bg-emerald-600 animate-pulse" />ACTIVE ORBIT</div>
                  </div>
                </div>
                <div className="space-y-0">
                  {satMetadata.map((m) => (
                    <div key={m.label} className="flex justify-between items-center py-1.5 border-b border-slate-200 last:border-0">
                      <span className="text-[9px] font-bold text-slate-700 uppercase tracking-wider">{m.label}</span>
                      <span className="text-[10px] font-black text-cyan-700 font-mono">{m.value}</span>
                    </div>
                  ))}
                </div>
                <div className="bg-slate-50 rounded-lg border border-slate-200 p-3 space-y-2 shadow-sm">
                  <div className="text-[8px] text-slate-800 uppercase tracking-wider font-black mb-2">Data Quality</div>
                  {[
                    { label: 'Radiometric Cal.', pct: 98 },
                    { label: 'Geometric Acc.', pct: 96 },
                    { label: 'Noise Floor', pct: 91 },
                  ].map(q => (
                    <div key={q.label}>
                      <div className="flex justify-between mb-0.5">
                        <span className="text-[8px] font-bold text-slate-700">{q.label}</span>
                        <span className="text-[8px] font-black text-emerald-700">{q.pct}%</span>
                      </div>
                      <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
                        <div className="h-full rounded-full bg-gradient-to-r from-emerald-600 to-emerald-400" style={{ width: `${q.pct}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="flex-shrink-0 border-t border-slate-200 px-3 py-2 flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-[8px] font-bold text-slate-600"><Cpu className="w-2.5 h-2.5" /><span>AI Engine v2.4.1</span></div>
            <div className="flex items-center gap-1.5 text-[8px] font-bold text-slate-600"><RefreshCw className="w-2.5 h-2.5" /><span>Last sync: 06:47 UTC</span></div>
          </div>
        </div>
      </div>

      {/* Status Bar */}
      <div className="flex-shrink-0 bg-white border-t border-slate-200 px-5 py-1.5 flex items-center gap-6 text-[8px]">
        <div className="flex items-center gap-1.5 text-emerald-700 font-black"><span className="w-1.5 h-1.5 rounded-full bg-emerald-600 animate-pulse" /><span>SYSTEM OPERATIONAL</span></div>
        <div className="text-slate-400 hidden sm:block font-bold">|</div>
        <div className="text-slate-700 hidden sm:block font-mono font-bold">CASE: {currentData?.activeCase || currentData?.title || 'SLK-A58D'}</div>
        <div className="text-slate-400 hidden sm:block font-bold">|</div>
        <div className="text-slate-700 hidden sm:block font-bold">DETECTION ENGINE: U-NET v3.1 - TRAINED ON SAR-OIL-INDIA-2024</div>
        <div className="text-slate-400 hidden sm:block font-bold">|</div>
        <div className="text-slate-700 hidden sm:block font-bold">COORDINATE SYSTEM: WGS84 - EPSG:4326</div>
        <div className="ml-auto flex items-center gap-1.5 text-slate-700 font-bold"><Info className="w-3 h-3" /><span>NEERAKSH SAR-AI MODULE - ISRO/ICG JOINT PLATFORM</span></div>
      </div>
    </div>
  );
};
