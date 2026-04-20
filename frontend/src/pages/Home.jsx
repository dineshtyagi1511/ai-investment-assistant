import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Newspaper, TrendingUp, AlertCircle } from 'lucide-react';
import axios from 'axios';

function Home() {
  const [ticker, setTicker] = useState('');
  const [news, setNews] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetchNews();
  }, []);

  const fetchNews = async () => {
    try {
      setLoading(true);
      const res = await axios.get('/api/v1/news?limit=6');
      if (res.data && res.data.articles) {
        setNews(res.data.articles);
      }
    } catch (err) {
      console.error('Error fetching news:', err);
      setError('Could not load market news.');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e) => {
    e.preventDefault();
    if (ticker.trim()) {
      navigate(`/stock/${ticker.trim().toUpperCase()}`);
    }
  };

  return (
    <div>
      {/* Hero Section */}
      <section className="hero-section">
        <div className="container">
          <h1 className="hero-title">Find the Right Stock for You</h1>
          <p className="hero-subtitle">Millions of AI-powered insights, analyses, and news articles.</p>
          
          <div className="search-bar-container">
            <form onSubmit={handleSearch} className="search-input-wrapper">
              <Search color="var(--text-secondary)" size={20} style={{ alignSelf: 'center', margin: '0 8px' }} />
              <input 
                type="text" 
                placeholder="Search by Ticker (e.g. AAPL, TSLA, NVDA)" 
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
              />
              <button type="submit" className="btn btn-primary search-btn">Search</button>
            </form>
          </div>
        </div>
      </section>

      {/* Main Content */}
      <section className="container" style={{ marginTop: '40px' }}>
        <h2 style={{ marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Newspaper /> Market News
        </h2>

        {error && (
          <div className="error-box">
            <AlertCircle size={20} />
            {error}
          </div>
        )}

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px' }}>Loading news...</div>
        ) : (
          <div className="grid-3">
            {news.map((item, idx) => (
              <a href={item.url} target="_blank" rel="noopener noreferrer" key={idx} className="card">
                <div className="card-body">
                  <div style={{ color: 'var(--text-secondary)', fontSize: '12px', marginBottom: '8px' }}>
                    {item.source || 'Market News'} • {item.published_at ? new Date(item.published_at).toLocaleDateString() : ''}
                  </div>
                  <h3 style={{ fontSize: '16px', marginBottom: '8px', lineHeight: 1.4 }}>{item.title}</h3>
                  <p style={{ fontSize: '14px', color: 'var(--text-secondary)', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                    {item.summary}
                  </p>
                </div>
              </a>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export default Home;
