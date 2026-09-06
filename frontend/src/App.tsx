import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { UploadView } from './components/UploadView';
import { ReviewWorkspace } from './components/ReviewWorkspace';
import { Review, ReviewSummary, DecisionStatus } from './types';
import {
  fetchReviews,
  fetchReviewDetail,
  createReview,
  createSampleReview,
  triggerAnalysis,
  updateFinding,
  deleteReview,
} from './api';

export const App: React.FC = () => {
  const [currentView, setCurrentView] = useState<'upload' | 'workspace'>('upload');
  const [currentReview, setCurrentReview] = useState<Review | null>(null);
  const [recentReviews, setRecentReviews] = useState<ReviewSummary[]>([]);
  const [isAccessibleView, setIsAccessibleView] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const loadRecentReviews = async () => {
    try {
      const summaries = await fetchReviews();
      setRecentReviews(summaries);
    } catch (e) {
      console.error('Failed to load recent reviews', e);
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
    setIsLoading(true);
    try {
      const review = await createReview(title, videoFile, srtFile, intentNotes);
      // Automatically trigger analysis after upload
      const analyzedReview = await triggerAnalysis(review.id);
      setCurrentReview(analyzedReview);
      setCurrentView('workspace');
      loadRecentReviews();
    } catch (e: any) {
      alert(`Upload failed: ${e.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleLoadSample = async () => {
    setIsLoading(true);
    try {
      const review = await createSampleReview();
      setCurrentReview(review);
      setCurrentView('workspace');
      loadRecentReviews();
    } catch (e: any) {
      alert(`Failed to load sample: ${e.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectReview = async (reviewId: string) => {
    setIsLoading(true);
    try {
      const review = await fetchReviewDetail(reviewId);
      setCurrentReview(review);
      setCurrentView('workspace');
    } catch (e: any) {
      alert(`Failed to load review: ${e.message}`);
    } finally {
      setIsLoading(false);
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
      alert(`Failed to update decision: ${e.message}`);
    }
  };

  const handleReanalyze = async (reviewId: string) => {
    setIsLoading(true);
    try {
      const reanalyzed = await triggerAnalysis(reviewId);
      setCurrentReview(reanalyzed);
      loadRecentReviews();
    } catch (e: any) {
      alert(`Re-analysis failed: ${e.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteReview = async (reviewId: string) => {
    try {
      await deleteReview(reviewId);
      setCurrentReview(null);
      setCurrentView('upload');
      loadRecentReviews();
    } catch (e: any) {
      alert(`Failed to delete review: ${e.message}`);
    }
  };

  return (
    <div className="app-container">
      <Header
        currentView={currentView}
        title={currentReview?.title}
        isAccessibleView={isAccessibleView}
        onToggleAccessibleView={() => setIsAccessibleView(!isAccessibleView)}
        onNewReview={() => {
          setCurrentView('upload');
          setCurrentReview(null);
        }}
        onLoadSample={handleLoadSample}
      />

      <main className="main-content">
        {currentView === 'upload' ? (
          <UploadView
            onUpload={handleUpload}
            onLoadSample={handleLoadSample}
            onSelectReview={handleSelectReview}
            recentReviews={recentReviews}
            isSubmitting={isLoading}
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
