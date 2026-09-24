import React, { useState } from 'react';
import { Search, Filter, Plus, FileText, Activity, Archive, CheckCircle, Clock, MoreVertical, Map as MapIcon, RefreshCw, UploadCloud, ChevronLeft, ChevronRight, AlertTriangle } from 'lucide-react';
import { CurrentDashboardData } from './types';
import { CaseResponse } from '../../services/api';

interface IncidentsModuleProps {
  activeCase: string;
  setActiveCase: (id: string) => void;
  availableCases: CaseResponse[];
  currentData: CurrentDashboardData | null;
  onOpenUpload: () => void;
  setActiveModule: (mod: string) => void;
}

// Mock extra cases to flesh out the table (since api returns few)
const MOCK_CASES = [
  { id: 'SLK-A58D', location: 'Arabian Sea, Gujarat Coast', detected: '22 Sep 2026', area: '284 km²', status: 'Active', stage: 'Forensic Analysis', vessels: 12, confidence: 92, lastUpdated: '22 Sep 2026 17:32' },
  { id: 'SLK-B21F', location: 'Gulf of Khambhat', detected: '21 Sep 2026', area: '45 km²', status: 'Under Investigation', stage: 'AIS Attribution', vessels: 34, confidence: 85, lastUpdated: '21 Sep 2026 09:14' },
  { id: 'SLK-C92A', location: 'Mumbai High North', detected: '19 Sep 2026', area: '12 km²', status: 'Processing', stage: 'SAR Detection', vessels: 0, confidence: 45, lastUpdated: '19 Sep 2026 11:05' },
  { id: 'SLK-D14E', location: 'Lakshadweep Sea', detected: '15 Sep 2026', area: '156 km²', status: 'Resolved', stage: 'Report Ready', vessels: 3, confidence: 98, lastUpdated: '16 Sep 2026 14:22' },
  { id: 'SLK-E88X', location: 'Bay of Bengal, East Coast', detected: '10 Sep 2026', area: '89 km²', status: 'Archived', stage: 'Report Ready', vessels: 1, confidence: 88, lastUpdated: '12 Sep 2026 08:45' },
  { id: 'SLK-F33Y', location: 'Andaman Sea', detected: '05 Sep 2026', area: '1.2 km²', status: 'Resolved', stage: 'Report Ready', vessels: 0, confidence: 72, lastUpdated: '06 Sep 2026 19:10' },
  { id: 'SLK-G99Z', location: 'Kochi Port Approach', detected: '01 Sep 2026', area: '5.5 km²', status: 'Archived', stage: 'Report Ready', vessels: 2, confidence: 95, lastUpdated: '02 Sep 2026 10:30' },
];

export const IncidentsModule: React.FC<IncidentsModuleProps> = ({
  activeCase, setActiveCase, availableCases, currentData, onOpenUpload, setActiveModule
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('All');
  const [selectedRow, setSelectedRow] = useState<string | null>(activeCase || null);

  const stats = {
    total: MOCK_CASES.length,
    active: MOCK_CASES.filter(c => c.status === 'Active').length,
    analysis: MOCK_CASES.filter(c => c.status === 'Under Investigation' || c.status === 'Processing').length,
    resolved: MOCK_CASES.filter(c => c.status === 'Resolved' || c.status === 'Archived').length,
  };

  const filteredCases = MOCK_CASES.filter(c => {
    const matchesSearch = c.id.toLowerCase().includes(searchTerm.toLowerCase()) || c.location.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = filterStatus === 'All' || c.status === filterStatus || 
      (filterStatus === 'Under Analysis' && (c.status === 'Under Investigation' || c.status === 'Processing'));
    return matchesSearch && matchesStatus;
  });

  const handleOpenCase = (id: string) => {
    setActiveCase(id);
    setActiveModule('dashboard');
  };

  const getStatusBadge = (status: string) => {
    switch(status) {
      case 'Active': return <span className="px-2 py-0.5 rounded bg-red-100 text-red-800 border border-red-200 flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />{status}</span>;
      case 'Under Investigation': return <span className="px-2 py-0.5 rounded bg-orange-100 text-orange-800 border border-orange-200">{status}</span>;
      case 'Processing': return <span className="px-2 py-0.5 rounded bg-blue-100 text-blue-800 border border-blue-200 flex items-center gap-1"><RefreshCw className="w-2.5 h-2.5 animate-spin"/>{status}</span>;
      case 'Resolved': return <span className="px-2 py-0.5 rounded bg-green-100 text-green-800 border border-green-200 flex items-center gap-1"><CheckCircle className="w-2.5 h-2.5"/>{status}</span>;
      default: return <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200 flex items-center gap-1"><Archive className="w-2.5 h-2.5"/>{status}</span>;
    }
  };

  const selectedCaseData = MOCK_CASES.find(c => c.id === selectedRow);

  return (
    <div className="h-full w-full flex flex-col bg-slate-50 overflow-hidden">
      
      {/* Header & Metrics */}
      <div className="bg-white border-b border-slate-200 px-6 py-4 flex-shrink-0">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h1 className="text-xl font-black text-navy-800">MARITIME INCIDENTS</h1>
            <p className="text-xs text-slate-500 mt-0.5">Central case registry and workflow management</p>
          </div>
          <button onClick={onOpenUpload} className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded text-xs font-bold uppercase tracking-wider flex items-center gap-2 transition-colors">
            <Plus className="w-4 h-4" /> Upload New Case
          </button>
        </div>

        <div className="grid grid-cols-4 gap-4">
          {[
            { label: 'TOTAL CASES', val: stats.total, color: 'text-navy-800', filter: 'All' },
            { label: 'ACTIVE INCIDENTS', val: stats.active, color: 'text-red-600', filter: 'Active' },
            { label: 'UNDER ANALYSIS', val: stats.analysis, color: 'text-blue-600', filter: 'Under Analysis' },
            { label: 'RESOLVED', val: stats.resolved, color: 'text-green-600', filter: 'Resolved' },
          ].map((s, i) => (
            <div key={i} onClick={() => setFilterStatus(s.filter)} className={`bg-white border ${filterStatus === s.filter ? 'border-blue-400 shadow-md ring-1 ring-blue-400' : 'border-slate-200 shadow-sm hover:border-slate-300'} rounded-lg p-3 cursor-pointer transition-all`}>
              <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-1">{s.label}</div>
              <div className={`text-2xl font-black ${s.color}`}>{s.val}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* Left: Case List */}
        <div className={`flex flex-col border-r border-slate-200 transition-all duration-300 ${selectedRow ? 'w-2/3' : 'w-full'}`}>
          {/* Search/Filter Bar */}
          <div className="bg-white px-4 py-2 border-b border-slate-200 flex items-center gap-3 text-xs flex-shrink-0">
            <div className="flex items-center gap-2 bg-slate-100 border border-slate-200 rounded px-3 py-1.5 flex-1 max-w-md">
              <Search className="w-3.5 h-3.5 text-slate-400" />
              <input 
                type="text" placeholder="Search by Spill ID, Location..." 
                className="bg-transparent border-none outline-none w-full text-navy-800 placeholder-slate-400"
                value={searchTerm} onChange={e => setSearchTerm(e.target.value)}
              />
            </div>
            
            <div className="flex items-center gap-2 ml-auto">
              <Filter className="w-3.5 h-3.5 text-slate-400" />
              <select className="bg-white border border-slate-200 rounded px-2 py-1.5 outline-none text-navy-800 font-medium" value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
                <option value="All">All Status</option>
                <option value="Active">Active</option>
                <option value="Under Investigation">Under Investigation</option>
                <option value="Processing">Processing</option>
                <option value="Resolved">Resolved</option>
                <option value="Archived">Archived</option>
              </select>
              <select className="bg-white border border-slate-200 rounded px-2 py-1.5 outline-none text-navy-800 font-medium">
                <option>All Stages</option>
                <option>SAR Detection</option>
                <option>Drift Analysis</option>
                <option>AIS Attribution</option>
                <option>Forensic Analysis</option>
                <option>Report Ready</option>
              </select>
              <button onClick={() => {setSearchTerm(''); setFilterStatus('All');}} className="text-slate-500 hover:text-slate-700 font-semibold px-2">Clear Filters</button>
            </div>
          </div>

          {/* Table */}
          <div className="flex-1 overflow-y-auto bg-white">
            <table className="w-full text-left border-collapse">
              <thead className="bg-slate-50 sticky top-0 z-10">
                <tr>
                  <th className="py-2.5 px-4 text-[10px] font-black uppercase tracking-wider text-slate-500 border-b border-slate-200">Case ID</th>
                  <th className="py-2.5 px-4 text-[10px] font-black uppercase tracking-wider text-slate-500 border-b border-slate-200">Location</th>
                  <th className="py-2.5 px-4 text-[10px] font-black uppercase tracking-wider text-slate-500 border-b border-slate-200">Detected</th>
                  <th className="py-2.5 px-4 text-[10px] font-black uppercase tracking-wider text-slate-500 border-b border-slate-200">Status</th>
                  <th className="py-2.5 px-4 text-[10px] font-black uppercase tracking-wider text-slate-500 border-b border-slate-200 hidden lg:table-cell">Stage</th>
                  <th className="py-2.5 px-4 text-[10px] font-black uppercase tracking-wider text-slate-500 border-b border-slate-200 text-center">Conf.</th>
                  <th className="py-2.5 px-4 text-[10px] font-black uppercase tracking-wider text-slate-500 border-b border-slate-200 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="text-xs">
                {filteredCases.map(c => (
                  <tr 
                    key={c.id} 
                    onClick={() => setSelectedRow(c.id === selectedRow ? null : c.id)}
                    className={`border-b border-slate-100 hover:bg-blue-50 cursor-pointer transition-colors ${selectedRow === c.id ? 'bg-blue-50' : ''}`}
                  >
                    <td className="py-3 px-4 font-bold text-navy-800">{c.id}</td>
                    <td className="py-3 px-4 text-slate-600">{c.location}</td>
                    <td className="py-3 px-4 text-slate-600 whitespace-nowrap">{c.detected}</td>
                    <td className="py-3 px-4 font-semibold text-[10px] uppercase tracking-wider whitespace-nowrap">{getStatusBadge(c.status)}</td>
                    <td className="py-3 px-4 text-slate-600 hidden lg:table-cell">{c.stage}</td>
                    <td className="py-3 px-4 text-center">
                      <div className="flex items-center gap-1.5 justify-center">
                        <span className="font-bold text-navy-800">{c.confidence}%</span>
                        <div className="w-12 h-1.5 bg-slate-200 rounded-full overflow-hidden hidden xl:block">
                          <div className={`h-full rounded-full ${c.confidence >= 90 ? 'bg-green-500' : c.confidence >= 70 ? 'bg-blue-500' : 'bg-orange-500'}`} style={{width: `${c.confidence}%`}}></div>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button onClick={(e) => { e.stopPropagation(); handleOpenCase(c.id); }} className="px-2.5 py-1 bg-navy-800 hover:bg-navy-700 text-white rounded font-semibold text-[10px] uppercase tracking-wider">Open</button>
                      </div>
                    </td>
                  </tr>
                ))}
                {filteredCases.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-slate-500">
                      <AlertTriangle className="w-8 h-8 mx-auto text-slate-300 mb-3" />
                      <div className="font-bold text-navy-800 text-sm">NO INCIDENTS FOUND</div>
                      <div className="text-xs mt-1">Try changing your filters or create a new maritime incident.</div>
                      <button onClick={onOpenUpload} className="mt-4 px-4 py-2 bg-white border border-slate-300 rounded font-bold text-navy-800 text-xs hover:bg-slate-50">
                        + UPLOAD NEW CASE
                      </button>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          
          {/* Pagination */}
          <div className="bg-white border-t border-slate-200 px-4 py-2.5 flex items-center justify-between text-xs text-slate-500 flex-shrink-0">
            <span>Showing 1–{filteredCases.length} of {stats.total} cases</span>
            <div className="flex gap-1">
              <button className="p-1 border border-slate-200 rounded hover:bg-slate-50" disabled><ChevronLeft className="w-4 h-4" /></button>
              <button className="p-1 border border-slate-200 rounded hover:bg-slate-50" disabled><ChevronRight className="w-4 h-4" /></button>
            </div>
          </div>
        </div>

        {/* Right: Case Detail Preview */}
        {selectedRow && selectedCaseData && (
          <div className="w-1/3 bg-white flex flex-col slide-in-right overflow-y-auto">
            
            {/* Header */}
            <div className="p-5 border-b border-slate-200 bg-slate-50 flex justify-between items-start">
              <div>
                <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">CASE DETAILS</div>
                <h2 className="text-xl font-black text-navy-800">{selectedCaseData.id}</h2>
                <div className="flex items-center gap-2 mt-2">
                  {getStatusBadge(selectedCaseData.status)}
                </div>
              </div>
              <button onClick={() => setSelectedRow(null)} className="text-slate-400 hover:text-slate-600 text-xl font-bold">&times;</button>
            </div>

            <div className="p-5 space-y-6">
              
              {/* Info Grid */}
              <div className="grid grid-cols-2 gap-4">
                <div><div className="text-[10px] text-slate-500 font-bold uppercase mb-1">Location</div><div className="text-xs font-semibold text-navy-800">{selectedCaseData.location}</div></div>
                <div><div className="text-[10px] text-slate-500 font-bold uppercase mb-1">Detected</div><div className="text-xs font-semibold text-navy-800">{selectedCaseData.detected}</div></div>
                <div><div className="text-[10px] text-slate-500 font-bold uppercase mb-1">Spill Area</div><div className="text-xs font-semibold text-navy-800">{selectedCaseData.area}</div></div>
                <div><div className="text-[10px] text-slate-500 font-bold uppercase mb-1">Confidence</div><div className="text-xs font-semibold text-navy-800">{selectedCaseData.confidence}%</div></div>
              </div>

              {/* Progress Bar */}
              <div>
                <div className="text-[10px] text-slate-500 font-bold uppercase mb-2">Processing Stage</div>
                <div className="bg-slate-100 rounded-lg p-3">
                  <div className="flex justify-between relative mb-2">
                    <div className="absolute top-1.5 left-2 right-2 h-0.5 bg-slate-200 -z-10"></div>
                    {['UPLOAD', 'SAR', 'DRIFT', 'AIS', 'FORENSIC', 'REPORT'].map((stage, i) => {
                      const stages = ['Uploaded', 'SAR Detection', 'Drift Analysis', 'AIS Attribution', 'Forensic Analysis', 'Report Ready'];
                      const currIdx = stages.indexOf(selectedCaseData.stage);
                      const isComplete = i <= currIdx;
                      const isCurrent = i === currIdx;
                      return (
                        <div key={stage} className="flex flex-col items-center">
                          <div className={`w-3 h-3 rounded-full mb-1 border-2 ${isComplete ? 'bg-blue-600 border-blue-600' : 'bg-white border-slate-300'} ${isCurrent ? 'ring-4 ring-blue-100' : ''}`} />
                          <div className={`text-[8px] font-bold ${isCurrent ? 'text-blue-700' : isComplete ? 'text-navy-800' : 'text-slate-400'}`}>{stage}</div>
                        </div>
                      )
                    })}
                  </div>
                  <div className="text-[11px] font-semibold text-blue-800 text-center mt-3 bg-blue-50 py-1.5 rounded">
                    Current: {selectedCaseData.stage}
                  </div>
                </div>
              </div>

              {/* Mini Map Placeholder */}
              <div>
                <div className="text-[10px] text-slate-500 font-bold uppercase mb-2">Case Preview</div>
                <div className="h-40 bg-slate-200 rounded-lg overflow-hidden relative border border-slate-300">
                  <img src="/neeraksh_logo.jpg" alt="Map Preview" className="w-full h-full object-cover opacity-20 filter blur-sm grayscale" />
                  <div className="absolute inset-0 flex items-center justify-center flex-col">
                    <MapIcon className="w-8 h-8 text-slate-500 mb-2" />
                    <span className="text-xs font-bold text-slate-600">Map Preview Available in Dashboard</span>
                  </div>
                </div>
              </div>

              {/* Data Sources */}
              <div className="space-y-2">
                <div className="text-[10px] text-slate-500 font-bold uppercase mb-2">Data Sources</div>
                <div className="flex justify-between text-xs py-1.5 border-b border-slate-100"><span className="text-slate-500">Satellite Source</span><span className="font-semibold text-navy-800">Sentinel-1 (SAR)</span></div>
                <div className="flex justify-between text-xs py-1.5 border-b border-slate-100"><span className="text-slate-500">AIS Availability</span><span className="font-semibold text-navy-800">{selectedCaseData.vessels > 0 ? `${selectedCaseData.vessels} Candidates` : 'None'}</span></div>
                <div className="flex justify-between text-xs py-1.5"><span className="text-slate-500">Weather/Ocean</span><span className="font-semibold text-navy-800">Copernicus Marine</span></div>
              </div>
              
              {/* Actions */}
              <div className="pt-4 border-t border-slate-200 flex flex-col gap-2">
                <button onClick={() => handleOpenCase(selectedCaseData.id)} className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded font-bold text-[11px] uppercase tracking-wider flex items-center justify-center gap-2 transition-colors">
                  <Activity className="w-4 h-4" /> Open Full Dashboard
                </button>
                <div className="grid grid-cols-2 gap-2">
                  <button onClick={() => {setActiveCase(selectedCaseData.id); setActiveModule('forensic');}} className="py-2 bg-white border border-slate-300 hover:border-blue-400 rounded font-bold text-[10px] text-navy-800 uppercase tracking-wider transition-colors">
                    Forensics
                  </button>
                  <button onClick={() => {setActiveCase(selectedCaseData.id); setActiveModule('drift');}} className="py-2 bg-white border border-slate-300 hover:border-blue-400 rounded font-bold text-[10px] text-navy-800 uppercase tracking-wider transition-colors">
                    Drift Physics
                  </button>
                </div>
              </div>

            </div>
          </div>
        )}

      </div>
    </div>
  );
};
