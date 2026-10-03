"use client";

import dynamic from "next/dynamic";
import type { SimRun } from "@/lib/api";

const SimReplay = dynamic(() => import("./SimReplay"), {
  ssr: false,
  loading: () => <div className="grid h-[480px] place-items-center rounded-md border border-rule bg-white text-sm text-muted">Loading 3D replay</div>,
});

export function SimReplayLoader({ run }: { run: SimRun }) {
  return <SimReplay run={run} />;
}
