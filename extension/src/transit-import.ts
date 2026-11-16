import type { StudentTpRecord, TransitImportResult, TransitTableData } from "../../shared/types";

function normalize(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim()
    .replace(/\s+/g, " ");
}

function columnIndex(headers: string[], aliases: string[]): number {
  const names = aliases.map(normalize);
  return headers.findIndex(header => names.includes(normalize(header)));
}

function parseTp(value: string): number | undefined {
  const match = value.trim().match(/^(?:TP\s*)?([1-6])$/i);
  return match ? Number(match[1]) : undefined;
}

export function parseTransitTables(tables: TransitTableData[]): TransitImportResult {
  const candidates = tables.flatMap(table => {
    const headerIndex = table.rows.findIndex(row =>
      columnIndex(row, ["Nama", "Nama Murid", "Name", "Student Name"]) >= 0 &&
      columnIndex(row, ["TP", "Tahap Penguasaan"]) >= 0,
    );
    if (headerIndex < 0) return [];

    const headers = table.rows[headerIndex];
    return [{
      rows: table.rows.slice(headerIndex + 1),
      nameIndex: columnIndex(headers, ["Nama", "Nama Murid", "Name", "Student Name"]),
      idIndex: columnIndex(headers, ["ID Pengenalan", "No. Kad Pengenalan", "No Kad Pengenalan", "IC", "Student ID"]),
      tpIndex: columnIndex(headers, ["TP", "Tahap Penguasaan"]),
    }];
  });
  if (candidates.length === 0) {
    throw new Error("Could not find a Rekod Transit table with student-name and TP columns.");
  }
  const observations = new Map<string, {
    record: StudentTpRecord;
    counts: Map<number, number>;
  }>();
  let missingTpCount = 0;
  for (const candidate of candidates) {
    for (const row of candidate.rows) {
      const name = row[candidate.nameIndex]?.trim() ?? "";
      const id = candidate.idIndex >= 0 ? row[candidate.idIndex]?.trim() ?? "" : "";
      const tpText = row[candidate.tpIndex]?.trim() ?? "";
      if (!name && !tpText) continue;
      const tp = parseTp(tpText);
      if (!name) continue;
      if (tp === undefined) {
        if (tpText) {
          throw new Error("Rekod Transit contains an invalid TP value. Each student must have a TP from 1 to 6.");
        }
        missingTpCount += 1;
        continue;
      }
      const key = id ? `id:${normalize(id)}` : `name:${normalize(name)}`;
      const observation = observations.get(key) ?? {
        record: { name, ...(id ? { id } : {}), tp },
        counts: new Map<number, number>(),
      };
      observation.counts.set(tp, (observation.counts.get(tp) ?? 0) + 1);
      observations.set(key, observation);
    }
  }
  const records: StudentTpRecord[] = [];
  let resolvedConflictCount = 0;
  let conflictingStudentCount = 0;
  for (const observation of observations.values()) {
    const highestCount = Math.max(...observation.counts.values());
    const mostFrequent = Array.from(observation.counts)
      .filter(([, count]) => count === highestCount)
      .map(([tp]) => tp);
    if (mostFrequent.length > 1) {
      conflictingStudentCount += 1;
      continue;
    }
    if (observation.counts.size > 1) resolvedConflictCount += 1;
    records.push({ ...observation.record, tp: mostFrequent[0] });
  }
  if (records.length === 0) throw new Error("No unambiguous student TP values found in Rekod Transit.");
  return { records, resolvedConflictCount, conflictingStudentCount, missingTpCount };
}

export function readTransitTablesFromPage(
  pageDocument: Document = document,
  pageUrl = location.href,
): TransitTableData[] {
  const url = new URL(pageUrl);
  const validHttps = url.protocol === "https:" && (url.hostname === "erph-pm.vercel.app" || (url.hostname.endsWith(".vercel.app") && /(erph|sjkc)/i.test(url.hostname)));
  const validLocal = url.protocol === "http:" && (url.hostname === "localhost" || url.hostname === "127.0.0.1");
  if (!validHttps && !validLocal) {
    throw new Error("This is not the eRPH-PM application.");
  }
  return Array.from(pageDocument.querySelectorAll("table")).map(table => ({
    rows: Array.from(table.rows).map(row =>
      Array.from(row.cells).map(cell => {
        const allControls = Array.from(cell.querySelectorAll(
          "input:not([type=hidden]), textarea, select, [contenteditable=true]",
        ));
        if (allControls.length === 0) return (cell.innerText || cell.textContent || "").trim();
        const controls = allControls.filter(control => {
          if (control instanceof HTMLInputElement && ["radio", "checkbox"].includes(control.type)) {
            return control.checked;
          }
          return true;
        });
        return controls.map(control => {
          if (control instanceof HTMLInputElement && control.type === "radio") {
            const labels = Array.from(control.labels ?? []).map(label =>
              label.innerText || label.textContent || "",
            );
            const candidates = [control.getAttribute("aria-label") ?? "", ...labels];
            return candidates.find(value => /^(?:TP\s*)?[1-6]$/i.test(value.trim())) ?? control.value;
          }
          if (control instanceof HTMLSelectElement) {
            return control.selectedOptions[0]?.textContent?.trim() || control.value;
          }
          if (control instanceof HTMLInputElement || control instanceof HTMLTextAreaElement) {
            return control.value.trim();
          }
          return control.textContent?.trim() ?? "";
        }).filter(Boolean).join(" ");
      }),
    ),
  }));
}
