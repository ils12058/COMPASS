import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import Image from "next/image";
import { Panel, PanelHeader } from "@/components/ui/panel";

export function HomeShortcuts({ title, titleId, destinations, illustration }: {
  title: string; titleId: string; destinations: readonly { href: string; label: string; icon: LucideIcon }[];
  illustration?: string;
}) {
  if (!destinations.length) return null;
  return <Panel className="@container" aria-labelledby={titleId}>
    {illustration ? <div className="flex items-center gap-3 pb-1 pr-4 pt-3 sm:pr-5">
      <PanelHeader className="min-w-0 flex-1 border-b-0 py-0" title={title} titleId={titleId} />
      <Image src={illustration} width={512} height={512} alt="" aria-hidden="true" sizes="80px"
        className="hidden size-16 shrink-0 @min-[17rem]:block @min-[26rem]:size-20" />
    </div> : <PanelHeader className="border-b-0 pb-1" title={title} titleId={titleId} />}
    <ul className="grid gap-1 px-2 pb-3 @min-[24rem]:grid-cols-2 @min-[42rem]:grid-cols-3 sm:px-3">
      {destinations.map(({ href, label, icon: Icon }) => <li key={href} className="min-w-0">
        <Link href={href} className="flex min-h-11 min-w-0 items-center gap-3 rounded-md px-2 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus">
          <Icon size={18} className="shrink-0 text-brand" aria-hidden="true" /><span className="min-w-0 [overflow-wrap:anywhere]">{label}</span>
        </Link>
      </li>)}
    </ul>
  </Panel>;
}
