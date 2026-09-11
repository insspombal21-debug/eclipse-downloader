import hashlib, io, json, os, queue, re, subprocess, sys, tempfile, threading, time, tkinter as tk, urllib.request, uuid, zipfile
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlsplit
import imageio_ffmpeg, yt_dlp
from PIL import Image, ImageDraw, ImageFont, ImageTk
try:import winsound
except ImportError:winsound=None

APP_NAME = "Eclipse Flow"
APP_VERSION = "6.1.0"
RELEASE_API = "https://api.github.com/repos/insspombal21-debug/eclipse-downloader/releases/latest"
HEIGHTS = {"Melhor disponível": None, "2160p (4K)": 2160, "1440p": 1440, "1080p": 1080, "720p": 720, "480p": 480, "360p": 360}
AUDIO_BITRATES = {"320 kbps": 320, "256 kbps": 256, "192 kbps": 192, "128 kbps": 128}
SPEEDS = {"Sem limite": None, "500 KB/s": 500*1024, "1 MB/s": 1024**2, "2 MB/s": 2*1024**2, "5 MB/s": 5*1024**2, "10 MB/s": 10*1024**2}
CONVERT_FORMATS = ("MP3","WAV","AAC","FLAC","OGG","MP4","MKV","AVI","WEBM")
CONVERT_AUDIO = {"MP3","WAV","AAC","FLAC","OGG"}
CONVERT_AUDIO_QUALITY = ("320 kbps","256 kbps","192 kbps","128 kbps")
CONVERT_VIDEO_QUALITY = ("Manter resolução","1080p","720p","480p","360p")
MEDIA_EXTENSIONS = {".mp4",".mkv",".avi",".webm",".mov",".wmv",".m4v",".mpg",".mpeg",".mp3",".wav",".aac",".m4a",".flac",".ogg",".opus",".wma"}
AUDIO_EXTENSIONS = {".mp3",".wav",".aac",".m4a",".flac",".ogg",".opus",".wma"}
NETWORKS = ("Detectar automaticamente","YouTube","Facebook","Instagram","TikTok","X / Twitter","Vimeo","Twitch","Reddit","SoundCloud","Dailymotion")
NETWORK_DOMAINS = {
    "YouTube":("youtube.com","youtu.be"),"Facebook":("facebook.com","fb.watch","fb.com"),"Instagram":("instagram.com",),
    "TikTok":("tiktok.com",),"X / Twitter":("x.com","twitter.com"),"Vimeo":("vimeo.com",),"Twitch":("twitch.tv",),
    "Reddit":("reddit.com","redd.it"),"SoundCloud":("soundcloud.com",),"Dailymotion":("dailymotion.com","dai.ly"),
}
NETWORK_COLORS = {"Automático":"#7c3aed","YouTube":"#ef4444","Facebook":"#1877f2","Instagram":"#c026d3","TikTok":"#111827","X / Twitter":"#111827","Vimeo":"#1ab7ea","Twitch":"#9146ff","Reddit":"#ff4500","SoundCloud":"#ff5500","Dailymotion":"#0066dc"}
NETWORK_STYLES = {name:f"Network{pos}.TButton" for pos,name in enumerate(NETWORK_COLORS)}

class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title(APP_NAME); self.geometry("1080x720"); self.minsize(920, 620); self.configure(bg="#0b0d17")
        self.settings_file=Path(os.getenv("APPDATA") or Path.home())/APP_NAME/"config.json";saved=self._load_settings()
        mode=saved.get("mode") if saved.get("mode") in ("Vídeo MP4","Áudio MP3") else "Vídeo MP4";valid_quality=AUDIO_BITRATES if mode=="Áudio MP3" else HEIGHTS
        quality=saved.get("quality") if saved.get("quality") in valid_quality else ("192 kbps" if mode=="Áudio MP3" else "1080p");speed=saved.get("speed") if saved.get("speed") in SPEEDS else "Sem limite";concurrent=str(saved.get("concurrent","1"));concurrent=concurrent if concurrent in ("1","2","3") else "1"
        self.events, self.work, self.analysis = queue.Queue(), queue.Queue(), queue.Queue(); self.tasks, self.images = {}, {}; self.active=set();self.download_condition=threading.Condition();self.download_limit=int(concurrent);self.batch_active=False
        self.mode, self.quality = tk.StringVar(value=mode), tk.StringVar(value=quality)
        network=saved.get("network") if saved.get("network") in NETWORKS else "Detectar automaticamente"
        self.folder = tk.StringVar(value=saved.get("folder") or str(Path.home()/"Downloads")); self.speed = tk.StringVar(value=speed);self.concurrent=tk.StringVar(value=concurrent);self.network=tk.StringVar(value=network);self.clipboard_watch=tk.BooleanVar(value=bool(saved.get("clipboard_watch",False)));self.last_clipboard="";self.status = tk.StringVar(value="Cole links para começar");self.playlist_status=tk.StringVar(value="")
        convert_format=saved.get("convert_format") if saved.get("convert_format") in CONVERT_FORMATS else "MP3";convert_quality=saved.get("convert_quality") or "192 kbps"
        valid_convert_quality=("Sem perda",) if convert_format in ("WAV","FLAC") else (CONVERT_AUDIO_QUALITY if convert_format in CONVERT_AUDIO else CONVERT_VIDEO_QUALITY)
        if convert_quality not in valid_convert_quality:convert_quality="Sem perda" if convert_format in ("WAV","FLAC") else ("192 kbps" if convert_format in CONVERT_AUDIO else "Manter resolução")
        self.convert_format=tk.StringVar(value=convert_format);self.convert_quality=tk.StringVar(value=convert_quality);self.convert_folder=tk.StringVar(value=saved.get("convert_folder") or str(Path.home()/"Downloads"/"Eclipse Flow Convertidos"));self.convert_status=tk.StringVar(value="Adicione arquivos para converter")
        self.convert_tasks={};self.convert_queue=queue.Queue();self.convert_active=None;self.convert_process=None
        self.update_url = self.checksum_url = None
        self._style(); self._ui(); self.after(100, self._poll); threading.Thread(target=self._worker, daemon=True).start()
        for _ in range(2):threading.Thread(target=self._analysis_worker,daemon=True).start()
        threading.Thread(target=self._convert_worker,daemon=True).start()
        self.protocol("WM_DELETE_WINDOW",self._close);self.after(1200,self._watch_clipboard);self.after(1800, self._check_updates)

    def _load_settings(self):
        try:return json.loads(self.settings_file.read_text(encoding="utf-8"))
        except (OSError,ValueError):return {}
    def _save_settings(self):
        try:
            data={"mode":self.mode.get(),"quality":self.quality.get(),"speed":self.speed.get(),"concurrent":self.concurrent.get(),"network":self.network.get(),"folder":self.folder.get(),"clipboard_watch":self.clipboard_watch.get(),"convert_format":self.convert_format.get(),"convert_quality":self.convert_quality.get(),"convert_folder":self.convert_folder.get()};self.settings_file.parent.mkdir(parents=True,exist_ok=True)
            temp=self.settings_file.with_suffix(".tmp");temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8");temp.replace(self.settings_file)
        except OSError:pass
    def _close(self):
        self._save_settings()
        if self.convert_process:
            try:self.convert_process.terminate()
            except OSError:pass
        self.destroy()
    def _concurrency_changed(self,_event=None):
        self.download_limit=int(self.concurrent.get())
        with self.download_condition:self.download_condition.notify_all()
        self._save_settings();self.status.set(f"Até {self.download_limit} download(s) ao mesmo tempo")

    def _make_logo(self):
        size=56; image=Image.new("RGBA",(size,size),(0,0,0,0)); draw=ImageDraw.Draw(image)
        for width,color in ((12,"#312e81"),(8,"#7c3aed"),(4,"#ec4899")):
            pad=(12-width)//2+5; draw.ellipse((pad,pad,size-pad,size-pad),outline=color,width=width)
        draw.ellipse((18,12,45,39),fill="#0b0d17")
        draw.rounded_rectangle((25,16,31,37),radius=3,fill="#ffffff")
        draw.polygon(((18,32),(38,32),(28,44)),fill="#ffffff")
        return ImageTk.PhotoImage(image)
    def _make_platform_icons(self):
        icons={}
        try:font=ImageFont.truetype("arialbd.ttf",14)
        except OSError:font=ImageFont.load_default()
        for name,color in NETWORK_COLORS.items():
            im=Image.new("RGBA",(22,22),(0,0,0,0));d=ImageDraw.Draw(im);d.ellipse((1,1,21,21),fill=color)
            if name=="YouTube":d.rounded_rectangle((3,6,19,16),radius=3,fill="#ffffff");d.polygon(((9,8),(9,14),(14,11)),fill=color)
            elif name=="Instagram":d.rounded_rectangle((5,5,17,17),radius=4,outline="white",width=2);d.ellipse((8,8,14,14),outline="white",width=2);d.ellipse((15,6,17,8),fill="white")
            elif name=="TikTok":d.line((12,5,12,14,9,17),fill="#25f4ee",width=3);d.ellipse((6,14,12,19),fill="#fe2c55")
            elif name=="X / Twitter":d.line((7,6,16,17),fill="white",width=2);d.line((16,6,7,17),fill="white",width=2)
            elif name=="Automático":d.ellipse((5,8,12,14),outline="white",width=2);d.ellipse((10,8,17,14),outline="white",width=2)
            else:
                label="f" if name=="Facebook" else name[0];box=d.textbbox((0,0),label,font=font);d.text(((22-(box[2]-box[0]))/2,(22-(box[3]-box[1]))/2-1),label,font=font,fill="white")
            icons[name]=ImageTk.PhotoImage(im)
        return icons

    def _style(self):
        s=ttk.Style(self); s.theme_use("clam"); s.configure("TFrame",background="#0b0d17"); s.configure("Card.TFrame",background="#17152b")
        s.configure("TLabel",background="#0b0d17",foreground="#f4f2ff",font=("Segoe UI",10)); s.configure("Card.TLabel",background="#17152b",foreground="#f4f2ff")
        s.configure("Title.TLabel",font=("Segoe UI Semibold",25),foreground="white"); s.configure("Muted.TLabel",foreground="#aaa6c3")
        s.configure("TButton",font=("Segoe UI Semibold",10),padding=9,background="#24213d",foreground="#f4f2ff"); s.configure("Accent.TButton",background="#ec4899",foreground="white",borderwidth=0)
        s.map("Accent.TButton",background=[("active","#f472b6")]); s.configure("TEntry",fieldbackground="#0d1020",foreground="white",padding=8)
        s.configure("Tab.TButton",font=("Segoe UI Semibold",11),padding=(18,10),background="#17152b",foreground="#aaa6c3",borderwidth=0);s.configure("ActiveTab.TButton",font=("Segoe UI Semibold",11),padding=(18,10),background="#7c3aed",foreground="white",borderwidth=0)
        for name,color in NETWORK_COLORS.items():s.configure(NETWORK_STYLES[name],font=("Segoe UI Semibold",10),padding=9,background=color,foreground="white",borderwidth=0);s.map(NETWORK_STYLES[name],background=[("active",color)])
        s.configure("TCombobox",fieldbackground="#0d1020",foreground="#111827",padding=7); s.configure("TCheckbutton",background="#17152b",foreground="#f4f2ff")
        s.configure("Queue.Treeview",background="#17152b",foreground="#f4f2ff",fieldbackground="#17152b",rowheight=72,borderwidth=0,font=("Segoe UI",10))
        s.configure("Queue.Treeview.Heading",background="#282444",foreground="#f4f2ff",font=("Segoe UI Semibold",10)); s.map("Queue.Treeview",background=[("selected","#3b3262")])
        s.configure("Picker.Treeview",background="#17152b",foreground="#f4f2ff",fieldbackground="#17152b",rowheight=30,borderwidth=0,font=("Segoe UI",10));s.configure("Picker.Treeview.Heading",background="#282444",foreground="#f4f2ff",font=("Segoe UI Semibold",10));s.map("Picker.Treeview",background=[("selected","#5b21b6")])

    def _ui(self):
        out=ttk.Frame(self,padding=22); out.pack(fill="both",expand=True)
        title_row=ttk.Frame(out); title_row.pack(fill="x"); self.brand_logo=self._make_logo(); ttk.Label(title_row,image=self.brand_logo).pack(side="left",padx=(0,11))
        ttk.Label(title_row,text=f"{APP_NAME}  v{APP_VERSION}",style="Title.TLabel").pack(side="left")
        self.update_btn=ttk.Button(title_row,text="Verificar atualizações",command=self._check_updates); self.update_btn.pack(side="right")
        ttk.Label(out,text="Seus downloads em movimento  •  Atualizações automáticas ativadas",style="Muted.TLabel").pack(anchor="w",padx=(67,0),pady=(0,14))
        tabbar=ttk.Frame(out);tabbar.pack(fill="x",pady=(0,10));self.download_tab_btn=ttk.Button(tabbar,text="↓  Baixar",style="ActiveTab.TButton",command=lambda:self._switch_tab("download"));self.download_tab_btn.pack(side="left",padx=(0,7));self.convert_tab_btn=ttk.Button(tabbar,text="⇄  Converter",style="Tab.TButton",command=lambda:self._switch_tab("convert"));self.convert_tab_btn.pack(side="left")
        self.page_host=ttk.Frame(out);self.page_host.pack(fill="both",expand=True);self.download_page=ttk.Frame(self.page_host);self.convert_page=ttk.Frame(self.page_host)
        out=self.download_page
        top=ttk.Frame(out,style="Card.TFrame",padding=16); top.pack(fill="x"); row=ttk.Frame(top,style="Card.TFrame"); row.pack(fill="x");self.platform_icons=self._make_platform_icons()
        self.urls=tk.Text(row,height=2,bg="#0d1020",fg="white",insertbackground="#ec4899",relief="flat",font=("Segoe UI",11),padx=10,pady=9); self.urls.pack(side="left",fill="x",expand=True)
        self.paste_btn=ttk.Button(row,text="Colar link",image=self.platform_icons["Automático"],compound="left",style=NETWORK_STYLES["Automático"],command=self._paste);self.paste_btn.pack(side="left",padx=(8,0)); ttk.Button(row,text="ADICIONAR À FILA",style="Accent.TButton",command=self._add).pack(side="left",padx=(8,0))
        cfg=ttk.Frame(top,style="Card.TFrame"); cfg.pack(fill="x",pady=(12,0));ttk.Label(cfg,text="Rede:",style="Card.TLabel").pack(side="left");self.network_box=ttk.Combobox(cfg,textvariable=self.network,state="readonly",width=20,values=NETWORKS);self.network_box.pack(side="left",padx=(6,16));self.network_box.bind("<<ComboboxSelected>>",self._network_changed);ttk.Label(cfg,text="Formato:",style="Card.TLabel").pack(side="left")
        self.mode_box=ttk.Combobox(cfg,textvariable=self.mode,state="readonly",width=15,values=["Vídeo MP4","Áudio MP3"]);self.mode_box.pack(side="left",padx=(6,16));self.mode_box.bind("<<ComboboxSelected>>",self._mode_changed);ttk.Label(cfg,text="Qualidade:",style="Card.TLabel").pack(side="left")
        quality_values=AUDIO_BITRATES if self.mode.get()=="Áudio MP3" else HEIGHTS;self.quality_box=ttk.Combobox(cfg,textvariable=self.quality,state="readonly",width=18,values=list(quality_values));self.quality_box.pack(side="left",padx=(6,16));self.quality_box.bind("<<ComboboxSelected>>",lambda _e:self._save_settings());ttk.Label(cfg,text="✓ Playlists detectadas automaticamente",style="Card.TLabel").pack(side="right")
        perf=ttk.Frame(top,style="Card.TFrame");perf.pack(fill="x",pady=(10,0));ttk.Label(perf,text="Limite de velocidade:",style="Card.TLabel").pack(side="left");self.speed_box=ttk.Combobox(perf,textvariable=self.speed,state="readonly",width=12,values=list(SPEEDS));self.speed_box.pack(side="left",padx=(6,18));self.speed_box.bind("<<ComboboxSelected>>",lambda _e:self._save_settings());ttk.Label(perf,text="Downloads simultâneos:",style="Card.TLabel").pack(side="left");self.concurrent_box=ttk.Combobox(perf,textvariable=self.concurrent,state="readonly",width=5,values=("1","2","3"));self.concurrent_box.pack(side="left",padx=6);self.concurrent_box.bind("<<ComboboxSelected>>",self._concurrency_changed);ttk.Checkbutton(perf,text="Monitorar links copiados",variable=self.clipboard_watch,command=self._toggle_clipboard).pack(side="right")
        dest=ttk.Frame(top,style="Card.TFrame");dest.pack(fill="x",pady=(10,0));ttk.Label(dest,text="Salvar em:",style="Card.TLabel").pack(side="left");ttk.Label(dest,textvariable=self.folder,style="Card.TLabel").pack(side="left",padx=8);ttk.Button(dest,text="Escolher pasta",command=self._choose).pack(side="right")
        card=ttk.Frame(out,style="Card.TFrame",padding=12); card.pack(fill="both",expand=True,pady=(14,0));head=ttk.Frame(card,style="Card.TFrame");head.pack(fill="x",pady=(0,8));ttk.Label(head,text="FILA DE DOWNLOADS",style="Card.TLabel",font=("Segoe UI Semibold",11)).pack(side="left");ttk.Label(head,textvariable=self.playlist_status,style="Card.TLabel",foreground="#c4b5fd").pack(side="right")
        cols=("title","profile","size","progress","status"); self.list=ttk.Treeview(card,columns=cols,show="tree headings",style="Queue.Treeview",selectmode="browse")
        for col,title in zip(("#0",)+cols,("Miniatura","Título","Formato","Tamanho","Progresso","Status")): self.list.heading(col,text=title)
        self.list.column("#0",width=125,stretch=False,anchor="center"); self.list.column("title",width=330); self.list.column("profile",width=115,anchor="center")
        self.list.column("size",width=105,anchor="center"); self.list.column("progress",width=190,anchor="center"); self.list.column("status",width=130,anchor="center")
        bar=ttk.Scrollbar(card,orient="vertical",command=self.list.yview); self.list.configure(yscrollcommand=bar.set); bar.pack(side="right",fill="y"); self.list.pack(fill="both",expand=True)
        self.list.bind("<Button-3>",self._right); self.list.bind("<Double-1>",lambda _e:self._open_selected())
        acts=ttk.Frame(out); acts.pack(fill="x",pady=(12,0))
        for label,cmd in (("Pausar",self._pause),("Continuar",self._resume),("Pausar tudo",self._pause_all),("Continuar tudo",self._resume_all),("Cancelar",self._cancel),("Mostrar arquivo",self._show),("Limpar",self._clear_completed),("⋮ Ações",self._popup)):
            ttk.Button(acts,text=label,command=cmd).pack(side="left",padx=(0,7))
        ttk.Label(out,textvariable=self.status,style="Muted.TLabel").pack(anchor="e",pady=(5,0))
        self.menu=tk.Menu(self,tearoff=False); self.menu.add_command(label="Mostrar arquivo na pasta",command=self._show); self.menu.add_command(label="Abrir pasta de destino",command=self._open_folder)
        self.menu.add_command(label="Baixar novamente",command=self._retry);self.menu.add_command(label="Detalhes do erro",command=self._show_error); self.menu.add_separator(); self.menu.add_command(label="Remover da fila",command=self._remove); self.menu.add_command(label="Excluir arquivo do computador",command=self._delete_file)
        self._converter_ui(self.convert_page);self._convert_format_changed();self._network_changed();self._switch_tab("download")

    def _switch_tab(self,name):
        self.download_page.pack_forget();self.convert_page.pack_forget()
        if name=="convert":
            self.convert_page.pack(fill="both",expand=True);self.download_tab_btn.configure(style="Tab.TButton");self.convert_tab_btn.configure(style="ActiveTab.TButton")
        else:
            self.download_page.pack(fill="both",expand=True);self.download_tab_btn.configure(style="ActiveTab.TButton");self.convert_tab_btn.configure(style="Tab.TButton")

    def _converter_ui(self,out):
        top=ttk.Frame(out,style="Card.TFrame",padding=16);top.pack(fill="x")
        ttk.Label(top,text="Conversor multiformato",style="Card.TLabel",font=("Segoe UI Semibold",16)).pack(anchor="w")
        ttk.Label(top,text="Converta vídeos e áudios que já estão no computador — sem instalar componentes adicionais.",style="Card.TLabel",foreground="#aaa6c3").pack(anchor="w",pady=(2,12))
        buttons=ttk.Frame(top,style="Card.TFrame");buttons.pack(fill="x");ttk.Button(buttons,text="+ Adicionar arquivos",command=self._convert_add_files).pack(side="left",padx=(0,7));ttk.Button(buttons,text="+ Adicionar pasta",command=self._convert_add_folder).pack(side="left")
        profile=ttk.Frame(top,style="Card.TFrame");profile.pack(fill="x",pady=(12,0));ttk.Label(profile,text="Formato de saída:",style="Card.TLabel").pack(side="left");self.convert_format_box=ttk.Combobox(profile,textvariable=self.convert_format,state="readonly",width=10,values=CONVERT_FORMATS);self.convert_format_box.pack(side="left",padx=(6,16));self.convert_format_box.bind("<<ComboboxSelected>>",self._convert_format_changed);ttk.Label(profile,text="Qualidade:",style="Card.TLabel").pack(side="left");self.convert_quality_box=ttk.Combobox(profile,textvariable=self.convert_quality,state="readonly",width=18,values=CONVERT_AUDIO_QUALITY);self.convert_quality_box.pack(side="left",padx=(6,16));self.convert_quality_box.bind("<<ComboboxSelected>>",lambda _e:self._save_settings());ttk.Button(profile,text="CONVERTER",style="Accent.TButton",command=self._convert_start).pack(side="right")
        dest=ttk.Frame(top,style="Card.TFrame");dest.pack(fill="x",pady=(10,0));ttk.Label(dest,text="Salvar em:",style="Card.TLabel").pack(side="left");ttk.Label(dest,textvariable=self.convert_folder,style="Card.TLabel").pack(side="left",padx=8);ttk.Button(dest,text="Escolher pasta",command=self._convert_choose_folder).pack(side="right")
        card=ttk.Frame(out,style="Card.TFrame",padding=12);card.pack(fill="both",expand=True,pady=(14,0));ttk.Label(card,text="FILA DE CONVERSÕES",style="Card.TLabel",font=("Segoe UI Semibold",11)).pack(anchor="w",pady=(0,8))
        cols=("source","target","size","progress","status");self.convert_list=ttk.Treeview(card,columns=cols,show="headings",style="Queue.Treeview",selectmode="browse")
        for col,title in zip(cols,("Arquivo","Conversão","Tamanho","Progresso","Status")):self.convert_list.heading(col,text=title)
        self.convert_list.column("source",width=390);self.convert_list.column("target",width=120,anchor="center");self.convert_list.column("size",width=105,anchor="center");self.convert_list.column("progress",width=160,anchor="center");self.convert_list.column("status",width=150,anchor="center")
        bar=ttk.Scrollbar(card,orient="vertical",command=self.convert_list.yview);self.convert_list.configure(yscrollcommand=bar.set);bar.pack(side="right",fill="y");self.convert_list.pack(fill="both",expand=True);self.convert_list.bind("<Double-1>",lambda _e:self._convert_show())
        acts=ttk.Frame(out);acts.pack(fill="x",pady=(12,0));ttk.Button(acts,text="Cancelar",command=self._convert_cancel).pack(side="left",padx=(0,7));ttk.Button(acts,text="Mostrar arquivo",command=self._convert_show).pack(side="left",padx=(0,7));ttk.Button(acts,text="Remover",command=self._convert_remove).pack(side="left",padx=(0,7));ttk.Button(acts,text="Limpar concluídos",command=self._convert_clear).pack(side="left");ttk.Label(acts,textvariable=self.convert_status,style="Muted.TLabel").pack(side="right")

    def _convert_format_changed(self,_event=None):
        fmt=self.convert_format.get();values=("Sem perda",) if fmt in ("WAV","FLAC") else (CONVERT_AUDIO_QUALITY if fmt in CONVERT_AUDIO else CONVERT_VIDEO_QUALITY)
        self.convert_quality_box.configure(values=values)
        if self.convert_quality.get() not in values:self.convert_quality.set("Sem perda" if fmt in ("WAV","FLAC") else ("192 kbps" if fmt in CONVERT_AUDIO else "Manter resolução"))
        for t in self.convert_tasks.values():
            if t["status"]=="Aguardando":t.update(format=fmt,quality=self.convert_quality.get());self._convert_row(t["id"])
        self._save_settings()
    def _convert_add_files(self):
        paths=filedialog.askopenfilenames(title="Escolher vídeos ou áudios",filetypes=[("Vídeos e áudios","*.mp4 *.mkv *.avi *.webm *.mov *.wmv *.m4v *.mpg *.mpeg *.mp3 *.wav *.aac *.m4a *.flac *.ogg *.opus *.wma"),("Todos os arquivos","*.*")])
        self._convert_add_paths(paths)
    def _convert_add_folder(self):
        folder=filedialog.askdirectory(title="Escolher pasta com vídeos ou áudios")
        if folder:self._convert_add_paths(sorted(str(p) for p in Path(folder).rglob("*") if p.is_file() and p.suffix.lower() in MEDIA_EXTENSIONS))
    def _convert_add_paths(self,paths):
        added=0;existing={t["source"] for t in self.convert_tasks.values() if t["status"] not in ("Removido",)}
        for raw in paths:
            p=Path(raw)
            if not p.is_file() or p.suffix.lower() not in MEDIA_EXTENSIONS or str(p) in existing:continue
            i=uuid.uuid4().hex;t={"id":i,"source":str(p),"title":p.name,"format":self.convert_format.get(),"quality":self.convert_quality.get(),"size":p.stat().st_size,"progress":"0%","percent":0.0,"status":"Aguardando","output":None,"cancel":False,"error":None}
            self.convert_tasks[i]=t;self.convert_list.insert("","end",iid=i,values=(p.name,f"{p.suffix.lstrip('.').upper()} → {t['format']}",self._human(t["size"]),"0%","Aguardando"));existing.add(str(p));added+=1
        self.convert_status.set(f"{added} arquivo(s) adicionado(s)" if added else "Nenhum arquivo novo compatível encontrado")
    def _convert_choose_folder(self):
        p=filedialog.askdirectory(initialdir=self.convert_folder.get(),title="Pasta dos arquivos convertidos")
        if p:self.convert_folder.set(p);self._save_settings()
    def _convert_start(self):
        pending=[t for t in self.convert_tasks.values() if t["status"]=="Aguardando"]
        if not pending:messagebox.showinfo(APP_NAME,"Adicione arquivos antes de iniciar a conversão.");return
        out=Path(self.convert_folder.get())
        try:out.mkdir(parents=True,exist_ok=True)
        except OSError as e:messagebox.showerror(APP_NAME,f"Não foi possível criar a pasta de destino:\n{e}");return
        for t in pending:
            t.update(format=self.convert_format.get(),quality=self.convert_quality.get(),folder=str(out),status="Na fila",cancel=False,error=None);self._convert_row(t["id"]);self.convert_queue.put(t["id"])
        self._save_settings();self.convert_status.set(f"{len(pending)} conversão(ões) iniciada(s)")
    def _convert_worker(self):
        while True:
            i=self.convert_queue.get();t=self.convert_tasks.get(i)
            if not t or t["status"]!="Na fila":continue
            self.convert_active=i;self._convert_one(t);self.convert_active=None;self.convert_process=None
    @staticmethod
    def _media_duration(ffmpeg,source):
        flags=0x08000000 if os.name=="nt" else 0
        try:r=subprocess.run([ffmpeg,"-hide_banner","-i",str(source)],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=30,creationflags=flags)
        except (OSError,subprocess.SubprocessError):return 0.0
        m=re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)",r.stderr or "")
        return int(m.group(1))*3600+int(m.group(2))*60+float(m.group(3)) if m else 0.0
    @staticmethod
    def _convert_command(ffmpeg,source,target,fmt,quality):
        cmd=[ffmpeg,"-y","-hide_banner","-loglevel","error","-i",str(source)];bitrate=(re.search(r"\d+",quality or "") or ["192"])[0]
        if fmt in CONVERT_AUDIO:
            cmd+=["-vn"]
            if fmt=="MP3":cmd+=["-c:a","libmp3lame","-b:a",f"{bitrate}k"]
            elif fmt=="WAV":cmd+=["-c:a","pcm_s16le"]
            elif fmt=="AAC":cmd+=["-c:a","aac","-b:a",f"{bitrate}k"]
            elif fmt=="FLAC":cmd+=["-c:a","flac"]
            elif fmt=="OGG":cmd+=["-c:a","libvorbis","-b:a",f"{bitrate}k"]
        else:
            if quality!="Manter resolução":cmd+=["-vf",f"scale=-2:min({int(re.search(r'\d+',quality).group())}\\,ih)"]
            if fmt in ("MP4","MKV"):cmd+=["-c:v","libx264","-preset","medium","-crf","23","-c:a","aac","-b:a","192k"]
            elif fmt=="AVI":cmd+=["-c:v","mpeg4","-q:v","4","-c:a","libmp3lame","-b:a","192k"]
            elif fmt=="WEBM":cmd+=["-c:v","libvpx-vp9","-crf","32","-b:v","0","-c:a","libopus","-b:a","128k"]
            if fmt=="MP4":cmd+=["-movflags","+faststart"]
        return cmd+["-progress","pipe:1","-nostats",str(target)]
    @staticmethod
    def _unique_output(folder,source,fmt):
        base=Path(folder)/(Path(source).stem+"."+fmt.lower());candidate=base;n=2
        while candidate.exists() or candidate.resolve()==Path(source).resolve():candidate=base.with_name(f"{base.stem} ({n}){base.suffix}");n+=1
        return candidate
    def _convert_one(self,t):
        source=Path(t["source"]);target=self._unique_output(t["folder"],source,t["format"]);ffmpeg=imageio_ffmpeg.get_ffmpeg_exe();duration=self._media_duration(ffmpeg,source);t.update(status="Convertendo",progress="0%",percent=0.0,output=str(target));self.events.put(("convert_update",t["id"]))
        if t["format"] not in CONVERT_AUDIO and source.suffix.lower() in AUDIO_EXTENSIONS:
            t.update(status="Erro",error="Um arquivo somente de áudio não pode ser convertido para um formato de vídeo.");self.events.put(("convert_update",t["id"]));return
        flags=0x08000000 if os.name=="nt" else 0;lines=[]
        try:
            self.convert_process=subprocess.Popen(self._convert_command(ffmpeg,source,target,t["format"],t["quality"]),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding="utf-8",errors="replace",creationflags=flags)
            for raw in self.convert_process.stdout:
                line=raw.strip();lines.append(line);lines=lines[-30:]
                if line.startswith(("out_time_us=","out_time_ms=")) and duration:
                    done=float(line.split("=",1)[1] or 0)/1_000_000;pct=min(99.9,done*100/duration);t["percent"]=pct;t["progress"]=f"{pct:.1f}%";self.events.put(("convert_update",t["id"]))
            code=self.convert_process.wait()
            if t["cancel"]:t["status"]="Cancelado"
            elif code==0 and target.exists():t.update(status="Concluído",progress="100%",percent=100.0)
            else:t.update(status="Erro",error="\n".join(x for x in lines if x)[-4000:] or f"O conversor encerrou com o código {code}.")
        except Exception as e:t.update(status="Cancelado" if t["cancel"] else "Erro",error=str(e))
        if t["status"] in ("Cancelado","Erro") and target.exists():
            try:target.unlink()
            except OSError:pass
        self.events.put(("convert_update",t["id"]))
    def _convert_row(self,i):
        t=self.convert_tasks.get(i)
        if t and self.convert_list.exists(i):self.convert_list.item(i,values=(t["title"],f"{Path(t['source']).suffix.lstrip('.').upper()} → {t['format']}",self._human(t["size"]),t["progress"],t["status"]))
    def _convert_selected(self):
        selected=self.convert_list.selection();return self.convert_tasks.get(selected[0]) if selected else None
    def _convert_cancel(self):
        t=self._convert_selected()
        if not t:return
        t["cancel"]=True
        if t["id"]==self.convert_active and self.convert_process:
            t["status"]="Cancelando..."
            try:self.convert_process.terminate()
            except OSError:pass
        elif t["status"] in ("Aguardando","Na fila"):t["status"]="Cancelado"
        self._convert_row(t["id"])
    def _convert_show(self):
        t=self._convert_selected();p=Path(t["output"]) if t and t.get("output") else None
        if not p or not p.exists():
            if t and t.get("error"):messagebox.showerror(APP_NAME,"Não foi possível converter:\n\n"+t["error"][-1500:])
            else:messagebox.showinfo(APP_NAME,"Esse item ainda não possui um arquivo convertido.")
            return
        subprocess.Popen(["explorer","/select,",str(p)])
    def _convert_remove(self):
        t=self._convert_selected()
        if not t:return
        if t["id"]==self.convert_active:messagebox.showinfo(APP_NAME,"Cancele a conversão antes de remover este item.");return
        if self.convert_list.exists(t["id"]):self.convert_list.delete(t["id"])
        self.convert_tasks.pop(t["id"],None)
    def _convert_clear(self):
        ids=[i for i,t in self.convert_tasks.items() if t["status"] in ("Concluído","Cancelado")]
        for i in ids:
            if self.convert_list.exists(i):self.convert_list.delete(i)
            self.convert_tasks.pop(i,None)
        self.convert_status.set(f"{len(ids)} item(ns) removido(s) da fila")

    def _sel(self):
        x=self.list.selection(); return x[0] if x else None
    def _profile(self,t): return f"MP3 {t['quality']}" if t["mode"]=="Áudio MP3" else t["quality"]
    def _human(self,n):
        if not n:return "—"
        n=float(n)
        for u in ("B","KB","MB","GB","TB"):
            if n<1024 or u=="TB": return f"{n:.1f} {u}" if u!="B" else f"{int(n)} B"
            n/=1024
    def _fsize(self,f,d=0):
        if not f:return 0
        n=f.get("filesize") or f.get("filesize_approx") or ((f.get("tbr") or 0)*125*d); return int(n or 0)
    def _sizes(self,info):
        fs=info.get("formats") or []; d=info.get("duration") or 0; aud=[f for f in fs if f.get("acodec")!="none" and f.get("vcodec")=="none"]
        a=max(aud,key=lambda f:(self._fsize(f,d),f.get("abr") or 0),default=None); az=self._fsize(a,d); result={}
        for h in (360,480,720,1080,1440,2160):
            vs=[f for f in fs if f.get("vcodec")!="none" and (f.get("height") or 0)<=h]
            if vs:
                v=max(vs,key=lambda f:((f.get("height") or 0),self._fsize(f,d),f.get("tbr") or 0)); result[h]=self._fsize(v,d)+(az if v.get("acodec")=="none" else 0)
        return result,az
    def _estimate_size(self,info,t):
        sizes,audio=self._sizes(info)
        if t["mode"]=="Áudio MP3":
            duration=info.get("duration") or 0;bitrate=AUDIO_BITRATES.get(t["quality"],192)
            return int(duration*bitrate*1000/8) if duration else audio
        height=HEIGHTS.get(t["quality"]);return sizes.get(height) if height else max(sizes.values(),default=0)
    @staticmethod
    def _metadata_hook(d):
        if d.get("status")!="started":return
        info=d.get("info_dict") or {}
        if not (info.get("artist") or info.get("artists")):
            for key in ("creator","creators","uploader","uploader_id"):info[key]=None
    def _mode_changed(self,_event=None):
        audio=self.mode.get()=="Áudio MP3";values=list(AUDIO_BITRATES if audio else HEIGHTS);self.quality_box.configure(values=values)
        if self.quality.get() not in values:self.quality.set("192 kbps" if audio else "1080p")
        self._save_settings()
    def _safe_folder(self,name):
        clean=re.sub(r'[<>:"/\\|?*\x00-\x1f]',"_",name or "Playlist").strip(" .")[:150] or "Playlist"
        if clean.upper().split(".")[0] in {"CON","PRN","AUX","NUL",*(f"COM{x}" for x in range(1,10)),*(f"LPT{x}" for x in range(1,10))}:clean="_"+clean
        return clean

    def _paste(self):
        try:
            content=self.clipboard_get().strip();self.urls.delete("1.0","end");self.urls.insert("1.0",content);self._update_paste_button(content)
        except tk.TclError:pass
    @staticmethod
    def _detect_platform(url):
        try:host=(urlsplit(url).hostname or "").lower().removeprefix("www.")
        except ValueError:return None
        for name,domains in NETWORK_DOMAINS.items():
            if any(host==domain or host.endswith("."+domain) for domain in domains):return name
        return None
    @classmethod
    def _supported_urls(cls,text):
        result=[]
        for raw in re.findall(r"https?://[^\s]+",text or "",re.I):
            url=raw.rstrip(",;.)]}")
            if cls._detect_platform(url):result.append(url)
        return result
    @classmethod
    def _supported_url(cls,text):
        urls=cls._supported_urls(text);return urls[0] if urls else None
    def _update_paste_button(self,text=""):
        url=self._supported_url(text);detected=self._detect_platform(url) if url else None;selected=self.network.get();shown=detected if selected=="Detectar automaticamente" and detected else (selected if selected!="Detectar automaticamente" else "Automático")
        self.paste_btn.configure(image=self.platform_icons[shown],style=NETWORK_STYLES[shown],text="Colar link")
    def _network_changed(self,_event=None):
        try:current=self.clipboard_get().strip()
        except tk.TclError:current=""
        self._update_paste_button(current);self._save_settings()
    def _toggle_clipboard(self):
        try:self.last_clipboard=self.clipboard_get().strip()
        except tk.TclError:self.last_clipboard=""
        self._save_settings();state="ativado" if self.clipboard_watch.get() else "desativado";self.status.set(f"Monitoramento de links {state}")
    def _watch_clipboard(self):
        try:
            current=self.clipboard_get().strip();self._update_paste_button(current)
            if not self.clipboard_watch.get():self.last_clipboard=current
            elif current!=self.last_clipboard:
                self.last_clipboard=current;url=self._supported_url(current);platform=self._detect_platform(url) if url else None;selected=self.network.get();allowed=selected=="Detectar automaticamente" or selected==platform
                if url and allowed and not self.grab_current() and messagebox.askyesno(APP_NAME,f"Link do {platform} detectado.\n\nDeseja adicionar à fila?"):
                    self.urls.delete("1.0","end");self.urls.insert("1.0",url);self._add()
        except tk.TclError:pass
        finally:self.after(1000,self._watch_clipboard)
    def _add(self):
        found=self._supported_urls(self.urls.get("1.0","end"));selected=self.network.get()
        if selected!="Detectar automaticamente":
            matching=[u for u in found if self._detect_platform(u)==selected]
            if found and not matching:messagebox.showwarning(APP_NAME,f"O link colado não pertence à rede selecionada ({selected}).\n\nEscolha Detectar automaticamente ou selecione a rede correta.");return
            found=matching
        if not found:messagebox.showwarning(APP_NAME,"Cole pelo menos um link válido de uma rede compatível.");return
        self.batch_active=True;self._save_settings()
        for url in found:
            i=uuid.uuid4().hex;t={"id":i,"url":url,"platform":self._detect_platform(url),"title":"Analisando link...","mode":self.mode.get(),"quality":self.quality.get(),"speed":self.speed.get(),"folder":self.folder.get(),"output_folder":self.folder.get(),"playlist":False,"is_playlist":False,"is_playlist_item":False,"playlist_title":None,"playlist_index":None,"analyzed":False,"status":"Analisando","size":0,"percent":0.0,"progress":"0%","file":None,"pause":False,"cancel":False,"remove":False}
            self.tasks[i]=t;self.list.insert("","end",iid=i,values=(t["title"],self._profile(t),"—","0%","Analisando"));threading.Thread(target=self._analyze,args=(i,),daemon=True).start()
        platforms=", ".join(sorted({self._detect_platform(u) for u in found}));self.urls.delete("1.0","end");self.status.set(f"{len(found)} item(ns) de {platforms} adicionado(s)")
    def _analyze(self,i):
        t=self.tasks.get(i)
        try:
            with yt_dlp.YoutubeDL({"quiet":True,"no_warnings":True,"noplaylist":False,"extract_flat":"in_playlist"}) as y: info=y.extract_info(t["url"],download=False)
            entries=[e for e in (info.get("entries") or []) if e]
            if entries:
                self.events.put(("playlist_select",i,info.get("title") or info.get("playlist_title") or "Playlist",entries));return
            show=info;size=self._estimate_size(show,t)
            thumb=None
            try:
                req=urllib.request.Request(show.get("thumbnail"),headers={"User-Agent":"Mozilla/5.0"});thumb=urllib.request.urlopen(req,timeout=12).read(2_000_000)
            except Exception:pass
            self.events.put(("ready",i,show.get("title") or "Conteúdo encontrado",size,thumb))
        except Exception as e:self.events.put(("fail",i,str(e)))

    def _playlist_dialog(self,i,title,entries):
        parent=self.tasks.get(i)
        if not parent:return
        win=tk.Toplevel(self);win.title(f"Selecionar vídeos — {title}");win.geometry("760x540");win.minsize(620,420);win.configure(bg="#0b0d17");win.transient(self);win.grab_set()
        box=ttk.Frame(win,padding=18);box.pack(fill="both",expand=True)
        ttk.Label(box,text=title,font=("Segoe UI Semibold",17)).pack(anchor="w");ttk.Label(box,text=f"{len(entries)} vídeos encontrados. Selecione os que deseja baixar.",style="Muted.TLabel").pack(anchor="w",pady=(3,12))
        tree=ttk.Treeview(box,columns=("number","title","duration"),show="headings",selectmode="extended",style="Picker.Treeview")
        tree.heading("number",text="#");tree.heading("title",text="Título");tree.heading("duration",text="Duração");tree.column("number",width=55,anchor="center",stretch=False);tree.column("title",width=560);tree.column("duration",width=90,anchor="center",stretch=False)
        bar=ttk.Scrollbar(box,orient="vertical",command=tree.yview);tree.configure(yscrollcommand=bar.set);bar.pack(side="right",fill="y");tree.pack(fill="both",expand=True)
        for pos,e in enumerate(entries):
            seconds=int(e.get("duration") or 0);duration=f"{seconds//60}:{seconds%60:02d}" if seconds else "—"
            tree.insert("","end",iid=str(pos),values=(e.get("playlist_index") or pos+1,e.get("title") or "Vídeo sem título",duration))
        tree.selection_set(*tree.get_children())
        buttons=ttk.Frame(box);buttons.pack(fill="x",pady=(12,0))
        ttk.Button(buttons,text="Selecionar todos",command=lambda:tree.selection_set(*tree.get_children())).pack(side="left",padx=(0,7));ttk.Button(buttons,text="Desmarcar todos",command=lambda:tree.selection_remove(*tree.get_children())).pack(side="left")
        def cancel():self._remove_task(i);win.destroy();self.status.set("Seleção da playlist cancelada")
        def confirm():
            chosen=sorted((int(x) for x in tree.selection()))
            if not chosen:messagebox.showwarning(APP_NAME,"Selecione pelo menos um vídeo.",parent=win);return
            win.destroy();self._expand_playlist(i,title,entries,chosen)
        ttk.Button(buttons,text="Cancelar",command=cancel).pack(side="right");ttk.Button(buttons,text="ADICIONAR SELECIONADOS",style="Accent.TButton",command=confirm).pack(side="right",padx=(0,7));win.protocol("WM_DELETE_WINDOW",cancel)
        win.wait_window()

    def _expand_playlist(self,i,title,entries,chosen):
        parent=self.tasks.get(i)
        if not parent:return
        output_folder=str(Path(parent["folder"])/self._safe_folder(title));self._remove_task(i)
        added=0
        for pos in chosen:
            entry=entries[pos];video_id=entry.get("id");url=entry.get("webpage_url") or (f"https://www.youtube.com/watch?v={video_id}" if video_id else entry.get("url"))
            if not url:continue
            size=self._estimate_size(entry,parent);item_id=uuid.uuid4().hex
            t={**parent,"id":item_id,"url":url,"title":entry.get("title") or "Vídeo sem título","output_folder":output_folder,"is_playlist":False,"is_playlist_item":True,"playlist_title":title,"playlist_index":entry.get("playlist_index") or pos+1,"analyzed":False,"status":"Na fila","size":size,"percent":0.0,"progress":"0%","file":None,"pause":False,"cancel":False,"remove":False}
            t["status"]="Analisando";self.tasks[item_id]=t;self.list.insert("","end",iid=item_id,values=(t["title"],self._profile(t),self._human(size),"0%","Analisando"));self.analysis.put(item_id);added+=1
        if added:self.batch_active=True
        self._refresh_playlist_summary();self.status.set(f"{added} vídeo(s) da playlist adicionado(s)")

    def _analysis_worker(self):
        while True:
            i=self.analysis.get();t=self.tasks.get(i)
            if not t or t["status"]!="Analisando":continue
            try:
                with yt_dlp.YoutubeDL({"quiet":True,"no_warnings":True,"noplaylist":True}) as y:info=y.extract_info(t["url"],download=False)
                size=self._estimate_size(info,t)
                self.events.put(("item_ready",i,info.get("title") or t["title"],size,info.get("thumbnail")))
            except Exception as e:self.events.put(("fail",i,str(e)))

    def _load_thumb(self,i,url):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"});data=urllib.request.urlopen(req,timeout=12).read(2_000_000);self.events.put(("thumb",i,data))
        except Exception:pass

    def _worker(self):
        while True:
            i=self.work.get();t=self.tasks.get(i)
            if not t or t["status"]!="Na fila":continue
            with self.download_condition:
                while len(self.active)>=self.download_limit:self.download_condition.wait()
                if not self.tasks.get(i) or t["status"]!="Na fila":continue
                self.active.add(i)
            threading.Thread(target=self._run_download,args=(i,),daemon=True).start()
    def _run_download(self,i):
        try:
            t=self.tasks.get(i)
            if t:self._download(t)
        finally:
            with self.download_condition:self.active.discard(i);self.download_condition.notify_all()
            self.events.put(("finished",i))
    def _download(self,t):
        t.update(status="Baixando",pause=False,cancel=False);self.events.put(("update",t["id"]));done,totals={},{}
        def hook(d):
            if t["pause"] or t["cancel"]:raise yt_dlp.utils.DownloadCancelled("Interrompido")
            if d.get("status")=="downloading":
                name=d.get("filename") or str(id(d.get("info_dict")));done[name]=d.get("downloaded_bytes",0);total=d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                if total:totals[name]=total
                got=sum(done.values());full=max(sum(totals.values()),t.get("size") or 0);pct=min(100,got*100/full) if full else 0
                t["percent"]=pct;t["progress"]=f"{pct:.1f}%  {self._human(got)}/{self._human(full)}";t["status"]=(d.get("_speed_str","").strip()+"  "+d.get("_eta_str","").strip()).strip() or "Baixando";self.events.put(("update",t["id"]))
        try:
            folder=Path(t["folder"]);folder.mkdir(parents=True,exist_ok=True)
            if t.get("is_playlist") or t.get("is_playlist_item"):
                output_folder=Path(t.get("output_folder") or folder/self._safe_folder(t.get("playlist_title")))
            else:output_folder=folder
            output_folder.mkdir(parents=True,exist_ok=True);t["output_folder"]=str(output_folder)
            prefix=f"{int(t.get('playlist_index') or 0):03d} - " if t.get("is_playlist_item") else ("%(playlist_index)03d - " if t.get("is_playlist") else "")
            opts={"outtmpl":str(output_folder/(prefix+"%(title)s [%(id)s].%(ext)s")),"noplaylist":not t["playlist"],"windowsfilenames":True,"progress_hooks":[hook],"ffmpeg_location":imageio_ffmpeg.get_ffmpeg_exe(),"quiet":True,"no_warnings":True,"continuedl":True}
            if SPEEDS.get(t.get("speed")):opts["ratelimit"]=SPEEDS[t["speed"]]
            if t["mode"]=="Áudio MP3":opts.update({"format":"bestaudio/best","writethumbnail":True,"postprocessor_hooks":[self._metadata_hook],"postprocessors":[{"key":"FFmpegExtractAudio","preferredcodec":"mp3","preferredquality":str(AUDIO_BITRATES.get(t["quality"],192))},{"key":"FFmpegMetadata","add_metadata":True},{"key":"EmbedThumbnail"}]})
            else:
                h=HEIGHTS.get(t["quality"]);opts["format"]=f"bv*[height<={h}]+ba/b[height<={h}]" if h else "bv*+ba/b";opts["merge_output_format"]="mp4"
            started=time.time()
            with yt_dlp.YoutubeDL(opts) as y:y.download([t["url"]])
            matches=[p for p in output_folder.rglob("*") if p.is_file() and p.stat().st_mtime>=started-3 and p.suffix.lower() not in (".part",".ytdl")]
            t["file"]=str(max(matches,key=lambda p:p.stat().st_mtime)) if matches else None;t["percent"]=100.0;t["progress"]="100%";t["status"]="Concluído"
        except yt_dlp.utils.DownloadCancelled:t["status"]="Pausado" if t["pause"] else "Cancelado"
        except Exception as e:self._set_error(t,e)
        self.events.put(("update",t["id"]));
        if t.get("remove"):self.events.put(("remove",t["id"]))

    def _row(self,i):
        t=self.tasks.get(i)
        if t and self.list.exists(i):
            shown=f"Erro: {t.get('error_label','Falha')}" if t["status"] in ("Erro","Erro na análise") else t["status"]
            self.list.item(i,values=(t["title"],self._profile(t),self._human(t.get("size")),t["progress"],shown))
        self._refresh_playlist_summary()
    def _refresh_playlist_summary(self):
        items=[t for t in self.tasks.values() if t.get("is_playlist_item")]
        if not items:self.playlist_status.set("");return
        done=sum(t["status"]=="Concluído" for t in items);percent=sum(float(t.get("percent",0)) for t in items)/len(items);names={t.get("playlist_title") for t in items}
        label="Playlist" if len(names)==1 else "Playlists";self.playlist_status.set(f"{label}: {done}/{len(items)} concluídos  •  {percent:.0f}%")
    def _check_queue_finished(self):
        if not self.batch_active:return
        with self.download_condition:active=bool(self.active)
        waiting=any(t["status"] in ("Analisando","Na fila","Pausado","Pausando...","Cancelando...") for t in self.tasks.values())
        if active or waiting:return
        if not self.tasks:self.batch_active=False;return
        completed=sum(t["status"]=="Concluído" for t in self.tasks.values());errors=sum(t["status"] in ("Erro","Erro na análise") for t in self.tasks.values());self.batch_active=False
        try:
            if winsound:winsound.MessageBeep(winsound.MB_ICONASTERISK)
            else:self.bell()
        except Exception:pass
        detail=f"{completed} download(s) concluído(s)."+(f"\n{errors} item(ns) com erro." if errors else "")
        messagebox.showinfo(APP_NAME,"A fila de downloads terminou!\n\n"+detail)
    def _poll(self):
        try:
            while True:
                e=self.events.get_nowait();kind,i=e[0],e[1];t=self.tasks.get(i)
                if kind=="convert_update":
                    self._convert_row(i);ct=self.convert_tasks.get(i)
                    if ct and ct["status"]=="Concluído":self.convert_status.set(f"Concluído: {ct['title']}")
                    elif ct and ct["status"]=="Erro":self.convert_status.set(f"Erro ao converter: {ct['title']}")
                elif kind=="ready" and t:
                    t.update(title=e[2],size=e[3],status="Na fila",analyzed=True)
                    if e[4]:
                        try:im=Image.open(io.BytesIO(e[4])).convert("RGB");im.thumbnail((112,63));ph=ImageTk.PhotoImage(im);self.images[i]=ph;self.list.item(i,image=ph)
                        except Exception:pass
                    self._row(i);self.work.put(i)
                elif kind=="playlist_select" and t:self._playlist_dialog(i,e[2],e[3])
                elif kind=="item_ready" and t and t["status"]=="Analisando":
                    t.update(title=e[2],size=e[3],status="Na fila",analyzed=True);self._row(i);self.work.put(i)
                    if e[4]:threading.Thread(target=self._load_thumb,args=(i,e[4]),daemon=True).start()
                elif kind=="thumb" and t:
                    try:im=Image.open(io.BytesIO(e[2])).convert("RGB");im.thumbnail((112,63));ph=ImageTk.PhotoImage(im);self.images[i]=ph;self.list.item(i,image=ph)
                    except Exception:pass
                elif kind=="fail" and t and t["status"]=="Analisando":self._set_error(t,e[2],analysis=True);self._row(i)
                elif kind=="update":self._row(i)
                elif kind=="finished":self._row(i)
                elif kind=="remove":self._remove_task(i)
                elif kind=="update_available":
                    self.update_url,self.checksum_url=e[2],e[3];self.status.set(f"Nova versão {e[1]} disponível")
                    self.update_btn.configure(state="normal",text="ATUALIZAR AGORA",command=self._start_update,style="Accent.TButton")
                elif kind=="update_status":
                    self.status.set(e[1]);self.update_btn.configure(state="normal",text="Verificar atualizações",command=self._check_updates,style="TButton")
                elif kind=="update_error":
                    self.update_btn.configure(state="normal",text="Tentar atualizar novamente",command=self._start_update)
                    messagebox.showerror(APP_NAME,"Não foi possível atualizar:\n\n"+e[1])
        except queue.Empty:pass
        self._check_queue_finished()
        self.after(100,self._poll)

    def _pause(self):
        t=self.tasks.get(self._sel())
        if t and t["status"] not in ("Concluído","Cancelado","Erro"):
            if t["id"] in self.active:t["pause"]=True;t["status"]="Pausando..."
            elif t["status"] in ("Na fila","Analisando"):t["status"]="Pausado"
            self._row(t["id"])
    def _resume(self):
        t=self.tasks.get(self._sel())
        if t and t["status"] in ("Pausado","Cancelado","Erro","Erro na análise"):
            self.batch_active=True
            t.update(pause=False,cancel=False,error=None,error_label=None,error_help=None,status="Na fila" if t.get("analyzed") else "Analisando");self._row(t["id"])
            (self.work if t.get("analyzed") else self.analysis).put(t["id"])
    def _pause_all(self):
        changed=0
        for t in self.tasks.values():
            if t["id"] in self.active:
                t["pause"]=True;t["status"]="Pausando...";changed+=1;self._row(t["id"])
            elif t["status"] in ("Na fila","Analisando"):
                t["status"]="Pausado";changed+=1;self._row(t["id"])
        self.status.set(f"{changed} item(ns) pausado(s)" if changed else "Não há downloads para pausar")
    def _resume_all(self):
        paused=[t for t in self.tasks.values() if t["status"]=="Pausado"]
        if paused:self.batch_active=True
        for t in paused:
            t.update(pause=False,cancel=False,error=None,error_label=None,error_help=None,status="Na fila" if t.get("analyzed") else "Analisando");self._row(t["id"])
            (self.work if t.get("analyzed") else self.analysis).put(t["id"])
        self.status.set(f"{len(paused)} item(ns) retomado(s)" if paused else "Não há downloads pausados")
    def _cancel(self):
        t=self.tasks.get(self._sel())
        if t:t["cancel"]=True;t["status"]="Cancelando..." if t["id"] in self.active else "Cancelado";self._row(t["id"]);self._check_queue_finished()
    def _retry(self):
        t=self.tasks.get(self._sel())
        if t and t["id"] not in self.active and t["status"] not in ("Analisando","Na fila"):
            self.batch_active=True
            t.update(pause=False,cancel=False,error=None,error_label=None,error_help=None,percent=0.0,progress="0%",status="Na fila" if t.get("analyzed") else "Analisando");self._row(t["id"])
            (self.work if t.get("analyzed") else self.analysis).put(t["id"])
    def _remove(self):
        t=self.tasks.get(self._sel())
        if t:
            if t["id"] in self.active:t["cancel"]=True;t["remove"]=True
            else:self._remove_task(t["id"])
    def _remove_task(self,i):
        if self.list.exists(i):self.list.delete(i)
        self.tasks.pop(i,None);self.images.pop(i,None);self._refresh_playlist_summary()
    def _clear_completed(self):
        completed=[i for i,t in self.tasks.items() if t["status"] in ("Concluído","Arquivo excluído")]
        for i in completed:self._remove_task(i)
        self.status.set(f"{len(completed)} item(ns) concluído(s) removido(s) da fila")
    def _show(self):
        t=self.tasks.get(self._sel());p=Path(t["file"]) if t and t.get("file") else None
        if not p or not p.exists():messagebox.showinfo(APP_NAME,"Esse item ainda não possui um arquivo concluído.");return
        subprocess.Popen(["explorer","/select,",str(p)])
    def _open_selected(self):
        t=self.tasks.get(self._sel())
        if t and t["status"] in ("Erro","Erro na análise"):self._show_error()
        else:self._show()
    @staticmethod
    def _error_info(error):
        raw=str(error or "");low=raw.lower()
        cases=(
            (("private video","vídeo privado","video is private"),"Vídeo privado","Esse vídeo é privado e não pode ser baixado sem acesso."),
            (("age-restricted","confirm your age","sign in to confirm your age"),"Restrição de idade","A rede social exige confirmação de idade ou login para acessar esse vídeo."),
            (("requested format is not available","format is not available"),"Qualidade indisponível","A qualidade escolhida não existe para esse vídeo. Tente outra qualidade."),
            (("video unavailable","not available","has been removed","this video is unavailable"),"Vídeo indisponível","O vídeo foi removido, bloqueado na sua região ou não está disponível publicamente."),
            (("no space left","disk full","not enough space"),"Sem espaço no disco","Libere espaço na unidade de destino e tente novamente."),
            (("timed out","timeout","name resolution","connection reset","network is unreachable"),"Problema de conexão","Verifique sua internet e tente novamente."),
            (("http error 403","forbidden","access denied"),"Acesso negado","O servidor recusou o acesso. Tente novamente mais tarde ou atualize o aplicativo."),
            (("ffmpeg","postprocessing"),"Erro de conversão","O download ocorreu, mas houve uma falha ao converter ou incorporar os dados do arquivo."),
        )
        for needles,label,help_text in cases:
            if any(x in low for x in needles):return label,help_text
        return "Falha no download","Não foi possível concluir este item. Consulte os detalhes técnicos abaixo ou tente novamente."
    def _set_error(self,t,error,analysis=False):
        label,help_text=self._error_info(error);t.update(status="Erro na análise" if analysis else "Erro",error=str(error),error_label=label,error_help=help_text)
    def _show_error(self):
        t=self.tasks.get(self._sel())
        if not t or not t.get("error"):
            messagebox.showinfo(APP_NAME,"Este item não possui detalhes de erro.");return
        win=tk.Toplevel(self);win.title("Detalhes do erro");win.geometry("700x430");win.minsize(560,360);win.configure(bg="#0b0d17");win.transient(self)
        box=ttk.Frame(win,padding=20);box.pack(fill="both",expand=True)
        ttk.Label(box,text=t.get("error_label") or "Falha no download",font=("Segoe UI Semibold",17)).pack(anchor="w")
        ttk.Label(box,text=t.get("error_help") or "",style="Muted.TLabel",wraplength=650,justify="left").pack(anchor="w",fill="x",pady=(5,14))
        ttk.Label(box,text="Detalhes técnicos:").pack(anchor="w")
        detail=tk.Text(box,height=11,bg="#0d1020",fg="#d8d5e8",insertbackground="white",relief="flat",font=("Consolas",9),padx=10,pady=10,wrap="word");detail.pack(fill="both",expand=True,pady=(5,12));detail.insert("1.0",t["error"]);detail.configure(state="disabled")
        buttons=ttk.Frame(box);buttons.pack(fill="x")
        def copy_details():self.clipboard_clear();self.clipboard_append(t["error"]);self.status.set("Detalhes do erro copiados")
        ttk.Button(buttons,text="Copiar detalhes",command=copy_details).pack(side="left");ttk.Button(buttons,text="Fechar",command=win.destroy).pack(side="right")
    def _open_folder(self):
        t=self.tasks.get(self._sel());p=Path(t.get("output_folder",t["folder"]) if t else self.folder.get());p.mkdir(parents=True,exist_ok=True);os.startfile(p)
    def _delete_file(self):
        t=self.tasks.get(self._sel());p=Path(t["file"]) if t and t.get("file") else None
        if not p or not p.exists():messagebox.showinfo(APP_NAME,"O arquivo não foi encontrado.");return
        if messagebox.askyesno(APP_NAME,f"Excluir permanentemente?\n\n{p.name}"):
            try:p.unlink();t["file"]=None;t["status"]="Arquivo excluído";self._row(t["id"])
            except OSError as e:messagebox.showerror(APP_NAME,f"Não foi possível excluir:\n{e}")
    def _choose(self):
        p=filedialog.askdirectory(initialdir=self.folder.get())
        if p:self.folder.set(p);self._save_settings()
    def _right(self,e):
        i=self.list.identify_row(e.y)
        if i:self.list.selection_set(i);self.menu.tk_popup(e.x_root,e.y_root)
    def _popup(self):
        if not self._sel():messagebox.showinfo(APP_NAME,"Selecione um item da fila.");return
        self.menu.tk_popup(*self.winfo_pointerxy())

    @staticmethod
    def _version_tuple(value):
        return tuple(int(x) for x in re.findall(r"\d+",value)[:3])
    def _check_updates(self):
        self.update_btn.configure(state="disabled",text="Verificando...");threading.Thread(target=self._check_updates_thread,daemon=True).start()
    def _check_updates_thread(self):
        try:
            req=urllib.request.Request(RELEASE_API,headers={"User-Agent":f"{APP_NAME}/{APP_VERSION}","Accept":"application/vnd.github+json"})
            with urllib.request.urlopen(req,timeout=15) as response:data=json.load(response)
            latest=str(data.get("tag_name","")).lstrip("vV");assets={a.get("name"):a.get("browser_download_url") for a in data.get("assets",[])}
            package="EclipseDownloader-Portatil-Windows.zip";checksum=package+".sha256"
            if latest and self._version_tuple(latest)>self._version_tuple(APP_VERSION) and assets.get(package) and assets.get(checksum):self.events.put(("update_available",latest,assets[package],assets[checksum]))
            else:self.events.put(("update_status","Você já está usando a versão mais recente"))
        except Exception:self.events.put(("update_status","Não foi possível verificar atualizações agora"))
    def _start_update(self):
        if not self.update_url or not self.checksum_url:return
        self._save_settings();self.update_btn.configure(state="disabled",text="Baixando atualização...");threading.Thread(target=self._update_thread,daemon=True).start()
    def _update_thread(self):
        try:
            tmp=Path(tempfile.mkdtemp(prefix="eclipse-update-"));package=tmp/"update.zip"
            req=urllib.request.Request(self.update_url,headers={"User-Agent":f"{APP_NAME}/{APP_VERSION}"})
            with urllib.request.urlopen(req,timeout=120) as src,package.open("wb") as dst:
                while True:
                    chunk=src.read(1024*1024)
                    if not chunk:break
                    dst.write(chunk)
            req=urllib.request.Request(self.checksum_url,headers={"User-Agent":f"{APP_NAME}/{APP_VERSION}"})
            with urllib.request.urlopen(req,timeout=20) as response:expected=response.read().decode().strip().split()[0].lower()
            actual=hashlib.sha256(package.read_bytes()).hexdigest().lower()
            if actual!=expected:raise ValueError("A verificação de segurança do arquivo falhou.")
            with zipfile.ZipFile(package) as archive:archive.extractall(tmp/"new")
            new_exe=tmp/"new"/"Eclipse Downloader.exe";current=Path(sys.executable).resolve()
            if not new_exe.exists():raise FileNotFoundError("O executável não foi encontrado no pacote.")
            if current.suffix.lower()!=".exe":raise RuntimeError("A atualização automática funciona apenas no aplicativo portátil.")
            script=tmp/"atualizar.bat";pid=os.getpid();parent_pid=os.getppid()
            script.write_text(f'@echo off\r\n:wait_child\r\ntasklist /FI "PID eq {pid}" | find "{pid}" >nul\r\nif not errorlevel 1 (timeout /t 1 /nobreak >nul & goto wait_child)\r\n:wait_parent\r\ntasklist /FI "PID eq {parent_pid}" | find "{parent_pid}" >nul\r\nif not errorlevel 1 (timeout /t 1 /nobreak >nul & goto wait_parent)\r\ntimeout /t 2 /nobreak >nul\r\ncopy /Y "{new_exe}" "{current}" >nul\r\nset PYINSTALLER_RESET_ENVIRONMENT=1\r\nstart "" "{current}"\r\ndel "%~f0"\r\n',encoding="ascii")
            subprocess.Popen(["cmd","/c",str(script)],creationflags=0x08000000);self.after(200,self.destroy)
        except Exception as exc:self.events.put(("update_error",str(exc)))

if __name__=="__main__":App().mainloop()
