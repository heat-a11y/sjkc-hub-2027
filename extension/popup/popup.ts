import type { StudentTpFillResult, StudentTpRecord } from "../../shared/types";
import { findTransferTabs } from "../src/workflow";
import { parseTransitTables, readTransitTablesFromPage } from "../src/transit-import";

document.addEventListener("DOMContentLoaded", () => {
  const transferButton = document.getElementById("transferTpBtn") as HTMLButtonElement;
  const statusText = document.getElementById("statusText") as HTMLElement;
  const spinner = document.getElementById("spinner") as HTMLElement;
  const logContainer = document.getElementById("logContainer") as HTMLElement;

  function report(message: string, error = false) {
    statusText.textContent = error ? "Tidak berjaya" : "Selesai";
    const item = document.createElement("div");
    item.className = `log-item${error ? " error" : " success"}`;
    item.textContent = `${new Date().toLocaleTimeString("ms-MY")} — ${message}`;
    logContainer.replaceChildren(item);
  }

  transferButton.onclick = async () => {
    transferButton.disabled = true;
    spinner.classList.add("active");
    statusText.textContent = "Mengisi pentaksiran…";
    try {
      const [active] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!active?.id) throw new Error("Could not identify the active tab.");

      const tabs = await chrome.tabs.query({});
      const { source, target } = findTransferTabs(tabs, active.id);
      if (!source.id || !target.id) throw new Error("Could not identify both open pages.");

      const injected = await chrome.scripting.executeScript({
        target: { tabId: source.id },
        func: readTransitTablesFromPage,
      });
      const tables = injected[0]?.result;
      if (!Array.isArray(tables)) {
        const sourceUrl = source.url ? new URL(source.url).pathname : "unknown page";
        throw new Error(
          `The Rekod Transit reader returned no data from ${sourceUrl}. Reload that tab and retry; if it repeats, send the extension error text only.`,
        );
      }
      const imported = parseTransitTables(tables);

      if (target.status === "loading") await waitForTabComplete(target.id);
      const response = await fillTarget(target.id, imported.records);
      if (response.error) throw new Error(response.error);
      const results = response.result ?? [];
      const filled = results.filter(result => result.filled).length;
      const missingSourceTp = results.filter(result => result.error === "No unambiguous TP found in Rekod Transit").length;
      const ambiguousMatches = results.filter(result =>
        result.error === "Multiple Rekod Transit TP records match this student" ||
        result.error === "Student ID or name is not unique in MOEIS table",
      ).length;
      const incomplete = results.filter(result =>
        result.tp !== undefined && !result.filled,
      ).length;
      const fieldIssues = ["Kemahiran", "TP", "Ulasan Guru", "Intervensi", "Usaha Murid"]
        .map(field => {
          const reasons = new Map<string, number>();
          for (const result of results) {
            if (result.tp === undefined || !result.error) continue;
            for (const issue of result.error.split("; ")) {
              if (!issue.startsWith(`${field}:`)) continue;
              const reason = issue.slice(field.length + 1).trim();
              reasons.set(reason, (reasons.get(reason) ?? 0) + 1);
            }
          }
          return reasons.size
            ? `${field}: ${Array.from(reasons, ([reason, count]) => `${reason} (${count})`).join(", ")}`
            : "";
        })
        .filter(Boolean);
      const fieldIssueSummary = fieldIssues.length
        ? ` Field details: ${fieldIssues.join("; ")}.`
        : "";
      const summary = `Filled Kemahiran, Tahap Penguasaan, Ulasan Guru, Intervensi, and Usaha Murid for ${filled} of ${results.length} target students; ${missingSourceTp} target student(s) had no unambiguous RPH TP; ${ambiguousMatches} student(s) had ambiguous name/ID matches and were left unchanged; ${incomplete} matched student(s) still have these fields to review; ${imported.resolvedConflictCount} student(s) used their most frequent TP across the weekly RPH; ${imported.conflictingStudentCount} student(s) had tied TP results and were left unchanged; ${imported.missingTpCount} source row(s) had no selected TP.${fieldIssueSummary}`;
      if (!filled) throw new Error(summary);
      report(`${summary} Review MOEIS before submitting.`);
      await chrome.tabs.update(target.id, { active: true });
    } catch (error) {
      report(error instanceof Error ? error.message : String(error), true);
    } finally {
      transferButton.disabled = false;
      spinner.classList.remove("active");
    }
  };

  async function waitForTabComplete(tabId: number): Promise<void> {
    await new Promise<void>((resolve, reject) => {
      let settled = false;
      const finish = (error?: Error) => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timeout);
        chrome.tabs.onUpdated.removeListener(onUpdated);
        if (error) reject(error);
        else resolve();
      };
      const timeout = window.setTimeout(
        () => finish(new Error("MOEIS is still loading. Wait for the PBD table, then retry.")),
        20000,
      );
      const onUpdated = (updatedId: number, changeInfo: chrome.tabs.TabChangeInfo) => {
        if (updatedId === tabId && changeInfo.status === "complete") finish();
      };
      chrome.tabs.onUpdated.addListener(onUpdated);
      void chrome.tabs.get(tabId).then(tab => {
        if (tab.status === "complete") finish();
      }).catch(() => finish(new Error("Could not read the MOEIS tab status.")));
    });
  }
});

async function fillTarget(
  tabId: number,
  records: StudentTpRecord[],
): Promise<{ result?: StudentTpFillResult[]; error?: string }> {
  let response: { result?: StudentTpFillResult[]; error?: string } | undefined;
  try {
    response = await chrome.tabs.sendMessage(tabId, { type: "MOEIS_FILL_TP", records });
  } catch {
    response = undefined;
  }
  if (!response) {
    await chrome.scripting.executeScript({ target: { tabId }, files: ["dist/content.js"] });
    response = await chrome.tabs.sendMessage(tabId, { type: "MOEIS_FILL_TP", records });
  }
  if (!response) throw new Error("MOEIS autofill did not respond. Reload the PBD page and try again.");
  return response;
}
