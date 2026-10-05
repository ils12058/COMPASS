import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";

export function GraduationGoodMoralPrerequisite() {
  return <Notice tone="warning" action={<Link href="/portal/exit-interviews" className={buttonVariants({ variant: "secondary" })}>Open Exit Interview</Link>}>
    Complete and submit your Exit Interview before requesting your graduation Good Moral certificate.
  </Notice>;
}
