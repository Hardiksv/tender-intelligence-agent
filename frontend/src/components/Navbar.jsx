import React, { useState } from 'react';
import { Bus, LayoutDashboard, UserCheck, MessageSquare, RefreshCw, CheckCircle, AlertTriangle } from 'lucide-react';
import { triggerIngestion, fetchIngestionStatus } from '../api/client';

export default function Navbar({ activeTab, setActiveTab, onIngestionCompleted }) {
  const [ingesting, setIngesting] = useState(false);
  const [jobProgress, setJobProgress] = useState(null);

  const handleStartIngestion = async () => {
    try {
      setIngesting(true);
      const res = await triggerIngestion();
      const jobId = res.job_id;

      const interval = setInterval(async () => {
        try {
          const statusRes = await fetchIngestionStatus(jobId);
          setJobProgress(statusRes);

          if (statusRes.status === 'COMPLETED' || statusRes.status === 'FAILED') {
            clearInterval(interval);
            setIngesting(false);
            if (onIngestionCompleted) onIngestionCompleted();
          }
        } catch (e) {
          clearInterval(interval);
          setIngesting(false);
        }
      }, 2000);

    } catch (err) {
      setIngesting(false);
      if (err.response && err.response.status === 409) {
        alert("Ingestion pipeline is already running in the background.");
      } else {
        alert("Failed to start ingestion pipeline: " + (err.response?.data?.detail || err.message));
      }
    }
  };

  return (
    <header className="sticky top-0 z-50 bg-slate-950/80 backdrop-blur-xl border-b border-slate-800/80 px-6 py-4">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        
                <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Bus className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white tracking-wide font-heading">
              Tender Intelligence <span className="text-indigo-400 font-light">Agent</span>
            </h1>
            <p className="text-xs text-slate-400">Bus Operations Procurement Platform</p>
          </div>
        </div>

                <nav className="flex items-center gap-1 bg-slate-900/90 p-1.5 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveTab('dashboard')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'dashboard'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <LayoutDashboard className="w-4 h-4" />
            <span>Dashboard</span>
          </button>

          <button
            onClick={() => setActiveTab('profile')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'profile'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <UserCheck className="w-4 h-4" />
            <span>Company Profile</span>
          </button>

          <button
            onClick={() => setActiveTab('chat')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'chat'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <MessageSquare className="w-4 h-4" />
            <span>Grounded RAG Chat</span>
          </button>
        </nav>

                <div className="flex items-center gap-3">
          {jobProgress && ingesting && (
            <div className="text-xs text-indigo-300 bg-indigo-950/60 border border-indigo-800/60 px-3 py-1.5 rounded-lg flex items-center gap-2">
              <RefreshCw className="w-3.5 h-3.5 animate-spin text-indigo-400" />
              <span>Ingesting: {jobProgress.completed_documents} / {jobProgress.total_documents || '10'}</span>
            </div>
          )}

          <button
            onClick={handleStartIngestion}
            disabled={ingesting}
            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow-md shadow-emerald-900/20 transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${ingesting ? 'animate-spin' : ''}`} />
            <span>{ingesting ? 'Ingesting Data...' : 'Run Seed Ingestion'}</span>
          </button>
        </div>

      </div>
    </header>
  );
}
