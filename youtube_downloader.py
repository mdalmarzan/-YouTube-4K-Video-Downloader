#!/usr/bin/env python3

"""
YouTube Downloader Pro - Modernized Layout
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import queue
import time
import shutil

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

# --- Helpers ---

def find_ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")

def find_aria2c():
    return shutil.which("aria2c")

# --- App ---

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Downloader Pro")
        self.root.geometry("650x450")
        self.root.configure(bg="#1e1e2e")

        self.style = ttk.Style()
        self.configure_styles()

        self.q = queue.Queue()
        self.ffmpeg_path = find_ffmpeg()
        self.aria2c_path = find_aria2c()
        self.out_dir = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Downloads"))

        self.ui()
        self.poll()

        if yt_dlp is None:
            messagebox.showerror("Error", "yt-dlp is not installed. Please run 'pip install yt-dlp'.")

    def configure_styles(self):
        self.style.theme_use("clam")
        # Modern Dark Theme Palette
        bg = "#1e1e2e"
        fg = "#f5f5f5"
        entry_bg = "#2b2b3d"
        btn_bg = "#7c3aed"

        self.style.configure("TFrame", background=bg)
        self.style.configure("TLabel", background=bg, foreground=fg, font=("Segoe UI", 10))
        self.style.configure("TButton", background="#3d3d55", foreground="white", font=("Segoe UI", 10), borderwidth=0, padding=5)
        self.style.configure("TCombobox", fieldbackground=entry_bg, background=entry_bg, borderwidth=0)
        self.style.configure("TProgressbar", thickness=15, troughcolor="#2b2b3d", background=btn_bg)

    def ui(self):
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill="both", expand=True)

        ttk.Label(main_frame, text="YouTube Downloader Pro", font=("Segoe UI", 20, "bold")).pack(pady=(0, 20))

        # Grid layout for inputs
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill="x", pady=5)
        input_frame.columnconfigure(1, weight=1)

        # URL
        ttk.Label(input_frame, text="Video URL:").grid(row=0, column=0, sticky="w", pady=5)
        self.url_var = tk.StringVar()
        entry_url = tk.Entry(input_frame, textvariable=self.url_var, font=("Segoe UI", 11), bg="#2b2b3d", fg="white", insertbackground="white", relief="flat")
        entry_url.grid(row=0, column=1, sticky="ew", padx=10, pady=5, ipady=5)
        tk.Button(input_frame, text="Paste", command=self._paste, bg="#3d3d55", fg="white", relief="flat", padx=10).grid(row=0, column=2, pady=5)

        # Folder
        ttk.Label(input_frame, text="Save To:").grid(row=1, column=0, sticky="w", pady=5)
        entry_dir = tk.Entry(input_frame, textvariable=self.out_dir, font=("Segoe UI", 11), bg="#2b2b3d", fg="white", relief="flat")
        entry_dir.grid(row=1, column=1, sticky="ew", padx=10, pady=5, ipady=5)
        tk.Button(input_frame, text="Browse", command=self._browse, bg="#3d3d55", fg="white", relief="flat", padx=10).grid(row=1, column=2, pady=5)

        # Quality
        ttk.Label(input_frame, text="Quality:").grid(row=2, column=0, sticky="w", pady=5)
        self.q_var = ttk.Combobox(input_frame, values=["4K (2160p)", "2K (1440p)", "HD (1080p)", "MP3 Audio"], state="readonly", font=("Segoe UI", 11))
        self.q_var.set("HD (1080p)")
        self.q_var.grid(row=2, column=1, columnspan=2, sticky="ew", padx=10, pady=5)

        # Download Button
        self.btn = tk.Button(main_frame, text="Download", command=self._start, bg="#7c3aed", fg="white", font=("Segoe UI", 12, "bold"), relief="flat", pady=10)
        self.btn.pack(fill="x", pady=20)

        # Progress
        self.bar = ttk.Progressbar(main_frame, orient="horizontal", mode="determinate")
        self.bar.pack(fill="x", pady=5)

        self.status = tk.StringVar(value="Ready")
        ttk.Label(main_frame, textvariable=self.status, font=("Consolas", 9), foreground="#a6adc8").pack(anchor="w")

    def _paste(self):
        try: self.url_var.set(self.root.clipboard_get().strip())
        except tk.TclError: pass

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self.out_dir.get())
        if d: self.out_dir.set(d)

    def _start(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Warning", "Please provide a URL.")
            return

        self.btn.config(state="disabled", text="Downloading...")
        self.status.set("Starting...")
        threading.Thread(target=self._run_download, args=(url,), daemon=True).start()

    def _run_download(self, url):
        q_map = {"4K (2160p)": 2160, "2K (1440p)": 1440, "HD (1080p)": 1080}
        height = q_map.get(self.q_var.get())
        is_mp3 = self.q_var.get() == "MP3 Audio"

        job = DownloadJob(url, self.out_dir.get(), height, is_mp3, self.ffmpeg_path, self.aria2c_path, self.q)
        job.run()

    def poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "bar": self.bar["value"] = val
                elif kind == "status": self.status.set(val)
                elif kind == "error":
                    self.btn.config(state="normal", text="Download")
                    messagebox.showerror("Error", val)
                elif kind == "done":
                    self.btn.config(state="normal", text="Download")
                    messagebox.showinfo("Done", val)
        except queue.Empty:
            pass
        self.root.after(120, self.poll)

class DownloadJob:
    def __init__(self, url, out, height, is_mp3, ffmpeg, aria2c, queue):
        self.url = url
        self.out = out
        self.height = height
        self.is_mp3 = is_mp3
        self.ffmpeg = ffmpeg
        self.aria2c = aria2c
        self.queue = queue
        self.last_update = 0

    def run(self):
        if not self.is_mp3 and not self.ffmpeg:
            self.queue.put(("error", "FFmpeg is required for video merging. Please install it."))
            return

        opts = {
            "ffmpeg_location": self.ffmpeg,
            "outtmpl": os.path.join(self.out, "%(title)s.%(ext)s"),
            "quiet": True,
            "concurrent_fragment_downloads": 16,
            "http_chunk_size": 10 * 1024 * 1024,
            "extractor_args": {'youtube': {'player_client': ['android', 'ios']}}
        }

        if self.is_mp3:
            opts.update({
                "format": "bestaudio/best",
                "postprocessors": [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '320'}]
            })
        else:
            opts.update({
                "format": f"bestvideo[height<={self.height}]+bestaudio/best[height<={self.height}]/best",
                "merge_output_format": "mkv",
                "postprocessor_args": {"merger": ["-c", "copy"]}
            })

        if self.aria2c:
            opts.update({
                "external_downloader": "aria2c",
                "external_downloader_args": {"aria2c": ["-x16", "-s16", "-k1M"]}
            })

        def hook(d):
            if d.get("status") == "downloading":
                now = time.time()
                if now - self.last_update < 0.25: return
                self.last_update = now

                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                got = d.get("downloaded_bytes", 0)
                pct = (got / total * 100) if total else 0.0
                self.queue.put(("bar", pct))
                self.queue.put(("status", f"{pct:.1f}% | {d.get('_speed_str', '')}"))

        opts["progress_hooks"] = [hook]

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.extract_info(self.url, download=True)
            self.queue.put(("done", "Download Finished Successfully!"))
        except Exception as e:
            self.queue.put(("error", str(e)))

if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
