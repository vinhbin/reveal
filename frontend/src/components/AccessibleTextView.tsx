import React, { useState } from 'react';
import { Cue, Finding, DecisionStatus } from '../types';
import { Download, Check, X, ShieldAlert, RefreshCw } from 'lucide-react';

interface AccessibleTextViewProps {
  title: string;
  cues: Cue[];
  findings: Finding[];
  onUpdateDecision: (findingId: string, status?: DecisionStatus, editedProposal?: string) => void;
  onExport: () => void;
  onSeek?: (seconds: number) => void;
}

export const AccessibleTextView: React.FC<AccessibleTextViewProps> = ({
  title,
  cues,
  findings,
  onUpdateDecision,
  onExport,
  onSeek,
}) => {
  const [editedProposals, setEditedProposals] = useState<Record<string, string>>({});

  const findingsMap = new Map<string, Finding[]>();
  findings.forEach((f) => {
    if (!findingsMap.has(f.cue_id)) {
      findingsMap.set(f.cue_id, []);
    }
    findingsMap.get(f.cue_id)!.push(f);
  });

  return (
    <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto', background: '#000', color: '#fff', minHeight: '80vh' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 800 }}>{title}</h1>
          <p style={{ color: '#aaa', fontSize: '1rem' }}>
            High-Contrast Accessible Text Review Table (Screen Reader & Accessible Editorial Mode)
          </p>
        </div>

        <button className="btn btn-primary" onClick={onExport} style={{ padding: '12px 20px', fontSize: '1rem' }}>
          <Download className="w-5 h-5" />
          Export Revised SRT
        </button>
      </div>

      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: '1rem',
          lineHeight: '1.6',
        }}
        aria-label="Audio Description Script Cues and Identity Disclosures Table"
      >
        <thead>
          <tr style={{ borderBottom: '2px solid #fff', textAlign: 'left' }}>
            <th style={{ padding: '12px', width: '80px' }}>Cue #</th>
            <th style={{ padding: '12px', width: '180px' }}>Timestamp</th>
            <th style={{ padding: '12px' }}>Audio Description & Candidate Disclosures</th>
            <th style={{ padding: '12px', width: '320px' }}>Editorial Decisions</th>
          </tr>
        </thead>
        <tbody>
          {cues.map((cue) => {
            const cueFindings = findingsMap.get(cue.id) || [];
            return (
              <tr key={cue.id} style={{ borderBottom: '1px solid #333' }}>
                <td style={{ padding: '12px', fontWeight: 'bold' }}>#{cue.index}</td>
                <td style={{ padding: '12px', fontFamily: 'monospace' }}>
                  <div>{cue.start_time} - {cue.end_time}</div>
                  {onSeek && (
                    <button
                      type="button"
                      aria-label={`Jump video to cue #${cue.index} at ${cue.start_time}`}
                      onClick={() => onSeek(cue.start_seconds)}
                      style={{
                        marginTop: '4px',
                        padding: '4px 8px',
                        background: '#334155',
                        color: '#f8fafc',
                        border: '1px solid #64748b',
                        borderRadius: '4px',
                        fontSize: '0.75rem',
                        cursor: 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                      }}
                    >
                      &#9654; Play from here
                    </button>
                  )}
                </td>
                <td style={{ padding: '12px' }}>
                  <div><strong>Original Text:</strong> {cue.text}</div>

                  {cueFindings.map((finding) => (
                    <div key={finding.id} style={{ marginTop: '12px', padding: '12px', background: '#1a1a1a', borderLeft: '4px solid #f59e0b', borderRadius: '4px' }}>
                      <p style={{ color: '#fbbf24', fontWeight: 'bold' }}>
                        Premature Disclosure Flag: {finding.candidate_name} ({finding.uncertainty} uncertainty)
                      </p>
                      <p style={{ fontSize: '0.9rem', color: '#ccc', margin: '4px 0' }}>{finding.issue_description}</p>
                      
                      <div style={{ marginTop: '8px' }}>
                        <label htmlFor={`proposal-${finding.id}`} style={{ display: 'block', fontSize: '0.85rem', color: '#34d399', fontWeight: 'bold', marginBottom: '4px' }}>
                          Proposed Anonymized Wording:
                        </label>
                        <textarea
                          id={`proposal-${finding.id}`}
                          rows={2}
                          value={editedProposals[finding.id] ?? (finding.edited_proposal || finding.proposed_text)}
                          onChange={(e) => setEditedProposals({ ...editedProposals, [finding.id]: e.target.value })}
                          style={{
                            width: '100%',
                            padding: '6px 10px',
                            background: '#111',
                            color: '#fff',
                            border: '1px solid #444',
                            borderRadius: '4px',
                            fontSize: '0.9rem',
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </td>
                <td style={{ padding: '12px' }}>
                  {cueFindings.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {cueFindings.map((finding) => {
                        const currentDraft = editedProposals[finding.id] ?? (finding.edited_proposal || finding.proposed_text);
                        return (
                          <div key={finding.id} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                            <div style={{ fontWeight: 'bold', textTransform: 'uppercase', fontSize: '0.85rem', color: finding.status === 'accepted' ? '#34d399' : '#fbbf24' }}>
                              {finding.candidate_name}: {finding.status}
                            </div>
                            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                              <button
                                onClick={() => onUpdateDecision(finding.id, 'accepted', currentDraft)}
                                style={{ padding: '6px 10px', background: '#10b981', color: '#000', fontWeight: 'bold', border: 'none', borderRadius: '4px', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                              >
                                <Check className="w-3 h-3" /> Accept
                              </button>
                              <button
                                onClick={() => onUpdateDecision(finding.id, 'dismissed')}
                                style={{ padding: '6px 10px', background: '#64748b', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                              >
                                <X className="w-3 h-3" /> Dismiss
                              </button>
                              <button
                                onClick={() => onUpdateDecision(finding.id, 'intentional')}
                                style={{ padding: '6px 10px', background: '#a855f7', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                              >
                                <ShieldAlert className="w-3 h-3" /> Intentional
                              </button>
                              {finding.status !== 'unreviewed' && (
                                <button
                                  onClick={() => onUpdateDecision(finding.id, 'unreviewed')}
                                  style={{ padding: '6px 10px', background: '#333', color: '#ccc', border: '1px solid #555', borderRadius: '4px', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                                >
                                  <RefreshCw className="w-3 h-3" /> Reopen
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <span style={{ color: '#888' }}>Clean Cue</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
