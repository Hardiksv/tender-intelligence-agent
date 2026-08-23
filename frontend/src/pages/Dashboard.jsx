import React, { useState, useEffect } from 'react';
import { fetchTenders } from '../api/client';
import DeadlineCountdown from '../components/DeadlineCountdown';
import { Search, Filter, CheckCircle2, XCircle, AlertTriangle, ArrowRight, ShieldCheck } from 'lucide-react';

export default function Dashboard({ onSelectTender }) {
  const [tenders, setTenders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedVerdict, setSelectedVerdict] = useState('');
  const [selectedState, setSelectedState] = useState('');

  const loadData = async () => {
    try {
      setLoading(true);
      const data = await fetchTenders({
        search: searchQuery,
        verdict: selectedVerdict,
        state: selectedState
      });
      console.log("SCREENING RAW:", data.tenders?.[0]?.screening);
      console.log("SCREENING TYPE:", typeof data.tenders?.[0]?.screening);
      console.log("VERDICT RAW:", data.tenders?.[0]?.screening?.verdict);
      console.log("VERDICT TYPE:", typeof data.tenders?.[0]?.screening?.verdict);
      setTenders(data.tenders || []);
    } catch (err) {
      console.error("Failed to load tenders:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [searchQuery, selectedVerdict, selectedState]);

const total = tenders.length;

const goCount = tenders.filter(
  t => t.screening?.verdict === 'GO'
).length;

const noGoCount = tenders.filter(
  t => t.screening?.verdict === 'NO-GO'
).length;

const reviewCount = tenders.filter(
  t => t.screening?.verdict === 'REVIEW'
).length;

const expiredCount = tenders.filter(
  t => t.is_expired === true
).length;


  return (
    <div className="space-y-6">
      
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        
        <div className="glass-card p-5 rounded-2xl border border-slate-800">
          <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Total Tenders</p>
          <div className="flex items-baseline justify-between mt-2">
            <span className="text-3xl font-extrabold text-white font-heading">{total}</span>
            <span className="text-xs text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded">All Tenders</span>
          </div>
        </div>

        <div className="glass-card p-5 rounded-2xl border border-emerald-500/20 bg-emerald-950/10">
          <p className="text-xs font-medium text-emerald-400 uppercase tracking-wider">GO Verdicts</p>
          <div className="flex items-baseline justify-between mt-2">
            <span className="text-3xl font-extrabold text-emerald-400 font-heading">{goCount}</span>
            <CheckCircle2 className="w-5 h-5 text-emerald-400" />
          </div>
        </div>

        <div className="glass-card p-5 rounded-2xl border border-rose-500/20 bg-rose-950/10">
          <p className="text-xs font-medium text-rose-400 uppercase tracking-wider">NO-GO Verdicts</p>
          <div className="flex items-baseline justify-between mt-2">
            <span className="text-3xl font-extrabold text-rose-400 font-heading">{noGoCount}</span>
            <XCircle className="w-5 h-5 text-rose-400" />
          </div>
        </div>

        <div className="glass-card p-5 rounded-2xl border border-amber-500/20 bg-amber-950/10">
          <p className="text-xs font-medium text-amber-400 uppercase tracking-wider">REVIEW Verdicts</p>
          <div className="flex items-baseline justify-between mt-2">
            <span className="text-3xl font-extrabold text-amber-400 font-heading">{reviewCount}</span>
            <AlertTriangle className="w-5 h-5 text-amber-400" />
          </div>
        </div>

      </div>

            <div className="glass-card p-4 rounded-2xl flex flex-col md:flex-row items-center justify-between gap-4 border border-slate-800">
        
        <div className="relative w-full md:w-96">
          <Search className="w-4 h-4 absolute left-3.5 top-3 text-slate-400" />
          <input
            type="text"
            placeholder="Search tender title or issuing authority..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-10 pr-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto">
          
          <select
            value={selectedVerdict}
            onChange={(e) => setSelectedVerdict(e.target.value)}
            className="bg-slate-900 border border-slate-800 text-slate-300 text-xs rounded-xl px-3 py-2 focus:outline-none focus:border-indigo-500"
          >
            <option value="">All Verdicts</option>
            <option value="GO">GO Only</option>
            <option value="NO-GO">NO-GO Only</option>
            <option value="REVIEW">REVIEW Only</option>
          </select>

          <select
            value={selectedState}
            onChange={(e) => setSelectedState(e.target.value)}
            className="bg-slate-900 border border-slate-800 text-slate-300 text-xs rounded-xl px-3 py-2 focus:outline-none focus:border-indigo-500"
          >
            <option value="">All States</option>
            <option value="Rajasthan">Rajasthan</option>
            <option value="Haryana">Haryana</option>
            <option value="Gujarat">Gujarat</option>
            <option value="Uttar Pradesh">Uttar Pradesh</option>
            <option value="Maharashtra">Maharashtra</option>
            <option value="Karnataka">Karnataka</option>
          </select>

        </div>

      </div>

            {loading ? (
        <div className="text-center py-16 text-slate-400">
          <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
          <p className="text-sm">Loading bus operations tenders...</p>
        </div>
      ) : tenders.length === 0 ? (
        <div className="text-center py-16 glass-card rounded-2xl border border-slate-800">
          <ShieldCheck className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <h3 className="text-lg font-semibold text-slate-300">No tenders found</h3>
          <p className="text-xs text-slate-500 mt-1">Try running the seed ingestion or clearing filters.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {tenders.map((t) => {
            const isExpired = t.is_expired === true;
            const verdict = t.screening?.verdict || 'PENDING';
            const displayStatus = isExpired ? 'EXPIRED' : verdict;

            const verdictColor =
              isExpired
                ? 'bg-slate-500/10 text-slate-400 border-slate-500/30'
                : verdict === 'GO'
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                : verdict === 'NO-GO'
                ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                : 'bg-amber-500/10 text-amber-400 border-amber-500/30';

            return (
              <div
                key={t.id}
                onClick={() => onSelectTender(t.id)}
                className="glass-card glass-card-hover p-5 rounded-2xl cursor-pointer border border-slate-800/80 flex flex-col md:flex-row items-start md:items-center justify-between gap-4"
              >
                <div className="space-y-1.5 max-w-2xl">
                  <div className="flex items-center gap-2">
                    <span className={`px-2.5 py-0.5 text-xs font-bold rounded-full border ${verdictColor}`}>
                      {displayStatus}
                    </span>
                    <span className="text-xs text-slate-400">
                      {t.city ? `${t.city}, ` : ''}{t.state}
                    </span>
                  </div>

                  <h3 className="text-base font-semibold text-slate-100 font-heading line-clamp-1 hover:text-indigo-400 transition-colors">
                    {t.title}
                  </h3>

                  <p className="text-xs text-slate-400">
                    <span className="font-medium text-slate-300">Authority:</span> {t.issuing_authority}
                  </p>
                </div>

                <div className="flex items-center gap-6 self-end md:self-auto">
                  <div className="text-right">
                    <p className="text-xs text-slate-400">EMD Deposit</p>
                    <p className="text-sm font-semibold text-slate-200">
                      {t.emd_amount ? `₹${(t.emd_amount / 1e5).toFixed(1)} Lakhs` : 'N/A'}
                    </p>
                  </div>

                  <div>
                    <DeadlineCountdown deadlineIso={t.submission_deadline} />
                  </div>

                  <div className="p-2 rounded-xl bg-slate-800/60 text-slate-300 hover:text-indigo-400">
                    <ArrowRight className="w-5 h-5" />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

    </div>
  );
}
