import { Award, CalendarClock, ClipboardList, GraduationCap, MessageCircle, type LucideIcon } from "lucide-react";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { getGoodMoralAccess } from "@/features/good-moral/good-moral-access";
import { getGraduateTracerAccess } from "@/features/graduate-tracer/graduate-tracer-access";
import { getGuidanceMessagesAccess } from "@/features/guidance-messages/guidance-messages-access";
import { getInventoryAccess } from "@/features/inventory/inventory-access";
import type { UserSummary } from "@/lib/api/generated/model";

type StudentHomeDestination = { href: string; label: string; description: string; icon: LucideIcon };

// A small selection of existing workspaces, not a second navigation registry or an action list.
// Reading a workspace never implies permission to start a record, book a slot or submit a form.
export function getStudentHomeDestinations(user: UserSummary): StudentHomeDestination[] {
  if (user.role !== "STUDENT") return [];
  const destinations: StudentHomeDestination[] = [];
  if (getAppointmentAccess(user).canViewSelf) {
    destinations.push({ href: "/portal/appointments/my", icon: CalendarClock, label: "View appointments",
      description: "Check your scheduled and past appointments." });
  }
  if (getGuidanceMessagesAccess(user).canViewSelf) {
    destinations.push({ href: "/portal/messages", icon: MessageCircle, label: "Guidance Messages",
      description: "Open your conversations with Guidance." });
  }
  if (getGraduateTracerAccess(user).canViewSelf) {
    destinations.push({ href: "/portal/graduate-tracer", icon: GraduationCap, label: "Graduate Tracer",
      description: "Open your survey and saved response." });
  } else if (getInventoryAccess(user).canViewSelf) {
    destinations.push({ href: "/portal/inventory", icon: ClipboardList, label: "Individual Inventory",
      description: "View your Inventory and saved records." });
  }
  if (getGoodMoralAccess(user).canViewSelf) {
    destinations.push({ href: "/portal/good-moral", icon: Award, label: "Good Moral requests",
      description: "View your requests and their status." });
  }
  return destinations;
}
