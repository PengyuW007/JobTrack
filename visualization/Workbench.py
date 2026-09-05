import queue
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
from business.ResumeAdvisor import get_api_key, recommend, save_api_key
from persistence.DataAccessJob import DataAccessJob
from visualization.DateRangeDialog import DateRangeDialog

MODEL_OPTIONS = {
    "GPT-5.6 Terra (Recommended)": "gpt-5.6-terra",
    "GPT-6 Astra (Best quality)": "gpt-6-astra",
    "GPT-5.6 Luna (Lower cost)": "gpt-5.6-luna",
    "Local assessment": "local",
}
DEFAULT_START_DATE = "2026-02-10"


def format_assessment(result):
    stars = "★" * max(1, min(5, round(result["score"] / 2)))
    modification = "Yes" if result["modification_needed"] else "No"
    source = f"AI assessment · {result.get('model', '')}".rstrip(" ·") if result["source"] == "AI" else "Local assessment"
    return (
        f"Recommended: {result['file']}\n"
        f"Match: {stars}  {result['score']:.1f}/10  ·  Modify: {modification}\n"
        f"Priority: {result.get('priority', result['recommendation'])}\n"
        f"{result['summary']}\n"
        f"{source}"
    )


class Workbench:
    def __init__(self, db, synchronize=None):
        self.db, self.dao = db, DataAccessJob(db.conn)
        self.duplicates, self.synchronize = DuplicateService(db.conn), synchronize
        self.events, self.resume_paths, self.matches, self.posting = queue.Queue(), [], [], None
        self.analyzing = False
        self.root = tk.Tk()
        self.root.title("JobTrack")
        self.root.geometry("1180x900")
        self.root.minsize(960, 700)
        self.root.columnconfigure(0, minsize=390)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=0)
        self.left = ttk.Frame(self.root, padding=18)
        self.left.grid(row=0, column=0, sticky="nsew")
        self.left.columnconfigure(0, weight=1)
        self.left.rowconfigure(7, weight=1)
        self.right = ttk.Frame(self.root, padding=(5, 18, 18, 18))
        self.right.grid(row=0, column=1, sticky="nsew")
        self.right.columnconfigure(0, weight=1)
        self.right.rowconfigure(1, weight=1)
        ttk.Label(self.left, text="JobTrack", font=("Segoe UI", 18, "bold")).grid(row=0, column=0, sticky="w")
        self._build_dates()
        self._build_lookup()
        self._build_chart()
        self._build_footer()
        self.refresh_resumes()
        self.refresh_chart()
        self.root.after(100, self.poll)

    def _build_dates(self):
        today = datetime.now(ZoneInfo("America/Toronto")).date().isoformat()
        default_start = DEFAULT_START_DATE if DEFAULT_START_DATE <= today else today
        self.start, self.end = tk.StringVar(value=default_start), tk.StringVar(value=today)
        box = ttk.LabelFrame(self.left, text="Date range", padding=10)
        box.grid(row=1, column=0, sticky="ew", pady=(16, 8))
        for row, (label, value) in enumerate((("From", self.start), ("To", self.end))):
            ttk.Label(box, text=label, width=6).grid(row=row, column=0, sticky="w", pady=3)
            entry = ttk.Entry(box, textvariable=value, width=16)
            entry.grid(row=row, column=1, sticky="ew", pady=3)
            entry.bind("<Return>", lambda _event: self.refresh_chart())
            ttk.Button(box, text="Calendar", command=lambda v=value: DateRangeDialog.open_calendar(self.root, v)).grid(row=row, column=2, padx=(6, 0))
        quick = ttk.Frame(box)
        quick.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(7, 0))
        for column, (label, days) in enumerate((("7D", 7), ("30D", 30), ("90D", 90), ("All", None))):
            ttk.Button(quick, text=label, command=lambda d=days: self.quick_range(d)).grid(row=0, column=column, padx=(0, 4))
        ttk.Button(quick, text="Update", command=self.refresh_chart).grid(row=0, column=4)

    def _build_lookup(self):
        box = ttk.LabelFrame(self.left, text="Job check", padding=10)
        box.grid(row=2, column=0, sticky="ew", pady=8)
        box.columnconfigure(0, weight=1)
        saved_model = self.db.get_setting("assessment_model", "gpt-5.6-terra")
        selected_label = next((label for label, model in MODEL_OPTIONS.items() if model == saved_model), next(iter(MODEL_OPTIONS)))
        model_row = ttk.Frame(box)
        model_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 7))
        ttk.Label(model_row, text="Model").grid(row=0, column=0, sticky="w")
        self.model_choice = tk.StringVar(value=selected_label)
        self.model_selector = ttk.Combobox(model_row, textvariable=self.model_choice, values=list(MODEL_OPTIONS), state="readonly", width=28)
        self.model_selector.grid(row=0, column=1, padx=(8, 0), sticky="ew")
        self.model_selector.bind("<<ComboboxSelected>>", self.change_model)
        ttk.Button(model_row, text="API Key…", command=self.configure_api_key).grid(row=0, column=2, padx=(6, 0))
        self.model_status = tk.StringVar()
        ttk.Label(model_row, textvariable=self.model_status, wraplength=330).grid(row=1, column=0, columnspan=2, sticky="w", pady=(3, 0))
        self.update_model_status()
        self.url = tk.StringVar()
        entry = ttk.Entry(box, textvariable=self.url)
        entry.grid(row=1, column=0, sticky="ew")
        entry.bind("<<Paste>>", lambda _event: self.root.after_idle(self.lookup_url))
        entry.bind("<Return>", lambda _event: self.lookup_url())
        self.clear_button = ttk.Button(box, text="Clear", command=self.clear_job)
        self.clear_button.grid(row=1, column=1, padx=(6, 0))
        self.job_title = tk.StringVar(value="Paste a job URL from any public platform")
        ttk.Label(box, textvariable=self.job_title, font=("Segoe UI", 10, "bold"), wraplength=330).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 2))
        self.lookup_status = tk.StringVar()
        ttk.Label(box, textvariable=self.lookup_status, wraplength=330).grid(row=3, column=0, columnspan=2, sticky="w")
        analysis = ttk.Frame(box)
        analysis.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        analysis.columnconfigure(0, weight=1)
        self.analysis_text = tk.Text(analysis, height=7, wrap="word", state="disabled", borderwidth=0, highlightthickness=0)
        self.analysis_text.grid(row=0, column=0, sticky="ew")
        analysis_scroll = ttk.Scrollbar(analysis, orient="vertical", command=self.analysis_text.yview)
        analysis_scroll.grid(row=0, column=1, sticky="ns")
        self.analysis_text.configure(yscrollcommand=analysis_scroll.set)
        resumes = ttk.LabelFrame(self.left, text="Resumes", padding=10)
        resumes.grid(row=3, column=0, sticky="ew", pady=8)
        resumes.columnconfigure(0, weight=1)
        self.resume_table = ttk.Treeview(resumes, columns=("use", "name", "updated"), show="headings", height=3)
        for key, label, width in (("use", "Use", 38), ("name", "Resume", 190), ("updated", "Updated", 75)):
            self.resume_table.heading(key, text=label)
            self.resume_table.column(key, width=width, minwidth=35)
        self.resume_table.grid(row=0, column=0, columnspan=4, sticky="ew")
        self.resume_table.bind("<Double-1>", lambda _event: self.toggle_resume())
        ttk.Button(resumes, text="Add", command=self.add_resumes).grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Button(resumes, text="Replace", command=self.replace_resume).grid(row=1, column=1, pady=(6, 0))
        ttk.Button(resumes, text="Rename", command=self.rename_resume).grid(row=1, column=2, pady=(6, 0))
        ttk.Button(resumes, text="Remove", command=self.remove_resume).grid(row=1, column=3, sticky="e", pady=(6, 0))
        self.history_label = ttk.Label(self.left, text="Application history", font=("Segoe UI", 10, "bold"))
        self.history_label.grid(row=4, column=0, sticky="w", pady=(10, 4))
        self.results = ttk.Treeview(self.left, columns=("company", "position", "date"), show="headings", height=4)
        for key, label, width in (("company", "Company", 90), ("position", "Role", 145), ("date", "Applied", 85)):
            self.results.heading(key, text=label)
            self.results.column(key, width=width, minwidth=55)
        self.results.grid(row=7, column=0, sticky="nsew")
        self.details = tk.StringVar()
        self.details_label = ttk.Label(self.left, textvariable=self.details, wraplength=340)
        self.details_label.grid(row=8, column=0, sticky="w", pady=(6, 0))
        self.results.bind("<<TreeviewSelect>>", self.show_details)
        self.set_history_visible(False)

    def _build_chart(self):
        ttk.Label(self.right, text="Application funnel", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")
        self.figure = Figure(figsize=(7, 6), dpi=100)
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.right)
        self.canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew")

    def selected_model(self):
        return MODEL_OPTIONS[self.model_choice.get()]

    def update_model_status(self, result=None):
        model = self.selected_model()
        if result and result.get("source") == "AI":
            self.model_status.set(f"Current: {result['model']}")
        elif model == "local":
            self.model_status.set("Current: Local assessment")
        elif not get_api_key():
            self.model_status.set("Current: Local assessment — API key not configured")
        elif result:
            self.model_status.set("Current: Local assessment — AI request unavailable")
        else:
            self.model_status.set(f"Selected: {model}")

    def change_model(self, _event=None):
        self.db.set_setting("assessment_model", self.selected_model())
        self.update_model_status()
        if self.posting and self.posting.description and self.resume_paths:
            self.start_resume_match()

    def configure_api_key(self):
        key = simpledialog.askstring(
            "OpenAI API key",
            "Enter an API key. Leave blank to remove the saved key.",
            show="*",
            parent=self.root,
        )
        if key is None:
            return
        try:
            save_api_key(key.strip())
        except Exception as error:
            messagebox.showerror("API key", f"Could not update Windows Credential Manager: {error}", parent=self.root)
            return
        self.update_model_status()
        if self.posting and self.posting.description and self.resume_paths:
            self.start_resume_match()

    def set_analysis(self, text):
        self.analysis_text.configure(state="normal")
        self.analysis_text.delete("1.0", "end")
        self.analysis_text.insert("1.0", text)
        self.analysis_text.configure(state="disabled")

    def set_history_visible(self, visible):
        if visible:
            self.history_label.grid()
            self.results.grid()
            self.details_label.grid()
        else:
            self.history_label.grid_remove()
            self.results.grid_remove()
            self.details_label.grid_remove()
            self.details.set("")

    def _build_footer(self):
        footer = ttk.Frame(self.root, padding=(18, 6, 18, 12))
        footer.grid(row=1, column=0, columnspan=2, sticky="ew")
        footer.columnconfigure(1, weight=1)
        self.sync_button = ttk.Button(footer, text="Sync Gmail", command=self.start_sync)
        self.sync_button.grid(row=0, column=0, sticky="w")
        last_sync = self.db.get_last_sync_at()
        self.sync_status = tk.StringVar(value=f"Last synced at {last_sync}" if last_sync else "Never synced")
        ttk.Label(footer, textvariable=self.sync_status).grid(row=0, column=1, sticky="e")

    def quick_range(self, days):
        today = datetime.now(ZoneInfo("America/Toronto")).date()
        first = self.dao.get_first_application_date()
        self.start.set((today - timedelta(days=days - 1)).isoformat() if days else first[:10] if first else today.isoformat())
        self.end.set(today.isoformat())
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
        bars = self.axes.barh(labels, counts, color=["#4263eb", "#f08080", "#e9b949", "#42b8a5", "#8b69ce"])
        self.axes.invert_yaxis()
        maximum = max(max(counts), 1)
        self.axes.set_xlim(0, maximum * 1.28)
        for bar, count in zip(bars, counts):
            pct = count / counts[0] * 100 if counts[0] else 0
            self.axes.text(bar.get_width() + maximum * .02, bar.get_y() + bar.get_height() / 2, f"{count}  {pct:.0f}%", va="center")
        self.axes.set_title(f"{start}  –  {end}")
        self.figure.tight_layout()
        self.canvas.draw_idle()

    @staticmethod
    def _resume_filetypes():
        return (("Resumes", "*.pdf *.docx *.txt *.md"), ("All files", "*.*"))

    def refresh_resumes(self):
        self.resume_table.delete(*self.resume_table.get_children())
        self.resume_paths = []
        for resume_id, name, path, enabled, updated in self.db.get_resumes():
            available = Path(path).is_file()
            use = "✓" if enabled and available else "—"
            self.resume_table.insert("", "end", iid=str(resume_id), values=(use, name, updated))
            if enabled and available:
                self.resume_paths.append(path)

    def selected_resume_id(self):
        selected = self.resume_table.selection()
        return int(selected[0]) if selected else None

    def add_resumes(self):
        paths = filedialog.askopenfilenames(parent=self.root, title="Add resumes", filetypes=self._resume_filetypes())
        for path in paths:
            self.db.add_resume(Path(path).stem, str(Path(path).resolve()))
        if paths:
            self.refresh_resumes()
            if self.posting and self.posting.description:
                self.start_resume_match()

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
        if not url or self.analyzing:
            return
        self.analyzing = True
        self.job_title.set("Analyzing job…")
        self.lookup_status.set("")
        self.set_analysis("")
        self.results.delete(*self.results.get_children())
        self.set_history_visible(False)
        threading.Thread(target=self._fetch_worker, args=(url,), daemon=True).start()

    def clear_job(self):
        self.analyzing = False
        self.url.set("")
        self.posting = None
        self.matches = []
        self.job_title.set("Paste a job URL from any public platform")
        self.lookup_status.set("")
        self.set_analysis("")
        self.results.delete(*self.results.get_children())
        self.set_history_visible(False)

    def _fetch_worker(self, url):
        try:
            posting = fetch_posting(url)
        except Exception:
            posting = Posting(url, warning="Could not analyze this job URL")
        self.events.put(("posting", posting))

    def show_posting(self, posting):
        self.posting = posting
        self.job_title.set(" · ".join(value for value in (posting.position, posting.company) if value) or "Job page unavailable")
        self.matches = self.duplicates.search(posting)
        self.results.delete(*self.results.get_children())
        for index, match in enumerate(self.matches):
            self.results.insert("", "end", iid=str(index), values=(match["company"], match["position"], match["dates"]))
        self.set_history_visible(bool(self.matches))
        if self.matches:
            self.lookup_status.set(f"Previously applied — {len(self.matches)} match(es)")
        elif posting.position:
            self.lookup_status.set("No previous application found")
        else:
            self.lookup_status.set(posting.warning or "Could not analyze this URL")
        if posting.description and self.resume_paths:
            self.start_resume_match()
        elif posting.description:
            self.set_analysis("Choose resumes to get a recommendation")
        else:
            self.set_analysis("Resume match unavailable without a job description")

    def start_resume_match(self):
        self.set_analysis("Comparing resumes…")
        job_context = f"{self.posting.position}\n{self.posting.description}"
        model = self.selected_model()
        threading.Thread(target=self._resume_worker, args=(job_context, tuple(self.resume_paths), model), daemon=True).start()

    def _resume_worker(self, description, paths, model):
        result, errors = recommend(description, paths, model)
        self.events.put(("resume", (result, errors)))

    def show_details(self, _event=None):
        selected = self.results.selection()
        if selected:
            match = self.matches[int(selected[0])]
            self.details.set(f"{match['status']} · {match['reason']}")

    def start_sync(self):
        if not self.synchronize or str(self.sync_button["state"]) == "disabled":
            return
        self.sync_button.configure(state="disabled")
        self.sync_status.set("Syncing…")
        def worker():
            try:
                self.synchronize()
                self.events.put(("sync", None))
            except Exception as error:
                self.events.put(("sync", str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "posting":
                    self.analyzing = False
                    if value.url == self.url.get().strip():
                        self.show_posting(value)
                elif kind == "resume":
                    result, errors = value
                    if result:
                        self.update_model_status(result)
                        self.set_analysis(format_assessment(result))
                    else:
                        self.set_analysis(errors[0] if errors else "No readable resumes found")
                else:
                    self.sync_button.configure(state="normal")
                    last_sync = self.db.get_last_sync_at()
                    self.sync_status.set("Sync failed" if value else f"Last synced at {last_sync}")
                    self.refresh_chart()
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def run(self):
        self.root.mainloop()
