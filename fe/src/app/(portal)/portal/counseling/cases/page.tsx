import { redirect } from "next/navigation";

// Cases are listed on the Counseling page itself.
export default function Page() {
  redirect("/portal/counseling");
}
