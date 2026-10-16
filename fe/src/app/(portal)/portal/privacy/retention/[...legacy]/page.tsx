import { redirect } from "next/navigation";

// Former rule and disposition-case bookmarks (ADR-115). Those workspaces are retired; the
// read-only Retention Policies page replaces them.
export default function Page() {
  redirect("/portal/privacy/retention");
}
