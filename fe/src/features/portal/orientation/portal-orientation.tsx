"use client";

import { Compass } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { createContext, useContext, useEffect, useCallback, useRef, useState, type ReactNode } from "react";

import { PageAction } from "@/components/ui/page-action";
import { useUnsavedNavigation } from "@/features/form-safety/unsaved-changes-provider";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { taskGuideAccess } from "./task-guide-access";
import { guideOnPage, taskGuides, taskGuideSteps, type TaskGuideDefinition, type TaskGuideId } from "./task-guide-definitions";
import { readTaskPreference, saveTaskPreference } from "./guide-preference";
import { OrientationGuide } from "./orientation-guide";
import { readGuidePreference, saveGuidePreference, type GuidePreference } from "./guide-preference";

const OrientationContext = createContext<{ launch: (opener: HTMLElement) => void; preference: GuidePreference; guides: readonly TaskGuideDefinition[]; preferences: Partial<Record<TaskGuideId, GuidePreference>>; launchTask: (id: TaskGuideId, opener: HTMLElement, catalog?: boolean) => void } | null>(null);

export function PortalOrientationProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, session } = usePortalSession();
  const query = useSearchParams().toString();
  const access = taskGuideAccess(user);
  const guides = taskGuides.filter(guide => access[guide.id]);
  const sessionKey = `${user.id}:${session.id}`; // In-memory only; never persisted.
  const [preferences, setPreferences] = useState<Partial<Record<TaskGuideId, GuidePreference>>>({});
  const { confirmNavigation } = useUnsavedNavigation();
  const [request, setRequest] = useState<{ opener: HTMLElement; from: string; destination: string; id?: TaskGuideId; session: string; query: string } | null>(null);
  const [preference, setPreference] = useState<GuidePreference>("new");
  const root = useRef<HTMLDivElement>(null);
  if (request && pathname === request.destination && request.from !== request.destination) {
    setRequest({ ...request, from: request.destination, query });
  }
  useEffect(() => {
    const frame = requestAnimationFrame(() => { setPreference(readGuidePreference()); setPreferences(Object.fromEntries(taskGuides.map(guide => [guide.id, readTaskPreference(guide.id, guide.version)]))); });
    return () => cancelAnimationFrame(frame);
  }, []);

  function launch(opener: HTMLElement, destination = "/portal", id?: TaskGuideId) {
    // Never compete with a privacy/security dialog, navigation drawer, or account menu.
    if (document.querySelector('[aria-modal="true"], [role="menu"], [popover]:popover-open, dialog[open]')) return;
    if (!confirmNavigation(destination)) return;
    setRequest({ opener, from: pathname, destination, id, session: sessionKey, query });
    if (pathname !== destination) router.push(destination);
  }

  function launchTask(id: TaskGuideId, opener: HTMLElement, catalog = false) {
    const guide = guides.find(guide => guide.id === id);
    if (guide && (catalog || guideOnPage(guide, pathname))) launch(opener, catalog ? guide.entry : pathname, id);
  }

  function finish(completed: boolean) {
    if (request?.id) {
      const guide = taskGuides.find(guide => guide.id === request.id);
      if (guide) {
        const next = completed || preferences[guide.id] === "completed" ? "completed" : "dismissed";
        saveTaskPreference(guide.id, guide.version, next);
        setPreferences(previous => ({ ...previous, [guide.id]: next }));
      }
      setRequest(null);
      return;
    }
    const next = completed ? "completed" : preference === "completed" ? "completed" : "dismissed";
    saveGuidePreference(next);
    setPreference(next);
    setRequest(null);
  }

  const valid = request && request.session === sessionKey && (!request.id || guides.some(guide => guide.id === request.id));
  const invalidRoute = request && (pathname !== request.destination && pathname !== request.from || request.from === request.destination && query !== request.query);
  return <OrientationContext.Provider value={{ launch: opener => launch(opener), preference, guides, preferences, launchTask }}>
    <div ref={root} className="contents">
      {children}
      {request && valid && !invalidRoute && pathname === request.destination ? <OrientationLaunch definition={guides.find(guide => guide.id === request.id)} root={root} opener={request.opener} onFinish={finish} /> : null}
      {/* A route change after launch ends the guide instead of teaching over another workspace. */}
      {request && (!valid || invalidRoute) ? <CancelOrientation onCancel={() => setRequest(null)} /> : null}
    </div>
  </OrientationContext.Provider>;
}

function OrientationLaunch({ definition, ...props }: React.ComponentProps<typeof OrientationGuide> & { definition?: TaskGuideDefinition }) {
  const { root, onFinish } = props;
  const resolveSteps = useCallback((root: HTMLElement) => definition ? taskGuideSteps(root, definition) : [], [definition]);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    // Let the router finish its own page focus before the optional guide takes focus.
    let second = 0;
    const show = () => {
      if (!definition || root.current && taskGuideSteps(root.current, definition).length) setReady(true);
    };
    const first = requestAnimationFrame(() => { second = requestAnimationFrame(show); });
    // A destination's Suspense/loading view can precede its source-owned launch control.
    // Wait for that control instead of dismissing an explicit catalog launch during navigation.
    const observer = new MutationObserver(show);
    if (root.current) observer.observe(root.current, { childList: true, subtree: true });
    const timeout = window.setTimeout(() => {
      if (definition && root.current && !taskGuideSteps(root.current, definition).length) onFinish(false);
    }, 10000);
    return () => { cancelAnimationFrame(first); cancelAnimationFrame(second); observer.disconnect(); clearTimeout(timeout); };
  }, [definition, root, onFinish]);
  return ready ? <OrientationGuide {...props} title={definition?.title} resolveSteps={definition ? resolveSteps : undefined} /> : null;
}

function CancelOrientation({ onCancel }: { onCancel: () => void }) {
  useEffect(() => { onCancel(); }, [onCancel]);
  return null;
}

export function useOptionalPortalOrientation() { return useContext(OrientationContext); }

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
