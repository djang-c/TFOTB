import { createContext, useContext } from "react";

export type Open = (claimId: string) => void;
export const Ctx = createContext<Open>(() => {});
export const useOpenClaim = () => useContext(Ctx);
