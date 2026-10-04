import { QueryClient } from "@tanstack/react-query";
import { createRouter } from "@tanstack/react-router";
import { HERO_STYLE } from "./lib/heroStyle";
import { routeTree } from "./routeTree.gen";

export const getRouter = () => {
  const queryClient = new QueryClient();
  return createRouter({
    routeTree,
    context: { queryClient },
    scrollRestoration: true,
    defaultPreloadStaleTime: 0,
    // the old page dissolves into the new one instead of vanishing (browsers without View Transitions just switch)
    defaultViewTransition: HERO_STYLE === "flow",
  });
};
