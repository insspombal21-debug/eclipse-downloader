import hashlib, io, json, os, queue, re, subprocess, sys, tempfile, threading, time, tkinter as tk, urllib.request, uuid, zipfile
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import imageio_ffmpeg, yt_dlp
from PIL import Image, ImageDraw, ImageTk
try:import winsound
except ImportError:winsound=None

APP_NAME = "Eclipse Flow"
APP_VERSION = "5.4.0"
RELEASE_API = "https://api.github.com/repos/insspombal21-debug/eclipse-downloader/releases/latest"
HEIGHTS = {"Melhor disponível": None, "2160p (4K)": 2160, "1440p": 1440, "1080p": 1080, "720p": 720, "480p": 480, "360p": 360}
AUDIO_BITRATES = {"320 kbps": 320, "256 kbps": 256, "192 kbps": 192, "128 kbps": 128}
SPEEDS = {"Sem limite": None, "500 KB/s": 500*1024, "1 MB/s": 1024**2, "2 MB/s": 2*1024**2, "5 MB/s": 5*1024**2, "10 MB/s": 10*1024**2}

class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title(APP_NAME); self.geometry("1080x720"); self.minsize(920, 620); self.configure(bg="#0b0d17")
        self.settings_file=Path(os.getenv("APPDATA") or Path.home())/APP_NAME/"config.json";saved=self._load_settings()
        mode=saved.get("mode") if saved.get("mode") in ("Vídeo MP4","Áudio MP3") else "Vídeo MP4";valid_quality=AUDIO_BITRATES if mode=="Áudio MP3" else HEIGHTS
        quality=saved.get("quality") if saved.get("quality") in valid_quality else ("192 kbps" if mode=="Áudio MP3" else "1080p");speed=saved.get("speed") if saved.get("speed") in SPEEDS else "Sem limite";concurrent=str(saved.get("concurrent","1"));concurrent=concurrent if concurrent in ("1","2","3") else "1"
        self.events, self.work, self.analysis = queue.Queue(), queue.Queue(), queue.Queue(); self.tasks, self.images = {}, {}; self.active=set();self.download_condition=threading.Condition();self.download_limit=int(concurrent);self.batch_active=False
        self.mode, self.quality = tk.StringVar(value=mode), tk.StringVar(value=quality)
        self.folder = tk.StringVar(value=saved.get("folder") or str(Path.home()/"Downloads")); self.speed = tk.StringVar(value=speed);self.concurrent=tk.StringVar(value=concurrent);self.status = tk.StringVar(value="Cole links para começar");self.playlist_status=tk.StringVar(value="")
        self.update_url = self.checksum_url = None
        self._style(); self._ui(); self.after(100, self._poll); threading.Thread(target=self._worker, daemon=True).start()
        for _ in range(2):threading.Thread(target=self._analysis_worker,daemon=True).start()
        self.protocol("WM_DELETE_WINDOW",self._close);self.after(1800, self._check_updates)

    def _load_settings(self):
        try:return json.loads(self.settings_file.read_text(encoding="utf-8"))
        except (OSError,ValueError):return {}
    def _save_settings(self):
        try:
            data={"mode":self.mode.get(),"quality":self.quality.get(),"speed":self.speed.get(),"concurrent":self.concurrent.get(),"folder":self.folder.get()};self.settings_file.parent.mkdir(parents=True,exist_ok=True)
            temp=self.settings_file.with_suffix(".tmp");temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8");temp.replace(self.settings_file)
        except OSError:pass
    def _close(self):self._save_settings();self.destroy()
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

    def _style(self):
        s=ttk.Style(self); s.theme_use("clam"); s.configure("TFrame",background="#0b0d17"); s.configure("Card.TFrame",background="#17152b")
        s.configure("TLabel",background="#0b0d17",foreground="#f4f2ff",font=("Segoe UI",10)); s.configure("Card.TLabel",background="#17152b",foreground="#f4f2ff")
        s.configure("Title.TLabel",font=("Segoe UI Semibold",25),foreground="white"); s.configure("Muted.TLabel",foreground="#aaa6c3")
        s.configure("TButton",font=("Segoe UI Semibold",10),padding=9,background="#24213d",foreground="#f4f2ff"); s.configure("Accent.TButton",background="#ec4899",foreground="white",borderwidth=0)
        s.map("Accent.TButton",background=[("active","#f472b6")]); s.configure("TEntry",fieldbackground="#0d1020",foreground="white",padding=8)
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
        top=ttk.Frame(out,style="Card.TFrame",padding=16); top.pack(fill="x"); row=ttk.Frame(top,style="Card.TFrame"); row.pack(fill="x")
        self.urls=tk.Text(row,height=2,bg="#0d1020",fg="white",insertbackground="#ec4899",relief="flat",font=("Segoe UI",11),padx=10,pady=9); self.urls.pack(side="left",fill="x",expand=True)
        ttk.Button(row,text="COLAR",command=self._paste).pack(side="left",padx=(8,0)); ttk.Button(row,text="ADICIONAR À FILA",style="Accent.TButton",command=self._add).pack(side="left",padx=(8,0))
        cfg=ttk.Frame(top,style="Card.TFrame"); cfg.pack(fill="x",pady=(12,0)); ttk.Label(cfg,text="Formato:",style="Card.TLabel").pack(side="left")
        self.mode_box=ttk.Combobox(cfg,textvariable=self.mode,state="readonly",width=15,values=["Vídeo MP4","Áudio MP3"]);self.mode_box.pack(side="left",padx=(6,16));self.mode_box.bind("<<ComboboxSelected>>",self._mode_changed);ttk.Label(cfg,text="Qualidade:",style="Card.TLabel").pack(side="left")
        quality_values=AUDIO_BITRATES if self.mode.get()=="Áudio MP3" else HEIGHTS;self.quality_box=ttk.Combobox(cfg,textvariable=self.quality,state="readonly",width=18,values=list(quality_values));self.quality_box.pack(side="left",padx=(6,16));self.quality_box.bind("<<ComboboxSelected>>",lambda _e:self._save_settings());ttk.Label(cfg,text="✓ Playlists detectadas automaticamente",style="Card.TLabel").pack(side="right")
        perf=ttk.Frame(top,style="Card.TFrame");perf.pack(fill="x",pady=(10,0));ttk.Label(perf,text="Limite de velocidade:",style="Card.TLabel").pack(side="left");self.speed_box=ttk.Combobox(perf,textvariable=self.speed,state="readonly",width=12,values=list(SPEEDS));self.speed_box.pack(side="left",padx=(6,18));self.speed_box.bind("<<ComboboxSelected>>",lambda _e:self._save_settings());ttk.Label(perf,text="Downloads simultâneos:",style="Card.TLabel").pack(side="left");self.concurrent_box=ttk.Combobox(perf,textvariable=self.concurrent,state="readonly",width=5,values=("1","2","3"));self.concurrent_box.pack(side="left",padx=6);self.concurrent_box.bind("<<ComboboxSelected>>",self._concurrency_changed)
        dest=ttk.Frame(top,style="Card.TFrame");dest.pack(fill="x",pady=(10,0));ttk.Label(dest,text="Salvar em:",style="Card.TLabel").pack(side="left");ttk.Label(dest,textvariable=self.folder,style="Card.TLabel").pack(side="left",padx=8);ttk.Button(dest,text="Escolher pasta",command=self._choose).pack(side="right")
        card=ttk.Frame(out,style="Card.TFrame",padding=12); card.pack(fill="both",expand=True,pady=(14,0));head=ttk.Frame(card,style="Card.TFrame");head.pack(fill="x",pady=(0,8));ttk.Label(head,text="FILA DE DOWNLOADS",style="Card.TLabel",font=("Segoe UI Semibold",11)).pack(side="left");ttk.Label(head,textvariable=self.playlist_status,style="Card.TLabel",foreground="#c4b5fd").pack(side="right")
        cols=("title","profile","size","progress","status"); self.list=ttk.Treeview(card,columns=cols,show="tree headings",style="Queue.Treeview",selectmode="browse")
        for col,title in zip(("#0",)+cols,("Miniatura","Título","Formato","Tamanho","Progresso","Status")): self.list.heading(col,text=title)
        self.list.column("#0",width=125,stretch=False,anchor="center"); self.list.column("title",width=330); self.list.column("profile",width=115,anchor="center")
        self.list.column("size",width=105,anchor="center"); self.list.column("progress",width=190,anchor="center"); self.list.column("status",width=130,anchor="center")
        bar=ttk.Scrollbar(card,orient="vertical",command=self.list.yview); self.list.configure(yscrollcommand=bar.set); bar.pack(side="right",fill="y"); self.list.pack(fill="both",expand=True)
        self.list.bind("<Button-3>",self._right); self.list.bind("<Double-1>",lambda _e:self._show())
        acts=ttk.Frame(out); acts.pack(fill="x",pady=(12,0))
        for label,cmd in (("Pausar",self._pause),("Continuar",self._resume),("Cancelar",self._cancel),("Baixar novamente",self._retry),("Mostrar arquivo",self._show),("Limpar concluídos",self._clear_completed),("⋮ Ações",self._popup)):
            ttk.Button(acts,text=label,command=cmd).pack(side="left",padx=(0,7))
        ttk.Label(acts,textvariable=self.status,style="Muted.TLabel").pack(side="right")
        self.menu=tk.Menu(self,tearoff=False); self.menu.add_command(label="Mostrar arquivo na pasta",command=self._show); self.menu.add_command(label="Abrir pasta de destino",command=self._open_folder)
        self.menu.add_command(label="Baixar novamente",command=self._retry); self.menu.add_separator(); self.menu.add_command(label="Remover da fila",command=self._remove); self.menu.add_command(label="Excluir arquivo do computador",command=self._delete_file)

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
    def _mode_changed(self,_event=None):
        audio=self.mode.get()=="Áudio MP3";values=list(AUDIO_BITRATES if audio else HEIGHTS);self.quality_box.configure(values=values)
        if self.quality.get() not in values:self.quality.set("192 kbps" if audio else "1080p")
        self._save_settings()
    def _safe_folder(self,name):
        clean=re.sub(r'[<>:"/\\|?*\x00-\x1f]',"_",name or "Playlist").strip(" .")[:150] or "Playlist"
        if clean.upper().split(".")[0] in {"CON","PRN","AUX","NUL",*(f"COM{x}" for x in range(1,10)),*(f"LPT{x}" for x in range(1,10))}:clean="_"+clean
        return clean

    def _paste(self):
        try:self.urls.delete("1.0","end");self.urls.insert("1.0",self.clipboard_get().strip())
        except tk.TclError:pass
    def _add(self):
        found=[u.rstrip(",;)") for u in re.findall(r"https?://[^\s]+",self.urls.get("1.0","end")) if re.match(r"^https?://([\w-]+\.)?(youtube\.com|youtu\.be)/",u,re.I)]
        if not found: messagebox.showwarning(APP_NAME,"Cole pelo menos um link válido do YouTube.");return
        self.batch_active=True;self._save_settings()
        for url in found:
            i=uuid.uuid4().hex;t={"id":i,"url":url,"title":"Analisando link...","mode":self.mode.get(),"quality":self.quality.get(),"speed":self.speed.get(),"folder":self.folder.get(),"output_folder":self.folder.get(),"playlist":False,"is_playlist":False,"is_playlist_item":False,"playlist_title":None,"playlist_index":None,"analyzed":False,"status":"Analisando","size":0,"percent":0.0,"progress":"0%","file":None,"pause":False,"cancel":False,"remove":False}
            self.tasks[i]=t;self.list.insert("","end",iid=i,values=(t["title"],self._profile(t),"—","0%","Analisando"));threading.Thread(target=self._analyze,args=(i,),daemon=True).start()
        self.urls.delete("1.0","end");self.status.set(f"{len(found)} item(ns) adicionado(s)")
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
            if t["mode"]=="Áudio MP3":opts.update({"format":"bestaudio/best","postprocessors":[{"key":"FFmpegExtractAudio","preferredcodec":"mp3","preferredquality":str(AUDIO_BITRATES.get(t["quality"],192))}]})
            else:
                h=HEIGHTS.get(t["quality"]);opts["format"]=f"bv*[height<={h}]+ba/b[height<={h}]" if h else "bv*+ba/b";opts["merge_output_format"]="mp4"
            started=time.time()
            with yt_dlp.YoutubeDL(opts) as y:y.download([t["url"]])
            matches=[p for p in output_folder.rglob("*") if p.is_file() and p.stat().st_mtime>=started-3 and p.suffix.lower() not in (".part",".ytdl")]
            t["file"]=str(max(matches,key=lambda p:p.stat().st_mtime)) if matches else None;t["percent"]=100.0;t["progress"]="100%";t["status"]="Concluído"
        except yt_dlp.utils.DownloadCancelled:t["status"]="Pausado" if t["pause"] else "Cancelado"
        except Exception as e:t["status"]="Erro";t["error"]=str(e)
        self.events.put(("update",t["id"]));
        if t.get("remove"):self.events.put(("remove",t["id"]))

    def _row(self,i):
        t=self.tasks.get(i)
        if t and self.list.exists(i):self.list.item(i,values=(t["title"],self._profile(t),self._human(t.get("size")),t["progress"],t["status"]))
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
                if kind=="ready" and t:
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
                elif kind=="fail" and t and t["status"]=="Analisando":t["status"]="Erro na análise";t["error"]=e[2];self._row(i)
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
            elif t["status"]=="Na fila":t["status"]="Pausado"
            self._row(t["id"])
    def _resume(self):
        t=self.tasks.get(self._sel())
        if t and t["status"] in ("Pausado","Cancelado","Erro","Erro na análise"):
            self.batch_active=True
            t.update(pause=False,cancel=False,status="Na fila" if t.get("analyzed") else "Analisando");self._row(t["id"])
            (self.work if t.get("analyzed") else self.analysis).put(t["id"])
    def _cancel(self):
        t=self.tasks.get(self._sel())
        if t:t["cancel"]=True;t["status"]="Cancelando..." if t["id"] in self.active else "Cancelado";self._row(t["id"]);self._check_queue_finished()
    def _retry(self):
        t=self.tasks.get(self._sel())
        if t and t["id"] not in self.active and t["status"] not in ("Analisando","Na fila"):
            self.batch_active=True
            t.update(pause=False,cancel=False,percent=0.0,progress="0%",status="Na fila" if t.get("analyzed") else "Analisando");self._row(t["id"])
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
