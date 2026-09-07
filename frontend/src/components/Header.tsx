import React from 'react';
import { Eye, Film, Sparkles, Accessibility } from 'lucide-react';

interface HeaderProps {
  currentView: 'upload' | 'workspace';
  title?: string;
  isAccessibleView: boolean;
  onToggleAccessibleView: () => void;
  onNewReview: () => void;
  onLoadSample: () => void;
  isBusy: boolean;
  onHome: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  currentView,
  title,
  isAccessibleView,
  onToggleAccessibleView,
  onNewReview,
  onLoadSample,
  isBusy,
  onHome,
}) => {
  return (
    <header className="header" role="banner">
      <button type="button" className="brand" onClick={onHome} disabled={isBusy} aria-label="Reveal home" style={{ cursor: 'pointer', background: 'none', border: 0, font: 'inherit' }}>
        <div className="brand-icon">
          <Eye className="w-5 h-5 text-white" />
        </div>
        <div>
          <span className="brand-title">REVEAL</span>
          <span className="brand-subtitle" style={{ marginLeft: '10px' }}>
            AD Reviewer
          </span>
        </div>
      </button>

      {currentView === 'workspace' && title && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)' }}>
          <Film className="w-4 h-4 text-indigo-400" />
          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{title}</span>
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        {currentView === 'upload' && (
          <button className="btn btn-secondary" onClick={onLoadSample} disabled={isBusy}>
            <Sparkles className="w-4 h-4 text-amber-400" />
            Try Demo Sample
          </button>
        )}

        {currentView === 'workspace' && (
          <button className="btn btn-secondary" onClick={onNewReview} disabled={isBusy}>
            + New Review
          </button>
        )}

        <button
          className={`btn ${isAccessibleView ? 'btn-primary' : 'btn-secondary'}`}
          onClick={onToggleAccessibleView}
          aria-pressed={isAccessibleView}
          title="Toggle High-Contrast Screen Reader Optimized View"
        >
          <Accessibility className="w-4 h-4" />
          {isAccessibleView ? 'Standard View' : 'Accessible Text View'}
        </button>
      </div>
    </header>
  );
};
