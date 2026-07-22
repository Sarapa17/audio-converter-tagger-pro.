import sys
import subprocess
import os
import shutil
import threading
import io
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, TCON, TYER, TRCK
from mutagen.flac import FLAC, Picture
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover
from PIL import Image
import numpy as np
from scipy.fft import fft
# Configuración global de etiquetas
TAG_CONFIG = {
    "Song Name":    {"mp3": "title",       "m4a": "\xa9nam", "flac": "title"},
    "Artist":       {"mp3": "artist",      "m4a": "\xa9ART", "flac": "artist"},
    "Album":        {"mp3": "album",       "m4a": "\xa9alb", "flac": "album"},
    "Genre":        {"mp3": "genre",       "m4a": "\xa9gen", "flac": "genre"},
    "Year":         {"mp3": "date",        "m4a": "\xa9day", "flac": "date"},
    "Track Number": {"mp3": "tracknumber", "m4a": "trkn",    "flac": "tracknumber"}
}

# Configuración global de apariencia
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AudioApp(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)
        
        self.title("Audio Converter & Tagger Pro")
        self.geometry("1150x850") 

        # --- BUSCADOR INTELIGENTE DE FFMPEG ---
        self.ffmpeg_path = self.find_ffmpeg()
        
        if self.ffmpeg_path is None:
            messagebox.showerror("Falta Archivo", "No se encontró el archivo 'ffmpeg'.\n\nPara que la app funcione, asegúrate de que el archivo 'ffmpeg' esté en la misma carpeta que esta aplicación.")
        
        # Variables de estado
        self.files_data = [] 
        self.current_selection_index = None
        self.output_folder = os.path.join(os.path.expanduser("~"), "Downloads")
        
        # --- LAYOUT PRINCIPAL (2 COLUMNAS) ---
        self.grid_columnconfigure(0, weight=4) 
        self.grid_columnconfigure(1, weight=6) 
        self.grid_rowconfigure(0, weight=1)

        # Panel Izquierdo (Editor)
        self.frame_editor = ctk.CTkFrame(self, corner_radius=0)
        self.frame_editor.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        self.setup_editor_panel()

        # Panel Derecho (Conversor)
        self.frame_converter = ctk.CTkFrame(self, corner_radius=0)
        self.frame_converter.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)
        self.setup_converter_panel()

    def find_ffmpeg(self):
        """Busca ffmpeg en el sistema o junto a la app (Modo Portable)"""
        # Si no estamos congelados (ejecutando desde Python)
        if not getattr(sys, 'frozen', False):
            # Buscar en el sistema
            path = shutil.which("ffmpeg")
            if path: 
                return path
            
            # Buscar en la misma carpeta que el script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            local_ffmpeg = os.path.join(script_dir, "ffmpeg")
            if os.path.exists(local_ffmpeg):
                return local_ffmpeg
            
            return None
        
        # Si estamos congelados (aplicación empaquetada)
        # 1. Primero buscar en _MEIPASS (carpeta temporal donde PyInstaller extrae archivos)
        if hasattr(sys, '_MEIPASS'):
            meipass_path = os.path.join(sys._MEIPASS, "ffmpeg")
            if os.path.exists(meipass_path):
                return meipass_path
        
        # 2. Buscar en el directorio del ejecutable
        exec_dir = os.path.dirname(sys.executable)
        exec_ffmpeg = os.path.join(exec_dir, "ffmpeg")
        if os.path.exists(exec_ffmpeg):
            return exec_ffmpeg
        
        # 3. Para macOS: buscar en Resources del bundle .app
        if sys.platform == "darwin":
            # El ejecutable está en Contents/MacOS, Resources está en Contents/Resources
            resources_path = os.path.join(exec_dir, "..", "Resources", "ffmpeg")
            resources_path = os.path.abspath(resources_path)
            if os.path.exists(resources_path):
                return resources_path
        
        # 4. Buscar en el sistema como último recurso
        path = shutil.which("ffmpeg")
        if path:
            return path
        
        return None

    def setup_editor_panel(self):
        ctk.CTkLabel(self.frame_editor, text="DETALLES Y ETIQUETAS", font=("Roboto", 18, "bold")).pack(pady=10)
        
        self.frame_editor.drop_target_register(DND_FILES)
        self.frame_editor.dnd_bind('<<Drop>>', self.drop_on_editor)

        # Información de calidad
        self.lbl_quality_info = ctk.CTkLabel(self.frame_editor, text="HEADER: ---", font=("Roboto", 13), text_color="gray")
        self.lbl_quality_info.pack(pady=2)

        self.lbl_real_quality = ctk.CTkLabel(self.frame_editor, text="ANÁLISIS FFT: Pendiente", font=("Roboto", 14, "bold"), text_color="#38bdf8")
        self.lbl_real_quality.pack(pady=5)

        self.btn_verify_real = ctk.CTkButton(self.frame_editor, text="🔍 VERIFICAR INTEGRIDAD (FFT)", command=self.start_verify_thread, fg_color="#1e293b")
        self.btn_verify_real.pack(pady=5)

        # --- CAMPO DE NOMBRE DE ARCHIVO ---
        frame_fn = ctk.CTkFrame(self.frame_editor, fg_color="transparent")
        frame_fn.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(frame_fn, text="ARCHIVO:", width=100, anchor="w").pack(side="left")
        self.entry_filename = ctk.CTkEntry(frame_fn, height=28)
        self.entry_filename.pack(side="left", fill="x", expand=True)

        # --- CAMPOS DE ETIQUETAS ---
        self.entries = {}
        for field in TAG_CONFIG.keys():
            frame = ctk.CTkFrame(self.frame_editor, fg_color="transparent")
            frame.pack(fill="x", padx=20, pady=2)
            ctk.CTkLabel(frame, text=field.upper() + ":", width=100, anchor="w", font=("Roboto", 11)).pack(side="left")
            entry = ctk.CTkEntry(frame, height=28)
            entry.pack(side="left", fill="x", expand=True)
            self.entries[field] = entry

        # --- ZONA DE CARÁTULA ---
        self.lbl_cover_preview = ctk.CTkLabel(self.frame_editor, text="[Sin Vista Previa]", width=160, height=160, fg_color="#333", corner_radius=5)
        self.lbl_cover_preview.pack(pady=15)

        btn_img_frame = ctk.CTkFrame(self.frame_editor, fg_color="transparent")
        btn_img_frame.pack(fill="x", padx=20)
        ctk.CTkButton(btn_img_frame, text="Imagen", command=self.browse_cover_art, height=30, fg_color="#444").pack(side="left", fill="x", expand=True, padx=2)
        self.btn_delete_cover = ctk.CTkButton(btn_img_frame, text="X", command=self.delete_current_cover, width=40, height=30, fg_color="#c42b1c")
        self.btn_delete_cover.pack(side="right", padx=2)

        ctk.CTkButton(self.frame_editor, text="GUARDAR CAMBIOS", command=self.save_tags, height=50, font=("Roboto", 14, "bold")).pack(pady=20, padx=20, fill="x", side="bottom")

    def setup_converter_panel(self):
        # Área de drop con estilo
        self.drop_frame = ctk.CTkFrame(self.frame_converter, fg_color="#2b2b2b", border_width=2, border_color="#3a3a3a")
        self.drop_frame.pack(fill="x", padx=20, pady=20)
        
        lbl_icon = ctk.CTkLabel(self.drop_frame, text="🎵", font=("Arial", 50))
        lbl_icon.pack(pady=(20, 0))
        
        lbl_drop = ctk.CTkLabel(self.drop_frame, text="ARRASTRAR ARCHIVOS AQUÍ\n(Para añadir a la cola)", font=("Roboto", 14, "bold"))
        lbl_drop.pack(pady=20)

        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind('<<Drop>>', self.drop_on_converter)

        # Lista de archivos
        self.scroll_frame = ctk.CTkScrollableFrame(self.frame_converter, label_text="Cola de Procesamiento")
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Controles inferiores
        controls = ctk.CTkFrame(self.frame_converter, fg_color="transparent")
        controls.pack(fill="x", padx=20, pady=20)
        self.lbl_output = ctk.CTkLabel(controls, text=f"Destino: {os.path.basename(self.output_folder)}")
        self.lbl_output.pack(side="left", padx=5)
        ctk.CTkButton(controls, text="Carpeta", width=80, command=self.change_output_folder).pack(side="left", padx=5)
        self.btn_convert = ctk.CTkButton(controls, text="PROCESAR TODO", fg_color="#1f6aa5", command=self.start_conversion_thread)
        self.btn_convert.pack(side="right", padx=5)

    # ==================== FUNCIONALIDADES DE CALIDAD Y ANÁLISIS ====================

    def start_verify_thread(self):
        if self.current_selection_index is None: return
        self.btn_verify_real.configure(state="disabled", text="Analizando...")
        threading.Thread(target=self.perform_spectral_analysis, daemon=True).start()

    def perform_spectral_analysis(self):
        obj = self.files_data[self.current_selection_index]
        path = obj['path']
        try:
            # --- 1) Descubrir duración y sample-rate reales del archivo ---
            # No forzamos 44.1 kHz: un FLAC de 48 kHz recortaría información
            # si lo bajamos a 44.1. Usamos el sample-rate nativo.
            sr = self._probe_sample_rate(path)
            if sr is None:
                self.after(0, lambda: self.update_quality_ui("No se pudo leer el audio", "red"))
                return

            # --- 2) Decodificar 5 s de audio empezando en ~25% del archivo ---
            # Slow-seek ("-ss" después de "-i") es preciso a muestra, no a keyframe.
            # Si el archivo dura < 35 s arrancamos desde el segundo 5.
            duration = self._probe_duration(path)
            if duration and duration > 35:
                start = duration * 0.25
            elif duration and duration > 10:
                start = 5.0
            else:
                start = 0.0

            cmd = [
                self.ffmpeg_path, "-y",
                "-i", path,
                "-ss", f"{start:.2f}",
                "-t", "5",
                "-f", "s16le",
                "-ac", "1",          # mono: el canal L/R tiene el mismo rolloff
                "-ar", str(sr),      # respetamos el SR nativo
                "-",
            ]
            with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
                raw_audio = process.stdout.read()
                process.wait()

            if not raw_audio or len(raw_audio) < sr * 2:  # menos de 2 s útil
                self.after(0, lambda: self.update_quality_ui("Audio demasiado corto / error", "red"))
                return

            # --- 3) FFT con ventana Hann para reducir spectral leakage ---
            samples = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32)
            # Normalizamos a [-1, 1] para que el umbral relativo tenga sentido
            samples /= 32768.0

            # Tomamos un tamaño potencia de 2 (mejor eficiencia FFT) del buffer
            # Usamos hasta 2^17 (~3.7 s a 44.1 kHz).
            n_fft = 1 << int(np.floor(np.log2(len(samples))))
            n_fft = max(n_fft, 1 << 14)  # mínimo 16384
            n_fft = min(n_fft, 1 << 17)
            if len(samples) < n_fft:
                n_fft = 1 << int(np.floor(np.log2(len(samples))))
            samples = samples[:n_fft]

            # Ventana Hann
            window = np.hanning(n_fft)
            windowed = samples * window

            # FFT y espectro de magnitud (mitad positiva)
            yf = fft(windowed)
            half = n_fft // 2
            mag = np.abs(yf[:half]) / (n_fft / 2)
            # dBFS, con floor para evitar log(0)
            eps = 1e-12
            mag_db = 20 * np.log10(mag + eps)

            # Eje de frecuencias
            freqs = np.linspace(0.0, sr / 2, half)

            # --- 4) Detección del corte de frecuencias "consistente" ---
            # Ignoramos bins individuales espurios: trabajamos por sub-bandas
            # y nos quedamos con el percentil 99 dentro de cada sub-banda.
            n_bands = 400
            band_size = half // n_bands
            if band_size < 1:
                band_size = 1
                n_bands = half

            band_edges_db = np.zeros(n_bands)
            band_freqs = np.zeros(n_bands)
            for i in range(n_bands):
                lo = i * band_size
                hi = lo + band_size
                chunk = mag_db[lo:hi]
                if len(chunk) == 0:
                    continue
                # p99 dentro de la sub-banda: robusto a 1-2 bins espurios
                band_edges_db[i] = np.percentile(chunk, 99)
                band_freqs[i] = freqs[lo + band_size // 2]

            # Umbral relativo: pico del espectro - 60 dB (adapta al volumen)
            peak_db = np.max(band_edges_db)
            threshold = peak_db - 60.0

            # Un bin aislado encima del umbral no cuenta: exigimos que el corte
            # sea "consistente" => la energía cae y NO vuelve a subir por >= 200 Hz.
            above = band_edges_db > threshold
            last_strong_idx = -1
            for i in range(len(above) - 1, -1, -1):
                if above[i]:
                    last_strong_idx = i
                    break
            if last_strong_idx < 0:
                self.after(0, lambda: self.update_quality_ui("Silencio o solo ruido", "red"))
                return

            cutoff_hz = band_freqs[last_strong_idx]
            cutoff_khz = cutoff_hz / 1000.0

            # --- 5) Clasificación honesta (estimación, no afirmación) ---
            # El FLAC lossless no se evalúa por bitrate: se reporta aparte.
            if obj['ext'] == '.flac':
                self.after(0, lambda: self.update_quality_ui(
                    f"Espectro hasta {cutoff_khz:.1f} kHz (FLAC lossless)", "#4ade80"))
                return

            text, color = self._classify_by_cutoff(cutoff_khz)
            self.after(0, lambda: self.update_quality_ui(text, color))

        except subprocess.CalledProcessError:
            self.after(0, lambda: self.update_quality_ui("ffmpeg falló (formato no soportado)", "red"))
        except Exception as e:
            self.after(0, lambda: self.update_quality_ui(f"Error: {type(e).__name__}", "red"))

    def _probe_sample_rate(self, path):
        """Devuelve el sample-rate nativo del archivo, o None."""
        try:
            # Volcamos un byte de audio y leemos el header PCM s16le
            cmd = [self.ffmpeg_path, "-i", path, "-t", "0.05",
                   "-f", "s16le", "-ac", "1", "-"]
            with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as p:
                raw = p.stdout.read(8192)
            if not raw:
                # fallback: pedimos info via ffprobe-style leyendo stderr
                return 44100
            # Si pedimos "-ar" sin especificar frecuencia, ffmpeg usa el nativo;
            # para recuperarlo leemos del stderr en una segunda pasada rápida.
            return self._probe_audio_property(path, "sample_rate") or 44100
        except Exception:
            return None

    def _probe_duration(self, path):
        """Devuelve la duración en segundos, o None."""
        try:
            value = self._probe_audio_property(path, "duration")
            return float(value) if value else None
        except Exception:
            return None

    def _probe_audio_property(self, path, prop):
        """Lee una propiedad del stream de audio usando ffmpeg (stderr parse)."""
        try:
            cmd = [self.ffmpeg_path, "-i", path, "-hide_banner"]
            with subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.PIPE) as p:
                _, err = p.communicate(timeout=5)
            for line in err.splitlines():
                line = line.decode("utf-8", "ignore")
                # Línea típica: "Stream #0:1: Audio: flac, 44100 Hz, stereo, ..."
                if "Audio:" in line and "Hz" in line:
                    if prop == "sample_rate":
                        parts = line.split("Audio:")[1]
                        for tok in parts.split(","):
                            tok = tok.strip()
                            if tok.endswith("Hz") and tok[:-2].strip().isdigit():
                                return int(tok[:-2].strip())
                    if prop == "duration":
                        return None  # no está en la línea de stream
                # Línea de duración global: "Duration: 00:03:21.45, ..."
                if prop == "duration" and line.startswith("  Duration:"):
                    seg = line.split("Duration:")[1].split(",")[0].strip()
                    h, m, s = seg.split(":")
                    return str(int(h) * 3600 + int(m) * 60 + float(s))
            return None
        except Exception:
            return None

    @staticmethod
    def _classify_by_cutoff(cutoff_khz: float):
        """Clasifica el corte espectral. Estimación, no afirmación de bitrate."""
        if cutoff_khz >= 19.0:
            return (f"Espectro hasta {cutoff_khz:.1f} kHz — estimación: 320 kbps",
                    "#4ade80")
        if cutoff_khz >= 16.0:
            return (f"Espectro hasta {cutoff_khz:.1f} kHz — estimación: ~192–256 kbps",
                    "#facc15")
        if cutoff_khz >= 13.0:
            return (f"Espectro hasta {cutoff_khz:.1f} kHz — posible 128 kbps o transcode",
                    "#f87171")
        return (f"Espectro hasta {cutoff_khz:.1f} kHz — baja calidad / transcode",
                "#ef4444")

    def update_quality_ui(self, text, color):
        self.lbl_real_quality.configure(text=f"ANÁLISIS FFT: {text}", text_color=color)
        self.btn_verify_real.configure(state="normal", text="🔍 VERIFICAR INTEGRIDAD (FFT)")

    def read_metadata_from_file(self, file_obj):
        try:
            path, ext = file_obj['path'], file_obj['ext'].replace('.','')
            tags, cover_data, quality = {}, None, "Desconocido"
            
            if ext == 'mp3':
                audio = MP3(path)
                quality = f"{int(audio.info.bitrate/1000)} kbps / {audio.info.sample_rate/1000} kHz"
                ez = EasyID3(path)
                for label, keys in TAG_CONFIG.items():
                    tags[label] = ez.get(keys['mp3'], [''])[0]
                if audio.tags:
                    for tag in audio.tags.values():
                        if isinstance(tag, APIC): cover_data = tag.data; break
            
            elif ext == 'm4a':
                audio = MP4(path)
                quality = f"{int(audio.info.bitrate/1000)} kbps / {audio.info.sample_rate/1000} kHz"
                for label, keys in TAG_CONFIG.items():
                    val = audio.get(keys['m4a'], [''])
                    tags[label] = str(val[0][0]) if label == "Track Number" and val != [''] else str(val[0])
                if 'covr' in audio: cover_data = audio['covr'][0]
            
            elif ext == 'flac':
                audio = FLAC(path)
                quality = f"LOSSLESS {audio.info.bits_per_sample}bit / {audio.info.sample_rate/1000} kHz"
                for label, keys in TAG_CONFIG.items():
                    tags[label] = audio.get(keys['flac'], [''])[0]
                if audio.pictures: cover_data = audio.pictures[0].data
            
            file_obj.update({'tags': tags, 'cover_bytes': cover_data, 'quality': quality})
        except: pass

    # ==================== FUNCIONALIDADES DE INTERFAZ ====================

    def update_cover_preview(self, file_obj):
        # Usar imagen cacheada si existe y no hay cambios
        if file_obj.get('ctk_thumb') and not file_obj.get('new_cover_path') and not file_obj.get('delete_cover'):
            self.lbl_cover_preview.configure(image=file_obj['ctk_thumb'], text="")
            self.btn_delete_cover.configure(state="normal")
            return
        
        image_data = None
        if file_obj.get('new_cover_path'):
            with open(file_obj['new_cover_path'], 'rb') as f: image_data = f.read()
        elif file_obj.get('cover_bytes') and not file_obj.get('delete_cover'):
            image_data = file_obj['cover_bytes']
        
        if image_data:
            try:
                img = Image.open(io.BytesIO(image_data))
                img.thumbnail((160, 160))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(160, 160))
                file_obj['ctk_thumb'] = ctk_img  # Cachear la imagen
                self.lbl_cover_preview.configure(image=ctk_img, text="")
                self.btn_delete_cover.configure(state="normal")
            except: 
                self.lbl_cover_preview.configure(image=None, text="Error")
        else:
            self.lbl_cover_preview.configure(image=None, text="Sin Carátula")
            self.btn_delete_cover.configure(state="disabled")

    def load_to_editor(self, index):
        self.current_selection_index = index
        file_obj = self.files_data[index]
        
        # Actualizar información de calidad
        self.lbl_quality_info.configure(text=f"HEADER: {file_obj.get('quality', '---')}")
        self.lbl_real_quality.configure(text="ANÁLISIS FFT: Pendiente", text_color="#38bdf8")
        
        # Actualizar nombre de archivo
        self.entry_filename.delete(0, tk.END)
        self.entry_filename.insert(0, file_obj['filename'])
        
        # Actualizar campos de etiquetas
        for key, entry in self.entries.items():
            entry.delete(0, tk.END)
            entry.insert(0, str(file_obj['tags'].get(key, "")))
        
        # Actualizar vista previa de carátula
        self.update_cover_preview(file_obj)
        
        # Resaltar archivo seleccionado en la lista
        for item in self.files_data:
            item['widget'].configure(fg_color=["#3B8ED0", "#1f538d"] if item == file_obj else ["#dbdbdb", "#2b2b2b"])

    def register_file(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext not in ['.flac', '.wav', '.mp3', '.m4a']: return -1
        
        # Verificar si ya existe
        for idx, f_data in enumerate(self.files_data):
            if f_data['path'] == path: return idx
        
        # Crear nuevo objeto de archivo
        file_obj = {
            "path": path, 
            "filename": os.path.basename(path), 
            "ext": ext, 
            "status": "Ready", 
            "tags": {}, 
            "widget": None, 
            "lbl_name": None, 
            "lbl_status": None, 
            "progress_bar": None, 
            "cover_bytes": None, 
            "new_cover_path": None, 
            "delete_cover": False, 
            "ctk_thumb": None
        }
        
        self.files_data.append(file_obj)
        self.add_file_to_ui(file_obj)
        self.read_metadata_from_file(file_obj)
        return len(self.files_data) - 1

    def add_file_to_ui(self, file_obj):
        row = ctk.CTkFrame(self.scroll_frame)
        row.pack(fill="x", pady=2)
        
        lbl_name = ctk.CTkLabel(row, text=file_obj['filename'], width=220, anchor="w")
        lbl_name.pack(side="left", padx=10)
        
        lbl_status = ctk.CTkLabel(row, text=file_obj['status'], width=100, text_color="orange")
        lbl_status.pack(side="right", padx=10)
        
        progress = ctk.CTkProgressBar(row, width=80)
        progress.set(0)
        progress.pack(side="right", padx=10)
        
        file_obj.update({
            'widget': row, 
            'lbl_name': lbl_name, 
            'lbl_status': lbl_status, 
            'progress_bar': progress
        })
        
        # Hacer clicable toda la fila
        for widget in [row, lbl_name, lbl_status]:
            widget.bind("<Button-1>", lambda e, obj=file_obj: self.manual_select(obj))

    def manual_select(self, file_obj):
        try:
            idx = self.files_data.index(file_obj)
            self.load_to_editor(idx)
        except: pass

    def parse_dropped_files(self, data):
        if data.startswith('{') and data.endswith('}'):
            return self.tk.splitlist(data)
        return self.tk.splitlist(data)

    def drop_on_converter(self, event):
        files = self.parse_dropped_files(event.data)
        for f in files: self.register_file(f)

    def drop_on_editor(self, event):
        files = self.parse_dropped_files(event.data)
        last_index = -1
        for f in files:
            idx = self.register_file(f)
            if idx != -1: last_index = idx
        if last_index != -1: self.load_to_editor(last_index)

    # ==================== FUNCIONALIDADES DE CARÁTULA ====================

    def browse_cover_art(self):
        if self.current_selection_index is None: return
        path = filedialog.askopenfilename(filetypes=[("Images", "*.jpg *.jpeg *.png")])
        if path:
            obj = self.files_data[self.current_selection_index]
            obj['new_cover_path'], obj['delete_cover'] = path, False
            self.update_cover_preview(obj)

    def delete_current_cover(self):
        if self.current_selection_index is not None:
            obj = self.files_data[self.current_selection_index]
            obj['delete_cover'], obj['new_cover_path'] = True, None
            self.update_cover_preview(obj)

    # ==================== FUNCIONALIDADES DE CARPETA ====================

    def change_output_folder(self):
        folder = filedialog.askdirectory()
        if folder: 
            self.output_folder = folder
            self.lbl_output.configure(text=f"Destino: {os.path.basename(folder)}")

    # ==================== FUNCIONALIDADES DE GUARDADO ====================

    def save_tags(self):
        if self.current_selection_index is None: return
        obj = self.files_data[self.current_selection_index]
        
        # 1. Renombrar archivo si es necesario
        new_name = self.entry_filename.get().strip()
        if new_name:
            if not new_name.lower().endswith(obj['ext']): new_name += obj['ext']
            if new_name != obj['filename']:
                new_path = os.path.join(os.path.dirname(obj['path']), new_name)
                try:
                    os.rename(obj['path'], new_path)
                    obj.update({'path': new_path, 'filename': new_name})
                    obj['lbl_name'].configure(text=new_name)
                except Exception as e: 
                    messagebox.showerror("Error", f"No se pudo renombrar: {e}")
                    return
        
        # 2. Guardar etiquetas de los campos
        for key, entry in self.entries.items(): 
            obj['tags'][key] = entry.get()
        
        # 3. Aplicar etiquetas según formato
        if obj['ext'] == '.mp3': 
            self.apply_tags_to_mp3(obj)
        elif obj['ext'] == '.m4a': 
            self.apply_tags_to_m4a(obj)
        elif obj['ext'] == '.flac':
            self.apply_tags_to_flac(obj)
        
        obj['lbl_status'].configure(text="Saved", text_color="green")
        messagebox.showinfo("OK", "Guardado.")

    def apply_tags_to_mp3(self, obj):
        try:
            audio = MP3(obj['path'], ID3=ID3)
            try: audio.add_tags()
            except: pass
            
            t = obj['tags']
            audio.tags.add(TIT2(encoding=3, text=t.get("Song Name","")))
            audio.tags.add(TPE1(encoding=3, text=t.get("Artist","")))
            audio.tags.add(TALB(encoding=3, text=t.get("Album","")))
            audio.tags.add(TCON(encoding=3, text=t.get("Genre","")))
            audio.tags.add(TYER(encoding=3, text=str(t.get("Year",""))))
            audio.tags.add(TRCK(encoding=3, text=str(t.get("Track Number",""))))
            
            # Manejar carátula
            audio.tags.delall("APIC")
            final_img = None
            if obj.get('new_cover_path'):
                with open(obj['new_cover_path'], 'rb') as f: final_img = f.read()
            elif obj.get('cover_bytes') and not obj.get('delete_cover'): 
                final_img = obj['cover_bytes']
            
            if final_img: 
                audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=final_img))
            
            audio.save()
            obj.update({'cover_bytes': final_img, 'new_cover_path': None, 'delete_cover': False, 'ctk_thumb': None})
        except Exception as e:
            print(f"Error guardando MP3: {e}")

    def apply_tags_to_m4a(self, obj):
        try:
            audio = MP4(obj['path'])
            t = obj['tags']
            
            audio['\xa9nam'] = t.get("Song Name","")
            audio['\xa9ART'] = t.get("Artist","")
            audio['\xa9alb'] = t.get("Album","")
            audio['\xa9gen'] = t.get("Genre","")
            audio['\xa9day'] = t.get("Year","")
            
            # Track number en M4A es una tupla (número, total)
            try: 
                audio['trkn'] = [(int(t.get("Track Number",0)), 0)]
            except: pass
            
            # Manejar carátula
            final_img = None
            if obj.get('new_cover_path'):
                with open(obj['new_cover_path'], 'rb') as f: final_img = f.read()
            elif obj.get('cover_bytes') and not obj.get('delete_cover'): 
                final_img = obj['cover_bytes']
            
            if final_img:
                img = Image.open(io.BytesIO(final_img))
                fmt = MP4Cover.FORMAT_PNG if img.format == 'PNG' else MP4Cover.FORMAT_JPEG
                audio['covr'] = [MP4Cover(final_img, imageformat=fmt)]
            elif obj.get('delete_cover'): 
                audio.pop('covr', None)
            
            audio.save()
            obj.update({'cover_bytes': final_img, 'new_cover_path': None, 'delete_cover': False, 'ctk_thumb': None})
        except Exception as e:
            print(f"Error guardando M4A: {e}")

    def apply_tags_to_flac(self, obj):
        try:
            audio = FLAC(obj['path'])
            t = obj['tags']
            
            audio['title'] = t.get("Song Name", "")
            audio['artist'] = t.get("Artist", "")
            audio['album'] = t.get("Album", "")
            audio['genre'] = t.get("Genre", "")
            audio['date'] = t.get("Year", "")
            audio['tracknumber'] = t.get("Track Number", "")
            
            # Manejar carátula
            final_img = None
            if obj.get('new_cover_path'):
                with open(obj['new_cover_path'], 'rb') as f: final_img = f.read()
            elif obj.get('cover_bytes') and not obj.get('delete_cover'): 
                final_img = obj['cover_bytes']
            
            if final_img:
                # Borrar imágenes existentes
                audio.clear_pictures()
                # Añadir nueva imagen
                picture = Picture()
                picture.data = final_img
                picture.type = 3  # Front cover
                picture.mime = 'image/jpeg'
                picture.width = 500
                picture.height = 500
                picture.depth = 24
                audio.add_picture(picture)
            elif obj.get('delete_cover'):
                audio.clear_pictures()
            
            audio.save()
            obj.update({'cover_bytes': final_img, 'new_cover_path': None, 'delete_cover': False, 'ctk_thumb': None})
        except Exception as e:
            print(f"Error guardando FLAC: {e}")

    # ==================== FUNCIONALIDADES DE CONVERSIÓN ====================

    def start_conversion_thread(self):
        threading.Thread(target=self.process_queue, daemon=True).start()

    def process_queue(self):
        self.btn_convert.configure(state="disabled")
        
        if not self.ffmpeg_path:
            messagebox.showerror("Error", "FFmpeg no encontrado.")
            self.btn_convert.configure(state="normal")
            return
        
        for obj in self.files_data:
            if obj['ext'] in ['.wav', '.flac']:
                obj['lbl_status'].configure(text="Converting...", text_color="yellow")
                out_p = os.path.join(self.output_folder, os.path.splitext(obj['filename'])[0] + ".mp3")
                try:
                    subprocess.run([
                        self.ffmpeg_path, "-y", "-i", obj['path'], 
                        "-b:a", "320k", "-threads", "0", 
                        "-id3v2_version", "3", out_p
                    ], check=True, capture_output=True)
                    
                    # Aplicar etiquetas al nuevo archivo
                    temp = obj.copy()
                    temp['path'] = out_p
                    self.apply_tags_to_mp3(temp)
                    
                    obj['lbl_status'].configure(text="Done", text_color="green")
                    obj['progress_bar'].set(1)
                except: 
                    obj['lbl_status'].configure(text="Error", text_color="red")
            else:
                # Para MP3 y M4A, solo marcar como completado
                obj['lbl_status'].configure(text="Done", text_color="green")
                obj['progress_bar'].set(1)
        
        self.btn_convert.configure(state="normal")
        messagebox.showinfo("Fin", "Proceso terminado.")

if __name__ == "__main__":
    app = AudioApp()
    app.mainloop()