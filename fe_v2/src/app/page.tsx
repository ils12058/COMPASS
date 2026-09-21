import { PublicSiteFooter } from "@/features/public/components/public-site-footer";
import { PublicSiteHeader } from "@/features/public/components/public-site-header";
import { Homepage } from "@/features/public/homepage/homepage";

export default function Home() {
  return (
    <div className="public-site flex min-h-screen flex-col bg-background text-foreground">
      <a className="landing-skip-link" href="#main-content">
        Skip to main content
      </a>
      <PublicSiteHeader overlay />
      <main id="main-content" className="flex flex-1 flex-col">
        <Homepage />
      </main>
      <PublicSiteFooter />
    </div>
  );
}
