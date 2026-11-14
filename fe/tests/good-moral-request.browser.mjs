// Synthetic self-service F6 scenarios. Every API response is intercepted locally.
import assert from 'node:assert/strict';
import { createBrowserHarness } from './support/browser-harness.mjs';
import { certificate, requestId } from './support/good-moral-print-fixtures.mjs';

const { check, screenshot, finish } = await createBrowserHarness('good-moral-student');
const requestPath = '/portal/good-moral/request';
const empty = { items: [], page: 1, page_size: 20, has_next: false };

function student(lifecycle) {
  return {
    id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    first_name: 'Synthetic', last_name: 'Alumnus', middle_name: '',
    email: 'synthetic.alumnus@example.test', role: 'STUDENT',
    student_lifecycle_status: lifecycle, designations: [], institutional_id: 'SYNTHETIC-UCN-1',
    capabilities: ['good_moral.request_self', 'good_moral.view_self', 'exit_interviews.view_self'],
  };
}

function fixture({ lifecycle, f4Status }) {
  const account = student(lifecycle);
  const state = { posts: [] };
  const item = certificate('REQUESTED', 'GRADUATE');
  return {
    state,
    options: {
      overrides: {
        '/api/v1/auth/session': { user: account, session: { id: 'synthetic', expires_at: '2099-01-01T00:00:00Z', is_current: true } },
        '/api/v1/good-moral/requests': empty,
      },
      handler: async ({ pathname, method, request, reply }) => {
        if (pathname === '/api/v1/good-moral/me/academic-context') {
          await reply({ status: f4Status, academic_classification: f4Status === 'ELIGIBLE' ? 'BACHELORS' : 'MASTERS', year_level: f4Status === 'ELIGIBLE' ? 4 : null });
          return true;
        }
        if (pathname === '/api/v1/good-moral/degree-options') {
          await reply({ items: ['Bachelor of Science in Information Systems'] });
          return true;
        }
        if (pathname === `/api/v1/good-moral/me/${requestId}`) {
          await reply(item);
          return true;
        }
        if (pathname === '/api/v1/exit-interviews/me/status') {
          await reply({ graduation_good_moral_blocked: false });
          return true;
        }
        if (pathname === '/api/v1/good-moral/me/requests/graduate' && method === 'POST') {
          state.posts.push(JSON.parse(request.postData()));
          await reply(item, 201);
          return true;
        }
        return false;
      },
    },
  };
}

{
  const f = fixture({ lifecycle: 'CURRENT', f4Status: 'POSTGRADUATE_PROGRAM' });
  await check('current Student re-enrolled in local postgraduate Program retains F6 request access', requestPath, f.options, async page => {
    // Postgraduate study rules out the current Student certificate: the graduate form opens directly.
    await page.getByRole('heading', { name: "Good Moral Certificate for UCN Bachelor's graduates", exact: true }).waitFor();
    assert.equal(await page.getByRole('heading', { name: 'Good Moral Certificate for current Students', exact: true }).count(), 0);
    assert.equal(await page.getByRole('button', { name: /current Student certificate|completed UCN Bachelor/ }).count(), 0);
    assert.equal(await page.locator("main h1").count(), 1);
    assert.equal(await page.getByRole("link", { name: "Back to Good Moral", exact: true }).count(), 1);
    await page.getByLabel('Degree').fill('Bachelor of Science in Information Systems');
    await page.getByLabel('Graduation date').fill('2020-06-30');
    await screenshot(page, 'student-current-local-postgraduate-f6-request');
    await page.getByRole('button', { name: 'Submit request', exact: true }).click();
    await page.waitForURL(`**/portal/good-moral/${requestId}`);
    assert.deepEqual(f.state.posts, [{ degree: 'Bachelor of Science in Information Systems', major: '', graduation_date: '2020-06-30' }]);
  });
}

{
  const f = fixture({ lifecycle: 'FORMER', f4Status: 'NOT_CURRENT' });
  await check('former UCN alumnus pursuing postgraduate study elsewhere retains F6 self-service', requestPath, f.options, async page => {
    await page.getByRole('heading', { name: "Good Moral Certificate for UCN Bachelor's graduates", exact: true }).waitFor();
    await page.getByText(/COMPASS doesn't verify your degree or graduation date/i).waitFor();
    await page.getByLabel('Degree').fill('Bachelor of Science in Information Systems (UCN)');
    await page.getByLabel('Graduation date').fill('2020-06-30');
    await screenshot(page, 'student-former-external-postgraduate-f6-request');
    assert.equal(f.state.posts.length, 0);
  });
}

{
  const f = fixture({ lifecycle: 'CURRENT', f4Status: 'ELIGIBLE' });
  await check('eligible current Student sees the current form directly and can switch to the graduate form', requestPath, f.options, async page => {
    await page.getByRole('heading', { name: 'Good Moral Certificate for current Students', exact: true }).waitFor();
    assert.equal(await page.getByText('Certificate type', { exact: true }).count(), 0, 'No certificate-type step');
    await page.getByRole('button', { name: "I need it for a completed UCN Bachelor's degree", exact: true }).click();
    await page.getByRole('heading', { name: "Good Moral Certificate for UCN Bachelor's graduates", exact: true }).waitFor();
    assert.equal(await page.getByRole('heading', { name: 'Good Moral Certificate for current Students', exact: true }).count(), 0);
    await page.getByRole('button', { name: 'Request the current Student certificate instead', exact: true }).click();
    await page.getByRole('heading', { name: 'Good Moral Certificate for current Students', exact: true }).waitFor();
    await screenshot(page, 'student-current-eligible-direct-form');
  });
}

{
  const f = fixture({ lifecycle: 'CURRENT', f4Status: 'INVENTORY_REQUIRED' });
  await check('current Student without Inventory sees the reason and no form until they choose the graduate certificate', requestPath, f.options, async page => {
    await page.getByText(/Submit this year's Individual Inventory/).waitFor();
    assert.equal(await page.locator('main form').count(), 0);
    await page.getByRole('button', { name: "I need it for a completed UCN Bachelor's degree", exact: true }).click();
    await page.getByRole('heading', { name: "Good Moral Certificate for UCN Bachelor's graduates", exact: true }).waitFor();
    assert.equal(await page.getByRole('button', { name: 'Request the current Student certificate instead', exact: true }).count(), 0, 'No switch back to an unavailable certificate');
  });
}

await finish();
