import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";

export default function FoundationPage() {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-3xl items-center px-5 py-12 sm:px-8">
      <section aria-labelledby="foundation-title" className="w-full">
        <p className="mb-3 text-sm font-semibold text-brand">COMPASS</p>
        <h1
          id="foundation-title"
          className="font-heading text-4xl font-bold tracking-tight text-ink sm:text-5xl"
        >
          Frontend foundation
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-muted">
          This temporary page verifies the application shell, design tokens, fonts,
          providers, and core interface primitives. Product workflows will be added
          in separate feature slices.
        </p>

        <div className="mt-10 border-t border-border pt-8">
          <div className="grid gap-5 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="foundation-input">Example field</Label>
              <Input id="foundation-input" placeholder="Enter a value" />
            </div>
            <div className="space-y-2 sm:row-span-2">
              <Label htmlFor="foundation-notes">Example notes</Label>
              <Textarea id="foundation-notes" placeholder="Add context" />
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button>Save changes</Button>
              <Button variant="secondary">Cancel</Button>
            </div>
          </div>

          <div className="mt-8 space-y-3" aria-label="Loading example">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        </div>
      </section>
    </main>
  );
}
