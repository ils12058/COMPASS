"use client";

import { Compass } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";

import { PageAction } from "@/components/ui/page-action";
import { useUnsavedNavigation } from "@/features/form-safety/unsaved-changes-provider";
import { OrientationGuide } from "./orientation-guide";
import { readGuidePreference, saveGuidePreference, type GuidePreference } from "./guide-preference";

const OrientationContext = createContext<{ launch: (opener: HTMLElement) => void; preference: GuidePreference } | null>(null);

export function PortalOrientationProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { confirmNavigation } = useUnsavedNavigation();
  const [request, setRequest] = useState<{ opener: HTMLElement; from: string } | null>(null);
  const [preference, setPreference] = useState<GuidePreference>("new");
  const root = useRef<HTMLDivElement>(null);
  if (request && pathname === "/portal" && request.from !== "/portal") {
    setRequest({ ...request, from: "/portal" });
  }
  useEffect(() => {
    const frame = requestAnimationFrame(() => setPreference(readGuidePreference()));
    return () => cancelAnimationFrame(frame);
  }, []);

  function launch(opener: HTMLElement) {
    // Never compete with a privacy/security dialog, navigation drawer, or account menu.
    if (document.querySelector('[aria-modal="true"], [role="menu"], [popover]:popover-open, dialog[open]')) return;
    if (!confirmNavigation("/portal")) return;
    setRequest({ opener, from: pathname });
    if (pathname !== "/portal") router.push("/portal");
  }

  function finish(completed: boolean) {
    const next = completed ? "completed" : preference === "completed" ? "completed" : "dismissed";
    saveGuidePreference(next);
    setPreference(next);
    setRequest(null);
  }

  return <OrientationContext.Provider value={{ launch, preference }}>
    <div ref={root} className="contents">
      {children}
      {request && pathname === "/portal" ? <OrientationLaunch root={root} opener={request.opener} onFinish={finish} /> : null}
      {/* A route change after launch ends the guide instead of teaching over another workspace. */}
      {request && pathname !== "/portal" && pathname !== request.from ? <CancelOrientation onCancel={() => setRequest(null)} /> : null}
    </div>
  </OrientationContext.Provider>;
}

function OrientationLaunch(props: React.ComponentProps<typeof OrientationGuide>) {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    // Let the router finish its own page focus before the optional guide takes focus.
    let second = 0;
    const first = requestAnimationFrame(() => { second = requestAnimationFrame(() => setReady(true)); });
    return () => { cancelAnimationFrame(first); cancelAnimationFrame(second); };
  }, []);
  return ready ? <OrientationGuide {...props} /> : null;
}

function CancelOrientation({ onCancel }: { onCancel: () => void }) {
  useEffect(() => { onCancel(); }, [onCancel]);
  return null;
}

export function usePortalOrientation() {
  const context = useContext(OrientationContext);
  if (!context) throw new Error("Portal orientation requires the portal shell.");
  return context;
}

export function HomeGuideAction() {
  const orientation = useContext(OrientationContext);
  if (!orientation) return null;
  return <PageAction variant="secondary" icon={Compass} label="Guide" labelDetail="to getting around COMPASS"
    data-orientation="guide-launch" onClick={event => orientation.launch(event.currentTarget)} />;
}
