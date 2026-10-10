import { SystemErrorPage } from "@/features/system/components/system-error-page";

export default function NotFound() {
  return (
    <SystemErrorPage
      code="404"
      title="That page isn’t here."
      description="The address may be out of date, or the page may have moved."
    />
  );
}
