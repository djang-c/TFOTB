import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export type ApiStatus = "checking" | "connected" | "building" | "down";

/** Whether the API answers. The whole app reads from it, so this is always visible. */
export function useApiStatus(): ApiStatus {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 30_000,
    retry: 0,
  });
  const ready = useQuery({
    queryKey: ["ready"],
    queryFn: api.ready,
    enabled: health.isSuccess,
    refetchInterval: (q) => (q.state.data?.ready ? false : 3_000),
    retry: 0,
  });
  if (health.isError) return "down";
  if (health.isPending) return "checking";
  return ready.data && !ready.data.ready ? "building" : "connected";
}

export const STATUS_TEXT: Record<ApiStatus, string> = {
  checking: "Checking the API",
  connected: "Connected to the API",
  building: "API is building its search index",
  down: "API not reachable",
};

export const STATUS_DOT: Record<ApiStatus, string> = {
  checking: "bg-gap",
  connected: "bg-reviewed",
  building: "bg-gap",
  down: "bg-destructive",
};
