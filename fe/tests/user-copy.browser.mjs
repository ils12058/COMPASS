// All requests use synthetic fixtures against local Next. No live records or notifications.
import assert from 'node:assert/strict';
import { createBrowserHarness } from './support/browser-harness.mjs';
import { worlds, empty, student, year } from './support/ux-hardening-fixtures.mjs';
import { user, service, appointment } from './support/ui-hierarchy-fixtures.mjs';
const bookingPosts = [];
const engine = process.env.COMPASS_UI_BROWSER ?? 'chromium';
const { check, shown, hidden, noHorizontalOverflow, screenshot, finish } = await createBrowserHarness(`user-copy-${engine}`);
const diagnostic = 'PRIVATE-DIAGNOSTIC-SENTINEL capability.secret tenant=hidden';
const error = (code, status = 422) => ({ reply }) => reply({ error: { code, message: diagnostic } }, status);
const session = (account) => ({ user: account, session: { id: 'copy-fixture', expires_at: '2099-01-01T00:00:00Z', is_current: true } });
const staff = { ...user(), capabilities: [...user().capabilities, 'referrals.view', 'referrals.manage', 'routine_interviews.view_assigned', 'routine_interviews.manage_assigned', 'inventory.view'] };
const currentStudent = { ...user('STUDENT'), capabilities: [...user('STUDENT').capabilities, 'appointments.manage_self', 'inventory.view_self', 'inventory.manage_self', 'exit_interviews.view_self', 'exit_interviews.manage_self', 'good_moral.view_self', 'good_moral.request_self', 'feedback.submit_customer_feedback', 'feedback.submit_csm'] };
async function safe(page) { assert.ok(!(await page.locator('body').innerText()).includes(diagnostic)); await noHorizontalOverflow(page); }
async function oneAlert(page, text) { await shown(page.getByRole('alert').filter({ hasText: text })); assert.equal(await page.getByRole('alert').filter({ hasText: text }).count(), 1); await safe(page); }
const inventoryRevision = { id: 'revision', family_key: 'individual_inventory', internal_schema_version: 1, official_code: 'TEST-INV', official_revision: '1' };
const inventory = { id: 'inventory', academic_year: year, status: 'DRAFT', program: null, form_revision: inventoryRevision, submitted_at: null, first_submitted_at: null, last_submitted_at: null, correction_pending: false, latest_correction: null, full_name: 'Synthetic Student' };
const inventoryStatus = { academic_year: year, status: 'DRAFT', form_revision: inventoryRevision, correction_pending: false, latest_correction: null, submitted_at: null, first_submitted_at: null, last_submitted_at: null };
for (const width of [320, 1440]) {
    const viewport = { width, height: 1000 };
    for (const [name, route, overrides, text] of [
        ['referral-validation', '/portal/referrals', { '/api/v1/referrals': error('invalid_referral_request') }, 'Some referral details need attention. Review them and try again.'],
        ['call-slip-validation', '/portal/call-slips', { '/api/v1/call-slips': error('invalid_call_slip_request') }, 'Some call slip details need attention. Review them and try again.'],
        ['appointment-validation', '/portal/appointments/manage', { '/api/v1/appointments': error('invalid_appointment_request') }, 'Some appointment details need attention. Review them and try again.'],
        ['counseling-validation', '/portal/counseling', { '/api/v1/counseling/me/encounters': error('counseling_invalid_request') }, 'Some counseling details need attention. Review them and try again.'],
        ['hidden-referral', '/portal/referrals/long', { '/api/v1/referrals/long': error('referral_not_permitted', 404) }, 'This referral is unavailable.'],
        ['hidden-call-slip', '/portal/call-slips/slip-density-test', { '/api/v1/call-slips/slip-density-test': error('call_slip_not_permitted', 404) }, 'This call slip is unavailable.'],
    ])
        await check(`${name}-${width}`, route, { viewport, overrides: { ...worlds, '/api/v1/auth/session': session(staff), ...overrides } }, async (page) => { await oneAlert(page, text); await shown(page.getByRole('button', { name: 'Retry', exact: true })); });
    await check(`exit-access-conflict-${width}`, '/portal/exit-interviews', { viewport, overrides: { '/api/v1/auth/session': session(currentStudent), '/api/v1/exit-interviews/me/status': error('exit_interview_opportunity_conflict', 409), '/api/v1/exit-interviews/me': empty } }, async (page) => {
        await oneAlert(page, "This Exit Interview access action can't be completed with the current details.");
        await shown(page.getByRole('button', { name: 'Retry', exact: true }));
        await hidden(page.getByRole('button', { name: 'Start Exit Interview', exact: true }));
    });
    await check(`retention-conflict-${width}`, '/portal/privacy/retention/rules', { viewport, overrides: { '/api/v1/auth/session': session({ ...user('IT_ADMIN'), capabilities: ['privacy_governance.view', 'privacy_governance.manage', 'privacy_governance.retention.view', 'privacy_governance.retention.manage'] }), '/api/v1/privacy/retention/rules': error('retention_state_changed', 409) } }, async (page) => {
        await oneAlert(page, "This retention action can't be completed with the current details.");
        await shown(page.getByRole('button', { name: 'Retry', exact: true }));
    });
    await check(`referral-create-rejection-${width}`, '/portal/referrals/new', { viewport, overrides: { '/api/v1/auth/session': session(staff), '/api/v1/referrals/students': { ...empty, items: [student] }, 'POST /api/v1/referrals': error('invalid_referral_request') } }, async (page, { requests }) => {
        await page.getByRole('radio', { name: /Maria Santos/ }).check();
        await page.getByLabel('Course / Year / Block', { exact: true }).fill('BSIT / 4 / A');
        await page.getByLabel('Reason for referral', { exact: true }).fill('Synthetic source wording');
        await page.getByLabel('Referrer name', { exact: true }).fill('Synthetic Referrer');
        await page.getByLabel('Date referred', { exact: true }).fill('2026-10-01');
        const submit = page.getByRole('button', { name: 'Record referral', exact: true });
        await submit.focus();
        await page.keyboard.press('Enter');
        await oneAlert(page, 'Some referral details need attention.');
        assert.equal(await page.getByLabel('Reason for referral', { exact: true }).inputValue(), 'Synthetic source wording');
        assert.equal(requests.filter(r => r.method === 'POST' && r.pathname === '/api/v1/referrals').length, 1);
    });
    await check(`call-slip-issue-rejection-${width}`, '/portal/call-slips/new', { viewport, overrides: { '/api/v1/auth/session': session(staff), '/api/v1/call-slips/students': { ...empty, items: [student] }, 'POST /api/v1/call-slips': error('invalid_call_slip_request') } }, async (page, { requests }) => {
        await page.getByRole('radio', { name: /Maria Santos/ }).check();
        await page.getByLabel('Course / Year', { exact: true }).fill('BSIT / 4');
        await page.getByLabel('Report date and time', { exact: true }).fill('2026-10-01T09:00');
        const submit = page.getByRole('button', { name: 'Review issuance', exact: true });
        await submit.focus();
        await page.keyboard.press('Enter');
        const dialog = page.getByRole('alertdialog');
        await shown(dialog);
        assert.match(await dialog.innerText(), /notification option|no new issuance notification/);
        await dialog.getByRole('button', { name: 'Issue Call Slip', exact: true }).click();
        await oneAlert(page, 'Some call slip details need attention.');
        await shown(dialog);
        await dialog.getByRole('button', { name: 'Review details', exact: true }).click();
        await hidden(dialog);
        assert.equal(await page.getByLabel('Course / Year', { exact: true }).inputValue(), 'BSIT / 4');
        assert.equal(requests.filter(r => r.method === 'POST' && r.pathname === '/api/v1/call-slips').length, 1);
    });
    await check(`referral-action-consequences-${width}`, '/portal/referrals/long', { viewport, overrides: { ...worlds, '/api/v1/auth/session': session(staff), 'POST /api/v1/referrals/long/actions': error('invalid_referral_request') } }, async (page, { requests }) => {
        await shown(page.getByText('Record actions already taken. Adding an entry here does not place a call, send a letter, or notify the student.', { exact: true }));
        await page.getByRole('button', { name: 'Record Parent / Guardian call', exact: true }).click();
        await page.getByLabel('Action occurred', { exact: true }).fill('2026-10-08T09:00');
        await page.getByLabel('Remarks (optional)', { exact: true }).fill('Synthetic historical action');
        await page.getByRole('button', { name: 'Review action', exact: true }).click();
        const dialog = page.getByRole('alertdialog');
        await shown(dialog);
        assert.match(await dialog.innerText(), /This action cannot be edited or deleted after it is recorded/);
        await dialog.getByRole('button', { name: 'Record Parent / Guardian call', exact: true }).click();
        await oneAlert(page, 'Some referral details need attention.');
        assert.equal(requests.filter(r => r.method === 'POST' && r.pathname === '/api/v1/referrals/long/actions').length, 1);
        assert.equal(await page.getByLabel('Remarks (optional)', { exact: true }).inputValue(), 'Synthetic historical action');
    });
    await check(`routine-form-blocker-${width}`, '/portal/routine-interviews', { viewport, overrides: { '/api/v1/auth/session': session(staff), '/api/v1/routine-interviews': { ...empty, filter_options: { form_revisions: [] } }, '/api/v1/routine-interviews/direct/options': error('routine_interview_form_revision_unsupported', 409) } }, async (page) => {
        const opener = page.getByRole('button', { name: 'Start Routine Interview', exact: true });
        await opener.focus();
        await page.keyboard.press('Enter');
        const dialog = page.getByRole('dialog');
        await shown(dialog);
        await oneAlert(page, "The current Routine Interview form can't be used to start a new interview.");
        await dialog.getByRole('button', { name: 'Close dialog', exact: true }).click();
        await hidden(dialog);
        assert.equal(await opener.evaluate(el => el === document.activeElement), true);
    });
    await check(`inventory-conflict-retains-answers-${width}`, '/portal/inventory/current', { viewport, overrides: { '/api/v1/auth/session': session(currentStudent), '/api/v1/inventory/me/current': inventory, '/api/v1/inventory/me/status': inventoryStatus, '/api/v1/inventory/me/history': empty, 'PUT /api/v1/inventory/me/current': error('inventory_conflict', 409) } }, async (page) => {
        const field = page.getByLabel('Full name', { exact: true });
        await field.fill('Unsaved Synthetic Name');
        await page.getByRole('button', { name: 'Save progress', exact: true }).click();
        await oneAlert(page, 'This action cannot be completed with the current inventory details.');
        await shown(page.getByText(/Your answers are kept on this page/));
        assert.equal(await field.inputValue(), 'Unsaved Synthetic Name');
    });
    await check(`good-moral-unconfirmed-${width}`, '/portal/good-moral/request', { viewport, overrides: { '/api/v1/auth/session': session(currentStudent), '/api/v1/exit-interviews/me/status': { graduation_good_moral_blocked: false }, 'POST /api/v1/good-moral/me/requests/current-student': error('internal_error', 500) } }, async (page, { requests }) => {
        await page.getByLabel('Year level').fill('4');
        await page.getByLabel('Semester').fill('First semester');
        await page.getByRole('button', { name: 'Submit request', exact: true }).click();
        await oneAlert(page, 'The request result could not be confirmed.');
        await page.getByRole('button', { name: 'Retry same request', exact: true }).click();
        await oneAlert(page, 'The request result could not be confirmed.');
        const sent = requests.filter(r => r.method === 'POST' && r.pathname.includes('/good-moral/me/requests/'));
        assert.equal(sent.length, 2);
        assert.equal(sent[0].body, sent[1].body);
        await screenshot(page, `good-moral-unconfirmed-${width}`);
    });
    await check(`booking-server-error-same-intent-${width}`, '/portal/appointments/book', { viewport, overrides: { '/api/v1/auth/session': session(currentStudent), '/api/v1/appointments/booking/services': { ...empty, items: [service] }, '/api/v1/appointments/booking/counselors': { ...empty, items: [{ ...appointment.provider, is_default: true }] }, '/api/v1/appointments/booking/slots': { items: [{ starts_at: '2098-10-10T02:00:00Z', ends_at: '2098-10-10T03:00:00Z' }], timezone: 'Asia/Manila' } }, handler: async ({ pathname, method, request, reply }) => { if (pathname === '/api/v1/appointments' && method === 'POST') {
            bookingPosts.push({ body: request.postData(), key: request.headers()['idempotency-key'] });
            await reply({ error: { code: 'internal_error', message: diagnostic } }, 500);
            return true;
        } return false; } }, async (page) => {
        bookingPosts.length = 0;
        await page.getByRole('button', { name: /^Counseling/ }).click();
        await page.getByRole('radio', { name: 'In person', exact: true }).check();
        await page.getByLabel('Appointment date', { exact: true }).fill('2098-10-10');
        await page.getByRole('group', { name: 'Available appointment times' }).getByRole('button').first().click();
        await page.getByRole('button', { name: 'Book appointment', exact: true }).click();
        await oneAlert(page, 'The booking response could not be confirmed.');
        await page.getByRole('button', { name: 'Retry booking', exact: true }).click();
        await oneAlert(page, 'The booking response could not be confirmed.');
        assert.equal(bookingPosts.length, 2);
        assert.ok(bookingPosts[0].key);
        assert.deepEqual(bookingPosts[1], bookingPosts[0]);
        await screenshot(page, `booking-unconfirmed-${width}`);
    });
    const opportunity = '11111111-1111-4111-8111-111111111111';
    await check(`feedback-server-error-${width}`, `/portal/feedback/customer-feedback?opportunity=${opportunity}`, { viewport, overrides: { '/api/v1/auth/session': session(currentStudent), '/api/v1/me/profile': { full_name: 'Synthetic Student', current_address: '', permanent_address: '', contact_number: '' }, [`/api/v1/feedback/opportunities/${opportunity}`]: { id: opportunity, service_kind: 'COUNSELING', service_label: 'Counseling', customer_feedback_submitted: false, can_submit_customer_feedback: true, service_completed_at: '2026-10-01T00:00:00Z' }, 'POST /api/v1/feedback/customer-feedback': error('internal_error', 500) } }, async (page, { requests }) => {
        await shown(page.getByRole('heading', { name: 'Customer Feedback Form', exact: true }));
        const groups = await page.locator('input[type="radio"]').evaluateAll(els => [...new Set(els.map(el => el.name))]);
        for (const name of groups)
            await page.locator(`input[type="radio"][name="${name}"]`).first().check();
        await page.locator('#feedback-office-visits').fill('1');
        await page.locator('#feedback-transaction-duration').fill('10 minutes');
        await page.locator('#feedback-course-year').fill('BSIT / 4');
        await page.getByRole('button', { name: 'Review and submit', exact: true }).click();
        const dialog = page.getByRole('alertdialog');
        await shown(dialog);
        await dialog.getByRole('button', { name: 'Submit Customer Feedback', exact: true }).click();
        await oneAlert(page, 'The submission result could not be confirmed.');
        assert.equal(requests.filter(r => r.method === 'POST' && r.pathname === '/api/v1/feedback/customer-feedback').length, 1);
        assert.equal(await page.locator('#feedback-course-year').inputValue(), 'BSIT / 4');
        assert.match(await dialog.innerText(), /Check your feedback status/);
        await screenshot(page, `feedback-unconfirmed-${width}`);
    });
    await check(`csm-server-error-${width}`, `/portal/feedback/csm?opportunity=${opportunity}`, { viewport, overrides: { '/api/v1/auth/session': session(currentStudent), [`/api/v1/feedback/opportunities/${opportunity}`]: { id: opportunity, service_kind: 'COUNSELING', service_label: 'Counseling', csm_submitted: false, can_submit_csm: true, customer_feedback_submitted: false, can_submit_customer_feedback: true, service_completed_at: '2026-10-01T00:00:00Z' }, 'POST /api/v1/feedback/csm': error('internal_error', 500) } }, async (page, { requests }) => {
        await shown(page.getByRole('heading', { name: 'HELP US SERVE YOU BETTER!', exact: true }));
        const groups = await page.locator('input[type="radio"]').evaluateAll(els => [...new Set(els.map(el => el.name))]);
        for (const name of groups)
            await page.locator(`input[type="radio"][name="${name}"]`).first().check();
        await page.locator('#csm-age').fill('21');
        await page.locator('#csm-region').fill('Synthetic Region');
        await page.getByRole('button', { name: 'Review and submit', exact: true }).click();
        const dialog = page.getByRole('alertdialog');
        await shown(dialog);
        assert.match(await dialog.innerText(), /will not be able to edit or view/);
        await dialog.getByRole('button', { name: 'Submit Client Satisfaction Measurement', exact: true }).click();
        await oneAlert(page, 'The submission result could not be confirmed.');
        assert.equal(requests.filter(r => r.method === 'POST' && r.pathname === '/api/v1/feedback/csm').length, 1);
        assert.equal(await page.locator('#csm-region').inputValue(), 'Synthetic Region');
        await screenshot(page, `csm-unconfirmed-${width}`);
    });
    await check(`auth-expired-security-${width}`, '/login', { viewport, overrides: { '/api/v1/auth/session': error('not_authenticated', 401), 'POST /api/v1/auth/login': error('csrf_failed', 403) } }, async (page, { requests }) => {
        await page.getByLabel('Email', { exact: true }).fill('synthetic@example.test');
        await page.getByLabel('Password', { exact: true }).fill('synthetic-test-only');
        await page.getByRole('button', { name: 'Sign in', exact: true }).click();
        const announcement = page.locator('[aria-live="polite"]').filter({ hasText: 'The security check expired. Submit the form again.' });
        await shown(announcement);
        assert.equal(await announcement.count(), 1);
        await safe(page);
        assert.equal(await page.getByLabel('Email', { exact: true }).inputValue(), 'synthetic@example.test');
        assert.equal(requests.filter(r => r.method === 'POST' && r.pathname === '/api/v1/auth/login').length, 1);
        await screenshot(page, `auth-expired-security-${width}`);
    });
}
await finish();
