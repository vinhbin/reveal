import React, { useState, useEffect } from 'react';
import { Finding, DecisionStatus } from '../types';
import { AlertTriangle, Check, X, ShieldAlert, RefreshCw } from 'lucide-react';

interface FindingInspectorProps {
  finding: Finding;
  originalCueText: string;
  onUpdateDecision: (findingId: string, status?: DecisionStatus, editedProposal?: string) => void;
}

export const FindingInspector: React.FC<FindingInspectorProps> = ({
  finding,
  originalCueText,
  onUpdateDecision,
}) => {
  const [editedText, setEditedText] = useState(finding.edited_proposal || finding.proposed_text);
  const isDraftUnsaved = editedText !== (finding.edited_proposal || finding.proposed_text);

  useEffect(() => {
    setEditedText(finding.edited_proposal || finding.proposed_text);
  }, [finding]);

  const handleAccept = () => {
    onUpdateDecision(finding.id, 'accepted', editedText);
  };

  const handleDismiss = () => {
    onUpdateDecision(finding.id, 'dismissed');
  };

  const handleIntentional = () => {
    onUpdateDecision(finding.id, 'intentional');
  };

  const handleReopen = () => {
    onUpdateDecision(finding.id, 'unreviewed');
  };

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <AlertTriangle className="w-5 h-5 text-amber-400" />
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>
            Finding Inspector — Cue #{finding.cue_index}
          </h3>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className={`badge badge-${finding.status}`}>{finding.status}</span>
          <span className="badge" style={{ background: 'var(--bg-secondary)', color: 'var(--text-secondary)' }}>
            {finding.evidence_origin.replace('_', ' ')}
          </span>
        </div>
      </div>

      {/* Candidate Issue Alert Box */}
      <div
        style={{
          background: 'rgba(245, 158, 11, 0.1)',
          border: '1px solid var(--status-unreviewed-border)',
          borderRadius: 'var(--radius-md)',
          padding: '14px',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
        }}
      >
        <div style={{ fontWeight: 700, color: 'var(--status-unreviewed-text)', fontSize: '0.9rem' }}>
          Premature Identity Disclosure: "{finding.candidate_name}"
        </div>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-primary)', lineHeight: 1.4 }}>
          {finding.issue_description}
        </p>
      </div>

      {/* Comparison Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
        {/* Original Cue Text */}
        <div style={{ background: 'var(--bg-secondary)', padding: '12px 14px', borderRadius: 'var(--radius-md)' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '4px' }}>
            ORIGINAL CUE TEXT
          </div>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>{originalCueText}</p>
        </div>

        {/* Proposed Wording Editor */}
        <div style={{ background: 'var(--bg-secondary)', padding: '12px 14px', borderRadius: 'var(--radius-md)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)' }}>
              PROPOSED ANONYMIZED WORDING
            </span>
            {isDraftUnsaved && (
              <span style={{ fontSize: '0.75rem', color: '#f59e0b', fontWeight: 600 }}>
                &bull; Unsaved Draft Edits
              </span>
            )}
          </div>

          <textarea
            rows={3}
            value={editedText}
            onChange={(e) => setEditedText(e.target.value)}
            style={{
              width: '100%',
              padding: '8px 10px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-primary)',
              fontSize: '0.9rem',
              resize: 'vertical',
            }}
          />
        </div>
      </div>

      {/* Decision Actions Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '8px' }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="btn btn-accept" onClick={handleAccept}>
            <Check className="w-4 h-4" />
            Accept Revision
          </button>

          <button className="btn btn-dismiss" onClick={handleDismiss}>
            <X className="w-4 h-4" />
            Dismiss Concern
          </button>

          <button className="btn btn-intentional" onClick={handleIntentional}>
            <ShieldAlert className="w-4 h-4" />
            Mark Intentional
          </button>
        </div>

        {finding.status !== 'unreviewed' && (
          <button className="btn btn-secondary" onClick={handleReopen}>
            <RefreshCw className="w-4 h-4" />
            Reopen Decision
          </button>
        )}
      </div>
    </div>
  );
};
