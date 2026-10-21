// Synthetic local responses only. The shared harness blocks external requests.
import { user } from './ui-hierarchy-fixtures.mjs';
import { sessionFor } from './guidance-messages-fixtures.mjs';
export const tracerPath = '/portal/graduate-tracer';
export const graduate = { ...user('STUDENT'), student_lifecycle_status: 'GRADUATED', capabilities: ['graduate_tracer.view_self', 'graduate_tracer.manage_self'] };
export const classifications = {
  colleges: [{ id: 'college-a', code: 'SYN-A', name: 'Synthetic College A' }, { id: 'college-b', code: 'SYN-B', name: 'Synthetic College B' }],
  programs: [{ id: 'program-a', code: 'SYN-BS', name: 'Synthetic Degree', college_id: 'college-a' }, { id: 'program-b', code: 'SYN-BA', name: 'Synthetic Other Degree', college_id: 'college-b' }],
};
export function tracerRecord(employed = true) {
  return {
    id: 'ux15-tracer', student_id: 'synthetic-graduate', instrument_schema_version: 1, status: 'DRAFT',
    created_at: '2026-10-20T01:00:00Z', updated_at: '2026-10-20T01:00:00Z', submitted_at: null,
    name: 'Synthetic Graduate', email: 'graduate@example.invalid', birth_date: '2000-01-01', province: 'Synthetic Province',
    permanent_address: 'Synthetic Address', telephone_contact_numbers: '', mobile_number: '', civil_status: 'SINGLE', sex: 'FEMALE', region_of_origin: 'REGION_5', residence_location: 'MUNICIPALITY',
    graduated_college_id: 'college-a', graduated_program_id: 'program-a', graduation_year: 2024,
    graduated_college: classifications.colleges[0], graduated_program: classifications.programs[0],
    education: [{ degree_and_specialization: 'Synthetic Degree', college_or_university: 'Synthetic University', year_graduated: 2024, honors_or_awards: '' }],
    professional_exams: [{ examination_name: 'Synthetic Examination', date_taken: null, rating: '' }],
    trainings: [{ title: 'Synthetic Training', duration_and_credits: '', institution: '' }],
    undergraduate_degree_reasons: ['PASSION_PROFESSION'], graduate_study_reasons: [], advanced_study_reasons: [],
    current_employment_state: employed ? 'EMPLOYED' : 'NOT_EMPLOYED',
    ...(employed ? { present_employment_status: 'REGULAR_PERMANENT', present_occupation: 'Synthetic occupation', employer_business_line: 'EDUCATION', place_of_work: 'LOCAL', first_job_after_college: false,
      first_job_duration: 'ONE_TO_SIX_MONTHS', first_job_source: 'ADVERTISEMENT', time_to_first_job: 'ONE_TO_SIX_MONTHS', first_job_level: 'RANK_CLERICAL', current_job_level: 'PROFESSIONAL_TECHNICAL_SUPERVISORY', initial_gross_monthly_earning: 'FROM_10000_TO_LT_15000', curriculum_relevant_to_first_job: false,
    } : { unemployment_reasons: ['ADVANCE_STUDY'] }),
    curriculum_improvement_suggestions: '',
  };
}
export function tracerFixture({ employed = true, partial = false, account = graduate, disposed = false, submitted = false, detailOverrides = {} } = {}) {
  let detail = tracerRecord(employed);
  if (partial) detail = { ...detail, name: '', birth_date: null, email: '', civil_status: null, sex: null, region_of_origin: null, province: '', residence_location: null, graduated_college_id: null, graduated_program_id: null, graduated_college: null, graduated_program: null, graduation_year: null, education: [], professional_exams: [], trainings: [], current_employment_state: null };
  if (submitted) detail = { ...detail, status: 'SUBMITTED', submitted_at: '2026-10-21T01:00:00Z' };
  detail = { ...detail, ...detailOverrides };
  const state = { writes: [], submissions: 0, reads: 0, failSave: 0, saveNetworkFailure: false, failRefresh: false, submitMode: 'ok', holdSave: null, holdSubmit: null, canonicalize: value => value };
  state.handler = async ({ pathname, method, request, reply, route }) => {
    if (pathname === '/api/v1/auth/session') { await reply(sessionFor(account)); return true; }
    if (pathname === '/api/v1/graduate-tracer/classification-options') { await reply(classifications); return true; }
    if (pathname === '/api/v1/graduate-tracer/me' && method === 'GET') {
      state.reads++;
      if (disposed) { await reply({ error: { code: 'graduate_tracer_disposed' } }, 410); return true; }
      if (state.failRefresh) { await reply({ error: { code: 'synthetic_failure' } }, 503); return true; }
      await reply(detail); return true;
    }
    if (pathname === '/api/v1/graduate-tracer/me' && method === 'PUT') {
      state.writes.push(JSON.parse(request.postData()));
      if (state.holdSave) await state.holdSave;
      if (state.saveNetworkFailure) { await route.abort('failed'); return true; }
      if (state.failSave) { await reply({ error: { code: state.failSave === 409 ? 'graduate_tracer_conflict' : 'synthetic_failure' } }, state.failSave); return true; }
      detail = state.canonicalize({ ...detail, ...state.writes.at(-1), updated_at: '2026-10-21T02:00:00Z' });
      await reply(detail); return true;
    }
    if (pathname === '/api/v1/graduate-tracer/me/submit') {
      state.submissions++;
      if (state.holdSubmit) await state.holdSubmit;
      if (state.submitMode !== 'unknown-draft') detail = { ...detail, status: 'SUBMITTED', submitted_at: '2026-10-21T03:00:00Z' };
      if (state.submitMode !== 'ok') { await reply({ error: { code: 'synthetic_failure' } }, 503); return true; }
      await reply(detail); return true;
    }
    return false;
  };
  return state;
}
