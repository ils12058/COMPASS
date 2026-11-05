"use client";

import { ContextHelp } from "@/components/ui/context-help";

export function FollowupsHelp() {
  return <ContextHelp title="Guidance Follow-Ups" sections={[
    { heading: "Next actions and responsibility", content: <p>Record the next action needed to support a Student and assign a responsible staff member. Set a due date in Philippine Time. Due soon means the next seven days.</p> },
    { heading: "Progress", content: <p>Record activity while work is pending. Complete the follow-up with an outcome, or cancel it with a reason. Completed and cancelled records remain in the history.</p> },
    { heading: "Completion and further action", content: <p>Completing a follow-up ends that task. It does not close the related record. If more work is needed, create a new follow-up.</p> },
    { heading: "Creating the next follow-up", content: <p>The next follow-up is a separate task with its own responsible staff member and due date. When the related record is still available, the new task is linked to it and takes its classification from that record. When the related record is unavailable, the new task is created without a link and does not inherit the earlier task&apos;s confidential classification.</p> },
    { heading: "Confidentiality", content: <p>Operational follow-ups support staff coordination. Counselor-confidential records remain limited to the assigned Counselor with the relevant professional relationship.</p> },
    { heading: "Notifications", content: <p>Follow-Ups do not automatically contact the Student. Assigned staff may receive in-app notices when responsibility or the due date changes. Email and push delivery depend on the Office’s notification settings.</p> },
    { heading: "When a related record becomes unavailable", content: <p>The follow-up keeps its own status and remains independently owned. Only the link to the related record becomes unavailable. Completing or cancelling the follow-up records your decision and does not change the related record.</p> },
  ]} />;
}
