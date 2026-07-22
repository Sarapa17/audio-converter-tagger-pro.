# Audio Converter & Tagger Pro

Aplicación de escritorio (Python + CustomTkinter) para **convertir, etiquetar y verificar** archivos de audio. Soporta **drag & drop**, edición de metadatos (incluida la carátula), conversión a MP3 de 320kbps y un verificador de integridad espectral (FFT) que estima la calidad *real* de un archivo (para detectar "falsos 320kbps").

> Interfaz oscura, layout de dos columnas: editor de etiquetas a la izquierda, cola de procesamiento a la derecha.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![Plataforma](https://img.shields.io/badge/platforms-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey)

---

## Características

- **Conversión de audio** con `ffmpeg`:
  - Entrada soportada: `.flac`, `.wav`, `.mp3`, `.m4a`
  - Salida: MP3 a **320 kbps** (con tags ID3v2.3)
- **Editor de etiquetas** para MP3 (ID3), M4A/MP4 y FLAC:
  - Título, Artista, Álbum, Género, Año, Número de pista
  - Carátula: agregar, reemplazar, eliminar o mantener la existente
  - Renombrado del archivo desde el editor
- **Verificador de integridad espectral (FFT)**:
  - Decodifica 5 s de audio y analiza el espectro con `numpy`/`scipy`
  - Estima la calidad *real* a partir del corte de altas frecuencias y clasifica: `REAL 320`, `~256`, `FAKE 320 (real 128)` o `BAJA`
- **Drag & drop** de archivos (tanto en la cola como en el editor) vía `tkinterdnd2`
- **Buscador inteligente de ffmpeg**: lo busca en `PATH`; si no está, lo busca junto al script o en el bundle de PyInstaller (`_MEIPASS`).
- **PyInstaller**: incluye `AudioTaggerPro.spec` para empaquetar la app como `.app` (macOS) o `.exe` (Windows) con ffmpeg embebido.

---

## Captura / Layout

```
┌─────────────────────────┬─────────────────────────────┐
│  EDITOR DE ETIQUETAS    │  COLA DE PROCESAMIENTO       │
│  - Header de calidad   │  - Archivos arrastrados      │
│  - Verificador FFT      │  - Estado / progreso         │
│  - Campos (título,      │  - Destino seleccionable     │
│    artista, álbum…)      │  - PROCESAR TODO             │
│  - Carátula             │                              │
└─────────────────────────┴─────────────────────────────┘
```

---

## Requisitos

- Python **3.10+**
- `ffmpeg` instalado en el sistema **o** un binario `ffmpeg` en la misma carpeta que `app.py` (ver abajo).
  - macOS:  `brew install ffmpeg`
  - Linux:  `sudo apt install ffmpeg`
  - Windows: descarga desde <https://ffmpeg.org/download.html> y coloca `ffmpeg.exe` en la carpeta del proyecto

Dependencias de Python (en [`requirements.txt`](requirements.txt)):

```
customtkinter>=5.2.0
Pillow>=10.0.0
mutagen>=1.47.0
numpy>=1.24.0
scipy>=1.10.0
tkinterdnd2>=0.3.0
```

> ⚠️ **Nota sobre ffmpeg:** el binario de ffmpeg (~80 MB) **no se incluye en este repositorio** porque excede el límite de GitHub para archivos sin LFS y por buena práctica. Debes proveerlo tú (vía `PATH` o copiándolo en la carpeta del proyecto). En macOS, el empaquetado con PyInstaller sí lo embebe si está presente en la carpeta al momento de compilar.

---

## Instalación y uso

```bash
# 1. Clonar
git clone https://github.com/<tu-usuario>/<tu-repo>.git
cd <tu-repo>

# 2. Crear entorno virtual e instalar dependencias
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. (Opcional) ubicar ffmpeg en la carpeta del proyecto
#    o asegurarse de que esté en el PATH

# 4. Ejecutar
python app.py
```

---

## Empaquetado con PyInstaller

El repositorio incluye [`AudioTaggerPro.spec`](AudioTaggerPro.spec) para generar la app portable
(con ffmpeg embebido como binario). Requiere `pip install pyinstaller`.

```bash
pyinstaller AudioTaggerPro.spec
# La app queda en dist/AudioTaggerPro.app  (macOS)
#              o en dist/AudioTaggerPro/    (Windows)
```

Los íconos `icon.icns` (macOS) y `icon.ico` (Windows) ya están incluidos.

---

## Estructura del proyecto

```
.
├── app.py                 # Código principal de la app
├── AudioTaggerPro.spec    # Spec de PyInstaller para empaquetar
├── requirements.txt       # Dependencias de Python
├── icon.icns              # Ícono para macOS
├── icon.ico               # Ícono para Windows
├── .gitignore
└── README.md
```

---

## Cómo funciona la verificación de calidad (FFT)

La función `perform_spectral_analysis` en [`app.py`](app.py) hace lo siguiente:

1. Decodifica **5 segundos** de audio (a partir de los 30 s) con `ffmpeg` a PCM mono 44.1 kHz.
2. Calcula la **FFT** con `numpy`/`scipy`.
3. Busca la frecuencia más alta con magnitud significativa (> -60 dB).
4. Clasifica según el corte:

| Corte aprox. | Clasificación            |
|--------------|--------------------------|
| ≥ 18.5 kHz   | REAL 320 kbps            |
| ≥ 16.0 kHz   | REAL ~256 kbps           |
| ≥ 13.5 kHz   | FAKE 320 (real 128k)     |
| < 13.5 kHz   | BAJA calidad             |

> Es una estimación heurística: el corte espectral de los codecs con pérdida revela hasta dónde llegó la información original. No es prueba forense, pero es útil para detectar upscaleups.

---

## Licencia

Este proyecto está bajo la **Licencia MIT**. Ver el archivo [LICENSE](LICENSE) para más detalles.

Resumen práctico: podés usarlo, copiarlo, modificarlo y distribuirlo libremente —incluido uso comercial— siempre que conserves el aviso de copyright y la nota de licencia. Sin garantías de ningún tipo.

## Autor

**Tomas Sarapura** — [@Sarapa17](https://github.com/Sarapa17)

Repositorio: <https://github.com/Sarapa17/audio-converter-tagger-pro>
