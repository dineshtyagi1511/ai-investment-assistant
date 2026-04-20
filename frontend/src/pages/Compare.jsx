import React, { useState } from 'react';
import axios from 'axios';
import { Scale, Loader, AlertCircle } from 'lucide-react';

function Compare() {
  const [tickersInput, setTickersInput] = useState('');
  const [queryInput, setQueryInput] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleCompare = async (e) => {
    e.preventDefault();
    setError(null);
    const tickers = tickersInput.split(',').map(t => t.trim().toUpperCase()).filter(t => t);
    
    if (tickers.length < 2) {
      setError('Please enter at least 2 tickers.');
      return;
    }
    if (tickers.length > 4) {
      setError('Maximum 4 tickers allowed for comparison.');
      return;
    }

    try {
      setLoading(true);
      const payload = { tickers };
      if (queryInput.trim()) {
        payload.query = queryInput.trim();
      }
      const res = await axios.post('/api/v1/compare', payload);
      setAnalysis(res.data);
    } catch (err) {
      console.error(err);
      setError('Failed to generate comparison. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container">
      <div className="card" style={{ marginBottom: '24px' }}>
        <div className="card-body">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
            <div style={{ width: '48px', height: '48px', backgroundColor: 'rgba(0, 240, 255, 0.1)', color: 'var(--primary)', border: '1px solid rgba(0, 240, 255, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '12px', boxShadow: '0 0 10px rgba(0, 240, 255, 0.2)' }}>
              <Scale size={24} />
            </div>
            <div>
              <h1 style={{ fontSize: '24px', margin: 0 }}>Compare Stocks</h1>
              <span style={{ color: 'var(--text-secondary)' }}>Multi-Agent Bull vs Bear Debate</span>
            </div>
          </div>

          <form onSubmit={handleCompare}>
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>Enter Tickers (comma separated)</label>
              <input 
                type="text" 
                className="input-control" 
                placeholder="e.g. AAPL, MSFT, GOOGL" 
                value={tickersInput}
                onChange={(e) => setTickersInput(e.target.value)}
              />
            </div>
            <div style={{ marginBottom: '24px' }}>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>Specific Question (Optional)</label>
              <input 
                type="text" 
                className="input-control" 
                placeholder="e.g. Which stock is better for long-term dividend growth?" 
                value={queryInput}
                onChange={(e) => setQueryInput(e.target.value)}
              />
            </div>
            {error && (
              <div className="error-box">
                <AlertCircle size={18} /> {error}
              </div>
            )}
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? <><Loader className="animate-spin" size={18} /> Debating...</> : 'Start Debate'}
            </button>
          </form>
        </div>
      </div>

      {loading && (
        <div className="card">
          <div className="card-body" style={{ textAlign: 'center', padding: '60px' }}>
            <Loader className="animate-spin" size={48} color="var(--primary)" style={{ margin: '0 auto 24px' }} />
            <h3>AI Agents are Debating...</h3>
            <p style={{ color: 'var(--text-secondary)' }}>Gathering data and structuring the bull/bear case. This may take a minute.</p>
          </div>
        </div>
      )}

      {analysis && !loading && (
        <div className="card">
          <div className="card-body">
            <h2 style={{ marginBottom: '24px', textShadow: '0 0 10px rgba(0, 240, 255, 0.3)' }}>Debate Verdict</h2>
            <div style={{ padding: '16px', backgroundColor: 'rgba(0, 240, 255, 0.05)', border: '1px solid var(--border-color)', borderRadius: '12px', marginBottom: '32px', boxShadow: 'inset 0 0 20px rgba(0, 240, 255, 0.05)' }}>
              <h3 style={{ color: 'var(--primary)', marginBottom: '8px', textShadow: '0 0 10px rgba(0, 240, 255, 0.4)' }}>Winner: {analysis.winner}</h3>
              <p style={{ margin: 0, color: 'var(--text-primary)' }}><strong>Confidence:</strong> {analysis.confidence_score}/100</p>
            </div>
            
            <h3>Full Debate Transcript</h3>
            <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.6', marginTop: '16px', backgroundColor: 'var(--bg-light)', padding: '24px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              {analysis.transcript}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Compare;
