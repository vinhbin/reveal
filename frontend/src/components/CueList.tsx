import React, { useState } from 'react';
import { Cue, Finding } from '../types';
import { AlertTriangle, CheckCircle2, XCircle, HelpCircle, Filter } from 'lucide-react';

interface CueListProps {
  cues: Cue[];
  findings: Finding[];
  selectedFindingId: string | null;
  onSelectCue: (cue: Cue) => void;
  onSelectFinding: (finding: Finding) => void;
  currentTime: number;
}

export const CueList: React.FC<CueListProps> = ({
  cues,
  findings,
  selectedFindingId,
  onSelectCue,
  onSelectFinding,
  currentTime,
}) => {
  const [filter, setFilter] = useState<'all' | 'findings' | 'unreviewed' | 'accepted'>('all');

  // Map cue_id -> array of findings (supporting multiple findings per cue)
  const findingsMap = new Map<string, Finding[]>();
  findings.forEach((f) => {
    if (!findingsMap.has(f.cue_id)) {
      findingsMap.set(f.cue_id, []);
    }
    findingsMap.get(f.cue_id)!.push(f);
  });

  const filteredCues = cues.filter((c) => {
    const cueFindings = findingsMap.get(c.id) || [];
    if (filter === 'findings') return cueFindings.length > 0;
    if (filter === 'unreviewed') return cueFindings.some((f) => f.status === 'unreviewed');
    if (filter === 'accepted') return cueFindings.some((f) => f.status === 'accepted');
    return true;
  });

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: '16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', flexWrap: 'wrap', gap: '12px' }}>
        <h2 style={{ fontSize: '1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Filter className="w-4 h-4 text-indigo-400" />
          AD Cues ({filteredCues.length} of {cues.length})
        </h2>

        <div role="group" aria-label="Filter audio description cues" style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
          {(['all', 'findings', 'unreviewed', 'accepted'] as const).map((f) => (
            <button
              key={f}
              className={`btn ${filter === f ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setFilter(f)}
              aria-pressed={filter === f}
              style={{ padding: '4px 10px', fontSize: '0.75rem', textTransform: 'capitalize' }}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {filteredCues.map((cue) => {
          const cueFindings = findingsMap.get(cue.id) || [];
          const isSelected = cueFindings.some((f) => f.id === selectedFindingId);
          const isCurrentCue = currentTime >= cue.start_seconds && currentTime <= cue.end_seconds;

          return (
            <div
              key={cue.id}
              style={{
                padding: '12px 14px',
                borderRadius: 'var(--radius-md)',
                background: isSelected
                  ? 'var(--bg-card-hover)'
                  : isCurrentCue
                  ? 'rgba(99, 102, 241, 0.12)'
                  : 'var(--bg-secondary)',
                border: isSelected
                  ? '1px solid var(--accent-primary)'
                  : cueFindings.length > 0
                  ? `1px solid ${
                      cueFindings.some((f) => f.status === 'accepted')
                        ? '#10b981'
                        : cueFindings.some((f) => f.status === 'unreviewed')
                        ? '#f59e0b'
                        : 'var(--border-subtle)'
                    }`
                  : '1px solid var(--border-subtle)',
                transition: 'all 0.2s ease',
              }}
            >
              <button
                type="button"
                className="cue-select"
                aria-label={`Play cue ${cue.index} at ${cue.start_time}: ${cue.text}`}
                onClick={() => {
                  onSelectCue(cue);
                  if (cueFindings.length > 0) onSelectFinding(cueFindings[0]);
                }}
              >
                <span style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <span
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      color: '#b5b8ff',
                      background: 'var(--bg-card)',
                      padding: '2px 6px',
                      borderRadius: '4px',
                    }}
                  >
                    #{cue.index}
                  </span>

                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {cue.start_time} &rarr; {cue.end_time}
                  </span>
                </span>
                <span style={{ display: 'block', fontSize: '0.9rem', color: 'var(--text-primary)', lineHeight: 1.4, marginTop: '6px' }}>{cue.text}</span>
              </button>

                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: cueFindings.length ? '10px' : 0 }}>
                  {cueFindings.map((f) => (
                    <button
                      type="button"
                      key={f.id}
                      className={`badge badge-${f.status}`}
                      aria-label={`Select finding #${f.cue_index} for ${f.candidate_name}, status ${f.status}`}
                      aria-pressed={selectedFindingId === f.id}
                      style={{ cursor: 'pointer', border: '1px solid transparent' }}
                      onClick={() => {
                        onSelectCue(cue);
                        onSelectFinding(f);
                      }}
                    >
                      {f.status === 'accepted' && <CheckCircle2 className="w-3 h-3" />}
                      {f.status === 'unreviewed' && <AlertTriangle className="w-3 h-3" />}
                      {f.status === 'dismissed' && <XCircle className="w-3 h-3" />}
                      {f.status === 'intentional' && <HelpCircle className="w-3 h-3" />}
                      {f.candidate_name}: {f.status}
                    </button>
                  ))}
                </div>

              {cueFindings.some((f) => f.status === 'accepted') && (
                <div
                  style={{
                    marginTop: '8px',
                    padding: '6px 10px',
                    background: 'rgba(16, 185, 129, 0.1)',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.8rem',
                    color: 'var(--status-accepted-text)',
                  }}
                >
                  <strong>Accepted Revision:</strong> "{cueFindings.find((f) => f.status === 'accepted')?.edited_proposal}"
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
