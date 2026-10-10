import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { safeMarkdownUrl, safePublicUrl } from "@/features/public/utils";

const components: Components = {
  h1: ({ children }) => <h2 className="mt-8 font-heading text-2xl font-bold">{children}</h2>,
  h2: ({ children }) => <h2 className="mt-8 font-heading text-2xl font-bold">{children}</h2>,
  h3: ({ children }) => <h3 className="mt-6 font-heading text-xl font-bold">{children}</h3>,
  p: ({ children }) => <p className="my-4 leading-7 text-foreground/90">{children}</p>,
  ul: ({ children }) => <ul className="my-4 list-disc space-y-2 pl-6">{children}</ul>,
  ol: ({ children }) => <ol className="my-4 list-decimal space-y-2 pl-6">{children}</ol>,
  blockquote: ({ children }) => (
    <blockquote className="my-5 border-l-4 border-[var(--compass-support)] pl-4 text-muted-foreground">
      {children}
    </blockquote>
  ),
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
        className="font-semibold underline decoration-[var(--compass-brand-gold)] underline-offset-4"
      >
        {children}
        {external ? <span className="sr-only"> (opens in a new tab)</span> : null}
      </a>
    );
  },
  code: ({ children }) => (
    <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-sm">{children}</code>
  ),
  hr: () => <hr className="my-7 border-border" />,
};

export function MarkdownContent({ source }: { source: string }) {
  return (
    <div className="max-w-none">
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
