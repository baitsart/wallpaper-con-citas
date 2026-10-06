#!/usr/bin/env python3
import io
import json
import os
import random
import re
import sys
import ast
import shutil
import subprocess
import tempfile
import threading
import urllib.parse
import urllib.request
import urllib.error
import threading
from pathlib import Path
from datetime import datetime
import gi
import gc
gi.require_version('Gtk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango, PangoCairo
from PIL import Image, ImageDraw, ImageFont, ExifTags

# ----------------------------------------------------------------------
# CONFIGURACIÓN Y RUTAS DE ALMACENAMIENTO UNIVERSALES ($HOME)
# ----------------------------------------------------------------------

HOME_DIR = Path.home()

# 1. Directorios base (Recursos globales instalados en el sistema - Solo lectura)
BASE_DIR = Path("/usr/share/wallpaper_manager")
IMAGENES_QUOTES_DIR = BASE_DIR / "Buenas_imágenes_citas"
QUOTES_DIR = IMAGENES_QUOTES_DIR / "Quotes"

# 2. Caché y Configuración (Escritura en el Home del usuario)
TEMP_DIR = Path(tempfile.gettempdir()) / "wallpaper_manager_cache"

# Ruta fija del archivo de tags en /usr/share/
CONFIG_FILE = IMAGENES_QUOTES_DIR / "auto-download.config"
CONFIG_TAGS_PATH = IMAGENES_QUOTES_DIR / "tags_activos.config"
CONFIG_LANG_FILE = IMAGENES_QUOTES_DIR / "language.config"
CONFIG_FONTS = IMAGENES_QUOTES_DIR / "fonts.config"
FONTE_DEFAULT_FALLBACK = IMAGENES_QUOTES_DIR / "fonts" / "C059-BdIta.t1"

# 3. Creación de carpetas si no existen
IMAGENES_QUOTES_DIR.mkdir(parents=True, exist_ok=True)
QUOTES_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
TEXT_SHADOW = True  

def cargar_config_idioma():
    if CONFIG_LANG_FILE.exists():
        try:
            val = CONFIG_LANG_FILE.read_text().strip().lower()
            if val in ["en", "es", "ar", "bn", "de", "el", "fa", "fr", "gu", "hi", "id", "it", "ja", "lt", "pt", "ro", "ru", "sk", "ta", "th", "uk", "zh-CN", "zh-TW"]:
                return val
        except Exception:
            pass
    return "es"

def guardar_config_fuentes(misma_fuente, font_path, fuente_sesion=None):
    # Convertimos a string por si vienen como objetos PosixPath
    datos = {
        "misma_fuente": misma_fuente,
        "font_path": str(font_path if font_path else FONTE_DEFAULT_FALLBACK),
        "fuente_sesion": str(fuente_sesion) if fuente_sesion else ""
    }
    try:
        with open(CONFIG_FONTS, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=4)
    except Exception as e:
        print(f"Error guardando configuración de fuentes: {e}")

def cargar_tags_activos():
    """
    Lee el archivo de configuración de tags.
    Procesa tanto los activos como los comentados con '#' para mostrarlos en la UI como desmarcados.
    """
    tags_config = {}
    
    if not CONFIG_TAGS_PATH.exists():
        CONFIG_TAGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        contenido_inicial = """# Archivo de configuración de tags activos
# Las líneas que empiezan con # se consideran desactivadas/comentadas pero aparecerán apagadas en la app.
# Formato: "Clave": "Valor"

"Naturaleza": "nature",
"Paisajes": "landscape",
"Montañas": "mountains",
"Espacio": "space",
"Arquitectura": "architecture",
"Borobudur Temple": "Borobudur temple",
"Japón": "Japan",
#"Linux": "Linux",
"Veganismo": "veganism",
"Love Animals": "love animals",
#"Tesla": "Tesla",
"Nikola Tesla": "Nikola Tesla",
"""
        CONFIG_TAGS_PATH.write_text(contenido_inicial, encoding="utf-8")

    lineas = CONFIG_TAGS_PATH.read_text(encoding="utf-8").splitlines()
    for linea in lineas:
        linea_limpia = linea.strip()
        
        # Si la línea está totalmente vacía, la ignoramos
        if not linea_limpia:
            continue
            
        activo = True
        
        # Si la línea empieza con #, está desactivada pero la queremos mostrar apagada
        if linea_limpia.startswith("#"):
            activo = False
            # Quitamos el '#' y los espacios para poder leer el par clave:valor igualmente
            linea_limpia = linea_limpia.lstrip("#").strip()
            
        try:
            if ":" in linea_limpia:
                partes = linea_limpia.split(":", 1)
                clave_str = partes[0].strip()
                valor_str = partes[1].strip().rstrip(",")
                
                clave = ast.literal_eval(clave_str)
                valor = ast.literal_eval(valor_str)
                
                tags_config[clave] = {"query": valor, "activo": activo}
        except Exception as e:
            # Ignora líneas puramente informativas que no tengan el formato clave:valor
            pass
            
    return tags_config

def cargar_config_fuentes(default_font):
    misma_fuente = True
    font_path = default_font
    
    if os.path.exists(CONFIG_FONTS):
        try:
            with open(CONFIG_FONTS, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    data = json.loads(content)
                    misma_fuente = data.get("misma_fuente", True)
                    font_path = data.get("font_path", default_font)
        except Exception as e:
            print(f"Error leyendo configuración de fuentes: {e}")
            # Comprueba si puedes utilizar un archivo limpio o el valor por defecto
            
        if not font_path or not os.path.exists(font_path):
            font_path = default_font
        
        return misma_fuente, font_path

def guardar_config_idioma(lang):
    try:
        CONFIG_LANG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_LANG_FILE.write_text(lang, encoding="utf-8")
    except Exception as e:
        print(f"Error guardando idioma: {e}")

def guardar_tags_activos(tags_config):
    """
    Guarda el estado actual de los tags en el archivo de configuración,
    escribiendo con '#' al principio las líneas que estén desactivadas (activo = False).
    """
    try:
        CONFIG_TAGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        lineas = [
            "# Archivo de configuración de tags activos",
            "# Las líneas que empiezan con # se consideran desactivadas/comentadas pero aparecerán apagadas en la app.",
            '# Formato: "Clave": "Valor"',
            ""
        ]
        
        for clave, datos in tags_config.items():
            activo = datos.get("activo", True)
            query = datos.get("query", "")
            
            # Formateamos como par clave-valor
            linea_formateada = f'"{clave}": "{query}",'
            
            # Si el usuario lo desmarcó, le anteponemos el '#'
            if not activo:
                linea_formateada = "#" + linea_formateada
                
            lineas.append(linea_formateada)
            
        CONFIG_TAGS_PATH.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    except Exception as e:
        print(f"Error al guardar tags_activos.config: {e}")

def buscar_script(nombre_script):
    """
    Busca el script ejecutable (.py) probando en:
    1. /usr/share/wallpaper_manager/
    2. /usr/share/wallpaper_manager/Buenas_imágenes_citas/
    3. /usr/share/wallpaper_manager/Buenas_imágenes_citas/Quotes/
    """
    rutas_posibles = [
        BASE_DIR / nombre_script,
        IMAGENES_QUOTES_DIR / nombre_script,
        QUOTES_DIR / nombre_script,
    ]

    for ruta in rutas_posibles:
        if ruta.exists():
            return ruta

    return None
    
def cargar_config_preguntar():
    if CONFIG_FILE.exists():
        try:
            val = CONFIG_FILE.read_text().strip().lower()
            return val in ["sí", "si", "true"]
        except Exception:
            return True
    return True

def guardar_config_preguntar(activo):
    try:
        CONFIG_FILE.write_text("Sí" if activo else "No", encoding="utf-8")
    except Exception as e:
        print(f"Error guardando configuración: {e}")

def obtener_directorios():
    try:
        res = subprocess.run(["xdg-user-dir", "PICTURES"], capture_output=True, text=True, check=True)
        base = Path(res.stdout.strip())
    except Exception:
        base = Path.home() / "Imágenes"

    dir_citas = base / "wallpaper manager_citas"
    dir_auto = dir_citas / "Automatica"

    dir_citas.mkdir(parents=True, exist_ok=True)
    dir_auto.mkdir(parents=True, exist_ok=True)
    return dir_citas, dir_auto

SAVE_DIR, AUTO_DIR = obtener_directorios()
WALLHAVEN_API_KEY = os.environ.get("WALLHAVEN_API_KEY", "jJm5diseSPiDVIqvvE7aUS4fWwgJ0koW")
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY", "57658781-0a7941b8305114c3f2db8a611")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "b1NfvD9UGKtR2kymNDr2jHp02R2IbeXpQzLILZnni2T0O4o5utkDBf2w")

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
}

IMAGE_STYLES = cargar_tags_activos()

LISTA_OTROS_AUTORES = [
    "Albert Einstein", "Nikola Tesla", "Mark Twain", "Benjamin Franklin",
    "Oscar Wilde", "Mahatma Gandhi", "Friedrich Nietzsche", "Marilyn Monroe",
    "George Bernard Shaw", "William Shakespeare", "Bob Marley", "Abraham Lincoln",
    "Bruce Lee", "Aristotle", "Plato", "Confucius", "Rumi", "Carl Sagan",
    "Stephen Hawking", "Steve Jobs", "Elon Musk"
]

# ----------------------------------------------------------------------
# FUENTES DEL SISTEMA
# ----------------------------------------------------------------------
def get_system_fonts():
    fonts = []
    # Directorios del sistema y del usuario (incluyendo .local/share/fonts y .fonts)
    base_dirs = [
        Path("/usr/share/fonts"),
        Path.home() / ".local" / "share" / "fonts",
        Path.home() / ".fonts"
    ]
    
    for base_dir in base_dirs:
        if base_dir.is_dir():
            for root, _, files in os.walk(base_dir):
                for filename in files:
                    if filename.lower().endswith((".ttf", ".otf")):
                        fonts.append(os.path.join(root, filename))
                        
    fonts.sort(key=lambda p: os.path.basename(p).lower())
    return fonts

SYSTEM_FONTS = get_system_fonts()

# ----------------------------------------------------------------------
# TRADUCTOR GRATUITO (Google Translate Endpoint API)
# ----------------------------------------------------------------------
def traducir_texto(texto, target_lang="es", source_lang="en"):
    if not texto or target_lang == source_lang:
        return texto
    try:
        url = (
            "https://translate.googleapis.com/translate_a/single?client=gtx&sl="
            + source_lang + "&tl=" + target_lang + "&dt=t&q=" + urllib.parse.quote(texto)
        )
        req = urllib.request.Request(url, headers=HTTP_HEADERS)
        with urllib.request.urlopen(req, timeout=8) as response:
            res_json = json.loads(response.read().decode("utf-8"))
            result = "".join([part[0] for part in res_json[0] if part[0]])
            return result
    except Exception as e:
        print(f"Error en traducción automática: {e}")
        return texto

# ----------------------------------------------------------------------
# PARSER Y BANCO DE CITAS
# ----------------------------------------------------------------------
SIVA_METADATA_URLS = (
    "https://www.pranaviolethealing.com/\n"
    "https://app.sanacionpranicavioleta.com/\n"
    "https://www.facebook.com/pranaviolet.singapore/\n"
    "https://www.pinterest.com/thevim/prana-violet-healing/"
)

def ejecutar_y_parsear_script(script_path, lang="es"):
    """
    Ejecuta scripts secundarios de citas (Prem Rawat, Sadhguru)
    pasándoles el idioma como parámetro y parsea la salida.
    """
    if not Path(script_path).exists():
        return {"Cita": "Archivo de script no encontrado.", "Autor": "", "Fecha": "", "URL": ""}

    try:
        # Pasamos sys.executable y el idioma 'es' o 'en' como argumento
        resultado = subprocess.run(
            [sys.executable, str(script_path), lang],
            capture_output=True,
            text=True,
            timeout=15
        )
        
        salida = resultado.stdout.strip()
        if not salida:
            print(f"Advertencia: El script {script_path.name} no devolvió datos. Stderr: {resultado.stderr}")
            return {"Cita": "", "Autor": "", "Fecha": "", "URL": ""}

        datos = {"Cita": "", "Autor": "", "Fecha": "", "URL": ""}
        
        # Parseo de la salida clave-valor
        for linea in salida.splitlines():
            linea = linea.strip()
            if linea.startswith("Cita:"):
                datos["Cita"] = linea.replace("Cita:", "", 1).strip()
            elif linea.startswith("Autor:"):
                datos["Autor"] = linea.replace("Autor:", "", 1).strip()
            elif linea.startswith("Fecha:"):
                datos["Fecha"] = linea.replace("Fecha:", "", 1).strip()
            elif linea.startswith("URL:"):
                datos["URL"] = linea.replace("URL:", "", 1).strip()

        return datos

    except Exception as e:
        nombre_script = script_path.name if hasattr(script_path, "name") else os.path.basename(str(script_path))
        print(f"Error ejecutando {nombre_script}: {e}")
        return {"Cita": "", "Autor": "", "Fecha": "", "URL": ""}

def obtener_cita_desde_txt(archivos_objetivo, patron_fallback=""):
    """
    Busca citas en los archivos específicos indicados y/o buscando por patrón.
    Acepta tanto una lista de nombres de archivos exactos como un patrón de texto.
    """
    citas = []
    
    # Directorios donde buscar los archivos .txt
    directorios_a_buscar = [QUOTES_DIR, IMAGENES_QUOTES_DIR, HOME_DIR]
    
    archivos_encontrados = []

    # 1. Buscar archivos con los nombres exactos indicados (ej. 'Dr Siva P s teachings.txt')
    if isinstance(archivos_objetivo, list):
        for direct in directorios_a_buscar:
            if direct.exists():
                for nombre_f in archivos_objetivo:
                    f_path = direct / nombre_f
                    if f_path.exists() and f_path not in archivos_encontrados:
                        archivos_encontrados.append(f_path)

    # 2. Búsqueda por patrón en caso de no hallar los exactos
    if not archivos_encontrados and patron_fallback:
        for direct in directorios_a_buscar:
            if direct.exists():
                for f in direct.glob("*.txt"):
                    if patron_fallback.lower() in f.name.lower() and f not in archivos_encontrados:
                        archivos_encontrados.append(f)

    # Procesar el contenido de los archivos encontrados
    for filepath in archivos_encontrados:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                contenido = f.read()

            # Si el archivo contiene el separador "---", tomamos lo que está después
            if "---" in contenido:
                contenido_util = contenido.split("---")[-1]
            else:
                contenido_util = contenido

            # Procesamos las líneas del texto
            for line in contenido_util.splitlines():
                linea = line.strip()
                # Ignora URLs, líneas vacías o fragmentos web
                if not linea or linea.startswith("http") or linea.startswith("/quote/"):
                    continue
                
                # Limpieza de corchetes, números de página y comillas
                texto_limpio = re.sub(r"^\[\d+\]\s*", "", linea)
                texto_limpio = re.sub(r"^Pág(ina)?\s*\d+:?\s*", "", texto_limpio, flags=re.IGNORECASE)
                texto_limpio = texto_limpio.strip("“\"” \n\t")
                
                if texto_limpio and len(texto_limpio) > 15:
                    citas.append(texto_limpio)
        except Exception as e:
            print(f"Error leyendo {filepath}: {e}")
            
    return citas

def on_boton_buscar_clicked(widget):
    # 1. Mostrar aviso inmediato en la interfaz para que el usuario sepa que está trabajando
    label_estado.set_text("Buscando cita, por favor espere...")
    spinner.start() # Si tienes un indicador de carga giratorio
    
    # Obtener el nombre del autor que escribió el usuario
    autor = entry_autor.get_text().strip()

    # 2. Definir la tarea que correrá EN SEGUNDO PLANO (para que no congele nada)
    def tarea_en_segundo_plano():
        # Aquí llamas a tu función que tarda (others_authors.py)
        resultado = obtener_cita_otros_autores_script(autor)
        
        # 3. Una vez que termina, usamos GLib.idle_add para actualizar 
        # la interfaz gráfica de forma segura desde el hilo principal
        GLib.idle_add(actualizar_interfaz_grafica, resultado)

    # Lanzar el hilo secundario
    threading.Thread(target=tarea_en_segundo_plano, daemon=True).start()

def actualizar_interfaz_grafica(resultado):
    """Esta función corre en el hilo principal y pinta los resultados en pantalla"""
    label_cita.set_text(resultado["Cita"])
    label_autor.set_text(resultado["Autor"])
    spinner.stop()
    label_estado.set_text("")  # Limpiar el aviso de espera
    return False # Importante para que GLib.idle_add no se repita

def traducir_nativo(texto, target_lang="es", source_lang="auto"):
    """Traduce usando auto-translate.py y usa MyMemory como respaldo ante fallos de red o timeouts."""
    if not texto or len(texto.strip()) < 3 or target_lang == source_lang:
        return texto

    # 1. Intentar primero con el script local (auto-translate.py)
    script_translate = IMAGENES_QUOTES_DIR / "auto-translate.py"
    if not script_translate.exists():
        script_translate = Path("/usr/share/wallpaper_manager/Buenas_imágenes_citas/auto-translate.py")

    if script_translate.exists():
        try:
            res = subprocess.run(
                [sys.executable, str(script_translate), texto, target_lang],
                capture_output=True,
                text=True,
                timeout=8  # Ajustado un poco por debajo para que no cuelgue la app si hay lag
            )
            if res.returncode == 0 and res.stdout.strip():
                salida_script = res.stdout.strip()
                lineas_limpias = [
                    l.strip() for l in salida_script.splitlines() 
                    if l.strip() and not l.startswith("Traduciendo") and not l.startswith("Original:") and not l.startswith("Destino") and not l.startswith("[!]")
                ]
                # Validar que lo devuelto no sea idéntico al original si hubo un error interno
                if lineas_limpias and lineas_limpias[-1] != texto:
                    return lineas_limpias[-1]
        except Exception as e:
            print(f"Aviso: auto-translate.py falló, probando respaldo alternativo... ({e})")

    # 2. Respaldo secundario con la API web de MyMemory si el script falló o dio timeout
    try:
        langpair = f"{source_lang}|{target_lang}"
        url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(texto)}&langpair={langpair}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            if data.get('responseStatus') == 200:
                traduccion = data.get('responseData', {}).get('translatedText')
                if traduccion and not traduccion.startswith("MYMEMORY WARNING"):
                    return traduccion
    except Exception:
        pass

    # 3. Última línea de defensa: si todo falla, devuelve el texto original
    return texto

def obtener_cita_otros_autores_script(autor_nombre, lang="es"):
    autor_nombre = autor_nombre.strip() if autor_nombre else ""
    if not autor_nombre:
        return {"Cita": "Por favor escribe un autor.", "Autor": "", "Fecha": "", "URL": ""}

    url_meta = ""
    json_db_path = IMAGENES_QUOTES_DIR / "autores_completos_db.json"

    # Búsqueda optimizada de memoria
    if json_db_path.exists():
        try:
            with open(json_db_path, "r", encoding="utf-8") as f:
                db_data = json.load(f)
                valores = db_data.values() if isinstance(db_data, dict) else db_data
                autor_buscado = autor_nombre.lower()

                for entry in valores:
                    if not isinstance(entry, dict):
                        continue
                    if autor_buscado in entry.get("nombre", "").lower() or autor_buscado in entry.get("exacto", "").lower():
                        rel_url = entry.get("url", "")
                        if rel_url:
                            url_meta = rel_url if rel_url.startswith("http") else f"https://www.azquotes.com{rel_url}"
                        break
                # Liberar explícitamente la estructura pesada de RAM
                del db_data
                del valores
        except Exception as e:
            print(f"Error leyendo autores_completos_db.json: {e}")

    # Búsqueda exhaustiva del script en todas las rutas conocidas
    posibles_rutas_script = [
        IMAGENES_QUOTES_DIR / "others_authors.py",
    ]
    
    script_path = None
    for r in posibles_rutas_script:
        if r.exists():
            script_path = r
            break

    salida = ""
    # NO reiniciamos url_meta aquí para conservar la del JSON si ya la tenemos
    exito_web = False

    # 1. Ejecutar script externo
    if script_path:
        try:
            res = subprocess.run(
                [sys.executable, str(script_path), autor_nombre],
                capture_output=True,
                text=True,
                timeout=25
            )
            salida = res.stdout.strip()
            if res.returncode == 0 and salida:
                exito_web = True
            else:
                print(f"Error en others_authors.py (Code {res.returncode}): {res.stderr.strip()}")
        except subprocess.TimeoutExpired:
            print(f"Aviso: others_authors.py tardó demasiado para '{autor_nombre}'.")
        except Exception as e:
            print(f"Error ejecutando others_authors.py: {e}")
    else:
        print("Error: No se encontró el archivo 'others_authors.py' en ninguna ruta conocida.")

    cita_pura = ""

    # 2. Extraer la cita y la URL de la salida estándar
    if exito_web and salida:
        for linea in salida.splitlines():
            linea_s = linea.strip()
            if not linea_s:
                continue
            
            if linea_s.startswith("http") or linea_s.startswith("/quote/"):
                if linea_s.startswith("/quote/"):
                    url_meta = f"https://www.azquotes.com{linea_s}"
                else:
                    url_meta = linea_s
                continue

            match = re.match(r"^\[\d+\]\s*(.+)$", linea_s)
            if match:
                cita_pura = match.group(1).strip()
            elif not cita_pura:
                cita_pura = linea_s

    # 3. Respaldo local si no se obtuvo respuesta web
    if not cita_pura:
        citas_locales = []
        partes_nombre = [p.lower() for p in autor_nombre.split() if len(p) > 2]
        
        directorios_busqueda = [QUOTES_DIR, IMAGENES_QUOTES_DIR, HOME_DIR]
        for direct in directorios_busqueda:
            if not direct.exists():
                continue
            for f in direct.glob("*.txt"):
                nombre_lower = f.name.lower()
                if any(p in nombre_lower for p in partes_nombre):
                    try:
                        with open(f, "r", encoding="utf-8", errors="ignore") as file:
                            contenido = file.read()
                            
                        if "---" in contenido:
                            contenido = contenido.split("---")[-1]

                        for line in contenido.splitlines():
                            linea = line.strip()
                            if not linea or linea.startswith("http") or linea.startswith("/quote/"):
                                continue
                            
                            texto_limpio = re.sub(r"^\[\d+\]\s*", "", linea)
                            texto_limpio = re.sub(r"^Pág(ina)?\s*\d+:?\s*", "", texto_limpio, flags=re.IGNORECASE)
                            texto_limpio = texto_limpio.strip("“\"” \n\t")
                            
                            if texto_limpio and len(texto_limpio) > 10:
                                citas_locales.append(texto_limpio)
                    except Exception as e:
                        print(f"Error leyendo {f}: {e}")

        if citas_locales:
            cita_pura = random.choice(citas_locales)
            url_meta = ""

    if not cita_pura:
        return {
            "Cita": f"No se encontraron citas disponibles para '{autor_nombre}'.",
            "Autor": autor_nombre,
            "Fecha": "",
            "URL": ""
        }

    # Traducir al idioma seleccionado (Corregido de lang= a target_lang=)
    if lang:
        cita_pura = traducir_nativo(cita_pura, target_lang=lang, source_lang="en")

    return {
        "Cita": cita_pura,
        "Autor": autor_nombre,
        "Fecha": "AZ Quotes" if url_meta else "Archivo Local",
        "URL": url_meta
    }

def obtener_cita_datos(autor_id, lang="es", autor_otro=""):
    """Función simplificada para obtener citas según el autor y el idioma."""
    lang_lower = lang.lower()

    if autor_id == "sadhguru":
        script_sadhguru = "/usr/share/wallpaper_manager/Buenas_imágenes_citas/sadhguru_quotes.py"
        sadhguru_sufijos = ["es", "ar", "bn", "en", "fr", "de", "gu", "hi", "id", "it", "ja", "lt", "fa", "pt", "ro", "ru", "sk", "th", "uk"]
        
        # Si el idioma está en la lista usa su sufijo, sino por defecto usa inglés
        sufijo_web = lang_lower if lang_lower in sadhguru_sufijos else "en"
        
        # 1. Intentar obtener la cita en el idioma solicitado
        resultado = ejecutar_y_parsear_script(script_sadhguru, sufijo_web)
        
        # 2. Si falla o da error, reintentar en inglés como respaldo universal
        if not resultado.get("Cita") or "No se pudo obtener" in resultado.get("Cita", ""):
            if sufijo_web != "en":
                resultado = ejecutar_y_parsear_script(script_sadhguru, "en")
                sufijo_web = "en"
        
        fecha_str = resultado.get("Fecha", "").strip()
        if fecha_str:
            resultado["URL"] = f"https://isha.sadhguru.org/{sufijo_web}/wisdom/quotes/date/{fecha_str}"
            resultado["Fecha"] = f"Isha Sadhguru ({fecha_str})"
            
        # 3. Si el idioma de la sesión no es español ni inglés, traducimos el resultado obtenido
        if lang_lower not in ["es", "en"] and resultado.get("Cita"):
            resultado["Cita"] = traducir_nativo(resultado["Cita"], target_lang=lang_lower, source_lang="en")

        return resultado

    elif autor_id == "prem_rawat":
        # En español usamos el archivo local banco.json
        if lang_lower == "es":
            json_banco_paths = [
                IMAGENES_QUOTES_DIR / "banco.json",
            ]
            banco_path = next((p for p in json_banco_paths if p.exists()), None)
            
            cita_elegida = ""
            url_elegida = "https://timelesstoday.tv/es"
            titulo_evento = ""
            cadena_extraida = ""
            
            if banco_path:
                try:
                    with open(banco_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if data and isinstance(data, list):
                            item = random.choice(data)
                            texto = str(item.get("cita", "")).strip()
                            titulo_evento = item.get("titulo", "").strip()
                            
                            match_firma = re.search(r'([“"„”\'«»]*)\s*Prem\s+Rawat\s*[,–\-—]?\s*(.+)$', texto, flags=re.IGNORECASE)
                            if match_firma:
                                texto = texto[:match_firma.start()].strip()
                                cadena_extraida = match_firma.group(2).strip()
                                cadena_extraida = re.sub(r'[.\s]+$', '', cadena_extraida).strip()
                            else:
                                texto = re.sub(r'[\s–\-—]*[“"„”\'«»]*\s*Prem\s+Rawat.*$', '', texto, flags=re.IGNORECASE).strip()
                            
                            texto = re.sub(r'[\s–\-—"“”\'\\.]+$', '', texto).strip()
                            texto = re.sub(r'^[“"„”\'«»]+', '', texto).strip()
                            
                            if texto.endswith(","):
                                texto = texto[:-1] + "."
                            elif texto and not texto.endswith((".", "!", "?", "…")):
                                texto += "."
                                
                            cita_elegida = texto
                            url_elegida = item.get("url") or "https://timelesstoday.tv/es"
                except Exception as e:
                    print(f"Error leyendo banco.json para Prem Rawat: {e}")
                    
            if not cita_elegida:
                cita_elegida = "La paz es la constante dentro de ti, no el evento que ocurre a tu alrededor."
                
            autor_str = "Prem Rawat"
            detalles = [d for d in [titulo_evento, cadena_extraida] if d]
            if detalles:
                autor_str += f" ({', '.join(detalles)})"

            return {
                "Cita": cita_elegida,
                "Autor": autor_str,
                "Fecha": "Timeless Today" if url_elegida else "Archivo Local",
                "URL": url_elegida,
            }
        
        else:
            # En otros idiomas: intentar ejecutar el script de Prem Rawat
            script_prem = "/usr/share/wallpaper_manager/Buenas_imágenes_citas/prem_rawat_quotes.py"
            prem_sufijos = ["en", "fr", "de", "hi", "it", "el", "ja", "pt", "zh-cn", "zh-tw", "ta"]
            
            sufijo_prem = lang_lower if lang_lower in prem_sufijos else "en"
            resultado = ejecutar_y_parsear_script(script_prem, sufijo_prem)
            
            # Si el script externo falla, da error 429 o no trae cita válida, usamos el respaldo local (banco.json)
            if not resultado or not resultado.get("Cita") or "No se pudo obtener" in resultado.get("Cita", ""):
                banco_path = IMAGENES_QUOTES_DIR / "banco.json"
                if banco_path.exists():
                    try:
                        with open(banco_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            if data and isinstance(data, list):
                                item = random.choice(data)
                                texto = str(item.get("cita", "")).strip()
                                # Limpieza básica de la firma si la trae
                                texto = re.sub(r'[\s–\-—]*[“"„”\'«»]*\s*Prem\s+Rawat.*$', '', texto, flags=re.IGNORECASE).strip()
                                texto = re.sub(r'[\s–\-—"“”\'\\.]+$', '', texto).strip()
                                texto = re.sub(r'^[“"„”\'«»]+', '', texto).strip()
                                if texto and not texto.endswith((".", "!", "?", "…")):
                                    texto += "."
                                
                                resultado = {
                                    "Cita": texto,
                                    "Autor": "Prem Rawat",
                                    "Fecha": "Archivo Local (Respaldo)",
                                    "URL": item.get("url") or "https://timelesstoday.tv/es"
                                }
                    except Exception as e:
                        print(f"Error cargando respaldo local para Prem Rawat: {e}")

            # Si el idioma solicitado no es inglés y tenemos cita, traducimos al idioma de destino
            if lang_lower != "en" and resultado.get("Cita"):
                resultado["Cita"] = traducir_texto(resultado["Cita"], target_lang=lang_lower, source_lang="en")
                
            return resultado

    elif autor_id == "siva":
        archivos_siva = [
            "Las enseñanzas del Dr Siva.txt",
            "Dr Siva P s teachings.txt",
        ]
        # Seleccionar el archivo según el idioma objetivo preferido primero
        if lang == "en":
            citas = obtener_cita_desde_txt(["Dr Siva P s teachings.txt"], patron_fallback="siva")
            if not citas:
                citas = obtener_cita_desde_txt(["Las enseñanzas del Dr Siva.txt"], patron_fallback="siva")
        else:
            citas = obtener_cita_desde_txt(["Las enseñanzas del Dr Siva.txt"], patron_fallback="siva")
            if not citas:
                citas = obtener_cita_desde_txt(["Dr Siva P s teachings.txt"], patron_fallback="siva")

        cita_sel = (
            random.choice(citas)
            if citas
            else "El perdón es la llave que abre todas las puertas de la sanación."
        )

        # Si el texto obtenido necesita traducción
        # Traducir al idioma seleccionado de la lista de 23 idiomas (si no es español base)
        if lang and lang != "es":
            cita_sel = traducir_texto(cita_sel, target_lang=lang, source_lang="auto")

        return {
            "Cita": cita_sel,
            "Autor": "Dr. Siva P.",
            "Fecha": "PVH",
            "URL": SIVA_METADATA_URLS,
        }

    elif autor_id == "ravi_shankar":
        # Priorizar el archivo correspondiente al idioma seleccionado
        if lang == "en":
            archivos = ["Sri Sri Ravi Shankar quotes.txt", "Citas de Sri Sri Ravi Shankar.txt"]
        else:
            archivos = ["Citas de Sri Sri Ravi Shankar.txt", "Sri Sri Ravi Shankar quotes.txt"]

        cita_sel = "La sonrisa es la verdadera riqueza del alma."
        url_meta = ""
        encontrado = False

        directorios_a_buscar = [QUOTES_DIR, IMAGENES_QUOTES_DIR, HOME_DIR]
        
        for nombre_archivo in archivos:
            if encontrado:
                break
            for direct in directorios_a_buscar:
                f_path = direct / nombre_archivo
                if f_path.exists():
                    try:
                        with open(f_path, "r", encoding="utf-8", errors="ignore") as f:
                            lineas = [l.strip() for l in f.readlines() if l.strip()]
                        
                        # Buscar pares de (cita, /quote/ID)
                        pares = []
                        i = 0
                        while i < len(lineas) - 1:
                            l1 = lineas[i]
                            l2 = lineas[i+1]
                            if l1.startswith("[") and l2.startswith("/quote/"):
                                pares.append((l1, l2))
                                i += 2
                            else:
                                i += 1
                        
                        if pares:
                            linea_cita, linea_url = random.choice(pares)
                            # Limpiar ID de la cita
                            match = re.match(r"^\[\d+\]\s*(.+)$", linea_cita)
                            cita_sel = match.group(1).strip() if match else linea_cita
                            # Construir URL directa tal como indicaste
                            url_meta = f"https://www.azquotes.com{linea_url}"
                            encontrado = True
                            break
                    except Exception as e:
                        print(f"Error leyendo {f_path}: {e}")

        # Traducir según corresponda permitiendo auto-detección del origen
        if lang and lang != "es":
            cita_sel = traducir_texto(cita_sel, target_lang=lang, source_lang="auto")

        return {
            "Cita": cita_sel,
            "Autor": "Sri Sri Ravi Shankar",
            "Fecha": "AZ Quotes" if url_meta else "Archivo Local",
            "URL": url_meta,
        }

    elif autor_id == "otros":
        return obtener_cita_otros_autores_script(autor_otro, lang)

    else:
        return {
            "Cita": "El conocimiento libera la mente.",
            "Autor": "Autor Desconocido",
            "Fecha": "",
            "URL": "",
        }


def descargar_archivo(url, destino_path):
    req = urllib.request.Request(url, headers=HTTP_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as response, open(destino_path, "wb") as out_file:
        out_file.write(response.read())

# ----------------------------------------------------------------------
# RENDERIZADO CON PILLOW
# ----------------------------------------------------------------------
def wrap_text(text, font, max_width, draw):
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            current = test
        else:
            if current: lines.append(current)
            current = word
    if current: lines.append(current)
    return lines


def generate_composite_image(bg_path, quote_text, author_text, font_path=None, font_size=42, offset_x=0, offset_y=0, align_mode="center", width_ratio=0.7, draw_background=True, cita_data=None, item_data=None
):
    bg_image = Image.open(bg_path).convert("RGB")

    # --- ¡OPTIMIZACIÓN CRUCIAL PARA LA CPU! ---
    bg_image.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
    # ------------------------------------------

    canvas_w, canvas_h = bg_image.size


    try:
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    overlay = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)

    dummy = Image.new("RGB", (1, 1))
    draw_dummy = ImageDraw.Draw(dummy)

    # --- 1. RECUPERAMOS EL ANCHO USANDO EL BOTÓN (width_ratio) ---
    box_w = int(canvas_w * width_ratio)
    max_text_w = box_w - 40

    # --- 2. VERIFICACIÓN Y ENVOLTURA DE TEXTOS ---
    if quote_text and quote_text.strip():
        clean_quote = quote_text.strip("“”).")

        if not clean_quote.endswith(('.', '!', '?')):
            clean_quote = clean_quote + "."

        lines_quote = wrap_text(f"“{clean_quote}”", font, max_text_w, draw_dummy)
    else:
        lines_quote = []

    author_line = f"— {author_text}" if author_text and author_text.strip() else ""
    author_lines_wrapped = []
    if author_line:
        author_lines_wrapped = wrap_text(author_line, font, max_text_w, draw_dummy)

    all_lines = lines_quote + author_lines_wrapped

    # --- 3. CÁLCULO DE ALTURA Y POSICIÓN DE LA CAJA ---
    if all_lines:
        bbox = draw_dummy.textbbox((0, 0), "Ag", font=font)
        line_h = bbox[3] - bbox[1] + 8
        
        # Sumamos todas las líneas reales para que la caja no corte al autor por abajo
        total_lines_count = len(lines_quote) + len(author_lines_wrapped)
        box_h = (total_lines_count * line_h) + 50

        margin = 20
        hpos = max(margin, min(margin + offset_x, canvas_w - box_w - margin))
        vpos = max(margin, min(margin + offset_y, canvas_h - box_h - margin))

        if draw_background:
            small = bg_image.resize((1, 1), Image.Resampling.LANCZOS).convert("RGB")
            pixel = small.getpixel((0, 0))
            r, g, b = pixel[0], pixel[1], pixel[2]
            draw_overlay.rectangle([hpos, vpos, hpos + box_w, vpos + box_h], fill=(r, g, b, 150))
    else:
        hpos, vpos, box_h, line_h = 0, 0, 0, 0

    result = Image.alpha_composite(bg_image.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(result)


    # --- 4. FUNCIÓN DE ALINEACIÓN CON EL // 2 CORREGIDO ---
    def calcular_x(line_text, align_type):
        line_box = draw.textbbox((0, 0), line_text, font=font)
        line_w = line_box[2] - line_box[0]
        if align_type == "left":
            return hpos + 20
        elif align_type == "right":
            return hpos + box_w - line_w - 20
        else:
            return hpos + (box_w - line_w) // 2  # <-- ¡Aquí va el // 2 para equilibrar el margen derecho!

    if align_mode == "left":
        q_align, a_align = "left", "left"
    elif align_mode == "right":
        q_align, a_align = "right", "right"
    elif align_mode == "q_left_a_right":
        q_align, a_align = "left", "right"
    elif align_mode == "q_right_a_left":
        q_align, a_align = "right", "left"
    else:
        q_align, a_align = "center", "center"

    text_y = vpos + 25
    min_top_y = vpos + 20
    if text_y < min_top_y:
        text_y = min_top_y

    # --- 5. RENDERIZADO DE LÍNEAS DE CITA ---
    for line in lines_quote:
        text_x = calcular_x(line, q_align)
        if TEXT_SHADOW:  
            draw.text((text_x + 2, text_y + 2), line, font=font, fill=(0, 0, 0, 180))
        draw.text((text_x, text_y), line, font=font, fill=(255, 255, 255, 255))
        text_y += line_h

    # --- 6. RENDERIZADO DE LA FIRMA / AUTOR ---
    if author_line:
        for author_l in author_lines_wrapped:
            author_w = draw_dummy.textbbox((0, 0), author_l, font=font)[2] - draw_dummy.textbbox((0, 0), author_l, font=font)[0]
            
            if a_align == "right":
                author_draw_x = hpos + box_w - author_w - 20
            elif a_align == "left":
                author_draw_x = hpos + 20
            else: 
                author_draw_x = hpos + (box_w - author_w) // 2

            if TEXT_SHADOW:
                draw.text(
                    (int(author_draw_x + 2), int(text_y + 2)),
                    author_l,
                    font=font,
                    fill=(0, 0, 0, 180),
                )

            draw.text(
                (int(author_draw_x), int(text_y)),
                author_l,
                font=font,
                fill=(255, 255, 255, 255),
            )
            text_y += line_h

    # --- 7. PROCESAMIENTO EXIF Y RETORNO ---
    img_final = result.convert("RGB")
    
    cita_info = cita_data or {}
    item_info = item_data or {}

    metadata_texto = (
        f"Cita: {quote_text}\n"
        f"Autor: {author_text}\n"
        f"Fuente/Fecha: {cita_info.get('Fecha', 'N/A')}\n"
        f"URL Cita: {cita_info.get('URL', 'N/A')}\n"
        f"ID Imagen: {item_info.get('id', 'N/A')}\n"
        f"URL Imagen: {item_info.get('source_url', 'N/A')}"
    )

    exif = img_final.getexif()
    exif[270] = metadata_texto
    img_final.info["exif"] = exif.tobytes()

    return img_final

# ----------------------------------------------------------------------
# DIÁLOGOS Y VENTANAS GTK
# ----------------------------------------------------------------------
class AuthorSelectionDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(
            title="Seleccionar Autor (AZ Quotes)", 
            transient_for=parent, 
            modal=True, 
            destroy_with_parent=True
        )
        self.set_default_size(480, 520)
        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.autor_seleccionado = ""

        content = self.get_content_area()
        content.set_spacing(10)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        lbl_info = Gtk.Label(label="<b>Elige un autor de la lista o escribe en el buscador:</b>")
        lbl_info.set_use_markup(True)
        content.pack_start(lbl_info, False, False, 0)

        store = Gtk.ListStore(str)
        for autor in LISTA_OTROS_AUTORES:
            store.append([autor])

        completion = Gtk.EntryCompletion()
        completion.set_model(store)
        completion.set_text_column(0)

        self.txt_search = Gtk.Entry()
        self.txt_search.set_placeholder_text("Escribe cualquier autor (ej: Nikola Tesla)...")
        self.txt_search.set_completion(completion)
        content.pack_start(self.txt_search, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        flow = Gtk.FlowBox()
        flow.set_max_children_per_line(2)
        flow.set_selection_mode(Gtk.SelectionMode.SINGLE)

        for autor in LISTA_OTROS_AUTORES:
            btn = Gtk.Button(label=autor)
            btn.connect("clicked", self.on_autor_btn_clicked, autor)
            flow.add(btn)

        scrolled.add(flow)
        content.pack_start(scrolled, True, True, 0)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_random = Gtk.Button(label="🎲 Aleatorio")
        btn_random.connect("clicked", lambda w: self.confirmar(""))
        
        btn_accept = Gtk.Button(label="✔ Confirmar Búsqueda")
        btn_accept.connect("clicked", lambda w: self.confirmar(self.txt_search.get_text().strip()))

        btn_box.pack_start(btn_random, True, True, 0)
        btn_box.pack_start(btn_accept, True, True, 0)
        content.pack_start(btn_box, False, False, 0)

        self.show_all()

    def on_autor_btn_clicked(self, widget, autor):
        self.confirmar(autor)

    def confirmar(self, autor_nombre):
        self.autor_seleccionado = autor_nombre
        self.response(Gtk.ResponseType.OK)


class PreviewDialog(Gtk.Dialog):
    def __init__(self, parent, item_data, autor_otro_override=""):
        super().__init__(title="Vista Previa y Edición", transient_for=parent, flags=0)
        self.set_default_size(880, 600)
        self.set_resizable(True)
        self.set_deletable(True)
        
        # Forzar que el administrador de ventanas muestre minimizar/maximizar/cerrar
        self.set_type_hint(Gdk.WindowTypeHint.NORMAL)
        self.main_app = parent
        self.item_data = item_data
        self.autor_otro_actual = autor_otro_override or self.main_app.autor_otro_seleccionado
        
        # Cargar configuración de fuentes de forma correcta
        self.misma_fuente, font_path_leida = cargar_config_fuentes(FONTE_DEFAULT_FALLBACK)
        
        # Guardamos la ruta personalizada para cuando el usuario active el toggle después
        self.font_path_personalizada = font_path_leida if (font_path_leida and os.path.exists(str(font_path_leida))) else FONTE_DEFAULT_FALLBACK
        
        # APLICACIÓN DE LA REGLA DE ARRANQUE:
        # Si misma_fuente es True, usamos la guardada. Si es False, arrancamos obligatoriamente con el fallback por defecto.
        if self.misma_fuente:
            self.font_path = self.font_path_personalizada
        else:
            self.font_path = FONTE_DEFAULT_FALLBACK
        
        self.font_size = 42
        self.offset_x = 0
        self.offset_y = 0
        self.width_ratio = 0.7
        self.align_mode = "center"
        self.draw_background = True
        self.cita_data = {"Cita": "", "Autor": "", "Fecha": "", "URL": ""}

        if self.main_app.citas_activas:
            self.cita_data = obtener_cita_datos(
                self.main_app.autor_seleccionado,
                self.main_app.idioma_actual,
                self.autor_otro_actual,
            )

        main_box = self.get_content_area()
        main_box.set_spacing(6)
        main_box.set_margin_top(8)
        main_box.set_margin_bottom(8)
        main_box.set_margin_start(8)
        main_box.set_margin_end(8)

        # -------------------------------------------------------------
        # BARRA SUPERIOR DE CONTROLES (COMPACTA Y EN UNA SOLA LÍNEA)
        # -------------------------------------------------------------
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        top_bar.set_valign(Gtk.Align.CENTER)
        top_bar.set_halign(Gtk.Align.CENTER)

        # Provider CSS válido para GTK3 (sin propiedades no soportadas)
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            .compact-bar button, .compact-bar combobox, .compact-bar spinbutton {
                min-height: 22px;
                margin-top: 0px;
                margin-bottom: 0px;
                padding-top: 0px;
                padding-bottom: 0px;
                padding-left: 3px;
                padding-right: 3px;
            }
        """)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        top_bar.get_style_context().add_class("compact-bar")
        
        
        # Contenedor horizontal para todo lo de fuentes
        box_font = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box_font.pack_start(Gtk.Label(label="Fuente:"), False, False, 0)

        # ListStore con 3 columnas: Columna 0 = Pixbuf, Columna 1 = Nombre, Columna 2 = Ruta
        self.font_store = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str)
        
        for font_path in SYSTEM_FONTS:
            font_name = os.path.basename(font_path)
            pixbuf_miniatura = None
            try:
                import cairo
                import io
                
                surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 45, 22)
                cr = cairo.Context(surface)
                cr.set_source_rgb(1, 1, 1)
                cr.paint()
                
                layout = PangoCairo.create_layout(cr)
                layout.set_text("Aa", -1)
                
                font_fam_limpia = os.path.splitext(font_name)[0].replace("-", " ")
                font_desc = Pango.FontDescription()
                font_desc.set_family(font_fam_limpia)
                font_desc.set_size(11 * Pango.SCALE)
                layout.set_font_description(font_desc)
                
                cr.set_source_rgb(0, 0, 0)
                cr.move_to(2, 2)
                PangoCairo.show_layout(cr, layout)
                
                bytes_io = io.BytesIO()
                surface.write_to_png(bytes_io)
                bytes_io.seek(0)
                loader = GdkPixbuf.PixbufLoader.new_with_type("png")
                loader.write(bytes_io.read())
                loader.close()
                pixbuf_miniatura = loader.get_pixbuf()
            except Exception:
                pixbuf_miniatura = None

            self.font_store.append([pixbuf_miniatura, font_name, font_path])

        self.combo_fonts = Gtk.ComboBox.new_with_model(self.font_store)
        self.combo_fonts.set_size_request(220, 26)
        
        # Renderizadores
        renderer_pixbuf = Gtk.CellRendererPixbuf()
        self.combo_fonts.pack_start(renderer_pixbuf, False)
        self.combo_fonts.add_attribute(renderer_pixbuf, "pixbuf", 0)

        renderer_text = Gtk.CellRendererText()
        renderer_text.set_property("ellipsize", Pango.EllipsizeMode.MIDDLE)
        self.combo_fonts.pack_start(renderer_text, True)
        self.combo_fonts.add_attribute(renderer_text, "text", 1)
        
        # Seleccionar la fuente actual guardada si existe en la lista
        if SYSTEM_FONTS:
            found_index = 0
            for i, row in enumerate(self.font_store):
                # Verificamos si la ruta de la fila coincide con self.font_path
                # Evitamos usar len() sobre el objeto row de PyGObject
                try:
                    if row[2] == self.font_path:
                        found_index = i
                        break
                except IndexError:
                    pass
            self.combo_fonts.set_active(found_index)

        # Mantenemos el combo SIEMPRE HABILITADO para que puedas abrir la lista cuando quieras
        self.combo_fonts.set_sensitive(True)
        self.combo_fonts.connect("changed", self.on_font_changed)
        
        box_font.pack_start(self.combo_fonts, False, False, 0)
        
        # El CheckButton de Misma fuente
        self.chk_misma_fuente = Gtk.CheckButton(label="Misma fuente")
        self.chk_misma_fuente.set_active(self.misma_fuente)
        self.chk_misma_fuente.connect("toggled", self.on_config_misma_fuente_toggled)
        box_font.pack_start(self.chk_misma_fuente, False, False, 0)

        top_bar.pack_start(box_font, False, False, 0)

        # 3. Los empaquetas en tu contenedor inferior del Preview
        font_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        # 2. Tamaño
        box_size = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        box_size.pack_start(Gtk.Label(label="Tam:"), False, False, 0)
        self.spin_size = Gtk.SpinButton.new_with_range(16, 120, 2)
        self.spin_size.set_size_request(60, 26)
        self.spin_size.set_value(self.font_size)
        self.spin_size.connect("value-changed", self.on_size_changed)
        box_size.pack_start(self.spin_size, False, False, 0)
        top_bar.pack_start(box_size, False, False, 0)

        # 3. Ancho
        box_width = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        box_width.pack_start(Gtk.Label(label="Ancho:"), False, False, 0)
        btn_w_dec = Gtk.Button(label="➖")
        btn_w_dec.set_size_request(26, 26)
        btn_w_dec.connect("clicked", lambda w: self.ajustar_ancho(-0.05))
        btn_w_inc = Gtk.Button(label="➕")
        btn_w_inc.set_size_request(26, 26)
        btn_w_inc.connect("clicked", lambda w: self.ajustar_ancho(0.05))
        box_width.pack_start(btn_w_dec, False, False, 0)
        box_width.pack_start(btn_w_inc, False, False, 0)
        top_bar.pack_start(box_width, False, False, 0)

        # 4. Alineación
        box_align = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        box_align.pack_start(Gtk.Label(label="Alínea:"), False, False, 0)
        self.combo_align = Gtk.ComboBoxText()
        self.combo_align.set_size_request(120, 26)
        self.combo_align.append("center", "↔ Centrado")
        self.combo_align.append("left", "⇤ Izquierda")
        self.combo_align.append("right", "⇥ Derecha")
        self.combo_align.append("q_left_a_right", " Cita ⇤ / Autor ⇥")
        self.combo_align.append("q_right_a_left", " Cita ⇥ / Autor ⇤")
        self.combo_align.set_active(0)
        self.combo_align.connect("changed", self.on_align_changed)
        box_align.pack_start(self.combo_align, False, False, 0)
        top_bar.pack_start(box_align, False, False, 0)
        
        self.chk_bg = Gtk.CheckButton(label="𝘉𝘖𝘟𝘌𝘚")
        self.chk_bg.set_active(True)
        self.chk_bg.connect("toggled", self.on_toggle_fondo)
        top_bar.pack_start(self.chk_bg, False, False, 0)


        # 5. Movimiento (4 botones en horizontal pura)
        box_pad = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        box_pad.pack_start(Gtk.Label(label="Mover:"), False, False, 0)
        
        btn_left = Gtk.Button(label="◄")
        btn_up = Gtk.Button(label="▲")
        btn_down = Gtk.Button(label="▼")
        btn_right = Gtk.Button(label="►")

        for b in (btn_left, btn_up, btn_down, btn_right):
            b.set_size_request(26, 26)

        btn_left.connect("clicked", lambda w: self.mover_posicion(-40, 0))
        btn_up.connect("clicked", lambda w: self.mover_posicion(0, -40))
        btn_down.connect("clicked", lambda w: self.mover_posicion(0, 40))
        btn_right.connect("clicked", lambda w: self.mover_posicion(40, 0))

        box_pad.pack_start(btn_left, False, False, 0)
        box_pad.pack_start(btn_up, False, False, 0)
        box_pad.pack_start(btn_down, False, False, 0)
        box_pad.pack_start(btn_right, False, False, 0)
        top_bar.pack_start(box_pad, False, False, 0)

        # 6. Botón de Información
        btn_info = Gtk.Button(label="ℹ️ Info")
        btn_info.set_size_request(60, 26)
        btn_info.connect("clicked", self.mostrar_info_metadatos)
        top_bar.pack_start(btn_info, False, False, 0)
        
        main_box.pack_start(top_bar, False, False, 2)        

        # -------------------------------------------------------------
        # ÁREA DE VISTA PREVIA (DINÁMICA)
        # -------------------------------------------------------------
        self.image_widget = Gtk.Image()
        scrolled_preview = Gtk.ScrolledWindow()
        scrolled_preview.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_preview.add(self.image_widget)
        main_box.pack_start(scrolled_preview, True, True, 0)

        # -------------------------------------------------------------
        # ACCIONES INFERIORES
        # -------------------------------------------------------------
        action_bar_1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        action_bar_1.set_halign(Gtk.Align.CENTER)

        btn_open_local = Gtk.Button(label="📂 Abrir Imagen")
        btn_open_local.connect("clicked", self.on_abrir_imagen_local)
        action_bar_1.pack_start(btn_open_local, False, False, 0)

        btn_custom_quote = Gtk.Button(label="✏️ Escribir Cita")
        btn_custom_quote.connect("clicked", self.on_escribir_cita)
        action_bar_1.pack_start(btn_custom_quote, False, False, 0)

        btn_change_quote = Gtk.Button(label="🔄 Cambiar Cita")
        btn_change_quote.connect("clicked", self.on_cambiar_cita)
        action_bar_1.pack_start(btn_change_quote, False, False, 0)

        btn_change_img = Gtk.Button(label="🖼️ Cambiar Imagen")
        btn_change_img.connect("clicked", self.on_cambiar_imagen)
        action_bar_1.pack_start(btn_change_img, False, False, 0)
        main_box.pack_start(action_bar_1, False, False, 0)

        action_bar_2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        action_bar_2.set_halign(Gtk.Align.CENTER)

        btn_dl_raw = Gtk.Button(label="📥 Solo Imagen")
        btn_dl_raw.connect("clicked", self.on_descargar_solo_imagen)
        action_bar_2.pack_start(btn_dl_raw, False, False, 0)

        btn_dl_comp = Gtk.Button(label="💾 Guardar con Cita")
        btn_dl_comp.connect("clicked", self.on_descargar_con_cita)
        action_bar_2.pack_start(btn_dl_comp, False, False, 0)

        btn_set_wallpaper = Gtk.Button(label="🖥️ Set as wallpaper")
        btn_set_wallpaper.connect("clicked", self.on_set_as_wallpaper)
        action_bar_2.pack_start(btn_set_wallpaper, False, False, 0)

        btn_copy = Gtk.Button(label="📋 Copiar Cita")
        btn_copy.connect("clicked", self.on_copiar_cita)
        action_bar_2.pack_start(btn_copy, False, False, 0)

        main_box.pack_start(action_bar_2, False, False, 0)

        self.hd_image_path = TEMP_DIR / f"full_{item_data['id']}.jpg"
        self.connect("size-allocate", self.on_window_resized)
        self.show_all()
        self.cargar_y_renderizar_async()
        self.set_resizable(True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        
        self.connect("key-press-event", self.on_preview_key_press)
    
    def on_preview_key_press(self, widget, event):
        # Detecta Ctrl + W (o w mayúscula)
        if event.state & Gdk.ModifierType.CONTROL_MASK and event.keyval in (Gdk.KEY_w, Gdk.KEY_W):
            self.destroy()
            return True
        return False
        
    def on_config_misma_fuente_toggled(self, button):
        estado = button.get_active()
        
        # 1. Aseguramos tener la ruta personalizada guardada en memoria
        if not hasattr(self, 'font_path_personalizada') or not self.font_path_personalizada:
            self.font_path_personalizada = getattr(self, 'font_path', FONTE_DEFAULT_FALLBACK)
            
        # 2. Guardamos en el JSON el estado (false/true) y la ruta personalizada intacta
        guardar_config_fuentes(estado, self.font_path_personalizada)
        
        # 3. AQUÍ ESTÁ EL CAMBIO: Asignamos explícitamente a la variable que usa el renderizador
        if estado:
            self.font_path = self.font_path_personalizada
        else:
            self.font_path = FONTE_DEFAULT_FALLBACK
            
        # 4. Forzamos el renderizado inmediato al vuelo
        self.cargar_y_renderizar_async()

    def on_window_resized(self, widget, allocation):
        # Re-renderiza de forma óptima al cambiar el tamaño de ventana
        GLib.idle_add(self.renderizar_vista_previa)

    def ajustar_ancho(self, delta):
        self.width_ratio = max(0.3, min(0.9, self.width_ratio + delta))
        self.renderizar_vista_previa()

    def mover_posicion(self, dx, dy):
        self.offset_x = max(0, self.offset_x + dx)
        self.offset_y = max(0, self.offset_y + dy)
        self.renderizar_vista_previa()

    def on_toggle_fondo(self, widget):
        self.draw_background = widget.get_active()
        self.renderizar_vista_previa()

    def on_align_changed(self, combo):
        self.align_mode = combo.get_active_id()
        self.renderizar_vista_previa()

    def on_font_changed(self, combo):
        tree_iter = combo.get_active_iter()
        if tree_iter is not None:
            model = combo.get_model()
            font_path = model[tree_iter][2]  # Ruta completa de la fuente
            if font_path and os.path.exists(font_path):
                self.font_path = font_path
                self.misma_fuente = False
                if hasattr(self, "chk_misma_fuente"):
                    self.chk_misma_fuente.set_active(False)
                
                guardar_config_fuentes(self.misma_fuente, self.font_path)
                self.renderizar_vista_previa()

    def on_size_changed(self, spin):
        self.font_size = int(spin.get_value())
        self.renderizar_vista_previa()

    def cargar_y_renderizar_async(self):
        def worker():
            try:
                if "local_path" in self.item_data:
                    hd_path = Path(self.item_data["local_path"])
                else:
                    hd_path = TEMP_DIR / f"full_{self.item_data['id']}.jpg"
                    if not hd_path.exists():
                        descargar_archivo(self.item_data["full_url"], hd_path)
                self.hd_image_path = hd_path
                self.main_app.imagenes_limpias_abiertas.add(str(hd_path))
                GLib.idle_add(self.renderizar_vista_previa)
            except Exception as e:
                print(f"Error procesando vista previa: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def renderizar_vista_previa(self):
            if not self.hd_image_path.exists():
                return False
            
            comp = None
            pixbuf = None
            try:
                comp = generate_composite_image(
                    str(self.hd_image_path),
                    self.cita_data.get("Cita", "") if self.main_app.citas_activas else "",
                    self.cita_data.get("Autor", "") if self.main_app.citas_activas else "",
                    font_path=self.font_path,
                    font_size=self.font_size,
                    offset_x=self.offset_x,
                    offset_y=self.offset_y,
                    align_mode=self.align_mode,
                    width_ratio=self.width_ratio,
                    draw_background=self.draw_background,
                    cita_data=self.cita_data,
                    item_data=self.item_data               
                )
                preview_path = TEMP_DIR / "preview_current.jpg"
                comp.save(preview_path, quality=90)
    
                # Obtener dimensiones disponibles para escalar adecuadamente la imagen
                alloc = self.image_widget.get_allocation()
                max_w = max(alloc.width, 700)
                max_h = max(alloc.height, 400)
    
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(preview_path), max_w, max_h, True)
                self.image_widget.set_from_pixbuf(pixbuf)
            except Exception as e:
                print(f"Error renderizando vista previa: {e}")
            finally:
                # Eliminamos las referencias locales pesadas antes del gc
                del comp
                del pixbuf
                gc.collect()
    
            return False

    def on_cambiar_cita(self, widget):
        self.cita_data = obtener_cita_datos(
            self.main_app.autor_seleccionado,
            self.main_app.idioma_actual,
            self.autor_otro_actual,
        )
        self.renderizar_vista_previa()

    def on_cambiar_imagen(self, widget):
        if self.main_app.imagenes_cache:
            self.item_data = random.choice(self.main_app.imagenes_cache)
            self.hd_image_path = TEMP_DIR / f"full_{self.item_data['id']}.jpg"
            self.cargar_y_renderizar_async()

    def on_abrir_imagen_local(self, widget):
        dialog = Gtk.FileChooserDialog(
            title="Seleccionar una Imagen Local",
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, 
            Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT
        )
        filter_img = Gtk.FileFilter()
        filter_img.set_name("Imágenes")
        filter_img.add_mime_type("image/jpeg")
        filter_img.add_mime_type("image/png")
        filter_img.add_mime_type("image/webp")
        dialog.add_filter(filter_img)

        if dialog.run() == Gtk.ResponseType.ACCEPT:
            filepath = dialog.get_filename()
            self.item_data = {
                "id": f"local_{random.randint(100, 999)}",
                "local_path": filepath,
                "source_url": filepath,
            }
            self.hd_image_path = Path(filepath)
            self.cargar_y_renderizar_async()
        dialog.destroy()

    def on_escribir_cita(self, widget):
        dialog = Gtk.Dialog(title="Escribir Cita Personalizada", transient_for=self, flags=0)
        dialog.set_default_size(600, 260)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK)

        content = dialog.get_content_area()
        content.set_spacing(8)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        content.pack_start(Gtk.Label(label="Escribe la cita:"), False, False, 0)
        text_view = Gtk.TextView()
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        text_view.set_vexpand(True)
        buffer = text_view.get_buffer()
        buffer.set_text(self.cita_data.get("Cita", ""))
        content.pack_start(text_view, True, True, 0)

        content.pack_start(Gtk.Label(label="Autor (opcional):"), False, False, 0)
        author_entry = Gtk.Entry()
        author_entry.set_text(self.cita_data.get("Autor", ""))
        content.pack_start(author_entry, False, False, 0)

        dialog.show_all()
        if dialog.run() == Gtk.ResponseType.OK:
            start, end = buffer.get_bounds()
            self.cita_data["Cita"] = buffer.get_text(start, end, True).strip()
            self.cita_data["Autor"] = author_entry.get_text().strip()
            if self.cita_data["Cita"]:
                self.main_app.citas_activas = True

            self.renderizar_vista_previa()
        dialog.destroy()

    def mostrar_mensaje(self, titulo, texto, message_type=Gtk.MessageType.INFO):
        dialog = Gtk.MessageDialog(
            transient_for=self, flags=0, message_type=message_type,
            buttons=Gtk.ButtonsType.OK, text=titulo
        )
        dialog.format_secondary_text(texto)
        dialog.run()
        dialog.destroy()

    def mostrar_mensaje_url(self, titulo, texto, message_type=Gtk.MessageType.INFO):
        dialog = Gtk.MessageDialog(
            transient_for=self, flags=0, message_type=message_type,
            buttons=Gtk.ButtonsType.OK, text=titulo
        )
        
        # Aplicar Pango Markup directamente al texto secundario
        dialog.format_secondary_markup(texto)
        
        # Obtener la etiqueta secundaria y habilitar selección y enlaces
        label_secundario = dialog.get_message_area().get_children()[1]
        if isinstance(label_secundario, Gtk.Label):
            label_secundario.set_selectable(True)
            label_secundario.set_use_markup(True)
    
        # Mostrar todos los elementos antes de bloquear con run()
        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def on_set_as_wallpaper(self, widget):
        if not self.hd_image_path.exists():
            return
        try:
            comp = generate_composite_image(
                str(self.hd_image_path),
                self.cita_data.get("Cita", "") if self.main_app.citas_activas else "",
                self.cita_data.get("Autor", "") if self.main_app.citas_activas else "",
                font_path=self.font_path,
                font_size=self.font_size,
                offset_x=self.offset_x,
                offset_y=self.offset_y,
                align_mode=self.align_mode,
                width_ratio=self.width_ratio,
                draw_background=self.draw_background,
                cita_data=self.cita_data,
                item_data=self.item_data
            )
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"quote_{self.item_data.get('id', 'imagen')}_{timestamp}.jpg"
            save_path = SAVE_DIR / filename
            if "exif" in comp.info:
                comp.save(save_path, quality=100, exif=comp.info["exif"])
            else:
                comp.save(save_path, quality=100)
            file_uri = save_path.as_uri()
            try:
                color_scheme = subprocess.check_output(
                    ['gsettings', 'get', 'org.gnome.desktop.interface', 'color-scheme'],
                    text=True
                ).strip().strip("'")
            except Exception:
                color_scheme = "default"

            key = "picture-uri-dark" if "dark" in color_scheme.lower() else "picture-uri"
            cmd_wallpaper = f'gsettings set org.gnome.desktop.background {key} "{file_uri}"'
            subprocess.Popen(cmd_wallpaper, shell=True)

            cmd_history = "sh /usr/share/wallpaper_manager/w_m/actions/ir-prev.sh"
            subprocess.Popen(cmd_history, shell=True)

            self.mostrar_mensaje_url(
                "¡Fondo Aplicado!",
                f"La imagen fue guardada y establecida como fondo de pantalla:\n{save_path}"
            )
        except Exception as e:
            self.mostrar_mensaje_url("Error", str(e), Gtk.MessageType.ERROR)

    def on_descargar_solo_imagen(self, widget):
        if not self.hd_image_path.exists():
            return
        nombre = f"wallpaper_{self.item_data.get('id', 'imagen')}.jpg"
        destino = SAVE_DIR / nombre
        try:
            shutil.copy2(self.hd_image_path, destino)
            self.mostrar_mensaje_url("¡Imagen guardada!", f"Guardada con éxito en:\n{destino}")
        except Exception as e:
            self.mostrar_mensaje_url("Error", str(e), Gtk.MessageType.ERROR)

    def on_descargar_con_cita(self, widget):
        if not self.hd_image_path.exists():
            return
        try:
            comp = generate_composite_image(
                str(self.hd_image_path),
                self.cita_data.get("Cita", "") if self.main_app.citas_activas else "",
                self.cita_data.get("Autor", "") if self.main_app.citas_activas else "",
                font_path=self.font_path,
                font_size=self.font_size,
                offset_x=self.offset_x,
                offset_y=self.offset_y,
                align_mode=self.align_mode,
                width_ratio=self.width_ratio,
                draw_background=self.draw_background,
                cita_data=self.cita_data,
                item_data=self.item_data
            )
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"quote_{self.item_data.get('id', 'imagen')}_{timestamp}.jpg"
            save_path = SAVE_DIR / filename
            if "exif" in comp.info:
                comp.save(save_path, quality=100, exif=comp.info["exif"])
            else:
                comp.save(save_path, quality=100)            

            self.mostrar_mensaje_url("¡Imagen Guardada!", f"Guardada con éxito en:\n{save_path}")
        except Exception as e:
            self.mostrar_mensaje_url("Error", str(e), Gtk.MessageType.ERROR)

    def on_copiar_cita(self, widget):
        texto_cita = self.cita_data.get("Cita", "").strip()
        autor = self.cita_data.get("Autor", "").strip()
        
        # Limpiamos guiones volantes o duplicados al final de la cita si los hubiera
        texto_cita = texto_cita.rstrip("— -")
        
        # Unimos de forma limpia una sola vez
        if autor and autor.lower() not in texto_cita.lower():
            texto_final = f"“{texto_cita}”\n— {autor}"
        else:
            texto_final = f"“{texto_cita}”"
            
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(texto_final, -1)

    def mostrar_info_metadatos(self, widget):
        # Función auxiliar para escapar texto plano pero no romper HTML
        def esc(val):
            return GLib.markup_escape_text(str(val)) if val else 'N/A'
    
        url_cita = self.cita_data.get('URL', '')
        url_img = self.item_data.get('source_url', '')
    
        # Construimos los links en formato Pango Markup
        link_cita = f'<a href="{esc(url_cita)}">{esc(url_cita)}</a>' if url_cita else 'N/A'
        link_img = f'<a href="{esc(url_img)}">{esc(url_img)}</a>' if url_img else 'N/A'
    
        texto = (
            f"• <b>Cita:</b> {esc(self.cita_data.get('Cita', 'N/A'))}\n"
            f"• <b>Autor:</b> {esc(self.cita_data.get('Autor', 'N/A'))}\n"
            f"• <b>Fuente/Fecha:</b> {esc(self.cita_data.get('Fecha', 'N/A'))}\n"
            f"• <b>URL Cita:</b> {link_cita}\n\n"
            f"• <b>ID Imagen:</b> {esc(self.item_data.get('id', 'N/A'))}\n"
            f"• <b>URL Imagen:</b> {link_img}"
        )
    
        self.mostrar_mensaje_url("Metadatos de la Imagen y Cita", texto)


class WallpaperManagerWindow(Gtk.Window):
    def __init__(self):
        super().__init__()
        
        header_bar = Gtk.HeaderBar()
        header_bar.set_show_close_button(True)
        header_bar.set_title("Wallpaper Manager — Citas & Wallpapers")
        self.set_titlebar(header_bar)

        self.set_default_size(910, 610)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.cancel_download_event = threading.Event()
        self.citas_activas = True
        self.autor_seleccionado = "prem_rawat"
        self.autor_otro_seleccionado = ""
        self.idioma_actual = cargar_config_idioma()
        self.imagenes_cache = []
        self.imagenes_limpias_abiertas = set()
        mapa_etiquetas_iniciales = {
            "es": "🇪🇸 ES", "en": "🇬🇧 EN", "ar": "🏳️ AR", "bn": "🇧🇩 BN",
            "de": "🇩🇪 DE", "el": "🇬🇷 EL", "fa": "🇮🇷 FA", "fr": "🇫🇷 FR",
            "gu": "🇮🇳 GU", "hi": "🇮🇳 HI", "id": "🇮🇩 ID", "it": "🇮🇹 IT",
            "ja": "🇯🇵 JA", "lt": "🇱🇹 LT", "pt": "🇧🇷 PT", "ro": "🇷🇴 RO",
            "ru": "🇷🇺 RU", "sk": "🇸🇰 SK", "ta": "🇮🇳 TA", "th": "🇹🇭 TH",
            "uk": "🇺🇦 UK", "zh-cn": "🇨🇳 ZH-CN", "zh-tw": "🇨🇳 ZH-TW"
        }

        self.preguntar_descargar_al_cerrar = cargar_config_preguntar()

        self.connect("delete-event", self.on_close_window)
        self.aplicar_estilos_css()

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_box.set_margin_top(12); main_box.set_margin_bottom(12)
        main_box.set_margin_start(12); main_box.set_margin_end(12)
        self.add(main_box)

        main_box.pack_start(self.crear_panel_superior(), False, False, 0)
        if hasattr(self, "btn_lang"):
            etiqueta_guardada = mapa_etiquetas_iniciales.get(self.idioma_actual, "🇪🇸 ES")
            self.btn_lang.set_label(etiqueta_guardada)
        main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 5)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(5)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.flowbox.connect("child-activated", self.on_imagen_doble_click)

        scrolled_window.add(self.flowbox)
        main_box.pack_start(scrolled_window, True, True, 0)

        bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.lbl_status = Gtk.Label(label="Listo.")
        bottom_bar.pack_start(self.lbl_status, False, False, 0)

        self.chk_preguntar = Gtk.CheckButton(label="Preguntar si descargar imágenes al cerrar")
        self.chk_preguntar.set_active(self.preguntar_descargar_al_cerrar)
        self.chk_preguntar.connect("toggled", self.on_config_preguntar_toggled)
        bottom_bar.pack_end(self.chk_preguntar, False, False, 0)
        
        # --- BOTÓN ABRIR CARPETA ---
        self.btn_open_folder = Gtk.Button(label=" 📂 +\n Folder ")
        self.btn_open_folder.set_sensitive(False)  # Deshabilitado por defecto (Modo ON)
        self.btn_open_folder.connect("clicked", self.on_btn_open_folder_clicked)
        
        # Empaquetamos en bottom_bar (junto al botón refresh)
        bottom_bar.pack_end(self.btn_open_folder, False, False, 0)

        # --- SWITCH ON / OFF (Insertado en bottom_bar a la derecha) ---
        lbl_switch = Gtk.Label(label=" ONLINE 🖼️ \n OFFLINE 📂 ")
        self.switch_online = Gtk.Switch()
        self.switch_online.set_active(True)  # ON por defecto
        self.switch_online.connect("state-set", self.on_switch_online_toggled)

        bottom_bar.pack_end(self.switch_online, False, False, 0)
        bottom_bar.pack_end(lbl_switch, False, False, 0)
        btn_refresh = Gtk.Button(label="🔄 Cargar más Imágenes")
        btn_refresh.connect("clicked", lambda w: self.cargar_imagenes_async())
        bottom_bar.pack_end(btn_refresh, False, False, 0)

        main_box.pack_start(bottom_bar, False, False, 0)
        self.cargar_imagenes_async()
        
        # En la inicialización de tu ventana principal
        self.connect("key-press-event", self.on_main_key_press)
        self.connect("delete-event", self.on_delete_event)


    def on_delete_event(self, widget, event):
            return False

    def on_main_key_press(self, widget, event):
        # Detecta Ctrl + Q
        if event.state & Gdk.ModifierType.CONTROL_MASK and event.keyval in (Gdk.KEY_q, Gdk.KEY_Q):
            self.close()  # Esto simula el cierre de la ventana y activa el control de la casilla
            return True
        return False

    def cargar_imagenes_locales(self, cantidad=25):
        """Carga hasta 25 imágenes desde los directorios locales"""
        dir_citas, dir_auto = obtener_directorios()
        
        # Extensiones válidas
        extensiones = ("*.jpg", "*.jpeg", "*.png", "*.webp")
        archivos_encontrados = []
        for ext in extensiones:
            archivos_encontrados.extend(dir_citas.glob(ext))
            archivos_encontrados.extend(dir_auto.glob(ext))
        
        # Barajar y limitar a la cantidad deseada (25 por defecto)
        import random
        random.shuffle(archivos_encontrados)
        archivos_seleccionados = archivos_encontrados[:cantidad]
        
        items_locales = []
        for p in archivos_seleccionados:
            img_id = f"local_{p.stem}"
            items_locales.append({
                "id": img_id,
                "thumb_path": str(p),
                "full_url": str(p),
                "local_path": str(p),
                "source_url": str(p)
            })
            
        return items_locales

    def on_switch_online_toggled(self, switch, state):
        """
        Callback del pasador.
        state == True -> ON (Descargas / Online)
        state == False -> OFF (Cancelar descargas y cargar 25 locales)
        """
        # Habilita 'Abrir Carpeta' solo cuando el switch esté en OFF (state == False)
        self.btn_open_folder.set_sensitive(not state)

        if not state:
            # --- OFF LINE ---
            self.cancel_download_event.set()
            self.lbl_status.set_text("Descargas canceladas. Cargando imágenes locales...")
            
            items_locales = self.cargar_imagenes_locales(cantidad=25)
            self.imagenes_cache = items_locales
            self.actualizar_flowbox_con_items(items_locales)
            self.lbl_status.set_text(f"Cargadas {len(items_locales)} imágenes locales.")
        else:
            # --- ON LINE ---
            self.cancel_download_event.clear()
            self.lbl_status.set_text("Modo Online activado.")
            self.cargar_imagenes_async()

        return False

    def on_btn_open_folder_clicked(self, widget):
        """Abre un diálogo de selección de carpeta si estamos en modo Offline"""
        if self.switch_online.get_active():
            return  # Seguridad extra: no hace nada si está en ON

        dialog = Gtk.FileChooserDialog(
            title="Seleccionar carpeta de imágenes",
            parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK
        )

        respuesta = dialog.run()
        if respuesta == Gtk.ResponseType.OK:
            carpeta_seleccionada = dialog.get_filename()
            dialog.destroy()
            
            # Cargar imágenes desde la nueva carpeta elegida
            items_locales = self.cargar_imagenes_desde_directorio(carpeta_seleccionada, cantidad=25)
            if items_locales:
                self.imagenes_cache = items_locales
                self.actualizar_flowbox_con_items(items_locales)
                self.lbl_status.set_text(f"Cargadas {len(items_locales)} imágenes desde carpeta personal.")
            else:
                self.lbl_status.set_text("No se encontraron imágenes compatibles en la carpeta seleccionada.")
        else:
            dialog.destroy()

    def cargar_imagenes_desde_directorio(self, ruta_dir, cantidad=25):
        """Escanea un directorio específico buscando formatos de imagen válidos"""
        from pathlib import Path
        import random

        path_obj = Path(ruta_dir)
        extensiones = ("*.jpg", "*.jpeg", "*.png", "*.webp")
        
        archivos_encontrados = []
        for ext in extensiones:
            archivos_encontrados.extend(path_obj.glob(ext))
            # Opcional: incluir variantes en mayúsculas (.JPG, .PNG, etc.)
            archivos_encontrados.extend(path_obj.glob(ext.upper()))

        random.shuffle(archivos_encontrados)
        archivos_seleccionados = archivos_encontrados[:cantidad]

        items_locales = []
        for p in archivos_seleccionados:
            img_id = f"custom_{p.stem}"
            items_locales.append({
                "id": img_id,
                "thumb_path": str(p),
                "full_url": str(p),
                "local_path": str(p),
                "source_url": str(p)
            })

        return items_locales

    def actualizar_flowbox_con_items(self, items):
        """Limpia el FlowBox y coloca las nuevas miniaturas obtenidas"""
        # Eliminar hijos anteriores
        for child in self.flowbox.get_children():
            self.flowbox.remove(child)
            
        for item in items:
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    item["thumb_path"], 180, 120, True
                )
                img = Gtk.Image.new_from_pixbuf(pixbuf)
                img.item_data = item
                self.flowbox.add(img)
            except Exception as e:
                print(f"Error al cargar miniatura local: {e}")
                
        self.flowbox.show_all()

    def crear_panel_superior(self):
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        
        # Inicializar o limpiar el diccionario antes de rellenarlo
        self.chk_estilos = {}

        # ------------------------------------------------------------------
        # 1. BLOQUE DE CITAS (Izquierda)
        # ------------------------------------------------------------------
        exp_citas = Gtk.Expander(label="<b>📜 Citas</b>")
        exp_citas.get_label_widget().set_use_markup(True)
        exp_citas.set_expanded(False)

        vbox_citas = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)

        box_citas_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.chk_citas = Gtk.CheckButton(label="Activar citas en imágenes")
        self.chk_citas.set_active(True)
        self.chk_citas.connect("toggled", self.on_citas_toggled)
        box_citas_header.pack_start(self.chk_citas, True, True, 0)
        
        # 1. Crear el Gtk.MenuButton para el panel superior
        self.btn_lang = Gtk.MenuButton()
        self.btn_lang.set_label("🇪🇸 ES")  # Etiqueta predeterminada inicial
        
        # 2. Crear el menú desplegable
        menu = Gtk.Menu()
        
        # Lista completa con los 23 idiomas y sus identificadores visuales
        idiomas = [
            ("ES", "🇪🇸 ES"),
            ("EN", "🇬🇧 EN"),      # Inglés
            ("AR", "🏳️ AR"),      # Árabe (ajustado con bandera neutral)
            ("BN", "🇧🇩 BN"),      # Bengalí (Bangladés)
            ("DE", "🇩🇪 DE"),      # Alemán
            ("EL", "🇬🇷 EL"),      # Griego
            ("FA", "🇮🇷 FA"),      # Persa (Irán)
            ("FR", "🇫🇷 FR"),      # Francés
            ("GU", "🇮🇳 GU"),      # Guyaratí
            ("HI", "🇮🇳 HI"),      # Hindi
            ("ID", "🇮🇩 ID"),      # Indonesio
            ("IT", "🇮🇹 IT"),      # Italiano
            ("JA", "🇯🇵 JA"),      # Japonés
            ("LT", "🇱🇹 LT"),      # Lituano
            ("PT", "🇧🇷 PT"),      # Portugués
            ("RO", "🇷🇴 RO"),      # Rumano
            ("RU", "🇷🇺 RU"),      # Ruso
            ("SK", "🇸🇰 SK"),      # Eslovaco
            ("TA", "🇮🇳 TA"),      # Tamil
            ("TH", "🇹🇭 TH"),      # Tailandés
            ("UK", "🇺🇦 UK"),      # Ucraniano
            ("ZH-CN", "🇨🇳 ZH-CN"), # Chino Simplificado
            ("ZH-TW", "🇹🇼 ZH-TW"), # Chino Tradicional
        ]
        
        for codigo, etiqueta_visual in idiomas:
            item = Gtk.MenuItem(label=etiqueta_visual)
            # Conectamos la señal para enviar el código en minúsculas o como lo requiera tu backend
            item.connect("activate", self.on_cambiar_idioma, codigo.lower())
            menu.append(item)
        
        menu.show_all()
        self.btn_lang.set_popup(menu)
        box_citas_header.pack_end(self.btn_lang, False, False, 0)

        vbox_citas.pack_start(box_citas_header, False, False, 0)

        self.vbox_autores = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.vbox_autores.set_margin_start(12)

        r1 = Gtk.RadioButton.new_with_label(None, "Prem Rawat")
        r1.connect("toggled", self.on_autor_changed, "prem_rawat")
        r2 = Gtk.RadioButton.new_with_label_from_widget(r1, "Sadhguru")
        r2.connect("toggled", self.on_autor_changed, "sadhguru")
        r3 = Gtk.RadioButton.new_with_label_from_widget(r1, "Siva P. de PVH")
        r3.connect("toggled", self.on_autor_changed, "siva")
        r4 = Gtk.RadioButton.new_with_label_from_widget(r1, "Sri Sri Ravi Shankar")
        r4.connect("toggled", self.on_autor_changed, "ravi_shankar")
        r5 = Gtk.RadioButton.new_with_label_from_widget(r1, "Otros autores (Búsqueda / Aleatorio)")
        r5.connect("toggled", self.on_autor_changed, "otros")

        for r in [r1, r2, r3, r4, r5]:
            self.vbox_autores.pack_start(r, False, False, 0)

        vbox_citas.pack_start(self.vbox_autores, False, False, 0)
        exp_citas.add(vbox_citas)
        hbox.pack_start(exp_citas, False, False, 0)

        # ------------------------------------------------------------------
        # 2. SPACER A LA IZQUIERDA DEL MEDIO (Empuja las citas y los estilos)
        # ------------------------------------------------------------------
        spacer1 = Gtk.Box()
        hbox.pack_start(spacer1, True, True, 0)

        # ------------------------------------------------------------------
        # 3. BLOQUE DE ESTILOS (Centro / Derecha)
        # ------------------------------------------------------------------
        exp_estilos = Gtk.Expander(label="<b>🎨 Estilos de imágenes</b>")
        exp_estilos.get_label_widget().set_use_markup(True)
        exp_estilos.set_expanded(False)

        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(4)

        row, col = 0, 0
        for nombre, info in IMAGE_STYLES.items():
            chk = Gtk.CheckButton(label=nombre)
            chk.set_active(info["activo"]) 
            self.chk_estilos[info["query"]] = chk
            
            grid.attach(chk, col, row, 1, 1)
            col += 1
            if col > 1: 
                col = 0
                row += 1

        exp_estilos.add(grid)
        hbox.pack_start(exp_estilos, False, False, 0)

        # Spacer secundario opcional si quieres separar estilos del botón derecho
        spacer2 = Gtk.Box()
        hbox.pack_start(spacer2, True, True, 0)

        # ------------------------------------------------------------------
        # 4. BOTÓN APP INDICATOR (Extremo Derecho)
        # ------------------------------------------------------------------
        btn_indicator = Gtk.Button()
        btn_indicator.set_relief(Gtk.ReliefStyle.NONE)
        
        icono_path = "/usr/share/wallpaper_manager/w_m/iconos/wallpaper-manager.png"
        if os.path.exists(icono_path):
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(icono_path, 18, 18, True)
            img_icono = Gtk.Image.new_from_pixbuf(pixbuf)
        else:
            img_icono = Gtk.Image.new_from_icon_name("applications-system", Gtk.IconSize.BUTTON)
            
        btn_indicator.add(img_icono)
        btn_indicator.set_tooltip_text("Wallpaper Manager App Indicator")

        def al_pulsar_indicator(widget):
            try:
                resultado = subprocess.run(["pgrep", "-f", "wm-app-indicador"], capture_output=True, text=True)
                if resultado.stdout.strip():
                    subprocess.run(["notify-send", "Wallpaper Manager", "Wallpaper Manager App Indicator it's running"])
                    return
            except Exception as e:
                print(f"Error al comprobar el proceso: {e}")

            try:
                subprocess.Popen(["python3", "/usr/share/wallpaper_manager/w_m/wm-app-indicador"])
            except Exception as e:
                print(f"Error al iniciar el indicator: {e}")

        btn_indicator.connect("clicked", al_pulsar_indicator)
        hbox.pack_end(btn_indicator, False, False, 0)

        return hbox


    def on_cambiar_idioma(self, widget, codigo):
        # Mapeo de códigos a sus etiquetas visuales
        mapa_idiomas = {
            "es": "🇪🇸 ES",
            "en": "🇬🇧 EN",
            "ar": "🏳️ AR",
            "bn": "🇧🇩 BN",
            "de": "🇩🇪 DE",
            "el": "🇬🇷 EL",
            "fa": "🇮🇷 FA",
            "fr": "🇫🇷 FR",
            "gu": "🇮🇳 GU",
            "hi": "🇮🇳 HI",
            "id": "🇮🇩 ID",
            "it": "🇮🇹 IT",
            "ja": "🇯🇵 JA",
            "lt": "🇱🇹 LT",
            "pt": "🇧🇷 PT",
            "ro": "🇷🇴 RO",
            "ru": "🇷🇺 RU",
            "sk": "🇸🇰 SK",
            "ta": "🇮🇳 TA",
            "th": "🇹🇭 TH",
            "uk": "🇺🇦 UK",
            "zh-cn": "🇨🇳 ZH-CN",
            "zh-tw": "🇨🇳 ZH-TW",
        }

        self.idioma_actual = codigo

        if codigo in mapa_idiomas:
            self.btn_lang.set_label(mapa_idiomas[codigo])

        # Guardar la selección de idioma inmediatamente
        guardar_config_idioma(self.idioma_actual)
    
    def on_config_preguntar_toggled(self, widget):
        self.preguntar_descargar_al_cerrar = widget.get_active()
        guardar_config_preguntar(self.preguntar_descargar_al_cerrar)

    def on_citas_toggled(self, widget):
        self.citas_activas = widget.get_active()
        self.vbox_autores.set_visible(self.citas_activas)

    def on_autor_changed(self, widget, autor_id):
        if widget.get_active():
            self.autor_seleccionado = autor_id
            if autor_id == "siva":
                tag_data = IMAGE_STYLES.get("Borobudur Temple", {})
                query_tag = tag_data.get("query")
                if query_tag and query_tag in self.chk_estilos:
                    self.chk_estilos[query_tag].set_active(True)


    def obtener_imagenes_pixabay(self, query_tag, cantidad=25):
        items = []
        try:
            params = {
                "key": PIXABAY_API_KEY,
                "q": urllib.parse.quote(query_tag),
                "image_type": "photo",
                "safesearch": "true",
                "per_page": 40
            }
            query_str = urllib.parse.urlencode(params)
            api_url = f"https://pixabay.com/api/?{query_str}"
            req = urllib.request.Request(api_url, headers=HTTP_HEADERS)
            
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    hits = data.get("hits", [])
                    # Filtrar estrictamente no verticales (ancho >= alto)
                    #hits = [h for h in hits if h.get("imageWidth", 0) >= h.get("imageHeight", 0)]
                    random.shuffle(hits)
                    
                    for hit in hits[:cantidad]:
                        img_id = f"pixabay_{hit['id']}"
                        thumb_url = hit.get("previewURL")
                        full_url = hit.get("largeImageURL") or hit.get("webformatURL")
                        
                        thumb_path = TEMP_DIR / f"thumb_{img_id}.jpg"
                        if not thumb_path.exists() and thumb_url:
                            descargar_archivo(thumb_url, thumb_path)
                            
                        items.append({
                            "id": img_id,
                            "thumb_path": str(thumb_path),
                            "full_url": full_url,
                            "source_url": hit.get("pageURL", full_url)
                        })
        except Exception as e:
            print(f"Error consultando Pixabay para '{query_tag}': {e}")
        return items

    def obtener_imagenes_pexels(self, query_tag, cantidad=25):
        items = []
        try:
            params = {"query": query_tag, "per_page": 30}
            query_str = urllib.parse.urlencode(params)
            api_url = f"https://api.pexels.com/v1/search?{query_str}"
            
            headers_pexels = {
                **HTTP_HEADERS,
                "Authorization": PEXELS_API_KEY
            }
            req = urllib.request.Request(api_url, headers=headers_pexels)
            
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    photos = data.get("photos", [])
                    # Filtrar estrictamente no verticales (ancho >= alto)
                    photos = [p for p in photos if p.get("width", 0) >= p.get("height", 0)]
                    random.shuffle(photos)
                    
                    for photo in photos[:cantidad]:
                        img_id = f"pexels_{photo['id']}"
                        src = photo.get("src", {})
                        thumb_url = src.get("medium") or src.get("small")
                        full_url = src.get("large2x") or src.get("original")
                        
                        thumb_path = TEMP_DIR / f"thumb_{img_id}.jpg"
                        if not thumb_path.exists() and thumb_url:
                            descargar_archivo(thumb_url, thumb_path)
                            
                        items.append({
                            "id": img_id,
                            "thumb_path": str(thumb_path),
                            "full_url": full_url,
                            "source_url": photo.get("url", full_url)
                        })
        except Exception as e:
            print(f"Error consultando Pexels para '{query_tag}': {e}")
        return items

        # Tomamos los tags activos en orden (sin random)
        tags_activos = [tag for tag, chk in self.chk_estilos.items() if chk.get_active()]
        if not tags_activos:
            tags_activos = ["nature"]

        def worker():
            items = []
            vistos = set()

            # Recorremos los tags activos ordenadamente hasta completar 25
            for query_tag in tags_activos:

                if self.cancel_download_event.is_set():
                    print("Descarga cancelada por el usuario (Switch en OFF)")
                    break

                if len(items) >= 25:
                    break
                
                # 1. Wallhaven (filtrando horizontales/cuadrados)
                try:
                    params = {"q": query_tag, "sorting": "date_added", "purity": "100", "apikey": WALLHAVEN_API_KEY}
                    api_url = f"https://wallhaven.cc/api/v1/search?{urllib.parse.urlencode(params)}"
                    req = urllib.request.Request(api_url, headers=HTTP_HEADERS)
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        if resp.status == 200:
                            data = json.loads(resp.read().decode("utf-8"))
                            for item in data.get("data", []):
                                if len(items) >= 25:
                                    break
                                if item["id"] not in vistos:
                                    if item.get("width", 0) >= item.get("height", 0):
                                        vistos.add(item["id"])
                                        thumb_path = TEMP_DIR / f"thumb_{item['id']}.jpg"
                                        if not thumb_path.exists():
                                            descargar_archivo(item["thumbs"]["small"], thumb_path)
                                        items.append({
                                            "id": item["id"],
                                            "thumb_path": str(thumb_path),
                                            "full_url": item["path"],
                                            "source_url": item.get("url", item["path"])
                                        })
                except Exception as e:
                    print(f"Aviso Wallhaven ({query_tag}): {e}")

                # 2. Rellenar con Pixabay / Pexels si aún faltan para llegar a 25
                if len(items) < 25:
                    pixabay_items = self.obtener_imagenes_pixabay(query_tag, cantidad=25 - len(items))
                    for p_item in pixabay_items:
                        if p_item["id"] not in vistos and len(items) < 25:
                            vistos.add(p_item["id"])
                            items.append(p_item)

            # 3. Respaldo estricto con Picsum si faltan elementos para completar los 25 exactos
            if len(items) < 25:
                faltantes = 25 - len(items)
                items.extend(self.obtener_imagenes_respaldo_picsum(cantidad=faltantes))

            # Limitamos estrictamente a los primeros 25 elementos recopilados
            items = items[:25]
            GLib.idle_add(self.actualizar_grid_miniaturas, items)

        threading.Thread(target=worker, daemon=True).start()

    def obtener_imagenes_respaldo_picsum(self, cantidad=15):
        """
        Generador de respaldo usando Picsum Photos cuando Wallhaven está caído (Error 521/Servidor caído).
        Devuelve una estructura equivalente a la de Wallhaven para mantener la compatibilidad del programa.
        """
        items = []
        for _ in range(cantidad):
            img_id = random.randint(1000, 999999)
            # Para miniaturas (thumb) y versión HD (full_url)
            width_thumb, height_thumb = 300, 200
            width_full, height_full = 1920, 1080
            
            thumb_url = f"https://picsum.photos/seed/{img_id}/{width_thumb}/{height_thumb}"
            full_url = f"https://picsum.photos/seed/{img_id}/{width_full}/{height_full}"
            
            thumb_path = TEMP_DIR / f"thumb_picsum_{img_id}.jpg"
            try:
                if not thumb_path.exists():
                    descargar_archivo(thumb_url, thumb_path)
                items.append({
                    "id": f"picsum_{img_id}",
                    "thumb_path": str(thumb_path),
                    "full_url": full_url,
                    "source_url": full_url
                })
            except Exception as e:
                print(f"Error al descargar miniatura de respaldo: {e}")
        return items

    def cargar_imagenes_async(self):
        # 1. VERIFICACIÓN INICIAL: Si está en OFF, carga locales de inmediato y no abre hilos
        if hasattr(self, 'switch_online') and not self.switch_online.get_active():
            self.lbl_status.set_text("Cargando imágenes locales...")
            items_locales = self.cargar_imagenes_locales(cantidad=25)
            self.imagenes_cache = items_locales
            self.actualizar_flowbox_con_items(items_locales)
            self.lbl_status.set_text(f"Cargadas {len(items_locales)} imágenes locales.")
            return

        # 2. MODO ONLINE (Si el switch está activado)
        self.cancel_download_event.clear()
        self.lbl_status.set_text("Obteniendo aleatoriamente 25 fondos de varios tags y sitios...")
        for child in self.flowbox.get_children():
            self.flowbox.remove(child)

        # Tomamos los tags activos
        tags_activos = [tag for tag, chk in self.chk_estilos.items() if chk.get_active()]
        if not tags_activos:
            tags_activos = ["nature"]

        def worker():
            items = []
            vistos = set()
            sitios = ["wallhaven", "pixabay"]

            # Bucle para recolectar de forma aleatoria hasta llegar a 25
            intentos = 0
            while len(items) < 25 and intentos < 60:
                # 3. VERIFICACIÓN DE CANCELACIÓN EN CADA ITERACIÓN
                if self.cancel_download_event.is_set():
#                    print("Descarga cancelada por el usuario (Switch pasó a OFF).")
                    break

                intentos += 1
                tag_actual = random.choice(tags_activos)
                sitio_actual = random.choice(sitios)

                if sitio_actual == "wallhaven":
                    try:
                        # Usamos orden aleatorio en la API de Wallhaven si lo soporta, o barajamos el resultado
                        params = {"q": tag_actual, "sorting": "random", "purity": "100", "apikey": WALLHAVEN_API_KEY}
                        api_url = f"https://wallhaven.cc/api/v1/search?{urllib.parse.urlencode(params)}"
                        req = urllib.request.Request(api_url, headers=HTTP_HEADERS)
                        with urllib.request.urlopen(req, timeout=8) as resp:
                            if resp.status == 200:
                                data = json.loads(resp.read().decode("utf-8"))
                                pool_wh = data.get("data", [])
                                random.shuffle(pool_wh)
                                for item in pool_wh:
                                    if len(items) >= 25:
                                        break
                                    if item["id"] not in vistos:
                                        if item.get("width", 0) >= item.get("height", 0):
                                            vistos.add(item["id"])
                                            thumb_path = TEMP_DIR / f"thumb_{item['id']}.jpg"
                                            if not thumb_path.exists():
                                                descargar_archivo(item["thumbs"]["small"], thumb_path)
                                            items.append({
                                                "id": item["id"],
                                                "thumb_path": str(thumb_path),
                                                "full_url": item["path"],
                                                "source_url": item.get("url", item["path"])
                                            })
                    except Exception as e:
                        print(f"Aviso Wallhaven ({tag_actual}): {e}")

                elif sitio_actual == "pixabay":
                    try:
                        pixabay_items = self.obtener_imagenes_pixabay(tag_actual, cantidad=15)
                        random.shuffle(pixabay_items)
                        for p_item in pixabay_items:
                            if len(items) >= 25:
                                break
                            if p_item["id"] not in vistos:
                                vistos.add(p_item["id"])
                                items.append(p_item)
                    except Exception as e:
                        print(f"Aviso Pixabay ({tag_actual}): {e}")

            # Respaldo con Picsum de manera aleatoria si aún faltan elementos para los 25 exactos
            if len(items) < 25:
                faltantes = 25 - len(items)
                items.extend(self.obtener_imagenes_respaldo_picsum(cantidad=faltantes))

            # Mezcla final de todo el conjunto y corte estricto a 25
            random.shuffle(items)
            items = items[:25]
            GLib.idle_add(self.actualizar_grid_miniaturas, items)

        threading.Thread(target=worker, daemon=True).start()

    
    def actualizar_grid_miniaturas(self, items):
            self.imagenes_cache = items
            self.lbl_status.set_text(f"{len(items)} miniaturas listas.")
    
            for item in items:
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(item["thumb_path"], 170, 110, True)
                    img = Gtk.Image.new_from_pixbuf(pixbuf)
                    box = Gtk.EventBox()
                    box.add(img)
                    box.item_data = item
                    self.flowbox.add(box)
                except Exception as e:
                    print(f"Error cargando miniatura {item['thumb_path']}: {e}")
                    # Si el archivo está corrupto, lo elimina para que la próxima lo descargue bien
                    try:
                        if os.path.exists(item["thumb_path"]):
                            os.remove(item["thumb_path"])
                    except Exception:
                        pass
                    continue
    
            self.flowbox.show_all()

    def on_imagen_doble_click(self, flowbox, child):
        item_data = getattr(child.get_child(), "item_data", None)
        if not item_data:
            return
    
        def tarea_abrir_preview():
            autor_otro_override = ""
            
            if self.citas_activas and self.autor_seleccionado == "otros":
                rutas_dialog = [
                    IMAGENES_QUOTES_DIR / "author_dialog.py",
                ]
                script_author_dialog = next((r for r in rutas_dialog if r.exists()), None)

                if script_author_dialog:
                    try:
                        res = subprocess.run(
                            [sys.executable, str(script_author_dialog)],
                            capture_output=True,
                            text=True,
                            timeout=15
                        )
                        
                        # CASO 1: El usuario CERRÓ o CANCELÓ la ventana (código de salida distinto de 0)
                        if res.returncode != 0:
                            print("Diálogo de autor cerrado o cancelado por el usuario. Abortando búsqueda.")
                            return

                        # CASO 2: Confirmó (returncode == 0), procesamos la salida
                        lineas = [l.strip() for l in res.stdout.splitlines() if l.strip()]

                        palabras_ignorar = [
                            "cargando", "autores disponibles", "listo", 
                            "iniciando", "base completa", "memoria"
                        ]

                        validas = [
                            l for l in lineas 
                            if not l.startswith("¡") and not any(p in l.lower() for p in palabras_ignorar)
                        ]

                        if validas:
                            # Se ingresó/seleccionó un autor específico
                            autor_otro_override = validas[-1]
                        else:
                            # Confirmó pero dejó el campo VACÍO: elegimos uno aleatorio
                            autor_otro_override = random.choice(LISTA_OTROS_AUTORES)
                            print(f"Campo vacío confirmado. Autor aleatorio seleccionado: {autor_otro_override}")

                    except Exception as e:
                        print(f"Error en dialogo autor: {e}")
                        return

                # Resguardo por si el script no existía
                if not autor_otro_override:
                    autor_otro_override = random.choice(LISTA_OTROS_AUTORES)

            # Si todo está bien, pasamos a abrir la vista previa
            GLib.idle_add(self._abrir_dialogo_preview, item_data, autor_otro_override)
    
        # Lanzamos en hilo secundario para evitar congelar GTK
        threading.Thread(target=tarea_abrir_preview, daemon=True).start()
    
    def _abrir_dialogo_preview(self, item_data, autor_otro_override):
        dialog = PreviewDialog(self, item_data, autor_otro_override=autor_otro_override)
        dialog.run()
        dialog.destroy()
        return False


    def on_close_window(self, widget, event):
        # 1. Guardar la configuración de tags activos/desactivados antes de cerrar
        for query_val, chk in self.chk_estilos.items():
            activo_actual = chk.get_active()
            for clave, datos in IMAGE_STYLES.items():
                if datos.get("query") == query_val:
                    datos["activo"] = activo_actual
                    break
        guardar_tags_activos(IMAGE_STYLES)

        # 2. Si el usuario desactivó el aviso de descarga, cerramos la app al instante
        if not self.preguntar_descargar_al_cerrar:
            Gtk.main_quit()
            return False

        dialog = Gtk.MessageDialog(
            transient_for=self, flags=0, message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO, text="Al cerrar, ¿guardamos las imágenes de la sesión?"
        )
        dialog.format_secondary_text(
            f"• Descargando imágenes limpias de las miniaturas en: {AUTO_DIR}\n"
            f"• Guardado de imágenes seleccionadas en: {SAVE_DIR}"
        )
        resp = dialog.run()
        dialog.destroy()

        if resp == Gtk.ResponseType.YES:
            progress_dialog = Gtk.MessageDialog(
                transient_for=self, flags=0, message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.NONE, text="Guardando y descargando imágenes..."
            )
            progress_dialog.format_secondary_text("Por favor espera un momento mientras finaliza la descarga.")
            progress_dialog.show_all()

            def process_saving():
                for src_clean_path in list(self.imagenes_limpias_abiertas):
                    if os.path.exists(src_clean_path):
                        dest_clean_path = AUTO_DIR / f"limpia_{Path(src_clean_path).name}"
                        shutil.copy(src_clean_path, dest_clean_path)

                for item in self.imagenes_cache:
                    hd_path = TEMP_DIR / f"full_{item['id']}.jpg"
                    if not hd_path.exists():
                        try:
                            descargar_archivo(item["full_url"], hd_path)
                        except Exception as e:
                            print(f"Error al descargar {item['id']}: {e}")
                    if hd_path.exists():
                        dest_path = AUTO_DIR / f"miniatura_{item['id']}.jpg"
                        shutil.copy(hd_path, dest_path)

                def finish():
                    progress_dialog.destroy()
                    Gtk.main_quit()

                GLib.idle_add(finish)

            threading.Thread(target=process_saving, daemon=True).start()
            return True

        # Si el usuario responde que NO al diálogo de guardado, liberamos la terminal también
        Gtk.main_quit()
        return False

    def aplicar_estilos_css(self):
        css = b"""
        window { background-color: #0f172a; color: #f8fafc; }
        checkbutton, radiobutton, label { color: #f8fafc; font-size: 13px; }
        button { background-color: #1e293b; color: #ffffff; border: 1px solid #475569; border-radius: 6px; padding: 4px 8px; }
        button:hover { background-color: #334155; }
        combobox, entry { background-color: #1e293b; color: #ffffff; border: 1px solid #475569; }
        expander label { font-size: 13px; font-weight: bold; color: #3b82f6; }
        .arrow-btn { font-size: 16px; font-weight: bold; padding: 2px 10px; }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

if __name__ == "__main__":
    try:
        # Instancias tu ventana principal aquí, por ejemplo:
        app = WallpaperManagerWindow() 
        app.show_all()  # <--- ¡Crucial para que los elementos salgan a la vista!
        
        Gtk.main()
    except KeyboardInterrupt:
        print("\nAplicación cerrada por el usuario (Ctrl+C).")
        try:
            Gtk.main_quit()
        except Exception:
            pass
