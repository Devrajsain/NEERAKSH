import React from 'react';
import { Search, Trash2 } from 'lucide-react';
import { CaseResponse } from '../../services/api';

interface TopNavbarProps {
  onNavigate: (view: 'home' | 'dashboard' | 'workflow') => void;
  onOpenUpload: () => void;
  availableCases: CaseResponse[];
  activeCase: string;
  setActiveCase: (id: string) => void;
  handleDeleteCase: (id: string) => void;
  showAttributionDashboard?: boolean;
  setShowAttributionDashboard?: (val: boolean) => void;
}

export const TopNavbar: React.FC<TopNavbarProps> = ({
  onNavigate,
  onOpenUpload,
  availableCases,
  activeCase,
  setActiveCase,
  handleDeleteCase,
  showAttributionDashboard = false,
  setShowAttributionDashboard
}) => {
  return (
    <header className="bg-white border-b border-gov-border px-4 py-2.5 flex items-center justify-between shadow-xs sticky top-0 z-40">
      <div className="flex items-center space-x-4">
        <button 
          onClick={() => onNavigate('home')}
          className="flex items-center space-x-2 text-navy-800 font-bold text-lg hover:opacity-80 transition-opacity"
        >
          <img 
            src="/neeraksh_logo.jpg" 
            alt="NEERAKSH Logo" 
            className="w-9 h-9 rounded-full object-cover shadow-sm border border-slate-200"
          />
          <span className="text-[15px] font-black tracking-wide text-navy-900">NEERAKSH</span>
        </button>

        <span className="text-gov-border">|</span>

        <div className="hidden md:flex items-center space-x-2 text-xs text-gov-muted">
          <span className="font-semibold text-navy-800">NATIONAL MARITIME GRID</span>
          <span>•</span>
          <span className="text-emerald-700 font-medium flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-emerald-600 animate-pulse"></span>
            {availableCases.length} Active Incident{availableCases.length !== 1 ? 's' : ''}
          </span>
        </div>
      </div>

      <div className="flex items-center space-x-3">
        <div className="relative w-64 sm:w-80">
          <Search className="w-4 h-4 text-gov-muted absolute left-3 top-1/2 -translate-y-1/2" />
          <input 
            type="text" 
            placeholder="Search by spill ID, vessel name, or MMSI..." 
            className="w-full pl-9 pr-3 py-1.5 text-xs bg-white border border-gov-border rounded-gov text-gov-text placeholder-gov-muted focus:outline-none focus:border-navy-800 focus:ring-1 focus:ring-navy-800"
          />
        </div>

        <select 
          value={activeCase}
          onChange={(e) => setActiveCase(e.target.value)}
          className="px-3 py-1.5 text-xs bg-white border border-gov-border rounded-gov font-bold text-navy-800 focus:outline-none focus:border-navy-800"
        >
          {availableCases.length > 0 ? (
            availableCases.map(c => (
              <option key={c.id} value={c.id}>{c.id} ({c.location_name})</option>
            ))
          ) : (
            <option value={activeCase}>{activeCase}</option>
          )}
        </select>

        <button
          onClick={() => handleDeleteCase(activeCase)}
          title={`Delete incident ${activeCase}`}
          className="p-1.5 text-red-600 hover:text-red-800 hover:bg-red-50 border border-red-200 rounded-gov transition-colors"
        >
          <Trash2 className="w-4 h-4" />
        </button>

        <button 
          onClick={onOpenUpload}
          className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 bg-navy-800 hover:bg-navy-900 text-white text-xs font-semibold uppercase tracking-wider rounded-gov shadow-xs transition-colors"
        >
          <span>+ Upload Case</span>
        </button>

        {setShowAttributionDashboard && (
          <button 
            onClick={() => setShowAttributionDashboard(!showAttributionDashboard)}
            className={`hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold uppercase tracking-wider rounded-gov shadow-xs transition-colors ${showAttributionDashboard ? 'bg-blue-600 text-white hover:bg-blue-700' : 'bg-gray-100 text-gray-700 hover:bg-gray-200 border border-gray-300'}`}
          >
            <span>{showAttributionDashboard ? 'Show Map' : 'Bayesian Dashboard'}</span>
          </button>
        )}
      </div>
    </header>
  );
};
