import { MfaSecurityPanel } from "@/features/auth/security/mfa-security-panel";
import { PasswordChangePanel } from "@/features/auth/security/password-change-panel";
import { SessionList } from "@/features/auth/sessions/session-list";
import { TrustedBrowserList } from "@/features/auth/sessions/trusted-browser-list";

export default function AccountSecurityPage() {
  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="font-heading text-3xl font-bold tracking-tight">Account security</h1>
        <p className="max-w-2xl text-muted-foreground">
          Review the security settings and browser access tied to your COMPASS account.
        </p>
      </header>

      <div className="grid gap-6">
        <MfaSecurityPanel />
        <PasswordChangePanel />
        <SessionList />
        <TrustedBrowserList />
      </div>
    </div>
  );
}
