export function analysisErrorMessage(message = ''): string {
  if (/429|resource_exhausted|quota exceeded/i.test(message)) {
    return 'Gemini quota is exhausted. Existing review data is still available. The app owner needs to check Gemini quota or billing before retrying.';
  }
  if (/503|unavailable|overloaded/i.test(message)) {
    return 'Gemini is temporarily unavailable. Existing review data is still available; try analysis again later.';
  }
  if (/timed?\s*out|timeout/i.test(message)) {
    return 'Analysis timed out. Existing review data is still available; try a shorter clip or retry later.';
  }
  return message || 'Analysis did not complete. Open the review details or retry later.';
}
