import React, { useState, useEffect } from 'react';
import { Review, DecisionStatus, SeekRequest } from '../types';
import { VideoPlayer } from './VideoPlayer';
import { CueList } from './CueList';
import { FindingInspector } from './FindingInspector';
import { AccessibleTextView } from './AccessibleTextView';
import { Download, RefreshCw, Trash2, CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react';
import { getExportUrl, getVideoUrl } from '../api';
import { analysisErrorMessage } from '../reviewStatus';

interface ReviewWorkspaceProps {
  review: Review;
  isAccessibleView: boolean;
  onUpdateDecision: (findingId: string, status?: DecisionStatus, editedProposal?: string) => void;
  onReanalyze: (reviewId: string) => void;
  onDeleteReview: (reviewId: string) => void;
  isAnalyzing: boolean;
}

export const ReviewWorkspace: React.FC<ReviewWorkspaceProps> = ({
  review,
  isAccessibleView,
  onUpdateDecision,
  onReanalyze,
  onDeleteReview,
  isAnalyzing,
}) => {
  const [currentTime, setCurrentTime] = useState(0);
  const [seekRequest, setSeekRequest] = useState<SeekRequest | null>(null);
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(null);
  const [unavailableVideoUrl, setUnavailableVideoUrl] = useState<string | null>(null);

  // Always derive current finding directly from review.findings to avoid stale state
  const selectedFinding = review.findings.find((f) => f.id === selectedFindingId) || review.findings[0] || null;

  useEffect(() => {
    if (review.findings.length > 0 && !selectedFindingId) {
      setSelectedFindingId(review.findings[0].id);
    }
  }, [review.findings, selectedFindingId]);

  const handleExport = () => {
    window.location.href = getExportUrl(review.id);
  };

  const activeCue = review.cues.find(
    (c) => currentTime >= c.start_seconds && currentTime <= c.end_seconds
  );

  const selectedCue = selectedFinding
    ? review.cues.find((c) => c.id === selectedFinding.cue_id)
    : activeCue || review.cues[0];

  const videoUrl = getVideoUrl(review.id);
  const mediaUnavailable = unavailableVideoUrl === videoUrl;
  const acceptedCount = review.findings.filter((f) => f.status === 'accepted').length;
  const unreviewedCount = review.findings.filter((f) => f.status === 'unreviewed').length;
  const hasAcceptedEdits = review.findings.some((finding) =>
    finding.status === 'accepted' &&
    (finding.edited_proposal || finding.proposed_text) !== review.cues.find((cue) => cue.id === finding.cue_id)?.text
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {review.analysis_source === 'recorded' && (
        <p role="note" className="public-demo-notice">
          <strong>Recorded Gemini example{review.recorded_at ? ` · ${new Date(review.recorded_at).toLocaleDateString()}` : ''}.</strong>{' '}
          This review starts with a saved Gemini result. Editing and exporting do not make a new model call.
          Re-run Analysis requests a new analysis.
        </p>
      )}
      {/* Review Status Banner for Analyzing or Failed States */}
      {(review.status === 'analyzing' || isAnalyzing) && (
        <div
          role="status"
          style={{
            background: 'rgba(99, 102, 241, 0.15)',
            border: '1px solid var(--accent-primary)',
            padding: '14px 20px',
            borderRadius: 'var(--radius-md)',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            color: 'var(--text-primary)',
          }}
        >
          <Loader2 className="w-5 h-5 animate-spin text-indigo-400" />
          <div>
            <strong>Analyzing Film & AD Script...</strong> Multimodal AI is inspecting timeline identity disclosures.
          </div>
        </div>
      )}

      {review.status === 'failed' && (
        <div
          role="alert"
          className="analysis-error"
          style={{
            background: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid #ef4444',
            padding: '14px 20px',
            borderRadius: 'var(--radius-md)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            color: '#fca5a5',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <AlertTriangle className="w-5 h-5 flex-shrink-0" />
            <div>
              <strong>Analysis failed:</strong> {analysisErrorMessage(review.error_message)}
              {review.error_message && (
                <details className="provider-details">
                  <summary>Technical details</summary>
                  <p>{review.error_message}</p>
                </details>
              )}
            </div>
          </div>

          <button className="btn btn-secondary" onClick={() => onReanalyze(review.id)} disabled={isAnalyzing || mediaUnavailable} aria-describedby={mediaUnavailable ? 'analysis-media-needed' : undefined}>
            <RefreshCw className={`w-4 h-4 ${isAnalyzing ? 'animate-spin' : ''}`} />
            Retry Analysis
          </button>
        </div>
      )}

      {/* Action Header Bar */}
      <div
        className="card"
        style={{
          padding: '16px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700 }}>{review.title}</h1>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            <span>Last completed analysis: <strong>{review.model_used || 'None yet'}</strong></span>
            <span>Total Cues: <strong>{review.cues.length}</strong></span>
            <span>Findings: <strong>{review.findings.length}</strong></span>
            <span>Unreviewed: <strong style={{ color: '#f59e0b' }}>{unreviewedCount}</strong></span>
            <span>Accepted Edits: <strong style={{ color: '#10b981' }}>{acceptedCount}</strong></span>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          {review.status !== 'failed' && <button className="btn btn-secondary" onClick={() => onReanalyze(review.id)} disabled={isAnalyzing || review.status === 'analyzing' || mediaUnavailable} aria-describedby={mediaUnavailable ? 'analysis-media-needed' : undefined}>
            <RefreshCw className={`w-4 h-4 ${isAnalyzing ? 'animate-spin' : ''}`} />
            {isAnalyzing ? 'Analyzing...' : 'Re-run Analysis'}
          </button>}

          <button className="btn btn-primary" onClick={handleExport}>
            <Download className="w-4 h-4" />
            {hasAcceptedEdits ? 'Export revised SRT' : 'Export original SRT'}
          </button>

          <button
            className="btn btn-danger"
            disabled={isAnalyzing || review.status === 'analyzing'}
            onClick={() => {
              if (window.confirm('Are you sure you want to delete this review session and its video file?')) {
                onDeleteReview(review.id);
              }
            }}
          >
            <Trash2 className="w-4 h-4" />
            Delete
          </button>
        </div>
      </div>

      {mediaUnavailable && <p id="analysis-media-needed" role="status" className="public-demo-notice">Analysis needs a playable clip. Refresh to retry loading the video, or start a new review with the original clip. You can also open the saved Gemini example.</p>}

      {isAccessibleView ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <VideoPlayer
            videoUrl={videoUrl}
            onMediaAvailabilityChange={(available) => setUnavailableVideoUrl(available ? null : videoUrl)}
            findings={review.findings}
            currentTime={currentTime}
            seekRequest={seekRequest}
            onTimeUpdate={setCurrentTime}
            activeFinding={selectedFinding}
            onSelectFinding={(f) => {
              setSelectedFindingId(f.id);
              setSeekRequest({ time: f.interval_start, nonce: Date.now() });
            }}
          />
          <AccessibleTextView
            title={review.title}
            cues={review.cues}
            findings={review.findings}
            onUpdateDecision={onUpdateDecision}
            onExport={handleExport}
            analysisCompleted={Boolean(review.model_used)}
            hasAcceptedEdits={hasAcceptedEdits}
            onSeek={(time) => {
              setSeekRequest({ time, nonce: Date.now() });
              setCurrentTime(time);
            }}
          />
        </div>
      ) : (
        /* Main Split Grid */
        <div className="workspace-grid" style={{ minHeight: '650px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <VideoPlayer
              videoUrl={videoUrl}
              onMediaAvailabilityChange={(available) => setUnavailableVideoUrl(available ? null : videoUrl)}
              findings={review.findings}
              currentTime={currentTime}
              seekRequest={seekRequest}
              onTimeUpdate={setCurrentTime}
              activeFinding={selectedFinding}
              onSelectFinding={(f) => {
                setSelectedFindingId(f.id);
                setSeekRequest({ time: f.interval_start, nonce: Date.now() });
              }}
            />

            {selectedFinding ? (
              <FindingInspector
                finding={selectedFinding}
                originalCueText={selectedCue?.text || ''}
                onUpdateDecision={onUpdateDecision}
              />
            ) : (
              <div className="card" style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
                {review.model_used
                  ? <CheckCircle2 className="w-8 h-8 text-emerald-400" style={{ margin: '0 auto 8px' }} />
                  : <AlertTriangle className="w-8 h-8" style={{ margin: '0 auto 8px' }} />}
                <p>{review.model_used
                  ? 'The last completed analysis returned no findings. You can still review the script and video.'
                  : mediaUnavailable ? 'No completed analysis yet. Restore the video before starting analysis.' : 'No completed analysis yet. Run analysis to review possible identity disclosures.'}</p>
              </div>
            )}
          </div>

          <CueList
            cues={review.cues}
            findings={review.findings}
            selectedFindingId={selectedFindingId}
            onSelectCue={(cue) => {
              setSeekRequest({ time: cue.start_seconds, nonce: Date.now() });
              setCurrentTime(cue.start_seconds);
            }}
            onSelectFinding={(f) => {
              setSelectedFindingId(f.id);
              setSeekRequest({ time: f.interval_start, nonce: Date.now() });
            }}
            currentTime={currentTime}
          />
        </div>
      )}
    </div>
  );
};
