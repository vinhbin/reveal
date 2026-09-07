import { test, expect, Page } from '@playwright/test';

// Fictional browser fixtures; no model calls or public reviews are used.
const timestamp = '2026-09-07T05:00:00Z';
function fixture(status = 'completed') {
  const cue = { id: 'cue-1', review_id: 'example', index: 1, start_time: '00:00:05,000', end_time: '00:00:09,000', start_seconds: 5, end_seconds: 9, text: 'Alpha meets Beta.' };
  return {
    id: 'example', title: 'Recorded test example', video_filename: 'sample.mp4', srt_filename: 'sample.srt',
    status, error_message: status === 'failed' ? '503 UNAVAILABLE: provider busy' : '',
    model_used: status === 'completed' ? 'google-adk/agent-platform/test-model' : '',
    analysis_source: status === 'completed' ? 'recorded' : null, recorded_at: timestamp,
    created_at: timestamp, updated_at: timestamp, cues: [cue],
    findings: status === 'completed' ? ['Alpha', 'Beta'].map((name, i) => ({
      id: `finding-${i}`, review_id: 'example', cue_id: cue.id, cue_index: 1, candidate_name: name,
      issue_description: `${name} may be introduced too early.`, proposed_text: i ? 'Alpha meets a clerk.' : 'A visitor meets Beta.',
      edited_proposal: '', evidence_origin: 'model_inference', interval_start: 5, interval_end: 30,
      uncertainty: 'medium', status: 'unreviewed', created_at: timestamp, updated_at: timestamp,
    })) : [],
  };
}

async function mockApi(page: Page, status = 'completed', delayList = false, errorMessage?: string) {
  const review = fixture(status);
  if (errorMessage) review.error_message = errorMessage;
  let releaseList = () => {};
  const gate = delayList ? new Promise<void>((resolve) => { releaseList = resolve; }) : Promise.resolve();
  const calls: string[] = [];
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const method = route.request().method();
    calls.push(`${method} ${path}`);
    if (path === '/api/reviews') {
      await gate;
      return route.fulfill({ json: [{ ...review, cue_count: 1, finding_count: review.findings.length, unreviewed_count: review.findings.length }] });
    }
    if (path === '/api/reviews/example' || path === '/api/reviews/example-copy') return route.fulfill({ json: review });
    if (path.endsWith('/video')) return route.fulfill({ status: 404, json: { detail: 'Video file not found' } });
    if (path.includes('/findings/') && method === 'PATCH') {
      const finding = review.findings.find((item) => item.id === path.split('/').pop());
      Object.assign(finding!, route.request().postDataJSON());
      return route.fulfill({ json: finding });
    }
    if (path.endsWith('/export')) return route.fulfill({ body: '1\n00:00:05,000 --> 00:00:09,000\nA visitor meets Beta.\n', contentType: 'application/x-subrip', headers: { 'Content-Disposition': 'attachment; filename="example.srt"' } });
    // A test must never reach Gemini or the real backend through an unhandled route.
    return route.fulfill({ status: 500, json: { detail: `Unexpected test request: ${method} ${path}` } });
  });
  return { calls, releaseList };
}

async function openExample(page: Page) {
  await page.goto('/#/review');
  await page.getByRole('button', { name: 'Open saved Gemini example', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Recorded test example', exact: true })).toBeVisible();
}

test('saved example opens without analysis and preserves recorded provenance after editing', async ({ page }) => {
  const { calls } = await mockApi(page);
  await openExample(page);
  await expect(page.getByRole('note').filter({ hasText: 'Recorded Gemini example' })).toBeVisible();
  await page.getByRole('button', { name: 'Select finding #1 for Alpha, status unreviewed', exact: true }).click();
  await page.getByRole('textbox', { name: 'Proposed wording editor' }).fill('A visitor meets Beta.');
  await page.getByRole('button', { name: 'Accept Revision', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Select finding #1 for Alpha, status accepted', exact: true })).toBeVisible();
  await expect(page.getByRole('note').filter({ hasText: 'Recorded Gemini example' })).toBeVisible();
  expect(calls.some((call) => call.endsWith('/analyze') || call.endsWith('/sample'))).toBe(false);
});

test('Space and Enter activate the selected secondary finding independently', async ({ page }) => {
  await mockApi(page);
  await openExample(page);
  const beta = page.getByRole('button', { name: 'Select finding #1 for Beta, status unreviewed', exact: true });
  await beta.focus();
  await beta.press('Space');
  await expect(page.getByRole('textbox', { name: 'Proposed wording editor' })).toHaveValue('Alpha meets a clerk.');
  await page.getByRole('button', { name: 'Select finding #1 for Alpha, status unreviewed', exact: true }).click();
  await beta.focus();
  await beta.press('Enter');
  await expect(page.getByRole('textbox', { name: 'Proposed wording editor' })).toHaveValue('Alpha meets a clerk.');
  await expect(page.getByRole('button', { name: 'all', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'accepted', exact: true }).click();
  await expect(page.getByRole('button', { name: 'accepted', exact: true })).toHaveAttribute('aria-pressed', 'true');
});

test('recent reviews announce loading without a premature empty state', async ({ page }) => {
  const { releaseList } = await mockApi(page, 'completed', true);
  await page.goto('/#/review');
  await expect(page.getByRole('status')).toHaveText('Loading recent reviews…');
  await expect(page.getByText(/No recent review sessions/)).toHaveCount(0);
  releaseList();
  await expect(page.getByRole('button', { name: /Open review session/ })).toBeVisible();
});

test('mobile navigation resets scroll, keeps the banner visible and labels failed cues honestly', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await mockApi(page, 'failed');
  await page.goto('/');
  await page.getByRole('link', { name: 'Open Reveal', exact: true }).first().click();
  await expect(page).toHaveTitle('New review — Reveal');
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
  await page.getByRole('checkbox', { name: /Include failed reviews/ }).check();
  await page.getByRole('button', { name: /Open review session/ }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'Analysis failed' })).toBeInViewport();
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
  await expect(page.getByRole('button', { name: /Retry analysis/i })).toHaveCount(1);
  await page.getByRole('button', { name: 'Text review', exact: true }).click();
  await expect(page.getByText(/^Not analyzed — no completed result yet$/)).toBeVisible();
  await expect(page.getByText('Clean Cue', { exact: true })).toHaveCount(0);
  await expect(page.locator('main h1')).toHaveCount(1);
});

test('mobile text review keeps editors and decision controls within the viewport', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await mockApi(page);
  await openExample(page);
  await page.getByRole('button', { name: 'Text review', exact: true }).click();
  const controls = page.locator('.accessible-review textarea, .accessible-review button');
  expect(await controls.count()).toBeGreaterThan(4);
  for (const item of await controls.all()) {
    const box = await item.boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(376);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
});

test('missing video shows an actionable message and original export has an honest label', async ({ page }) => {
  await mockApi(page);
  await openExample(page);
  await expect(page.getByText(/Video unavailable/i)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Export original SRT', exact: true })).toBeVisible();
});

test('a missing source video is not misreported as Gemini unavailability', async ({ page }) => {
  await mockApi(page, 'failed', false, "Analysis failed: This review's video is unavailable. Upload the original clip again.");
  await openExample(page);
  await expect(page.getByRole('alert').filter({ hasText: 'Analysis failed' })).toContainText('The video for this review is missing.');
  await expect(page.getByText('Gemini is temporarily unavailable.', { exact: false })).toHaveCount(0);
});

test('editor skip link preserves the editor route and home preserves a draft', async ({ page }) => {
  await mockApi(page);
  await openExample(page);
  await page.getByRole('button', { name: 'Select finding #1 for Alpha, status unreviewed', exact: true }).click();
  await page.getByRole('textbox', { name: 'Proposed wording editor' }).fill('Unsaved editorial wording.');
  await page.getByRole('button', { name: 'Reveal home', exact: true }).click();
  await expect(page).toHaveTitle('Reveal — Same suspense. Shared discovery.');
  await page.getByRole('link', { name: 'Open Reveal', exact: true }).first().click();
  await expect(page.getByRole('textbox', { name: 'Proposed wording editor' })).toHaveValue('Unsaved editorial wording.');
  const skip = page.getByRole('link', { name: 'Skip to review content', exact: true });
  await skip.focus();
  await skip.press('Enter');
  await expect(page).toHaveURL(/#\/review$/);
  await expect(page.locator('#reveal-editor-main')).toBeFocused();
});
