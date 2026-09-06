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
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
        <h3 style={{ fontSize: '1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Filter className="w-4 h-4 text-indigo-400" />
          AD Cues ({filteredCues.length} of {cues.length})
        </h3>

        <div style={{ display: 'flex', gap: '4px' }}>
          {(['all', 'findings', 'unreviewed', 'accepted'] as const).map((f) => (
            <button
              key={f}
              className={`btn ${filter === f ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setFilter(f)}
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
              role="button"
              tabIndex={0}
              onClick={() => {
                onSelectCue(cue);
                if (cueFindings.length > 0) onSelectFinding(cueFindings[0]);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onSelectCue(cue);
                  if (cueFindings.length > 0) onSelectFinding(cueFindings[0]);
                }
              }}
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
                cursor: 'pointer',
                transition: 'all 0.2s ease',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      color: 'var(--accent-primary)',
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
                </div>

                <div style={{ display: 'flex', gap: '4px' }}>
                  {cueFindings.map((f) => (
                    <span
                      key={f.id}
                      className={`badge badge-${f.status}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectCue(cue);
                        onSelectFinding(f);
                      }}
                    >
                      {f.status === 'accepted' && <CheckCircle2 className="w-3 h-3" />}
                      {f.status === 'unreviewed' && <AlertTriangle className="w-3 h-3" />}
                      {f.status === 'dismissed' && <XCircle className="w-3 h-3" />}
                      {f.status === 'intentional' && <HelpCircle className="w-3 h-3" />}
                      {f.candidate_name}: {f.status}
                    </span>
                  ))}
                </div>
              </div>

              <p style={{ fontSize: '0.9rem', color: 'var(--text-primary)', lineHeight: 1.4 }}>{cue.text}</p>

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
