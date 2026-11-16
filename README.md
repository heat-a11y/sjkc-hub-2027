# 🇲🇾 SJKC Hub 2027 — Unified eRPH-PM & Penjana Kertas Ujian (UPSA / UASA)

A single unified web application and repository combining:
1. **`erph-pm` (Rancangan Pengajaran Harian + PBD + Rekod Transit + 2027 Takwim)** — 14 subjects, Years 1–6 & Prasekolah, BM/EN/ZH interface, KPM 2027 43-week academic calendar preset, 1-click Lesson Carry-Forward (`Tangguh Minggu Depan`), and AI RPH Content Generator.
2. **`exam-gen` (Penjana Kertas Ujian Bahasa Inggeris 013 — UPSA & UASA)** — 7-part (50 marks) exam paper generator with DSKP vocabulary gate, CEFR alignment, per-paper JSU blueprint table, OMR + Writing answer sheet, Teacher Answer Key, Borang Markah, SVG scene illustrations, and `.docx` / PDF export.
3. **`extension/` (MOEIS PBD Chrome Extension)** — Transfers Rekod Transit TP values into `moeissppb.moe.gov.my` (works with both `erph-pm.vercel.app`, `*.vercel.app`, and `localhost`).
4. **`materials/2027/` (Unified Curriculum & Exam Corpus Store)** — Replaces the old hardcoded `~/Downloads/exam2026` directory with a portable, versioned store (`reference.json`, `textbook_corpus.json`, `textbook_ocr/`, `web_passages.json`, `crest.png`, and `past-papers/`).

---

## 🌐 Using Online Across Multiple PCs (Vercel Deployment)

This repository is structured to deploy directly to **Vercel** (free tier) with zero configuration:
- **Static Web App (`index.html`, `curriculum-db.js`, `rpt-data.js`, `exam-browser.js`, `tailwind.css`)**
- **Python Serverless API (`/api/exam` -> `api/exam.py` & `/api/generate-content` -> `api/generate_content.py`)**
- **Offline Fallback (`exam-browser.js` + `sw.js`)**: Even if you lose internet connection in the classroom, the app caches all assets and pre-bundled exam papers in the browser.

### Deploy to Vercel in 1 Command (or via GitHub Integration)
```bash
cd /home/school/Projects/sjkc-hub-2027
vercel --prod
```
*(Optional Vercel Environment Variables)*:
- `SITE_PASSWORD` & `AUTH_SECRET`: Set these in Vercel Project Settings if you want the password login gate (`login.html`) enabled. If left blank, the app opens directly.
- `OPENROUTER_API_KEY`: Optional OpenRouter key for LLM RPH generation (falls back automatically to the built-in KSSR deterministic generator when unset).

---

## 💻 Running Locally on Any PC (Zero Dependencies)

Clone this repository on any computer with Python 3 installed and run:
```bash
git clone https://github.com/heat-a11y/sjkc-hub-2027.git
cd sjkc-hub-2027
python3 server.py --port 8080
```
Then open **`http://localhost:8080`** in your browser.

---

## ✨ Key Unified Features (2027 Edition)

1. **📄 Kertas Ujian Tab (`UPSA / UASA 013`) Inside eRPH-PM**
   - Generate Year 1–6 UPSA/UASA papers right inside the web app.
   - **🔗 Ikut Minggu RPH Semasa**: Syncs the exam generator's Year, RPT Week, and RPT Theme directly from your active RPH lesson plans.
   - **📄 Kertas Ujian Topik Ini** button on every Bahasa Inggeris RPH card jumps straight to a matching exam paper for that lesson's unit.
   - Download **Pupil Paper (`.docx`)**, **Set B (`.docx`)**, **Teacher Copy with Answer Key + JSU (`.docx`)**, **Borang Markah (`.docx`)**, or **Print to A4 PDF**.
2. **📊 Interactive Borang Markah → Rekod Transit & PBD Auto-Sync**
   - Enter Section A (`/25`) and Section B (`/25`) scores for your class in the **Borang Markah & PBD Sync** sub-tab.
   - Automatically calculates `%` and suggests **TP 1–6** (`85%+ = TP6`, `70%+ = TP5`, `55%+ = TP4`, `40%+ = TP3`, `20%+ = TP2`, `<20% = TP1`).
   - Click **📥 Simpan TP ke Rekod Transit & Prestasi** to push all pupils' TP values into Rekod Transit & Prestasi (ready for the Chrome Extension to fill into MOEIS PBD!).
3. **🗓️ 2027 Academic Session & Rollover**
   - Built-in **KPM 2027 Kalendar Akademik (43 Mingguan)** preset in **⚙️ Tetapan** alongside the 2026 calendar.
   - **⏭️ Tangguh Minggu Depan** button on every RPH card shifts a postponed lesson to the following week in one click.
   - **🤖 Jana AI** button on every RPH card generates KSSR 5-phase differentiated activities, SP-aligned objectives, success criteria, remedial tasks, and reflections.
