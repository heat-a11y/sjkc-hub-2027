"""GTK4 GUI for Penjana Kertas Ujian (SJKC exam paper generator).

Material Design 3 themed and fully responsive:
  * wide windows: config pane beside a live paper preview (WebKitGTK)
  * narrow windows: the config pane collapses into a slide-in drawer
  * live re-generation while you configure; instant DOCX/PDF export
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

try:
    gi.require_version("WebKit", "6.0")
    from gi.repository import WebKit
    HAVE_WEBKIT = True
except Exception:  # pragma: no cover - graceful fallback
    WebKit = None
    HAVE_WEBKIT = False

from . import art, bank, data as D, pdfmake, render_html, webfetch
from .__init__ import APP_NAME, APP_ID

NARROW = 980

DIFF_LABELS = {"easy": ("Mudah", "Easy"),
               "medium": ("Sederhana", "Medium"),
               "hard": ("Sukar", "Hard")}

# UI strings (BM key kept for data compatibility; UI is always English now).
U = {
    "app_title": ("Penjana Kertas Ujian", "Exam Paper Generator"),
    "menu_bulk": ("Jana Semua Tahun…", "Generate All Years…"),
    "menu_bulk12": ("Jana 12 Kertas (UPSA+UASA)…", "Generate All 12 Papers (UPSA+UASA)…"),
    "menu_compare": ("Banding dengan varian", "Compare with a variant"),
    "menu_warm": ("Muat turun foto", "Warm photo cache"),
    "menu_termpack": ("Pek term (ZIP)", "Term pack (ZIP)"),
    "menu_about": ("Tentang", "About"),
    "menu_open_papers": ("Buka Folder Kertas…", "Open Papers Folder…"),
    "menu_pack_save": ("Simpan Pek Sekolah…", "Save School Pack…"),
    "menu_pack_load": ("Muat Pek Sekolah…", "Load School Pack…"),
    "bank_saved_one": ("Disimpan ke bank soalan anda.", "Saved to your question bank."),
    "bank_dup": ("Sudah ada dalam bank.", "Already in your bank."),
    "bank_skip_writing": ("Bahagian menulis tidak boleh disimpan ke bank.",
                         "Writing parts can't be saved to the bank."),
    "pack_done": ("Pek '{}' disimpan.", "Pack '{}' saved."),
    "pack_loaded": ("Pek '{}' dimuat.", "Pack '{}' loaded."),
    "pack_none": ("Tiada pek disimpan lagi.", "No saved packs yet."),
    "pack_exists": ("Nama pek sudah wujud: {}", "Pack name already exists: {}"),
    "pack_name_me": ("Nama pek ini:", "Name this pack:"),
    "pack_choose": ("Pilih pek:", "Choose a pack:"),
    "card_school": ("Sekolah & Peperiksaan", "School & Exam"),
    "lbl_school": ("Nama sekolah", "School name"),
    "lbl_teacher": ("Nama guru", "Teacher name"),
    "lbl_pupilid": ("ID murid (cth. 2026-0451)", "Pupil ID (e.g. 2026-0451)"),
    "lbl_crest": ("Lencana sekolah", "School crest"),
    "btn_choose": ("Pilih fail gambar…", "Choose picture file…"),
    "lbl_qr": ("Cop ID murid sebagai QR", "Stamp pupil ID as a QR code"),
    "lbl_calibrate": ("Sulitkan soalan kerap silap (statistik)", "Rotate out frequently-missed questions (stats)"),
    "lbl_bundle_n": ("Saiz set kelas (kertas)", "Class set size (papers)"),
    "menu_bundle": ("Jana Set Kelas…", "Generate Class Set…"),
    "menu_results": ("Tanda & Keputusan Kelas…", "Mark & Class Results…"),
    "menu_import": ("Import Soalan (bank/past paper)…", "Import Questions (bank/past paper)…"),
    "menu_dskp": ("Laporan Liputan DSKP", "DSKP Coverage Report"),
    "bundle_saved": ("Set kelas disimpan ({} kertas + helaian tandaan).",
                     "Class set saved ({} papers + marking sheet)."),
    "bundle_none": ("Tiada kertas untuk disetkan.", "No paper to set yet."),
    "results_ok": ("{} murid dikira; ringkasan: {}", "{} pupils tallied; summary: {}"),
    "results_none": ("Tiada baris murid dalam fail itu.", "No pupil rows in that file."),
    "results_read_err": ("Tak dapat baca fail tandaan: {}", "Cannot read marking file: {}"),
    "import_ok": ("{} soalan diimport ke bank.", "{} question(s) imported to the bank."),
    "import_json_ok": ("Kertas lampau disahkan: {} soalan.", "Past paper validated: {} questions."),
    "import_bad": ("Format import tidak dikenali: {}", "Unrecognised import format: {}"),
    "dskp_title": ("Liputan DSKP — Tahun {}", "DSKP Coverage — Year {}"),
    "lbl_examtype": ("Jenis ujian", "Exam type"),
    "lbl_session": ("Sesi", "Session"),
    "card_year": ("Tahun", "Year"),
    "dur_hint": ("Tempoh: {} · 50 markah", "Duration: {} · 50 marks"),
    "card_parts": ("Bahagian kertas", "Paper sections"),
    "card_opts": ("Pilihan", "Options"),
    "lbl_key": ("Sertakan salinan guru (kunci jawapan + JSU)",
                "Include teacher copy (answer key + JSU)"),
    "lbl_sheet": ("Sertakan helaian jawapan", "Include answer sheet"),
    "lbl_web": ("Guna petikan yang dimuat turun", "Use web-fetched passages"),
    "web_y3plus": ("Petikan web sesuai untuk Tahun 3–6 (Tahun 1–2 sangat ditapis, jadi kebanyakan kertas mereka kekal pakej terbina).",
                   "Web passages suit Years 3–6 (Years 1–2 are heavily filtered, so most of their papers stay on built-in sets)."),
    "web_usable": ("{} sesuai / {} untuk Tahun {}",
                   "{} usable / {} for Year {}"),
    "lbl_seed": ("Set soalan (variasi)", "Question set (variation)"),
    "btn_generate": ("Jana & Simpan", "Generate & Save"),
    "btn_regen": ("Jana Semula", "Regenerate"),
    "btn_open": ("Buka DOCX", "Open DOCX"),
    "btn_save_docx": ("Simpan DOCX", "Save DOCX"),
    "btn_save_pdf": ("Simpan PDF", "Save PDF"),
    "btn_save_both": ("Simpan DOCX + PDF", "Save DOCX + PDF"),
    "lbl_difficulty": ("Tahap kesukaran", "Difficulty level"),
    "lbl_theme": ("Tema RPT", "RPT theme"),
    "lbl_week": ("Minggu RPT (0 = auto mati)", "RPT week (0 = auto off)"),
    "lbl_pictures": ("Sertakan gambar berkaitan", "Include related pictures"),
    "lbl_marksheet": ("Sertakan borang markah", "Include marking sheet"),
    "lbl_abset": ("Jana set A & B", "Generate set A & B"),
    "btn_bank": ("Buka Bank Soalan…", "Open Question Bank…"),
    "btn_backup": ("Sandaran", "Backup"),
    "backup_done": ("Sandaran disimpan: {}", "Backup saved: {}"),
    "backup_none": ("Tiada bank/pack untuk sandaran lagi", "Nothing to back up yet"),
    "undo_ok": ("Edit dimansuhkan", "Edit undone"),
    "redo_ok": ("Edit dipulihkan", "Edit redone"),
    "undo_none": ("Tiada edit untuk dimansuhkan", "Nothing to undo"),
    "redo_none": ("Tiada edit untuk dipulihkan", "Nothing to redo"),
    "reset_ok": ("Bahagian diset semula", "Part reset"),
    "bank_loaded": ("Bank dimuat: {} entri", "Bank loaded: {} entries"),
    "bank_error": ("Bank tidak sah: {}", "Invalid bank: {}"),
    "saved_ab": ("Set A & B dan borang markah disimpan.",
                 "Sets A & B and marking sheet saved."),
    "saved_ab_simple": ("Set A & B disimpan.", "Sets A & B saved."),
    "btn_config": ("Konfigurasi", "Settings"),
    "btn_fetch": ("Muat Turun Petikan Web", "Fetch Web Passages"),
    "web_done": ("{} petikan sedia daripada {} sumber", "{} passages ready from {} sources"),
    "web_none": ("Tiada petikan web. Klik “Muat Turun Petikan Web”.", 
                 "No web passages yet. Click “Fetch Web Passages”."),
    "web_fetching": ("Sedang memuat turun pasal web…", "Fetching web passages…"),
    "web_retired": ("Petikan Gutenberg tidak lagi digunakan; buku teks kini "
                    "satu-satunya rujukan.",
                    "Gutenberg passages are retired; the textbooks are now the "
                    "sole reference."),
    "gen_status": ("{} bahagian · {} markah · {} soalan", 
                   "{} parts · {} marks · {} questions"),
    "gen_key": (" · skema disertakan", " · answer key included"),
    "gen_web": (" · petikan web", " · web passages"),
    "saved_docx": ("Kertas disimpan: {}", "Paper saved: {}"),
    "saved_pdf": ("PDF disimpan: {}", "PDF saved: {}"),
    "saved_both": ("DOCX + PDF disimpan: {}", "DOCX + PDF saved: {}"),
    "saving": ("Menyimpan… (LibreOffice)", "Saving… (LibreOffice)"),
    "save_error": ("Ralat semasa menyimpan: {}", "Error while saving: {}"),
    "no_pdf": ("LibreOffice tidak dijumpai — PDF gagal.", 
               "LibreOffice not found — PDF generation failed."),
    "qc_warn": ("Amaran QC ({}) — semak konsol.", "Quality warnings ({}) — see the console."),
    "saved_all": ("{} kertas dijana dalam {}", "{} papers generated in {}"),
    "save_docx_t": ("Simpan kertas (.docx)", "Save paper (.docx)"),
    "save_pdf_t": ("Simpan kertas (.pdf)", "Save paper (.pdf)"),
    "save_both_t": ("Simpan kertas (.docx + .pdf)", "Save paper (.docx + .pdf)"),
    "save_gen_t": ("Jana dan simpan kertas", "Generate and save paper"),
    "choose_folder": ("Pilih folder output", "Choose output folder"),
    "none_selected": ("Tiada kertas dijana lagi.", "No paper generated yet."),
    "edit_kertas": ("Edit Kertas…", "Edit Paper…"),
    "edit_save": ("Simpan Suntingan", "Save Edits"),
    "edit_cancel": ("Batal", "Cancel"),
    "edit_reset": ("Set Semula Bahagian", "Reset Part"),
    "edited_ok": ("Kertas dikemas kini.", "Paper updated."),
    "edit_inline": ("Edit Dalam Paparan", "Edit on Paper"),
    "edit_done": ("Selesai Sunting", "Done Editing"),
    "quick_ok": ("Soalan dikemas kini.", "Question updated."),
    "quick_hint": ("Klik mana-mana soalan untuk sunting.", 
                   "Click any question on the paper to edit it."),
}


_STATE = {"bm": False}


def _t(key: str, *args) -> str:
    en = U[key][1]
    return en.format(*args) if args else en


def _jsc_string(result) -> str:
    """Return the string a WebKit ``script-message-received`` callback got.

    WebKitGTK 6.0 passes a ``JSC.Value`` directly (``.to_string()``); older
    builds wrapped it in an object exposing ``get_js_value()``.  Handle both.
    """
    try:
        value = result
        if hasattr(result, "get_js_value"):
            value = result.get_js_value()
        fn = getattr(value, "to_string", None)
        if fn is None:
            return ""
        return str(fn() or "")
    except Exception:
        return ""


def parse_paper_eid(eid) -> tuple[int, int] | None:
    """Parse ``P<part>:I<item>`` (header = ``I-1``) into ``(part, item)``.

    Accepts the emitted ``P0:I2`` form (and a colon-less ``P0I2`` fallback).
    """
    body, _, item = str(eid or "").partition("I")
    body = body.rstrip(":")
    if not body.startswith("P"):
        return None
    try:
        return int(body[1:]), int(item or "-1")
    except ValueError:
        return None


class ExamApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.win = None
        self._theme = "dark"
        self._settings = {}
        self._crest_path = ""
        self._mode = None
        self._regen_timer = 0
        self._theme_idx: dict[int, int] = {}   # per-year RPT theme index
        self._user_bank = None
        self.paper = None
        self._open_paper = None     # paper as it was when an editor opened
        self._quick_item_idx = None
        self._undone = []           # paper_export snapshots (undo stack, S8)
        self._redone = []
        self.web_cache = None
        self.webview = None
        self._photo_thread = None
        self._photo_wanted = False
        self._photos_enabled = True
        self._editor = None
        self._editing = False

    # ----------------------------------------------------------- persistence
    def _settings_path(self):
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share")
        return os.path.join(base, "exam-gen", "settings.json")

    def _load_settings(self):
        self._saved_packs = {}
        self._settings = {}
        try:
            with open(self._settings_path(), encoding="utf-8") as fh:
                self._settings = json.load(fh)
        except Exception:
            self._settings = {}
        try:
            self._saved_packs = self._load_packs()
        except Exception:
            pass
        self._theme = "dark"

    def _save_settings(self):
        try:
            os.makedirs(os.path.dirname(self._settings_path()), exist_ok=True)
            if hasattr(self, "ent_school"):
                self._settings.update({
                    "school": self.ent_school.get_text().strip(),
                    "teacher": self.ent_teacher.get_text().strip(),
                    "pupil_id": self.ent_pupil.get_text().strip(),
                    "crest": getattr(self, "_crest_path", "") or "",
                    "qr": self.sw_qr.get_active(),
                    "calibrate": (self.sw_calibrate.get_active()
                                  if hasattr(self, "sw_calibrate") else False),
                })
            with open(self._settings_path(), "w", encoding="utf-8") as fh:
                json.dump({"theme": self._theme or "dark",
                           "packs": getattr(self, "_saved_packs", {}),
                           **self._settings},
                          fh, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _packs_path(self):
        return os.path.join(os.path.dirname(self._settings_path()),
                            "packs.json")

    def _load_packs(self):
        try:
            with open(self._packs_path(), encoding="utf-8") as fh:
                self._saved_packs = json.load(fh)
        except Exception:
            self._saved_packs = {}
        return self._saved_packs

    def _save_packs(self):
        try:
            os.makedirs(os.path.dirname(self._packs_path()), exist_ok=True)
            with open(self._packs_path(), "w", encoding="utf-8") as fh:
                json.dump(self._saved_packs, fh, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---------------------------------------------------------------- theme
    # The app is always in dark mode (Material 3 dark tokens).  The toggle /
    # auto behaviour was removed so the look is consistent across machines.
    def _apply_theme(self):
        Gtk.Settings.get_default().set_property(
            "gtk-application-prefer-dark-theme", True)
        if "dark" not in self.win.get_css_classes():
            self.win.add_css_class("dark")
        if "light" in self.win.get_css_classes():
            self.win.remove_css_class("light")
        self._save_settings()

    # ------------------------------------------------------------------ css
    def _install_css(self):
        css = os.path.join(os.path.dirname(__file__), "assets", "style.css")
        try:
            provider = Gtk.CssProvider()
            provider.load_from_path(css)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(), provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        except Exception:
            pass

    # ------------------------------------------------------------- activate
    def do_activate(self):
        self._install_css()
        self._install_actions()
        if self.win is not None:
            self.win.present()
            return
        self.web_cache = webfetch.load_cache()
        from . import textbook as TB
        self._textbook = TB.load_corpus() or None

        win = Gtk.ApplicationWindow(application=self)
        win.set_title(_t("app_title"))
        win.set_default_size(1240, 840)
        win.set_size_request(760, 580)
        win.add_css_class("dark")
        self.win = win

        header = Gtk.HeaderBar()
        header.set_show_title_buttons(True)
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon = Gtk.Image.new_from_file(os.path.join(
            os.path.dirname(__file__), "assets", "icon.svg"))
        icon.set_pixel_size(26)
        head.append(icon)
        head.append(Gtk.Label(label=_t("app_title"),
                              css_classes=["gen-title"]))
        header.set_title_widget(head)

        # Hamburger = configuration.  On wide windows it opens a side drawer
        # over the paper; on narrow ones it drops the same panel from the top.
        self.config_btn = Gtk.MenuButton(css_classes=["flat"])
        self.config_btn.set_icon_name("open-menu-symbolic")
        self.config_btn.set_tooltip_text(_t("btn_config"))
        header.pack_start(self.config_btn)

        menu = Gtk.PopoverMenu()
        gm = Gio.Menu()
        gm.append(_t("menu_bulk"), "app.bulk")
        gm.append(_t("menu_bulk12"), "app.bulk12")
        gm.append(_t("menu_compare"), "app.compare")
        gm.append(_t("menu_warm"), "app.warm")
        gm.append(_t("menu_termpack"), "app.termpack")
        gm.append(_t("menu_open_papers"), "app.open_papers")
        gm.append(_t("menu_pack_save"), "app.pack_save")
        gm.append(_t("menu_pack_load"), "app.pack_load")
        gm.append(_t("menu_bundle"), "app.bundle")
        gm.append(_t("menu_dskp"), "app.dskp")
        gm.append(_t("menu_results"), "app.results")
        gm.append(_t("menu_import"), "app.import_q")
        gm.append(_t("menu_about"), "app.about")
        menu.set_menu_model(gm)
        mbtn = Gtk.MenuButton(popover=menu, css_classes=["flat"])
        mbtn.set_icon_name("view-more-symbolic")
        header.pack_end(mbtn)

        gen = Gtk.Button(label=_t("btn_generate"), css_classes=["primary"])
        gen.connect("clicked", self.on_generate_save)
        header.pack_end(gen)

        win.set_titlebar(header)

        self._build_config_side()
        self._apply_saved_settings()
        self._build_preview()

        # The paper preview is the only main child: it always fills the whole
        # window.  Configuration slides over it (wide) or drops from the
        # hamburger (narrow), so the paper is never squeezed to one half.
        self.root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        win.set_child(self.root)
        self.root.append(self.overlay)

        self.drawer = Gtk.Revealer(
            transition_type=Gtk.RevealerTransitionType.SLIDE_RIGHT)
        self.drawer.add_css_class("config-drawer")
        self.drawer.set_halign(Gtk.Align.START)
        self.drawer.set_valign(Gtk.Align.FILL)
        self.drawer.set_vexpand(True)

        self.popover = Gtk.Popover()
        self.popover.add_css_class("config-popover")
        self.config_btn.connect("activate", self._on_config_btn)

        self._apply_layout(win.get_width())
        win.connect("notify::default-width", self._on_resize)
        win.connect("notify::width", self._on_resize)

        self._set_status(_t("web_none") if not self.web_total() else
                         _t("web_done", self.web_total(), len(self.web_cache)))
        self._regen()
        win.present()

    def _install_actions(self):
        bulk = Gio.SimpleAction.new("bulk", None)
        bulk.connect("activate", self.on_bulk)
        self.add_action(bulk)
        bulk12 = Gio.SimpleAction.new("bulk12", None)
        bulk12.connect("activate", self.on_bulk12)
        self.add_action(bulk12)
        compare = Gio.SimpleAction.new("compare", None)
        compare.connect("activate", self.on_compare)
        self.add_action(compare)
        warm = Gio.SimpleAction.new("warm", None)
        warm.connect("activate", self.on_warm)
        self.add_action(warm)
        termpack = Gio.SimpleAction.new("termpack", None)
        termpack.connect("activate", self.on_termpack)
        self.add_action(termpack)
        regen = Gio.SimpleAction.new("regen", None)
        regen.connect("activate", self.on_regen)
        self.add_action(regen)
        about = Gio.SimpleAction.new("about", None)
        about.connect("activate", self.on_about)
        self.add_action(about)

        open_papers = Gio.SimpleAction.new("open_papers", None)
        open_papers.connect("activate", self.on_open_papers)
        self.add_action(open_papers)

        pack_save = Gio.SimpleAction.new("pack_save", None)
        pack_save.connect("activate", self.on_pack_save)
        self.add_action(pack_save)

        pack_load = Gio.SimpleAction.new("pack_load", None)
        pack_load.connect("activate", self.on_pack_load)
        self.add_action(pack_load)

        bundle = Gio.SimpleAction.new("bundle", None)
        bundle.connect("activate", self.on_bundle)
        self.add_action(bundle)

        dskp = Gio.SimpleAction.new("dskp", None)
        dskp.connect("activate", self.on_dskp)
        self.add_action(dskp)

        results = Gio.SimpleAction.new("results", None)
        results.connect("activate", self.on_results)
        self.add_action(results)

        import_q = Gio.SimpleAction.new("import_q", None)
        import_q.connect("activate", self.on_import_q)
        self.add_action(import_q)

        undo = Gio.SimpleAction.new("undo", None)
        undo.connect("activate", self.on_undo)
        self.add_action(undo)
        redo = Gio.SimpleAction.new("redo", None)
        redo.connect("activate", self.on_redo)
        self.add_action(redo)
        self.set_accels_for_action("app.undo", ["<Control>z"])
        self.set_accels_for_action("app.redo",
                                   ["<Control><Shift>z", "<Control>y"])

    # ------------------------------------------------------------ my bank
    def _bank_save_part(self, part_idx: int, part_edits: dict):
        """\"Save to My Bank…\" — persist an edited part as a user-bank entry."""
        from . import editor
        if self.paper is None or not (0 <= part_idx < len(self.paper.parts)):
            return
        edits_parts = [{} for _ in self.paper.parts]
        edits_parts[part_idx] = part_edits
        paper = editor.apply_edits(self.paper, {"parts": edits_parts})
        part = paper.parts[part_idx]
        try:
            kind = bank.bank_kind_for(part)
            entry = bank.part_to_user_entry(
                part, year=int(self.conf().get("year", 0) or 0))
            if kind is None or entry is None:
                self._set_status(_t("bank_skip_writing"), "err")
                return
            try:
                bank.backup_state()   # Round 12/S10: never lose a whole bank
            except Exception:
                pass
            added = bank.save_user_bank_entry(bank.default_bank_path(),
                                              kind, entry)
            path = bank.default_bank_path()
            try:
                self._user_bank = bank.load_user_bank(path)
            except Exception:
                pass
        except Exception as exc:            # pragma: no cover - UI path
            self._set_status(str(exc), "err")
            return
        self._set_status(_t("bank_saved_one") if added
                         else _t("bank_dup"), "ok")

    # ------------------------------------------------------------ responsive
    def _on_resize(self, *_):
        GLib.idle_add(self._apply_layout, self.win.get_width())

    @staticmethod
    def _detach(widget):
        if widget.get_parent() is not None:
            widget.unparent()

    def _apply_layout(self, w: int):
        """Reparent the config panel by window width.

        wide  -> slide-in side drawer over the full-size paper preview
        narrow -> the same panel becomes a drop-down from the hamburger
        """
        thin = w < NARROW
        side = self.side_scroll
        if thin:
            if self._mode != "narrow":
                self.config_btn.set_popover(None)
                self.popover.set_child(None)
                self._detach(side)
                if self.drawer.get_parent() is self.overlay:
                    self.overlay.remove_overlay(self.drawer)
                self.popover.set_child(side)
                self.config_btn.set_popover(self.popover)
                self.side_scroll.set_size_request(320, 460)
            self._mode = "narrow"
        else:
            if self._mode != "wide":
                self.config_btn.set_popover(None)
                self.popover.set_child(None)
                self._detach(side)
                self.drawer.set_child(side)
                self.side_scroll.set_size_request(360, -1)
                self.side_scroll.set_vexpand(True)
                if self.drawer.get_parent() is None:
                    self.overlay.add_overlay(self.drawer)
                self.drawer.set_reveal_child(False)
            self._mode = "wide"

    def _on_config_btn(self, *_):
        if self._mode == "narrow":
            return                      # MenuButton pops the panel itself
        self.drawer.set_reveal_child(not self.drawer.get_reveal_child())

    # -------------------------------------------------------------- config UI
    def _build_config_side(self):
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        side.add_css_class("sidebar")
        side.set_hexpand(False)

        def card(title):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            box.add_css_class("card")
            box.append(Gtk.Label(label=title, xalign=0.0,
                                 css_classes=["overline"]))
            side.append(box)
            return box

        def field(parent, label):
            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            row.add_css_class("field-row")
            row.append(Gtk.Label(label=label, xalign=0.0,
                                 css_classes=["muted"]))
            parent.append(row)
            return row

        # school & exam
        c = card(_t("card_school"))
        self.ent_school = Gtk.Entry()
        self.ent_school.set_text("")
        r = field(c, _t("lbl_school"))
        r.append(self.ent_school)
        self.ent_teacher = Gtk.Entry()
        self.ent_teacher.set_text("")
        r = field(c, _t("lbl_teacher"))
        r.append(self.ent_teacher)
        self.ent_pupil = Gtk.Entry()
        r = field(c, _t("lbl_pupilid"))
        r.append(self.ent_pupil)
        r = field(c, _t("lbl_crest"))
        crest_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                            spacing=6)
        self.lbl_crestfile = Gtk.Label(label="", xalign=0.0, hexpand=True,
                                       ellipsize="start", css_classes=["muted"])
        choose = Gtk.Button(label=_t("btn_choose"), css_classes=["tonal"])
        choose.connect("clicked", self._on_choose_crest)
        crest_row.append(self.lbl_crestfile)
        crest_row.append(choose)
        r.append(crest_row)
        self.ent_school.connect("changed", self._on_touched)
        self.ent_teacher.connect("changed", self._on_touched)
        self.ent_pupil.connect("changed", self._on_touched)

        r = field(c, _t("lbl_examtype"))
        types = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.exam_chips = {}
        for key, label in (("upsa", "UPSA"), ("uasa", "UASA")):
            b = Gtk.ToggleButton(label=label, css_classes=["chip"])
            b.set_active(key == "upsa")
            b.connect("toggled", self._on_exam_chip, key)
            types.append(b)
            self.exam_chips[key] = b
        r.append(types)

        r = field(c, _t("lbl_session"))
        self.ent_session = Gtk.SpinButton.new_with_range(2020, 2035, 1)
        self.ent_session.set_value(D.DEFAULT_CONFIG["session"])
        self.ent_session.connect("value-changed", self._on_touched)
        r.append(self.ent_session)

        # year
        y = card(_t("card_year"))
        yrow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        group = None
        self.year_chips = {}
        for year in D.YEARS:
            b = Gtk.ToggleButton(label=f"Y{year}",
                                 css_classes=["chip", "small"], group=group)
            group = b
            b.set_active(year == D.DEFAULT_CONFIG["year"])
            b.connect("toggled", self._on_year_chip, year)
            yrow.append(b)
            self.year_chips[year] = b
        y.append(yrow)
        self.lbl_dur = Gtk.Label(xalign=0.0, css_classes=["muted"])
        y.append(self.lbl_dur)
        self._update_dur_label()

        r = field(y, _t("lbl_difficulty"))
        drow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        group = None
        self.diff_chips = {}
        for key in D.DIFFICULTIES:
            bm, en = DIFF_LABELS[key]
            b = Gtk.ToggleButton(label=bm if _STATE["bm"] else en,
                                 css_classes=["chip", "small"], group=group)
            group = b
            b.set_active(key == D.DEFAULT_CONFIG["difficulty"])
            b.connect("toggled", self._on_diff_chip, key)
            drow.append(b)
            self.diff_chips[key] = b
        r.append(drow)

        r = field(y, _t("lbl_theme"))
        self.sp_theme = Gtk.DropDown()
        r.append(self.sp_theme)
        self._fill_themes()
        self.sp_theme.connect("notify::selected", self._on_theme_changed)

        r = field(y, _t("lbl_week"))
        self.sp_week = Gtk.SpinButton.new_with_range(0, 40, 1)
        self.sp_week.set_value(0)
        self.sp_week.connect("value-changed", self._on_touched)
        r.append(self.sp_week)

        # parts
        pytitle = card(_t("card_parts"))
        prow = Gtk.FlowBox(column_spacing=6, row_spacing=4,
                           max_children_per_line=4)
        prow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.part_chips = {}
        for spec in D.PARTS[self.year()]:
            b = Gtk.ToggleButton(label=f"P{spec['id']} · {spec['marks']}m",
                                 css_classes=["chip", "small"])
            b.set_active(True)
            b.connect("toggled", self._on_touched)
            prow.append(b)
            self.part_chips[spec["id"]] = b
        pytitle.append(prow)

        # options
        o = card(_t("card_opts"))
        self.sw_key = self._switch(o, _t("lbl_key"), False)
        self.sw_sheet = self._switch(o, _t("lbl_sheet"), True)
        self.sw_pictures = self._switch(o, _t("lbl_pictures"), True)
        self.sw_marksheet = self._switch(o, _t("lbl_marksheet"), False)
        self.sw_abset = self._switch(o, _t("lbl_abset"), False)
        self.sw_web = self._switch(o, _t("lbl_web"), False)
        self.sw_qr = self._switch(o, _t("lbl_qr"), False)
        self.sw_calibrate = self._switch(o, _t("lbl_calibrate"), False)
        self._update_web_hint()
        r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        r.append(Gtk.Label(label=_t("lbl_bundle_n"), hexpand=True, xalign=0.0))
        self.sp_bundle = Gtk.SpinButton.new_with_range(2, 60, 1)
        self.sp_bundle.set_value(12)
        self.sp_bundle.connect("value-changed", self._on_touched)
        r.append(self.sp_bundle)
        o.append(r)
        r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        r.append(Gtk.Label(label=_t("lbl_seed"), hexpand=True, xalign=0.0))
        self.sp_seed = Gtk.SpinButton.new_with_range(1, 999, 1)
        self.sp_seed.set_value(D.DEFAULT_CONFIG["seed"])
        self.sp_seed.connect("value-changed", self._on_touched)
        r.append(self.sp_seed)
        o.append(r)

        fetch = Gtk.Button(label=_t("btn_fetch"), css_classes=["tonal"])
        fetch.connect("clicked", self.on_fetch_web)
        o.append(fetch)

        bank_btn = Gtk.Button(label=_t("btn_bank"), css_classes=["tonal"])
        bank_btn.connect("clicked", self.on_open_bank)
        o.append(bank_btn)

        backup_btn = Gtk.Button(label=_t("btn_backup"),
                                css_classes=["tonal"])
        backup_btn.connect("clicked", self.on_backup)
        o.append(backup_btn)

        self.status = Gtk.Label(selectable=True, wrap=True, xalign=0.0)
        self.status.add_css_class("statusbar")
        side.append(self.status)
        side.set_margin_bottom(2)

        self.side_scroll = Gtk.ScrolledWindow(vexpand=True)
        self.side_scroll.add_css_class("side-scroll")
        self.side_scroll.set_child(side)
        self.side_scroll.set_policy(Gtk.PolicyType.NEVER,
                                    Gtk.PolicyType.AUTOMATIC)

    def _switch(self, parent, label, default):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.append(Gtk.Label(label=label, hexpand=True, xalign=0.0, wrap=True))
        sw = Gtk.Switch()
        sw.set_active(default)
        sw.connect("state-set", self._on_touched)
        row.append(sw)
        parent.append(row)
        return sw

    def _on_choose_crest(self, *_):
        def ok(path):
            # Copy the picked image into the app data dir so the crest
            # persists even if the original file is moved or deleted (and
            # becomes the default `crest.png` everywhere).  Round 15 fix.
            persisted = D.persist_crest(path or "")
            if not persisted:
                self._set_status(_t("lbl_crest") + ": "
                                 "couldn't store image", "err")
                return
            self._crest_path = persisted
            self.lbl_crestfile.set_text(persisted)
            self._save_settings()
            self._on_touched()

        if hasattr(Gtk, "FileDialog"):
            ff = Gtk.FileFilter()
            ff.set_name("Image")
            for mime in ("image/png", "image/jpeg", "image/svg+xml"):
                ff.add_mime_type(mime)
            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(ff)
            fd = Gtk.FileDialog(title=_t("btn_choose"))
            fd.set_filters(filters)
            fd.open(self.win, None, self._open_cb, (ok,))
        else:  # pragma: no cover - legacy GTK
            dlg = Gtk.FileChooserNative(
                title=_t("btn_choose"), action=Gtk.FileChooserAction.OPEN,
                transient_for=self.win)
            if dlg.run() == Gtk.ResponseType.ACCEPT:
                ok(dlg.get_filename())
            dlg.destroy()

    def _open_cb(self, dialog, res, data):
        (on_ok,) = data
        try:
            f = dialog.open_finish(res)
        except GLib.Error:
            return
        GLib.idle_add(on_ok, f.get_path())

    def _apply_saved_settings(self):
        s = self._settings or {}
        _default_crest = D.default_crest_path()
        self.ent_school.set_text(str(s.get("school")
                                     or D.DEFAULT_CONFIG.get("school", "")))
        self.ent_teacher.set_text(str(s.get("teacher")
                                      or D.DEFAULT_CONFIG.get("teacher", "")))
        self.ent_pupil.set_text(str(s.get("pupil_id") or ""))
        self._crest_path = str(s.get("crest") or _default_crest)
        if not os.path.exists(self._crest_path):
            self._crest_path = _default_crest
        self.lbl_crestfile.set_text(self._crest_path)
        self.sw_qr.set_active(bool(s.get("qr")))
        if hasattr(self, "sw_calibrate"):
            self.sw_calibrate.set_active(bool(s.get("calibrate")))

    def _build_preview(self):
        self.preview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                   spacing=6)
        self.preview_box.add_css_class("preview-box")
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bar.add_css_class("preview-bar")
        self.fname = Gtk.Label(selectable=True, xalign=0.0, hexpand=True,
                               css_classes=["muted"], ellipsize="start")
        bar.append(self.fname)
        regen = Gtk.Button(label=_t("btn_regen"), css_classes=["tonal"])
        regen.connect("clicked", self.on_regen)
        bar.append(regen)
        self.bt_edit_inline = Gtk.ToggleButton(label=_t("edit_inline"),
                                               css_classes=["tonal"])
        self.bt_edit_inline.connect("toggled", self.on_toggle_inline_edit)
        bar.append(self.bt_edit_inline)
        editb = Gtk.Button(label=_t("edit_kertas"), css_classes=["tonal"])
        editb.connect("clicked", self.on_edit)
        bar.append(editb)
        buttons = [
            (_t("btn_open"), "tonal", self.on_open_docx),
            (_t("btn_save_docx"), "tonal", self.on_save_both),
            (_t("btn_save_pdf"), "tonal", self._save_pdf),
            (_t("btn_save_both"), "primary", self.on_save_both),
        ]
        for label, css, fn in buttons:
            b = Gtk.Button(label=label, css_classes=[css])
            b.connect("clicked", fn)
            bar.append(b)
        self.preview_box.append(bar)

        if HAVE_WEBKIT:
            self.webview = WebKit.WebView()
            self.webview.set_vexpand(True)
            self.webview.set_hexpand(True)
            self.preview_box.append(self.webview)
            mgr = self.webview.get_user_content_manager()
            try:
                mgr.register_script_message_handler("paperEdit")
            except Exception:
                pass
            mgr.connect("script-message-received::paperEdit",
                        self._on_paper_message)
        else:
            self.webview = None
            lab = Gtk.Label(
                label="WebKitGTK tidak dijumpai — pasang webkitgtk-6.0 untuk "
                      "paparan langsung.",
                css_classes=["muted"], vexpand=True, wrap=True, xalign=0.5)
            self.preview_box.append(lab)

        self.overlay = Gtk.Overlay(child=self.preview_box)
        self.overlay.set_vexpand(True)
        self.overlay.set_hexpand(True)

    # ---------------------------------------------------------------- state
    def year(self):
        for year, b in self.year_chips.items():
            if b.get_active():
                return year
        return D.DEFAULT_CONFIG["year"]

    def _exam_type(self):
        """The exam type the chips currently select (default UPSA)."""
        return next((k for k, b in getattr(self, "exam_chips", {}).items()
                     if b.get_active()), "upsa")

    def _update_dur_label(self):
        # Round 60: the duration depends on the exam type as well as the year
        # (Years 1-3 are a 60-minute UPSA paper and a 75-minute UASA paper),
        # so reading the year-only D.DURATION showed 60 minutes on a UASA.
        self.lbl_dur.set_text(_t(
            "dur_hint", D.duration_text(D.duration(self.year(),
                                                   self._exam_type()))))

    def _on_touched(self, *_):
        if self._regen_timer:
            GLib.source_remove(self._regen_timer)
        self._regen_timer = GLib.timeout_add(320, self._regen)

    def _on_exam_chip(self, btn, key):
        if btn.get_active():
            for k, b in self.exam_chips.items():
                if k != key:
                    b.set_active(False)
            self._update_dur_label()
            self._on_touched()

    def _update_web_hint(self):
        """Label the web toggle for the current year (Round 12/S2): Years 1-2
        sit behind the A1 cap so most Gutenberg passages are filtered out."""
        try:
            year = self.year()
            total = self.web_total()
            usable = webfetch.usable_for_year(year) if self.web_cache else 0
            tip = _t("web_y3plus") if year in (1, 2) else _t("lbl_web")
            if self.web_cache:
                tip += " — " + _t("web_usable", usable, total, year)
            self.sw_web.set_tooltip_text(tip)
        except Exception:
            pass

    def _on_year_chip(self, btn, year):
        if btn.get_active():
            for k, b in self.year_chips.items():
                if k != year:
                    b.set_active(False)
            self._update_dur_label()
            self._update_web_hint()
            self._fill_themes()
            self._on_touched()

    def _fill_themes(self):
        model = self.sp_theme.get_model()
        if model is None:
            model = Gtk.StringList()
            self.sp_theme.set_model(model)
        themes = list(D.RPT_THEMES.get(self.year(), []))
        model.splice(0, model.get_n_items(), ["Auto"] + themes)
        prev = self._theme_idx.get(self.year())
        self.sp_theme.set_selected((prev + 1) if prev is not None else 0)

    def _on_theme_changed(self, *_):
        themes = D.RPT_THEMES.get(self.year(), [])
        pos = self.sp_theme.get_selected()
        if pos <= 0:
            self._theme_idx.pop(self.year(), None)
        elif pos - 1 < len(themes):
            self._theme_idx[self.year()] = pos - 1
        else:
            self._theme_idx.pop(self.year(), None)
        self._on_touched()

    def _selected_theme(self) -> str:
        themes = D.RPT_THEMES.get(self.year(), [])
        pos = self.sp_theme.get_selected()
        if 0 < pos <= len(themes):
            return themes[pos - 1]
        return ""

    def _on_diff_chip(self, btn, key):
        if btn.get_active():
            for k, b in self.diff_chips.items():
                if k != key:
                    b.set_active(False)
            self._on_touched()

    def on_regen(self, *_):
        ns = bank.next_seed(int(self.sp_seed.get_value()))
        self.sp_seed.set_value(ns)
        year = self.year()
        themes = D.RPT_THEMES.get(year, [])
        cur = self._theme_idx.get(year)
        if themes:
            if cur is None:
                self._theme_idx[year] = 0
                self.sp_theme.set_selected(1)
            else:
                nxt, theme = bank.next_theme(year, cur)
                self._theme_idx[year] = nxt
                if theme in themes:
                    self.sp_theme.set_selected(themes.index(theme) + 1)
        if self._regen_timer:
            GLib.source_remove(self._regen_timer)
            self._regen_timer = 0
        # Never wait for the network: regenerate every question and answer
        # right now from the current seed/theme.  Round 17 — the textbooks are
        # the sole reference; the web cache is no longer fed into papers.
        self._regen()

    def web_total(self):
        return sum(len(v) for v in self.web_cache.values()) if self.web_cache else 0

    def _web_pool(self):
        pool = []
        if self.web_cache:
            for name in self.web_cache:
                pool.extend(self.web_cache.get(name, []))
        return pool

    def conf(self):
        c = {
            "school": self.ent_school.get_text().strip(),
            "teacher": self.ent_teacher.get_text().strip(),
            "crest": getattr(self, "_crest_path", "") or "",
            "pupil_id": (self.ent_pupil.get_text().strip()
                         if hasattr(self, "ent_pupil") else ""),
            "qr": self.sw_qr.get_active() if hasattr(self, "sw_qr") else False,
            "calibrate": (self.sw_calibrate.get_active()
                          if hasattr(self, "sw_calibrate") else False),
            "exam_type": next((k for k, b in self.exam_chips.items()
                               if b.get_active()), "upsa"),
            "session": int(self.ent_session.get_value()),
            "subject_key": "bi",
            "year": self.year(),
            "lang": "en",
            "answer_key": self.sw_key.get_active(),
            "answer_sheet": self.sw_sheet.get_active(),
            "pictures": self.sw_pictures.get_active(),
            "difficulty": next((k for k, b in self.diff_chips.items()
                                if b.get_active()), "medium"),
            "theme": self._selected_theme(),
            "week": int(self.sp_week.get_value()),
            "marksheet": self.sw_marksheet.get_active(),
            "ab": self.sw_abset.get_active(),
            "user_bank": self._user_bank,
            "use_web": self.sw_web.get_active(),
            "seed": int(self.sp_seed.get_value()),
            "parts": [pid for pid, b in self.part_chips.items()
                      if b.get_active()],
        }
        c["textbook"] = getattr(self, "_textbook", None)
        return c

    def _set_status(self, txt, cls=""):
        self.status.remove_css_class("ok")
        self.status.remove_css_class("err")
        self.status.remove_css_class("warn")
        if cls:
            self.status.add_css_class(cls)
        self.status.set_text(txt)

    # ------------------------------------------------------------ generation
    def _regen(self):
        self._regen_timer = 0
        conf = self.conf()
        passages = None                    # Round 17: textbooks, not the web
        paper = bank.generate_clean(conf, passages)
        self.paper = paper
        nq = sum(len(p.items) for p in paper.parts)
        st = _t("gen_status", len(paper.parts), D.TOTAL, nq)
        if conf["answer_key"]:
            st += _t("gen_key")
        if conf["use_web"]:
            st += _t("gen_web")
        pc = bank.paper_compliance(paper)
        qr = getattr(paper, "_qc", None)
        if qr is not None:
            st += f"  QC {qr.score}/10"
            if getattr(paper, "_qc_rolls", 0):
                rolls = paper._qc_rolls
                st += f" (re-rolled ×{rolls + 1})"
        if pc["ok"]:
            det = (f"RPT w{pc['week']} {pc['theme']}" if pc["week"]
                   else f"RPT {pc['theme'] or 'auto'}")
            self.status.set_tooltip_text("\n".join(pc["messages"]))
            self._set_status(st + f"  ✓ exam-ready · DSKP ✓ · CEFR ✓ · {det}",
                             "ok")
        else:
            self.status.set_tooltip_text(" · ".join(pc["issues"]))
            self._set_status(st + "  ✗ not a proper exam paper yet", "warn")
        self._photos_enabled = bool(conf["pictures"])
        # Render immediately using only cached photos (or SVG scenes) so the
        # UI never blocks on the network; pictures are then fetched in the
        # background and swapped in when ready.
        self._render_preview(allow_fetch=False)
        name = (f"{conf['exam_type'].upper()}_Tahun{conf['year']}_BI_"
                f"{conf['session']}_set{conf['seed']}.docx")
        self.fname.set_text(name)
        self._fetch_photos_async()
        return False

    def _render_preview(self, allow_fetch: bool = False):
        if self.webview is not None and self.paper is not None:
            self.webview.load_html(
                render_html.render_html(self.paper, allow_fetch=allow_fetch,
                                        editable=self._editing),
                "")

    def _fetch_photos_async(self):
        """Warm the photo cache off the UI thread, then re-render with photos."""
        self._photo_wanted = True
        t = self._photo_thread
        if t is not None and t.is_alive():
            return                      # running worker will pick up the rest
        self._photo_thread = threading.Thread(target=self._photo_worker,
                                              daemon=True)
        self._photo_thread.start()

    def _photo_worker(self):
        while self._photo_wanted:
            self._photo_wanted = False
            paper = self.paper
            if paper is None or not self._photos_enabled:
                break
            queries = [q for p in paper.parts
                       for q in art.photo_candidates(p) if q]
            art.reset_photo_budget()
            try:
                art.fetch_photos(queries)
            except Exception:
                pass
            GLib.idle_add(self._photos_ready, paper)

    def _photos_ready(self, paper):
        if self.paper is paper:
            self._render_preview(allow_fetch=False)
        return False

    # ------------------------------------------------------------ inline edit
    def on_toggle_inline_edit(self, *_):
        self._editing = self.bt_edit_inline.get_active()
        self.bt_edit_inline.set_label(_t("edit_done") if self._editing
                                      else _t("edit_inline"))
        self._set_status(_t("quick_hint"), "ok")
        self._render_preview(allow_fetch=False)

    def _on_paper_message(self, mgr, result):
        parsed = parse_paper_eid(_jsc_string(result))
        if parsed is None:
            return
        pi, ii = parsed
        if self.paper is not None and 0 <= pi < len(self.paper.parts):
            GLib.idle_add(self._open_quick_edit, pi, ii)

    def _open_quick_edit(self, pi, ii):
        self._quick_edit_win(pi, ii if ii >= 0 else None)
        return False

    def _quick_edit_win(self, part_idx: int, item_idx: int | None):
        if self.paper is None:
            return
        from . import editor
        self._open_paper = bank.paper_export(self.paper)
        self._quick_item_idx = item_idx
        part = self.paper.parts[part_idx]
        title = f"PART {part.num}"
        if item_idx is not None:
            qnos = part.qnos()
            q = qnos[min(item_idx, len(qnos) - 1)] if qnos else "?"
            title += f" · Q{q}"
        win = Gtk.Window(transient_for=self.win, modal=True)
        win.set_title(title)
        win.set_default_size(760, 620)
        win.add_css_class("dark")
        header = Gtk.HeaderBar()
        cancel = Gtk.Button(label=_t("edit_cancel"), css_classes=["flat"])
        cancel.connect("clicked", lambda *_: win.close())
        header.pack_start(cancel)
        reset = Gtk.Button(label=_t("edit_reset"), css_classes=["flat"])
        reset.connect("clicked",
                      lambda *_: self._quick_edit_reset(win, part_idx))
        header.pack_start(reset)
        save = Gtk.Button(label=_t("edit_save"), css_classes=["primary"])
        save.connect("clicked",
                     lambda *_: self._quick_edit_save(win, part_idx, item_idx))
        header.pack_end(save)
        win.set_titlebar(header)
        self._quick_editor = editor.QuickItemEditor(
            self.paper, part_idx, item_idx)
        self._quick_editor.on_save_to_bank = self._bank_save_part
        win.set_child(self._quick_editor.scrolled)
        win.present()

    def _quick_edit_reset(self, win, part_idx: int):
        """Revert this entire part to how it read when the editor opened
        (Round 12/S8 reset-part), then reopen the small editor."""
        from . import editor
        if self.paper is None or self._open_paper is None:
            win.close()
            return
        orig = bank.paper_from_export(self._open_paper)
        if not (0 <= part_idx < len(orig.parts)):
            win.close()
            return
        edits_parts = [{} for _ in self.paper.parts]
        edits_parts[part_idx] = editor.part_to_edit(orig.parts[part_idx])
        self._snapshot_undo()
        self.paper = editor.apply_edits(self.paper, {"parts": edits_parts})
        self._render_preview(allow_fetch=False)
        self._set_status(_t("reset_ok"), "ok")
        win.close()
        if (0 <= part_idx < len(self.paper.parts)
                and self.paper.parts[part_idx].items):
            self._quick_edit_win(part_idx, self._quick_item_idx)

    def _quick_edit_save(self, win, part_idx: int, item_idx: int | None):
        from . import editor
        qe = getattr(self, "_quick_editor", None)
        if qe is None:
            win.close()
            return
        try:
            collected = qe.collect()["parts"][0]
            part = self.paper.parts[part_idx]
            merged = editor.part_to_edit(part)
            merged["lead"] = collected["lead"]
            merged["lead_text"] = collected["lead_text"]
            if "marks" in collected:
                merged["marks"] = collected["marks"]
            if item_idx is not None and collected.get("items"):
                target = min(item_idx, len(part.items) - 1)
                merged["items"][target] = collected["items"][0]
            edits_parts = [{} for _ in self.paper.parts]
            edits_parts[part_idx] = merged
            self._snapshot_undo()
            self.paper = editor.apply_edits(self.paper,
                                            {"parts": edits_parts})
        finally:
            self._quick_editor = None
        self._render_preview(allow_fetch=False)
        self._set_status(_t("quick_ok"), "ok")
        win.close()

    # ----------------------------------------------------------------- editor
    def _snapshot_undo(self):
        """Remember the current paper so an edit can be undone (Round 12/S8)."""
        if self.paper is None:
            return
        self._undone.append(bank.paper_export(self.paper))
        del self._undone[:-30]
        self._redone.clear()

    def _restore_paper(self, export):
        self.paper = bank.paper_from_export(export)
        self._render_preview(allow_fetch=False)

    def on_undo(self, *_):
        if not self._undone:
            self._set_status(_t("undo_none"), "err")
            return
        if self.paper is not None:
            self._redone.append(bank.paper_export(self.paper))
        self._restore_paper(self._undone.pop())
        self._set_status(_t("undo_ok"), "ok")

    def on_redo(self, *_):
        if not self._redone:
            self._set_status(_t("redo_none"), "err")
            return
        if self.paper is not None:
            self._undone.append(bank.paper_export(self.paper))
        self._restore_paper(self._redone.pop())
        self._set_status(_t("redo_ok"), "ok")

    def on_edit(self, *_):
        """Open the structured editor for the current paper."""
        if self.paper is None:
            self._set_status(_t("none_selected"), "err")
            return
        from . import editor
        win = Gtk.Window(transient_for=self.win, modal=True)
        win.set_title(_t("edit_kertas"))
        win.set_default_size(860, 700)
        win.add_css_class("dark")
        header = Gtk.HeaderBar()
        cancel = Gtk.Button(label=_t("edit_cancel"), css_classes=["flat"])
        cancel.connect("clicked", lambda *_: win.close())
        header.pack_start(cancel)
        save = Gtk.Button(label=_t("edit_save"), css_classes=["primary"])
        save.connect("clicked", lambda *_: self._editor_save(win))
        header.pack_end(save)
        win.set_titlebar(header)
        try:
            self._editor = editor.PaperEditor(self.paper)
            self._editor.on_save_to_bank = self._bank_save_part
        except Exception as exc:           # pragma: no cover - display only
            self._set_status(str(exc), "err")
            return
        win.set_child(self._editor.scrolled)
        win.present()

    def _editor_save(self, win):
        from . import editor
        if self._editor is None:
            win.close()
            return
        try:
            self._snapshot_undo()
            self.paper = editor.apply_edits(self.paper, self._editor.collect())
        finally:
            self._editor = None
        self._render_preview(allow_fetch=False)
        self._set_status(_t("edited_ok"), "ok")
        win.close()

    def on_fetch_web(self, *_):
        # Round 17/T3: Gutenberg passages are retired — the pupil's textbooks
        # are the sole reference for every question.  Web fetching now only
        # concerns the Wikimedia-Commons photos, which are pulled on demand by
        # the renderer (so this button only confirms the change).
        self._set_status(_t("web_retired"), "ok")

    def on_backup(self, *_):
        """Round 12/S10: timestamped copies of the user bank + packs."""
        try:
            done = bank.backup_state()
        except Exception as exc:            # pragma: no cover - UI path
            self._set_status(str(exc), "err")
            return
        if not done:
            self._set_status(_t("backup_none"), "err")
            return
        self._set_status(_t("backup_done", done.replace("\n", " · ")), "ok")

    def _on_web_done(self, cache):
        self.web_cache = cache
        n = sum(len(v) for v in cache.values())
        self._update_web_hint()
        self._set_status(_t("web_done", n, len(cache)), "ok")
        self._regen()

    def on_open_bank(self, *_):
        if hasattr(Gtk, "FileDialog"):
            fd = Gtk.FileDialog(title=_t("btn_bank"))
            fd.open(self.win, None, self._bank_cb)
        else:  # pragma: no cover - legacy GTK
            dlg = Gtk.FileChooserNative(
                title=_t("btn_bank"), action=Gtk.FileChooserAction.OPEN,
                transient_for=self.win)
            if dlg.run() == Gtk.ResponseType.ACCEPT:
                self._bank_load(dlg.get_filename())
            dlg.destroy()

    def _bank_cb(self, fd, res, _):
        try:
            f = fd.open_finish(res)
        except GLib.Error:
            return
        self._bank_load(f.get_path())

    def _bank_load(self, path):
        try:
            parsed = bank.load_user_bank(path)
        except Exception as exc:
            self._set_status(_t("bank_error", exc), "err")
            return
        self._user_bank = parsed
        n = sum(len(v) for y in parsed.values()
                for v in (y.values() if isinstance(y, dict) else []))
        self._set_status(_t("bank_loaded", n), "ok")
        self._regen()

    # -------------------------------------------------------------- exports
    def _tmp_docx(self):
        import tempfile
        fd, path = tempfile.mkstemp(suffix=".docx", prefix="examgen-")
        os.close(fd)
        return path

    def on_open_docx(self, *_):
        if self.paper is None:
            self._set_status(_t("none_selected"), "err")
            return
        tmp = pdfmake.save_docx(self.paper, self._tmp_docx(),
                                allow_fetch=False)
        subprocess.Popen(["xdg-open", tmp])

    def _ask_save(self, title, filename, on_ok):
        if self.paper is None:
            self._set_status(_t("none_selected"), "err")
            return
        if hasattr(Gtk, "FileDialog"):
            fd = Gtk.FileDialog(title=title)
            fd.set_initial_name(filename)
            fd.save(self.win, None, self._save_cb, (on_ok,))
        else:  # pragma: no cover - legacy GTK
            dlg = Gtk.FileChooserNative(
                title=title, action=Gtk.FileChooserAction.SAVE,
                transient_for=self.win)
            dlg.set_current_name(filename)
            if dlg.run() == Gtk.ResponseType.ACCEPT:
                on_ok(dlg.get_filename())
            dlg.destroy()

    def _save_cb(self, fd, res, data):
        (on_ok,) = data
        try:
            f = fd.save_finish(res)
        except GLib.Error:
            return
        GLib.idle_add(on_ok, f.get_path())

    def _base_name(self):
        conf = self.conf()
        suf = "A" if conf.get("ab") else ""
        return (f"{conf['exam_type'].upper()}_Tahun{conf['year']}_BI_"
                f"{conf['session']}_set{conf['seed']}{suf}")

    def _run_export(self, work, done):
        """Run ``work()`` on a worker thread; call ``done(result)`` on the
        UI thread via GLib.idle_add so LibreOffice export never freezes the
        window.  Saves already render from the photo cache (allow_fetch=False),
        so the background step only writes files + spawns soffice."""
        import threading

        def _worker():
            try:
                res = work()
            except Exception as exc:        # pragma: no cover - defensive
                res = exc
            GLib.idle_add(lambda: done(res))

        threading.Thread(target=_worker, daemon=True).start()

    def on_save_both(self, *_):
        base = self._base_name() + ".docx"
        self._ask_save(_t("save_both_t"), base, self._do_save_both)

    def _do_save_both(self, path):
        path = str(path)
        if path.lower().endswith(".pdf"):
            path = path[:-4]
        elif path.lower().endswith(".docx"):
            path = path[:-5]
        conf = dict(self.conf())

        def work():
            res = pdfmake.save_with_extras(self.paper, path, want_pdf=True,
                                           marksheet=conf.get("marksheet", False),
                                           allow_fetch=False)
            if conf.get("ab"):
                bconf = dict(conf)
                bconf["seed"] = bank.next_seed(int(conf["seed"]))
                b_paper = bank.generate_clean(bconf, None)
                pdfmake.save_paper(b_paper, path + "B", want_pdf=True,
                                   allow_fetch=False)
                return None
            return res

        def done(res):
            if isinstance(res, Exception):            # pragma: no cover
                self._set_status(_t("save_error", res), "err")
            else:
                issues = bank.quality_issues(self.paper)
                if issues:
                    for issue in issues:
                        print(f"QC: - {issue}")
                marked = conf.get("marksheet")
                if conf.get("ab"):
                    self._set_status(_t("saved_ab") if marked
                                     else _t("saved_ab_simple"), "ok")
                elif res and res.get("pdf"):
                    base = os.path.basename(path) + ".docx"
                    if issues:
                        self._set_status(
                            _t("qc_warn", len(issues)) + " " +
                            _t("saved_both", base), "warn")
                    else:
                        self._set_status(_t("saved_both", base), "ok")
                else:
                    self._set_status(_t("no_pdf"), "err")
            self._regen()

        self._set_status(_t("saving"))
        self._run_export(work, done)

    def _save_pdf(self, *_):
        base = self._base_name() + ".pdf"
        self._ask_save(_t("save_pdf_t"), base, self._do_save_pdf)

    def _do_save_pdf(self, path):
        path = str(path)
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        tmp = self._tmp_docx()

        def work():
            pdfmake.save_docx(self.paper, tmp, allow_fetch=False)
            return pdfmake.docx_to_pdf(tmp, path)

        def done(ok):
            try:
                os.remove(tmp)
            except OSError:
                pass
            self._set_status(_t("saved_pdf", os.path.basename(path)) if ok
                             else _t("no_pdf"), "ok" if ok else "err")

        self._set_status(_t("saving"))
        self._run_export(work, done)

    def on_generate_save(self, *_):
        self._regen()
        base = self._base_name() + ".docx"
        self._ask_save(_t("save_both_t"), base, self._do_save_both)

    def _open_folder(self, folder):
        try:
            subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            try:
                self._set_status(str(e), "err")
            except Exception:
                pass
        return False

    # ---------------------------------------------------------------- bulk
    def on_bulk(self, *_):
        fd = Gtk.FileDialog(title=_t("choose_folder"))
        fd.select_folder(self.win, None, self._bulk_cb, None)

    def _bulk_cb(self, fd, res, _):
        try:
            folder = fd.select_folder_finish(res)
        except GLib.Error:
            return
        folder = folder.get_path()
        self._set_status(_t("web_fetching"))

        def work():
            try:
                conf = self.conf()
                entries = []
                for year in D.YEARS:
                    c = dict(conf)
                    c["year"] = year
                    c["seed"] = int(conf["seed"]) + year
                    paper = bank.generate_clean(c, None)
                    stem = (f"{c['exam_type'].upper()}_Tahun{year}_BI_"
                            f"{c['session']}")
                    entries.append((paper, stem,
                                    {"marksheet": conf.get("marksheet", False),
                                     "imgs": None, "allow_fetch": False}))
                    if conf.get("ab"):
                        bc = dict(c)
                        bc["seed"] = bank.next_seed(int(c["seed"]))
                        b_paper = bank.generate_clean(bc, None)
                        entries.append((b_paper, stem + "B",
                                        {"marksheet": False, "imgs": None,
                                         "allow_fetch": False}))
                pdfmake.batch_save(entries, folder, want_pdf=True)
                import json as _json
                for paper, stem, extra in entries:
                    stem = os.path.splitext(stem)[0]
                    try:
                        with open(os.path.join(folder, stem + ".json"), "w",
                                  encoding="utf-8") as fh:
                            _json.dump(bank.paper_export(paper), fh,
                                       ensure_ascii=False, indent=2)
                    except Exception:
                        pass
                count = len(entries)
                GLib.idle_add(self._set_status,
                              _t("saved_all", count, folder), "ok")
                GLib.idle_add(self._open_folder, folder)
            except Exception as e:
                GLib.idle_add(self._set_status, str(e), "err")

        threading.Thread(target=work, daemon=True).start()

    def on_bulk12(self, *_):
        try:
            fd = Gtk.FileDialog(title=_t("choose_folder"))
            fd.select_folder(self.win, None, self._bulk12_cb, None)
        except Exception as e:
            self._set_status(str(e), "err")

    def _bulk12_cb(self, fd, res, _):
        try:
            folder = fd.select_folder_finish(res)
        except GLib.Error:
            return
        try:
            folder = folder.get_path()
        except Exception as e:
            self._set_status(str(e), "err")
            return
        self._set_status(_t("web_fetching"))

        def work():
            try:
                conf = self.conf()
                entries = []
                for year in D.YEARS:
                    pair = bank.generate_year_pair(
                        year, seed=int(conf.get("seed", 1)) + year,
                        difficulty=conf.get("difficulty", "medium"))
                    for tag, paper in (("UPSA", pair[0]), ("UASA", pair[1])):
                        stem = (f"{tag}_Tahun{year}_BI_"
                                f"{conf.get('session', 2026)}")
                        entries.append((paper, stem, {
                            "marksheet": bool(conf.get("marksheet", False)),
                            "imgs": None, "allow_fetch": False}))
                pdfmake.batch_save(entries, folder, want_pdf=True)
                count = len(entries)
                GLib.idle_add(self._set_status,
                              _t("saved_all", count, folder), "ok")
                GLib.idle_add(self._open_folder, folder)
            except Exception as e:
                GLib.idle_add(self._set_status, str(e), "err")

        threading.Thread(target=work, daemon=True).start()

    def on_compare(self, *_):
        if self.paper is None:
            self._set_status(_t("bundle_none"), "err")
            return
        try:
            conf = self.conf()
            bconf = dict(conf)
            bconf["seed"] = bank.next_seed(int(conf.get("seed", 1)))
            other = bank.generate_clean(bconf, None)
            rep = bank.repeat_report([self.paper, other])
            text = rep.get("text", "")
            win = Gtk.Window(transient_for=self.win, modal=True)
            win.set_title(_t("menu_compare"))
            win.set_default_size(520, 320)
            win.add_css_class("dark")
            view = Gtk.TextView()
            view.set_editable(False)
            view.get_buffer().set_text(text + "\n\n"
                                      + "Variant seed: " + str(bconf["seed"]))
            sw = Gtk.ScrolledWindow(vscrollbar_policy=Gtk.PolicyType.AUTOMATIC)
            sw.set_child(view)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                          margin_top=12, margin_bottom=12,
                          margin_start=12, margin_end=12)
            box.append(sw)
            btn = Gtk.Button(label="OK")
            btn.connect("clicked", lambda *_: win.close())
            box.append(btn)
            win.set_child(box)
            win.show()
        except Exception as e:
            self._set_status(str(e), "err")

    def on_warm(self, *_):
        if self.paper is None:
            self._set_status(_t("bundle_none"), "err")
            return

        def work():
            try:
                queries = [q for part in self.paper.parts
                           for q in art.photo_candidates(part) if q]
                art.reset_photo_budget()
                art.fetch_photos(queries)
                GLib.idle_add(self._render_preview, False)
                GLib.idle_add(self._set_status, "Photo cache warmed", "ok")
            except Exception as e:
                GLib.idle_add(self._set_status, str(e), "err")

        threading.Thread(target=work, daemon=True).start()

    def on_termpack(self, *_):
        fd = Gtk.FileDialog(title=_t("choose_folder"))
        fd.select_folder(self.win, None, self._termpack_cb, None)

    def _termpack_cb(self, fd, res, _):
        try:
            folder = fd.select_folder_finish(res)
        except GLib.Error:
            return
        folder = folder.get_path()
        self._set_status(_t("web_fetching"))

        def work():
            try:
                conf = self.conf()
                entries = []
                for year in D.YEARS:
                    pair = bank.generate_year_pair(
                        year, seed=int(conf.get("seed", 1)) + year,
                        difficulty=conf.get("difficulty", "medium"))
                    for tag, paper in (("UPSA", pair[0]), ("UASA", pair[1])):
                        stem = f"{tag}_Tahun{year}_BI_{conf.get('session', 2026)}"
                        entries.append((paper, stem, {
                            "marksheet": bool(conf.get("marksheet", False)),
                            "imgs": None, "allow_fetch": False}))
                pdfmake.batch_save(entries, folder, want_pdf=True)
                import json as _json, os as _os, zipfile as _zip
                for paper, stem, extra in entries:
                    stem = _os.path.splitext(stem)[0]
                    try:
                        with open(_os.path.join(folder, stem + ".json"), "w",
                                  encoding="utf-8") as fh:
                            _json.dump(bank.paper_export(paper), fh,
                                       ensure_ascii=False, indent=2)
                    except Exception:
                        pass
                zip_path = _os.path.join(_os.path.dirname(folder),
                                         _os.path.basename(folder) + "_termpack.zip")
                with _zip.ZipFile(zip_path, "w", _zip.ZIP_DEFLATED) as z:
                    for root, _, files in _os.walk(folder):
                        for fn in files:
                            full = _os.path.join(root, fn)
                            arc = _os.path.relpath(full, _os.path.dirname(folder))
                            z.write(full, arc)
                GLib.idle_add(self._set_status,
                              "Term pack: " + zip_path, "ok")
                GLib.idle_add(self._open_folder, _os.path.dirname(folder))
            except Exception as e:
                GLib.idle_add(self._set_status, str(e), "err")

        threading.Thread(target=work, daemon=True).start()

    def on_bundle(self, *_):
        if self.paper is None:
            self._set_status(_t("bundle_none"), "err")
            return
        base = f"{self._base_name()}_class_set"
        self._ask_save(_t("menu_bundle"), base + ".docx", self._do_bundle)

    def _do_bundle(self, path):
        path = str(path)
        if path.lower().endswith(".pdf"):
            path = path[:-4]
        elif path.lower().endswith(".docx"):
            path = path[:-5]
        conf = dict(self.conf())
        n = int(self.sp_bundle.get_value())

        def work():
            papers = bank.bundle_papers(conf, n, None)
            return pdfmake.save_bundle(
                papers, path,
                class_label=f"Year {conf['year']}",
                allow_fetch=False)

        def done(res):
            if isinstance(res, Exception):     # pragma: no cover
                self._set_status(_t("save_error", res), "err")
            else:
                m = (f"{n} papers + marking sheet"
                     if res.get("pdf") else f"{n} papers")
                self._set_status(_t("bundle_saved", m), "ok")
            self._regen()

        self._set_status(_t("saving"))
        self._run_export(work, done)

    def on_dskp(self, *_):
        if self.paper is None:
            self._set_status(_t("bundle_none"), "err")
            return
        text = bank.dskp_report(self.paper)
        win = Gtk.Window(transient_for=self.win, modal=True)
        win.set_title(_t("dskp_title", self.paper.year()))
        win.set_default_size(560, 420)
        win.add_css_class("dark")
        view = Gtk.TextView()
        view.set_editable(False)
        buffer = view.get_buffer()
        buffer.set_text(text)
        sw = Gtk.ScrolledWindow(vscrollbar_policy=Gtk.PolicyType.AUTOMATIC)
        sw.set_child(view)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                      margin_top=12, margin_bottom=12,
                      margin_start=12, margin_end=12)
        box.append(sw)
        btn = Gtk.Button(label="OK")
        btn.connect("clicked", lambda *_: win.close())
        box.append(btn)
        win.set_child(box)
        win.show()

    def on_results(self, *_):
        if self.paper is None:
            self._set_status(_t("results_none"), "err")
            return
        if hasattr(Gtk, "FileDialog"):
            ff = Gtk.FileFilter()
            ff.set_name("CSV")
            ff.add_mime_type("text/csv")
            ff.add_pattern("*.csv")
            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(ff)
            fd = Gtk.FileDialog(title=_t("menu_results"))
            fd.set_filters(filters)
            fd.open(self.win, None, self._open_cb,
                    (self._results_ok,))
        else:  # pragma: no cover - legacy GTK
            dlg = Gtk.FileChooserNative(
                title=_t("menu_results"),
                action=Gtk.FileChooserAction.OPEN, transient_for=self.win)
            if dlg.run() == Gtk.ResponseType.ACCEPT:
                self._results_ok(dlg.get_filename())
            dlg.destroy()

    def _results_ok(self, path):
        from . import marks as M
        path = str(path or "")
        try:
            with open(path, encoding="utf-8") as fh:
                pupils = M.pupils_from_csv(fh.read())
        except OSError as exc:
            self._set_status(_t("results_read_err", exc), "err")
            return
        if not pupils:
            self._set_status(_t("results_none"), "err")
            return
        paper = self.paper
        summary = M.results_csv([paper], pupils)
        base = os.path.splitext(path)[0] + ".summary.csv"
        try:
            with open(base, "w", encoding="utf-8") as fh:
                fh.write(summary)
        except OSError as exc:
            self._set_status(_t("results_read_err", exc), "err")
            return
        tot = M.out_of([paper])
        grades: dict[str, int] = {}
        for p in pupils:
            g = M.grade(M.total_mark(p, [paper]), tot)
            grades[g] = grades.get(g, 0) + 1
        spread = ", ".join(f"{g}={grades[g]}" for g in sorted(grades))
        self._set_status(_t("results_ok", len(pupils),
                            f"{base} [{spread}]"), "ok")

    def on_import_q(self, *_):
        ff = Gtk.FileFilter()
        ff.set_name("CSV / JSON")
        for mime, pat in (("text/csv", "*.csv"), ("application/json", "*.json")):
            ff.add_mime_type(mime)
            ff.add_pattern(pat)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(ff)
        if hasattr(Gtk, "FileDialog"):
            fd = Gtk.FileDialog(title=_t("menu_import"))
            fd.set_filters(filters)
            fd.open(self.win, None, self._open_cb,
                    (self._import_q_ok,))
        else:  # pragma: no cover - legacy GTK
            dlg = Gtk.FileChooserNative(
                title=_t("menu_import"),
                action=Gtk.FileChooserAction.OPEN, transient_for=self.win)
            if dlg.run() == Gtk.ResponseType.ACCEPT:
                self._import_q_ok(dlg.get_filename())
            dlg.destroy()

    def _import_q_ok(self, path):
        path = str(path or "")
        try:
            if path.lower().endswith(".json"):
                verdict = bank.import_past_json(path)
                self._set_status(
                    _t("import_json_ok", verdict["questions"]), "ok")
            elif path.lower().endswith(".csv"):
                n = bank.import_csv(path, year=int(self.conf()["year"]))
                self._set_status(_t("import_ok", n), "ok")
            else:
                self._set_status(_t("import_bad", path), "err")
                return
        except Exception as exc:
            self._set_status(_t("import_bad", exc), "err")

    def on_about(self, *_):
        dlg = Gtk.AlertDialog() if hasattr(Gtk, "AlertDialog") else None
        text = (f"{APP_NAME} 1.0.0\n\n"
                "Penjana kertas ujian Bahasa Inggeris (UPSA/UASA) untuk "
                "murid SJKC Tahun 1, 2, 3, 5 & 6.\n"
                "Based on the SJKC UPSA 2026 paper format.")
        if dlg is not None:
            dlg.set_message(text)
            dlg.show(self.win)
        else:  # pragma: no cover
            d = Gtk.Dialog(transient_for=self.win)
            d.add_button("OK", Gtk.ResponseType.OK)
            d.set_default_size(420, 220)
            d.get_content_area().append(Gtk.Label(label=text, wrap=True))
            d.show()

    # ------------------------------------------------------------ packs (R2)
    def on_open_papers(self, *_):
        folder = os.path.join(os.path.dirname(self._settings_path()), "papers")
        try:
            os.makedirs(folder, exist_ok=True)
            subprocess.Popen(["xdg-open", folder])
        except Exception as exc:          # pragma: no cover - display only
            self._set_status(str(exc), "err")

    def on_pack_save(self, *_):
        win = Gtk.Window(transient_for=self.win, modal=True)
        win.set_title(_t("menu_pack_save"))
        win.set_default_size(380, 160)
        win.add_css_class("dark")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                      spacing=10, margin_top=16, margin_bottom=16,
                      margin_start=16, margin_end=16)
        entry = Gtk.Entry()
        entry.set_placeholder_text(_t("pack_name_me"))
        entry.set_text(self.ent_school.get_text().strip() or "Pek saya")
        box.append(entry)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        ok = Gtk.Button(label="Simpan", css_classes=["primary"])
        no = Gtk.Button(label="Batal", css_classes=["flat"])
        row.append(no)
        row.append(ok)
        box.append(row)
        win.set_child(box)

        def _go(*_):
            name = entry.get_text().strip()
            win.close()
            if not name:
                return
            conf = dict(self.conf())
            conf.pop("user_bank", None)
            self._saved_packs = self._load_packs()
            self._saved_packs[name] = conf
            self._save_packs()
            self._set_status(_t("pack_done", name), "ok")

        ok.connect("clicked", _go)
        no.connect("clicked", lambda *_: win.close())
        win.present()

    def on_pack_load(self, *_):
        packs = self._load_packs()
        if not packs:
            self._set_status(_t("pack_none"), "err")
            return
        win = Gtk.Window(transient_for=self.win, modal=True)
        win.set_title(_t("menu_pack_load"))
        win.set_default_size(420, 240)
        win.add_css_class("dark")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                      spacing=10, margin_top=16, margin_bottom=16,
                      margin_start=16, margin_end=16)
        store = Gtk.StringList.new(sorted(packs))
        drop = Gtk.DropDown.new_from_strings(sorted(packs))
        box.append(drop)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        ok = Gtk.Button(label="Muat", css_classes=["primary"])
        no = Gtk.Button(label="Batal", css_classes=["flat"])
        row.append(no)
        row.append(ok)
        box.append(row)
        win.set_child(box)

        def _go(*_):
            name = sorted(packs)[drop.get_selected()]
            win.close()
            self._apply_pack(packs[name])
            self._set_status(_t("pack_loaded", name), "ok")

        ok.connect("clicked", _go)
        no.connect("clicked", lambda *_: win.close())
        win.present()

    def _apply_pack(self, conf: dict):
        """Push a saved pack back onto the controls and regenerate."""
        if "school" in conf:
            self.ent_school.set_text(str(conf.get("school", "")))
        if "teacher" in conf:
            self.ent_teacher.set_text(str(conf.get("teacher", "")))
        if "session" in conf:
            self.ent_session.set_value(float(conf["session"]))
        if "seed" in conf:
            self.sp_seed.set_value(float(conf["seed"]))
        if "week" in conf:
            self.sp_week.set_value(float(conf["week"]))
        if "exam_type" in conf:
            for k, b in self.exam_chips.items():
                b.set_active(k == conf.get("exam_type"))
        if "year" in conf:
            for y, b in self.year_chips.items():
                b.set_active(int(y) == int(conf["year"]))
            self._update_dur_label()
            self._fill_themes()
        for key, sw in (("answer_key", self.sw_key),
                        ("answer_sheet", self.sw_sheet),
                        ("pictures", self.sw_pictures),
                        ("marksheet", self.sw_marksheet),
                        ("ab", self.sw_abset),
                        ("use_web", self.sw_web)):
            if key in conf:
                sw.set_active(bool(conf[key]))
        if "parts" in conf:
            for pid, b in self.part_chips.items():
                b.set_active(pid in conf.get("parts", []))
        self._on_touched()


def run():
    """Start the GUI.  If another instance already owns the app name the run
    loop hands off to it and returns immediately here - never exit silently,
    or a launch that shows no window looks like a crash."""
    app = ExamApp()
    code = app.run(None)
    if getattr(app, "win", None) is None:
        sys.stderr.write(
            "Penjana Kertas Ujian: no new window was opened by this launch.\n"
            "If an instance of the app is already running, that window may "
            "now be in the foreground (this app is single-window).\n"
            "If no window is visible at all, close the existing instance and "
            "relaunch, or start the app from inside your desktop session.\n")
        return code or 1
    return code