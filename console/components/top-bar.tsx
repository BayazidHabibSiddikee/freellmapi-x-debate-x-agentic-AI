"use client";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { ChevronRight, ExternalLink } from "lucide-react";

const SEGMENT_LABELS: Record<string, string> = {
  "": "Today",
  business: "Business",
  skills: "Skills",
  ceo: "CEO Pack",
  cro: "Revenue Pack",
  cmo: "Marketing Pack",
  cpo: "Product Pack",
  cto: "Engineering Pack",
  caio: "AI Ops Pack",
  cfo: "Finance Pack",
  wiki: "Wiki",
  journal: "Journal",
  sources: "Sources",
  automations: "Automations",
  insights: "Insights",
  settings: "Settings",
};

/** Cross-app surfaces served by the FreeLLM dashboard on :3001. */
const APP_LINKS = [
  { href: "/debate", label: "Debate" },
  { href: "/knowledge", label: "Knowledge" },
  { href: "/personal", label: "Personal" },
];

function humanize(seg: string): string {
  if (SEGMENT_LABELS[seg] !== undefined) return SEGMENT_LABELS[seg];
  if (seg.startsWith("[")) return seg;
  return seg.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function TopBar() {
  const path = usePathname();
  const segments = path.split("/").filter(Boolean);
  const trail = segments.length === 0 ? ["Today"] : segments.map(humanize);
  const dashBase =
    typeof window !== "undefined"
      ? `${window.location.protocol}//${window.location.hostname}:3001`
      : "http://localhost:3001";

  return (
    <div className="hidden md:flex h-12 items-center gap-5 border-b border-[hsl(var(--border-default))] px-6 dense">
      <div className="flex items-center gap-1.5 text-xs">
        <Link href="/" className="text-[hsl(var(--fg-dim))] hover:text-[hsl(var(--fg-secondary))] transition-colors">
          SwordOffice
        </Link>
        {trail.map((label, i) => (
          <span key={i} className="flex items-center gap-1.5">
            <ChevronRight className="h-3 w-3 text-[hsl(var(--fg-dim))]" />
            <span
              className={
                i === trail.length - 1
                  ? "text-[hsl(var(--fg-primary))] font-medium"
                  : "text-[hsl(var(--fg-dim))]"
              }
            >
              {label}
            </span>
          </span>
        ))}
      </div>

      <div className="flex items-center gap-4 font-mono text-[10px] text-[hsl(var(--fg-dim))]">
        {APP_LINKS.map(({ href, label }) => (
          <a
            key={href}
            href={`${dashBase}${href}`}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 transition-colors hover:text-[hsl(var(--fg-secondary))]"
          >
            {label}
            <ExternalLink className="h-2.5 w-2.5" />
          </a>
        ))}
      </div>
      <span className="ml-auto font-mono text-[10px] text-[hsl(var(--fg-dim))]">
        {new Date().toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
      </span>
    </div>
  );
}
