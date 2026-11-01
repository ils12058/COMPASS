import assert from 'node:assert/strict';
import { join } from 'node:path';
import { createBrowserHarness } from './support/browser-harness.mjs';
import { tracerFixture, tracerPath, graduate } from './support/ux15-tracer-fixtures.mjs';
const phase = process.env.COMPASS_UX15_TRACER_PHASE ?? 'after';
const { check, shown, hidden, noHorizontalOverflow, artifacts, finish, settleFetches } = await createBrowserHarness(`ux15-tracer-${phase}`);
const saveButton = page => page.getByRole('button', { name: 'Save draft', exact: true });
const submitButton = page => page.getByRole('button', { name: 'Submit Graduate Tracer Survey', exact: true });
async function focusId(page, id) { assert.equal(await page.evaluate(() => document.activeElement?.id), id); }
async function capture(page, name, target) {
  await page.addStyleTag({ content: 'nextjs-portal { display:none !important; }' });
  if (target) await target.evaluate(el => { el.scrollIntoView({ block: "start" }); window.scrollBy(0, el.getBoundingClientRect().top - 80); });
  await page.screenshot({ path: join(artifacts, `${phase}-${name}.png`), animations: 'disabled' });
}
for (const device of ['desktop', 'phone']) {
  const state = tracerFixture();
  await check(`${phase} ${device} visual evidence`, tracerPath, { handler: state.handler, device }, async page => {
    await shown(page.locator('#gts-name'));
    await page.evaluate(() => document.fonts.ready);
    await noHorizontalOverflow(page);
    await capture(page, `${device}-general`);
    await capture(page, `${device}-education`, page.locator('#graduate-tracer-education'));
    await capture(page, `${device}-training`, page.locator('#graduate-tracer-training'));
    await capture(page, `${device}-employed`, page.locator('#graduate-tracer-employment'));
    await capture(page, `${device}-matrix`, page.getByRole('table', { name: /Compare job level/ }));
    await capture(page, `${device}-ready`, submitButton(page));
    await page.locator('#gts-mobile').fill('0917 000 0000');
    await capture(page, `${device}-unsaved`, saveButton(page));
    await saveButton(page).click();
    await shown(page.getByRole('status').filter({ hasText: 'Draft saved.' }));
    await capture(page, `${device}-saved`, saveButton(page));
    await page.locator('#gts-employment-state-not-employed').check();
    await capture(page, `${device}-not-employed`, page.locator('#graduate-tracer-employment'));
    assert.equal(state.submissions, 0);
  });
}
{
  const state = tracerFixture({ partial: true });
  await check(`${phase} validation evidence`, tracerPath, { handler: state.handler, device: 'phone' }, async page => {
    await shown(page.locator('#gts-name'));
    await submitButton(page).click();
    await focusId(page, 'gts-name');
    if (phase === 'after') await capture(page, 'phone-validation', page.locator('#graduate-tracer-error-summary').locator('..'));
    else await capture(page, 'phone-validation');
  });
}
if (phase !== 'before') {
  for (const [device, viewport] of [['desktop', { width: 1440, height: 1000 }], ['wide', { width: 1920, height: 1080 }], ['tablet', { width: 768, height: 1024 }], ['phone', undefined], ['narrowPhone', undefined]]) {
    const state = tracerFixture();
    await check(`Navigation, matrix keyboard access and text reflow ${device}`, tracerPath, { handler: state.handler, device: device === 'wide' ? 'desktop' : device, viewport }, async page => {
      await shown(page.locator('#gts-name'));
      const nav = page.getByRole('navigation', { name: 'Survey sections', exact: true });
      const links = nav.getByRole('link');
      assert.equal(await links.count(), 5);
      const controls = await page.locator('form input, form select, form textarea').count();
      for (let i = 0; i < 5; i++) {
        const href = await links.nth(i).getAttribute('href');
        await links.nth(i).focus(); await page.keyboard.press('Enter');
        await focusId(page, href.slice(1));
        assert.ok(await page.locator(href).evaluate(el => el.getBoundingClientRect().top >= 55));
        assert.equal(await page.locator('form input, form select, form textarea').count(), controls);
      }
      await page.getByRole('link', { name: 'Back to sections', exact: true }).click();
      await focusId(page, 'graduate-tracer-section-links');
      for (const name of ['Reasons for taking degrees choices', 'Job level comparison choices']) {
        const region = page.getByRole('region', { name, exact: true });
        await region.focus();
        if (await region.evaluate(el => el.scrollWidth > el.clientWidth)) {
          await page.keyboard.press('ArrowRight');
          assert.ok(await region.evaluate(el => el.scrollLeft > 0));
          await page.keyboard.press('ArrowLeft');
          assert.equal(await region.evaluate(el => el.scrollLeft), 0);
        }
        const rect = await region.locator('tbody label').first().boundingBox();
        assert.ok(rect.width >= 44 && rect.height >= 44);
      }
      const radios = page.locator('input[name="gts-first-job-level"]');
      await radios.first().focus(); await page.keyboard.press('ArrowDown');
      assert.equal(await radios.nth(1).isChecked(), true);
      const checkbox = page.getByRole('checkbox', { name: /Good grades in high school — Undergraduate/ });
      await checkbox.focus(); await page.keyboard.press('Space'); assert.equal(await checkbox.isChecked(), true);
      await noHorizontalOverflow(page);
      await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
      const overflow = await page.locator('main form').evaluate(el => [...el.querySelectorAll('*')].filter(child => !child.closest('[role="region"]') && child.getBoundingClientRect().width && (child.getBoundingClientRect().right > innerWidth + 1 || child.getBoundingClientRect().left < -1)).map(child => child.id || child.tagName));
      assert.deepEqual(overflow, [], 'Form reflows independently of the known portal top-bar limitation');
      assert.equal(state.writes.length, 0); assert.equal(state.submissions, 0);
    });
  }
  {
    const state = tracerFixture({ partial: true });
    await check('Partial drafts, draft errors, deduplicated review and original field focus', tracerPath, { handler: state.handler, device: 'phone' }, async page => {
      await page.locator('#gts-name').fill('Synthetic partial graduate');
      await saveButton(page).click(); await shown(page.getByRole('status').filter({ hasText: 'Draft saved.' }));
      assert.equal(state.writes.length, 1, 'Final required answers do not block saving');
      await page.getByRole('button', { name: 'Add another degree', exact: true }).click();
      await page.getByRole('button', { name: 'Add training / advance study', exact: true }).click();
      await saveButton(page).click(); await focusId(page, 'degree-0-name'); assert.equal(state.writes.length, 1);
      await page.getByRole('button', { name: 'Review answers', exact: true }).click();
      const summary = page.locator('section[aria-labelledby="graduate-tracer-error-summary"]');
      await summary.getByRole('button', { name: 'Enter a title for Training 1 before saving.', exact: true }).click(); await focusId(page, 'training-0-title');
      assert.equal(await page.locator('#training-0-title').getAttribute('aria-describedby'), 'training-0-title-error');
      await summary.getByRole('button', { name: 'Select your civil status.', exact: true }).click(); await focusId(page, 'gts-civil-status');
      await page.locator('#gts-email').fill('invalid');
      assert.equal(await summary.getByRole('button', { name: 'Enter a valid email address or leave the field blank.', exact: true }).count(), 1);
      assert.equal(await summary.getByRole('button', { name: /curriculum suggestion|mobile number|permanent address/i }).count(), 0);
    });
  }
  {
    const state = tracerFixture({ detailOverrides: { first_job_level: null, current_job_level: null } });
    await check('Matrix validation summary focuses original radios and preserves error descriptions', tracerPath, { handler: state.handler, device: 'narrowPhone' }, async page => {
      await shown(page.locator('#gts-name'));
      await submitButton(page).click(); await focusId(page, 'gts-first-job-level');
      await page.getByRole('button', { name: 'Select the current-job level.', exact: true }).click(); await focusId(page, 'gts-current-job-level');
      assert.equal(await page.locator('#gts-current-job-level').getAttribute('aria-describedby'), 'gts-current-job-level-error');
      assert.equal(await page.locator('input[name="gts-first-job-level"]').count(), 4);
      await page.locator('#gts-first-job-level').check(); await page.locator('#gts-current-job-level').check();
      await saveButton(page).click(); await shown(page.getByRole('status').filter({ hasText: 'Draft saved.' }));
      assert.equal(state.writes.at(-1).first_job_level, 'RANK_CLERICAL'); assert.equal(state.writes.at(-1).current_job_level, 'RANK_CLERICAL');
      assert.equal(state.submissions, 0);
    });
  }
  for (const failure of [500, 409, 'network']) {
    const state = tracerFixture(); state.failSave = typeof failure === 'number' ? failure : 0; state.saveNetworkFailure = failure === 'network';
    await check(`Failed save preserves unsaved answers ${failure}`, tracerPath, { handler: state.handler }, async page => {
      await page.locator('#gts-mobile').fill('Synthetic retained input');
      await saveButton(page).click();
      await shown(page.getByRole('alert').filter({ hasText: failure === 409 ? 'The response changed or became unavailable' : 'could not be saved' }));
      assert.equal(await page.locator('#gts-mobile').inputValue(), 'Synthetic retained input');
      await shown(page.getByRole('status').filter({ hasText: 'Unsaved changes' }));
      assert.equal(await submitButton(page).isEnabled(), false);
      assert.equal(state.writes.length, 1); assert.equal(state.submissions, 0);
    });
  }
  {
    const state = tracerFixture(); let release; state.holdSave = new Promise(resolve => { release = resolve; });
    state.canonicalize = detail => ({ ...detail, mobile_number: 'Canonical synthetic answer' });
    await check('Pending protection and canonical save synchronization across return', tracerPath, { handler: state.handler }, async page => {
      await page.locator('#gts-mobile').fill('Local synthetic answer');
      await saveButton(page).click(); await shown(page.getByRole('button', { name: 'Saving…', exact: true }));
      assert.equal(await page.locator('#gts-name').isEnabled(), false); assert.equal(await submitButton(page).isEnabled(), false);
      await page.getByRole('navigation', { name: 'Survey sections' }).getByRole('link').first().click();
      assert.equal(state.writes.length, 1);
      release(); await shown(page.getByRole('status').filter({ hasText: 'Draft saved.' }));
      assert.equal(await page.locator('#gts-mobile').inputValue(), 'Canonical synthetic answer');
      assert.equal(await saveButton(page).isEnabled(), false);
      await settleFetches(page);
      await page.reload(); await shown(page.locator('#gts-name'));
      assert.equal(await page.locator('#gts-mobile').inputValue(), 'Canonical synthetic answer');
      assert.equal(await saveButton(page).isEnabled(), false);
    });
  }
  {
    const state = tracerFixture();
    await check('Employment transitions clear stale branches and preserve conditional semantics', tracerPath, { handler: state.handler }, async page => {
      await page.locator('#gts-present-employment-status-self-employed').check();
      await page.locator('#gts-self-employed-skills').fill('Synthetic skills');
      await page.locator('#gts-first-job-after-college-yes').check();
      await shown(page.locator('#gts-staying-reasons'));
      await page.locator('#gts-first-job-related-yes').check();
      await page.locator('#gts-accepting-reasons-other').check();
      await page.locator('#gts-accepting-other').fill('Synthetic accepting reason');
      await page.locator('#gts-first-job-related-no').check(); await hidden(page.locator('#gts-accepting-other'));
      await page.locator('#gts-first-job-after-college-no').check(); await hidden(page.locator('#gts-staying-reasons'));
      await page.locator('#gts-employment-state-not-employed').check(); await hidden(page.locator('#gts-present-occupation'));
      await page.locator('#gts-unemployment-reasons-other').check(); await page.locator('#gts-unemployment-other').fill('Synthetic reason');
      await saveButton(page).click(); await shown(page.getByRole('status').filter({ hasText: 'Draft saved.' }));
      const saved = state.writes.at(-1);
      for (const key of ['present_occupation', 'present_employment_status', 'first_job_level', 'current_job_level', 'self_employed_college_skills', 'reasons_for_accepting_other']) assert.equal(saved[key], undefined, key);
      await page.locator('#gts-employment-state-never-employed').check(); await shown(page.locator('#gts-unemployment-reasons'));
      await page.getByRole('button', { name: 'Review answers', exact: true }).click();
      assert.equal(await page.locator('#graduate-tracer-error-summary').count(), 0, 'Hidden employed fields never appear as review errors');
      await page.locator('#gts-employment-state-employed').check(); await hidden(page.locator('#gts-unemployment-reasons'));
      await page.getByRole('button', { name: 'Review answers', exact: true }).click();
      await page.getByRole('button', { name: 'Select your present employment status.', exact: true }).click();
      await focusId(page, 'gts-present-employment-status-regular-permanent');
      await saveButton(page).click(); await shown(page.getByRole('status').filter({ hasText: 'Draft saved.' }));
      assert.deepEqual(state.writes.at(-1).unemployment_reasons, []); assert.equal(state.writes.at(-1).unemployment_other_reason, undefined);
    });
  }
  {
    const state = tracerFixture();
    await check('Stable repeating records and College to Program filtering', tracerPath, { handler: state.handler, device: 'phone' }, async page => {
      await page.locator('#gts-graduated-college option[value="college-b"]').waitFor({ state: 'attached' });
      await page.locator('#gts-graduated-college').selectOption('college-b');
      assert.equal(await page.locator('#gts-graduated-program').inputValue(), '');
      assert.deepEqual(await page.locator('#gts-graduated-program option').evaluateAll(options => options.map(o => o.value)), ['', 'program-b']);
      await page.locator('#gts-graduated-program').selectOption('program-b');
      await page.getByRole('button', { name: 'Add another degree', exact: true }).click();
      await page.locator('#degree-1-name').fill('Second synthetic degree'); await page.locator('#degree-1-institution').fill('Second synthetic university'); await page.locator('#degree-1-year').fill('2025');
      await page.locator('#degree-1-name').evaluate(el => { el.dataset.identity = 'retained'; });
      await page.getByRole('button', { name: 'Remove degree 1', exact: true }).click();
      assert.equal(await page.locator('#degree-0-name').inputValue(), 'Second synthetic degree');
      assert.equal(await page.locator('#degree-0-name').getAttribute('data-identity'), 'retained');
      await page.getByRole('button', { name: 'Add training / advance study', exact: true }).click(); await page.locator('#training-1-title').fill('Second synthetic training');
      await page.getByRole('button', { name: 'Remove training / advance study 1', exact: true }).click(); assert.equal(await page.locator('#training-0-title').inputValue(), 'Second synthetic training');
      await page.getByRole('button', { name: 'Add examination', exact: true }).click(); await page.locator('#exam-1-name').fill('Second synthetic exam'); await page.getByRole('button', { name: 'Remove examination 1', exact: true }).click();
      await saveButton(page).click(); await shown(page.getByRole('status').filter({ hasText: 'Draft saved.' }));
      assert.equal(state.writes.at(-1).education[0].degree_and_specialization, 'Second synthetic degree');
      assert.equal(state.writes.at(-1).trainings[0].title, 'Second synthetic training');
      assert.equal(state.writes.at(-1).professional_exams[0].examination_name, 'Second synthetic exam');
      assert.equal(state.writes.at(-1).graduated_program_id, 'program-b');
      assert.equal(JSON.stringify(state.writes.at(-1)).includes('formKey'), false);
    });
  }
  for (const mode of ['ok', 'unknown-committed', 'unknown-draft', 'unknown-check-fails']) {
    const state = tracerFixture({ employed: false });
    state.submitMode = mode === 'unknown-check-fails' ? 'unknown-draft' : mode;
    let release; state.holdSubmit = new Promise(resolve => { release = resolve; });
    await check(`Deliberate submission and canonical reconciliation ${mode}`, tracerPath, { handler: state.handler, device: 'phone' }, async page => {
      await shown(page.locator('#gts-name'));
      await submitButton(page).click(); const dialog = page.getByRole('alertdialog'); await shown(dialog);
      await dialog.getByRole('button', { name: 'Cancel', exact: true }).click(); assert.equal(state.submissions, 0);
      await submitButton(page).click(); await dialog.getByRole('button', { name: 'Submit Graduate Tracer Survey', exact: true }).click();
      await shown(dialog.getByRole('button', { name: 'Submitting…', exact: true }));
      assert.equal(await dialog.getByRole('button', { name: 'Submitting…', exact: true }).isEnabled(), false);
      await page.keyboard.press('Escape'); await shown(dialog); assert.equal(state.submissions, 1);
      if (mode === 'unknown-check-fails') state.failRefresh = true;
      release();
      if (mode === 'ok' || mode === 'unknown-committed') {
        await shown(page.getByText(/This response is read-only\./)); await hidden(page.locator('form')); assert.equal(state.submissions, 1);
      } else {
        await shown(dialog.getByText(mode === 'unknown-draft' ? /The response is still a draft/ : /We could not verify whether submission completed/));
        if (mode === 'unknown-check-fails') {
          assert.equal(await dialog.getByRole('button', { name: 'Submit Graduate Tracer Survey', exact: true }).isEnabled(), false);
          state.failRefresh = false;
          await dialog.getByRole('button', { name: 'Check response status', exact: true }).click();
          await shown(dialog.getByText(/The saved response is still a draft/));
        }
        assert.equal(state.submissions, 1, 'Status checks never replay the submission');
        state.submitMode = 'ok'; await dialog.getByRole('button', { name: 'Submit Graduate Tracer Survey', exact: true }).click();
        await shown(page.getByText(/This response is read-only\./)); assert.equal(state.submissions, 2);
      }
      assert.equal(state.writes.length, 0, 'Submission uses the saved draft without a replacement save');
    });
  }
  {
    const state = tracerFixture();
    await check('Dirty route navigation, browser back and native unload remain guarded', '/portal', { handler: state.handler }, async page => {
      await page.getByRole('link', { name: 'Graduate Tracer', exact: true }).first().click();
      await page.locator('#gts-mobile').fill('Unsaved synthetic answer');
      const prompts = [];
      page.on('dialog', async dialog => { prompts.push(dialog.type()); await dialog.dismiss(); });
      await page.getByRole('link', { name: 'Overview', exact: true }).first().click();
      assert.equal(prompts.length, 1);
      await page.goBack({ timeout: 2000 }).catch(() => null);
      await page.waitForURL(/graduate-tracer$/); assert.equal(prompts.length, 2);
      await page.locator('#gts-mobile').click();
      const unload = page.waitForEvent('dialog', { predicate: dialog => dialog.type() === 'beforeunload' });
      await page.close({ runBeforeUnload: true }); await unload;
      assert.equal(await page.locator('#gts-mobile').inputValue(), 'Unsaved synthetic answer');
      await saveButton(page).click(); await shown(page.getByRole('status').filter({ hasText: 'Draft saved.' }));
      const count = prompts.length;
      await page.getByRole('link', { name: 'Overview', exact: true }).first().click();
      await page.waitForURL(/\/portal$/); assert.equal(prompts.length, count);
      assert.equal(state.submissions, 0);
    });
  }

  for (const condition of ['non-graduate', 'restricted', 'read-only-draft', 'submitted', 'disposed']) {
    const account = condition === 'non-graduate' ? { ...graduate, student_lifecycle_status: 'ENROLLED' } : condition === 'restricted' ? { ...graduate, capabilities: [] } : condition === 'read-only-draft' ? { ...graduate, capabilities: ['graduate_tracer.view_self'] } : graduate;
    const state = tracerFixture({ account, disposed: condition === 'disposed', submitted: condition === 'submitted' });
    await check(`Eligibility and historical response ${condition}`, tracerPath, { handler: state.handler }, async page => {
      if (condition === 'non-graduate') await shown(page.getByText('The Graduate Tracer Survey is for graduates.', { exact: true }));
      else if (condition === 'restricted') await shown(page.getByRole('heading', { name: 'Graduate Tracer unavailable', exact: true }));
      else if (condition === 'read-only-draft') await shown(page.getByText('This saved draft is read-only for this account.', { exact: true }));
      else if (condition === 'submitted') await shown(page.getByText(/This response is read-only\./));
      else await shown(page.getByText(/Your personal response was anonymized/));
      await hidden(page.locator('form')); assert.equal(state.writes.length, 0); assert.equal(state.submissions, 0);
      if (['restricted', 'non-graduate'].includes(condition)) assert.equal(state.reads, 0);
    });
  }
}
await finish();
