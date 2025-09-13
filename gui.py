import threading
import queue
import csv
import os
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import ipaddress

from utils import Logger, ping_check_success
import api as API


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

        # Options state (defaults mirror API defaults)
        self.options = {
            "SslPortNo": "50003",
            "Proxy": {"ServerAddress": "", "PortNo": "8080", "SslPortNo": "8080", "FtpPortNo": "21", "UserName": ""},
            "VerificationStrength": {
                "Client": "Off",
                "ExpirationDate": "Off",
                "CN": "Off",
                "KeyDirections": "Off",
                "Chain": "Off",
                "LapseConfirmation": "Off",
            },
            "HTTPVersionSetting": "HttpV2n1",
            "OpenApiEnable": "OnWithoutPassword",
            "ExtApplicationLink": "On",
            "SpecifiedAppMode": {"StartUpApplication": "3", "MfpBasicFunction": "On"},
        }

        # UI
        notebook = ttk.Notebook(self.root)
        notebook.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        # Device Management tab
        tab1 = ttk.Frame(notebook, padding=10)
        notebook.add(tab1, text="Device Management")

        # Options tab
        tab2 = ttk.Frame(notebook, padding=10)
        notebook.add(tab2, text="Options")

        # Device Management widgets
        input_frame = ttk.LabelFrame(tab1, text="Add device")
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

        # Devices table
        table_frame = ttk.LabelFrame(tab1, text="Devices")
        table_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 6))
        tab1.rowconfigure(1, weight=1)

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
        btns = ttk.Frame(tab1)
        btns.grid(row=2, column=0, sticky="ew", pady=(0, 6))
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
        prog_frame = ttk.Frame(tab1)
        prog_frame.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        self.progress = ttk.Progressbar(prog_frame, mode="determinate")
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.progress_label = ttk.Label(prog_frame, text="0/0")
        self.progress_label.pack(side=tk.LEFT, padx=(6, 0))

        # Log output
        log_frame = ttk.LabelFrame(tab1, text="Log")
        log_frame.grid(row=4, column=0, sticky="nsew")
        tab1.rowconfigure(4, weight=1)
        self.log_text = tk.Text(log_frame, height=10, wrap="word", state=tk.DISABLED)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        lsb = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=lsb.set)
        lsb.grid(row=0, column=1, sticky="ns")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.logger = Logger(self.log_text)

        # Options tab widgets
        opts_frame = ttk.Frame(tab2)
        opts_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 10))
        self.mode_var = tk.StringVar(value="enable")
        self.enable_radio = ttk.Radiobutton(opts_frame, text="Enable default application", variable=self.mode_var, value="enable")
        self.disable_radio = ttk.Radiobutton(opts_frame, text="Disable default application", variable=self.mode_var, value="disable")
        self.enable_radio.pack(side=tk.LEFT)
        self.disable_radio.pack(side=tk.LEFT, padx=(12, 0))

        self.options_frame = ttk.LabelFrame(tab2, text="Options", padding=10)
        self.options_frame.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        # Options widgets
        self.opt_openapi_enable = tk.StringVar(value=self.options.get("OpenApiEnable", "OnWithoutPassword"))
        ttk.Label(self.options_frame, text="OpenApiEnable").grid(row=0, column=0, sticky="w")
        openapi_enable = ttk.Combobox(self.options_frame, textvariable=self.opt_openapi_enable, values=["Off", "On", "OnWithoutPassword"], state="readonly", width=22)
        openapi_enable.grid(row=0, column=1, sticky="w", pady=4)

        self.opt_http_version = tk.StringVar(value=self.options.get("HTTPVersionSetting", "HttpV2n1"))
        ttk.Label(self.options_frame, text="HTTPVersionSetting").grid(row=1, column=0, sticky="w")
        http_combo = ttk.Combobox(self.options_frame, textvariable=self.opt_http_version, values=["HttpV2n1", "HttpV1"], state="readonly", width=22)
        http_combo.grid(row=1, column=1, sticky="w", pady=4)

        self.opt_ssl_port = tk.StringVar(value=self.options.get("SslPortNo", "50003"))
        ttk.Label(self.options_frame, text="SslPortNo").grid(row=2, column=0, sticky="w")
        ttk.Entry(self.options_frame, textvariable=self.opt_ssl_port, width=25).grid(row=2, column=1, sticky="w", pady=4)

        self.opt_ext_app_link = tk.StringVar(value=self.options.get("ExtApplicationLink", "On"))
        ttk.Checkbutton(self.options_frame, text="ExtApplicationLink", variable=self.opt_ext_app_link, onvalue="On", offvalue="Off").grid(row=3, column=0, columnspan=2, sticky="w", pady=2)

        self.opt_startup_app = tk.StringVar(value=self.options.get("SpecifiedAppMode", {}).get("StartUpApplication", "3"))
        ttk.Label(self.options_frame, text="StartUpApplication").grid(row=4, column=0, sticky="w")
        ttk.Entry(self.options_frame, textvariable=self.opt_startup_app, width=25).grid(row=4, column=1, sticky="w", pady=4)

        self.opt_mfp_basic = tk.StringVar(value=self.options.get("SpecifiedAppMode", {}).get("MfpBasicFunction", "On"))
        ttk.Checkbutton(self.options_frame, text="MfpBasicFunction", variable=self.opt_mfp_basic, onvalue="On", offvalue="Off").grid(row=5, column=0, columnspan=2, sticky="w", pady=2)

        # Proxy sub-frame
        proxy_frame = ttk.LabelFrame(self.options_frame, text="Proxy", padding=6)
        proxy_frame.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(6, 2))
        for c in range(2):
            proxy_frame.columnconfigure(c, weight=1)
        proxy = self.options.get("Proxy", {})
        self.opt_proxy_server = tk.StringVar(value=proxy.get("ServerAddress", ""))
        self.opt_proxy_port = tk.StringVar(value=proxy.get("PortNo", "8080"))
        self.opt_proxy_ssl = tk.StringVar(value=proxy.get("SslPortNo", "8080"))
        self.opt_proxy_ftp = tk.StringVar(value=proxy.get("FtpPortNo", "21"))
        self.opt_proxy_user = tk.StringVar(value=proxy.get("UserName", ""))
        ttk.Label(proxy_frame, text="ServerAddress").grid(row=0, column=0, sticky="w")
        ttk.Entry(proxy_frame, textvariable=self.opt_proxy_server, width=25).grid(row=0, column=1, sticky="ew", pady=2)
        ttk.Label(proxy_frame, text="PortNo").grid(row=1, column=0, sticky="w")
        ttk.Entry(proxy_frame, textvariable=self.opt_proxy_port, width=25).grid(row=1, column=1, sticky="ew", pady=2)
        ttk.Label(proxy_frame, text="SslPortNo").grid(row=2, column=0, sticky="w")
        ttk.Entry(proxy_frame, textvariable=self.opt_proxy_ssl, width=25).grid(row=2, column=1, sticky="ew", pady=2)
        ttk.Label(proxy_frame, text="FtpPortNo").grid(row=3, column=0, sticky="w")
        ttk.Entry(proxy_frame, textvariable=self.opt_proxy_ftp, width=25).grid(row=3, column=1, sticky="ew", pady=2)
        ttk.Label(proxy_frame, text="UserName").grid(row=4, column=0, sticky="w")
        ttk.Entry(proxy_frame, textvariable=self.opt_proxy_user, width=25).grid(row=4, column=1, sticky="ew", pady=2)

        # VerificationStrength sub-frame
        ver_frame = ttk.LabelFrame(self.options_frame, text="VerificationStrength", padding=6)
        ver_frame.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(6, 2))
        ver = self.options.get("VerificationStrength", {})
        self.opt_vs_client = tk.StringVar(value=ver.get("Client", "Off"))
        self.opt_vs_exp = tk.StringVar(value=ver.get("ExpirationDate", "Off"))
        self.opt_vs_cn = tk.StringVar(value=ver.get("CN", "Off"))
        self.opt_vs_keydir = tk.StringVar(value=ver.get("KeyDirections", "Off"))
        self.opt_vs_chain = tk.StringVar(value=ver.get("Chain", "Off"))
        self.opt_vs_lapse = tk.StringVar(value=ver.get("LapseConfirmation", "Off"))
        ttk.Checkbutton(ver_frame, text="Client", variable=self.opt_vs_client, onvalue="On", offvalue="Off").grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(ver_frame, text="ExpirationDate", variable=self.opt_vs_exp, onvalue="On", offvalue="Off").grid(row=0, column=1, sticky="w")
        ttk.Checkbutton(ver_frame, text="CN", variable=self.opt_vs_cn, onvalue="On", offvalue="Off").grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(ver_frame, text="KeyDirections", variable=self.opt_vs_keydir, onvalue="On", offvalue="Off").grid(row=1, column=1, sticky="w")
        ttk.Checkbutton(ver_frame, text="Chain", variable=self.opt_vs_chain, onvalue="On", offvalue="Off").grid(row=2, column=0, sticky="w")
        ttk.Checkbutton(ver_frame, text="LapseConfirmation", variable=self.opt_vs_lapse, onvalue="On", offvalue="Off").grid(row=2, column=1, sticky="w")

        # Save button
        ttk.Button(self.options_frame, text="Save Options", command=self.save_options).grid(row=8, column=0, columnspan=2, pady=(10, 0))

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
        self.enable_radio.configure(state=state_disable)
        self.disable_radio.configure(state=state_disable)
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
        disable = self.mode_var.get() == "disable"
        self.save_options()  # Save current options
        self._init_progress(len(devices))
        self._set_controls_state(True)
        # pass a snapshot of options to avoid mutation while running
        opts = json.loads(json.dumps(self.options))
        self.worker_thread = threading.Thread(target=self._process_devices, args=(devices, disable, opts), daemon=True)
        self.worker_thread.start()

    def cancel_processing(self):
        if self.worker_thread and self.worker_thread.is_alive():
            self.stop_event.set()
            self.logger.write("Cancellation requested. Stopping after current device…")

    # Background work
    def _process_devices(self, devices: list[tuple[str, str]], disable: bool, options: dict):
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
                        status = API.set_settings(pw, f"http://{ip}", disable, options=options)
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

    def save_options(self):
        self.options = {
            "SslPortNo": self.opt_ssl_port.get().strip() or "50003",
            "Proxy": {
                "ServerAddress": self.opt_proxy_server.get().strip(),
                "PortNo": self.opt_proxy_port.get().strip() or "8080",
                "SslPortNo": self.opt_proxy_ssl.get().strip() or "8080",
                "FtpPortNo": self.opt_proxy_ftp.get().strip() or "21",
                "UserName": self.opt_proxy_user.get().strip(),
            },
            "VerificationStrength": {
                "Client": self.opt_vs_client.get(),
                "ExpirationDate": self.opt_vs_exp.get(),
                "CN": self.opt_vs_cn.get(),
                "KeyDirections": self.opt_vs_keydir.get(),
                "Chain": self.opt_vs_chain.get(),
                "LapseConfirmation": self.opt_vs_lapse.get(),
            },
            "HTTPVersionSetting": self.opt_http_version.get(),
            "OpenApiEnable": self.opt_openapi_enable.get(),
            "ExtApplicationLink": self.opt_ext_app_link.get(),
            "SpecifiedAppMode": {
                "StartUpApplication": self.opt_startup_app.get().strip() or "3",
                "MfpBasicFunction": self.opt_mfp_basic.get(),
            },
        }


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