"use client";

import { ContextHelp } from "@/components/ui/context-help";

export function FollowupsHelp() {
  return <ContextHelp title="Guidance Follow-Ups" sections={[
    { heading: "Next actions and responsibility", content: <p>Record the next action needed to support a Student and assign a responsible staff member. Set a due date in Philippine Time. Due soon means the next seven days.</p> },
    { heading: "Progress", content: <p>Record activity while work is pending. Complete the Follow-Up with an outcome, or cancel it with a reason. Completed and cancelled records remain in the history.</p> },
    { heading: "Completion and further action", content: <p>Completing a Follow-Up ends that task. It does not close the related record. If more work is needed, create a new Follow-Up.</p> },
    { heading: "Creating the next Follow-Up", content: <ul className="list-disc space-y-2 pl-5"><li>Each new Follow-Up has its own staff member and due date. If you can still open the related record, it keeps that link and confidentiality setting.</li><li>If you can no longer open the related record, the new Follow-Up has no link and does not keep the earlier task&apos;s confidential classification.</li></ul> },
    { heading: "Confidentiality", content: <p>Staff Follow-Ups support coordination. Counselor-confidential records stay limited to the assigned Counselor with the relevant professional relationship.</p> },
    { heading: "Notifications", content: <p>Follow-Ups do not automatically contact the Student. Assigned staff may receive in-app notices when responsibility or the due date changes. Email and push delivery depend on the Office’s notification settings.</p> },
    { heading: "When you can't open a related record", content: <p>You can still complete or cancel the Follow-Up when you can no longer open its related record. Its owner and status stay the same until you act; completing or cancelling it does not change the related record.</p> },
  ]} />;
}
