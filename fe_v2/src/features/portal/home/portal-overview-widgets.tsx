"use client";

import { useSyncExternalStore } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  Bell,
  CalendarDays,
  CircleUserRound,
  Clock,
  HeartHandshake,
  LifeBuoy,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import type { UserSummary } from "@/lib/api/generated/model";
import { getPortalInitials } from "@/features/portal/portal-identity";

export type PortalCapabilityWidgetDefinition = {
  capability: string;
  title: string;
  description: string;
  icon: LucideIcon;
};

const PORTAL_CAPABILITY_WIDGETS: readonly PortalCapabilityWidgetDefinition[] = [
  {
    capability: "student_support.view",
    title: "Support options",
    description: "Review support options available for your next step.",
    icon: LifeBuoy,
  },
  {
    capability: "appointments.view_self",
    title: "Appointments",
    description: "Keep track of requests and scheduled meetings.",
    icon: CalendarDays,
  },
  {
    capability: "services.view",
    title: "Services",
    description: "Review service options available for your account.",
    icon: Sparkles,
  },
  {
    capability: "counseling.view_assigned",
    title: "Counseling work",
    description: "Review counseling work assigned to you.",
    icon: HeartHandshake,
  },
];

export function getPortalCapabilityWidgets(
  capabilities: readonly string[],
) {
  return PORTAL_CAPABILITY_WIDGETS.filter((widget) =>
    capabilities.includes(widget.capability),
  );
}

function getDateParts(date: Date) {
  return {
    day: new Intl.DateTimeFormat(undefined, {
      weekday: "long",
      month: "short",
      day: "numeric",
    }).format(date),
    time: new Intl.DateTimeFormat(undefined, {
      hour: "numeric",
      minute: "2-digit",
    }).format(date),
  };
}

type ClockListener = () => void;

let portalClockNow: Date | null = null;
let portalClockTimer: number | undefined;
const portalClockListeners = new Set<ClockListener>();

function subscribeToPortalClock(listener: ClockListener) {
  portalClockListeners.add(listener);

  if (portalClockListeners.size === 1) {
    portalClockNow = new Date();
    portalClockTimer = window.setInterval(() => {
      portalClockNow = new Date();
      portalClockListeners.forEach((clockListener) => clockListener());
    }, 30_000);
  }

  return () => {
    portalClockListeners.delete(listener);

    if (portalClockListeners.size === 0 && portalClockTimer !== undefined) {
      window.clearInterval(portalClockTimer);
      portalClockTimer = undefined;
      portalClockNow = null;
    }
  };
}

function getPortalClockSnapshot() {
  return portalClockNow;
}

function getPortalClockServerSnapshot() {
  return null;
}

export function PortalDateTimeWidget() {
  const now = useSyncExternalStore(
    subscribeToPortalClock,
    getPortalClockSnapshot,
    getPortalClockServerSnapshot,
  );

  const dateParts = now ? getDateParts(now) : null;

  return (
    <div className="rounded-2xl border border-[var(--compass-border)] bg-white/95 p-5 text-foreground shadow-sm">
      <div className="flex items-center gap-2 text-[var(--compass-brand-maroon)]">
        <Clock aria-hidden="true" className="size-4" />
        <p className="text-xs font-bold uppercase tracking-[0.14em]">Today</p>
      </div>
      {dateParts ? (
        <>
          <p className="mt-4 font-heading text-2xl font-bold">{dateParts.day}</p>
          <p className="mt-1 text-sm text-muted-foreground">{dateParts.time}</p>
        </>
      ) : (
        <div className="mt-4 space-y-2" aria-hidden="true">
          <div className="h-8 w-3/4 animate-pulse rounded-lg bg-muted" />
          <div className="h-4 w-1/3 animate-pulse rounded-lg bg-muted" />
        </div>
      )}
    </div>
  );
}

type PortalAccountWidgetProps = {
  name: string;
  photoUrl?: string | null;
  role: string;
  user: UserSummary;
};

export function PortalAccountWidget({
  name,
  photoUrl,
  role,
  user,
}: PortalAccountWidgetProps) {
  return (
    <div className="rounded-2xl border border-[var(--compass-border)] bg-white/95 p-5 text-foreground shadow-sm">
      <div className="flex items-center gap-3">
        <Avatar size="lg" className="size-14">
          {photoUrl ? <AvatarImage src={photoUrl} alt="" /> : null}
          <AvatarFallback className="bg-[var(--compass-brand-maroon)] text-base font-bold text-white">
            {getPortalInitials(user)}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[var(--compass-brand-maroon)]">
            <CircleUserRound aria-hidden="true" className="size-4" />
            <p className="text-xs font-bold uppercase tracking-[0.14em]">Account</p>
          </div>
          <h3 className="mt-1 truncate font-heading text-lg font-bold">{name}</h3>
          <p className="truncate text-sm text-muted-foreground">{role}</p>
        </div>
      </div>
      <Link
        href="/portal/account"
        className="group mt-5 inline-flex items-center gap-2 text-sm font-bold text-[var(--compass-brand-maroon)] underline-offset-4 hover:underline"
      >
        View profile
        <ArrowUpRight
          aria-hidden="true"
          className="size-4 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
        />
      </Link>
    </div>
  );
}

export function PortalNotificationWidget({
  unreadCount,
}: {
  unreadCount: number;
}) {
  return (
    <Link
      href="/portal/notifications"
      className="group rounded-2xl border border-[var(--compass-border)] bg-white/95 p-5 text-foreground shadow-sm transition-transform hover:-translate-y-0.5 hover:bg-white"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-[var(--compass-brand-maroon)]">
          <Bell aria-hidden="true" className="size-4" />
          <p className="text-xs font-bold uppercase tracking-[0.14em]">Notifications</p>
        </div>
        {unreadCount ? (
          <span className="rounded-full bg-[var(--compass-brand-gold)]/20 px-2 py-1 text-xs font-bold text-[var(--compass-brand-maroon)]">
            {unreadCount} new
          </span>
        ) : null}
      </div>
      <p className="mt-3 text-sm leading-6 text-muted-foreground">
        Check messages and reminders waiting for you.
      </p>
      <span className="mt-4 inline-flex items-center gap-2 text-sm font-bold text-[var(--compass-brand-maroon)]">
        View notifications
        <ArrowUpRight
          aria-hidden="true"
          className="size-4 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
        />
      </span>
    </Link>
  );
}

export function PortalCapabilityWidget({
  widget,
}: {
  widget: PortalCapabilityWidgetDefinition;
}) {
  const Icon = widget.icon;

  return (
    <article className="rounded-3xl border bg-card p-6 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div className="flex size-11 items-center justify-center rounded-2xl bg-[var(--compass-brand-maroon)]/10 text-[var(--compass-brand-maroon)]">
          <Icon aria-hidden="true" className="size-5" />
        </div>
        <span className="rounded-full bg-[var(--compass-support-soft)] px-2.5 py-1 text-xs font-bold text-[var(--compass-support-strong)]">
          Available
        </span>
      </div>
      <h3 className="mt-5 font-heading text-xl font-bold text-foreground">
        {widget.title}
      </h3>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        {widget.description}
      </p>
    </article>
  );
}
