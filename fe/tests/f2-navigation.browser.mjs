// F2 reachability and interaction contract. Local synthetic accounts only.
import assert from 'node:assert/strict';
import './support/register-tsx.mjs';
import { createBrowserHarness } from './support/browser-harness.mjs';
import { navigationWorld, profiles } from './support/f2-navigation-fixtures.mjs';
const { portalNavigationGroups, portalWorkspaceGroups } = await import('../src/features/portal/components/portal-workspaces.ts');
const { portalCommandDestinations } = await import('../src/features/portal/components/portal-command-destinations.ts');
const h = await createBrowserHarness('f2-navigation');
const allAvailable = { can_confirm_student: true, can_submit_referral: true, can_view_submissions: true, valid_until: null };
const hrefs = links => links.map(x=>x.href);
const navFor = page => page.getByRole('navigation', { name: 'Portal navigation', exact: true });
async function menu(page) {
  await h.shown(page.getByRole('button', {name:/^Open user menu for /}));
  if (await page.getByRole('button', { name: 'Open portal navigation' }).isVisible()) await page.getByRole('button', { name: 'Open portal navigation' }).click();
  const nav = navFor(page); await h.shown(nav); return nav;
}
async function visibleHrefs(nav) { return nav.getByRole('link').evaluateAll(links=>links.map(x=>x.getAttribute('href'))); }
async function verifyNavigation(page, user, availability, width) {
  await h.shown(page.locator('main h1'));
  await h.settleFetches(page);
  const {daily, secondary} = portalNavigationGroups(user, availability);
  const before = ['/portal', ...portalWorkspaceGroups(user, availability).flatMap(g=>hrefs(g.links))].sort();
  const nav = await menu(page);
  assert.deepEqual(await visibleHrefs(nav), hrefs(daily));
  const more = nav.getByRole('button', { name: /^(More|Administration),/ });
  if (secondary.links.length) {
    assert.equal(await more.getAttribute('aria-expanded'), 'false');
    assert.equal(await more.innerText(), `${secondary.label} (${secondary.links.length})`);
    await more.focus(); await page.keyboard.press('Enter');
    assert.equal(await more.getAttribute('aria-expanded'), 'true');
    assert.deepEqual(await visibleHrefs(nav), hrefs([...daily, ...secondary.links]));
    await nav.getByRole('link').last().scrollIntoViewIfNeeded();
    await h.shown(nav.getByRole('link').last());
    assert.deepEqual((await visibleHrefs(nav)).sort(), before);
    await more.focus(); await page.keyboard.press('Space');
    assert.equal(await more.getAttribute('aria-expanded'), 'false');
    assert.deepEqual(await visibleHrefs(nav), hrefs(daily));
  } else assert.equal(await more.count(), 0);
  if (width < 1024) {
    await page.keyboard.press('Escape');
    await h.hidden(page.getByRole('dialog', {name:'Portal navigation'}));
    assert.equal(await page.getByRole('button', {name:'Open portal navigation'}).evaluate(x=>x===document.activeElement), true);
  }
  await page.getByRole('button', {name:'Go to a COMPASS feature'}).click();
  const dialog = page.getByRole('dialog', {name:'Go to a COMPASS feature'});
  await h.shown(dialog);
  const actual = await dialog.locator('a[href]').evaluateAll(links=>links.map(x=>x.getAttribute('href')));
  // Complete command list, including every currently authorized deep action.
  assert.deepEqual(actual, hrefs(portalCommandDestinations(user, availability)));
  await page.keyboard.press('Escape');
  await h.noHorizontalOverflow(page);
}
for (const [name, user] of Object.entries(profiles)) for (const width of [1440,390]) {
  await h.check(`${name}-${width}-complete-reachability`, '/portal', navigationWorld(user).options({mobile:width===390, viewport:{width,height:844}}), page=>verifyNavigation(page,user,undefined,width));
}
const variants = [
  ['student-exit-available', {...profiles.Student, exit_interview_workspace_available:true}],
  ['alumni-exit-available', {...profiles.Alumni, exit_interview_workspace_available:true}],
  ['head-without-grants', {...profiles.Head, capabilities:[]}],
  ['officer-default', {...profiles['Institutional Officer'], capabilities:[]}],
  ['explicit-notice-manage-only', {...profiles['Institutional Officer'], capabilities:['privacy_governance.notices.manage']}],
  ['explicit-activity-only', {...profiles['Institutional Officer'], capabilities:['privacy_governance.activity.view']}],
  ['counselor-read-only', {...profiles.Counselor, capabilities:profiles.Counselor.capabilities.filter(x=>x.includes('view'))}],
  ['counselor-manage-only', {...profiles.Counselor, capabilities:profiles.Counselor.capabilities.filter(x=>!x.includes('view'))}],
  ['additional-effective-grants', {...profiles.Counselor, capabilities:[...profiles.Counselor.capabilities,'accounts.manage','platform_operations.view']}],
];
for (const a of [false,true]) for (const b of [false,true]) for (const c of [false,true]) {
  variants.push([`faculty-availability-${a}-${b}-${c}`, profiles.Faculty, {can_confirm_student:a,can_submit_referral:b,can_view_submissions:c,valid_until:null}]);
}
for (const [name,user,availability] of variants) {
  await h.check(name, '/portal', navigationWorld(user,availability).options(), page=>verifyNavigation(page,user,availability,1440));
}
for (const [name,user,path] of [
  ['head', profiles.Head, '/portal/academic-years'],
  ['alumni', profiles.Alumni, '/portal/appointments/my'],
  ['it-admin', profiles['IT Admin'], '/portal/availability/office'],
  ['goa', profiles.GOA, '/portal/counseling/coverage'],
]) {
  await h.check(`${name}-active-secondary-route`, path, navigationWorld(user).options(), async page=>{
    const nav=navFor(page); await h.shown(nav);
    const more=nav.getByRole('button',{name:/^(More|Administration),/});
    assert.equal(await more.getAttribute('aria-expanded'),'true');
    await h.shown(nav.locator('[aria-current="page"]'));
    await page.getByRole('button',{name:'Collapse navigation'}).click();
    await h.shown(nav.locator('[aria-current="page"]'));
    await nav.locator('[aria-current="page"]').focus();
    await h.shown(page.locator('div.fixed[aria-hidden="true"]').filter({hasText:await nav.locator('[aria-current="page"]').innerText()}));
    await page.getByRole('button',{name:'Expand navigation'}).click();
    await h.shown(nav.locator('[aria-current="page"]'));
    await more.click(); assert.equal(await more.getAttribute('aria-expanded'),'false');
    await more.click(); assert.equal(await more.getAttribute('aria-expanded'),'true');
  });
}
for (const width of [320,360,375,390,402,414,440,1280]) {
  await h.check(`long-menu-${width}-200-percent-reduced-motion`, '/portal', navigationWorld(profiles.Head).options({viewport:{width,height:640}}), async page=>{
    await h.shown(page.locator('main h1'));
    await page.emulateMedia({reducedMotion:'reduce', ...(process.env.COMPASS_UI_BROWSER !== 'webkit' ? {forcedColors:'active'} : {})});
    await page.evaluate(()=>{document.documentElement.style.fontSize='200%';});
    const nav=await menu(page);
    const more=nav.getByRole('button',{name:/^More,/}); await more.click();
    await nav.getByRole('link').last().scrollIntoViewIfNeeded();
    const dimensions=await nav.evaluate(x=>({scroll:x.scrollHeight,client:x.clientHeight,width:x.clientWidth,overflow:x.scrollWidth}));
    assert.ok(dimensions.scroll>dimensions.client,'Long menu scrolls within the dock or drawer');
    assert.ok(dimensions.overflow<=dimensions.width+1,'Menu labels wrap without horizontal overflow');
    for (const link of await nav.getByRole('link').all()) assert.ok((await link.boundingBox()).height>=44);
    await h.screenshot(page,`long-menu-${width}-200-percent`);
    await h.noHorizontalOverflow(page);
  });
}
// Permission/session changes replace the rendered menu and command results, including open More.
const switching = navigationWorld(profiles.Head);
await h.check('account-switch-and-permission-loss', '/portal', switching.options(), async page=>{
  const nav=navFor(page); await h.shown(nav);
  await nav.getByRole('button',{name:/^More,/}).click();
  await h.shown(nav.locator('a[href="/portal/assessment-records"]'));
  switching.account = {...profiles['IT Admin'], id:'synthetic-new-account'};
  await h.settleFetches(page);
  await page.clock.fastForward(31_000);
  await page.evaluate(()=>{window.dispatchEvent(new Event('offline'));window.dispatchEvent(new Event('online'));});
  await h.shown(nav.getByRole('link',{name:'Accounts',exact:true}));
  assert.equal(await nav.locator('a[href="/portal/assessment-records"]').count(),0);
  assert.equal(await nav.getByRole('button',{name:/^Administration,/}).getAttribute('aria-expanded'),'false');
  switching.account = {...switching.account, capabilities:[]};
  await h.settleFetches(page);
  await page.clock.fastForward(31_000);
  await page.evaluate(()=>{window.dispatchEvent(new Event('offline'));window.dispatchEvent(new Event('online'));});
  await h.hidden(nav.getByRole('link',{name:'Accounts',exact:true}));
  assert.deepEqual(await visibleHrefs(nav), ['/portal']);
  await page.getByRole('button',{name:'Go to a COMPASS feature'}).click();
  assert.equal(await page.getByRole('dialog').locator('a[href="/portal/accounts"],a[href="/portal/assessment-records"]').count(),0);
});
const pendingFaculty = navigationWorld(profiles.Faculty,allAvailable);
let releaseAvailability;
pendingFaculty.availabilityHold = new Promise(resolve=>{releaseAvailability=resolve;});
await h.check('faculty-loading-failed-refresh-and-recovery', '/portal', pendingFaculty.options(), async page=>{
  const nav=navFor(page); await h.shown(nav);
  assert.equal(await nav.locator('a[href^="/portal/faculty/referrals"]').count(),0);
  releaseAvailability();
  await h.shown(nav.getByRole('link',{name:'Submit Referral',exact:true}));
  pendingFaculty.availabilityStatus=503;
  await page.evaluate(()=>{window.dispatchEvent(new Event('offline'));window.dispatchEvent(new Event('online'));});
  await h.hidden(nav.getByRole('link',{name:'Submit Referral',exact:true}));
  assert.equal(await nav.locator('a[href^="/portal/faculty/referrals"]').count(),0);
  pendingFaculty.availabilityStatus=200;
  await page.evaluate(()=>{window.dispatchEvent(new Event('offline'));window.dispatchEvent(new Event('online'));});
  await h.shown(nav.getByRole('link',{name:'Submit Referral',exact:true}));
  await nav.getByRole('link',{name:'My Referrals',exact:true}).click();
  await page.waitForURL(/\/portal\/faculty\/referrals$/);
  assert.equal(await nav.locator('[aria-current="page"]').getAttribute('href'),'/portal/faculty/referrals');
});
await h.check('phone-more-link-navigates-and-closes-drawer', '/portal', navigationWorld(profiles.Student).options({mobile:true}), async page=>{
  const nav=await menu(page);
  await nav.getByRole('button',{name:/^More,/}).click();
  await nav.getByRole('link',{name:'Academic record',exact:true}).click();
  await page.waitForURL(/\/portal\/academic-record$/);
  await h.hidden(page.getByRole('dialog',{name:'Portal navigation'}));
  assert.equal(await page.getByRole('button',{name:'Open portal navigation'}).evaluate(x=>x===document.activeElement),true);
  await menu(page);
  assert.equal(await nav.getByRole('button',{name:/^More,/}).getAttribute('aria-expanded'),'true');
  assert.equal(await nav.locator('[aria-current="page"]').getAttribute('href'),'/portal/academic-record');
});
await h.finish();
