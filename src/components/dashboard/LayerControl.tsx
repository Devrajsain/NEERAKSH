import React, { useState } from 'react';
import { Layers, ChevronDown, Eye, EyeOff } from 'lucide-react';

interface LayerControlProps {
  showLayers: boolean;
  setShowLayers: (val: boolean) => void;
  layers: { spill: boolean; drift: boolean; ais: boolean; satTile: string };
  setLayers: (val: any) => void;
}

const LAYER_ITEMS = [
  { key: 'spill', label: 'Oil Spill', color: '#DC2626' },
  { key: 'drift', label: 'Origin & Forecast', color: '#2563EB' },
  { key: 'ais', label: 'AIS Vessels', color: '#059669' },
];

export const LayerControl: React.FC<LayerControlProps> = ({ showLayers, setShowLayers, layers, setLayers }) => {
  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-md overflow-hidden w-full pointer-events-auto">
        <div
          className="flex items-center justify-between px-3 py-2 cursor-pointer select-none hover:bg-slate-50 transition-colors"
          onClick={() => setShowLayers(!showLayers)}
        >
          <span className="flex items-center gap-1.5 text-[10px] font-bold text-navy-800 uppercase tracking-wider">
            <Layers className="w-3.5 h-3.5" /> Map Layers
          </span>
          <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${showLayers ? '' : '-rotate-90'}`} />
        </div>

        {showLayers && (
          <div className="border-t border-slate-100 p-2 space-y-1">
            {LAYER_ITEMS.map(item => {
              const isOn = (layers as any)[item.key];
              return (
                <button
                  key={item.key}
                  onClick={() => setLayers({ ...layers, [item.key]: !isOn })}
                  className={`layer-toggle w-full ${isOn ? 'on' : 'off'}`}
                >
                  <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: isOn ? item.color : '#cbd5e1' }} />
                  <span className="flex-1 text-left">{item.label}</span>
                  {isOn ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
                </button>
              );
            })}
          </div>
        )}
      </div>
  );
};
