import { Review, ReviewSummary, Finding, DecisionStatus } from './types';

const API_BASE = '/api/reviews';

export async function fetchReviews(): Promise<ReviewSummary[]> {
  const res = await fetch(API_BASE);
  if (!res.ok) throw new Error('Failed to fetch reviews');
  return res.json();
}

export async function fetchReviewDetail(reviewId: string): Promise<Review> {
  const res = await fetch(`${API_BASE}/${reviewId}`);
  if (!res.ok) throw new Error('Failed to fetch review detail');
  return res.json();
}

export async function createReview(
  title: string,
  videoFile: File,
  srtFile: File,
  intentNotes: string
): Promise<Review> {
  const formData = new FormData();
  formData.append('title', title);
  formData.append('video_file', videoFile);
  formData.append('srt_file', srtFile);
  formData.append('intent_notes', intentNotes);

  const res = await fetch(API_BASE, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: 'Failed to create review' }));
    throw new Error(errData.detail || 'Failed to create review');
  }

  return res.json();
}

export async function createSampleReview(): Promise<Review> {
  const res = await fetch(`${API_BASE}/sample`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to create sample review');
  return res.json();
}

export async function triggerAnalysis(reviewId: string): Promise<Review> {
  const res = await fetch(`${API_BASE}/${reviewId}/analyze`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to run analysis');
  return res.json();
}

export async function updateFinding(
  reviewId: string,
  findingId: string,
  status?: DecisionStatus,
  editedProposal?: string
): Promise<Finding> {
  const payload: { status?: DecisionStatus; edited_proposal?: string } = {};
  if (status) payload.status = status;
  if (editedProposal !== undefined) payload.edited_proposal = editedProposal;

  const res = await fetch(`${API_BASE}/${reviewId}/findings/${findingId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) throw new Error('Failed to update finding decision');
  return res.json();
}

export async function deleteReview(reviewId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/${reviewId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete review');
}

export function getExportUrl(reviewId: string): string {
  return `${API_BASE}/${reviewId}/export`;
}

export function getVideoUrl(reviewId: string): string {
  return `${API_BASE}/${reviewId}/video`;
}
