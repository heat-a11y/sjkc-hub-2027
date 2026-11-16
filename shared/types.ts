// Shared TypeScript interfaces for the Chrome Extension + AI Content + Face Attendance system.

// ---------------------------------------------------------------------------
// Rekod Transit → MOEIS PBD TP transfer
// ---------------------------------------------------------------------------

export interface StudentTpRecord {
  name: string;
  id?: string;
  tp: number;
}

export interface TransitTableData {
  rows: string[][];
}

export interface TransitImportResult {
  records: StudentTpRecord[];
  resolvedConflictCount: number;
  conflictingStudentCount: number;
  missingTpCount: number;
}

export interface StudentTpFillResult {
  studentName: string;
  selector: string;
  tp?: number;
  found: boolean;
  filled: boolean;
  fieldsFilled?: number;
  fieldsTotal?: number;
  error?: string;
}

// ---------------------------------------------------------------------------
// RPH Data (shared between AI content)
// ---------------------------------------------------------------------------

export type SubjectCode = "BM" | "BC" | "BI" | "MT" | "SN" | "SJ" | "RBT"
  | "PJ" | "PK" | "PSV" | "MZ" | "PM" | "PI" | "MA";

export type InterfaceLanguage = "bm" | "en" | "zh";

export interface RPHData {
  subject: SubjectCode;
  year: number;          // 1–6
  language: InterfaceLanguage;
  class: string;         // e.g. "Year 3" / "Tahun 3"
  week: number;
  theme: string;
  unit: string;
  topic: string;
  date: string;          // YYYY-MM-DD
  period: number;
  sk: { code: string; desc: string }[];
  sp: { code: string; desc: string }[];
  objectives: string[];
  activities: {
    setInduction: string;
    preLesson: string;
    development: string;
    postLesson: string;
    closure: string;
  };
  successCriteria: string[];
  bbm: string;
  moralValues: string;
  emk: string;
  remedial: string[];
  reflection: string;
  studentCount: number;
}

// ---------------------------------------------------------------------------
// Face Attendance (shared between extension and face-attendance module)
// ---------------------------------------------------------------------------

export interface FaceTemplate {
  studentId: string;
  studentName: string;
  className: string;          // e.g. "Year 3"
  faceDescriptor: number[];     // 128-dim face embedding
  createdAt: number;            // epoch ms
  updatedAt?: number;
}

export interface FaceRecognitionResult {
  recognized: boolean;
  template?: FaceTemplate;
  confidence: number;      // 0–1
  timestamp: number;
}

// ---------------------------------------------------------------------------
// AI Content Generator (serverless function schemas)
// ---------------------------------------------------------------------------

export interface AIContentRequest {
  subject: SubjectCode;
  year: number;
  language: InterfaceLanguage;
  week: number;
  sk: string[];
  sp: string[];
  theme: string;
  unit: string;
  topic: string;
  studentCount: number;
  existingReflections?: string;
  model?: string;         // override default model
}

export interface AIActivities {
  setInduction: string;
  preLesson: string;
  development: string;
  postLesson: string;
  closure: string;
}

export interface AITpInterventions {
  low: string;       // TP 1–2
  medium: string;    // TP 3–4
  high: string;      // TP 5–6
}

export interface AIContentResponse {
  objectives: string[];
  successCriteria: string[];
  activities: AIActivities;
  remedial: string[];
  reflection: string;
  tpInterventions: AITpInterventions;
  creditsUsed: number;
}
