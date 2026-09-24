import React from 'react';
import { Upload, Trash2 } from 'lucide-react';
import { CaseResponse } from '../../services/api';

interface TopNavbarProps {
  onNavigate: (view: 'home' | 'dashboard' | 'workflow') => void;
  activeModule: string;
  setActiveModule: (mod: string) => void;
  onOpenUpload: () => void;
  availableCases: CaseResponse[];
  activeCase: string;
  setActiveCase: (id: string) => void;
  handleDeleteCase: (id: string) => void;
  showAttributionDashboard?: boolean;
  setShowAttributionDashboard?: (val: boolean) => void;
}

const NAV_ITEMS = ['Dashboard', 'Incidents', 'SAR Satellite', 'Drift', 'Forensic Analytics'];

export const TopNavbar: React.FC<TopNavbarProps> = ({
  onNavigate, activeModule, setActiveModule, onOpenUpload, availableCases, activeCase, setActiveCase, handleDeleteCase,
  showAttributionDashboard = false, setShowAttributionDashboard,
}) => {
  return (
    <header className="map-top-navbar sticky top-0 z-50 h-11 px-4 flex items-center justify-between">
      {/* LEFT — Brand */}
      <div className="flex items-center gap-3 flex-shrink-0">
        <button onClick={() => onNavigate('home')} className="flex items-center gap-2 hover:opacity-80 transition-opacity">
          <img src="/neeraksh_logo.jpg" alt="NEERAKSH" className="w-7 h-7 rounded-full object-cover border border-slate-200 shadow-sm" />
          <span className="text-[13px] font-black tracking-wider text-navy-800">NEERAKSH</span>
        </button>
      </div>

      {/* CENTER — Nav Links */}
      <nav className="hidden md:flex items-center gap-1 absolute left-1/2 -translate-x-1/2">
        {NAV_ITEMS.map(item => {
          const modKey = item.toLowerCase().split(' ')[0]; // dashboard, incidents, sar, drift, forensic, reports
          const isActive = activeModule === modKey;
          return (
            <button
              key={item}
              className={`px-2.5 py-1 text-[10.5px] font-semibold uppercase tracking-wider rounded transition-colors whitespace-nowrap ${
                isActive
                  ? 'text-navy-800 bg-blue-50 border border-blue-200'
                  : 'text-gov-muted hover:text-navy-800 hover:bg-slate-50'
              }`}
              onClick={() => setActiveModule(modKey)}
            >
              {item}
            </button>
          );
        })}
      </nav>

      {/* RIGHT — Controls */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <button onClick={onOpenUpload} className="flex items-center gap-1 px-2.5 py-1 bg-navy-800 hover:bg-navy-700 text-white text-[10px] font-bold uppercase tracking-wider rounded transition-colors">
          <Upload className="w-3 h-3" />
          <span className="hidden sm:inline">Upload</span>
        </button>

        {setShowAttributionDashboard && (
          <button
            onClick={() => setShowAttributionDashboard(!showAttributionDashboard)}
            className={`px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider rounded border transition-colors ${
              showAttributionDashboard ? 'bg-blue-600 border-blue-500 text-white shadow-xs' : 'bg-white border-gov-border text-gov-muted hover:text-navy-800 hover:bg-slate-50'
            }`}
            title="Open Attribution Dossier Window"
          >
            Attribution
          </button>
        )}
      </div>
    </header>
  );
};
