import { SystemErrorPage } from "@/features/system/components/system-error-page";

export default function NotFound() {
  return (
    <SystemErrorPage
      code="404"
      title="That page isn’t here."
      description="We couldn’t find the page you’re looking for. Check the link or go back to COMPASS."
    />
  );
}
