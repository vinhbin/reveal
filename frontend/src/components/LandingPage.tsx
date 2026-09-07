import { useEffect, useRef, useState } from 'react';
import { ArrowRight, Check, Eye, FileText, Film, Play, Sparkles } from 'lucide-react';
import './LandingPage.css';

const DEMO_URL = 'https://youtu.be/py-tZLzaG-U';

export function LandingPage({ focusOnMount = false }: { focusOnMount?: boolean }) {
  const [revised, setRevised] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    // Give browser-back and the editor's home control a clear focus destination.
    if (!focusOnMount) return;
    if (window.location.hash === '#how-it-works') {
      document.getElementById('how-it-works')?.focus();
    } else {
      heading.current?.focus({ preventScroll: true });
    }
  }, [focusOnMount]);

  return (
    <div className="reveal-landing">
      <a className="rl-skip" href="#landing-main">Skip to content</a>
      <header className="rl-nav rl-shell">
        <a className="rl-wordmark" href="#" aria-label="Reveal home"><span className="brand-icon"><Eye size={20} aria-hidden="true" /></span><span className="brand-title">REVEAL</span><span className="brand-subtitle">AD Reviewer</span></a>
        <nav aria-label="Main navigation">
          <a className="rl-how-link" href="#how-it-works">How it works</a>
          <a className="rl-nav-open" href="#/review">Open Reveal <ArrowRight size={16} aria-hidden="true" /></a>
        </nav>
      </header>

      <main id="landing-main" tabIndex={-1}>
        <section className="rl-hero rl-shell" aria-labelledby="landing-title">
          <div className="rl-hero-copy">
            <p className="rl-eyebrow"><span /> A second look for audio description</p>
            <h1 id="landing-title" ref={heading} tabIndex={-1}>Same suspense.<br /><em>Shared discovery.</em></h1>
            <p className="rl-hero-description">A name can give away the story. Catch identity spoilers in audio-description scripts <strong>before narration is recorded.</strong></p>
            <div className="rl-actions">
              <a className="rl-button rl-button-primary" href="#/review">Open Reveal <ArrowRight size={19} aria-hidden="true" /></a>
              <a className="rl-button rl-button-quiet" href={DEMO_URL} target="_blank" rel="noreferrer"><Play size={16} aria-hidden="true" /> Watch the demo <span className="rl-runtime">2:19</span></a>
            </div>
            <p className="rl-hero-note"><Sparkles size={14} aria-hidden="true" /> Gemini assists. The editor decides.</p>
          </div>

          <figure className="rl-scene">
            <div className="rl-scene-top"><span><span className="rl-record-dot" /> The moment before the reveal</span><span>00:05</span></div>
            <svg viewBox="0 0 560 300" className="rl-scene-art" role="img" aria-label="Illustration of an unidentified visitor standing in a dim theater doorway">
              <defs>
                <linearGradient id="rl-room" x2="0" y2="1"><stop stopColor="#1c2640" /><stop offset="1" stopColor="#0b0f19" /></linearGradient>
                <linearGradient id="rl-door" x2="0" y2="1"><stop stopColor="#e3ce9b" /><stop offset="1" stopColor="#64748b" /></linearGradient>
              </defs>
              <path fill="url(#rl-room)" d="M0 0h560v300H0z" />
              <path fill="#243152" d="M0 252 560 233v67H0z" />
              <path fill="#334155" d="M0 255 560 236v2L0 257z" />
              <path fill="#0b0f19" d="M175 31h162v235H175z" />
              <path fill="#64748b" d="M184 40h144v224H184z" />
              <path fill="url(#rl-door)" d="M192 46h128v218H192z" />
              <path fill="#131b2e" d="m192 46 84 26v187l-84 5z" />
              <path fill="#94a3b8" d="m276 72 3 1v185l-3 1z" />
              <circle cx="263" cy="169" r="3" fill="#dabf82" />
              <path fill="#a4a681" opacity=".12" d="m280 259 40-1 176 42H153z" />
              <ellipse cx="311" cy="267" rx="36" ry="6" fill="#0b0f19" opacity=".7" />
              <path fill="#0b0f19" d="M293 151q-1-28 17-31 18 3 19 32l-3 21 16 68h-58l12-68z" />
              <path fill="#131b2e" d="M304 145q10-11 18 0l-5 19h-10z" />
              <path fill="#0b0f19" d="m291 237-3 30h17l6-27 5 27h17l-8-30z" />
              <path fill="#243152" d="m297 170-7 61 10-42z" />
              <path fill="#243152" d="M54 115h69v85H54zM402 89h82v111h-82z" />
              <path stroke="#64748b" strokeWidth="1" fill="none" opacity=".5" d="M60 122h57v72H60zM409 96h68v97h-68z" />
              <text x="443" y="133" textAnchor="middle" fill="#94a3b8" fontSize="8" letterSpacing="3">THE LAST</text>
              <text x="443" y="148" textAnchor="middle" fill="#94a3b8" fontSize="8" letterSpacing="3">VISITOR</text>
              <path stroke="#475569" d="M0 215h174M338 215h222" />
            </svg>
            <div className="rl-description-card">
              <div className="rl-description-label"><FileText size={13} aria-hidden="true" /> Audio-description draft <span>{revised ? 'Editor revision' : 'Possible spoiler'}</span></div>
              <p aria-live="polite" aria-atomic="true">“{revised ? <><mark className="rl-safe">A hooded visitor</mark> enters the room.</> : <><mark>Mara</mark> enters the room.</>}”</p>
              <button type="button" className="rl-revision-toggle" aria-pressed={revised} onClick={() => setRevised(!revised)}>
                {revised ? <><Check size={15} aria-hidden="true" /> Show original wording</> : <>See an editor’s revision <ArrowRight size={15} aria-hidden="true" /></>}
              </button>
            </div>
            <figcaption>Illustrative example · The film hasn’t revealed her name yet.</figcaption>
          </figure>
        </section>

        <section className="rl-timing rl-shell" aria-label="Why the timing matters">
          <div className="rl-timing-intro"><span className="rl-eyebrow">One name. Two different moments.</span><p>Keep the reveal<br /> where the story puts it.</p></div>
          <div className="rl-timeline">
            <div className="rl-timeline-track" aria-hidden="true"><span /><span /></div>
            <div className="rl-timeline-labels">
              <div><time>00:05</time><strong>The description says “Mara.”</strong><span>The audience hears her identity early.</span></div>
              <div><time>01:06</time><strong>The film reveals her name.</strong><span>This is the intended discovery.</span></div>
            </div>
            <p>Timing from our synthetic demo scene.</p>
          </div>
        </section>

        <section id="how-it-works" className="rl-workflow rl-shell" aria-labelledby="workflow-title" tabIndex={-1}>
          <div className="rl-section-heading"><p className="rl-eyebrow">Fits the review you already do</p><h2 id="workflow-title">Between the draft<br />and the recording.</h2><p>Bring the scene and its description. Leave with wording you’ve reviewed and approved.</p></div>
          <ol className="rl-steps">
            <li><span className="rl-step-number">01 / Upload</span><Film size={24} aria-hidden="true" /><h3>One clip. One script.</h3><p>Add an MP4 or WebM clip and a timed audio-description draft in SRT format. Include filmmaker notes for context.</p></li>
            <li><span className="rl-step-number">02 / Review</span><Eye size={24} aria-hidden="true" /><h3>A closer look, with Gemini.</h3><p>Compare possible early reveals with the scene. Edit a suggestion, dismiss the concern, or mark the wording intentional.</p></li>
            <li><span className="rl-step-number">03 / Export</span><FileText size={24} aria-hidden="true" /><h3>Your words. Your final cut.</h3><p>Export the revised SRT with your accepted wording, ready for the next step in your narration workflow.</p></li>
          </ol>
        </section>

        <section className="rl-purpose" aria-labelledby="purpose-title">
          <div className="rl-shell rl-purpose-inner"><div><p className="rl-eyebrow">Accessibility includes the experience</p><h2 id="purpose-title">Let everyone meet<br />the mystery.</h2></div><div><p>Audio description conveys visual details for blind and low-vision audiences. Revealing a name too soon can change how someone experiences a scene.</p><p>Reveal helps editors consider what to describe—and when—so the description supports both understanding and suspense.</p><a href="https://www.w3.org/WAI/media/av/description/" target="_blank" rel="noreferrer">Learn about audio description <ArrowRight size={16} aria-hidden="true" /></a></div></div>
        </section>

        <section className="rl-faq rl-shell" aria-labelledby="faq-title">
          <h2 id="faq-title">Before you bring a scene.</h2>
          <div>
            <details><summary>Does my clip need captions?</summary><p>No. Upload the movie clip and a separate audio-description draft. Dialogue captions convey speech and sounds; audio description conveys visual details. Reveal currently reviews an existing description draft.</p></details>
            <details><summary>What does Gemini actually do?</summary><p>Reveal sends the clip, timed cues, and any filmmaker notes to the Gemini API through Google’s Gen AI SDK. It returns possible identity disclosures and suggested wording. Findings need human review; they aren’t a verdict.</p></details>
            <details><summary>Can I try it if Gemini is busy?</summary><p>You can watch the demo above to explore a recorded, successful Gemini result. New analyses require available Gemini quota and capacity. A failed analysis is shown explicitly.</p></details>
            <details><summary>Is this a private workspace?</summary><p>This release is a shared public demo. Other visitors can access and change reviews. Use sample or non-confidential material; separate accounts and durable media storage are planned.</p></details>
          </div>
        </section>

        <section className="rl-closing rl-shell" aria-labelledby="closing-title"><p className="rl-eyebrow">The next reveal belongs to your audience</p><h2 id="closing-title">Give the story a second look.</h2><a className="rl-button rl-button-primary" href="#/review">Open Reveal <ArrowRight size={19} aria-hidden="true" /></a><p>A shared public demo. Bring non-confidential test material.</p></section>
      </main>
      <footer className="rl-footer rl-shell"><a className="rl-wordmark" href="#" aria-label="Reveal home"><span className="brand-icon"><Eye size={20} aria-hidden="true" /></span><span className="brand-title">REVEAL</span><span className="brand-subtitle">AD Reviewer</span></a><p>Same suspense. Shared discovery.</p><a href="https://github.com/vinhbin/reveal" target="_blank" rel="noreferrer">View source <ArrowRight size={14} aria-hidden="true" /></a></footer>
    </div>
  );
}
