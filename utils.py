import threading
import time
import tkinter as tk
from pythonping import ping


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
    """
    Ping given IP address. try twice and 1s timeout.

    @params:
        host   - Required  : IP address of the device (Str)

    @return:
        boolean            : True if response received otherwise false.
    """
    try:
        response = ping(host, count=2, timeout=1)
        for res in response._responses:
            if res.success:
                return True
        return False
    except Exception as e:
        print(f"Error occurred while pinging {host}: {str(e)}")
        return False