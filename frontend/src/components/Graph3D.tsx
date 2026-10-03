"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph3D, { type ForceGraphMethods } from "react-force-graph-3d";
import SpriteText from "three-spritetext";
import { enc, type GraphData } from "@/lib/api";
import { useOpenClaim } from "./EvidenceDrawer";
import { NODE_COLOR } from "./GraphSection";

type N = { id: string; label: string; type: string; x?: number; y?: number; z?: number };
type L = { source: string | N; target: string | N; claim_id: string; status: string; predicate: string };

export default function Graph3D({ data, focusId }: { data: GraphData; focusId: string }) {
  const router = useRouter();
  const openClaim = useOpenClaim();
  const wrap = useRef<HTMLDivElement>(null);
  const fg = useRef<ForceGraphMethods<N, L> | undefined>(undefined);
  const [width, setWidth] = useState(640);
  const [hover, setHover] = useState<string | null>(null);

  const graph = useMemo(() => ({
    nodes: data.nodes.map((n) => ({ ...n })),
    links: data.edges.map((e) => ({ ...e })),
  }), [data]);

  const neighbours = useMemo(() => {
    const m = new Map<string, Set<string>>();
    for (const e of data.edges) {
      if (!m.has(e.source)) m.set(e.source, new Set());
      if (!m.has(e.target)) m.set(e.target, new Set());
      m.get(e.source)!.add(e.target);
      m.get(e.target)!.add(e.source);
    }
    return m;
  }, [data]);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const lit = (id: string) => !hover || hover === id || neighbours.get(hover)?.has(id);
  const idOf = (x: string | N) => (typeof x === "string" ? x : x.id);

  return (
    <div ref={wrap} className="overflow-hidden rounded-md border border-rule bg-[#fbfcfd]">
      <ForceGraph3D<N, L>
        ref={fg}
        graphData={graph}
        width={width}
        height={460}
        backgroundColor="#fbfcfd"
        showNavInfo={false}
        cooldownTicks={120}
        onEngineStop={() => fg.current?.zoomToFit(400, 40)}
        nodeLabel={(n) => `${n.label} (${n.type})`}
        nodeThreeObjectExtend
        nodeThreeObject={(n) => {
          const t = new SpriteText(n.label.replace(" (synthetic)", ""));
          t.color = lit(n.id) ? "#17212e" : "#c3cad2";
          t.textHeight = n.id === focusId ? 6.5 : 4.2;
          t.fontFace = "Public Sans, system-ui, sans-serif";
          t.fontWeight = n.id === focusId ? "700" : "500";
          t.position.y = -9;
          return t;
        }}
        nodeColor={(n) => (lit(n.id) ? NODE_COLOR[n.type] ?? "#888" : "#dde2e7")}
        nodeVal={(n) => (n.id === focusId ? 14 : 5)}
        nodeOpacity={0.95}
        linkColor={(l) => {
          if (hover && !(idOf(l.source) === hover || idOf(l.target) === hover)) return "#e3e7eb";
          return l.status === "inference" ? "#6a46b0" : l.status === "computational_prediction" ? "#9aa6b2" : "#4a5868";
        }}
        linkWidth={(l) => (l.status === "reported_observation" ? 1.2 : 0.5)}
        linkDirectionalParticles={(l) => (hover && (idOf(l.source) === hover || idOf(l.target) === hover) ? 2 : 0)}
        linkDirectionalParticleWidth={2}
        linkLabel={(l) => `${l.predicate.toLowerCase().replaceAll("_", " ")}. Click for evidence.`}
        onNodeHover={(n) => setHover(n ? n.id : null)}
        onNodeClick={(n) => router.push(`/entity/${enc(n.id)}`)}
        onLinkClick={(l) => openClaim(l.claim_id)}
      />
    </div>
  );
}
