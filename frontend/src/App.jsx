import React from 'react';
import { Routes, Route, Link, useLocation } from 'react-router-dom';
import { TrendingUp, Scale, Newspaper, Search } from 'lucide-react';
import Home from './pages/Home';
import StockProfile from './pages/StockProfile';
import Compare from './pages/Compare';

function Navbar() {
  const location = useLocation();

  return (
    <nav className="navbar">
      <div className="container">
        <Link to="/" className="nav-brand">
          <TrendingUp size={28} />
          <span>AIRA</span>
        </Link>
        <div className="nav-links">
          <Link to="/" className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}>
            Home
          </Link>
          <Link to="/compare" className={`nav-link ${location.pathname === '/compare' ? 'active' : ''}`}>
            Compare
          </Link>
        </div>
      </div>
    </nav>
  );
}

function App() {
  return (
    <div className="app-container">
      <Navbar />
      <main className="page-container">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/stock/:ticker" element={<StockProfile />} />
          <Route path="/compare" element={<Compare />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
