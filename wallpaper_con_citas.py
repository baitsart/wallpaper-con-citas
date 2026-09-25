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
gi.require_version('Gtk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib
from PIL import Image, ImageDraw, ImageFont, ExifTags

# ----------------------------------------------------------------------
# CONFIGURACIÓN Y RUTAS DE ALMACENAMIENTO UNIVERSALES ($HOME)
# ----------------------------------------------------------------------

HOME_DIR = Path.home()

# 1. Directorios base (Recursos globales instalados en el sistema - Solo lectura)
SHARE_DIR = Path("/usr/share/wallpaper_manager")
BASE_DIR = SHARE_DIR
IMAGENES_QUOTES_DIR = SHARE_DIR / "Buenas_imágenes_citas"
QUOTES_DIR = IMAGENES_QUOTES_DIR / "Quotes"

# 2. Caché y Configuración (Escritura en el Home del usuario)
TEMP_DIR = Path(tempfile.gettempdir()) / "wallpaper_manager_cache"

# Ruta fija del archivo de tags en /usr/share/
CONFIG_FILE = SHARE_DIR / "auto-download.config"
CONFIG_TAGS_PATH = SHARE_DIR / "tags_activos.config"
CONFIG_LANG_FILE = SHARE_DIR / "language.config"

# 3. Creación de carpetas si no existen
IMAGENES_QUOTES_DIR.mkdir(parents=True, exist_ok=True)
QUOTES_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)


def cargar_config_idioma():
    if CONFIG_LANG_FILE.exists():
        try:
            val = CONFIG_LANG_FILE.read_text().strip().lower()
            if val in ["en", "es"]:
                return val
        except Exception:
            pass
    return "es"

def guardar_config_idioma(lang):
    try:
        CONFIG_LANG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_LANG_FILE.write_text(lang, encoding="utf-8")
    except Exception as e:
        print(f"Error guardando idioma: {e}")

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
    base_dir = "/usr/share/fonts"
    if os.path.isdir(base_dir):
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
        print(f"Error ejecutando {script_path.name}: {e}")
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

def traducir_nativo(texto, lang="es"):
    """Traduce usando el script externo del sistema y tiene MyMemory como respaldo."""
    if not texto or len(texto.strip()) < 3:
        return texto

    # 1. Intentar primero con el script externo del sistema
    if lang == "es":
        script_translate = Path("/usr/share/wallpaper_manager/Buenas_imágenes_citas/auto-translate.py")
        if script_translate.exists():
            try:
                res = subprocess.run(
                    [sys.executable, str(script_translate), texto],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if res.returncode == 0 and res.stdout.strip():
                    salida_script = res.stdout.strip()
                    
                    # --- FILTRADO DE DEPURACIÓN AQUÍ ---
                    # Si el script imprime "Español: ...", extraemos solo esa parte
                    for linea in salida_script.splitlines():
                        if "Español:" in linea:
                            return linea.split("Español:", 1)[1].strip()
                    
                    # Si no contiene esos encabezados, usamos la última línea que no sea un aviso
                    lineas_limpias = [
                        l.strip() for l in salida_script.splitlines() 
                        if l.strip() and not l.startswith("Traduciendo") and not l.startswith("Original:")
                    ]
                    if lineas_limpias:
                        return lineas_limpias[-1]

            except Exception as e:
                print(f"Error ejecutando auto-translate.py: {e}")

    # 2. Respaldo nativo con la API de MyMemory (si el script no existe o falló)
    try:
        url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(texto)}&langpair=en|{lang}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            if data.get('responseStatus') == 200:
                traduccion = data.get('responseData', {}).get('translatedText')
                if traduccion and not traduccion.startswith("MYMEMORY WARNING"):
                    return traduccion
    except Exception:
        pass

    return texto

def obtener_cita_otros_autores_script(autor_nombre, lang="es"):
    autor_nombre = autor_nombre.strip() if autor_nombre else ""
    if not autor_nombre:
        return {
            "Cita": "Por favor escribe un autor en el buscador.",
            "Autor": "",
            "Fecha": "",
            "URL": ""
        }

    url_meta = ""
    
    # --- BÚSQUEDA DINÁMICA ESTILO GREP EN EL JSON DE AUTORES ---
    # --- BÚSQUEDA DINÁMICA ESTILO GREP EN EL JSON DE AUTORES ---
    json_db_path = IMAGENES_QUOTES_DIR / "autores_completos_db.json"
    if not json_db_path.exists():
        json_db_path = SHARE_DIR / "Buenas_imágenes_citas" / "autores_completos_db.json"

    if json_db_path.exists():
        try:
            with open(json_db_path, "r", encoding="utf-8") as f:
                db_data = json.load(f)
                
                # Obtenemos los valores internos si es un diccionario o la lista directa
                valores = db_data.values() if isinstance(db_data, dict) else db_data
                
                autor_buscado = autor_nombre.lower()
                for entry in valores:
                    if not isinstance(entry, dict):
                        continue
                    nombre_db = entry.get("nombre", "").lower()
                    exacto_db = entry.get("exacto", "").lower()
                    
                    if autor_buscado in nombre_db or autor_buscado in exacto_db:
                        rel_url = entry.get("url", "")
                        if rel_url:
                            if rel_url.startswith("http"):
                                url_meta = rel_url
                            else:
                                url_meta = f"https://www.azquotes.com{rel_url}"
                            break
        except Exception as e:
            print(f"Error leyendo autores_completos_db.json: {e}")

    # Búsqueda exhaustiva del script en todas las rutas conocidas
    posibles_rutas_script = [
        IMAGENES_QUOTES_DIR / "others_authors.py",
        SHARE_DIR / "Buenas_imágenes_citas" / "others_authors.py",
        BASE_DIR / "others_authors.py"
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

    # 4. Traducir al español
    if lang == "es":
        cita_pura = traducir_nativo(cita_pura, lang="es")

    return {
        "Cita": cita_pura,
        "Autor": autor_nombre,
        "Fecha": "AZ Quotes" if url_meta else "Archivo Local",
        "URL": url_meta
    }

def obtener_cita_datos(autor_id, lang="es", autor_otro=""):
    """Función principal que despacha la obtención de citas según el autor."""
    if autor_id == "sadhguru":
        script_sadhguru = buscar_script("sadhguru_quotes.py")
        if not script_sadhguru:
            return {
                "Cita": "No se encontró sadhguru_quotes.py",
                "Autor": "Sadhguru",
                "Fecha": "",
                "URL": "",
            }
        return ejecutar_y_parsear_script(script_sadhguru, lang)

    elif autor_id == "prem_rawat":
        script_prem = buscar_script("prem_rawat_quotes.py")
        if not script_prem:
            return {
                "Cita": "No se encontró prem_rawat_quotes.py",
                "Autor": "Prem Rawat",
                "Fecha": "",
                "URL": "",
            }
        return ejecutar_y_parsear_script(script_prem, lang)

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
        if lang == "en":
            cita_sel = traducir_texto(cita_sel, target_lang="en", source_lang="auto")
        elif lang == "es":
            cita_sel = traducir_texto(cita_sel, target_lang="es", source_lang="auto")

        return {
            "Cita": cita_sel,
            "Autor": "Dr. Siva P.",
            "Fecha": "PVH",
            "URL": SIVA_METADATA_URLS,
        }

    elif autor_id == "ravi_shankar":
        # Priorizar el archivo correspondiente al idioma seleccionado
        if lang == "en":
            citas = obtener_cita_desde_txt(["Sri Sri Ravi Shankar quotes.txt"], patron_fallback="ravi shankar")
            if not citas:
                citas = obtener_cita_desde_txt(["Citas de Sri Sri Ravi Shankar.txt"], patron_fallback="ravi shankar")
        else:
            citas = obtener_cita_desde_txt(["Citas de Sri Sri Ravi Shankar.txt"], patron_fallback="ravi shankar")
            if not citas:
                citas = obtener_cita_desde_txt(["Sri Sri Ravi Shankar quotes.txt"], patron_fallback="ravi shankar")

        cita_sel = (
            random.choice(citas)
            if citas
            else "La sonrisa es la verdadera riqueza del alma."
        )

        # Traducir según corresponda permitiendo auto-detección del origen
        if lang == "en":
            cita_sel = traducir_texto(cita_sel, target_lang="en", source_lang="auto")
        elif lang == "es":
            cita_sel = traducir_texto(cita_sel, target_lang="es", source_lang="auto")

        return {
            "Cita": cita_sel,
            "Autor": "Sri Sri Ravi Shankar",
            "Fecha": "",
            "URL": "",
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
    # Esto reduce la imagen gigante a un máximo de 1920x1080 de forma proporcional 
    # antes de hacer ningún cálculo de texto o filtros. Alivia la CPU por completo.
    bg_image.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
    # ------------------------------------------

    canvas_w, canvas_h = bg_image.size

    try:
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    overlay = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)

    small = bg_image.resize((1, 1), Image.Resampling.LANCZOS).convert("RGB")
    pixel = small.getpixel((0, 0))
    r, g, b = pixel[0], pixel[1], pixel[2]

    box_w = int(canvas_w * width_ratio)
    max_text_w = box_w - 40
    dummy = Image.new("RGB", (1, 1))
    draw_dummy = ImageDraw.Draw(dummy)

    clean_quote = quote_text.strip("“”).")
    lines_quote = wrap_text(f"“{clean_quote}”", font, max_text_w, draw_dummy)

    author_line = f"— {author_text}" if author_text else ""
    total_lines = len(lines_quote) + (1 if author_line else 0)

    bbox = draw_dummy.textbbox((0, 0), "Ag", font=font)
    line_h = bbox[3] - bbox[1] + 8
    box_h = (total_lines * line_h) + 40

    margin = 20
    hpos = max(margin, min(margin + offset_x, canvas_w - box_w - margin))
    vpos = max(margin, min(margin + offset_y, canvas_h - box_h - margin))

    if draw_background:
        small = bg_image.resize((1, 1), Image.Resampling.LANCZOS).convert("RGB")
        pixel = small.getpixel((0, 0))
        r, g, b = pixel[0], pixel[1], pixel[2]
        draw_overlay.rectangle([hpos, vpos, hpos + box_w, vpos + box_h], fill=(r, g, b, 150))

    result = Image.alpha_composite(bg_image.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(result)

    text_y = vpos + 20

    def calcular_x(line_text, align_type):
        line_box = draw.textbbox((0, 0), line_text, font=font)
        line_w = line_box[2] - line_box[0]
        if align_type == "left":
            return hpos + 20
        elif align_type == "right":
            return hpos + box_w - line_w - 20
        else:
            return hpos + (box_w - line_w) // 2

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

    for line in lines_quote:
        text_x = calcular_x(line, q_align)
        draw.text((text_x + 2, text_y + 2), line, font=font, fill=(0, 0, 0, 180))
        draw.text((text_x, text_y), line, font=font, fill=(255, 255, 255, 255))
        text_y += line_h

    if author_line:
        text_x = calcular_x(author_line, a_align)
        draw.text((text_x + 2, text_y + 2), author_line, font=font, fill=(0, 0, 0, 180))
        draw.text((text_x, text_y), author_line, font=font, fill=(255, 255, 255, 255))

    img_final = result.convert("RGB")
    
    # Preparar el texto completo de metadatos
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
    # Tag Exif 270: ImageDescription (Descripción de la imagen)
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
        self.set_default_size(900, 650)
        self.main_app = parent
        self.item_data = item_data
        self.autor_otro_actual = autor_otro_override or self.main_app.autor_otro_seleccionado

        self.font_path = SYSTEM_FONTS[0] if SYSTEM_FONTS else None
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

        # 1. Fuente
        box_font = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        box_font.pack_start(Gtk.Label(label="Fuente:"), False, False, 0)
        self.combo_fonts = Gtk.ComboBoxText()
        self.combo_fonts.set_size_request(130, 26)
        for font in SYSTEM_FONTS:
            self.combo_fonts.append_text(os.path.basename(font))
        if SYSTEM_FONTS:
            self.combo_fonts.set_active(0)
        self.combo_fonts.connect("changed", self.on_font_changed)
        box_font.pack_start(self.combo_fonts, False, False, 0)
        top_bar.pack_start(box_font, False, False, 0)

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

        btn_dl_raw = Gtk.Button(label="📥 Solo Imagen Libre")
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
        idx = combo.get_active()
        if 0 <= idx < len(SYSTEM_FONTS):
            self.font_path = SYSTEM_FONTS[idx]
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
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT),
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

            cmd_history = "sh /usr/share/wallpaper_manager/w_m/actions/ir-prev.sh"
            subprocess.Popen(cmd_history, shell=True)

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

            self.mostrar_mensaje(
                "¡Fondo Aplicado!",
                f"La imagen fue guardada y establecida como fondo de pantalla:\n{save_path}"
            )
        except Exception as e:
            self.mostrar_mensaje("Error", str(e), Gtk.MessageType.ERROR)

    def on_descargar_solo_imagen(self, widget):
        if not self.hd_image_path.exists():
            return
        nombre = f"wallpaper_{self.item_data.get('id', 'imagen')}.jpg"
        destino = SAVE_DIR / nombre
        try:
            shutil.copy2(self.hd_image_path, destino)
            self.mostrar_mensaje("¡Imagen guardada!", f"Guardada con éxito en:\n{destino}")
        except Exception as e:
            self.mostrar_mensaje("Error", str(e), Gtk.MessageType.ERROR)

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

            self.mostrar_mensaje("¡Imagen Guardada!", f"Guardada con éxito en:\n{save_path}")
        except Exception as e:
            self.mostrar_mensaje("Error", str(e), Gtk.MessageType.ERROR)

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
        texto = (
            f"• Cita: {self.cita_data.get('Cita', 'N/A')}\n"
            f"• Autor: {self.cita_data.get('Autor', 'N/A')}\n"
            f"• Fuente/Fecha: {self.cita_data.get('Fecha', 'N/A')}\n"
            f"• URL Cita: {self.cita_data.get('URL', 'N/A')}\n\n"
            f"• ID Imagen: {self.item_data.get('id', 'N/A')}\n"
            f"• URL Imagen: {self.item_data.get('source_url', 'N/A')}"
        )
        self.mostrar_mensaje("Metadatos de la Imagen y Cita", texto)

class WallpaperManagerWindow(Gtk.Window):
    def __init__(self):
        super().__init__()
        
        header_bar = Gtk.HeaderBar()
        header_bar.set_show_close_button(True)
        header_bar.set_title("Wallpaper Manager — Citas & Wallpapers")
        self.set_titlebar(header_bar)

        self.set_default_size(880, 600)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.citas_activas = True
        self.autor_seleccionado = "prem_rawat"
        self.autor_otro_seleccionado = ""
        self.idioma_actual = cargar_config_idioma()
        self.imagenes_cache = []
        self.imagenes_limpias_abiertas = set()

        self.preguntar_descargar_al_cerrar = cargar_config_preguntar()

        self.connect("delete-event", self.on_close_window)
        self.aplicar_estilos_css()

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_box.set_margin_top(12); main_box.set_margin_bottom(12)
        main_box.set_margin_start(12); main_box.set_margin_end(12)
        self.add(main_box)

        main_box.pack_start(self.crear_panel_superior(), False, False, 0)
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

        btn_refresh = Gtk.Button(label="🔄 Cargar más Imágenes")
        btn_refresh.connect("clicked", lambda w: self.cargar_imagenes_async())
        bottom_bar.pack_end(btn_refresh, False, False, 0)

        main_box.pack_start(bottom_bar, False, False, 0)
        self.cargar_imagenes_async()

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
        
        # Configuración dinámica del botón según el idioma guardado
        self.btn_lang = Gtk.ToggleButton()
        if self.idioma_actual == "en":
            self.btn_lang.set_label("🇬🇧 >")
            self.btn_lang.set_active(True)
        else:
            self.btn_lang.set_label("🇪🇸 >")
            self.btn_lang.set_active(False)

        self.btn_lang.connect("toggled", self.on_idioma_toggled)
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
        

    def on_config_preguntar_toggled(self, widget):
        self.preguntar_descargar_al_cerrar = widget.get_active()
        guardar_config_preguntar(self.preguntar_descargar_al_cerrar)

    def on_idioma_toggled(self, widget):
        if widget.get_active():
            self.idioma_actual = "en"
            widget.set_label("🇬🇧 >")
        else:
            self.idioma_actual = "es"
            widget.set_label("🇪🇸 >")
            
        # Guardar la selección de idioma inmediatamente
        guardar_config_idioma(self.idioma_actual)

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

    def obtener_imagenes_pixabay(self, query_tag, cantidad=5):
        items = []
        try:
            params = {
                "key": PIXABAY_API_KEY,
                "q": urllib.parse.quote(query_tag),
                "image_type": "photo",
                "safesearch": "true",
                "per_page": 20
            }
            query_str = urllib.parse.urlencode(params)
            api_url = f"https://pixabay.com/api/?{query_str}"
            req = urllib.request.Request(api_url, headers=HTTP_HEADERS)
            
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    hits = data.get("hits", [])
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
                    hits = [h for h in hits if h.get("imageWidth", 0) >= h.get("imageHeight", 0)]
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

    def cargar_imagenes_async(self):
        self.lbl_status.set_text("Obteniendo exactamente 25 fondos...")
        for child in self.flowbox.get_children():
            self.flowbox.remove(child)

        # Tomamos los tags activos en orden (sin random)
        tags_activos = [tag for tag, chk in self.chk_estilos.items() if chk.get_active()]
        if not tags_activos:
            tags_activos = ["nature"]

        def worker():
            items = []
            vistos = set()

            # Recorremos los tags activos ordenadamente hasta completar 25
            for query_tag in tags_activos:
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
    
        autor_otro_override = ""
        if self.citas_activas and self.autor_seleccionado == "otros":
            rutas_dialog = [
                IMAGENES_QUOTES_DIR / "author_dialog.py",
                SHARE_DIR / "Buenas_imágenes_citas" / "author_dialog.py",
                BASE_DIR / "author_dialog.py"
            ]
            
            script_author_dialog = next((r for r in rutas_dialog if r.exists()), None)

            if script_author_dialog:
                try:
                    res = subprocess.run(
                        [sys.executable, str(script_author_dialog)],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if res.returncode == 0 and res.stdout.strip():
                        salida_cruda = res.stdout.strip()
                        # Limpiamos y filtramos cualquier texto o depuración que imprima el script,
                        # quedándonos únicamente con la última línea válida que contiene el autor seleccionado.
                        lineas_validas = [
                            l.strip() for l in salida_cruda.splitlines() 
                            if l.strip() and not l.startswith("Traceback") and not l.startswith("File")
                        ]
                        if lineas_validas:
                            autor_otro_override = lineas_validas[-1]
                except Exception as e:
                    print(f"Error ejecutando author_dialog.py: {e}")
    
            # Si el usuario cerró el diálogo sin elegir nada, asignamos un autor por defecto 
            # en lugar de hacer un 'return' abrupto que congela o cancela la vista previa.
            if not autor_otro_override:
                autor_otro_override = "Nikola Tesla"

        dialog = PreviewDialog(self, item_data, autor_otro_override=autor_otro_override)
        dialog.run()
        dialog.destroy()


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
