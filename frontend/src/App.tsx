import React, { useState, useEffect, useRef } from 'react';
import { Header } from './components/Header';
import { UploadView } from './components/UploadView';
import { ReviewWorkspace } from './components/ReviewWorkspace';
import { LandingPage } from './components/LandingPage';
import { Review, ReviewSummary, DecisionStatus } from './types';
import {
  fetchReviews,
  fetchReviewDetail,
  createReview,
  createSampleReview,
  createRecordedExample,
  triggerAnalysis,
  updateFinding,
  deleteReview,
} from './api';

export const App: React.FC = () => {
  const [isEditor, setIsEditor] = useState(() => window.location.hash === '#/review');
  const [hasOpenedEditor, setHasOpenedEditor] = useState(isEditor);
  const hasNavigated = useRef(false);

  useEffect(() => {
    if (!isEditor) document.title = 'Reveal — Same suspense. Shared discovery.';
    const handleNavigation = () => {
      const nextIsEditor = window.location.hash === '#/review';
      if (nextIsEditor !== isEditor) {
        hasNavigated.current = true;
        if (nextIsEditor) setHasOpenedEditor(true);
        setIsEditor(nextIsEditor);
        window.scrollTo(0, 0);
      }
    };
    window.addEventListener('hashchange', handleNavigation);
    return () => window.removeEventListener('hashchange', handleNavigation);
  }, [isEditor]);

  return (
    <>
      {!isEditor && <LandingPage focusOnMount={hasNavigated.current} />}
      <div hidden={!isEditor}>
        {hasOpenedEditor && <EditorApp isActive={isEditor} />}
      </div>
    </>
  );
};

const EditorApp: React.FC<{ isActive: boolean }> = ({ isActive }) => {
  const [currentView, setCurrentView] = useState<'upload' | 'workspace'>('upload');
  const [currentReview, setCurrentReview] = useState<Review | null>(null);
  const [recentReviews, setRecentReviews] = useState<ReviewSummary[]>([]);
  const [isLoadingReviews, setIsLoadingReviews] = useState(true);
  const recentRequest = useRef(0);
  const [isAccessibleView, setIsAccessibleView] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const operationInFlight = useRef(false);
  const mainRef = useRef<HTMLElement>(null);

  const beginOperation = () => {
    if (operationInFlight.current) return false;
    operationInFlight.current = true;
    setError(null);
    setIsLoading(true);
    return true;
  };
  const endOperation = () => {
    operationInFlight.current = false;
    setIsLoading(false);
  };

  useEffect(() => {
    if (isActive) {
      document.title = currentView === 'workspace' && currentReview
        ? `${currentReview.title} — Reveal` : 'New review — Reveal';
      mainRef.current?.focus({ preventScroll: true });
      window.scrollTo({ top: 0, behavior: 'instant' });
    } else mainRef.current?.querySelector('video')?.pause();
  }, [isActive, currentView, currentReview?.id]);

  const loadRecentReviews = async () => {
    const request = ++recentRequest.current;
    setIsLoadingReviews(true);
    try {
      const summaries = await fetchReviews();
      if (request === recentRequest.current) setRecentReviews(summaries);
    } catch (e) {
      if (request === recentRequest.current) setError('Could not load recent reviews. Check your connection and refresh the page.');
    } finally {
      if (request === recentRequest.current) setIsLoadingReviews(false);
    }
  };

  useEffect(() => {
    loadRecentReviews();
  }, []);

  const handleUpload = async (
    title: string,
    videoFile: File,
    srtFile: File,
    intentNotes: string
  ) => {
    if (!beginOperation()) return;
    try {
      const review = await createReview(title, videoFile, srtFile, intentNotes);
      // Automatically trigger analysis after upload
      const analyzedReview = await triggerAnalysis(review.id);
      setCurrentReview(analyzedReview);
      setCurrentView('workspace');
      loadRecentReviews();
    } catch (e: any) {
      setError(`Upload failed: ${e.message}`);
    } finally {
      endOperation();
    }
  };

  const handleLoadSample = async () => {
    if (!beginOperation()) return;
    try {
      const review = await createSampleReview();
      setCurrentReview(review);
      setCurrentView('workspace');
      loadRecentReviews();
    } catch (e: any) {
      setError(`Failed to load sample: ${e.message}`);
    } finally {
      endOperation();
    }
  };

  const handleLoadExample = async () => {
    if (!beginOperation()) return;
    try {
      const review = await createRecordedExample();
      setCurrentReview(review);
      setCurrentView('workspace');
      loadRecentReviews();
    } catch (e: any) {
      setError(`Could not open the example: ${e.message}`);
    } finally {
      endOperation();
    }
  };

  const handleSelectReview = async (reviewId: string) => {
    if (!beginOperation()) return;
    try {
      const review = await fetchReviewDetail(reviewId);
      setCurrentReview(review);
      setCurrentView('workspace');
    } catch (e: any) {
      setError(`Failed to load review: ${e.message}`);
    } finally {
      endOperation();
    }
  };

  const handleUpdateDecision = async (
    findingId: string,
    status?: DecisionStatus,
    editedProposal?: string
  ) => {
    if (!currentReview) return;
    try {
      const updatedFinding = await updateFinding(
        currentReview.id,
        findingId,
        status,
        editedProposal
      );

      setCurrentReview((prev) => {
        if (!prev) return null;
        return {
          ...prev,
          findings: prev.findings.map((f) =>
            f.id === findingId ? updatedFinding : f
          ),
        };
      });
      loadRecentReviews();
    } catch (e: any) {
      setError(`Failed to update decision: ${e.message}`);
    }
  };

  const handleReanalyze = async (reviewId: string) => {
    if (!beginOperation()) return;
    try {
      const reanalyzed = await triggerAnalysis(reviewId);
      setCurrentReview(reanalyzed);
      loadRecentReviews();
    } catch (e: any) {
      setError(`Re-analysis failed: ${e.message}`);
    } finally {
      endOperation();
    }
  };

  const handleDeleteReview = async (reviewId: string) => {
    try {
      await deleteReview(reviewId);
      setCurrentReview(null);
      setCurrentView('upload');
      loadRecentReviews();
    } catch (e: any) {
      setError(`Failed to delete review: ${e.message}`);
    }
  };

  return (
    <div className="app-container">
      <a className="skip-link" href="#reveal-editor-main" onClick={(event) => {
        event.preventDefault();
        mainRef.current?.focus({ preventScroll: true });
        window.scrollTo({ top: 0, behavior: 'instant' });
      }}>Skip to review content</a>
      <Header
        currentView={currentView}
        title={currentReview?.title}
        isAccessibleView={isAccessibleView}
        onToggleAccessibleView={() => setIsAccessibleView(!isAccessibleView)}
        onNewReview={() => {
          setCurrentView('upload');
          setCurrentReview(null);
        }}
        onLoadSample={handleLoadExample}
        isBusy={isLoading}
        onHome={() => { window.location.hash = ''; }}
      />

      <main id="reveal-editor-main" className="main-content" ref={mainRef} tabIndex={-1}>
        {error && <div role="alert" className="public-demo-notice">{error}</div>}
        {isLoading && <p role="status">Working on your review. Please wait before starting another request.</p>}
        {currentView === 'upload' ? (
          <UploadView
            onUpload={handleUpload}
            onLoadSample={handleLoadSample}
            onLoadExample={handleLoadExample}
            onSelectReview={handleSelectReview}
            recentReviews={recentReviews}
            isSubmitting={isLoading}
            isLoadingReviews={isLoadingReviews}
          />
        ) : currentReview ? (
          <ReviewWorkspace
            review={currentReview}
            isAccessibleView={isAccessibleView}
            onUpdateDecision={handleUpdateDecision}
            onReanalyze={handleReanalyze}
            onDeleteReview={handleDeleteReview}
            isAnalyzing={isLoading}
          />
        ) : null}
      </main>
    </div>
  );
};
