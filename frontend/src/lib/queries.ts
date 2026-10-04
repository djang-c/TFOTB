import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";

const noRetryOn404 = (n: number, e: unknown) =>
  !(e instanceof ApiError && e.status === 404) && n < 1;

export const useMeta = () =>
  useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: 300_000, retry: 1 });
export const useEntity = (id: string) =>
  useQuery({
    queryKey: ["entity", id],
    queryFn: () => api.entity(id),
    retry: noRetryOn404,
    staleTime: 60_000,
    enabled: id.length > 0,
  });
export const useGraph = (id: string, max = 40) =>
  useQuery({
    queryKey: ["graph", id, max],
    queryFn: () => api.graph(id, max),
    retry: 1,
    staleTime: 60_000,
  });
export const useConnections = (id: string) =>
  useQuery({
    queryKey: ["connections", id],
    queryFn: () => api.connections(id),
    retry: 0,
    staleTime: 60_000,
  });
export const useActions = (id: string) =>
  useQuery({
    queryKey: ["actions", id],
    queryFn: () => api.actions(id),
    retry: 0,
    staleTime: 60_000,
  });
export const useAssets = (id: string) =>
  useQuery({
    queryKey: ["assets", id],
    queryFn: () => api.assets(id),
    retry: 0,
    staleTime: 60_000,
  });
export const useGap = (id: string) =>
  useQuery({ queryKey: ["gap", id], queryFn: () => api.gap(id), retry: 0, staleTime: 60_000 });
export const isNotFound = (e: unknown) => e instanceof ApiError && e.status === 404;

/** Entries to start from: the seed cluster the API reports, else its featured entries. Never hand-picked here. */
export function useStarters() {
  const meta = useMeta();
  return { meta, items: meta.data?.real?.seed ?? meta.data?.featured ?? [] };
}
