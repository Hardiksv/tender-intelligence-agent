import React, { useState, useEffect } from 'react';
import { fetchTenderById, rescreenTender } from '../api/client';
import DeadlineCountdown from '../components/DeadlineCountdown';
import { ArrowLeft, CheckCircle2, XCircle, AlertTriangle, ShieldCheck, FileText, MapPin, Building, Calendar, DollarSign, ExternalLink, RefreshCw } from 'lucide-react';

export default function TenderDetail({ tenderId, onBack }) {
  const [tender, setTender] = useState(null);
  const [loading, setLoading] = useState(true);
  const [screening, setScreening] = useState(null);
  const [rescreening, setRescreening] = useState(false);

const loadTender = async () => {
  try {
    setLoading(true);
    setScreening(null);

    const data = await fetchTenderById(tenderId);

    console.log("TENDER DETAIL API:", data);
    console.log("TENDER DETAIL SCREENING:", data.screening);

    setTender(data);
    setScreening(data.screening ?? null);
  } catch (err) {
    console.error("Failed to load tender details:", err);
    setTender(null);
    setScreening(null);
  } finally {
    setLoading(false);
  }
};

  useEffect(() => {
    if (tenderId) loadTender();
  }, [tenderId]);

  const handleRescreen = async () => {
    try {
      setRescreening(true);
      const res = await rescreenTender(tenderId);
      setScreening(res);
    } catch (err) {
      alert("Failed to re-screen tender: " + err.message);
    } finally {
      setRescreening(false);
    }
  };

  if (loading || !tender) {
    return (
      <div className="text-center py-20">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
        <p className="text-sm text-slate-400">Loading tender specifications...</p>
      </div>
    );
  }

  const verdict = screening?.verdict || 'PENDING';
  const verdictBadgeColor = 
    verdict === 'GO' ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' :
    verdict === 'NO-GO' ? 'bg-rose-500/20 text-rose-300 border-rose-500/40' :
    'bg-amber-500/20 text-amber-300 border-amber-500/40';

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      
            <button
        onClick={onBack}
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-300 hover:text-white text-xs font-medium transition-all"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Tenders</span>
      </button>

            <div className="glass-card p-6 rounded-2xl border border-slate-800 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className={`px-3 py-1 text-xs font-extrabold rounded-full border ${verdictBadgeColor}`}>
              {verdict} VERDICT
            </span>
            <span className="text-xs text-slate-400 bg-slate-900 border border-slate-800 px-2.5 py-1 rounded-full">
              Category: {tender.category}
            </span>
          </div>

          <DeadlineCountdown deadlineIso={tender.submission_deadline} />
        </div>

        <h1 className="text-2xl font-bold text-white font-heading">{tender.title}</h1>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2 text-xs text-slate-300">
          <div className="flex items-center gap-2">
            <Building className="w-4 h-4 text-indigo-400" />
            <span><strong className="text-slate-400">Authority:</strong> {tender.issuing_authority}</span>
          </div>
          <div className="flex items-center gap-2">
            <MapPin className="w-4 h-4 text-indigo-400" />
            <span><strong className="text-slate-400">Location:</strong> {tender.city ? `${tender.city}, ` : ''}{tender.state}</span>
          </div>
          <div className="flex items-center gap-2">
            <DollarSign className="w-4 h-4 text-indigo-400" />
            <span><strong className="text-slate-400">EMD Deposit:</strong> {tender.emd_amount ? `₹${(tender.emd_amount / 1e5).toFixed(1)} Lakhs` : 'N/A'}</span>
          </div>
        </div>
      </div>

            {screening && (
        <div className="glass-card p-6 rounded-2xl border border-slate-800 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-indigo-400" />
              <h2 className="text-lg font-semibold text-white font-heading">Deterministic Eligibility Screening</h2>
            </div>

            <button
              onClick={handleRescreen}
              disabled={rescreening}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600/20 text-indigo-300 hover:bg-indigo-600/30 text-xs font-medium border border-indigo-500/30 transition-all"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${rescreening ? 'animate-spin' : ''}`} />
              <span>{rescreening ? 'Screening...' : 'Re-screen Profile'}</span>
            </button>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 text-xs text-slate-300">
            <strong className="text-slate-200">Verdict Rationale:</strong> {screening.reasoning}
          </div>

<div className="overflow-x-auto">
  <table className="w-full text-left text-xs border-collapse">
    <thead>
      <tr className="border-b border-slate-800 text-slate-400 bg-slate-900/50">
        <th className="py-2.5 px-3">Criterion</th>
        <th className="py-2.5 px-3">Status</th>
        <th className="py-2.5 px-3">Details</th>
      </tr>
    </thead>

    <tbody className="divide-y divide-slate-800/60">
        {(screening.criteria_results || []).map((c, idx) => {
          const criterionName = c.criterion || c.criterion_name;
          const statusVal = c.status || (c.verdict === 'PASS' ? 'MET' : c.verdict);
          const detailsVal = c.details || c.reason;

          const statusColor =
            statusVal === 'MET' || statusVal === 'PASS'
              ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30'
              : statusVal === 'FAIL'
              ? 'text-rose-400 bg-rose-500/10 border-rose-500/30'
              : 'text-amber-400 bg-amber-500/10 border-amber-500/30';

          return (
            <tr key={idx} className="hover:bg-slate-900/40">
              <td className="py-3 px-3 font-semibold text-slate-200">
                {criterionName}
              </td>

              <td className="py-3 px-3">
                <span
                  className={`px-2 py-0.5 rounded-full border text-[10px] font-extrabold ${statusColor}`}
                >
                  {statusVal}
                </span>
              </td>

              <td className="py-3 px-3 text-slate-400 leading-relaxed max-w-lg">
                {detailsVal}
              </td>
            </tr>
        );
      })}
    </tbody>
  </table>
</div>

        </div>
      )}

            <div className="glass-card p-6 rounded-2xl border border-slate-800 space-y-3">
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-indigo-400" />
          <h2 className="text-lg font-semibold text-white font-heading">Bus Operations Scope Summary</h2>
        </div>
        <p className="text-xs text-slate-300 leading-relaxed bg-slate-900/60 p-4 rounded-xl border border-slate-800">
          {tender.scope_summary || 'No explicit scope summary extracted.'}
        </p>
      </div>

    </div>
  );
}
