import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { TrendingUp, TrendingDown, Clock, Loader, AlertTriangle } from 'lucide-react';

function StockProfile() {
  const { ticker } = useParams();
  const [quote, setQuote] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [news, setNews] = useState([]);
  const [activeTab, setActiveTab] = useState('overview');
  
  const [loadingQuote, setLoadingQuote] = useState(true);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchQuote();
    fetchNews();
  }, [ticker]);

  const fetchQuote = async () => {
    try {
      setLoadingQuote(true);
      const res = await axios.get(`/api/v1/quote/${ticker}`);
      setQuote(res.data);
    } catch (err) {
      setError('Could not fetch real-time quote.');
    } finally {
      setLoadingQuote(false);
    }
  };

  const fetchNews = async () => {
    try {
      const res = await axios.get(`/api/v1/news/${ticker}`);
      if (res.data && res.data.articles) {
        setNews(res.data.articles);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchAnalysis = async () => {
    if (analysis) return; // already fetched
    try {
      setLoadingAnalysis(true);
      const res = await axios.post('/api/v1/analyze', { ticker });
      setAnalysis(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingAnalysis(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'analysis') {
      fetchAnalysis();
    }
  }, [activeTab]);

  return (
    <div className="container">
      {/* Header Profile Card */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div className="card-body" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
              <div style={{ width: '48px', height: '48px', backgroundColor: 'var(--bg-white)', border: '1px solid var(--border-color)', color: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '12px', fontSize: '20px', fontWeight: 'bold', boxShadow: '0 0 15px rgba(0, 240, 255, 0.2)' }}>
                {ticker[0]}
              </div>
              <div>
                <h1 style={{ fontSize: '24px', margin: 0 }}>{quote?.company_name || ticker}</h1>
                <span style={{ color: 'var(--text-secondary)', fontWeight: '500' }}>{ticker}</span>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)', fontSize: '14px' }}>
              <Clock size={16} /> Market Data
            </div>
          </div>

          {loadingQuote ? (
            <Loader className="animate-spin" size={24} color="var(--primary)" />
          ) : quote ? (
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '32px', fontWeight: 'bold', textShadow: '0 0 10px rgba(255, 255, 255, 0.2)' }}>${quote.current_price?.toFixed(2)}</div>
              <div style={{ 
                color: quote.change_percent >= 0 ? '#39ff14' : '#ff3366',
                textShadow: quote.change_percent >= 0 ? '0 0 10px rgba(57, 255, 20, 0.4)' : '0 0 10px rgba(255, 51, 102, 0.4)',
                display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '4px',
                fontWeight: '600'
              }}>
                {quote.change_percent >= 0 ? <TrendingUp size={20} /> : <TrendingDown size={20} />}
                {quote.change_percent >= 0 ? '+' : ''}{quote.change_percent?.toFixed(2)}%
              </div>
            </div>
          ) : (
            <div style={{ color: '#d93025' }}><AlertTriangle /></div>
          )}
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', borderTop: '1px solid var(--border-color)', padding: '0 24px' }}>
          {['overview', 'analysis', 'news'].map(tab => (
            <button 
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                background: 'none',
                border: 'none',
                padding: '16px 24px',
                fontSize: '16px',
                fontWeight: '600',
                cursor: 'pointer',
                color: activeTab === tab ? 'var(--primary)' : 'var(--text-secondary)',
                borderBottom: activeTab === tab ? '3px solid var(--primary)' : '3px solid transparent',
                textShadow: activeTab === tab ? '0 0 10px rgba(0, 240, 255, 0.4)' : 'none',
                textTransform: 'capitalize'
              }}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <div className="card">
          <div className="card-body">
            <h3>About {quote?.company_name || ticker}</h3>
            <p style={{ marginTop: '16px', color: 'var(--text-secondary)' }}>
              Select the <strong>Analysis</strong> tab to generate an in-depth AI investment report for this company.
            </p>
          </div>
        </div>
      )}

      {activeTab === 'analysis' && (
        <div className="card">
          <div className="card-body">
            {loadingAnalysis ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '40px' }}>
                <Loader className="animate-spin" size={48} color="var(--primary)" style={{ marginBottom: '16px' }} />
                <h3>Generating AI Analysis...</h3>
                <p style={{ color: 'var(--text-secondary)' }}>This may take 30-60 seconds as AIRA reviews documents and recent data.</p>
              </div>
            ) : analysis ? (
              <div>
                <div style={{ display: 'flex', gap: '16px', marginBottom: '24px' }}>
                  <span className="badge-primary">
                    Recommendation: {analysis.recommendation}
                  </span>
                  <span className="badge-secondary">
                    Confidence: {analysis.confidence_score}/100
                  </span>
                </div>
                <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>
                  {analysis.summary}
                </div>
              </div>
            ) : (
              <div>No analysis available yet.</div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'news' && (
        <div className="grid-2">
          {news.length > 0 ? news.map((item, idx) => (
            <a href={item.url} target="_blank" rel="noopener noreferrer" key={idx} className="card">
              <div className="card-body">
                <div style={{ color: 'var(--text-secondary)', fontSize: '12px', marginBottom: '8px' }}>
                  {item.source || 'Market News'} • {item.published_at ? new Date(item.published_at).toLocaleDateString() : ''}
                </div>
                <h3 style={{ fontSize: '16px', marginBottom: '8px', lineHeight: 1.4 }}>{item.title}</h3>
                <p style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
                  {item.summary}
                </p>
              </div>
            </a>
          )) : (
            <div className="card" style={{ gridColumn: 'span 2' }}>
              <div className="card-body">No recent news found for {ticker}.</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default StockProfile;
