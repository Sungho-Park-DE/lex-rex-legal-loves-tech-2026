import { createContext, useContext } from "react";

import type { Zitat } from "@/types/viewmodel";

export interface ViewerSteuerung {
  zeigeZitat: (zitat: Zitat) => void;
}

const Ctx = createContext<ViewerSteuerung>({ zeigeZitat: () => {} });

export const ViewerProvider = Ctx.Provider;

export function useViewer() {
  return useContext(Ctx);
}
