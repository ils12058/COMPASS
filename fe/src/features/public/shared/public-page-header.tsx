import Image from "next/image";
import type { ReactNode } from "react";

// A public page's title band. A page may add one approved GCO character, which stands on the
// band's lower edge beside the title and is hidden on phones, where it would crowd the title.
export function PublicPageHeader({
  illustration,
  children,
}: {
  illustration?: { src: string; width: number; height: number };
  children: ReactNode;
}) {
  return (
    <div className="border-b border-brand-line bg-surface-raised">
      <div className="mx-auto max-w-6xl px-5 py-6 sm:px-8 sm:py-8">
        {illustration ? (
          <div className="flex items-end gap-4">
            <Image
              src={illustration.src}
              width={illustration.width}
              height={illustration.height}
              alt=""
              aria-hidden="true"
              className="-mb-8 hidden h-24 w-auto shrink-0 sm:block"
            />
            <div className="min-w-0">{children}</div>
          </div>
        ) : (
          children
        )}
      </div>
    </div>
  );
}
