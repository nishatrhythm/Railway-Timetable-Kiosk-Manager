from __future__ import annotations

import json
import os
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk


APP_DIR = Path(__file__).resolve().parent
DATA_FILE = APP_DIR / "data.json"
INDEX_FILE = APP_DIR / "index.html"
WINDOW_TITLE = "ঢাকা রেলওয়ে স্টেশন - ট্রেন সময়সূচী"

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
VK_F5 = 0x74


FIELDS = [
    ("number", "ট্রেন নং"),
    ("name", "ট্রেনের নাম"),
    ("platform", "প্লাটফর্ম নং"),
    ("destination", "গন্তব্য"),
    ("departure", "ছাড়ার সময়"),
    ("expected", "সম্ভাব্য সময়"),
]


def find_edge_executable() -> Path | None:
    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def normalize_record(record: dict[str, object]) -> dict[str, str]:
    return {field: str(record.get(field, "") or "") for field, _ in FIELDS}


def record_is_blank(record: dict[str, str]) -> bool:
    return all(not value.strip() for value in record.values())


def platform_to_editor(value: str) -> str:
    return value.replace("<br>", "\n")


def platform_to_storage(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.replace("\n", "<br>")


def platform_for_table(value: str) -> str:
    return value.replace("<br>", "\n")


def enable_windows_dpi_awareness() -> None:
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def refresh_window_by_title(title: str) -> bool:
    try:
        import ctypes

        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, title)
        if not hwnd:
            return False
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        user32.PostMessageW(hwnd, WM_KEYDOWN, VK_F5, 0)
        user32.PostMessageW(hwnd, WM_KEYUP, VK_F5, 0)
        return True
    except Exception:
        return False


class KioskManager(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Railway Kiosk Manager")
        self.geometry("1180x760")
        self.minsize(1080, 680)
        self.configure(bg="#11161a")

        self.records: list[dict[str, str]] = []
        self.kiosk_process: subprocess.Popen[str] | None = None
        self.kiosk_running = False

        self._build_style()
        self._build_ui()
        self.load_from_disk(confirm_action=False)
        self.after(0, lambda: self.state("zoomed"))
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def confirm(self, message: str, title: str = "Confirm") -> bool:
        return messagebox.askyesno(title, message)

    def _build_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#11161a")
        style.configure("Header.TLabel", background="#11161a", foreground="#d7e7ee", font=("Nirmala UI", 16, "bold"))
        style.configure("Subtle.TLabel", background="#11161a", foreground="#8fa3af", font=("Nirmala UI", 10))
        style.configure(
            "Manager.TButton",
            font=("Nirmala UI", 10, "bold"),
            padding=(12, 8),
            background="#20313b",
            foreground="#eaf4fa",
            borderwidth=1,
            relief="flat",
        )
        style.map(
            "Manager.TButton",
            background=[("active", "#2c424d")],
            foreground=[("active", "#ffffff")],
        )
        style.configure(
            "Manager.Kiosk.TButton",
            font=("Nirmala UI", 10, "bold"),
            padding=(14, 10),
            background="#1a242c",
            foreground="#eaf4fa",
            borderwidth=1,
            relief="flat",
        )
        style.map(
            "Manager.Kiosk.TButton",
            background=[("active", "#2c424d")],
            foreground=[("active", "#ffffff")],
        )
        style.configure(
            "Manager.KioskStart.TButton",
            font=("Nirmala UI", 10, "bold"),
            padding=(14, 10),
            background="#1f5f32",
            foreground="#eaf4fa",
            borderwidth=1,
            relief="flat",
        )
        style.map(
            "Manager.KioskStart.TButton",
            background=[("active", "#2d7a42")],
            foreground=[("active", "#ffffff")],
        )
        style.configure(
            "Manager.KioskStop.TButton",
            font=("Nirmala UI", 10, "bold"),
            padding=(14, 10),
            background="#7b2430",
            foreground="#ffeef1",
            borderwidth=1,
            relief="flat",
        )
        style.map(
            "Manager.KioskStop.TButton",
            background=[("active", "#a73746")],
            foreground=[("active", "#ffffff")],
        )
        style.configure(
            "Manager.KioskRefresh.TButton",
            font=("Nirmala UI", 10, "bold"),
            padding=(14, 10),
            background="#1f4f72",
            foreground="#eaf4fa",
            borderwidth=1,
            relief="flat",
        )
        style.map(
            "Manager.KioskRefresh.TButton",
            background=[("active", "#2b6f9b")],
            foreground=[("active", "#ffffff")],
        )
        style.configure(
            "Treeview",
            background="#172027",
            fieldbackground="#172027",
            foreground="#f2f7fa",
            rowheight=42,
            font=("Nirmala UI", 10),
        )
        style.configure(
            "Treeview.Heading",
            background="#20313b",
            foreground="#eaf4fa",
            font=("Nirmala UI", 10, "bold"),
        )
        style.map(
            "Treeview.Heading",
            background=[("active", "#2c424d")],
            foreground=[("active", "#ffffff")],
        )
        style.map(
            "Treeview",
            background=[("selected", "#2a6f95")],
            foreground=[("selected", "#ffffff")],
        )

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top_bar = ttk.Frame(self, padding=14)
        top_bar.grid(row=0, column=0, sticky="ew")
        top_bar.grid_columnconfigure(0, weight=1)
        top_bar.grid_columnconfigure(1, weight=1)
        top_bar.grid_columnconfigure(2, weight=1)

        title_box = ttk.Frame(top_bar)
        title_box.grid(row=0, column=1, sticky="n")
        title_box.grid_columnconfigure(0, weight=1)
        ttk.Label(title_box, text="Railway Kiosk Manager", style="Header.TLabel", anchor="center").grid(row=0, column=0, sticky="ew")
        ttk.Label(title_box, text="", style="Subtle.TLabel").grid(row=1, column=0, sticky="ew", pady=(10, 18))

        main = ttk.Frame(self, padding=(14, 0, 14, 14))
        main.grid(row=1, column=0, sticky="nsew")
        main.grid_columnconfigure(0, weight=3)
        main.grid_columnconfigure(1, weight=2)
        main.grid_rowconfigure(0, weight=1)

        table_frame = ttk.Frame(main)
        table_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        columns = [field for field, _ in FIELDS]
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        tree_scroll_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        tree_scroll_y.grid(row=0, column=1, sticky="ns")
        tree_scroll_x = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        tree_scroll_x.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)

        widths = {"number": 90, "name": 180, "platform": 110, "destination": 150, "departure": 100, "expected": 100}
        for field, title in FIELDS:
            self.tree.heading(field, text=title)
            self.tree.column(field, width=widths[field], anchor="center", stretch=True)

        form_frame = ttk.Frame(main)
        form_frame.grid(row=0, column=1, sticky="nsew")
        form_frame.grid_columnconfigure(1, weight=1)

        editor_header = ttk.Frame(form_frame)
        editor_header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 18))
        editor_header.grid_columnconfigure(0, weight=1)
        editor_header.grid_columnconfigure(1, weight=1)

        ttk.Label(editor_header, text="Record Editor", style="Header.TLabel").grid(row=0, column=0, sticky="w")

        editor_button_box = ttk.Frame(editor_header)
        editor_button_box.grid(row=0, column=1, sticky="e")
        for label, handler in [
            ("Load", self.load_from_disk),
            ("Save JSON", self.save_to_disk),
        ]:
            ttk.Button(editor_button_box, text=label, command=handler, style="Manager.TButton").pack(side="left", padx=(0, 8))

        self.entries: dict[str, ttk.Entry] = {}
        for row, (field, label) in enumerate(FIELDS, start=1):
            ttk.Label(form_frame, text=label, style="Subtle.TLabel").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 12))
            if field == "platform":
                entry = tk.Text(
                    form_frame,
                    height=3,
                    wrap="word",
                    bg="#1b242c",
                    fg="#f2f7fa",
                    insertbackground="#f2f7fa",
                    relief="flat",
                    highlightthickness=1,
                    highlightbackground="#425866",
                    highlightcolor="#5f7f93",
                    font=("Nirmala UI", 10),
                )
            else:
                entry = tk.Entry(
                    form_frame,
                    bg="#1b242c",
                    fg="#f2f7fa",
                    insertbackground="#f2f7fa",
                    relief="flat",
                    highlightthickness=1,
                    highlightbackground="#425866",
                    highlightcolor="#5f7f93",
                    font=("Nirmala UI", 10),
                )
            entry.grid(row=row, column=1, sticky="ew", pady=6)
            self.entries[field] = entry

        action_box = ttk.Frame(form_frame)
        action_box.grid(row=len(FIELDS) + 1, column=0, columnspan=2, sticky="ew", pady=(18, 10))
        action_box.grid_columnconfigure(0, weight=1)
        action_box.grid_columnconfigure(1, weight=1)
        action_box.grid_columnconfigure(2, weight=1)

        ttk.Button(action_box, text="Add New", command=self.add_record, style="Manager.TButton").grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=4)
        ttk.Button(action_box, text="Update Selected", command=self.update_selected, style="Manager.TButton").grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(action_box, text="Delete Selected", command=self.delete_selected, style="Manager.TButton").grid(row=0, column=2, sticky="ew", padx=(8, 0), pady=4)
        ttk.Button(action_box, text="Move Up", command=self.move_up, style="Manager.TButton").grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=4)
        ttk.Button(action_box, text="Move Down", command=self.move_down, style="Manager.TButton").grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(action_box, text="Clear Form", command=self.clear_form_confirmed, style="Manager.TButton").grid(row=1, column=2, sticky="ew", padx=(8, 0), pady=4)

        kiosk_panel = tk.Frame(form_frame, bg="#0f151b", highlightbackground="#4f6675", highlightthickness=1)
        kiosk_panel.grid(row=len(FIELDS) + 2, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        kiosk_panel.grid_columnconfigure(0, weight=1)
        kiosk_panel.grid_columnconfigure(1, weight=1)
        kiosk_panel.grid_columnconfigure(2, weight=1)

        kiosk_title = tk.Frame(kiosk_panel, bg="#0f151b")
        kiosk_title.grid(row=0, column=0, columnspan=3, sticky="ew", padx=12, pady=(12, 4))
        kiosk_title.grid_columnconfigure(0, weight=1)

        ttk.Label(kiosk_title, text="Live Kiosk Controls", style="Header.TLabel", anchor="center").grid(row=0, column=0, sticky="ew")
        ttk.Label(kiosk_title, text="", style="Subtle.TLabel").grid(row=1, column=0, sticky="ew", pady=(4, 0))

        kiosk_button_row = tk.Frame(kiosk_panel, bg="#0f151b")
        kiosk_button_row.grid(row=1, column=0, columnspan=3, sticky="ew", padx=12, pady=(10, 12))
        kiosk_button_row.grid_columnconfigure(0, weight=1)
        kiosk_button_row.grid_columnconfigure(1, weight=1)
        kiosk_button_row.grid_columnconfigure(2, weight=1)

        self.start_kiosk_button = ttk.Button(kiosk_button_row, text="Start", command=self.start_kiosk, style="Manager.KioskStart.TButton")
        self.stop_kiosk_button = ttk.Button(kiosk_button_row, text="Stop", command=self.stop_kiosk, style="Manager.KioskStop.TButton")
        self.refresh_kiosk_button = ttk.Button(kiosk_button_row, text="Refresh", command=self.refresh_kiosk, style="Manager.KioskRefresh.TButton")

        self.start_kiosk_button.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.stop_kiosk_button.grid(row=0, column=1, sticky="ew", padx=4)
        self.refresh_kiosk_button.grid(row=0, column=2, sticky="ew", padx=(8, 0))

        self.update_kiosk_controls()

        self.status_var = tk.StringVar(value="Ready")
        status = ttk.Label(self, textvariable=self.status_var, style="Subtle.TLabel", anchor="w", padding=(14, 0, 14, 12))
        status.grid(row=2, column=0, sticky="ew")

    def set_status(self, text: str) -> None:
        self.status_var.set(text)

    def update_kiosk_controls(self) -> None:
        kiosk_running = self.kiosk_process is not None and self.kiosk_process.poll() is None
        self.kiosk_running = kiosk_running

        if kiosk_running:
            self.start_kiosk_button.configure(text="Running", state="disabled")
            self.stop_kiosk_button.configure(state="normal")
            self.refresh_kiosk_button.configure(state="normal")
        else:
            self.start_kiosk_button.configure(text="Start", state="normal")
            self.stop_kiosk_button.configure(state="disabled")
            self.refresh_kiosk_button.configure(state="disabled")

    def read_form(self) -> dict[str, str]:
        data: dict[str, str] = {}
        for field, entry in self.entries.items():
            if isinstance(entry, tk.Text):
                value = entry.get("1.0", "end-1c")
            else:
                value = entry.get()
            value = value.strip()
            if field == "platform":
                value = platform_to_storage(value)
            data[field] = value
        return data

    def fill_form(self, record: dict[str, str]) -> None:
        for field, entry in self.entries.items():
            value = record.get(field, "")
            if field == "platform":
                value = platform_to_editor(value)
            if isinstance(entry, tk.Text):
                entry.delete("1.0", tk.END)
                entry.insert("1.0", value)
            else:
                entry.delete(0, tk.END)
                entry.insert(0, value)

    def clear_form(self) -> None:
        for entry in self.entries.values():
            if isinstance(entry, tk.Text):
                entry.delete("1.0", tk.END)
            else:
                entry.delete(0, tk.END)

    def refresh_tree(self, select_index: int | None = None) -> None:
        self.tree.delete(*self.tree.get_children())
        for index, record in enumerate(self.records):
            self.tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=[platform_for_table(record[field]) if field == "platform" else record[field] for field, _ in FIELDS],
            )
        if select_index is not None and 0 <= select_index < len(self.records):
            self.tree.selection_set(str(select_index))
            self.tree.see(str(select_index))

    def selected_index(self) -> int | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return int(selection[0])

    def refresh_kiosk(self) -> None:
        if not self.confirm("Refresh the kiosk browser so the latest data.json changes are shown?"):
            return
        if not self.save_to_disk(confirm_action=False):
            return
        if refresh_window_by_title(WINDOW_TITLE):
            self.set_status("Kiosk refreshed")
            return
        if self.kiosk_process and self.kiosk_process.poll() is None:
            self.set_status("Kiosk window not found, browser is still running")
            return
        messagebox.showinfo("Refresh kiosk", "Kiosk is not running. Start it first, then refresh will reload the page in place.")

    def on_tree_select(self, _event: object) -> None:
        index = self.selected_index()
        if index is None:
            return
        self.fill_form(self.records[index])
        self.set_status(f"Selected row {index + 1}")

    def load_from_disk(self, confirm_action: bool = True) -> None:
        if confirm_action and not self.confirm("Reload records from data.json? Unsaved changes in the editor will be lost."):
            return
        try:
            if DATA_FILE.exists():
                payload = json.loads(DATA_FILE.read_text(encoding="utf-8-sig"))
            else:
                payload = []
            if not isinstance(payload, list):
                raise ValueError("data.json must contain a JSON array")
            self.records = [normalize_record(item if isinstance(item, dict) else {}) for item in payload]
            self.refresh_tree()
            self.clear_form()
            self.set_status(f"Loaded {len(self.records)} records from data.json")
            self.update_kiosk_controls()
        except Exception as error:
            messagebox.showerror("Load failed", str(error))
            self.set_status("Load failed")

    def save_to_disk(self, confirm_action: bool = True) -> bool:
        if confirm_action and not self.confirm("Save the current records to data.json?"):
            return False
        try:
            DATA_FILE.write_text(json.dumps(self.records, ensure_ascii=False, indent=2), encoding="utf-8")
            self.set_status(f"Saved {len(self.records)} records to data.json")
            self.update_kiosk_controls()
            return True
        except Exception as error:
            messagebox.showerror("Save failed", str(error))
            self.set_status("Save failed")
            return False

    def validate_record(self, record: dict[str, str]) -> bool:
        if record_is_blank(record):
            messagebox.showinfo("Blank row not allowed", "At least one field must contain data.")
            return False
        return True

    def add_record(self) -> None:
        if not self.confirm("Add this new row to the list?"):
            return
        record = normalize_record(self.read_form())
        if not self.validate_record(record):
            return
        self.records.append(record)
        self.refresh_tree(len(self.records) - 1)
        self.set_status("Added new row")

    def update_selected(self) -> None:
        index = self.selected_index()
        if index is None:
            messagebox.showinfo("Update selected", "Select a row first.")
            return
        if not self.confirm(f"Replace row {index + 1} with the values currently in the form?"):
            return
        updated_record = normalize_record(self.read_form())
        if not self.validate_record(updated_record):
            return
        self.records[index] = updated_record
        self.refresh_tree(index)
        self.set_status(f"Updated row {index + 1}")

    def delete_selected(self) -> None:
        index = self.selected_index()
        if index is None:
            messagebox.showinfo("Delete selected", "Select a row first.")
            return
        if not self.confirm(f"Delete row {index + 1}?"):
            return
        del self.records[index]
        new_index = min(index, len(self.records) - 1) if self.records else None
        self.refresh_tree(new_index)
        self.clear_form() if new_index is None else self.fill_form(self.records[new_index])
        self.set_status("Deleted row")

    def move_up(self) -> None:
        index = self.selected_index()
        if index is None or index == 0:
            return
        if not self.confirm(f"Move row {index + 1} up?"):
            return
        self.records[index - 1], self.records[index] = self.records[index], self.records[index - 1]
        self.refresh_tree(index - 1)
        self.fill_form(self.records[index - 1])
        self.set_status("Moved row up")

    def move_down(self) -> None:
        index = self.selected_index()
        if index is None or index >= len(self.records) - 1:
            return
        if not self.confirm(f"Move row {index + 1} down?"):
            return
        self.records[index + 1], self.records[index] = self.records[index], self.records[index + 1]
        self.refresh_tree(index + 1)
        self.fill_form(self.records[index + 1])
        self.set_status("Moved row down")

    def start_kiosk(self, confirm_action: bool = True) -> None:
        if confirm_action and not self.confirm("Save changes and start the kiosk browser?"):
            return
        if not self.save_to_disk(confirm_action=False):
            return
        edge_path = find_edge_executable()
        if edge_path is None:
            messagebox.showerror("Edge not found", "Microsoft Edge was not found in the standard install locations.")
            return
        if self.kiosk_process and self.kiosk_process.poll() is None:
            messagebox.showinfo("Kiosk already running", "The kiosk window is already running.")
            return

        args = [
            str(edge_path),
            "--kiosk",
            str(INDEX_FILE),
            "--edge-kiosk-type=fullscreen",
            "--no-first-run",
            "--allow-file-access-from-files",
            "--disable-features=Translate,TranslateUI",
        ]
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        try:
            self.kiosk_process = subprocess.Popen(args, cwd=str(APP_DIR), creationflags=creationflags)
            self.set_status("Kiosk started")
            self.update_kiosk_controls()
        except Exception as error:
            messagebox.showerror("Start failed", str(error))
            self.set_status("Start failed")

    def stop_kiosk(self, confirm_action: bool = True) -> None:
        if not self.kiosk_running:
            self.update_kiosk_controls()
            return
        if confirm_action and not self.confirm("Stop the kiosk browser?"):
            return
        if self.kiosk_process is None:
            self.set_status("No kiosk process running")
            self.update_kiosk_controls()
            return
        if self.kiosk_process.poll() is None:
            subprocess.run(
                ["taskkill", "/PID", str(self.kiosk_process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        self.kiosk_process = None
        self.set_status("Kiosk stopped")
        self.update_kiosk_controls()

    def clear_form_confirmed(self) -> None:
        if not self.confirm("Clear the current form fields?"):
            return
        self.clear_form()
        self.set_status("Form cleared")

    def on_close(self) -> None:
        self.stop_kiosk()
        self.destroy()


if __name__ == "__main__":
    enable_windows_dpi_awareness()
    app = KioskManager()
    app.mainloop()