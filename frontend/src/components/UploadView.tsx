import React, { useState } from 'react';
import { Upload, FileText, Film, Sparkles, AlertCircle, Clock } from 'lucide-react';
import { ReviewSummary } from '../types';

interface UploadViewProps {
  onUpload: (title: string, videoFile: File, srtFile: File, intentNotes: string) => void;
  onLoadSample: () => void;
  onSelectReview: (reviewId: string) => void;
  recentReviews: ReviewSummary[];
  isSubmitting: boolean;
}

export const UploadView: React.FC<UploadViewProps> = ({
  onUpload,
  onLoadSample,
  onSelectReview,
  recentReviews,
  isSubmitting,
}) => {
  const [title, setTitle] = useState('');
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [srtFile, setSrtFile] = useState<File | null>(null);
  const [intentNotes, setIntentNotes] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError('Please provide a review title.');
      return;
    }
    if (!videoFile) {
      setError('Please select a video file (MP4/WebM).');
      return;
    }
    if (!srtFile) {
      setError('Please select an SRT audio description file.');
      return;
    }
    setError(null);
    onUpload(title.trim(), videoFile, srtFile, intentNotes);
  };

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '32px' }}>
      <div style={{ textAlign: 'center', margin: '20px 0' }}>
        <h1 style={{ fontSize: '2.5rem', fontWeight: 800, letterSpacing: '-0.03em', marginBottom: '12px' }}>
          Detect Premature Identity Disclosures
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '1.1rem', maxWidth: '650px', margin: '0 auto' }}>
          Upload your short film and Audio Description (SRT) script. Reveal checks whether AD cues prematurely name concealed characters before their identity is established in dialogue or visuals.
        </p>
      </div>

      {error && (
        <div
          role="alert"
          style={{
            background: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid #ef4444',
            color: '#fca5a5',
            padding: '14px 20px',
            borderRadius: 'var(--radius-md)',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid-responsive">
        <form onSubmit={handleSubmit} className="card" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div>
            <label htmlFor="review-title-input" style={{ display: 'block', fontWeight: 600, marginBottom: '8px', color: 'var(--text-primary)' }}>
              Film Title / Review Session Name *
            </label>
            <input
              id="review-title-input"
              type="text"
              placeholder="e.g. The Alleyway Encounter — Rough Cut AD"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              style={{
                width: '100%',
                padding: '12px 16px',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--text-primary)',
                fontSize: '0.95rem',
              }}
              required
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            <div>
              <label htmlFor="video-file-input" style={{ display: 'block', fontWeight: 600, marginBottom: '8px' }}>
                Film Video (MP4 / WebM) *
              </label>
              <div
                style={{
                  border: '2px dashed var(--border-strong)',
                  borderRadius: 'var(--radius-md)',
                  padding: '24px 16px',
                  textAlign: 'center',
                  background: 'var(--bg-secondary)',
                  position: 'relative',
                }}
              >
                <input
                  id="video-file-input"
                  type="file"
                  accept="video/mp4,video/webm"
                  aria-label="Upload film video file"
                  onChange={(e) => {
                    if (e.target.files?.[0]) setVideoFile(e.target.files[0]);
                  }}
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: '100%',
                    opacity: 0,
                    cursor: 'pointer',
                  }}
                />
                <Film className="w-8 h-8" style={{ color: 'var(--accent-primary)', margin: '0 auto 8px' }} />
                <p style={{ fontSize: '0.85rem', fontWeight: 600 }}>
                  {videoFile ? videoFile.name : 'Select Video File'}
                </p>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  {videoFile ? `${(videoFile.size / 1024 / 1024).toFixed(1)} MB` : 'MP4 or WebM (up to 200MB)'}
                </p>
              </div>
            </div>

            <div>
              <label htmlFor="srt-file-input" style={{ display: 'block', fontWeight: 600, marginBottom: '8px' }}>
                Audio Description (SRT) *
              </label>
              <div
                style={{
                  border: '2px dashed var(--border-strong)',
                  borderRadius: 'var(--radius-md)',
                  padding: '24px 16px',
                  textAlign: 'center',
                  background: 'var(--bg-secondary)',
                  position: 'relative',
                }}
              >
                <input
                  id="srt-file-input"
                  type="file"
                  accept=".srt"
                  aria-label="Upload SRT Audio Description file"
                  onChange={(e) => {
                    if (e.target.files?.[0]) setSrtFile(e.target.files[0]);
                  }}
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: '100%',
                    opacity: 0,
                    cursor: 'pointer',
                  }}
                />
                <FileText className="w-8 h-8" style={{ color: '#a855f7', margin: '0 auto 8px' }} />
                <p style={{ fontSize: '0.85rem', fontWeight: 600 }}>
                  {srtFile ? srtFile.name : 'Select SRT Script'}
                </p>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  {srtFile ? `${(srtFile.size / 1024).toFixed(1)} KB` : 'UTF-8 format .srt file (up to 5MB)'}
                </p>
              </div>
            </div>
          </div>

          <div>
            <label htmlFor="intent-notes-input" style={{ display: 'block', fontWeight: 600, marginBottom: '8px' }}>
              Filmmaker Intent Notes (Optional)
            </label>
            <textarea
              id="intent-notes-input"
              rows={3}
              placeholder="e.g. The identity of Dr. Aris Thorne is concealed until the unmasking climax. Cue #3 prematurely names Dr. Thorne."
              value={intentNotes}
              onChange={(e) => setIntentNotes(e.target.value)}
              style={{
                width: '100%',
                padding: '12px 16px',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--text-primary)',
                fontSize: '0.9rem',
                resize: 'vertical',
              }}
            />
          </div>

          <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isSubmitting}
              style={{ flex: 1, padding: '14px' }}
            >
              <Upload className="w-5 h-5" />
              {isSubmitting ? 'Uploading & Creating Review...' : 'Start Review Session'}
            </button>

            <button
              type="button"
              className="btn btn-secondary"
              onClick={onLoadSample}
              disabled={isSubmitting}
              style={{ padding: '14px 20px' }}
            >
              <Sparkles className="w-5 h-5 text-amber-400" />
              Load Sample Demo
            </button>
          </div>
        </form>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="card" style={{ height: '100%' }}>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Clock className="w-5 h-5 text-indigo-400" />
              Recent Reviews
            </h2>

            {recentReviews.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                No recent review sessions found. Upload a film and SRT or click "Load Sample Demo" to begin.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {recentReviews.map((r) => (
                  <button
                    key={r.id}
                    onClick={() => onSelectReview(r.id)}
                    aria-label={`Open review session: ${r.title}`}
                    style={{
                      background: 'var(--bg-secondary)',
                      padding: '12px 14px',
                      borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--border-subtle)',
                      cursor: 'pointer',
                      textAlign: 'left',
                      width: '100%',
                      transition: 'all 0.2s ease',
                    }}
                  >
                    <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: '4px', color: 'var(--text-primary)' }}>{r.title}</div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      <span>{r.cue_count} Cues</span>
                      <span className={`badge badge-${r.status === 'completed' ? 'accepted' : 'unreviewed'}`}>
                        {r.finding_count} Findings
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
