import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import ts from 'typescript';
import { createElement as h } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { CompassApiError } from '../src/lib/api/errors.ts';
import { activityErrorMessage } from '../src/features/activity/activity-errors.ts';
import { privacyErrorMessage } from '../src/features/privacy-governance/privacy-governance-errors.ts';
import { exitInterviewErrorMessage } from '../src/features/exit-interviews/exit-interview-shared.tsx';
import { inventoryErrorMessage, InventoryQueryError } from '../src/features/inventory/inventory-shared.tsx';
import { referralErrorMessage, ReferralQueryError, ReferralListSkeleton, uncertainReferralMutation } from '../src/features/referrals/referrals-shared.tsx';
import { callSlipErrorMessage, CallSlipListSkeleton, uncertainCallSlipMutation } from '../src/features/call-slips/call-slips-shared.tsx';
import { routineErrorMessage, RoutineQueryError } from '../src/features/routine-interviews/routine-interviews-shared.tsx';
import { appointmentErrorMessage } from '../src/features/appointments/appointments-shared.tsx';
import { classifyBookingFailure, BOOKING_UNCONFIRMED } from '../src/features/appointments/appointment-booking-outcome.ts';
import { counselingErrorMessage } from '../src/features/counseling/counseling-shared.tsx';
import { servicesErrorMessage } from '../src/features/services/services-shared.tsx';
import { availabilityErrorMessage } from '../src/features/availability/availability-shared.tsx';
import { feedbackErrorMessage, feedbackSubmissionErrorMessage } from '../src/features/feedback/feedback-shared.tsx';
import { goodMoralErrorMessage, uncertainGoodMoralMutation } from '../src/features/good-moral/good-moral-shared.tsx';
import { graduateTracerErrorMessage } from '../src/features/graduate-tracer/graduate-tracer-shared.tsx';
import { authErrorMessage } from '../src/features/auth/utils/errors.ts';
import { accountErrorMessage } from '../src/features/account/components/account-errors.ts';
import { managedAccountError } from '../src/features/accounts/components/account-action.tsx';
import { organizationErrorMessage } from '../src/features/organization/components/organization-action.tsx';
import { institutionConfigurationErrorMessage } from '../src/features/institution-configuration/institution-action.tsx';
import { platformErrorMessage } from '../src/features/platform/platform-actions.tsx';
import { reportErrorMessage } from '../src/features/reports/reports-shared.tsx';
import { announcementErrorMessage } from '../src/features/announcements/announcement-errors.ts';
import { resourceErrorMessage } from '../src/features/resources/resource-errors.ts';
import { describeSendError } from '../src/features/guidance-messages/guidance-messages-errors.ts';
import { nextSendIntent, isUncertainSendFailure } from '../src/features/guidance-messages/guidance-message-send.ts';
import { PublicPageError } from '../src/features/public/shared/public-state.tsx';
import { PageActionLink } from '../src/components/ui/page-action.tsx';
import { Pencil } from 'lucide-react';
const privateMessage = 'PRIVATE-DIAGNOSTIC-SENTINEL capability.internal tenant=secret';
const api = (code, status = 422, details, message = privateMessage) => new CompassApiError({ status, body: { error: { code, message, details } }, headers: {}, method: 'POST', url: '/api/v1/synthetic' });
const fallback = 'This action could not be completed. Check the details before trying again.';
const producers = { activityErrorMessage, privacyErrorMessage, exitInterviewErrorMessage, inventoryErrorMessage, referralErrorMessage, callSlipErrorMessage, routineErrorMessage, appointmentErrorMessage, counselingErrorMessage, servicesErrorMessage, availabilityErrorMessage, feedbackErrorMessage, goodMoralErrorMessage, graduateTracerErrorMessage, authErrorMessage, accountErrorMessage, managedAccountError, organizationErrorMessage, institutionConfigurationErrorMessage, platformErrorMessage, reportErrorMessage, announcementErrorMessage, resourceErrorMessage };
for (const [name, produce] of Object.entries(producers))
    test(`${name}: unknown codes and non-API errors retain safe fallback`, () => {
        for (const error of [api('future_unknown_error', 500), new Error(privateMessage), api(undefined)])
            assert.equal(produce(error, fallback), fallback);
    });
const mappings = [
    [activityErrorMessage, 'invalid_privacy_activity_request', /Check the activity filters/],
    [activityErrorMessage, 'invalid_technical_activity_request', /Check the activity filters/],
    [activityErrorMessage, 'invalid_supervised_activity_request', /Check the activity filters/],
    [activityErrorMessage, 'invalid_pagination', /previous page or adjust the filters/],
    [activityErrorMessage, 'privacy_activity_export_too_large', /More than 10,000.*Narrow/],
    [activityErrorMessage, 'release_audit_unavailable', /cannot be released.*privacy audit/],
    [privacyErrorMessage, 'retention_state_changed', /Review the rule or case status/],
    [privacyErrorMessage, 'invalid_retention_rule', /category, trigger, disposition action, duration, code, label, and policy reference/],
    [privacyErrorMessage, 'invalid_disposition_hold', /240 characters.*Do not include sensitive/],
    [exitInterviewErrorMessage, 'exit_interview_opportunity_required', /Office needs to open an Exit Interview for you first/],
    [exitInterviewErrorMessage, 'exit_interview_opportunity_not_open', /no longer open.*Contact/],
    [exitInterviewErrorMessage, 'exit_interview_opportunity_conflict', /Review the access record or contact/],
    [inventoryErrorMessage, 'inventory_conflict', /Review your answers and inventory status/],
    [referralErrorMessage, 'invalid_referral_request', /Some referral details need attention/],
    [callSlipErrorMessage, 'invalid_call_slip_request', /Some call slip details need attention/],
    [routineErrorMessage, 'routine_interview_form_revision_unsupported', /can't be used.*Contact the Guidance Office administrator/],
    [appointmentErrorMessage, 'appointment_default_provider_unresolved', /could not be selected.*Choose an eligible counselor/],
    [counselingErrorMessage, 'counseling_invalid_request', /Some counseling details need attention/],
    [servicesErrorMessage, 'invalid_service_catalog_request', /Some service details need attention/],
    [availabilityErrorMessage, 'availability_conflict', /schedule is unavailable.*contact the institutional administrator/],
    [availabilityErrorMessage, 'invalid_availability_request', /Some schedule details need attention/],
    [authErrorMessage, 'csrf_failed', /security check expired.*Submit the form again/],
    [accountErrorMessage, 'csrf_failed', /security check expired.*Try again/],
    [platformErrorMessage, 'invalid_maintenance_request', /Some maintenance details need attention/],
];
for (const [produce, code, expected] of mappings)
    test(`${produce.name}/${code}: authoritative code-owned copy hides diagnostics`, () => {
        const text = produce(api(code), fallback);
        assert.match(text, expected);
        assert.doesNotMatch(text, /PRIVATE|capability\.internal|tenant=|payload|request contains/);
    });
for (const [produce, code] of [[referralErrorMessage, 'referral_not_permitted'], [callSlipErrorMessage, 'call_slip_not_permitted'], [counselingErrorMessage, 'counseling_resource_not_found'], [inventoryErrorMessage, 'inventory_not_found'], [exitInterviewErrorMessage, 'exit_interview_not_found']])
    test(`${produce.name}: concealed record remains unavailable`, () => {
        const text = produce(api(code, 404), fallback);
        assert.match(text, /unavailable|not available|could not be found|no longer available/);
        assert.doesNotMatch(text, /exists|another account|owner|tenant|capability/);
    });
test('Routine forbidden and not-found records preserve identical concealment', () => assert.equal(routineErrorMessage(api('routine_interview_not_found', 404), fallback), routineErrorMessage(api('routine_interview_not_permitted', 403), fallback)));
test('Privacy keeps useful structured visible field guidance and hides unknown paths', () => {
    const issue = (field) => api('validation_error', 422, [{ loc: ['body', field], msg: privateMessage }]);
    assert.equal(privacyErrorMessage(issue('effective_on'), fallback), '“Effective date” was not accepted. Check it and try again.');
    assert.match(privacyErrorMessage(issue('duration_days'), fallback, { duration_days: 'Whole elapsed days' }), /Whole elapsed days/);
    assert.equal(privacyErrorMessage(issue('internal_key_material'), fallback), 'Some values were not accepted. Review the form and try again.');
});
test('Existing bounded translations honor stable codes and reject unfamiliar messages', () => {
    assert.equal(announcementErrorMessage(api('invalid_announcement_input', 422, undefined, 'title is too long'), fallback), 'The title must be 200 characters or fewer.');
    assert.equal(resourceErrorMessage(api('invalid_resource_input'), fallback), fallback);
    assert.equal(announcementErrorMessage(api('unknown', 422, undefined, 'title is too long'), fallback), fallback);
    assert.equal(privacyErrorMessage(api('invalid_privacy_governance_input'), fallback), 'Some privacy record details were not accepted. Review them and try again.');
});
for (const status of [408, 500, 502, 503, 504])
    test(`Booking ${status}: unconfirmed with original intent retained`, () => assert.deepEqual(classifyBookingFailure(api('internal_error', status)), { step: 'review', message: BOOKING_UNCONFIRMED, uncertain: true, keepIntent: true }));
test('Booking rejection, key conflict, slot conflict and connection failure stay distinct', () => {
    assert.equal(classifyBookingFailure(api('invalid_appointment_request')).uncertain, false);
    assert.equal(classifyBookingFailure(api('idempotency_key_conflict', 409)).keepIntent, false);
    assert.equal(classifyBookingFailure(api('appointment_time_conflict', 409)).message, 'That time was just taken. Choose another available time.');
    assert.equal(classifyBookingFailure(new TypeError('offline')).keepIntent, true);
    assert.match(appointmentErrorMessage(api('idempotency_unavailable', 503), fallback), /Keep the same booking details/);
    assert.match(classifyBookingFailure(api('idempotency_unavailable', 503)).message, /Keep the same booking details/);
});
for (const code of ['idempotency_in_progress', 'idempotency_unavailable'])
    test(`Feedback ${code}: same-response recovery remains explicit`, () => {
        const text = feedbackErrorMessage(api(code, 503), fallback);
        assert.match(text, /same response/);
        assert.doesNotMatch(text, /not submitted|new submission|was not saved/);
    });
test('Feedback submission wording keeps authoritative known codes ahead of generic statuses', () => {
    for (const code of ['idempotency_in_progress', 'idempotency_unavailable', 'feedback_configuration_conflict', 'feedback_already_submitted', 'permission_denied']) {
        assert.equal(feedbackSubmissionErrorMessage(api(code, 503), fallback), feedbackErrorMessage(api(code, 503), fallback));
    }
});
test('Feedback generic failure requires status checking without promising unchanged identity', () => {
    for (const status of [408, 500, 503]) {
        const text = feedbackSubmissionErrorMessage(api('internal_error', status), fallback);
        assert.match(text, /could not be confirmed.*Check your feedback status.*contact/);
        assert.doesNotMatch(text, /not submitted|Retry the same|new submission|was not saved/);
    }
    assert.match(feedbackSubmissionErrorMessage(api('invalid_feedback_request'), fallback), /Review the form/);
    assert.match(feedbackErrorMessage(api('feedback_already_submitted', 409), fallback), /already been submitted/);
});
for (const status of [408, 500, 503])
    test(`Messages ${status}: unconfirmed send retains same-ID Retry`, () => {
        const error = api('internal_error', status);
        assert.equal(isUncertainSendFailure(error), true);
        const text = describeSendError(error, 'thread');
        assert.match(text, /could not confirm|could not be confirmed/);
        assert.doesNotMatch(text, /not sent/);
        const intent = { target: 'thread', body: 'Private synthetic text', clientMessageId: 'original' }, state = { kind: 'uncertain', intent };
        assert.equal(nextSendIntent(state, 'thread', intent.body, () => { throw Error('No new ID'); }), intent);
        assert.equal(nextSendIntent(state, 'thread', 'Edited', () => 'new'), null);
    });
test('Known Message validation rejection remains confirmed', () => {
    assert.match(describeSendError(api('validation_error', 422), 'thread'), /not sent.*4,000 characters/);
    assert.equal(isUncertainSendFailure(api('validation_error', 422)), false);
});
test('Prerequisites, linked records, controlled issuance dates and uncertainty keep their meaning', () => {
    assert.match(goodMoralErrorMessage(api('good_moral_exit_interview_required', 409), fallback), /Complete and submit your Exit Interview before requesting/);
    assert.match(referralErrorMessage(api('referral_active_call_slip_conflict', 409), fallback), /Void the Call Slip first/);
    assert.match(referralErrorMessage(api('referral_completed_call_slip_conflict', 409), fallback), /cannot be voided.*completed interview/);
    assert.match(counselingErrorMessage(api('counseling_finalized_routine_conflict', 409), fallback), /cannot be saved.*finalized Routine Interview/);
    for (const field of ['Official Receipt', 'Graduation']) {
        const text = `${field} date cannot be in the future. Correct the certificate details before issuance.`;
        assert.equal(goodMoralErrorMessage(api('good_moral_certificate_date_in_future', 409, undefined, text), fallback), text);
    }
    for (const uncertain of [uncertainReferralMutation, uncertainCallSlipMutation, uncertainGoodMoralMutation]) {
        assert.equal(uncertain(new Error('offline')), true);
        assert.equal(uncertain(api('internal_error', 500)), true);
        assert.equal(uncertain(api('invalid', 422)), false);
    }
});
test('Rendered query errors retain one alert, explicit Retry, and no diagnostics', () => {
    const nodes = [h(ReferralQueryError, { error: api('invalid_referral_request'), fallback, onRetry() { } }), h(InventoryQueryError, { error: api('inventory_conflict', 409), fallback, onRetry() { } }), h(PublicPageError, { message: "Couldn't load the announcement. Try again.", onRetry() { } }), h(RoutineQueryError, { message: routineErrorMessage(api('routine_interview_form_revision_unsupported', 409), fallback), onRetry() { } })];
    for (const node of nodes) {
        const html = renderToStaticMarkup(node);
        assert.equal((html.match(/role="alert"/g) ?? []).length, 1);
        assert.match(html, /<button[^>]*>Retry<\/button>/);
        assert.doesNotMatch(html, /PRIVATE|aria-live/);
    }
});
test('Ordinary loading copy has one sentence-case status announcement', () => {
    for (const [component, label] of [[ReferralListSkeleton, 'Loading referrals…'], [CallSlipListSkeleton, 'Loading call slips…']]) {
        const html = renderToStaticMarkup(h(component));
        assert.match(html, new RegExp(label));
        assert.equal((html.match(/role="status"/g) ?? []).length, 1);
        assert.match(html, /aria-busy="true"/);
    }
});
const src = new URL('../src/', import.meta.url);
function sourceFiles(dir) { return readdirSync(dir, { withFileTypes: true }).flatMap(item => item.name === 'generated' ? [] : item.isDirectory() ? sourceFiles(new URL(item.name + '/', dir)) : /\.tsx?$/.test(item.name) ? [new URL(item.name, dir)] : []); }
test('Raw API message reading stays confined to verified transport and bounded/controlled translators', () => {
    const allowed = new Set(['lib/api/errors.ts', 'features/announcements/announcement-errors.ts', 'features/resources/resource-errors.ts', 'features/privacy-governance/privacy-governance-errors.ts', 'features/good-moral/good-moral-shared.tsx']);
    for (const file of sourceFiles(src)) {
        const sf = ts.createSourceFile(file.pathname, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true);
        for (const statement of sf.statements)
            if (ts.isImportDeclaration(statement) && statement.importClause?.namedBindings && ts.isNamedImports(statement.importClause.namedBindings))
                for (const imported of statement.importClause.namedBindings.elements)
                    if ((imported.propertyName ?? imported.name).text === 'readApiErrorMessage')
                        assert.ok(allowed.has(path.relative(src.pathname, file.pathname)), `Review backend message display in ${file.pathname}`);
    }
});
test('Actual assessment commands render natural complete names and visible labels', () => {
    for (const [file, expected] of [['assessment-records-list.tsx', [['Record', 'assessment result'], ['Manage', 'assessment types']]], ['assessment-record-detail.tsx', [['Edit', 'assessment record']]]]) {
        const sf = ts.createSourceFile(file, readFileSync(new URL(`../src/features/assessment-records/${file}`, import.meta.url), 'utf8'), ts.ScriptTarget.Latest, true), pairs = [];
        function visit(node) {
            if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && node.tagName.getText(sf) === 'PageActionLink') {
                const props = Object.fromEntries(node.attributes.properties.filter(ts.isJsxAttribute).filter(a => a.initializer && ts.isStringLiteral(a.initializer)).map(a => [a.name.getText(sf), a.initializer.text]));
                const html = renderToStaticMarkup(h(PageActionLink, { ...props, href: props.href ?? '/synthetic-record/edit', icon: Pencil }));
                assert.match(html, /data-page-action-label=""/);
                assert.ok(props.label.trim());
                assert.match(html, new RegExp(`${props.label}<span class="sr-only"> ${props.labelDetail}`));
                pairs.push([props.label, props.labelDetail]);
            }
            ts.forEachChild(node, visit);
        }
        visit(sf);
        assert.deepEqual(pairs, expected);
    }
});
