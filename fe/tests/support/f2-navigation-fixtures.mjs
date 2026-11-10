// Synthetic baseline profiles from the approved F2 proposal (2026-11-10).
import profiles from './f2-navigation-profiles.json' with { type: 'json' };
import { homeWorld } from './ux15-home-fixtures.mjs';
export { profiles };
export function navigationWorld(profile, availability) {
  const state = homeWorld({ role: profile.role, lifecycle: profile.student_lifecycle_status, capabilities: profile.capabilities, designations: profile.designations, items: [] });
  state.account = structuredClone(profile);
  state.availabilityStatus = 200;
  state.availabilityHold = null;
  state.availability = availability ?? { can_confirm_student: false, can_submit_referral: false, can_view_submissions: false, valid_until: null };
  const handler = state.handler;
  state.handler = async (args) => {
    if (args.pathname === '/api/v1/faculty/referrals/availability') {
      if (state.availabilityHold) await state.availabilityHold;
      await args.reply(state.availabilityStatus === 200 ? state.availability : {error:{code:'unavailable',message:'Synthetic'}}, state.availabilityStatus); return true;
    }
    if (args.pathname === '/api/v1/faculty/referrals') { await args.reply({ items: [], page: 1, page_size: 20, has_next: false }); return true; }
    return handler(args);
  };
  const options = state.options;
  state.options = (extra = {}) => ({ ...options(extra), handler: state.handler });
  return state;
}
