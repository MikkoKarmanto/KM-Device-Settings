import threading
import queue
import csv
import os
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import ipaddress

from pythonping import ping

import api as API


class Logger:
    """Simple logger that writes to a Tk Text widget and stdout."""
    def __init__(self, text_widget: tk.Text):
        self.text_widget = text_widget
        self._lock = threading.Lock()

    def write(self, msg: str):
        with self._lock:
            ts = time.strftime('%H:%M:%S')
            line = f"[{ts}] {msg}\n" if not msg.endswith("\n") else f"[{ts}] {msg}"
            self.text_widget.configure(state=tk.NORMAL)
            self.text_widget.insert(tk.END, line)
            self.text_widget.see(tk.END)
            self.text_widget.configure(state=tk.DISABLED)
        print(msg, end="" if msg.endswith("\n") else "\n")


def ping_check_success(host: str) -> bool:
    try:
        response = ping(host, count=2, timeout=1)
        for res in response._responses:
            if res.success:
                return True
        return False
    except Exception:
        return False


class DeviceManagerGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("KM Device Settings")
        icon_path = os.path.join(os.path.dirname(__file__), "Settings_icon.png")
        try:
            if os.path.exists(icon_path):
                self.root.iconphoto(True, tk.PhotoImage(file=icon_path))
        except Exception:
            pass

        # State
        self.stop_event = threading.Event()
        self.worker_thread: threading.Thread | None = None
        self.log_queue: queue.Queue[str] = queue.Queue()

        # UI
        main = ttk.Frame(self.root, padding=10)
        main.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        input_frame = ttk.LabelFrame(main, text="Add device")
        input_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 10))
        input_frame.columnconfigure(3, weight=1)

        ttk.Label(input_frame, text="IP address").grid(row=0, column=0, padx=(10, 6), pady=6, sticky="w")
        self.ip_entry = ttk.Entry(input_frame, width=20)
        self.ip_entry.grid(row=0, column=1, padx=(0, 12), pady=6, sticky="w")

        ttk.Label(input_frame, text="Admin password").grid(row=0, column=2, padx=(0, 6), pady=6, sticky="w")
        self.pw_entry = ttk.Entry(input_frame, width=24, show="*")
        self.pw_entry.grid(row=0, column=3, padx=(0, 12), pady=6, sticky="ew")

        self.add_btn = ttk.Button(input_frame, text="Add", command=self.add_device_row)
        self.add_btn.grid(row=0, column=4, padx=(0, 10), pady=6)

        opts_frame = ttk.Frame(main)
        opts_frame.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        self.disable_var = tk.BooleanVar(value=False)
        self.disable_chk = ttk.Checkbutton(opts_frame, text="Disable default application", variable=self.disable_var)
        self.disable_chk.pack(side=tk.LEFT)

        # Devices table
        table_frame = ttk.LabelFrame(main, text="Devices")
        table_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 6))
        main.rowconfigure(2, weight=1)

        columns = ("ip", "password", "status")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=10)
        self.tree.heading("ip", text="IP address")
        self.tree.heading("password", text="Password")
        self.tree.heading("status", text="Status")
        self.tree.column("ip", width=140, anchor=tk.W)
        self.tree.column("password", width=160, anchor=tk.W)
        self.tree.column("status", width=260, anchor=tk.W)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        # Action buttons
        btns = ttk.Frame(main)
        btns.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        self.import_btn = ttk.Button(btns, text="Import CSV…", command=self.import_csv)
        self.import_btn.pack(side=tk.LEFT)
        self.remove_btn = ttk.Button(btns, text="Remove selected", command=self.remove_selected)
        self.remove_btn.pack(side=tk.LEFT, padx=(6, 0))
        self.clear_btn = ttk.Button(btns, text="Clear", command=self.clear_all)
        self.clear_btn.pack(side=tk.LEFT, padx=(6, 0))
        self.start_btn = ttk.Button(btns, text="Start", command=self.start_processing)
        self.start_btn.pack(side=tk.RIGHT)
        self.cancel_btn = ttk.Button(btns, text="Cancel", command=self.cancel_processing, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.RIGHT, padx=(0, 6))

        # Progress
        prog_frame = ttk.Frame(main)
        prog_frame.grid(row=4, column=0, sticky="ew", pady=(0, 6))
        self.progress = ttk.Progressbar(prog_frame, mode="determinate")
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.progress_label = ttk.Label(prog_frame, text="0/0")
        self.progress_label.pack(side=tk.LEFT, padx=(6, 0))

        # Log output
        log_frame = ttk.LabelFrame(main, text="Log")
        log_frame.grid(row=5, column=0, sticky="nsew")
        main.rowconfigure(5, weight=1)
        self.log_text = tk.Text(log_frame, height=10, wrap="word", state=tk.DISABLED)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        lsb = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=lsb.set)
        lsb.grid(row=0, column=1, sticky="ns")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.logger = Logger(self.log_text)

        # periodic UI updater for queued logs (if needed later)
        self.root.after(200, self._drain_log_queue)

    # Helpers
    def _existing_ips(self) -> set[str]:
        return {self.tree.item(i, "values")[0] for i in self.tree.get_children()}

    @staticmethod
    def _normalize_ip(ip: str) -> str:
        ip = (ip or "").strip()
        if ip.lower().startswith("http://"):
            ip = ip[7:]
        elif ip.lower().startswith("https://"):
            ip = ip[8:]
        return ip.strip("/ ")

    @staticmethod
    def _is_valid_ipv4(ip: str) -> bool:
        try:
            ipaddress.IPv4Address(ip)
            return True
        except Exception:
            return False

    def _set_controls_state(self, running: bool):
        # Disable/enable inputs while running
        state_disable = tk.DISABLED if running else tk.NORMAL
        state_enable = tk.NORMAL if running else tk.DISABLED
        self.ip_entry.configure(state=state_disable)
        self.pw_entry.configure(state=state_disable)
        self.add_btn.configure(state=state_disable)
        self.disable_chk.configure(state=state_disable)
        self.import_btn.configure(state=state_disable)
        self.remove_btn.configure(state=state_disable)
        self.clear_btn.configure(state=state_disable)
        self.start_btn.configure(state=state_disable)
        self.cancel_btn.configure(state=state_enable)

    def _init_progress(self, total: int):
        total = max(0, int(total))
        self.progress.configure(maximum=total, value=0)
        self.progress_label.configure(text=f"0/{total}")

    def _advance_progress(self):
        def _apply():
            val = min(self.progress["value"] + 1, self.progress["maximum"])
            self.progress.configure(value=val)
            self.progress_label.configure(text=f"{int(val)}/{int(self.progress['maximum'])}")
        self.root.after(0, _apply)

    def _finish_progress(self, cancelled: bool = False):
        def _apply():
            if cancelled:
                # Keep current value; just mark as cancelled
                self.progress_label.configure(text=f"Cancelled {int(self.progress['value'])}/{int(self.progress['maximum'])}")
            else:
                self.progress.configure(value=self.progress["maximum"])
                self.progress_label.configure(text=f"{int(self.progress['maximum'])}/{int(self.progress['maximum'])}")
            self._set_controls_state(False)
        self.root.after(0, _apply)

    # UI actions
    def add_device_row(self):
        ip = self._normalize_ip(self.ip_entry.get())
        pw = self.pw_entry.get().strip()
        if not ip or not pw:
            messagebox.showwarning("Missing data", "Please provide both IP address and admin password.")
            return
        if not self._is_valid_ipv4(ip):
            messagebox.showerror("Invalid IP", f"'{ip}' is not a valid IPv4 address.")
            return
        if ip in self._existing_ips():
            messagebox.showinfo("Duplicate", f"{ip} is already in the list.")
            return
        self.tree.insert("", tk.END, values=(ip, pw, ""))
        self.ip_entry.delete(0, tk.END)
        self.pw_entry.delete(0, tk.END)

    def import_csv(self):
        path = filedialog.askopenfilename(title="Select CSV file", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                required = {"ipaddress", "password"}
                if not required.issubset({h.strip().lower() for h in reader.fieldnames or []}):
                    messagebox.showerror(
                        "Invalid CSV",
                        "CSV must have headers: ipaddress,password",
                    )
                    return
                added = 0
                invalid = 0
                duplicates = 0
                existing = self._existing_ips()
                for row in reader:
                    ip = self._normalize_ip(row.get("ipaddress") or "")
                    pw = (row.get("password") or "").strip()
                    if not ip or not pw or not self._is_valid_ipv4(ip):
                        invalid += 1
                        continue
                    if ip in existing:
                        duplicates += 1
                        continue
                    self.tree.insert("", tk.END, values=(ip, pw, ""))
                    existing.add(ip)
                    added += 1
                messagebox.showinfo("Import complete", f"Imported: {added}\nInvalid: {invalid}\nDuplicates skipped: {duplicates}")
        except Exception as ex:
            messagebox.showerror("Error reading CSV", str(ex))

    def remove_selected(self):
        for item in self.tree.selection():
            self.tree.delete(item)

    def clear_all(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

    def start_processing(self):
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo("Busy", "Processing is already running.")
            return
        items = self.tree.get_children()
        if not items:
            messagebox.showwarning("No devices", "Add devices or import a CSV first.")
            return
        self.stop_event.clear()
        devices = [self.tree.item(i, "values")[:2] for i in items]  # (ip, pw)
        disable = self.disable_var.get()
        self._init_progress(len(devices))
        self._set_controls_state(True)
        self.worker_thread = threading.Thread(target=self._process_devices, args=(devices, disable), daemon=True)
        self.worker_thread.start()

    def cancel_processing(self):
        if self.worker_thread and self.worker_thread.is_alive():
            self.stop_event.set()
            self.logger.write("Cancellation requested. Stopping after current device…")

    # Background work
    def _process_devices(self, devices: list[tuple[str, str]], disable: bool):
        outfile = "status.csv"
        # Ensure header exists if creating new file
        need_header = not os.path.isfile(outfile) or os.path.getsize(outfile) == 0
        try:
            with open(outfile, "a", newline="", encoding="utf-8") as out:
                writer = csv.writer(out)
                if need_header:
                    writer.writerow(["ipaddress", "status", "disable_Default_Application"])
                for idx, (ip, pw) in enumerate(devices, start=1):
                    if self.stop_event.is_set():
                        self._update_row_status(idx - 1, "Cancelled")
                        break
                    self.logger.write(f"Checking {ip}…")
                    self._update_row_status(idx - 1, "Pinging…")
                    reachable = ping_check_success(ip)
                    if not reachable:
                        msg = "Not reachable"
                        self.logger.write(f"Error: {ip} is not reachable. Please check the connection.")
                        writer.writerow([ip, False, disable])
                        self._update_row_status(idx - 1, msg)
                        self._advance_progress()
                        continue
                    try:
                        action = "Disabling" if disable else "Enabling"
                        self._update_row_status(idx - 1, f"{action} default app…")
                        status = API.set_settings(pw, f"http://{ip}", disable)
                        status_bool = bool(status)
                        writer.writerow([ip, status_bool, disable])
                        result_msg = "Success" if status_bool else ("Failed" if status is False else "Error")
                        self._update_row_status(idx - 1, result_msg)
                        self._advance_progress()
                    except Exception as ex:
                        writer.writerow([ip, False, disable])
                        self._update_row_status(idx - 1, f"Error: {ex}")
                        self.logger.write(f"An error occurred: {ex}")
                        self._advance_progress()
        except Exception as ex:
            self.logger.write(f"Failed writing status.csv: {ex}")
        finally:
            cancelled = self.stop_event.is_set()
            self.logger.write("Processing finished." if not cancelled else "Processing cancelled.")
            self._finish_progress(cancelled=cancelled)

    def _update_row_status(self, row_index: int, status: str):
        # must run on UI thread
        def _apply():
            items = self.tree.get_children()
            if 0 <= row_index < len(items):
                iid = items[row_index]
                ip, pw, _ = self.tree.item(iid, "values")
                self.tree.item(iid, values=(ip, pw, status))
        self.root.after(0, _apply)

    def _drain_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.logger.write(msg)
        except queue.Empty:
            pass
        self.root.after(200, self._drain_log_queue)


def main():
    root = tk.Tk()
    # Use modern ttk theme if available
    try:
        if "vista" in ttk.Style().theme_names():
            ttk.Style().theme_use("vista")
    except Exception:
        pass
    app = DeviceManagerGUI(root)
    root.minsize(720, 520)
    root.mainloop()


if __name__ == "__main__":
    main()
