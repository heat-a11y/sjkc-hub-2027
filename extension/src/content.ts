import { fillStudentTpRecords } from "./moeis-fill";
import type { StudentTpFillResult, StudentTpRecord } from "../../shared/types";

chrome.runtime.onMessage.addListener((
  message: { type?: string; records?: StudentTpRecord[] },
  _sender: chrome.runtime.MessageSender,
  sendResponse: (response: { result?: StudentTpFillResult[]; error?: string }) => void,
) => {
  if (message.type !== "MOEIS_FILL_TP" || !Array.isArray(message.records)) return false;
  void fillStudentTpRecords(message.records).then(
    result => sendResponse({ result }),
    error => sendResponse({ error: error instanceof Error ? error.message : String(error) }),
  );
  return true;
});
