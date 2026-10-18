"use client";

import { ContextHelp } from "@/components/ui/context-help";

export function FollowupsHelp() {
  return <ContextHelp title="Guidance Follow-Ups" sections={[
    { heading: "Next actions and responsibility", content: <p>Record the next action needed to support a Student and assign a responsible staff member. Set a due date in Philippine Time. Due soon means the next seven days.</p> },
    { heading: "Progress", content: <p>Record activity while work is pending. Complete the follow-up with an outcome, or cancel it with a reason. Completed and cancelled records remain in the history.</p> },
    { heading: "Confidentiality", content: <p>Operational follow-ups support staff coordination. Counselor-confidential records remain limited to the assigned Counselor with the relevant professional relationship.</p> },
    { heading: "Notifications", content: <p>Follow-Ups do not automatically contact the Student. Assigned staff may receive in-app notices when responsibility or the due date changes. Email and push delivery depend on the Office’s notification settings.</p> },
  ]} />;
}
