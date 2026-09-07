import { Review, ReviewSummary, Finding, DecisionStatus } from './types';

const API_BASE = '/api/reviews';

async function requireSuccess(res: Response, fallback: string): Promise<void> {
  if (res.ok) return;
  const body = await res.json().catch(() => null);
  const detail = body?.detail;
  const message = typeof detail === 'string' ? detail
    : Array.isArray(detail) ? detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join('; ')
    : '';
  throw new Error(message || fallback);
}

export async function fetchReviews(): Promise<ReviewSummary[]> {
  const res = await fetch(API_BASE);
  await requireSuccess(res, 'Failed to fetch reviews');
  return res.json();
}

export async function fetchReviewDetail(reviewId: string): Promise<Review> {
  const res = await fetch(`${API_BASE}/${reviewId}`);
  await requireSuccess(res, 'Failed to fetch review detail');
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
  await requireSuccess(res, 'Failed to create sample review');
  return res.json();
}

export async function triggerAnalysis(reviewId: string): Promise<Review> {
  const res = await fetch(`${API_BASE}/${reviewId}/analyze`, {
    method: 'POST',
  });
  await requireSuccess(res, 'Failed to run analysis');
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

  await requireSuccess(res, 'Failed to update finding decision');
  return res.json();
}

export async function deleteReview(reviewId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/${reviewId}`, {
    method: 'DELETE',
  });
  await requireSuccess(res, 'Failed to delete review');
}

export function getExportUrl(reviewId: string): string {
  return `${API_BASE}/${reviewId}/export`;
}

export function getVideoUrl(reviewId: string): string {
  return `${API_BASE}/${reviewId}/video`;
}
