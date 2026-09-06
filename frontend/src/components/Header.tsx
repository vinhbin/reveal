import React from 'react';
import { Eye, Film, Sparkles, Accessibility } from 'lucide-react';

interface HeaderProps {
  currentView: 'upload' | 'workspace';
  title?: string;
  isAccessibleView: boolean;
  onToggleAccessibleView: () => void;
  onNewReview: () => void;
  onLoadSample: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  currentView,
  title,
  isAccessibleView,
  onToggleAccessibleView,
  onNewReview,
  onLoadSample,
}) => {
  return (
    <header className="header" role="banner">
      <div className="brand" onClick={onNewReview} style={{ cursor: 'pointer' }}>
        <div className="brand-icon">
          <Eye className="w-5 h-5 text-white" />
        </div>
        <div>
          <span className="brand-title">REVEAL</span>
          <span className="brand-subtitle" style={{ marginLeft: '10px' }}>
            AD Reviewer
          </span>
        </div>
      </div>

      {currentView === 'workspace' && title && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)' }}>
          <Film className="w-4 h-4 text-indigo-400" />
          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{title}</span>
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        {currentView === 'upload' && (
          <button className="btn btn-secondary" onClick={onLoadSample}>
            <Sparkles className="w-4 h-4 text-amber-400" />
            Try Demo Sample
          </button>
        )}

        {currentView === 'workspace' && (
          <button className="btn btn-secondary" onClick={onNewReview}>
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
