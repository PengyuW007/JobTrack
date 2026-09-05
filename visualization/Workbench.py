import queue
import threading
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk, messagebox
from zoneinfo import ZoneInfo

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from business.AnalyticsService import AnalyticsService
from business.DuplicateService import DuplicateService, Posting, fetch_posting
from persistence.DataAccessJob import DataAccessJob
from visualization.DateRangeDialog import DateRangeDialog


class Workbench:
    def __init__(self, db, synchronize=None):
        self.db = db
        self.dao = DataAccessJob(db.conn)
        self.duplicates = DuplicateService(db.conn)
        self.synchronize = synchronize
        self.events = queue.Queue()
        self.matches = []
        self.matched_posting = None
        self.root = tk.Tk()
        self.root.title('JobTrack 工作台')
        self.root.geometry('1180x900')
        self.root.minsize(950, 740)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=3)
        self.root.rowconfigure(2, weight=2)
        today = datetime.now(ZoneInfo('America/Toronto')).date().isoformat()
        first = self.dao.get_first_application_date()
        self.start = tk.StringVar(value=first[:10] if first else today)
        self.end = tk.StringVar(value=today)
        header = ttk.Frame(self.root, padding=10)
        header.grid(row=0, column=0, sticky='ew')
        for column, (label, value) in enumerate([('开始', self.start), ('结束', self.end)]):
            ttk.Label(header, text=label).grid(row=0, column=column * 3)
            entry = ttk.Entry(header, textvariable=value, width=12)
            entry.grid(row=0, column=column * 3 + 1, padx=4)
            entry.bind('<Return>', lambda event: self.refresh_chart())
            ttk.Button(header, text='日历', command=lambda v=value: DateRangeDialog.open_calendar(self.root, v)).grid(row=0, column=column * 3 + 2)
        ttk.Button(header, text='刷新图表', command=self.refresh_chart).grid(row=0, column=6, padx=8)
        for column, days in enumerate((7, 30, 90), 7):
            ttk.Button(header, text=f'近 {days} 天', command=lambda d=days: self.quick_range(d)).grid(row=0, column=column)
        ttk.Button(header, text='全部', command=lambda: self.quick_range(None)).grid(row=0, column=10)
        self.sync_button = ttk.Button(header, text='同步 Gmail', command=self.start_sync)
        self.sync_button.grid(row=0, column=11, padx=8)
        self.sync_status = tk.StringVar(value='已加载本地记录；同步可补充历史邮件证据。')
        ttk.Label(header, textvariable=self.sync_status).grid(row=1, column=0, columnspan=12, sticky='w', pady=(8, 0))
        self.figure = Figure(figsize=(10, 3), dpi=100)
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.root)
        self.canvas.get_tk_widget().grid(row=1, column=0, sticky='nsew')

        panel = ttk.LabelFrame(self.root, text='职位查重 · 始终查询全部历史，不受上方日期影响', padding=10)
        panel.grid(row=2, column=0, sticky='nsew', padx=10, pady=10)
        panel.columnconfigure(1, weight=1)
        panel.rowconfigure(5, weight=1)
        self.url = tk.StringVar()
        self.company = tk.StringVar()
        self.position = tk.StringVar()
        ttk.Label(panel, text='职位网址').grid(row=0, column=0, sticky='w')
        url_entry = ttk.Entry(panel, textvariable=self.url)
        url_entry.grid(row=0, column=1, sticky='ew', padx=6)
        url_entry.bind('<<Paste>>', lambda event: self.root.after_idle(self.lookup_url))
        url_entry.bind('<Return>', lambda event: self.lookup_url())
        self.lookup_button = ttk.Button(panel, text='解析并查重', command=self.lookup_url)
        self.lookup_button.grid(row=0, column=2)
        fields = ttk.Frame(panel)
        fields.grid(row=1, column=0, columnspan=3, sticky='ew', pady=6)
        fields.columnconfigure(1, weight=1)
        fields.columnconfigure(3, weight=1)
        ttk.Label(fields, text='公司').grid(row=0, column=0)
        ttk.Entry(fields, textvariable=self.company).grid(row=0, column=1, sticky='ew', padx=6)
        ttk.Label(fields, text='岗位名称').grid(row=0, column=2)
        ttk.Entry(fields, textvariable=self.position).grid(row=0, column=3, sticky='ew', padx=6)
        ttk.Label(panel, text='职位描述').grid(row=2, column=0, sticky='nw')
        self.description = tk.Text(panel, height=3, wrap='word')
        self.description.grid(row=2, column=1, sticky='ew', padx=6)
        ttk.Button(panel, text='按补充信息查重', command=self.search).grid(row=2, column=2)
        self.lookup_status = tk.StringVar(value='粘贴网址后自动解析；历史信息不足时只能给出候选结果。')
        ttk.Label(panel, textvariable=self.lookup_status, wraplength=1050).grid(row=3, column=0, columnspan=3, sticky='w', pady=5)
        ttk.Label(panel, text='选中结果可查看全部日期与依据。只有确认是同一投递后，才关联当前职位描述。').grid(row=4, column=0, columnspan=3, sticky='w')
        self.results = ttk.Treeview(panel, columns=('company', 'position', 'date', 'reason'), show='headings', height=5)
        for key, label, width in [('company', '公司', 150), ('position', '岗位', 230), ('date', '历史时间', 270), ('reason', '匹配依据', 370)]:
            self.results.heading(key, text=label)
            self.results.column(key, width=width, minwidth=80)
        self.results.grid(row=5, column=0, columnspan=3, sticky='nsew')
        scrollbar = ttk.Scrollbar(panel, orient='vertical', command=self.results.yview)
        scrollbar.grid(row=5, column=3, sticky='ns')
        self.results.configure(yscrollcommand=scrollbar.set)
        self.results.bind('<<TreeviewSelect>>', self.show_details)
        self.details = tk.StringVar()
        ttk.Label(panel, textvariable=self.details, wraplength=1040).grid(row=6, column=0, columnspan=3, sticky='w', pady=4)
        ttk.Button(panel, text='确认同一投递并保存网址／描述', command=self.link_posting).grid(row=7, column=0, columnspan=3, sticky='e')
        self.refresh_chart()
        self.root.after(100, self.poll)
        if synchronize:
            self.root.after(250, self.start_sync)

    def quick_range(self, days):
        today = datetime.now(ZoneInfo('America/Toronto')).date()
        first = self.dao.get_first_application_date()
        self.start.set((today - timedelta(days=days - 1)).isoformat() if days else first[:10] if first else today.isoformat())
        self.end.set(today.isoformat())
        self.refresh_chart()

    def refresh_chart(self):
        try:
            start, end = DateRangeDialog.validate_dates(self.start.get().strip(), self.end.get().strip())
        except ValueError as error:
            messagebox.showerror('日期错误', str(error), parent=self.root)
            return
        values = AnalyticsService(self.dao, start, end).get_funnel_data()
        labels = ['Applications', 'Rejected', 'Assessments', 'Interviews', 'Offers']
        counts = [values[label.lower()] for label in labels]
        self.axes.clear()
        bars = self.axes.barh(labels, counts, color=['#4263eb', '#f08080', '#e9b949', '#42b8a5', '#8b69ce'])
        self.axes.invert_yaxis()
        self.axes.set_xlim(0, max(max(counts), 1) * 1.25)
        for bar, count in zip(bars, counts):
            pct = count / counts[0] * 100 if counts[0] else 0
            self.axes.text(bar.get_width() + max(max(counts), 1) * .015, bar.get_y() + bar.get_height() / 2,
                           f'{count} ({pct:.1f}%)', va='center')
        self.axes.set_title(f'JobTrack Recruitment Funnel | {start} to {end}')
        self.figure.tight_layout()
        self.canvas.draw_idle()

    def start_sync(self):
        if not self.synchronize or str(self.sync_button['state']) == 'disabled':
            return
        self.sync_button.configure(state='disabled')
        self.sync_status.set('正在同步并补充历史邮件；工作台仍可使用…')
        def worker():
            try:
                self.synchronize()
                self.events.put(('sync', None))
            except Exception as error:
                self.events.put(('sync', str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def lookup_url(self):
        if str(self.lookup_button['state']) == 'disabled':
            return
        url = self.url.get().strip()
        if not url:
            return
        self.company.set('')
        self.position.set('')
        self.description.delete('1.0', 'end')
        self.matches = []
        self.matched_posting = None
        self.results.delete(*self.results.get_children())
        self.details.set('')
        self.lookup_button.configure(state='disabled')
        self.lookup_status.set('正在读取职位页面…')
        def worker():
            try:
                posting = fetch_posting(url)
            except Exception:
                posting = Posting(url, warning='无法读取页面（可能需要登录或限制访问）。已查询网址；请补充公司、岗位和描述。')
            self.events.put(('posting', posting))
        threading.Thread(target=worker, daemon=True).start()

    def current_posting(self):
        return Posting(self.url.get().strip(), self.company.get().strip(), self.position.get().strip(), self.description.get('1.0', 'end').strip())

    def search(self, warning=''):
        try:
            posting = self.current_posting()
            matches = self.duplicates.search(posting)
        except ValueError as error:
            self.lookup_status.set(str(error))
            return
        self.matches = matches
        self.matched_posting = posting
        self.results.delete(*self.results.get_children())
        self.details.set('')
        for index, match in enumerate(matches):
            self.results.insert('', 'end', iid=str(index), values=(match['company'], match['position'], match['dates'], match['reason']))
        message = f'发现 {len(matches)} 条历史匹配，请核对依据。' if matches else '未找到匹配记录；不代表从未投递，旧邮件可能缺少职位信息。'
        self.lookup_status.set((warning + ' ' + message).strip())

    def show_details(self, event=None):
        selected = self.results.selection()
        if selected:
            match = self.matches[int(selected[0])]
            self.details.set(f"{match['dates']}\n状态：{match['status']} · {match['reason']}")

    def link_posting(self):
        selected = self.results.selection()
        if not selected or self.matched_posting is None:
            self.lookup_status.set('请先查重并选中一条历史记录。')
            return
        if self.current_posting() != self.matched_posting:
            self.lookup_status.set('职位信息已更改，请重新查重后再关联。')
            return
        self.duplicates.save_snapshot(self.matches[int(selected[0])]['key'], self.matched_posting)
        self.search('已保存关联，以后可比较新网址与此职位描述。')

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'sync':
                    self.sync_button.configure(state='normal')
                    self.sync_status.set('同步失败，本地记录仍可用：' + value if value else '同步完成，历史记录已更新。')
                    self.refresh_chart()
                    if self.matched_posting:
                        self.search()
                else:
                    self.lookup_button.configure(state='normal')
                    if value.url != self.url.get().strip():
                        self.lookup_url()
                        continue
                    self.company.set(value.company)
                    self.position.set(value.position)
                    self.description.delete('1.0', 'end')
                    self.description.insert('1.0', value.description)
                    self.search(value.warning)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def run(self):
        self.root.mainloop()
