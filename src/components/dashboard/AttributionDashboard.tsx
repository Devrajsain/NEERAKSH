import React, { useState } from 'react';
import { FinalAttributionReport, executeAttributionPipelineDemo, executeAttributionPipeline } from '../../services/api';
import { AlertTriangle, Database, Info, Loader2, Navigation, Ship, CheckCircle, XCircle, Map as MapIcon, Lock, RefreshCw } from 'lucide-react';

interface AttributionDashboardProps {
  spillId: string;
  isDemoMode?: boolean;
  existingReport?: FinalAttributionReport | null;
}

export const AttributionDashboard: React.FC<AttributionDashboardProps> = ({ spillId, isDemoMode = false, existingReport = null }) => {
  const [report, setReport] = useState<FinalAttributionReport | null>(existingReport);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  React.useEffect(() => {
    if (existingReport) {
      setReport(existingReport);
    } else {
      setReport(null);
    }
  }, [existingReport, spillId]);

  const handleRunPipeline = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const requestPayload = {
        spill_id: spillId,
        observation_timestamp: new Date().toISOString(),
        observation_geometry: { type: "Polygon", coordinates: [] },
        include_feature3: true
      };

      let result: FinalAttributionReport;
      if (isDemoMode) {
        result = await executeAttributionPipelineDemo(requestPayload);
      } else {
        result = await executeAttributionPipeline(spillId);
      }
      setReport(result);
    } catch (err: any) {
      setError(err.message || 'Failed to execute attribution pipeline.');
    } finally {
      setIsLoading(false);
    }
  };

  if (!report && !isLoading && !error) {
    return (
      <div className="flex-1 min-h-full flex items-center justify-center p-4 sm:p-8 my-auto">
        <div className="max-w-lg w-full bg-white rounded-2xl shadow-xl border border-slate-200/80 p-8 sm:p-10 text-center flex flex-col items-center animate-in zoom-in-95 duration-200">
          <div className="w-16 h-16 rounded-2xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 mb-5 shadow-inner">
            <Database className="h-8 w-8" />
          </div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight mb-2">
            Bayesian Attribution Pipeline
          </h2>
          <p className="text-xs sm:text-sm text-slate-500 leading-relaxed max-w-md mb-5">
            Execute the end-to-end AIS trajectory attribution pipeline (Phases 1–6 + Feature 3 Supplemental Evidence) to correlate candidate vessel tracks with hindcast drift physics.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-2 mb-6 text-[11px] font-medium text-slate-600">
            <span className="bg-slate-100 px-3 py-1 rounded-md border border-slate-200 font-mono text-slate-700">
              Case: {spillId}
            </span>
            <span className="bg-blue-50 text-blue-700 px-3 py-1 rounded-md border border-blue-200/70">
              Phases 1–6 Bayesian Engine
            </span>
            {isDemoMode && (
              <span className="bg-amber-50 text-amber-700 px-3 py-1 rounded-md border border-amber-200">
                Demo / Synthetic Mode
              </span>
            )}
          </div>

          <button 
            onClick={handleRunPipeline}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2.5 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 active:scale-[0.98] text-white font-semibold text-xs shadow-md shadow-blue-500/25 transition-all duration-200 cursor-pointer"
          >
            <Ship className="h-4 w-4" />
            <span>Run Attribution Pipeline</span>
          </button>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex-1 min-h-full flex items-center justify-center p-4 sm:p-8 my-auto">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-xl border border-slate-200/80 p-8 sm:p-10 text-center flex flex-col items-center animate-in zoom-in-95 duration-200">
          <div className="relative w-16 h-16 rounded-2xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 mb-5">
            <Loader2 className="h-8 w-8 animate-spin" />
            <span className="absolute inset-0 rounded-2xl border-2 border-blue-400/40 animate-ping pointer-events-none" />
          </div>
          <h2 className="text-lg font-bold text-slate-900 mb-1.5">Executing Attribution Pipeline...</h2>
          <p className="text-xs text-slate-500 leading-relaxed max-w-xs">
            Evaluating candidate trajectories, running hindcast dispersion physics, and computing posterior probabilities.
          </p>
          <div className="mt-5 w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
            <div className="bg-blue-600 h-full w-2/3 animate-pulse rounded-full" />
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 min-h-full flex items-center justify-center p-4 sm:p-8 my-auto">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-xl border border-red-200/80 p-8 text-center flex flex-col items-center animate-in zoom-in-95 duration-200">
          <div className="w-14 h-14 rounded-2xl bg-red-50 border border-red-100 flex items-center justify-center text-red-600 mb-4">
            <AlertTriangle className="h-7 w-7" />
          </div>
          <h2 className="text-base font-bold text-red-800 mb-1">Pipeline Execution Failed</h2>
          <p className="text-xs text-red-600 mb-5 leading-relaxed max-w-xs">{error}</p>
          <button 
            onClick={handleRunPipeline}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-red-600 hover:bg-red-700 text-white font-semibold text-xs shadow-md transition-all cursor-pointer"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span>Retry Pipeline</span>
          </button>
        </div>
      </div>
    );
  }

  if (!report) return null;

  return (
    <div className="w-full max-w-4xl mx-auto p-4 sm:p-6 md:p-8 space-y-6">
      {/* Demo Banner */}
      {isDemoMode && (
        <div className="bg-amber-50 border border-amber-200/90 text-amber-800 p-4 rounded-xl shadow-xs flex items-center justify-between">
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-5 w-5 text-amber-600 flex-shrink-0" />
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-amber-900">Demo / Synthetic Fixture Mode</p>
              <p className="text-xs text-amber-700 mt-0.5">This analysis is running on deterministic synthetic test fixtures and should not be used as live legal testimony.</p>
            </div>
          </div>
        </div>
      )}

      {/* Header Summary */}
      <div className="bg-white p-5 sm:p-6 rounded-xl shadow-xs border border-slate-200/90">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 mb-5 border-b border-slate-100 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600">
              <Database className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Final Attribution Intelligence Report
              </h2>
              <p className="text-[11px] text-slate-500">Bayesian Posterior Distribution & Physicochemical Risk Ranking</p>
            </div>
          </div>
          <button 
            onClick={handleRunPipeline}
            disabled={isLoading}
            className="bg-slate-100 hover:bg-slate-200 active:bg-slate-300 text-slate-700 font-semibold py-1.5 px-3.5 rounded-lg text-xs shadow-xs flex items-center gap-1.5 disabled:opacity-50 transition-colors cursor-pointer"
          >
            {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            <span>Re-run Pipeline</span>
          </button>
        </div>
        
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-slate-50/80 p-3 rounded-lg border border-slate-100">
            <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Evaluation Status</p>
            <p className={`text-sm font-bold mt-0.5 flex items-center gap-1 ${report.status === 'SUCCESS' ? 'text-emerald-600' : 'text-red-600'}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${report.status === 'SUCCESS' ? 'bg-emerald-500' : 'bg-red-500'}`} />
              {report.status}
            </p>
          </div>
          <div className="bg-slate-50/80 p-3 rounded-lg border border-slate-100">
            <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Spill Incident</p>
            <p className="text-sm font-bold text-slate-800 font-mono mt-0.5">{report.spill_id}</p>
          </div>
          <div className="bg-slate-50/80 p-3 rounded-lg border border-slate-100">
            <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Evaluated AIS Candidates</p>
            <p className="text-sm font-bold text-slate-800 mt-0.5">{report.evaluated_candidate_count} <span className="text-xs text-slate-400 font-normal">/ {report.total_valid_candidates} valid</span></p>
          </div>
          <div className="bg-slate-50/80 p-3 rounded-lg border border-slate-100">
            <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Prior Mode</p>
            <p className="text-xs font-semibold text-slate-700 truncate mt-1" title={report.prior_mode}>{report.prior_mode}</p>
          </div>
        </div>

        {report.hypothesis_space_truncated && (
          <div className="bg-blue-50/80 text-blue-900 p-3 rounded-lg border border-blue-200/60 flex items-start gap-2.5 text-xs mt-3.5">
            <Info className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
            <p><strong>Hypothesis Space Truncated:</strong> The posterior distribution is conditional on the {report.returned_candidate_count} returned candidates, not the entire physical hypothesis space ({report.total_valid_candidates} total valid).</p>
          </div>
        )}
      </div>

      {/* Candidate List */}
      <div className="bg-white rounded-xl shadow-xs border border-slate-200/90 overflow-hidden">
        <div className="px-5 py-3.5 border-b border-slate-100 bg-slate-50/80 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Ship className="h-4 w-4 text-slate-600" />
            <h3 className="text-sm font-bold text-slate-900">Candidate Vessel Hypotheses</h3>
          </div>
          <span className="text-[11px] font-semibold text-slate-500 bg-white px-2.5 py-0.5 rounded-full border border-slate-200">
            {report.candidates.length} Ranked
          </span>
        </div>
        
        {report.candidates.length === 0 ? (
          <div className="p-8 text-center text-slate-400 text-xs">
            No valid candidate hypotheses found.
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {report.candidates.map((candidate) => (
              <div key={candidate.candidate_id} className={`p-5 transition-colors ${candidate.evaluation_status !== 'SUCCESS' ? 'bg-slate-50/50' : 'bg-white hover:bg-slate-50/30'}`}>
                
                {/* Header: MMSI & Identifiers */}
                <div className="flex flex-col md:flex-row justify-between items-start mb-4 gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="text-lg font-bold text-gray-900">MMSI: {candidate.mmsi}</h4>
                      {candidate.evaluation_status === 'SUCCESS' ? (
                        <span className="bg-green-100 text-green-800 text-xs px-2 py-0.5 rounded font-medium flex items-center gap-1">
                          <CheckCircle className="h-3 w-3" /> EVALUATED
                        </span>
                      ) : (
                        <span className="bg-gray-200 text-gray-700 text-xs px-2 py-0.5 rounded font-medium flex items-center gap-1">
                          <XCircle className="h-3 w-3" /> {candidate.evaluation_status}
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-gray-500 mt-1 flex items-center gap-4">
                      <span className="flex items-center gap-1"><Navigation className="h-3 w-3" /> {candidate.release_latitude.toFixed(4)}, {candidate.release_longitude.toFixed(4)}</span>
                      <span className="flex items-center gap-1"><MapIcon className="h-3 w-3" /> {new Date(candidate.release_timestamp).toLocaleString()}</span>
                    </div>
                    <div className="text-xs text-gray-400 mt-1 font-mono">ID: {candidate.candidate_id}</div>
                  </div>
                  
                  {/* Phase 5 Posterior Visualization */}
                  <div className="w-full md:w-64 flex-shrink-0">
                    <div className="text-sm text-gray-600 mb-1 flex justify-between">
                      <span>Bayesian Posterior:</span>
                      <span className="font-bold text-gray-900">{(candidate.posterior_probability * 100).toFixed(1)}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-3">
                      <div 
                        className="bg-blue-600 h-3 rounded-full" 
                        style={{ width: `${candidate.posterior_probability * 100}%` }}
                      ></div>
                    </div>
                    <div className="flex justify-between text-xs text-gray-400 mt-1">
                      <span>Prior: {(candidate.prior_probability * 100).toFixed(1)}%</span>
                      <span>L: {candidate.likelihood.toExponential(2)}</span>
                    </div>
                  </div>
                </div>

                {/* Grid for Phase 6 and Feature 3 */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4 pt-4 border-t border-gray-100">
                  
                  {/* Phase 6: Confidence & Diagnostics */}
                  <div className="bg-gray-50 p-4 rounded border border-gray-200">
                    <h5 className="text-sm font-bold text-gray-700 mb-2 flex items-center gap-1 uppercase">
                      <Lock className="h-4 w-4" /> Phase 6: Physics Confidence
                    </h5>
                    {candidate.confidence_diagnostics.length === 0 ? (
                      <p className="text-sm text-gray-500 italic">No diagnostics available.</p>
                    ) : (
                      <ul className="space-y-2 text-sm">
                        {candidate.confidence_diagnostics.map((diag: any, idx: number) => (
                          <li key={idx} className="flex items-start gap-2">
                            <span className={`flex-shrink-0 mt-0.5 h-2 w-2 rounded-full ${
                              diag.status === 'MEASURED' ? 'bg-green-500' :
                              diag.status === 'UNAVAILABLE' ? 'bg-amber-500' :
                              'bg-gray-400'
                            }`} />
                            <span className="text-gray-700">
                              <span className="font-medium">{diag.metric_name}:</span>{' '}
                              {diag.status === 'MEASURED' ? (
                                <span>{diag.value !== null ? diag.value : 'N/A'} {diag.unit}</span>
                              ) : (
                                <span className="text-gray-500">N/A</span>
                              )}
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                    {candidate.confidence_flags.length > 0 && (
                      <div className="mt-3">
                        <p className="text-xs font-semibold text-gray-500 mb-1">WARNING FLAGS:</p>
                        <div className="flex flex-wrap gap-1">
                          {candidate.confidence_flags.map((flag, idx) => (
                            <span key={idx} className={`text-xs px-2 py-1 rounded bg-amber-100 text-amber-800`}>
                              {flag.flag}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Feature 3: Supplemental Evidence */}
                  <div className="bg-indigo-50 p-4 rounded border border-indigo-100">
                    <h5 className="text-sm font-bold text-indigo-900 mb-2 uppercase">
                      Feature 3: Supplemental Deterministic Evidence
                    </h5>
                    {candidate.supplemental_deterministic_evidence ? (
                      <div>
                        <div className="flex justify-between items-center mb-2">
                          <span className="text-sm text-indigo-800">Overall Score:</span>
                          <span className="font-bold text-indigo-900 text-lg">
                            {candidate.supplemental_deterministic_evidence.feature3_overall_score ?? 'N/A'}
                          </span>
                        </div>
                        <div className="flex justify-between items-center mb-3">
                          <span className="text-sm text-indigo-800">Risk Class:</span>
                          <span className="text-xs font-bold px-2 py-1 bg-indigo-200 text-indigo-800 rounded">
                            {candidate.supplemental_deterministic_evidence.risk_class ?? 'UNAVAILABLE'}
                          </span>
                        </div>
                        <div className="text-xs text-indigo-700 mt-2 border-t border-indigo-200 pt-2">
                          <strong>Metrics: </strong> 
                          {JSON.stringify(candidate.supplemental_deterministic_evidence.metrics)}
                        </div>
                      </div>
                    ) : (
                      <p className="text-sm text-indigo-500 italic">No supplemental evidence available.</p>
                    )}
                  </div>

                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Limitations and Provenance */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white p-5 rounded-lg shadow-sm border border-gray-200">
          <h3 className="text-md font-bold text-gray-800 mb-3 border-b pb-2">Limitations & Warnings</h3>
          <ul className="list-disc pl-5 text-sm text-gray-700 space-y-1">
            {report.limitations.map((lim, i) => <li key={`lim-${i}`}>{lim}</li>)}
            {report.warnings.map((warn, i) => <li key={`warn-${i}`} className="text-amber-600">{warn}</li>)}
            {report.errors.map((err, i) => <li key={`err-${i}`} className="text-red-600">{err}</li>)}
            {report.limitations.length === 0 && report.warnings.length === 0 && report.errors.length === 0 && (
              <li className="text-gray-400 italic list-none -ml-5">No active limitations.</li>
            )}
          </ul>
        </div>

        <div className="bg-white p-5 rounded-lg shadow-sm border border-gray-200">
          <h3 className="text-md font-bold text-gray-800 mb-3 border-b pb-2">Data Provenance</h3>
          <div className="text-sm text-gray-700 space-y-2">
            <p><strong>Environment Provider:</strong> {report.provenance.environmental_data_provider || 'Unknown'}</p>
            <p><strong>Simulation Engine:</strong> {report.provenance.simulation_engine || 'Unknown'}</p>
            <div>
              <strong>Bayesian Config:</strong>
              <pre className="mt-1 text-xs bg-gray-50 p-2 rounded border">{JSON.stringify(report.provenance.bayesian_configuration, null, 2)}</pre>
            </div>
          </div>
        </div>
      </div>

    </div>
  );
};
