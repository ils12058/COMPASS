"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { AuthShell } from "@/features/auth/components/auth-shell";
import { RecoveryCodesPanel } from "@/features/auth/components/recovery-codes-panel";
import { TotpSetup } from "@/features/auth/components/totp-setup";
import { LoginForm, type LoginCredentials } from "@/features/auth/login/login-form";
import {
  LoginMfaForm,
  type LoginMfaMethod,
} from "@/features/auth/login/login-mfa-form";
import { friendlyAuthError, getApiErrorCode } from "@/features/auth/utils/errors";
import { getSafeInternalPath } from "@/features/auth/utils/redirect";
import {
  getAuthGetSessionQueryKey,
  useAuthConfirmMandatoryTotpBootstrap,
  useAuthLogin,
  useAuthStartMandatoryTotpBootstrap,
  useAuthVerifyLoginMfa,
} from "@/lib/api/generated/auth/auth";
import type { TOTPSetupResponse } from "@/lib/api/generated/model";

type LoginStage = "login" | "mfa" | "mandatory_setup" | "recovery_codes";

const GENERIC_LOGIN_ERROR =
  "Sign-in was not successful. Check your details and security verification, then try again.";

export function LoginScreen() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const destination = getSafeInternalPath(searchParams.get("next"));

  const login = useAuthLogin();
  const verifyMfa = useAuthVerifyLoginMfa();
  const startMandatoryTotp = useAuthStartMandatoryTotpBootstrap();
  const confirmMandatoryTotp = useAuthConfirmMandatoryTotpBootstrap();

  const [stage, setStage] = useState<LoginStage>("login");
  const [mfaMethods, setMfaMethods] = useState<string[]>([]);
  const [challengeExpiresAt, setChallengeExpiresAt] = useState<string | null>(null);
  const [totpSetup, setTotpSetup] = useState<TOTPSetupResponse | null>(null);
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function finishAuthentication() {
    await queryClient.invalidateQueries({ queryKey: getAuthGetSessionQueryKey() });
    router.replace(destination);
  }

  async function submitLogin(credentials: LoginCredentials) {
    setError(null);
    setNotice(null);

    try {
      const response = await login.mutateAsync({
        data: {
          email: credentials.email,
          password: credentials.password,
          trust_browser: credentials.trustBrowser,
          turnstile_token: credentials.turnstileToken,
        },
      });

      if (response.data.authenticated) {
        await finishAuthentication();
        return;
      }

      if (response.data.mfa_required) {
        setMfaMethods(response.data.mfa_methods);
        setChallengeExpiresAt(response.data.challenge_expires_at ?? null);
        setStage("mfa");
        return;
      }

      setError(GENERIC_LOGIN_ERROR);
    } catch (caught) {
      if (getApiErrorCode(caught) === "mfa_setup_required") {
        try {
          const setup = await startMandatoryTotp.mutateAsync();
          setTotpSetup(setup.data);
          setStage("mandatory_setup");
        } catch (setupError) {
          setError(
            friendlyAuthError(
              setupError,
              "Two-step verification setup could not be started. Please sign in again.",
            ),
          );
        }
      } else if (
        getApiErrorCode(caught) === "rate_limited" ||
        getApiErrorCode(caught) === "security_unavailable"
      ) {
        setError(friendlyAuthError(caught, GENERIC_LOGIN_ERROR));
      } else {
        setError(GENERIC_LOGIN_ERROR);
      }
    }
  }

  async function submitMfa(method: LoginMfaMethod, code: string) {
    setError(null);

    try {
      const response = await verifyMfa.mutateAsync({
        data: { method, code },
      });

      if (!response.data.authenticated) {
        setError("That verification code could not be used. Please try again.");
        return;
      }

      await finishAuthentication();
    } catch (caught) {
      setError(
        getApiErrorCode(caught) === "mfa_failed"
          ? "That verification code could not be used. Please try again."
          : friendlyAuthError(caught, "Two-step verification could not be completed."),
      );
    }
  }

  async function confirmMandatoryTotpCode(code: string) {
    setError(null);

    try {
      const response = await confirmMandatoryTotp.mutateAsync({ data: { code } });
      setTotpSetup(null);
      setRecoveryCodes(response.data.recovery_codes);
      setStage("recovery_codes");
    } catch (caught) {
      setError(
        friendlyAuthError(
          caught,
          "The authenticator code could not be verified. Please try again.",
        ),
      );
    }
  }

  if (stage === "mandatory_setup" && totpSetup) {
    return (
      <AuthShell
        title="Secure your COMPASS account"
        description="Your account needs two-step verification before you can sign in."
      >
        <TotpSetup
          setup={totpSetup}
          busy={confirmMandatoryTotp.isPending}
          error={error}
          onConfirm={confirmMandatoryTotpCode}
        />
      </AuthShell>
    );
  }

  if (stage === "recovery_codes") {
    return (
      <AuthShell
        title="Save your recovery codes"
        description="Keep these codes safe before returning to sign in."
      >
        <RecoveryCodesPanel
          codes={recoveryCodes}
          onDone={() => {
            setRecoveryCodes([]);
            setChallengeExpiresAt(null);
            setStage("login");
            setNotice(
              "Two-step verification is ready. Sign in again to continue.",
            );
          }}
        />
      </AuthShell>
    );
  }

  if (stage === "mfa") {
    return (
      <AuthShell
        title="Two-step verification"
        description="Enter your verification code to finish signing in."
      >
        <LoginMfaForm
          methods={mfaMethods}
          challengeExpiresAt={challengeExpiresAt}
          busy={verifyMfa.isPending}
          error={error}
          onSubmit={submitMfa}
          onStartOver={() => {
            setMfaMethods([]);
            setChallengeExpiresAt(null);
            setError(null);
            setStage("login");
          }}
        />
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Sign in to COMPASS"
      description="Sign in with your UCN email to continue."
    >
      <LoginForm
        busy={login.isPending || startMandatoryTotp.isPending}
        error={error}
        notice={notice}
        onSubmit={submitLogin}
      />
    </AuthShell>
  );
}
