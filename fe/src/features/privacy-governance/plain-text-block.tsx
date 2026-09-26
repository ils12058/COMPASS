import { cn } from "@/lib/utils/cn";

// Governance and notice text is plain text. Blank lines separate paragraphs
// and single line breaks are preserved; nothing is interpreted as markup.
export function PlainTextBlock({
  text,
  empty = "None recorded.",
  className,
}: {
  text: string;
  empty?: string;
  className?: string;
}) {
  const paragraphs = text
    .split(/\n\s*\n/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);
  if (paragraphs.length === 0) {
    return <p className={cn("text-sm text-muted", className)}>{empty}</p>;
  }
  return (
    <div className={cn("max-w-3xl space-y-3 text-sm leading-7 text-ink", className)}>
      {paragraphs.map((paragraph, index) => (
        <p key={index} className="whitespace-pre-line break-words">
          {paragraph}
        </p>
      ))}
    </div>
  );
}
