import queue
import re
import threading
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from zoneinfo import ZoneInfo

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from business.AnalyticsService import AnalyticsService
from business.DuplicateService import DuplicateService, Posting, fetch_posting
from business.ResumeAdvisor import recommend, _HEADINGS
from persistence.DataAccessJob import DataAccessJob
from visualization.DateRangeDialog import DateRangeDialog

DEFAULT_START_DATE = "2026-02-10"
TORONTO_TIMEZONE = ZoneInfo("America/Toronto")
UI = {
    "window": "#f3f6fb",
    "surface": "#ffffff",
    "surface_alt": "#f8faff",
    "text": "#172033",
    "muted": "#5d6981",
    "border": "#d9e0ec",
    "primary": "#315fdb",
    "primary_hover": "#284fbd",
    "success": "#147a5a",
    "warning": "#a35d00",
    "danger": "#b42318",
}


def format_assessment(result):
    labels = {"recommended": "Recommended resume", "provisional": "Resume to review",
              "skip": "Skip this job",
              "close": "Review two options", "none": "No suitable resume found",
              "insufficient": "More job information needed"}
    state = result.get("state", "provisional")
    choice = " / ".join(result.get("alternatives", [])) if state == "close" else result.get("name") or result.get("file")
    compared = result.get("readable_count", len(result.get("candidates", [])))
    lines = [labels.get(state, "Review needed") + (f": {choice}" if choice else "")]
    if state == "skip" and result.get("closest_resumes"):
        closest = result["closest_resumes"]
        label = "Closest resumes — tied (reference only)" if len(closest) > 1 else "Closest resume (reference only)"
        lines.append(f"{label}: {' / '.join(closest)}")
    if compared:
        lines.append(f"{compared} resumes compared")
    lines.append(result["summary"])
    job = result.get("job", {})
    if result.get("candidates") and state not in {"none", "insufficient"}:
        best = result["candidates"][0]
        roles = job.get("roles") or []
        core = ", ".join(skill.title() for skill in job.get("skills", [])) or "No core skills identified"
        gaps = list(dict.fromkeys(best.get("gaps", [])))
        lines.extend(["", "Responsibilities", role_summary(roles),
                      "", "Core skills", core, "", "To verify"])
        lines.extend([f"{index}. {gap}" for index, gap in enumerate(gaps, 1)]
                     or ["No unresolved core requirement gaps found."])
    if result.get("errors"):
        lines.extend(["", "Unreadable resumes:"] + result["errors"])
    return "\n".join(lines)


def role_summary(roles):
    labels = {
        "full stack": "Web frontend + backend delivery",
        "frontend": "Web frontend delivery",
        "backend": "Backend delivery",
        "mobile": "Mobile app delivery",
        "qa": "Quality engineering",
    }
    return " + ".join(labels.get(role, role.title()) for role in roles) or "Direction not established"


class Workbench:
    def __init__(self, db, synchronize=None):
        self.db, self.dao = db, DataAccessJob(db.conn)
        self.duplicates, self.synchronize = DuplicateService(db.conn), synchronize
        self.events, self.resume_paths, self.matches, self.history_rows, self.posting = queue.Queue(), [], [], [], None
        self.analyzing = False
        self._chart_resize_job = None
        self._job_version = self._resume_version = 0
        self.resume_profiles = {}
        self.root = tk.Tk()
        self.root.title("JobTrack")
        self._configure_styles()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        initial_width = min(1400, max(900, int(screen_width * .82)))
        initial_height = min(950, max(760, int(screen_height * .82)))
        self.root.geometry(f"{initial_width}x{initial_height}")
        self.root.minsize(900, 760)
        self.root.columnconfigure(0, weight=1, minsize=420, uniform="workspace")
        self.root.columnconfigure(1, weight=1, minsize=420, uniform="workspace")
        self.root.rowconfigure(0, weight=0)
        self.root.rowconfigure(1, weight=1)
        self.root.rowconfigure(2, weight=0)
        self._build_header()
        self.left = ttk.Frame(self.root, padding=(14, 12, 7, 10), style="Workspace.TFrame")
        self.left.grid(row=1, column=0, sticky="nsew")
        self.left.columnconfigure(0, weight=1)
        self.left.rowconfigure(0, weight=0)
        self.left.rowconfigure(1, weight=0)
        self.left.rowconfigure(2, weight=1)
        self.right = ttk.Frame(self.root, padding=(7, 12, 14, 10), style="Workspace.TFrame")
        self.right.grid(row=1, column=1, sticky="nsew")
        self.right.columnconfigure(0, weight=1)
        self.right.rowconfigure(0, weight=0, minsize=145)
        self.right.rowconfigure(1, weight=1, minsize=330)
        self._build_lookup()
        self._build_chart()
        self._build_footer()
        self.left.bind("<Configure>", self._resize_left_content)
        self.right.bind("<Configure>", self._resize_right_content)
        self.refresh_resumes()
        self.refresh_chart()
        self.root.after(100, self.poll)
        self.url.trace_add("write", self._url_changed)
        self.root.after_idle(self.startup_sync)

    def _configure_styles(self):
        self.root.configure(background=UI["window"])
        style = ttk.Style(self.root)
        style.configure("Workspace.TFrame", background=UI["window"])
        style.configure("Header.TFrame", background=UI["surface"], relief="flat")
        style.configure("Footer.TFrame", background=UI["surface_alt"])
        style.configure("Title.TLabel", background=UI["surface"], foreground=UI["text"],
                        font=("Segoe UI", 17, "bold"))
        style.configure("Subtitle.TLabel", background=UI["surface"], foreground=UI["muted"],
                        font=("Segoe UI", 9))
        style.configure("Status.TLabel", background=UI["surface_alt"], foreground=UI["muted"])
        style.configure("Tag.TLabel", background="#eef3ff", foreground="#294fae",
                        padding=(7, 3), font=("Segoe UI", 9))
        style.configure("Panel.TLabelframe", background=UI["surface"], bordercolor=UI["border"],
                        relief="solid", borderwidth=1)
        style.configure("Panel.TLabelframe.Label", background=UI["surface"], foreground=UI["text"],
                        font=("Segoe UI", 10, "bold"))
        # Keep the platform button colors: Windows native themes ignore custom
        # backgrounds but may still apply the foreground, making text invisible.
        style.configure("Primary.TButton", font=("Segoe UI", 9, "bold"), padding=(10, 5))
        style.configure("TButton", padding=(8, 4))
        style.configure("TNotebook", background=UI["surface"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=(11, 5))
        style.configure("Treeview", rowheight=27, background=UI["surface"],
                        fieldbackground=UI["surface"], foreground=UI["text"], borderwidth=0)
        style.configure("Comparison.Treeview", rowheight=49, background=UI["surface"],
                        fieldbackground=UI["surface"], foreground=UI["text"], borderwidth=0)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), padding=(5, 5))
        style.map("Treeview", background=[("selected", "#dce7ff")],
                  foreground=[("selected", UI["text"])])

    def _build_header(self):
        header = ttk.Frame(self.root, padding=(18, 11, 18, 10), style="Header.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(1, weight=1)
        title = ttk.Frame(header, style="Header.TFrame")
        title.grid(row=0, column=0, sticky="w")
        ttk.Label(title, text="JobTrack", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(title, text="Local application workspace", style="Subtitle.TLabel").grid(row=1, column=0, sticky="w")
        last_sync = self.db.get_last_sync_at()
        self.sync_status = tk.StringVar(value=f"Last synced at {last_sync}" if last_sync else "Gmail not synced yet")
        ttk.Label(header, textvariable=self.sync_status, style="Subtitle.TLabel").grid(
            row=0, column=1, rowspan=2, sticky="e", padx=(12, 10)
        )
        self.sync_button = ttk.Button(header, text="Sync Gmail", command=self.start_sync,
                                      style="Primary.TButton")
        self.sync_button.grid(row=0, column=2, rowspan=2, sticky="e")

    def _build_dates(self):
        today = datetime.now(ZoneInfo("America/Toronto")).date().isoformat()
        default_start = DEFAULT_START_DATE if DEFAULT_START_DATE <= today else today
        self.start, self.end = tk.StringVar(value=default_start), tk.StringVar(value=today)
        box = ttk.Frame(self.overview)
        box.grid(row=0, column=0, sticky="ew")
        self.date_box = box
        box.columnconfigure(2, weight=1)
        ttk.Label(box, text="Select time").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.time_choice = tk.StringVar(value="All time")
        selector = ttk.Combobox(
            box, textvariable=self.time_choice, state="readonly", width=16,
            values=("Today", "Yesterday", "Last 7 days", "Last 30 days",
                    "Last 90 days", "All time", "Custom…"),
        )
        selector.grid(row=0, column=1, sticky="w")
        selector.bind("<<ComboboxSelected>>", self._select_time)
        self.range_caption = ttk.Label(box, text=f"{default_start} – {today}")
        self.range_caption.grid(row=0, column=2, sticky="e", padx=(10, 0))

    def _select_time(self, _event=None):
        choice = self.time_choice.get()
        presets = {
            "Today": (1, 0), "Yesterday": (1, 1), "Last 7 days": (7, 0),
            "Last 30 days": (30, 0), "Last 90 days": (90, 0), "All time": (None, 0),
        }
        if choice == "Custom…":
            selected = DateRangeDialog.select(self.start.get(), self.end.get(), parent=self.root)
            if selected:
                self.start.set(selected[0])
                self.end.set(selected[1])
                self.refresh_chart()
            return
        days, offset = presets[choice]
        self.quick_range(days, offset)

    def _build_lookup(self):
        box = ttk.LabelFrame(self.left, text="Job check", padding=10, style="Panel.TLabelframe")
        box.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        box.columnconfigure(0, weight=1)
        self.job_check = box
        model_row = ttk.Frame(box)
        model_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 7))
        model_row.columnconfigure(0, weight=1)
        self.model_status = tk.StringVar()
        self.model_status_label = ttk.Label(model_row, textvariable=self.model_status, wraplength=255)
        self.model_status_label.grid(row=0, column=0, sticky="w")
        self.update_model_status()
        self.url = tk.StringVar()
        self.input_tabs = ttk.Notebook(box)
        self.input_tabs.grid(row=1, column=0, columnspan=2, sticky="ew")
        url_input, jd_input = ttk.Frame(self.input_tabs, padding=4), ttk.Frame(self.input_tabs, padding=4)
        self.input_tabs.add(url_input, text="Job URL")
        self.input_tabs.add(jd_input, text="Paste JD")
        self.input_tabs.bind("<<NotebookTabChanged>>", self._fit_input_tab)
        url_input.columnconfigure(0, weight=1)
        jd_input.columnconfigure(1, weight=1)
        entry = ttk.Entry(url_input, textvariable=self.url)
        entry.grid(row=0, column=0, sticky="ew")
        self.url_entry = entry
        entry.bind("<<Paste>>", lambda _event: self.root.after_idle(self._paste_and_lookup))
        entry.bind("<Return>", lambda _event: self.lookup_url())
        self.clear_button = ttk.Button(url_input, text="Clear", command=self.clear_job, width=6)
        self.clear_button.grid(row=0, column=1, padx=(6, 0))
        self.jd_title, self.jd_company = tk.StringVar(), tk.StringVar()
        for row, (label, value) in enumerate((("Title", self.jd_title), ("Company", self.jd_company))):
            ttk.Label(jd_input, text=label).grid(row=row, column=0, sticky="w", padx=(0, 6))
            ttk.Entry(jd_input, textvariable=value).grid(row=row, column=1, sticky="ew", pady=1)
        self.jd_text = tk.Text(jd_input, height=2, width=1, wrap="word")
        self.jd_text.grid(row=2, column=0, columnspan=2, sticky="ew", pady=3)
        jd_scroll = ttk.Scrollbar(jd_input, orient="vertical", command=self.jd_text.yview)
        jd_scroll.grid(row=2, column=2, sticky="ns")
        self.jd_text.configure(yscrollcommand=jd_scroll.set)
        ttk.Button(jd_input, text="Compare resumes", command=self.lookup_jd).grid(row=3, column=0, columnspan=2, sticky="e")
        self.root.after_idle(self._fit_input_tab)
        self.job_prompt = ttk.Label(box, text="Paste a job URL from any public platform",
                                    font=("Segoe UI", 10, "bold"))
        self.job_prompt.grid(row=2, column=0, columnspan=2, sticky="w", pady=(9, 0))
        self.job_summary = ttk.Frame(box)
        self.job_summary.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.job_summary.columnconfigure(2, weight=1)
        self.job_summary.columnconfigure(0, weight=1)
        self.job_summary.columnconfigure(1, weight=1)
        self.job_title = tk.StringVar(value="Paste a job URL from any public platform")
        self.job_title_label = ttk.Label(self.job_summary, textvariable=self.job_title,
                                         font=("Segoe UI", 10, "bold"), wraplength=220)
        self.job_title_label.grid(row=0, column=0, sticky="w")
        self.job_meta = tk.StringVar()
        self.job_meta_label = ttk.Label(self.job_summary, textvariable=self.job_meta,
                                        foreground=UI["muted"], wraplength=160)
        self.job_meta_label.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.lookup_status = tk.StringVar()
        self.input_status = tk.StringVar()
        self.lookup_status_label = ttk.Label(self.job_summary, textvariable=self.input_status,
                                             foreground=UI["success"])
        self.lookup_status_label.grid(row=0, column=2, sticky="e", padx=(8, 0))
        self.job_tags = ttk.Frame(self.job_summary)
        self.job_tags.grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))
        self.review_button = ttk.Button(self.job_summary, text="Review JD", command=self.review_jd)
        self.review_button.grid(row=1, column=2, sticky="e", pady=(5, 0))
        analysis = ttk.LabelFrame(self.left, text="Resume choice", padding=8, style="Panel.TLabelframe")
        analysis.grid(row=2, column=0, sticky="nsew")
        analysis.columnconfigure(0, weight=1)
        self.analysis_frame = analysis
        analysis.rowconfigure(0, weight=1)
        self.analysis_tabs = ttk.Notebook(analysis)
        self.analysis_tabs.grid(row=0, column=0, sticky="nsew")
        self.analysis_empty = ttk.Label(
            analysis, text="Check a job to compare enabled local resumes.",
            foreground=UI["muted"], padding=(8, 7), anchor="nw",
        )
        summary, comparison = ttk.Frame(self.analysis_tabs), ttk.Frame(self.analysis_tabs)
        self.analysis_tabs.add(summary, text="Summary")
        self.analysis_tabs.add(comparison, text="All resumes")
        for frame in (summary, comparison):
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=1)
        self.analysis_text = tk.Text(summary, height=4, width=1, wrap="word", state="disabled", borderwidth=0, highlightthickness=0)
        self.analysis_text.grid(row=0, column=0, sticky="nsew")
        analysis_scroll = ttk.Scrollbar(summary, orient="vertical", command=self.analysis_text.yview)
        analysis_scroll.grid(row=0, column=1, sticky="ns")
        self.analysis_text.configure(yscrollcommand=analysis_scroll.set)
        self.comparison_table = ttk.Treeview(
            comparison,
            columns=("resume", "role", "requirements", "choice"),
            show="headings",
            height=2,
            style="Comparison.Treeview",
        )
        for key, label, width in (
            ("resume", "Resume", 95),
            ("role", "Role evidence", 145),
            ("requirements", "Core requirements", 185),
            ("choice", "Choice", 110),
        ):
            self.comparison_table.heading(key, text=label, anchor="w")
            self.comparison_table.column(key, width=width, minwidth=75, anchor="w", stretch=True)
        self.comparison_table.grid(row=0, column=0, sticky="nsew")
        comparison_scroll = ttk.Scrollbar(comparison, orient="vertical", command=self.comparison_table.yview)
        comparison_scroll.grid(row=0, column=1, sticky="ns")
        comparison_scroll_x = ttk.Scrollbar(comparison, orient="horizontal", command=self.comparison_table.xview)
        comparison_scroll_x.grid(row=1, column=0, sticky="ew")
        self.comparison_table.configure(yscrollcommand=comparison_scroll.set, xscrollcommand=comparison_scroll_x.set)
        self.comparison_scroll_x = comparison_scroll_x
        self.comparison_table.bind("<Configure>", lambda event: self._resize_table(
            event.widget, (("resume", .18), ("role", .27), ("requirements", .35), ("choice", .20))
        ))
        self.comparison_table.bind("<Configure>", lambda _event: self._update_comparison_scrollbar(), add="+")
        self.root.after_idle(self._update_comparison_scrollbar)
        self.analysis_text.configure(background=UI["surface"], foreground=UI["text"],
                                     selectbackground="#dce7ff", font=("Segoe UI", 10),
                                     padx=9, pady=8, spacing1=2, spacing3=3, tabs=(145,))
        self.analysis_text.tag_configure("result", font=("Segoe UI", 12, "bold"), foreground=UI["primary"])
        self.analysis_text.tag_configure("section", foreground=UI["muted"], font=("Segoe UI", 10, "bold"))
        self.analysis_text.tag_configure("detail", lmargin1=12, lmargin2=12, spacing3=6)

        history = ttk.LabelFrame(self.left, text="Application history · All imported dates", padding=(8, 7), style="Panel.TLabelframe")
        history.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        history.columnconfigure(0, weight=1)
        history.rowconfigure(1, weight=1)
        self.history_label = history
        self.history_status_label = ttk.Label(history, textvariable=self.lookup_status, wraplength=340)
        self.history_status_label.grid(row=0, column=0, columnspan=2, sticky="w")
        self.results = ttk.Treeview(history, columns=("date", "channel", "company", "position"), show="headings", height=4)
        for key, label, width in (("date", "Applied", 80), ("channel", "Channel", 95),
                                  ("company", "Company", 95), ("position", "Role", 130)):
            self.results.heading(key, text=label)
            self.results.column(key, width=width, minwidth=max(55, width - 30), stretch=True)
        self.results.grid(row=1, column=0, sticky="nsew")
        self.results.bind(
            "<Configure>",
            lambda _event: self.root.after_idle(self._position_empty_history),
            add="+",
        )
        self.history_scroll = ttk.Scrollbar(history, orient="vertical", command=self.results.yview)
        self.history_scroll.grid(row=1, column=1, sticky="ns")
        self.history_scroll_x = ttk.Scrollbar(history, orient="horizontal", command=self.results.xview)
        self.history_scroll_x.grid(row=2, column=0, sticky="ew")
        self.results.configure(
            yscrollcommand=self.history_scroll.set,
            xscrollcommand=self.history_scroll_x.set,
        )
        self.results.bind("<Configure>", lambda _event: self._update_history_scrollbar(), add="+")
        self.root.after_idle(self._update_history_scrollbar)
        self.empty_history_label = ttk.Label(
            self.results,
            text="No previous application found",
            anchor="center",
        )
        self.details = tk.StringVar()
        self.details_label = ttk.Label(history, textvariable=self.details, wraplength=315)
        self.details_label.grid(row=3, column=0, columnspan=2, sticky="w", pady=(3, 0))
        self.details_label.grid_remove()
        self.results.bind("<<TreeviewSelect>>", self.show_details)
        self.set_analysis("Check a job to compare enabled local resumes.")
        self.show_empty_history("Waiting for a job to check")
        self._set_job_details_visible(False)

        resumes = ttk.LabelFrame(self.right, text="Resumes", padding=8, style="Panel.TLabelframe")
        resumes.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        self.resumes_box = resumes
        resumes.columnconfigure(0, weight=1)
        resumes.rowconfigure(1, weight=1)
        resume_toolbar = ttk.Frame(resumes)
        resume_toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        resume_toolbar.columnconfigure(0, weight=1)
        ttk.Label(resume_toolbar, text="Double-click a row to enable / disable", foreground=UI["muted"]).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(resume_toolbar, text="＋  Add resume", command=self.add_resumes).grid(
            row=0, column=1, sticky="e"
        )
        self.resume_table = ttk.Treeview(
            resumes, columns=("use", "name", "edit", "delete"), show="headings", height=4
        )
        for key, label, width in (("use", "Use", 45), ("name", "Resume", 220),
                                  ("edit", "Edit", 58), ("delete", "Delete", 64)):
            self.resume_table.heading(key, text=label)
            self.resume_table.column(key, width=width, minwidth=width,
                                     anchor="center" if key in {"edit", "delete"} else "w")
        self.resume_table.grid(row=1, column=0, sticky="nsew")
        resume_scroll = ttk.Scrollbar(resumes, orient="vertical", command=self.resume_table.yview)
        resume_scroll.grid(row=1, column=1, sticky="ns")
        self.resume_scroll_x = ttk.Scrollbar(resumes, orient="horizontal", command=self.resume_table.xview)
        self.resume_scroll_x.grid(row=2, column=0, sticky="ew")
        self.resume_table.configure(yscrollcommand=resume_scroll.set, xscrollcommand=self.resume_scroll_x.set)
        self.resume_table.bind("<Button-1>", self._resume_table_click, add="+")
        self.resume_table.bind("<Double-1>", self._resume_table_double_click)
        self.resume_table.bind("<Configure>", lambda event: self._resize_table(
            event.widget, (("use", .10), ("name", .66), ("edit", .11), ("delete", .13))
        ))
        self.resume_table.bind("<Configure>", lambda _event: self._update_resume_scrollbar(), add="+")
        self.root.after_idle(self._set_top_panel_heights)

    def _build_chart(self):
        self.overview = ttk.LabelFrame(self.right, text="Application overview", padding=8, style="Panel.TLabelframe")
        self.overview.grid(row=1, column=0, sticky="nsew")
        self.overview.columnconfigure(0, weight=1)
        self.overview.rowconfigure(1, weight=1)
        self._build_dates()
        self.figure = Figure(figsize=(4, 2), dpi=100, layout="constrained")
        self.figure.patch.set_facecolor(UI["surface"])
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.overview)
        self.canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew")
        self.canvas.get_tk_widget().bind(
            "<Configure>",
            self._schedule_chart_layout,
            add="+",
        )
        ttk.Label(self.overview, text="First recorded in range · Stages can overlap").grid(row=2, column=0, sticky="w")

    @staticmethod
    def _resize_table(table, columns):
        available = max(1, table.winfo_width() - 24)
        for name, ratio in columns:
            minimum = int(table.column(name, "minwidth"))
            table.column(name, width=max(minimum, int(available * ratio)), stretch=True)

    def _fit_input_tab(self, _event=None):
        if not hasattr(self, "input_tabs"):
            return
        selected = self.input_tabs.nametowidget(self.input_tabs.select())
        self.input_tabs.configure(height=max(45, selected.winfo_reqheight()))
        self.root.after_idle(self._set_top_panel_heights)

    def _set_top_panel_heights(self):
        if not all(hasattr(self, name) for name in ("input_tabs", "job_check", "resumes_box")):
            return
        selected_index = self.input_tabs.index(self.input_tabs.select())
        height = 278 if selected_index == 1 else 220
        for panel in (self.job_check, self.resumes_box):
            panel.configure(height=height)
            panel.grid_propagate(False)

    def _update_resume_scrollbar(self):
        if not hasattr(self, "resume_scroll_x"):
            return
        content_width = sum(
            int(self.resume_table.column(name, "width"))
            for name in ("use", "name", "edit", "delete")
        )
        viewport_width = max(1, self.resume_table.winfo_width() - 2)
        if content_width > viewport_width:
            self.resume_scroll_x.grid()
        else:
            self.resume_scroll_x.grid_remove()

    def _update_comparison_scrollbar(self):
        if not hasattr(self, "comparison_scroll_x"):
            return
        names = ("resume", "role", "requirements", "choice")
        content_width = sum(int(self.comparison_table.column(name, "width")) for name in names)
        viewport_width = max(1, self.comparison_table.winfo_width() - 2)
        if content_width > viewport_width:
            self.comparison_scroll_x.grid()
        else:
            self.comparison_scroll_x.grid_remove()

    def _update_history_scrollbar(self):
        if not hasattr(self, "history_scroll_x"):
            return
        names = ("date", "channel", "company", "position")
        content_width = sum(int(self.results.column(name, "width")) for name in names)
        viewport_width = max(1, self.results.winfo_width() - 2)
        if content_width > viewport_width:
            self.history_scroll_x.grid()
        else:
            self.history_scroll_x.grid_remove()

    def _resize_left_content(self, event):
        wrap = max(230, event.width - 55)
        for label in (self.model_status_label, self.job_title_label, self.job_meta_label, self.lookup_status_label):
            label.configure(wraplength=wrap)
        # Title, company/location and status share a row, not the full panel width.
        summary_wrap = max(70, (event.width - 150) // 2)
        self.job_title_label.configure(wraplength=summary_wrap)
        self.job_meta_label.configure(wraplength=summary_wrap)
        self.details_label.configure(wraplength=wrap)
        self.history_status_label.configure(wraplength=wrap)
        self._resize_table(self.results, (("date", .19), ("channel", .24), ("company", .24), ("position", .33)))

    def _resize_right_content(self, event):
        self._resize_table(self.resume_table, (("use", .10), ("name", .66), ("edit", .11), ("delete", .13)))

    def _schedule_chart_layout(self, _event=None):
        if self._chart_resize_job is not None:
            self.root.after_cancel(self._chart_resize_job)
        self._chart_resize_job = self.root.after(120, self._finish_chart_layout)

    def _finish_chart_layout(self):
        self._chart_resize_job = None
        self.canvas.draw_idle()

    def update_model_status(self, result=None):
        self.model_status.set("Basic version · Local assessment")

    def set_analysis(self, text, result=None):
        if result and result.get("candidates"):
            self.analysis_empty.grid_remove()
            self.analysis_tabs.grid()
        else:
            self.analysis_tabs.grid_remove()
            self.analysis_empty.configure(text=text or "Check a job to compare enabled local resumes.")
            self.analysis_empty.grid(row=0, column=0, sticky="nsew")
        self.analysis_text.configure(state="normal")
        self.analysis_text.delete("1.0", "end")
        self.analysis_text.insert("1.0", text)
        if text:
            self.analysis_text.tag_add("result", "1.0", "1.end")
        for line_number, line in enumerate(text.splitlines(), start=1):
            label = next((label for label in ("Responsibilities", "Core skills", "To verify")
                          if line == label), None)
            if label:
                self.analysis_text.tag_add("section", f"{line_number}.0", f"{line_number}.{len(label)}")
            elif line_number > 3 and line:
                self.analysis_text.tag_add("detail", f"{line_number}.0", f"{line_number}.end+1c")
        self.analysis_text.configure(state="disabled")
        self.comparison_table.delete(*self.comparison_table.get_children())
        if not result or not result.get("candidates"):
            self.comparison_table.insert("", "end", values=("No comparison available yet.", "", "", ""))
            return
        candidates = list(result["candidates"])
        alternatives = set(result.get("alternatives", []))
        for index, candidate in enumerate(candidates):
            primary = candidate.get("primary_direction")
            role = self._role_summary([primary]) if primary else "Direction unclear"
            evidence = " · ".join(skill.title() for skill in candidate.get("project_overlap", [])) or "No project evidence"
            gaps = candidate.get("gaps", [])
            if gaps:
                gap = gaps[0].replace("Core skills without project evidence: ", "Missing: ")
                gap = gap.replace(" is preferred; no clear evidence found.", " not evidenced")
                if not gap.startswith(("Missing:", "Verify:")):
                    gap = "Verify: " + gap
                if len(gap) > 32:
                    gap = gap[:29].rstrip() + "…"
                evidence += "\n" + gap
            if candidate.get("compatibility", 0) < 0:
                choice = "Role mismatch"
            elif result.get("state") == "close" and candidate.get("name") in alternatives:
                choice = "Close match"
            elif index == 0 and result.get("state") == "recommended":
                choice = "Best fit"
            elif result.get("state") == "skip" and candidate.get("name") in result.get("closest_resumes", []):
                choice = "Tied closest · skip" if len(result.get("closest_resumes", [])) > 1 else "Closest only · skip"
            elif index == 0:
                choice = "Leading · verify"
            elif candidate.get("compatibility") == 2:
                choice = "Alternative"
            else:
                choice = "Direction unclear"
            self.comparison_table.insert("", "end", values=(candidate["name"], role, evidence, choice))

    def show_job_tags(self, job=None):
        for child in self.job_tags.winfo_children():
            child.destroy()
        if not job:
            return
        tags = []
        roles = job.get("roles", [])
        if roles:
            tags.append(" / ".join(role.title() for role in roles))
        required = [skill for requirement in job.get("required", [])
                    for skill in requirement.get("skills", [])]
        for skill in required + job.get("skills", []):
            label = skill.title()
            if label not in tags:
                tags.append(label)
            if len(tags) == 4:
                break
        for column, label in enumerate(tags):
            ttk.Label(self.job_tags, text=label, style="Tag.TLabel").grid(
                row=0, column=column, padx=(0, 5))

    @staticmethod
    def _role_summary(roles):
        labels = {
            "full stack": "Web frontend + backend",
            "frontend": "Web frontend delivery",
            "backend": "Backend delivery",
            "mobile": "Mobile app delivery",
            "qa": "Quality engineering",
        }
        return " + ".join(labels.get(role, role.title()) for role in roles) or "Direction not established"

    def set_history_visible(self, visible):
        self.history_label.grid()
        self.empty_history_label.place_forget()
        self.results.grid()
        self.history_scroll.grid()
        self.details.set("")
        self.details_label.grid_remove()
        self._update_history_scrollbar()
        self.root.after_idle(self._update_history_scrollbar)

    def show_empty_history(self, message="No matching application found"):
        self.results.configure(height=4)
        self.results.delete(*self.results.get_children())
        self.results.insert("", "end", iid="empty", values=("", "", "", ""))
        self.set_history_visible(True)
        self.empty_history_label.configure(text=message)
        self.root.after_idle(self._position_empty_history)
        self.details.set("")

    def _position_empty_history(self):
        if not self.results.exists("empty"):
            self.empty_history_label.place_forget()
            return
        bounds = self.results.bbox("empty")
        if bounds:
            _x, y, _width, height = bounds
            self.empty_history_label.place(
                x=1,
                y=y,
                width=max(1, self.results.winfo_width() - 2),
                height=height,
            )

    def _set_job_details_visible(self, visible):
        if visible:
            self.job_prompt.grid_remove()
            self.job_summary.grid()
        else:
            self.job_summary.grid_remove()
            self.job_prompt.grid()

    def _build_footer(self):
        footer = ttk.Frame(self.root, padding=(18, 6, 18, 7), style="Footer.TFrame")
        footer.grid(row=2, column=0, columnspan=2, sticky="ew")
        footer.columnconfigure(1, weight=1)
        ttk.Label(footer, text="Analysis stays on this device", style="Status.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(footer, text="Basic version · Local assessment", style="Status.TLabel").grid(row=0, column=1, sticky="e")

    def quick_range(self, days, end_offset=0):
        today = datetime.now(ZoneInfo("America/Toronto")).date()
        first = self.dao.get_first_application_date()
        range_end = today - timedelta(days=end_offset)
        self.start.set((range_end - timedelta(days=days - 1)).isoformat() if days else first[:10] if first else range_end.isoformat())
        self.end.set(range_end.isoformat())
        self.refresh_chart()

    def refresh_chart(self):
        try:
            start, end = DateRangeDialog.validate_dates(self.start.get().strip(), self.end.get().strip())
        except ValueError as error:
            messagebox.showerror("Invalid date range", str(error), parent=self.root)
            return
        values = AnalyticsService(self.dao, start, end).get_funnel_data()
        labels = ["Applications", "Rejected", "Assessments", "Interviews", "Offers"]
        counts = [values[label.lower()] for label in labels]
        self.axes.clear()
        self.axes.set_facecolor(UI["surface"])
        bars = self.axes.barh(labels, counts, color=[UI["primary"], "#df706b", "#d49a28", "#3f9d86", "#8067ba"], height=.58)
        self.axes.invert_yaxis()
        maximum = max(max(counts), 1)
        self.axes.set_xlim(0, maximum * 1.28)
        self.axes.xaxis.grid(True, color=UI["border"], linewidth=.7)
        self.axes.set_axisbelow(True)
        self.axes.tick_params(colors=UI["muted"], labelsize=9, length=0)
        for spine in self.axes.spines.values():
            spine.set_visible(False)
        for bar, count in zip(bars, counts):
            pct = count / counts[0] * 100 if counts[0] else 0
            self.axes.text(bar.get_width() + maximum * .02, bar.get_y() + bar.get_height() / 2,
                           f"{count}  {pct:.0f}%", va="center", color=UI["text"], fontsize=9)
        self.axes.set_title(f"{start}  –  {end}", color=UI["text"], fontsize=10, pad=8)
        self.range_caption.configure(text=f"{start} – {end}")
        self.canvas.draw_idle()

    @staticmethod
    def _resume_filetypes():
        return (("Resumes", "*.pdf *.docx *.txt *.md"), ("All files", "*.*"))

    def refresh_resumes(self):
        self._resume_version += 1
        self.resume_table.delete(*self.resume_table.get_children())
        self.resume_paths, self.resume_profiles = [], {}
        for resume_id, name, path, enabled, _updated in self.db.get_resumes():
            available = Path(path).is_file()
            use = "✓" if enabled and available else "—"
            if not available:
                name = f"{name} · File missing"
            self.resume_table.insert("", "end", iid=str(resume_id), values=(use, name, "✎", "🗑"))
            self.resume_profiles[path] = {"name": name}
            if enabled:
                self.resume_paths.append(path)
        if self.posting and self.posting.description:
            self.start_resume_match()

    def selected_resume_id(self):
        selected = self.resume_table.selection()
        return int(selected[0]) if selected else None

    def _resume_table_click(self, event):
        if self.resume_table.identify_region(event.x, event.y) != "cell":
            return None
        column = self.resume_table.identify_column(event.x)
        if column not in {"#3", "#4"}:
            return None
        row = self.resume_table.identify_row(event.y)
        if not row:
            return "break"
        self.resume_table.selection_set(row)
        if column == "#3":
            menu = tk.Menu(self.root, tearoff=False)
            menu.add_command(label="Rename", command=self.rename_resume)
            menu.add_command(label="Replace file", command=self.replace_resume)
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
        elif messagebox.askyesno(
            "Remove resume",
            "Remove this saved resume reference?\n\nThe original file will not be deleted.",
            parent=self.root,
        ):
            self.remove_resume()
        return "break"

    def _resume_table_double_click(self, event):
        if self.resume_table.identify_column(event.x) in {"#3", "#4"}:
            return "break"
        row = self.resume_table.identify_row(event.y)
        if row:
            self.resume_table.selection_set(row)
            self.toggle_resume()
        return "break"

    def add_resumes(self):
        paths = filedialog.askopenfilenames(parent=self.root, title="Add resumes", filetypes=self._resume_filetypes())
        for path in paths:
            self.db.add_resume(Path(path).stem, str(Path(path).resolve()))
        if paths:
            self.refresh_resumes()

    def replace_resume(self):
        resume_id = self.selected_resume_id()
        if resume_id is None:
            self.set_analysis("Select a resume to replace")
            return
        path = filedialog.askopenfilename(parent=self.root, title="Replace resume", filetypes=self._resume_filetypes())
        if path:
            self.db.update_resume(resume_id, name=Path(path).stem, file_path=str(Path(path).resolve()))
            self.refresh_resumes()

    def rename_resume(self):
        resume_id = self.selected_resume_id()
        if resume_id is None:
            self.set_analysis("Select a resume to rename")
            return
        current = self.resume_table.item(str(resume_id), "values")[1]
        name = simpledialog.askstring("Rename resume", "Name", initialvalue=current, parent=self.root)
        if name and name.strip():
            self.db.update_resume(resume_id, name=name.strip())
            self.refresh_resumes()

    def toggle_resume(self):
        resume_id = self.selected_resume_id()
        if resume_id is None:
            return
        current = next(row for row in self.db.get_resumes() if row[0] == resume_id)
        self.db.update_resume(resume_id, enabled=0 if current[3] else 1)
        self.refresh_resumes()

    def remove_resume(self):
        resume_id = self.selected_resume_id()
        if resume_id is None:
            self.set_analysis("Select a resume to remove")
            return
        self.db.delete_resume(resume_id)
        self.refresh_resumes()

    def lookup_url(self):
        url = self.url.get().strip()
        if not url:
            return
        self._clear_job_result()
        self.analyzing = True
        self.job_title.set("Analyzing job link…")
        self.job_meta.set("")
        self.input_status.set("Analyzing…")
        self.review_button.configure(state="disabled")
        self._set_job_details_visible(True)
        self.lookup_status.set("Waiting for job analysis")
        self.show_empty_history("Analyzing job description…")
        self.set_analysis("Analyzing job description…")
        threading.Thread(target=self._fetch_worker, args=(self._job_version, url), daemon=True).start()

    def _url_changed(self, *_args):
        if self.analyzing or (self.posting and self.posting.url and self.posting.url != self.url.get().strip()):
            self._clear_job_result()

    def lookup_jd(self):
        description = self.jd_text.get("1.0", "end").strip()
        if not description:
            self.set_analysis("Paste the full JD to compare resumes.")
            return
        self._clear_job_result()
        self.show_posting(Posting("", self.jd_company.get().strip(), self.jd_title.get().strip(), description))

    def review_jd(self):
        if not self.posting:
            self.set_analysis("Check a job before reviewing its description.")
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Job description used for assessment")
        dialog.geometry("800x650")
        dialog.minsize(420, 300)
        dialog.transient(self.root)
        dialog.configure(background=UI["surface"])
        body = ttk.Frame(dialog, padding=16)
        body.pack(fill="both", expand=True)
        text = tk.Text(body, wrap="word", font=("Segoe UI", 10),
                       background=UI["surface"], foreground=UI["text"],
                       borderwidth=0, highlightthickness=0, padx=8, pady=8,
                       spacing1=2, spacing3=8)
        text.tag_configure("title", font=("Segoe UI", 15, "bold"), foreground=UI["primary"], spacing3=10)
        text.tag_configure("meta", foreground=UI["muted"], spacing3=16)
        text.tag_configure("heading", font=("Segoe UI", 11, "bold"),
                           foreground=UI["primary"], spacing1=14, spacing3=8)
        text.tag_configure("paragraph", lmargin1=0, lmargin2=0, spacing3=10)
        text.tag_configure("bullet", lmargin1=12, lmargin2=30, spacing3=8,
                           tabs=(30,))
        if self.posting.position:
            text.insert("end", self.posting.position + "\n", "title")
        metadata = " · ".join(value for value in (self.posting.company,
                              self.posting.location, self.posting.work_mode) if value)
        if metadata:
            text.insert("end", metadata + "\n", "meta")
        description = self.posting.description or "No job description retrieved. Use Paste JD."
        for line in description.splitlines():
            line = line.strip()
            if not line:
                continue
            # Reuse the assessment's section vocabulary without changing JD text.
            if _HEADINGS.fullmatch(line) or (len(line) < 90 and line.endswith(":")):
                text.insert("end", line + "\n", "heading")
            elif re.match(r"^(?:[•*\-]|\d+[.)])\s+", line):
                marker, content = line.split(maxsplit=1)
                text.insert("end", marker + "\t" + content + "\n", "bullet")
            else:
                text.insert("end", line + "\n", "paragraph")
        text.configure(state="disabled")
        scroll = ttk.Scrollbar(body, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)

    def _paste_and_lookup(self):
        # A pasted URL starts a new check; discard any recommendation from the
        # previous posting before the new fetch begins.
        self.lookup_url()

    def _clear_job_result(self):
        self._job_version += 1
        self._resume_version += 1
        self.analyzing = False
        self.posting = None
        self.matches = []
        self.history_rows = []
        self.job_title.set("Paste a job URL from any public platform")
        self.job_meta.set("")
        self.show_job_tags()
        self._set_job_details_visible(False)
        self.input_status.set("")
        self.lookup_status.set("")
        self.set_analysis("Check a job to compare enabled local resumes.")
        self.results.delete(*self.results.get_children())
        self.show_empty_history("Waiting for a job to check")

    def clear_job(self):
        self.url.set("")
        self._clear_job_result()
        self.jd_title.set("")
        self.jd_company.set("")
        self.jd_text.delete("1.0", "end")

    def _fetch_worker(self, version, url):
        try:
            posting = fetch_posting(url)
        except Exception:
            posting = Posting(url, warning="Could not analyze this job URL")
        self.events.put(("posting", (version, posting)))

    def show_posting(self, posting):
        self.posting = posting
        self._set_job_details_visible(True)
        self.job_title.set(posting.position or "Job page unavailable")
        self.job_meta.set(" · ".join(value for value in
                          (posting.company, posting.location, posting.work_mode) if value))
        self.show_job_tags()
        self.input_status.set("JD ready" if posting.description else "JD unavailable")
        self.review_button.configure(state="normal" if posting.description else "disabled")
        self.refresh_history()
        if posting.description and self.resume_paths:
            self.start_resume_match()
        elif posting.description:
            self.set_analysis("Enable at least one local resume to compare.")
        else:
            self.set_analysis("No usable JD retrieved. Use Paste JD to supply the full description.")

    def refresh_history(self):
        posting = self.posting
        if not posting:
            return
        # Pasted JDs have no URL. A supplied company and title can still be
        # checked, but absence of those identifiers is not a negative result.
        if not posting.url and not (posting.company and posting.position):
            self.matches, self.history_rows = [], []
            self.lookup_status.set("History unavailable without a job URL or company and title")
            self.show_empty_history("Insufficient identifiers for history check")
            return
        self.matches = self.duplicates.search(posting)
        self.history_rows = []
        self.results.delete(*self.results.get_children())
        for match in self.matches:
            for application in match["applications"]:
                index = len(self.history_rows)
                self.history_rows.append(match)
                self.results.insert("", "end", iid=str(index), values=(
                    application["date"], application["channel"], match["company"], match["position"]
                ))
        self.results.configure(height=4)
        self.set_history_visible(True)
        if not self.matches:
            self.show_empty_history()
        if self.matches:
            application_count = len(self.history_rows)
            unit = "time" if application_count == 1 else "times"
            exact = sum(len(match["applications"]) for match in self.matches if match["score"] == 100)
            self.lookup_status.set(f"Previously applied — {exact} exact URL matches" if exact else
                                   f"Possible previous application — {application_count} {unit}; review evidence")
        elif posting.position or posting.url:
            self.lookup_status.set("No matching application in imported history")
        else:
            self.lookup_status.set(posting.warning or "Could not analyze this URL")

    def start_resume_match(self):
        self._resume_version += 1
        if not self.resume_paths:
            self.set_analysis("Enable at least one local resume to compare.")
            return
        self.set_analysis("Comparing resumes…")
        threading.Thread(
            target=self._resume_worker,
            args=((self._job_version, self._resume_version), self.posting,
                  tuple(self.resume_paths), dict(self.resume_profiles)),
            daemon=True,
        ).start()

    def _resume_worker(self, version, posting, paths, profiles):
        try:
            result, errors = recommend(posting.description, paths, "local", job_title=posting.position, resume_profiles=profiles)
        except Exception:
            result, errors = None, ["Assessment failed. Check the resume formats and retry."]
        self.events.put(("resume", (version, result, errors)))

    def show_details(self, _event=None):
        selected = self.results.selection()
        if selected and selected[0] != "empty":
            match = self.history_rows[int(selected[0])]
            self.details.set(f"{match['status']} · {match['reason']}")
            self.details_label.grid()
        else:
            self.details.set("")
            self.details_label.grid_remove()

    def startup_sync(self):
        if Path("token.json").is_file():
            self.start_sync(automatic=True)

    def start_sync(self, automatic=False):
        if not self.synchronize or str(self.sync_button["state"]) == "disabled":
            return
        self.sync_button.configure(state="disabled")
        self.sync_status.set("Syncing…")
        def worker():
            try:
                progress = lambda message: self.events.put(("sync_progress", message))
                unreadable_count = self.synchronize(progress, interactive=False) if automatic else self.synchronize(progress)
                self.events.put(("sync", (None, unreadable_count or 0)))
            except Exception as error:
                self.events.put(("sync", (type(error).__name__, 0)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "posting":
                    version, posting = value
                    if version != self._job_version or posting.url != self.url.get().strip():
                        continue
                    self.analyzing = False
                    self.show_posting(posting)
                elif kind == "resume":
                    version, result, errors = value
                    if not self.posting or version != (self._job_version, self._resume_version):
                        continue
                    if result:
                        self.update_model_status(result)
                        self.show_job_tags(result.get("job"))
                        self.input_status.set("JD needs details" if result['state'] == 'insufficient' else "JD ready")
                        self.set_analysis(format_assessment(result), result)
                    else:
                        self.set_analysis(errors[0] if errors else "No readable resumes found")
                elif kind == "sync_progress":
                    self.sync_status.set(value)
                elif kind == "sync":
                    self.sync_button.configure(state="normal")
                    last_sync = self.db.get_last_sync_at()
                    error_name, unreadable_count = value
                    if error_name:
                        self.sync_status.set("Gmail needs reconnection · Select Sync Gmail" if error_name == "PermissionError" else
                                             f"Sync incomplete · {error_name} · Showing saved history")
                    else:
                        suffix = f" · {unreadable_count} unreadable skipped" if unreadable_count else ""
                        self.sync_status.set(f"Last synced at {last_sync}{suffix}")
                    self.refresh_chart()
                    self.refresh_history()
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def run(self):
        self.root.mainloop()
