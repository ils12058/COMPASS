import Link from "next/link";
import ReactMarkdown from "react-markdown";

import { getSafeHttpUrl } from "@/features/public/shared/presentation";

export function PublicMarkdown({ children }: { children: string }) {
  return (
    <div className="public-markdown">
      <ReactMarkdown
        components={{
          a({ children: linkChildren, href }) {
            if (!href) return <span>{linkChildren}</span>;

            if (href.startsWith("/") && !href.startsWith("//")) {
              return <Link href={href}>{linkChildren}</Link>;
            }

            if (href.startsWith("#")) {
              return <a href={href}>{linkChildren}</a>;
            }

            const safeHref = getSafeHttpUrl(href);
            return safeHref ? (
              <a href={safeHref} target="_blank" rel="noopener noreferrer">
                {linkChildren}
              </a>
            ) : (
              <span>{linkChildren}</span>
            );
          },
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
