import assert from 'node:assert/strict';
import { createBrowserHarness } from './support/browser-harness.mjs';
import { chooseAppointmentDate } from './support/appointment-calendar.mjs';
import { appointment, appointmentId, service, user } from './support/ui-hierarchy-fixtures.mjs';

const h = await createBrowserHarness('appointment-picker');
const path = '/portal/appointments/book';
const counselors = [
  { id: '11111111-1111-4111-8111-111111111111', display_name: 'Maria Reyes', is_default: true, profile_photo_url: '/picker-photo.svg', profile_photo_updated_at: null },
  { id: '22222222-2222-4222-8222-222222222222', display_name: 'Alexandra Gabriella Delos Santos Villanueva', is_default: false, profile_photo_url: null, profile_photo_updated_at: null },
];
const day = '2027-01-05';
function world({ items = counselors, mode = 'ok', counselorMode = 'ok' } = {}) {
  const state = { mode, counselorMode, items, posts: [], reads: [] };
  const account = { ...user('STUDENT'), capabilities: ['appointments.view_self', 'appointments.manage_self', 'services.catalog.view'] };
  const options = {
    role: 'STUDENT',
    beforeNavigate: async ({ context }) => {
      await context.route('**/picker-photo.svg', route => route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80"><rect width="80" height="80" fill="#dfe9df"/><circle cx="40" cy="28" r="14" fill="#587466"/><path d="M12 80V68a28 28 0 0 1 56 0v12" fill="#36584b"/></svg>' }));
    },
    handler: async ({ pathname, method, url, request, reply }) => {
      if (pathname === '/api/v1/auth/session') { await reply({ user: account, session: { id: 'synthetic', expires_at: '2099-01-01T00:00:00Z', is_current: true } }); return true; }
      if (pathname === '/api/v1/appointments/booking/services') { await reply({ items: [{ ...service, delivery_modes: ['IN_PERSON', 'ONLINE'] }], page: 1, page_size: 10, has_next: false }); return true; }
      if (pathname === '/api/v1/appointments/booking/counselors') {
        if (state.counselorMode === 'pending') await new Promise(resolve => setTimeout(resolve, 500));
        await reply(state.counselorMode === 'error' ? { error: { code: 'internal_error' } } : { items: state.items }, state.counselorMode === 'error' ? 500 : 200); return true;
      }
      if (pathname === '/api/v1/appointments/booking/slots' || pathname.endsWith('/reschedule-slots')) {
        state.reads.push(Object.fromEntries(url.searchParams));
        if (state.mode === 'pending') await new Promise(resolve => setTimeout(resolve, 750));
        const date = url.searchParams.get('date');
        await reply(state.mode === 'error' ? { error: { code: 'internal_error' } } : { timezone: 'Asia/Manila', duration_minutes: 60, items: ['empty', 'lost'].includes(state.mode) ? [] : [2, 3, 4, 5, 6, 7].map(hour => ({ starts_at: `${date}T0${hour}:00:00Z`, ends_at: `${date}T0${hour + 1}:00:00Z` })) }, state.mode === 'error' ? 500 : 200); return true;
      }
      if (method === 'POST' && (pathname === '/api/v1/appointments' || pathname.endsWith('/reschedule'))) {
        state.posts.push(JSON.parse(request.postData()));
        if (state.mode === 'conflict') { state.mode = 'lost'; await reply({ error: { code: 'appointment_time_conflict' } }, 409); }
        else await reply({ ...appointment, provider: counselors[0], service, starts_at: state.posts.at(-1).starts_at, ends_at: `${day}T03:00:00Z` });
        return true;
      }
      return false;
    },
  };
  return { state, options };
}
async function start(page) {
  await h.shown(page.getByRole('button', { name: /^Counseling/ }));
  // Install after DayPicker initializes: replacing Date before @date-fns/tz loads removes
  // its prototype getters under Playwright's clock shim. This is a fixture-only constraint.
  await page.clock.install({ time: new Date('2026-12-31T16:05:00Z') });
  await page.getByRole('button', { name: /^Counseling/ }).click();
  await page.getByRole('radio', { name: 'In person', exact: true }).check();
  await h.shown(page.getByRole('group', { name: 'Appointment date', exact: true }));
}
const calendar = page => page.getByRole('group', { name: 'Appointment date', exact: true });
const times = page => page.getByRole('group', { name: 'Available Appointment times' });

for (const chosen of ['2027-01-05', '2027-02-05']) {
  const w = world();
  await h.check(`today navigation from ${chosen} preserves the selected schedule`, path, { ...w.options, viewport: { width: 390, height: 500 }, timezoneId: 'America/Los_Angeles' }, async page => {
    await start(page);
    await chooseAppointmentDate(page, chosen);
    await times(page).getByRole('button').first().click();
    const selected = w.state.reads.at(-1).date;
    const shortcut = calendar(page).getByRole('button', { name: 'Go to today', exact: true });
    for (let repeat = 0; repeat < 2; repeat++) {
      if (repeat === 0) await shortcut.click();
      else { await shortcut.focus(); await page.keyboard.press('Enter'); }
      const todayButton = calendar(page).locator('[data-day="2027-01-01"] button');
      assert.equal(await todayButton.evaluate(el => el === document.activeElement), true);
      assert.ok(await todayButton.evaluate(el => getComputedStyle(el).boxShadow !== 'none'), 'today has visible focus after mouse or keyboard navigation');
      const box = await todayButton.boundingBox();
      const header = await page.getByRole('banner').boundingBox();
      assert.ok(box.y >= Math.max(0, header.y + header.height) && box.y + box.height <= 500, `today stays fully visible in the short viewport: ${JSON.stringify(box)}`);
      await h.shown(page.getByRole('heading', { name: '5. Review Appointment' }));
      assert.equal(w.state.reads.at(-1).date, selected, 'navigation does not fetch slots for another date');
    }
    await page.keyboard.press('Enter');
    await h.shown(page.getByText('Selected date: January 1, 2027', { exact: true }));
    await h.shown(times(page));
    assert.equal(w.state.reads.at(-1).date, '2027-01-01', 'deliberate activation selects today');
    assert.equal(await page.getByRole('heading', { name: '5. Review Appointment' }).count(), 0, 'selecting another date clears the chosen time');
    assert.equal(w.state.posts.length, 0);
  });
}

for (const width of [1440, 1024, 390, 320]) {
  const w = world();
  await h.check(`booking layout ${width}`, path, { ...w.options, viewport: { width, height: width > 1000 ? 720 : 844 } }, async page => {
    await start(page);
    await chooseAppointmentDate(page, day);
    await times(page).getByRole('button').first().click();
    await h.shown(page.getByRole('heading', { name: '5. Review Appointment' }));
    await h.noHorizontalOverflow(page);
    assert.ok((await calendar(page).getByLabel('Month', { exact: true }).boundingBox()).height >= 44, 'full-size month control');
    const dateBox = await calendar(page).boundingBox();
    const timeBox = await page.getByRole('region', { name: 'Appointment times' }).boundingBox();
    if (width === 1440) assert.ok(timeBox.x > dateBox.x + dateBox.width - 1, 'times beside calendar');
    if (width <= 390) assert.ok(timeBox.y > dateBox.y + dateBox.height - 1, 'times below calendar');
    assert.equal(await page.getByRole('button', { name: /About/ }).count(), 0, 'no unsupported About action');
    await h.screenshot(page, `booking-${width}`);
    assert.equal(w.state.reads.every(read => read.date === day), true, `no visible-month availability fan-out: ${JSON.stringify(w.state.reads)}`);
  });
}
await h.check('enlarged text and long names at 320', path, { ...world().options, viewport: { width: 320, height: 640 } }, async page => {
  await start(page);
  await page.addStyleTag({ content: 'html { font-size: 200%; }' });
  await chooseAppointmentDate(page, day);
  await h.noHorizontalOverflow(page);
  await times(page).getByRole('button').first().click();
  await h.screenshot(page, 'booking-320-enlarged');
});
await h.check('keyboard radio and calendar navigation do not select until activation', path, world().options, async page => {
  await start(page);
  const radio = page.getByRole('radio', { name: /Maria Reyes/ });
  await radio.focus();
  await page.keyboard.press('ArrowRight');
  assert.equal(await page.getByRole('radio', { name: /Alexandra/ }).isChecked(), true);
  assert.ok(await page.getByRole('radio', { name: /Alexandra/ }).evaluate(el => getComputedStyle(el.closest('label')).boxShadow !== 'none'), 'visible keyboard ring');
  const first = calendar(page).locator('[data-day="2027-01-01"] button');
  await first.focus();
  await page.keyboard.press('ArrowRight');
  assert.equal(await calendar(page).locator('[data-day="2027-01-02"] button').evaluate(el => el === document.activeElement), true);
  assert.ok(await calendar(page).locator('[data-day="2027-01-02"] button').evaluate(el => getComputedStyle(el).boxShadow !== 'none'), 'visible calendar focus');
  await h.shown(page.getByText('No date selected.', { exact: true }));
  await page.keyboard.press('Enter');
  await h.shown(page.getByText('Selected date: January 2, 2027', { exact: true }));
  await page.keyboard.press('PageDown');
  await page.keyboard.press('Enter');
  await h.shown(page.getByText('Selected date: February 2, 2027', { exact: true }));
  await page.keyboard.press('Home');
  await page.keyboard.press('End');
  await page.keyboard.press('Enter');
  await h.shown(page.getByText('Selected date: February 6, 2027', { exact: true }));
});
for (const timezoneId of ['America/Los_Angeles', 'Asia/Manila', 'Pacific/Kiritimati']) {
  const w = world();
  await h.check(`Manila today and boundary dates in ${timezoneId}`, path, { ...w.options, timezoneId }, async page => {
    await start(page);
    assert.equal(await calendar(page).getByRole('button', { name: 'Previous month' }).isDisabled(), true);
    assert.equal(await calendar(page).locator('[data-today="true"]').getAttribute('data-day'), '2027-01-01');
    await chooseAppointmentDate(page, '2028-02-29');
    await h.shown(times(page));
    assert.equal(w.state.reads.at(-1).date, '2028-02-29', JSON.stringify(w.state.reads));
    await chooseAppointmentDate(page, '2027-12-31');
    await calendar(page).locator('[data-day="2027-12-31"] button').focus();
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('Enter');
    await h.shown(page.getByText('Selected date: January 1, 2028', { exact: true }));
    await h.shown(times(page));
    assert.equal(w.state.reads.at(-1).date, '2028-01-01', JSON.stringify(w.state.reads));
    await calendar(page).getByLabel('Year', { exact: true }).fill('2026');
    await calendar(page).getByRole('button', { name: 'Go', exact: true }).click();
    await h.shown(calendar(page).getByRole('alert'));
  });
}
await h.check('single unassigned counselor is selected directly', path, world({ items: [{ ...counselors[1] }] }).options, async page => {
  await start(page);
  assert.equal(await page.getByRole('radio', { name: /Alexandra/ }).count(), 0);
  await chooseAppointmentDate(page, day);
  await h.shown(times(page));
});
for (const counselorMode of ['error', 'pending', 'empty']) {
  const w = world({ counselorMode, items: counselorMode === 'empty' ? [] : counselors });
  await h.check(`counselor ${counselorMode}`, path, w.options, async page => {
    await page.getByRole('button', { name: /^Counseling/ }).click();
    await page.getByRole('radio', { name: 'In person', exact: true }).check();
    if (counselorMode === 'empty') await h.shown(page.getByText('No Counselors are available for this Service and delivery mode.'));
    else if (counselorMode === 'error') {
      await h.shown(page.getByText("Couldn't load Counselors. Try again."));
      w.state.counselorMode = 'ok';
      await page.getByRole('button', { name: 'Retry', exact: true }).click();
      await h.shown(calendar(page));
    } else { await h.shown(page.getByText('Loading Counselors…')); await h.shown(calendar(page)); }
  });
}
for (const mode of ['pending', 'empty', 'error']) {
  const w = world({ mode });
  await h.check(`available times ${mode} and recovery`, path, w.options, async page => {
    await start(page);
    await chooseAppointmentDate(page, day);
    if (mode === 'pending') { await h.shown(page.getByText('Loading available times…')); await h.shown(times(page)); }
    else if (mode === 'empty') {
      await h.shown(page.getByText('No available Appointment times were found for this date. Choose another date.'));
      assert.equal(await calendar(page).locator(`[data-day="${day}"] button`).isEnabled(), true, 'selected empty day stays selectable');
      w.state.mode = 'ok'; await page.getByRole('button', { name: 'Refresh times' }).click(); await h.shown(times(page));
    } else {
      await h.shown(page.getByText("Couldn't load available times. Try again."));
      w.state.mode = 'ok'; await page.getByRole('button', { name: 'Retry', exact: true }).click(); await h.shown(times(page));
    }
  });
}
await h.check('counselor date delivery and service changes clear incompatible selections', path, world().options, async page => {
  await start(page); await chooseAppointmentDate(page, day); await times(page).getByRole('button').first().click();
  await chooseAppointmentDate(page, '2027-01-06');
  assert.equal(await page.getByRole('heading', { name: '5. Review Appointment' }).count(), 0);
  await times(page).getByRole('button').first().click();
  await page.getByRole('radio', { name: /Alexandra/ }).check();
  await h.shown(page.getByText('No date selected.', { exact: true }));
  assert.equal(await times(page).count(), 0);
  await chooseAppointmentDate(page, day);
  await page.getByRole('radio', { name: 'Online', exact: true }).check();
  await h.shown(page.getByText('No date selected.', { exact: true }));
  await chooseAppointmentDate(page, day);
  await page.getByRole('button', { name: /^Counseling/ }).click();
  assert.equal(await calendar(page).count(), 0);
});
await h.check('failed refresh holds choices then drops lost selection', path, world().options, async (page, fixture) => {
  // A separate mutable world is installed below in the polling/conflict checks.
  await start(page); await chooseAppointmentDate(page, day); await times(page).getByRole('button').first().click();
  await page.route('**/api/v1/appointments/booking/slots?*', route => route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: { code: 'internal_error' } }) }));
  await page.getByRole('button', { name: 'Refresh times' }).click();
  await h.shown(page.getByText("Couldn't recheck available times. Retry before choosing a time."));
  assert.equal(await times(page).getByRole('button').first().isDisabled(), true);
  assert.equal(await page.getByRole('button', { name: 'Book Appointment', exact: true }).isDisabled(), true);
  await page.unroute('**/api/v1/appointments/booking/slots?*');
  await page.route('**/api/v1/appointments/booking/slots?*', route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: [], timezone: 'Asia/Manila' }) }));
  await page.getByRole('button', { name: 'Retry', exact: true }).click();
  await h.shown(page.getByText('The selected time is no longer available. Choose another available time.'));
  assert.equal(await page.getByRole('heading', { name: '5. Review Appointment' }).count(), 0);
  assert.equal(fixture.requests.filter(r => r.method === 'POST').length, 0);
});
for (const trigger of ['polling', 'submission recheck', 'conflict']) {
  const w = world();
  await h.check(`booking ${trigger} invalidates lost time`, path, w.options, async page => {
    await start(page); await chooseAppointmentDate(page, day); await times(page).getByRole('button').first().click();
    const before = w.state.reads.length;
    w.state.mode = trigger === 'conflict' ? 'conflict' : 'lost';
    if (trigger === 'polling') await page.clock.fastForward(16000);
    else await page.getByRole('button', { name: 'Book Appointment', exact: true }).click();
    await h.shown(page.getByText(trigger === 'conflict' ? 'That time was just taken. Choose another available time.' : 'The selected time is no longer available. Choose another available time.'));
    assert.ok(w.state.reads.length > before);
    assert.equal(w.state.posts.length, trigger === 'conflict' ? 1 : 0);
    assert.equal(await page.getByRole('heading', { name: '5. Review Appointment' }).count(), 0);
  });
}
for (const trigger of ['date change', 'recheck', 'conflict']) {
  const w = world();
  await h.check(`reschedule ${trigger} preserves reason and focus`, `/portal/appointments/${appointmentId}`, { ...w.options, viewport: { width: 390, height: 640 }, handler: async args => {
    if (args.pathname === '/api/v1/auth/session') return false;
    return w.options.handler(args);
  } }, async page => {
    const opener = page.getByRole('button', { name: 'Reschedule', exact: true });
    await h.shown(opener);
    await page.clock.install({ time: new Date('2026-12-31T16:05:00Z') });
    await opener.click();
    const dialog = page.getByRole('dialog', { name: 'Reschedule Appointment', exact: true });
    await chooseAppointmentDate(dialog, day, 'New date');
    await dialog.getByLabel('Reason (optional)').fill('Keep my reason');
    await dialog.getByRole('group', { name: 'Available replacement times' }).getByRole('button').first().click();
    await dialog.getByRole('button', { name: 'Go to today', exact: true }).click();
    assert.equal(await dialog.locator('[data-day="2027-01-01"] button').evaluate(el => el === document.activeElement), true);
    await h.shown(dialog.getByRole('heading', { name: 'Review reschedule' }));
    if (trigger === 'date change') {
      await chooseAppointmentDate(dialog, '2027-01-06', 'New date');
      assert.equal(await dialog.getByRole('heading', { name: 'Review reschedule' }).count(), 0);
    } else {
      w.state.mode = trigger === 'conflict' ? 'conflict' : 'lost';
      await dialog.getByRole('button', { name: 'Reschedule Appointment', exact: true }).click();
      await h.shown(dialog.getByText(trigger === 'conflict' ? 'That time was just taken. Choose another available time.' : 'The selected time is no longer available. Choose another available time.'));
      assert.equal(w.state.posts.length, trigger === 'conflict' ? 1 : 0);
    }
    assert.equal(await dialog.getByLabel('Reason (optional)').inputValue(), 'Keep my reason');
    await h.noHorizontalOverflow(page);
    await h.screenshot(page, `reschedule-${trigger}`);
    await page.keyboard.press('Escape'); await h.hidden(dialog);
    assert.equal(await opener.evaluate(el => el === document.activeElement), true);
  });
}
await h.finish();
