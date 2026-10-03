"use client";

import { usePathname } from "next/navigation";
import { SearchBox } from "./SearchBox";

/** The header search, except on the home page, which has its own large search. */
export function HeaderSearch() {
  if (usePathname() === "/") return null;
  return <SearchBox />;
}
