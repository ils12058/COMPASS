import assert from 'node:assert/strict';
import { test } from 'node:test';
import profiles from './support/f2-navigation-profiles.json' with { type: 'json' };
import expected from './support/f2-navigation-expected.json' with { type: 'json' };
import { portalNavigationGroups, portalWorkspaceGroups } from '../src/features/portal/components/portal-workspaces.ts';
import { portalCommandDestinations, searchPortalCommands } from '../src/features/portal/components/portal-command-destinations.ts';

const available = { can_confirm_student: true, can_submit_referral: true, can_view_submissions: true };
const hrefs = links => links.map(x => x.href);
const fields = links => links.map(({href, label}) => ({href, label}));
function reachability(user, availability) {
  // The untouched access registry is the before-list, also consumed by public quick access.
  const before = ['/portal', ...portalWorkspaceGroups(user, availability).flatMap(g => hrefs(g.links))];
  const {daily, secondary} = portalNavigationGroups(user, availability);
  const after = hrefs([...daily, ...secondary.links]);
  assert.deepEqual([...after].sort(), [...before].sort());
  assert.equal(new Set(after).size, after.length, 'No duplicate destinations');
  assert.ok(daily.length <= 7);
  const commands = portalCommandDestinations(user, availability);
  for (const href of after) assert.ok(commands.some(x => x.href === href), `Search retains ${href}`);
  return {daily, secondary};
}
for (const [role, profile] of Object.entries(profiles)) {
  test(`${role}: approved ordering and unchanged reachability, including available conditional roots`, () => {
    const user = {...profile, exit_interview_workspace_available: true};
    const {daily, secondary} = reachability(user, available);
    assert.deepEqual(fields(daily), expected[role].daily);
    assert.deepEqual(fields(secondary.links), expected[role].more);
    assert.equal(secondary.label, role === 'IT Admin' ? 'Administration' : 'More');
  });
  test(`${role}: every revoked grant, read-only, manage-only, empty and additive capabilities retain the registry set`, () => {
    const all = [...new Set(Object.values(profiles).flatMap(p => p.capabilities))];
    for (const capabilities of [[], profile.capabilities.filter(x=>x.includes('view')), profile.capabilities.filter(x=>!x.includes('view')), all,
      ...profile.capabilities.map(revoked=>profile.capabilities.filter(x=>x!==revoked)), ...all.map(grant=>[...new Set([...profile.capabilities, grant])])]) {
      for (const exit_interview_workspace_available of [false, true]) reachability({...profile, capabilities, exit_interview_workspace_available}, available);
    }
  });
}
test('Faculty availability combinations and absent availability keep independent submission/read gates', () => {
  for (const availability of [undefined, ...[false,true].flatMap(can_confirm_student=>[false,true].flatMap(can_submit_referral=>[false,true].map(can_view_submissions=>({can_confirm_student,can_submit_referral,can_view_submissions}))))]) {
    for (const capabilities of [[], ['referrals.submit_self'], ['referrals.view_submitted_self'], profiles.Faculty.capabilities]) reachability({...profiles.Faculty, capabilities}, availability);
  }
});
test('designation titles confer no workspace, and ordinary identities cannot gain confidential roots through ordering', () => {
  for (const name of ['Head']) {
    const withTitle = reachability({...profiles[name], capabilities: []});
    const withoutTitle = reachability({...profiles[name], capabilities: [], designations: []});
    assert.deepEqual(hrefs([...withTitle.daily, ...withTitle.secondary.links]).sort(), hrefs([...withoutTitle.daily, ...withoutTitle.secondary.links]).sort());
  }
  for (const name of ['Student','Alumni','Faculty','IT Admin']) {
    const user = {...profiles[name], designations: ['HEAD_GUIDANCE_COUNSELOR'], capabilities: [...new Set(Object.values(profiles).flatMap(p=>p.capabilities))]};
    const {daily, secondary} = reachability(user, available);
    assert.ok(!hrefs([...daily, ...secondary.links]).includes('/portal/assessment-records'));
  }
  reachability({...profiles['Institutional Officer'], designations: [], capabilities: ['privacy_governance.notices.manage']});
  reachability({...profiles['Institutional Officer'], capabilities: ['privacy_governance.activity.view']});
});
test('additional allowed roots append to More without displacing approved destinations', () => {
  const user = {...profiles.Counselor, capabilities: [...profiles.Counselor.capabilities, 'accounts.manage', 'platform_operations.view']};
  const {secondary} = reachability(user);
  assert.deepEqual(hrefs(secondary.links).slice(-2), ['/portal/accounts', '/portal/platform/health']);
});
test('renamed destinations retain their formal names as search aliases', () => {
  const index = portalCommandDestinations(profiles.Head);
  for (const [query, href] of [['Overview','/portal'], ['Individual Inventory','/portal/inventory'], ['Guidance operations','/portal/operations']]) {
    assert.ok(searchPortalCommands(index, query).some(x=>x.href===href), query);
  }
  assert.ok(searchPortalCommands(portalCommandDestinations(profiles['IT Admin']), 'Platform Operations').some(x=>x.href==='/portal/platform/health'));
});

test('CW-2 moves only the Counselor daily Follow-ups entry to More and preserves destination search', () => {
  const navigation = portalNavigationGroups(profiles.Counselor, available);
  assert.deepEqual(hrefs(navigation.daily), ['/portal', '/portal/work', '/portal/appointments', '/portal/messages', '/portal/counseling', '/portal/routine-interviews']);
  assert.equal(hrefs(navigation.secondary.links)[0], '/portal/follow-ups');
  assert.ok(searchPortalCommands(portalCommandDestinations(profiles.Counselor), 'Follow-ups').some(command => command.href === '/portal/follow-ups'));
  for (const role of ['Head', 'GOA']) {
    const other = portalNavigationGroups(profiles[role], available);
    assert.deepEqual(fields(other.daily), expected[role].daily);
    assert.deepEqual(fields(other.secondary.links), expected[role].more);
  }
});
