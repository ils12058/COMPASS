import { Compass } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl items-center px-5 py-12 sm:px-8">
      <section className="grid w-full gap-8 lg:grid-cols-[1.2fr_0.8fr] lg:items-center">
        <div className="space-y-5">
          <div className="flex size-12 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
            <Compass aria-hidden="true" className="size-6" />
          </div>

          <div className="space-y-3">
            <Badge variant="gold">Frontend foundation</Badge>
            <h1 className="font-heading text-4xl font-bold tracking-tight sm:text-5xl">
              COMPASS
            </h1>
            <p className="max-w-2xl text-lg text-muted-foreground">
              Counseling Office Management Platform and Student Services
            </p>
            <p className="text-sm font-semibold text-[var(--compass-support-strong)]">
              University of Camarines Norte
            </p>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Design system preview</CardTitle>
            <CardDescription>
              A minimal verification surface for shared tokens and primitives.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="flex flex-wrap gap-2" aria-label="Design token samples">
              <Badge>Maroon</Badge>
              <Badge variant="support">Support</Badge>
              <Badge variant="gold">Gold</Badge>
              <Badge variant="neutral">Neutral</Badge>
            </div>

            <div className="space-y-2">
              <Label htmlFor="foundation-preview">Interface preview</Label>
              <Input
                id="foundation-preview"
                value="Current backend contract → generated client"
                readOnly
                aria-readonly="true"
              />
            </div>
          </CardContent>
          <CardFooter>
            <Button disabled>Foundation only</Button>
            <Button variant="outline" disabled>
              Features come next
            </Button>
          </CardFooter>
        </Card>
      </section>
    </main>
  );
}
