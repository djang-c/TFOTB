import { useQuery } from "@tanstack/react-query";
import { Check, Copy, Download } from "lucide-react";
import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { Markdown } from "@/components/Markdown";
import { cardToMarkdown, KIND } from "@/lib/cards";
import { Button } from "@/components/ui/button";
import { api, type ActionCard } from "@/lib/api";
import { safeHref } from "@/lib/safeHref";
import { Empty, Section } from "./Common";

export function Cards({ id }: { id: string }) {
  const cards = useQuery({ queryKey: ["actions", id], queryFn: () => api.actions(id), retry: 1 });
  const assets = useQuery({ queryKey: ["assets", id], queryFn: () => api.assets(id), retry: 0 });
  return (
    <>
      <Section title="Action cards" count={cards.data?.cards.length ?? "…"}>
        <p className="text-xs text-muted-foreground">
          Drafted research notes. Each footnote opens the claim behind it. A person should review a
          card before it is used or sent.
        </p>
      </Section>
      {cards.isError && (
        <p role="alert" className="p-6 text-xs text-destructive">
          Action cards could not be loaded.
        </p>
      )}
      {cards.data?.cards.length === 0 && (
        <div className="border-b border-border p-6">
          <Empty>No action cards are drafted for this entry yet.</Empty>
        </div>
      )}
      {cards.data?.cards.map((c) => (
        <CardView key={c.card_id} card={c} />
      ))}
      {assets.data && assets.data.assets.length > 0 && (
        <Section
          title="Reusable assets and studies"
          count={assets.data.total ?? assets.data.assets.length}
        >
          <ul className="space-y-3 text-xs">
            {assets.data.assets.slice(0, 8).map((a) => (
              <li key={a.asset_id}>
                <strong className="block">{a.label}</strong>
                <span className="text-muted-foreground">
                  {[a.asset_kind.replaceAll("_", " "), a.status, a.access_conditions]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
                {a.contact && safeHref(a.contact.url) && (
                  <a
                    className="block text-[11px] underline-offset-2 hover:underline"
                    href={safeHref(a.contact.url)}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {a.contact.label}
                  </a>
                )}
              </li>
            ))}
          </ul>
        </Section>
      )}
    </>
  );
}

function CardView({ card }: { card: ActionCard }) {
  const [copied, setCopied] = useState(false);
  const md = card.body_markdown.replace(/^# .*\n/, "");
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(cardToMarkdown(card));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };
  const download = () => {
    const url = URL.createObjectURL(
      new Blob([cardToMarkdown(card)], { type: "text/markdown;charset=utf-8" }),
    );
    const a = Object.assign(document.createElement("a"), {
      href: url,
      download: `${card.card_id.replace(/[^a-z0-9-]/gi, "-")}.md`,
    });
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <article className="border-b border-border p-6">
      <div className="flex items-center justify-between gap-2">
        <span className="section-kicker text-primary">{KIND[card.kind]}</span>
        <div className="flex gap-1">
          <Button
            variant="ghost"
            size="icon"
            title="Copy Markdown"
            aria-label={`Copy ${KIND[card.kind]} as Markdown`}
            onClick={() => void copy()}
          >
            {copied ? <Check /> : <Copy />}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            title="Download Markdown"
            aria-label={`Download ${KIND[card.kind]} as Markdown`}
            onClick={download}
          >
            <Download />
          </Button>
        </div>
      </div>
      <p className="mt-1 text-[11px] text-muted-foreground">
        For {card.audience === "family" ? "families" : "researchers"}
      </p>
      <p className="mt-3 text-xs font-medium">This week: {card.this_week}</p>
      <div className="mt-2">
        <Markdown md={md} />
      </div>
      {card.kind === "simulation_report" && (
        <Link to="/simulation" className="mt-2 block text-xs underline underline-offset-2">
          Open the simulation
        </Link>
      )}
      <ul className="mt-3 list-disc pl-4 text-[10px] leading-4 text-muted-foreground">
        {card.limitations.map((l) => (
          <li key={l}>{l}</li>
        ))}
      </ul>
      <p className="mt-2 text-[10px] text-muted-foreground">
        Reviewed before use by: {card.responsible_human}
      </p>
    </article>
  );
}
