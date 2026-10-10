import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { safeMarkdownUrl, safePublicUrl } from "@/features/public/utils";

const components: Components = {
  h1: ({ children }) => <h3>{children}</h3>,
  h2: ({ children }) => <h4>{children}</h4>,
  h3: ({ children }) => <h5>{children}</h5>,
  img: () => null,
  a: ({ href, children }) => {
    const safe = safePublicUrl(href);
    if (!safe) {
      return <span>{children}</span>;
    }

    const external = /^https?:\/\//i.test(safe);
    return (
      <a
        href={safe}
        target={external ? "_blank" : undefined}
        rel={external ? "noopener noreferrer" : undefined}
      >
        {children}
        {external ? <span className="sr-only"> (opens in a new tab)</span> : null}
      </a>
    );
  },
  code: ({ children }) => <code>{children}</code>,
};

export function MarkdownContent({
  source,
  className = "",
  compact = false,
}: {
  source: string;
  className?: string;
  compact?: boolean;
}) {
  return (
    <div
      className={`landing-markdown ${compact ? "landing-markdown--compact" : ""} ${className}`.trim()}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        urlTransform={safeMarkdownUrl}
        components={components}
      >
        {source}
      </ReactMarkdown>
    </div>
  );
}
