"use client";

import { ContextHelp } from "@/components/ui/context-help";

export function FollowupsHelp() {
  return <ContextHelp title="Guidance Follow-Ups" sections={[
    { heading: "Next actions and responsibility", content: <p>Record the next action needed to support a Student and assign a responsible staff member. Set a due date in Philippine Time. Due soon means the next seven days.</p> },
    { heading: "Progress", content: <p>Record activity while work is pending. Complete the Follow-Up with an outcome, or cancel it with a reason. Completed and cancelled records remain in the history.</p> },
    { heading: "Completion and further action", content: <p>Completing a Follow-Up ends that task. It does not close the related record. If more work is needed, create a new Follow-Up.</p> },
    { heading: "Creating the next action", content: <p>Create next action keeps the same Student, case and related record, with a link to the preceding task. Choose a new action title, responsible staff member and deadline. If the related record is unavailable, this continuation is unavailable too.</p> },
    { heading: "Confidentiality", content: <p>Counseling next actions can start from a case, Counseling Encounter or Routine Interview. Case-only tasks stay with the primary Counselor. A linked case does not expand access to a task created from a professional record.</p> },
    { heading: "Notifications", content: <p>Follow-Ups do not automatically contact the Student. Assigned staff may receive in-app notices when responsibility or the due date changes. Email and push delivery depend on the Office’s notification settings.</p> },
    { heading: "When you can't open a related record", content: <p>An operational task may remain available when its related record is unavailable. Review whether the work is still needed. Completing or cancelling the task keeps the related record&apos;s own status.</p> },
  ]} />;
}
