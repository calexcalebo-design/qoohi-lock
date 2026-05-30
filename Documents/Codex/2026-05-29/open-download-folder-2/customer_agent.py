import json
import sys
import tkinter as tk
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen


SERVER_URL = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8080"
COMPUTER_ID = sys.argv[2] if len(sys.argv) > 2 else "1"
COMPUTER_TOKEN = sys.argv[3] if len(sys.argv) > 3 else ""
POLL_SECONDS = 1
TIMER_WIDTH = 560
TIMER_HEIGHT = 86


def format_time(seconds):
    seconds = max(0, int(seconds or 0))
    minutes, remaining = divmod(seconds, 60)
    return f"{minutes:02d}:{remaining:02d}"


class CustomerAgent:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("QOOHI")
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        self.root.bind("<Alt-F4>", lambda event: "break")
        self.root.bind("<Escape>", lambda event: "break")
        self.locked_mode = None

        self.name = tk.Label(self.root, text="Customer PC", fg="#f4d9d9", bg="#250d0d", font=("Arial", 20, "bold"))
        self.name.pack(pady=(80, 10))
        self.state = tk.Label(self.root, text="Locked", fg="white", bg="#250d0d", font=("Arial", 58, "bold"))
        self.state.pack(pady=10)
        self.time_left = tk.Label(self.root, text="00:00", fg="white", bg="#250d0d", font=("Arial", 96, "bold"))
        self.time_left.pack(pady=10)
        self.message = tk.Label(
            self.root,
            text="Please pay at the counter to start a session.",
            fg="#f4d9d9",
            bg="#250d0d",
            font=("Arial", 20),
            wraplength=900,
            justify="center",
        )
        self.message.pack(pady=20)
        self.connection = tk.Label(
            self.root,
            text="",
            fg="#d8b4fe",
            bg="#250d0d",
            font=("Arial", 12),
            wraplength=900,
            justify="center",
        )
        self.connection.pack(pady=8)

    def set_locked_layout(self):
        if self.locked_mode is True:
            self.root.lift()
            self.root.focus_force()
            return
        self.locked_mode = True
        self.root.maxsize(self.root.winfo_screenwidth() * 2, self.root.winfo_screenheight() * 2)
        self.root.minsize(0, 0)
        self.root.deiconify()
        self.root.state("normal")
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#250d0d")
        self.name.config(fg="#f4d9d9", bg="#250d0d", font=("Arial", 20, "bold"))
        self.state.config(fg="white", bg="#250d0d", font=("Arial", 58, "bold"))
        self.time_left.config(fg="white", bg="#250d0d", font=("Arial", 96, "bold"))
        self.message.config(fg="#f4d9d9", bg="#250d0d", font=("Arial", 20), wraplength=900)
        self.connection.config(fg="#d8b4fe", bg="#250d0d", font=("Arial", 12), wraplength=900)
        self.name.pack_configure(pady=(80, 10))
        self.state.pack_configure(pady=10)
        self.time_left.pack_configure(pady=10)
        self.message.pack_configure(pady=20)
        self.connection.pack_configure(pady=8)
        self.root.lift()
        self.root.focus_force()

    def set_timer_bar_layout(self):
        if self.locked_mode is False:
            self.root.lift()
            return
        self.locked_mode = False
        self.root.deiconify()
        self.root.attributes("-fullscreen", False)
        self.root.state("normal")
        self.root.update_idletasks()
        self.root.attributes("-topmost", True)
        self.root.geometry(f"{TIMER_WIDTH}x{TIMER_HEIGHT}+0+0")
        self.root.minsize(TIMER_WIDTH, TIMER_HEIGHT)
        self.root.maxsize(TIMER_WIDTH, TIMER_HEIGHT)
        self.root.configure(bg="#020409")
        self.name.config(fg="#94a3b8", bg="#020409", font=("Arial", 11, "bold"))
        self.state.config(fg="#13c8a3", bg="#020409", font=("Arial", 10, "bold"))
        self.time_left.config(fg="#13c8a3", bg="#020409", font=("Arial", 28, "bold"))
        self.message.config(fg="#f7fbff", bg="#020409", font=("Arial", 9), wraplength=500)
        self.connection.config(fg="#64748b", bg="#020409", font=("Arial", 8), wraplength=540)
        self.name.pack_configure(pady=(4, 0))
        self.state.pack_configure(pady=0)
        self.time_left.pack_configure(pady=0)
        self.message.pack_configure(pady=0)
        self.connection.pack_configure(pady=0)
        self.root.lift()

    def fetch_status(self):
        url = f"{SERVER_URL}/api/computers/{COMPUTER_ID}"
        if COMPUTER_TOKEN:
            url += f"?token={COMPUTER_TOKEN}"
        
        # Cloud services like Render prefer a User-Agent; increased timeout for cold starts
        req = Request(url, headers={'User-Agent': 'QOOHI-Agent/1.0'})
        with urlopen(req, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))

    def show_locked(self, data=None, offline=False, error=""):
        if offline:
            message = "Connecting to cloud... (Render may take 30s to wake up)"
        else:
            message = (data or {}).get("message") or "Time is finished. Ask the operator to add time."
            
        self.set_locked_layout()
        self.name.config(text=(data or {}).get("name", "Customer PC"))
        self.state.config(text="Locked")
        self.time_left.config(text=format_time((data or {}).get("remaining_seconds", 0)))
        self.message.config(text=message)
        details = f"Server: {SERVER_URL}   PC ID: {COMPUTER_ID}"
        if data:
            details += f"   Status: {data.get('status', 'unknown')}"
        if error:
            details += f"   Error: {error}"
        self.connection.config(text=details)

    def show_active(self, data):
        self.set_timer_bar_layout()
        self.name.config(text=data.get("name", "Customer PC"))
        self.state.config(text="Session active")
        self.time_left.config(text=format_time(data.get("remaining_seconds", 0)))
        msg = data.get("message") or "Timer is running. This window stays on top."
        self.message.config(text=msg)
        self.connection.config(text=f"Server: {SERVER_URL}   PC ID: {COMPUTER_ID}")

    def tick(self):
        try:
            data = self.fetch_status()
            if data.get("status") == "active":
                self.show_active(data)
            else:
                self.show_locked(data)
        except HTTPError as exc:
            if exc.code == 404:
                self.show_locked(error=f"PC ID {COMPUTER_ID} not found on server. Add it in Admin.")
            elif exc.code == 403:
                self.show_locked(error="Invalid PC Token. Get the new token from Admin.")
            else:
                self.show_locked(offline=True, error=f"HTTP Error {exc.code}")
        except (URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            self.show_locked(offline=True, error=str(exc)[:120])
        self.root.after(POLL_SECONDS * 1000, self.tick)

    def run(self):
        self.tick()
        self.root.mainloop()


if __name__ == "__main__":
    CustomerAgent().run()
