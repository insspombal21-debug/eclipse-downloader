import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import imageio_ffmpeg
import yt_dlp

APP_NAME = "Eclipse Downloader"

class DownloaderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("760x570")
        self.minsize(700, 530)
        self.configure(bg="#10131a")
        self.events = queue.Queue()
        self.cancel_requested = False
        self.url = tk.StringVar()
        self.mode = tk.StringVar(value="Vídeo MP4")
        self.quality = tk.StringVar(value="1080p")
        self.folder = tk.StringVar(value=str(Path.home() / "Downloads"))
        self.status = tk.StringVar(value="Pronto para baixar")
        self.title_text = tk.StringVar(value="Cole um link para começar")
        self.progress = tk.DoubleVar(value=0)
        self.playlist = tk.BooleanVar(value=False)
        self._style()
        self._layout()
        self.after(100, self._poll_events)

    def _style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#10131a")
        style.configure("Card.TFrame", background="#191e29")
        style.configure("TLabel", background="#10131a", foreground="#eef2ff", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 22), foreground="#ffffff")
        style.configure("Muted.TLabel", foreground="#9da8bd")
        style.configure("Card.TLabel", background="#191e29", foreground="#eef2ff")
        style.configure("TButton", font=("Segoe UI Semibold", 10), padding=9)
        style.configure("Accent.TButton", background="#7c3aed", foreground="white", borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#8b5cf6"), ("disabled", "#414754")])
        style.configure("TEntry", fieldbackground="#0f131b", foreground="#ffffff", padding=9)
        style.configure("TCombobox", fieldbackground="#0f131b", foreground="#111827", padding=7)
        style.configure("TCheckbutton", background="#191e29", foreground="#eef2ff")
        style.configure("Horizontal.TProgressbar", troughcolor="#282f3d", background="#7c3aed")

    def _layout(self):
        outer = ttk.Frame(self, padding=28)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=APP_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Baixe somente conteúdos próprios ou com autorização.", style="Muted.TLabel").pack(anchor="w", pady=(3, 20))
        card = ttk.Frame(outer, style="Card.TFrame", padding=22)
        card.pack(fill="both", expand=True)
        ttk.Label(card, text="Link do YouTube", style="Card.TLabel").pack(anchor="w")
        url_row = ttk.Frame(card, style="Card.TFrame")
        url_row.pack(fill="x", pady=(6, 15))
        self.url_entry = ttk.Entry(url_row, textvariable=self.url)
        self.url_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(url_row, text="Colar", command=self._paste).pack(side="left", padx=(8, 0))
        ttk.Label(card, textvariable=self.title_text, style="Card.TLabel", wraplength=650).pack(anchor="w", pady=(0, 16))
        choices = ttk.Frame(card, style="Card.TFrame")
        choices.pack(fill="x")
        left = ttk.Frame(choices, style="Card.TFrame")
        left.pack(side="left", fill="x", expand=True, padx=(0, 8))
        right = ttk.Frame(choices, style="Card.TFrame")
        right.pack(side="left", fill="x", expand=True, padx=(8, 0))
        ttk.Label(left, text="Formato", style="Card.TLabel").pack(anchor="w")
        mode_box = ttk.Combobox(left, textvariable=self.mode, state="readonly", values=["Vídeo MP4", "Áudio MP3"])
        mode_box.pack(fill="x", pady=(6, 0))
        mode_box.bind("<<ComboboxSelected>>", self._mode_changed)
        ttk.Label(right, text="Qualidade máxima", style="Card.TLabel").pack(anchor="w")
        self.quality_box = ttk.Combobox(right, textvariable=self.quality, state="readonly", values=["Melhor disponível", "2160p (4K)", "1440p", "1080p", "720p", "480p", "360p"])
        self.quality_box.pack(fill="x", pady=(6, 0))
        ttk.Checkbutton(card, text="Baixar playlist inteira quando o link for de uma playlist", variable=self.playlist).pack(anchor="w", pady=14)
        ttk.Label(card, text="Salvar em", style="Card.TLabel").pack(anchor="w")
        folder_row = ttk.Frame(card, style="Card.TFrame")
        folder_row.pack(fill="x", pady=(6, 18))
        ttk.Entry(folder_row, textvariable=self.folder, state="readonly").pack(side="left", fill="x", expand=True)
        ttk.Button(folder_row, text="Escolher pasta", command=self._choose_folder).pack(side="left", padx=(8, 0))
        ttk.Progressbar(card, variable=self.progress, maximum=100).pack(fill="x", pady=(3, 8))
        ttk.Label(card, textvariable=self.status, style="Card.TLabel").pack(anchor="w")
        buttons = ttk.Frame(card, style="Card.TFrame")
        buttons.pack(fill="x", pady=(18, 0))
        self.download_btn = ttk.Button(buttons, text="BAIXAR", style="Accent.TButton", command=self._start)
        self.download_btn.pack(side="left", fill="x", expand=True)
        self.cancel_btn = ttk.Button(buttons, text="Cancelar", command=self._cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=(9, 0))
        ttk.Button(buttons, text="Abrir pasta", command=self._open_folder).pack(side="left", padx=(9, 0))

    def _paste(self):
        try:
            self.url.set(self.clipboard_get().strip())
        except tk.TclError:
            pass

    def _choose_folder(self):
        selected = filedialog.askdirectory(initialdir=self.folder.get())
        if selected:
            self.folder.set(selected)

    def _open_folder(self):
        folder = Path(self.folder.get())
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(folder)

    def _mode_changed(self, _event=None):
        if self.mode.get() == "Áudio MP3":
            self.quality_box.configure(state="disabled")
            self.quality.set("Melhor disponível")
        else:
            self.quality_box.configure(state="readonly")
            self.quality.set("1080p")

    @staticmethod
    def _valid_url(url):
        return bool(re.match(r"^https?://([\w-]+\.)?(youtube\.com|youtu\.be)/", url, re.I))

    def _start(self):
        url = self.url.get().strip()
        if not self._valid_url(url):
            messagebox.showwarning(APP_NAME, "Cole um link válido do YouTube.")
            return
        folder = Path(self.folder.get())
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"Não foi possível usar essa pasta:\n{exc}")
            return
        self.cancel_requested = False
        self.progress.set(0)
        self.status.set("Preparando...")
        self.download_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        threading.Thread(target=self._download, args=(url, folder), daemon=True).start()

    def _cancel(self):
        self.cancel_requested = True
        self.status.set("Cancelando...")
        self.cancel_btn.configure(state="disabled")

    def _hook(self, data):
        if self.cancel_requested:
            raise yt_dlp.utils.DownloadCancelled("Cancelado pelo usuário")
        if data.get("status") == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            downloaded = data.get("downloaded_bytes", 0)
            pct = downloaded * 100 / total if total else 0
            speed = data.get("_speed_str", "").strip()
            eta = data.get("_eta_str", "").strip()
            self.events.put(("progress", pct, f"Baixando: {pct:.1f}%  •  {speed}  •  restante {eta}"))
        elif data.get("status") == "finished":
            self.events.put(("progress", 100, "Processando o arquivo..."))

    def _download(self, url, folder):
        try:
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            options = {
                "outtmpl": str(folder / "%(title)s [%(id)s].%(ext)s"),
                "noplaylist": not self.playlist.get(),
                "windowsfilenames": True,
                "progress_hooks": [self._hook],
                "ffmpeg_location": ffmpeg,
                "quiet": True,
                "no_warnings": True,
            }
            if self.mode.get() == "Áudio MP3":
                options.update({
                    "format": "bestaudio/best",
                    "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
                })
            else:
                heights = {"2160p (4K)": 2160, "1440p": 1440, "1080p": 1080, "720p": 720, "480p": 480, "360p": 360}
                height = heights.get(self.quality.get())
                options["format"] = f"bv*[height<={height}]+ba/b[height<={height}]" if height else "bv*+ba/b"
                options["merge_output_format"] = "mp4"
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
                self.events.put(("title", info.get("title") or "Conteúdo encontrado"))
                ydl.download([url])
            self.events.put(("done",))
        except yt_dlp.utils.DownloadCancelled:
            self.events.put(("cancelled",))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def _poll_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "progress":
                    self.progress.set(event[1])
                    self.status.set(event[2])
                elif kind == "title":
                    self.title_text.set(event[1])
                elif kind == "done":
                    self.progress.set(100)
                    self.status.set("Download concluído!")
                    self._finish()
                    messagebox.showinfo(APP_NAME, "Download concluído com sucesso.")
                elif kind == "cancelled":
                    self.status.set("Download cancelado")
                    self._finish()
                elif kind == "error":
                    self.status.set("Não foi possível concluir")
                    self._finish()
                    messagebox.showerror(APP_NAME, "Falha no download:\n\n" + event[1])
        except queue.Empty:
            pass
        self.after(100, self._poll_events)

    def _finish(self):
        self.download_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")

if __name__ == "__main__":
    DownloaderApp().mainloop()
