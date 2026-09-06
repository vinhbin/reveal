import React, { useRef, useEffect, useState } from 'react';
import { Play, Pause, RotateCcw, Volume2, VolumeX } from 'lucide-react';
import { Finding } from '../types';

interface VideoPlayerProps {
  videoUrl: string;
  findings: Finding[];
  currentTime: number;
  seekTargetTime: number | null;
  onTimeUpdate: (time: number) => void;
  activeFinding: Finding | null;
  onSelectFinding: (finding: Finding) => void;
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({
  videoUrl,
  findings,
  currentTime,
  seekTargetTime,
  onTimeUpdate,
  activeFinding,
  onSelectFinding,
}) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [isMuted, setIsMuted] = useState(false);

  // Directly seek the video element whenever seekTargetTime changes
  useEffect(() => {
    if (videoRef.current && seekTargetTime !== null && !isNaN(seekTargetTime)) {
      videoRef.current.currentTime = seekTargetTime;
      onTimeUpdate(seekTargetTime);
    }
  }, [seekTargetTime]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleTimeUpdate = () => {
      onTimeUpdate(video.currentTime);
    };

    const handleLoadedMetadata = () => {
      setDuration(video.duration || 0);
    };

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);

    video.addEventListener('timeupdate', handleTimeUpdate);
    video.addEventListener('loadedmetadata', handleLoadedMetadata);
    video.addEventListener('play', handlePlay);
    video.addEventListener('pause', handlePause);

    return () => {
      video.removeEventListener('timeupdate', handleTimeUpdate);
      video.removeEventListener('loadedmetadata', handleLoadedMetadata);
      video.removeEventListener('play', handlePlay);
      video.removeEventListener('pause', handlePause);
    };
  }, [onTimeUpdate]);

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
    } else {
      videoRef.current.play();
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    if (videoRef.current) {
      videoRef.current.currentTime = time;
      onTimeUpdate(time);
    }
  };

  const formatSeconds = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    const ms = Math.floor((sec % 1) * 10);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}.${ms}`;
  };

  return (
    <div className="card" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div
        style={{
          position: 'relative',
          borderRadius: 'var(--radius-md)',
          overflow: 'hidden',
          background: '#000',
          aspectRatio: '16/9',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <video
          ref={videoRef}
          src={videoUrl}
          style={{ width: '100%', height: '100%', objectFit: 'contain' }}
          controls={false}
          playsInline
        />

        {activeFinding && (
          <div
            style={{
              position: 'absolute',
              top: '12px',
              left: '12px',
              right: '12px',
              background: 'rgba(15, 23, 42, 0.85)',
              backdropFilter: 'blur(8px)',
              padding: '8px 14px',
              borderRadius: 'var(--radius-sm)',
              borderLeft: '4px solid #f59e0b',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '0.85rem',
            }}
          >
            <span>
              <strong>Finding Candidate #{activeFinding.cue_index}:</strong> {activeFinding.candidate_name}
            </span>
            <span className="badge badge-unreviewed">{activeFinding.uncertainty} Uncertainty</span>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div style={{ position: 'relative', height: '12px', display: 'flex', alignItems: 'center' }}>
          <input
            type="range"
            min={0}
            max={duration || 100}
            step={0.1}
            value={currentTime}
            onChange={handleSeek}
            aria-label="Video Timeline Seek"
            style={{
              width: '100%',
              accentColor: 'var(--accent-primary)',
              cursor: 'pointer',
              height: '6px',
              borderRadius: '3px',
              zIndex: 10,
            }}
          />

          {duration > 0 &&
            findings.map((f) => {
              const leftPercent = (f.interval_start / duration) * 100;
              const isActive = activeFinding?.id === f.id;
              return (
                <button
                  key={f.id}
                  onClick={() => {
                    if (videoRef.current) {
                      videoRef.current.currentTime = f.interval_start;
                    }
                    onSelectFinding(f);
                  }}
                  title={`Finding #${f.cue_index}: ${f.candidate_name}`}
                  aria-label={`Jump to finding #${f.cue_index} for ${f.candidate_name}`}
                  style={{
                    position: 'absolute',
                    left: `${Math.min(leftPercent, 98)}%`,
                    top: '2px',
                    width: '10px',
                    height: '10px',
                    borderRadius: '50%',
                    background: isActive ? '#fbbf24' : '#f59e0b',
                    boxShadow: isActive ? '0 0 10px #fbbf24' : 'none',
                    border: 'none',
                    cursor: 'pointer',
                    zIndex: 20,
                    transform: 'translateX(-50%)',
                  }}
                />
              );
            })}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button className="btn btn-secondary" onClick={togglePlay} aria-label={isPlaying ? 'Pause' : 'Play'}>
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </button>

            <button
              className="btn btn-secondary"
              onClick={() => {
                if (videoRef.current) videoRef.current.currentTime = 0;
              }}
              aria-label="Restart Video"
            >
              <RotateCcw className="w-4 h-4" />
            </button>

            <button
              className="btn btn-secondary"
              onClick={() => {
                if (videoRef.current) {
                  videoRef.current.muted = !isMuted;
                  setIsMuted(!isMuted);
                }
              }}
              aria-label={isMuted ? 'Unmute' : 'Mute'}
            >
              {isMuted ? <VolumeX className="w-4 h-4 text-red-400" /> : <Volume2 className="w-4 h-4" />}
            </button>

            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              {formatSeconds(currentTime)} / {formatSeconds(duration)}
            </span>
          </div>

          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Keyboard: <kbd>Space</kbd> Play/Pause &bull; <kbd>J</kbd>/<kbd>L</kbd> Seek 5s
          </div>
        </div>
      </div>
    </div>
  );
};
