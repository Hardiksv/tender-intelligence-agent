import React, { useState } from 'react';
import { sendChatQuestion } from '../api/client';
import { MessageSquare, Send, Sparkles, BookOpen, AlertTriangle } from 'lucide-react';

export default function RagChat() {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([
    {
      sender: 'bot',
      answer: 'Hello! I am your Grounded Tender Intelligence Assistant. Ask me any question regarding stored bus operations tenders (e.g., "Which tenders close in the next 15 days?", "What turnover does Jaipur tender require?", "Which tenders are we eligible for?"). All answers are grounded strictly in stored documents with page citations.',
      citations: [],
      model_used: 'system'
    }
  ]);
  const [loading, setLoading] = useState(false);

  const sampleQuestions = [
    "Which tenders close in the next 15 days?",
    "What turnover and fleet size does Jaipur tender require?",
    "What is the EMD deposit for Gurugram tender?",
    "Which tenders are we eligible for based on our company profile?"
  ];

  const handleSend = async (qText) => {
    const query = qText || question;
    if (!query.trim()) return;

    const userMsg = { sender: 'user', text: query };
    setMessages(prev => [...prev, userMsg]);
    if (!qText) setQuestion('');
    setLoading(true);

    try {
      const res = await sendChatQuestion(query);
      const botMsg = {
        sender: 'bot',
        answer: res.answer,
        citations: res.citations || [],
        model_used: res.model_used
      };
      setMessages(prev => [...prev, botMsg]);
    } catch (err) {
      setMessages(prev => [...prev, {
        sender: 'bot',
        answer: 'Failed to process question: ' + (err.response?.data?.detail || err.message),
        citations: [],
        model_used: 'error'
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      
            <div className="glass-card p-6 rounded-2xl border border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
            <Sparkles className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white font-heading">Grounded RAG Tender Q&A</h1>
            <p className="text-xs text-slate-400">Strictly grounded responses backed by page-aware vector citations.</p>
          </div>
        </div>
      </div>

            <div className="flex flex-wrap gap-2">
        {sampleQuestions.map((sq, idx) => (
          <button
            key={idx}
            onClick={() => handleSend(sq)}
            className="px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 hover:border-indigo-500/40 text-xs text-indigo-300 hover:text-white transition-all text-left"
          >
            "{sq}"
          </button>
        ))}
      </div>

            <div className="glass-card p-6 rounded-2xl border border-slate-800 min-h-[420px] max-h-[600px] overflow-y-auto space-y-4">
        {messages.map((m, idx) => (
          <div key={idx} className={`flex ${m.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-2xl rounded-2xl p-4 text-xs leading-relaxed ${
              m.sender === 'user'
                ? 'bg-indigo-600 text-white rounded-br-none'
                : 'bg-slate-900/90 text-slate-200 border border-slate-800 rounded-bl-none space-y-3'
            }`}>
              {m.sender === 'user' ? (
                <p className="font-medium text-sm">{m.text}</p>
              ) : (
                <>
                  <p className="whitespace-pre-wrap">{m.answer}</p>

                                    {m.citations && m.citations.length > 0 && (
                    <div className="pt-3 border-t border-slate-800/80 space-y-2">
                      <div className="flex items-center gap-1.5 text-indigo-400 font-semibold text-[11px]">
                        <BookOpen className="w-3.5 h-3.5" />
                        <span>Source Citations ({m.citations.length})</span>
                      </div>

                      <div className="space-y-1.5">
                        {m.citations.map((c, cIdx) => (
                          <div key={cIdx} className="p-2 rounded-lg bg-slate-950/80 border border-slate-800 text-[11px] space-y-0.5">
                            <p className="font-bold text-slate-200">{c.tender_title}</p>
                            <p className="text-slate-400">Document: <span className="text-indigo-300">{c.document_name}</span> (Page {c.page_number})</p>
                            <p className="text-slate-500 italic font-mono text-[10px]">"{c.snippet}"</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-slate-900 p-4 rounded-2xl border border-slate-800 flex items-center gap-2 text-xs text-indigo-400">
              <div className="w-4 h-4 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
              <span>Retrieving pgvector context & generating grounded answer...</span>
            </div>
          </div>
        )}
      </div>

            <form
        onSubmit={(e) => { e.preventDefault(); handleSend(); }}
        className="glass-card p-2 rounded-2xl border border-slate-800 flex items-center gap-2"
      >
        <input
          type="text"
          placeholder="Ask any question about stored tender documents..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          className="flex-1 bg-transparent px-4 py-2.5 text-sm text-white focus:outline-none placeholder-slate-500"
        />

        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="p-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl transition-all shadow-md shadow-indigo-600/30"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>

    </div>
  );
}
