import React from 'react';
import { Layers, ChevronDown } from 'lucide-react';

interface LayerControlProps {
  showLayers: boolean;
  setShowLayers: (val: boolean) => void;
  layers: { spill: boolean; drift: boolean; ais: boolean; satTile: string };
  setLayers: (val: any) => void;
}

export const LayerControl: React.FC<LayerControlProps> = ({ showLayers, setShowLayers, layers, setLayers }) => {
  return (
    <div className="absolute top-4 left-4 z-10 bg-white border border-gov-border rounded-gov p-3 shadow-md w-64 text-xs space-y-2 pointer-events-auto">
      <div className="flex items-center justify-between border-b border-gov-border pb-1.5 font-bold text-navy-800">
        <span className="flex items-center gap-1.5">
          <Layers className="w-4 h-4" />
          INTEGRATED MAP LAYERS
        </span>
        <button 
          onClick={() => setShowLayers(!showLayers)}
          className="text-gov-muted hover:text-navy-800"
        >
          <ChevronDown className={`w-4 h-4 transform transition-transform ${showLayers ? '' : 'rotate-180'}`} />
        </button>
      </div>

      {showLayers && (
        <div className="space-y-2 pt-1 animate-in slide-in-from-top-2">
          <label className="flex items-center space-x-2 cursor-pointer text-gov-text font-medium">
            <input 
              type="checkbox" 
              checked={layers.spill}
              onChange={(e) => setLayers({ ...layers, spill: e.target.checked })}
              className="rounded text-navy-800 focus:ring-navy-800"
            />
            <span>Feature 1: SAR Slick Detection</span>
          </label>
          <label className="flex items-center space-x-2 cursor-pointer text-gov-text font-medium">
            <input 
              type="checkbox" 
              checked={layers.drift}
              onChange={(e) => setLayers({ ...layers, drift: e.target.checked })}
              className="rounded text-navy-800 focus:ring-navy-800"
            />
            <span>Feature 2: Origin &amp; 48h Trajectory</span>
          </label>
          <label className="flex items-center space-x-2 cursor-pointer text-gov-text font-medium">
            <input 
              type="checkbox" 
              checked={layers.ais}
              onChange={(e) => setLayers({ ...layers, ais: e.target.checked })}
              className="rounded text-navy-800 focus:ring-navy-800"
            />
            <span>AIS Vessel Attribution</span>
          </label>
        </div>
      )}
    </div>
  );
};
