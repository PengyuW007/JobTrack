import tkinter as tk
import calendar
from datetime import date, datetime, timedelta
from tkinter import messagebox, ttk
from zoneinfo import ZoneInfo


class CalendarPopup(tk.Toplevel):

    def __init__(self, parent, initial_date, on_select):
        super().__init__(parent)
        self.title("Select date")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.on_select = on_select
        self.visible_month = initial_date.replace(day=1)

        self.header = ttk.Frame(self, padding=(8, 8, 8, 3))
        self.header.grid(row=0, column=0, sticky="ew")
        ttk.Button(self.header, text="<", width=3, command=self.previous_month).grid(
            row=0, column=0
        )
        self.month_label = ttk.Label(
            self.header, width=18, anchor="center", font=("Segoe UI", 10, "bold")
        )
        self.month_label.grid(row=0, column=1, padx=5)
        ttk.Button(self.header, text=">", width=3, command=self.next_month).grid(
            row=0, column=2
        )

        self.days_frame = ttk.Frame(self, padding=(8, 3, 8, 8))
        self.days_frame.grid(row=1, column=0)
        self.render_month()

    def change_month(self, offset):
        month_index = self.visible_month.year * 12 + self.visible_month.month - 1
        month_index += offset
        year, month_zero_based = divmod(month_index, 12)
        self.visible_month = date(year, month_zero_based + 1, 1)
        self.render_month()

    def previous_month(self):
        self.change_month(-1)

    def next_month(self):
        self.change_month(1)

    def render_month(self):
        for child in self.days_frame.winfo_children():
            child.destroy()

        self.month_label.configure(
            text=self.visible_month.strftime("%B %Y")
        )
        for column, weekday in enumerate(("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")):
            ttk.Label(self.days_frame, text=weekday, anchor="center", width=4).grid(
                row=0, column=column
            )

        weeks = calendar.monthcalendar(
            self.visible_month.year,
            self.visible_month.month
        )
        for row, week in enumerate(weeks, start=1):
            for column, day_number in enumerate(week):
                if day_number == 0:
                    ttk.Label(self.days_frame, text="", width=4).grid(
                        row=row, column=column
                    )
                    continue
                ttk.Button(
                    self.days_frame,
                    text=str(day_number),
                    width=3,
                    command=lambda day=day_number: self.select_day(day)
                ).grid(row=row, column=column, padx=1, pady=1)

    def select_day(self, day_number):
        selected = self.visible_month.replace(day=day_number)
        self.on_select(selected.isoformat())
        self.destroy()


class DateRangeDialog:
    DATE_FORMAT = "%Y-%m-%d"

    @classmethod
    def validate_dates(cls, start_date, end_date):
        try:
            start = datetime.strptime(start_date, cls.DATE_FORMAT).date()
            end = datetime.strptime(end_date, cls.DATE_FORMAT).date()
        except ValueError as error:
            raise ValueError("Please enter dates as YYYY-MM-DD.") from error

        if start > end:
            raise ValueError("Start date cannot be later than end date.")

        return start.isoformat(), end.isoformat()

    @classmethod
    def select(cls, default_start, default_end):
        root = tk.Tk()
        root.title("JobTrack Date Range")
        root.resizable(False, False)

        result = {"value": None}
        start_value = tk.StringVar(value=default_start)
        end_value = tk.StringVar(value=default_end)

        frame = ttk.Frame(root, padding=18)
        frame.grid(row=0, column=0)

        ttk.Label(
            frame,
            text="Choose the application date range",
            font=("Segoe UI", 11, "bold")
        ).grid(row=0, column=0, columnspan=3, pady=(0, 14))

        quick_range_frame = ttk.LabelFrame(frame, text="Quick ranges", padding=8)
        quick_range_frame.grid(
            row=1, column=0, columnspan=3, sticky="ew", pady=(0, 10)
        )

        def set_quick_range(number_of_days):
            today = datetime.now(ZoneInfo("America/Toronto")).date()
            start = today - timedelta(days=number_of_days - 1)
            start_value.set(start.isoformat())
            end_value.set(today.isoformat())

        quick_ranges = (
            ("Today", 1),
            ("Last 7 Days", 7),
            ("Last 30 Days", 30),
            ("Last 90 Days", 90)
        )
        for column, (label, number_of_days) in enumerate(quick_ranges):
            ttk.Button(
                quick_range_frame,
                text=label,
                command=lambda days=number_of_days: set_quick_range(days)
            ).grid(row=0, column=column, padx=3)

        ttk.Label(frame, text="Start date").grid(
            row=2, column=0, sticky="w", padx=(0, 12), pady=5
        )
        start_entry = ttk.Entry(frame, textvariable=start_value, width=16)
        start_entry.grid(row=2, column=1, pady=5)
        ttk.Button(
            frame,
            text="Choose...",
            command=lambda: cls.open_calendar(root, start_value)
        ).grid(row=2, column=2, padx=(8, 0), pady=5)

        ttk.Label(frame, text="End date").grid(
            row=3, column=0, sticky="w", padx=(0, 12), pady=5
        )
        ttk.Entry(frame, textvariable=end_value, width=16).grid(
            row=3, column=1, pady=5
        )
        ttk.Button(
            frame,
            text="Choose...",
            command=lambda: cls.open_calendar(root, end_value)
        ).grid(row=3, column=2, padx=(8, 0), pady=5)

        ttk.Label(frame, text="Format: YYYY-MM-DD").grid(
            row=4, column=0, columnspan=3, pady=(3, 14)
        )

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=5, column=0, columnspan=3, sticky="e")

        def confirm():
            try:
                result["value"] = cls.validate_dates(
                    start_value.get().strip(),
                    end_value.get().strip()
                )
            except ValueError as error:
                messagebox.showerror("Invalid date range", str(error), parent=root)
                return
            root.destroy()

        ttk.Button(button_frame, text="Cancel", command=root.destroy).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(button_frame, text="Show report", command=confirm).grid(
            row=0, column=1
        )

        root.bind("<Return>", lambda _event: confirm())
        root.bind("<Escape>", lambda _event: root.destroy())
        root.protocol("WM_DELETE_WINDOW", root.destroy)
        start_entry.focus_set()

        root.update_idletasks()
        x = (root.winfo_screenwidth() - root.winfo_width()) // 2
        y = (root.winfo_screenheight() - root.winfo_height()) // 2
        root.geometry(f"+{x}+{y}")
        root.mainloop()

        return result["value"]

    @classmethod
    def open_calendar(cls, parent, target_value):
        try:
            initial_date = datetime.strptime(
                target_value.get().strip(), cls.DATE_FORMAT
            ).date()
        except ValueError:
            initial_date = date.today()

        CalendarPopup(parent, initial_date, target_value.set)
