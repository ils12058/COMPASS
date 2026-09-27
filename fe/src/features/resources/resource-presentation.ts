import { ResourceKindValue, type ResourceManagementResponse } from "@/lib/api/generated/model";

export const resourceKindDescriptions: Record<ResourceKindValue, string> = {
  [ResourceKindValue.ARTICLE]: "Written content that readers read in COMPASS.",
  [ResourceKindValue.EXTERNAL_LINK]: "A description with a link to another website.",
  [ResourceKindValue.FILE]: "A description with a PDF file that readers download.",
};

export const resourceBodyHints: Record<ResourceKindValue, string> = {
  [ResourceKindValue.ARTICLE]: "Readers see this text on the Resource page.",
  [ResourceKindValue.EXTERNAL_LINK]: "Explain what readers will find at the link. Readers see this text with the link.",
  [ResourceKindValue.FILE]: "Explain what the file contains. Readers see this text with the download.",
};

const listFormatter = new Intl.ListFormat("en", { style: "long", type: "conjunction" });

// What the backend will require before this draft can be published.
export function missingForPublication(resource: ResourceManagementResponse): string[] {
  const missing: string[] = [];
  if (!resource.title.trim()) missing.push("a title");
  if (!resource.body_markdown.trim()) missing.push("body text");
  if (resource.kind === ResourceKindValue.EXTERNAL_LINK && !resource.external_url?.trim()) {
    missing.push("a link address");
  }
  if (resource.kind === ResourceKindValue.FILE && !resource.has_file) missing.push("a PDF file");
  return missing;
}

export function joinList(items: string[]): string {
  return listFormatter.format(items);
}

export function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return (url.protocol === "https:" || url.protocol === "http:") && Boolean(url.hostname);
  } catch {
    return false;
  }
}
