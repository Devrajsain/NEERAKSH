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
      <div className="flex flex-col items-center justify-center p-12 bg-white shadow rounded-lg border border-gray-200">
        <Database className="h-16 w-16 text-blue-500 mb-4" />
        <h2 className="text-2xl font-semibold text-gray-800 mb-2">Bayesian Attribution Pipeline</h2>
        <p className="text-gray-600 mb-6 text-center max-w-lg">
          Execute the end-to-end attribution pipeline (Phases 1-6 + Feature 3). 
          {isDemoMode && <span className="block mt-2 font-bold text-amber-600">Note: Currently running in DEMO / SYNTHETIC DATA mode.</span>}
        </p>
        <button 
          onClick={handleRunPipeline}
          className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-md shadow flex items-center gap-2"
        >
          <Ship className="h-5 w-5" />
          Run Attribution Pipeline
        </button>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 bg-white shadow rounded-lg border border-gray-200 min-h-[400px]">
        <Loader2 className="h-12 w-12 text-blue-600 animate-spin mb-4" />
        <h2 className="text-xl font-medium text-gray-800">Executing Pipeline...</h2>
        <p className="text-gray-500 mt-2">This may take a moment.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 bg-red-50 shadow rounded-lg border border-red-200">
        <div className="flex items-start gap-4">
          <AlertTriangle className="h-8 w-8 text-red-600 flex-shrink-0" />
          <div>
            <h2 className="text-lg font-semibold text-red-800">Pipeline Execution Failed</h2>
            <p className="text-red-700 mt-1">{error}</p>
            <button 
              onClick={handleRunPipeline}
              className="mt-4 bg-red-600 hover:bg-red-700 text-white font-medium py-1.5 px-4 rounded shadow text-sm"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!report) return null;

  return (
    <div className="space-y-6">
      {/* Demo Banner */}
      {isDemoMode && (
        <div className="bg-amber-100 border-l-4 border-amber-500 text-amber-800 p-4 rounded shadow-sm flex items-center justify-between">
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-6 w-6" />
            <div>
              <p className="font-bold">DEMO / SYNTHETIC DATA</p>
              <p className="text-sm">This is a deterministic frontend fixture and must not be interpreted as real scientific data.</p>
            </div>
          </div>
        </div>
      )}

      {/* Header Summary */}
      <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <div className="flex justify-between items-center mb-4 border-b pb-2">
          <h2 className="text-xl font-bold text-gray-800 flex items-center gap-2">
            <Database className="h-5 w-5 text-blue-600" />
            Final Attribution Report
          </h2>
          <button 
            onClick={handleRunPipeline}
            disabled={isLoading}
            className="bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium py-1 px-3 rounded text-sm shadow-sm flex items-center gap-1 disabled:opacity-50"
          >
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Re-run Bayesian Attribution
          </button>
        </div>
        
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          <div className="bg-gray-50 p-3 rounded border border-gray-100">
            <p className="text-xs text-gray-500 font-medium uppercase">Status</p>
            <p className={`font-semibold ${report.status === 'SUCCESS' ? 'text-green-600' : 'text-red-600'}`}>
              {report.status}
            </p>
          </div>
          <div className="bg-gray-50 p-3 rounded border border-gray-100">
            <p className="text-xs text-gray-500 font-medium uppercase">Spill ID</p>
            <p className="font-semibold text-gray-800">{report.spill_id}</p>
          </div>
          <div className="bg-gray-50 p-3 rounded border border-gray-100">
            <p className="text-xs text-gray-500 font-medium uppercase">Evaluated Candidates</p>
            <p className="font-semibold text-gray-800">{report.evaluated_candidate_count} / {report.total_valid_candidates}</p>
          </div>
          <div className="bg-gray-50 p-3 rounded border border-gray-100">
            <p className="text-xs text-gray-500 font-medium uppercase">Prior Mode</p>
            <p className="font-semibold text-gray-800 text-sm truncate" title={report.prior_mode}>{report.prior_mode}</p>
          </div>
        </div>

        {report.hypothesis_space_truncated && (
          <div className="bg-blue-50 text-blue-800 p-3 rounded border border-blue-100 flex items-start gap-2 text-sm mt-2">
            <Info className="h-4 w-4 mt-0.5 flex-shrink-0" />
            <p><strong>Hypothesis Space Truncated:</strong> The posterior distribution is conditional on the {report.returned_candidate_count} returned candidates, not the entire physical hypothesis space ({report.total_valid_candidates} total valid).</p>
          </div>
        )}
      </div>

      {/* Candidate List */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <div className="p-4 border-b bg-gray-50 flex items-center gap-2">
          <Ship className="h-5 w-5 text-gray-600" />
          <h3 className="text-lg font-bold text-gray-800">Candidate Hypotheses</h3>
        </div>
        
        {report.candidates.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            No valid candidate hypotheses found.
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {report.candidates.map((candidate) => (
              <div key={candidate.candidate_id} className={`p-5 ${candidate.evaluation_status !== 'SUCCESS' ? 'bg-gray-50' : 'bg-white'}`}>
                
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
