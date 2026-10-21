import assert from 'node:assert/strict';
import { test } from 'node:test';
import { tracerRecord, graduate } from './support/ux15-tracer-fixtures.mjs';
import { graduateTracerDraftFromDetail, graduateTracerPayloadFromDraft, normalizeGraduateTracerDraft, getGraduateTracerDraftRowIssues, getGraduateTracerSubmissionIssues } from '../src/features/graduate-tracer/graduate-tracer-presentation.ts';
import { getGraduateTracerAccess } from '../src/features/graduate-tracer/graduate-tracer-access.ts';
const draft = () => graduateTracerDraftFromDetail(tracerRecord());
test('Synthetic survey fixtures satisfy existing submission and draft validators', () => {
  for (const employed of [true, false]) {
    const value = graduateTracerDraftFromDetail(tracerRecord(employed));
    assert.deepEqual(getGraduateTracerSubmissionIssues(value), []);
    assert.deepEqual(getGraduateTracerDraftRowIssues(value), []);
  }
});
for (const state of ['NOT_EMPLOYED', 'NEVER_EMPLOYED']) test(`${state} clears stale employed payload fields without changing applicable answers`, () => {
  const value = normalizeGraduateTracerDraft({ ...draft(), current_employment_state: state, present_employment_status: 'SELF_EMPLOYED', self_employed_college_skills: 'Synthetic', reasons_for_staying_other: 'Synthetic', first_job_duration_other: 'Synthetic', useful_competencies: ['OTHER'], useful_competencies_other: 'Synthetic', unemployment_reasons: ['ADVANCE_STUDY'] });
  const payload = JSON.parse(JSON.stringify(graduateTracerPayloadFromDraft(value)));
  for (const key of ['present_occupation', 'first_job_level', 'current_job_level', 'self_employed_college_skills', 'first_job_duration_other', 'useful_competencies_other']) assert.equal(key in payload, false, key);
  assert.deepEqual(payload.unemployment_reasons, ['ADVANCE_STUDY']);
  assert.deepEqual(getGraduateTracerSubmissionIssues(value), []);
});
test('Employed transitions clear unemployment and inactive Other answers', () => {
  const value = normalizeGraduateTracerDraft({ ...draft(), unemployment_reasons: ['OTHER'], unemployment_other_reason: 'Synthetic', present_employment_status: 'REGULAR_PERMANENT', self_employed_college_skills: 'Synthetic', advanced_study_reasons: [], advanced_study_other_reason: 'Synthetic' });
  assert.deepEqual(value.unemployment_reasons, []);
  for (const key of ['unemployment_other_reason', 'self_employed_college_skills', 'advanced_study_other_reason']) assert.equal(value[key], undefined);
});
test('First-job and curriculum switches clear only their inactive branch answers', () => {
  const first = { ...draft(), first_job_after_college: true, first_job_related_to_course: false, reasons_for_accepting_first_job: ['OTHER'], reasons_for_accepting_other: 'Synthetic', reasons_for_staying_on_job: ['SALARIES_BENEFITS'], useful_competencies: ['OTHER'], useful_competencies_other: 'Synthetic' };
  const unrelated = normalizeGraduateTracerDraft(first);
  assert.deepEqual(unrelated.reasons_for_accepting_first_job, []);
  assert.deepEqual(unrelated.reasons_for_staying_on_job, ['SALARIES_BENEFITS']);
  assert.deepEqual(unrelated.useful_competencies, []);
  const laterJob = normalizeGraduateTracerDraft({ ...first, first_job_after_college: false });
  assert.deepEqual(laterJob.reasons_for_staying_on_job, []);
  assert.equal(laterJob.first_job_related_to_course, undefined);
});
test('Partial drafts retain separate row constraints and final submission requirements', () => {
  const partial = { ...draft(), name: '', email: '', current_employment_state: undefined, graduated_college_id: null, graduated_program_id: null, graduation_year: null, education: [], trainings: [], professional_exams: [], curriculum_improvement_suggestions: '' };
  assert.deepEqual(getGraduateTracerDraftRowIssues(partial), []);
  const issues = getGraduateTracerSubmissionIssues(partial);
  for (const target of ['gts-name', 'gts-employment-state', 'gts-add-degree', 'gts-graduated-college']) assert.ok(issues.some(issue => issue.targetId === target));
  assert.equal(issues.some(issue => /suggestion|mobile|email/.test(issue.targetId)), false);
  const rows = { ...partial, education: [{ degree_and_specialization: '', college_or_university: '', year_graduated: '', formKey: 'stable' }], trainings: [{ title: '', formKey: 'training' }] };
  assert.deepEqual(getGraduateTracerDraftRowIssues(rows).map(issue => issue.targetId), ['degree-0-name', 'degree-0-institution', 'degree-0-year', 'training-0-title']);
});
test('Historical graduation summaries still map to IDs and row keys never enter payloads', () => {
  const value = graduateTracerDraftFromDetail({ ...tracerRecord(), graduated_college_id: undefined, graduated_program_id: undefined });
  assert.equal(value.graduated_college_id, 'college-a'); assert.equal(value.graduated_program_id, 'program-a');
  const payload = graduateTracerPayloadFromDraft(value);
  assert.equal(JSON.stringify(payload).includes('formKey'), false); assert.equal(typeof payload.education[0].year_graduated, 'number');
  assert.equal(payload.professional_exams[0].date_taken, null);
});
test('Eligibility still requires GRADUATED and self capabilities; reviewer access stays separate', () => {
  assert.equal(getGraduateTracerAccess(graduate).canManageSelf, true);
  for (const state of ['ENROLLED', 'EXITED', null]) assert.equal(getGraduateTracerAccess({ ...graduate, student_lifecycle_status: state }).hasStudentWorkspace, false);
  assert.equal(getGraduateTracerAccess({ ...graduate, capabilities: ['graduate_tracer.view_self'] }).canManageSelf, false);
  assert.equal(getGraduateTracerAccess({ ...graduate, role: 'COUNSELOR', capabilities: ['graduate_tracer.view'] }).hasOperationalWorkspace, true);
  assert.equal(getGraduateTracerAccess({ ...graduate, role: 'COUNSELOR', capabilities: ['graduate_tracer.view'] }).hasStudentWorkspace, false);
});
