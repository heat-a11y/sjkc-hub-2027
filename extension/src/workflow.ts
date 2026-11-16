export interface TransferTab {
  id?: number;
  url?: string;
  status?: string;
}

export function isErphAppUrl(value: string): boolean {
  try {
    const url = new URL(value);
    if (url.protocol === "https:" && (url.hostname === "erph-pm.vercel.app" || url.hostname.endsWith(".github.io") || (url.hostname.endsWith(".vercel.app") && /(erph|sjkc)/i.test(url.hostname)))) {
      return true;
    }
    if (url.protocol === "http:" && (url.hostname === "localhost" || url.hostname === "127.0.0.1")) {
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

export function isMoeisPbdUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "https:" &&
      url.hostname === "moeissppb.moe.gov.my" &&
      /^\/keputusan\/pbd\/pbd\/[^/]+\/?$/.test(url.pathname);
  } catch {
    return false;
  }
}

export function findTransferTabs<T extends TransferTab>(
  tabs: T[],
  activeTabId: number,
): { source: T; target: T } {
  const sources = tabs.filter(tab => tab.url && isErphAppUrl(tab.url));
  const targets = tabs.filter(tab => tab.url && isMoeisPbdUrl(tab.url));

  const source = sources.find(tab => tab.id === activeTabId) ??
    (sources.length === 1 ? sources[0] : undefined);
  const target = targets.find(tab => tab.id === activeTabId) ??
    (targets.length === 1 ? targets[0] : undefined);

  if (!source) {
    throw new Error(sources.length > 1
      ? "Multiple eRPH-PM tabs are open. Activate the intended Rekod Transit tab or close extras."
      : "Open Rekod Transit in eRPH-PM before using Import RPH & Fill MOEIS.");
  }
  if (!target) {
    throw new Error(targets.length > 1
      ? "Multiple MOEIS PBD tabs are open. Activate the intended class assessment tab or close extras."
      : "Open the MOEIS class PBD assessment page before using Import RPH & Fill MOEIS.");
  }
  return { source, target };
}
