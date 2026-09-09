import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    import imageio_ffmpeg
    import yt_dlp
except ImportError:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Dependências ausentes", "Execute primeiro o arquivo INSTALAR_E_ABRIR.bat.")
    raise SystemExit(1)


APP_NAME = "Eclipse Downloader"


class DownloaderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("800x700")
        self.minsize(740, 650)
        self.configure(bg="#10131a")
        self.events = queue.Queue()
        self.cancel_requested = False
        self.worker = None

        self.url = tk.StringVar()
        self.mode = tk.StringVar(value="Vídeo MP4")
        self.quality = tk.StringVar(value="1080p")
        self.folder = tk.StringVar(value=str(Path.home() / "Downloads"))
        self.status = tk.StringVar(value="Pronto para baixar")
        self.title_text = tk.StringVar(value="Cole um link para começar")
        self.progress = tk.DoubleVar(value=0)
        self.playlist = tk.BooleanVar(value=False)
        self.size_text = tk.StringVar(value="Tamanho estimado: analise o link")
        self.format_sizes = {}
        self.progress_files = {}
        self.progress_totals = {}

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

        title_row = ttk.Frame(card, style="Card.TFrame")
        title_row.pack(fill="x", pady=(0, 14))
        ttk.Label(title_row, textvariable=self.title_text, style="Card.TLabel", wraplength=570).pack(side="left", fill="x", expand=True)
        self.analyze_btn = ttk.Button(title_row, text="Analisar link", command=self._start_analysis)
        self.analyze_btn.pack(side="right", padx=(8, 0))

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
        self.quality_box.bind("<<ComboboxSelected>>", self._quality_changed)

        ttk.Label(card, textvariable=self.size_text, style="Card.TLabel").pack(anchor="w", pady=(12, 2))
        self.sizes = ttk.Treeview(card, columns=("quality", "size"), show="headings", height=4)
        self.sizes.heading("quality", text="Qualidade")
        self.sizes.heading("size", text="Tamanho estimado")
        self.sizes.column("quality", width=180, anchor="center")
        self.sizes.column("size", width=220, anchor="center")
        self.sizes.pack(fill="x", pady=(5, 4))

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
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])

    def _mode_changed(self, _event=None):
        if self.mode.get() == "Áudio MP3":
            self.quality_box.configure(state="disabled")
            self.quality.set("Melhor disponível")
        else:
            self.quality_box.configure(state="readonly")
            self.quality.set("1080p")
        self._refresh_size_text()

    def _quality_changed(self, _event=None):
        self._refresh_size_text()

    @staticmethod
    def _human_size(value):
        if not value:
            return "Não informado"
        units = ["B", "KB", "MB", "GB", "TB"]
        number = float(value)
        for unit in units:
            if number < 1024 or unit == units[-1]:
                return f"{number:.1f} {unit}" if unit != "B" else f"{int(number)} B"
            number /= 1024

    @staticmethod
    def _format_size(fmt, duration=0):
        size = fmt.get("filesize") or fmt.get("filesize_approx")
        if not size and fmt.get("tbr") and duration:
            size = fmt["tbr"] * 1000 / 8 * duration
        return int(size) if size else 0

    def _estimate_sizes(self, info):
        if info.get("entries"):
            info = next((item for item in info["entries"] if item), {})
        formats = info.get("formats") or []
        duration = info.get("duration") or 0
        audio = [f for f in formats if f.get("acodec") != "none" and f.get("vcodec") == "none"]
        best_audio = max(audio, key=lambda f: (self._format_size(f, duration), f.get("abr") or 0), default=None)
        audio_size = self._format_size(best_audio, duration) if best_audio else 0
        results = {}
        for height in (360, 480, 720, 1080, 1440, 2160):
            video = [f for f in formats if f.get("vcodec") != "none" and (f.get("height") or 0) <= height]
            if not video:
                continue
            best = max(video, key=lambda f: ((f.get("height") or 0), self._format_size(f, duration), f.get("tbr") or 0))
            size = self._format_size(best, duration)
            if best.get("acodec") == "none":
                size += audio_size
            results[height] = size
        return results

    def _start_analysis(self):
        url = self.url.get().strip()
        if not self._valid_url(url):
            messagebox.showwarning(APP_NAME, "Cole um link válido do YouTube.")
            return
        self.analyze_btn.configure(state="disabled")
        self.status.set("Analisando qualidades e tamanhos...")
        threading.Thread(target=self._analyze, args=(url,), daemon=True).start()

    def _analyze(self, url):
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "noplaylist": not self.playlist.get()}) as ydl:
                info = ydl.extract_info(url, download=False)
            title = info.get("title") or "Conteúdo encontrado"
            if info.get("entries"):
                first = next((item for item in info["entries"] if item), {})
                title = info.get("title") or first.get("title") or "Playlist encontrada"
            self.events.put(("analysis", title, self._estimate_sizes(info)))
        except Exception as exc:
            self.events.put(("analysis_error", str(exc)))

    def _refresh_size_text(self):
        if self.mode.get() == "Áudio MP3":
            self.size_text.set("Áudio MP3: o tamanho final pode variar após a conversão")
            return
        height = {"2160p (4K)": 2160, "1440p": 1440, "1080p": 1080, "720p": 720, "480p": 480, "360p": 360}.get(self.quality.get())
        size = self.format_sizes.get(height)
        self.size_text.set(f"Tamanho estimado selecionado: {self._human_size(size)}" if size else "Tamanho estimado: analise o link")

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
        self.progress_files = {}
        self.progress_totals = {}
        self.progress.set(0)
        self.status.set("Preparando...")
        self.download_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.worker = threading.Thread(target=self._download, args=(url, folder), daemon=True)
        self.worker.start()

    def _cancel(self):
        self.cancel_requested = True
        self.status.set("Cancelando...")
        self.cancel_btn.configure(state="disabled")

    def _hook(self, data):
        if self.cancel_requested:
            raise yt_dlp.utils.DownloadCancelled("Cancelado pelo usuário")
        status = data.get("status")
        if status == "downloading":
            name = data.get("filename") or str(id(data.get("info_dict")))
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            self.progress_files[name] = data.get("downloaded_bytes", 0)
            if total:
                self.progress_totals[name] = total
            downloaded = sum(self.progress_files.values())
            known_total = sum(self.progress_totals.values())
            target_height = {"2160p (4K)": 2160, "1440p": 1440, "1080p": 1080, "720p": 720, "480p": 480, "360p": 360}.get(self.quality.get())
            estimated = self.format_sizes.get(target_height, 0)
            display_total = max(known_total, estimated)
            pct = min(100, downloaded * 100 / display_total) if display_total else 0
            speed = data.get("_speed_str", "").strip()
            eta = data.get("_eta_str", "").strip()
            amount = f"{self._human_size(downloaded)} de {self._human_size(display_total)}" if display_total else self._human_size(downloaded)
            self.events.put(("progress", pct, f"Baixando: {amount}  •  {pct:.1f}%  •  {speed}  •  restante {eta}"))
        elif status == "finished":
            name = data.get("filename") or str(id(data.get("info_dict")))
            if name in self.progress_totals:
                self.progress_files[name] = self.progress_totals[name]
            self.events.put(("progress", 100, "Processando o arquivo..."))

    def _download(self, url, folder):
        try:
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            outtmpl = str(folder / "%(playlist_index&{} - |)s%(title)s [%(id)s].%(ext)s")
            options = {
                "outtmpl": outtmpl,
                "noplaylist": not self.playlist.get(),
                "windowsfilenames": True,
                "restrictfilenames": False,
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
                options["format"] = (f"bv*[height<={height}]+ba/b[height<={height}]" if height else "bv*+ba/b")
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
                elif kind == "analysis":
                    self.title_text.set(event[1])
                    self.format_sizes = event[2]
                    for item in self.sizes.get_children():
                        self.sizes.delete(item)
                    for height in (360, 480, 720, 1080, 1440, 2160):
                        if height in self.format_sizes:
                            label = "2160p (4K)" if height == 2160 else f"{height}p"
                            self.sizes.insert("", "end", values=(label, self._human_size(self.format_sizes[height])))
                    self._refresh_size_text()
                    self.status.set("Análise concluída. Escolha o formato e clique em baixar.")
                    self.analyze_btn.configure(state="normal")
                elif kind == "analysis_error":
                    self.status.set("Não foi possível analisar o link")
                    self.analyze_btn.configure(state="normal")
                    messagebox.showerror(APP_NAME, "Falha na análise:\n\n" + event[1])
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
                    messagebox.showerror(APP_NAME, "Falha no download:\n\n" + event[1] + "\n\nTente atualizar o aplicativo pelo arquivo ATUALIZAR.bat.")
        except queue.Empty:
            pass
        self.after(100, self._poll_events)

    def _finish(self):
        self.download_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")


if __name__ == "__main__":
    DownloaderApp().mainloop()
