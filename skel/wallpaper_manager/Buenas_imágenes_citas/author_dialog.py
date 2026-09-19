#!/usr/bin/env python3
import sys
import json
import urllib.request
from pathlib import Path

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

# Directorio global de recursos instalados en el sistema (Solo lectura)
SHARE_DIR = Path("/usr/share/wallpaper_manager")
IMAGENES_QUOTES_DIR = SHARE_DIR / "Buenas_imágenes_citas"

# Archivos de autores provistos por la aplicación
AUTORES_JSON_PATH = IMAGENES_QUOTES_DIR / "autores.json"
AUTORES_COMPLETOS_DB_PATH = IMAGENES_QUOTES_DIR / "autores_completos_db.json"

# URL de respaldo o enlace directo desde donde descargar el archivo de 8 MB si no existe
URL_AUTORES_DB = "https://raw.githubusercontent.com/baitsart/autores_completos_db.json/refs/heads/main/autores_completos_db.json"


DEFAULT_AUTORES = [
    "Albert Einstein",
    "Nikola Tesla",
    "Mark Twain",
    "Benjamin Franklin",
    "Oscar Wilde",
    "Mahatma Gandhi",
    "Friedrich Nietzsche",
    "Marilyn Monroe",
    "George Bernard Shaw",
    "William Shakespeare",
    "Bob Marley",
    "Abraham Lincoln",
    "Bruce Lee",
    "Aristotle",
    "Plato",
    "Confucius",
    "Rumi",
    "Carl Sagan",
    "Stephen Hawking",
    "Steve Jobs",
    "Elon Musk",
]


def progress_hook(block_num, block_size, total_size):
    """Muestra una barra de progreso dinámica en la terminal con porcentaje y MB."""
    downloaded = block_num * block_size
    if total_size > 0:
        percent = min(int(downloaded * 100 / total_size), 100)
        mb_downloaded = downloaded / (1024 * 1024)
        mb_total = total_size / (1024 * 1024)
        # \r permite sobreescribir la misma línea en la terminal
        print(f"\r📥 Descargando base de datos: {percent}% [{mb_downloaded:.1f} MB / {mb_total:.1f} MB]", end="", flush=True)
    else:
        mb_downloaded = downloaded / (1024 * 1024)
        print(f"\r📥 Descargando base de datos: {mb_downloaded:.1f} MB descargados", end="", flush=True)


def verificar_y_descargar_db_completa():
    """Verifica si existe el archivo de 8 MB; si no, lo descarga mostrando el progreso."""
    if not AUTORES_COMPLETOS_DB_PATH.exists():
        print(f"Aviso: no existe la base completa en {AUTORES_COMPLETOS_DB_PATH}")
        print("Iniciando descarga de la base de datos de autores...")
        
        try:
            AUTORES_COMPLETOS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            
            # Usamos urlretrieve con nuestro gancho de progreso personalizado
            urllib.request.urlretrieve(URL_AUTORES_DB, AUTORES_COMPLETOS_DB_PATH, reporthook=progress_hook)
            
            print("\n¡Base de datos descargada e instalada con éxito! ✨")
            
        except Exception as e:
            print(f"\n[ERROR CRÍTICO] No se pudo descargar la base completa: {e}")
            print(f"Verifica que la URL sea correcta y accesible: {URL_AUTORES_DB}")


def cargar_autores_json():
    """Carga solamente los autores principales de autores.json."""

    if AUTORES_JSON_PATH.exists():
        try:
            with open(AUTORES_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list) and data:
                return [
                    str(autor).strip()
                    for autor in data
                    if str(autor).strip()
                ]

        except Exception as e:
            print(f"Error leyendo autores.json: {e}")

    # Si no existe o hay error, creamos el archivo por defecto
    try:
        AUTORES_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)

        with open(AUTORES_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(
                DEFAULT_AUTORES,
                f,
                ensure_ascii=False,
                indent=4
            )

    except Exception as e:
        print(f"Error creando autores.json: {e}")

    return DEFAULT_AUTORES


def extraer_nombres_autores(data):
    """
    Extrae nombres de autores de distintas estructuras JSON.
    """
    nombres = []

    def agregar(valor):
        if isinstance(valor, str):
            nombre = valor.strip()
            if nombre:
                nombres.append(nombre)
        elif isinstance(valor, dict):
            for campo in ("author", "author_name", "name", "nombre"):
                valor_campo = valor.get(campo)
                if isinstance(valor_campo, str):
                    nombre = valor_campo.strip()
                    if nombre:
                        nombres.append(nombre)
                        return
            for subvalor in valor.values():
                agregar(subvalor)
        elif isinstance(valor, list):
            for elemento in valor:
                agregar(elemento)

    agregar(data)

    resultado = []
    vistos = set()

    for nombre in nombres:
        clave = nombre.casefold()
        if clave not in vistos:
            vistos.add(clave)
            resultado.append(nombre)

    return resultado


def cargar_autores_completos():
    """
    Carga la base completa de autores para el buscador.
    """
    verificar_y_descargar_db_completa()

    if not AUTORES_COMPLETOS_DB_PATH.exists():
        return []

    try:
        print("Cargando base completa de autores en memoria...")

        with open(
            AUTORES_COMPLETOS_DB_PATH,
            "r",
            encoding="utf-8"
        ) as f:
            data = json.load(f)

        autores = extraer_nombres_autores(data)
        print(f"¡Listo! Autores disponibles para búsqueda: {len(autores)}")

        return autores

    except Exception as e:
        print(f"Error leyendo autores_completos_db.json: {e}")
        return []


# ------------------------------------------------------------
# Cargar ambas fuentes
# ------------------------------------------------------------

LISTA_AUTORES_PRINCIPALES = cargar_autores_json()
LISTA_AUTORES_COMPLETOS = cargar_autores_completos()


class AuthorSelectionWindow(Gtk.Window):

    def __init__(self):
        super().__init__(
            title="Seleccionar Autor (AZ Quotes)"
        )

        self.set_default_size(480, 520)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.autor_seleccionado = ""

        self.aplicar_estilos_css()

        main_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10
        )

        main_box.set_margin_top(12)
        main_box.set_margin_bottom(12)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)

        self.add(main_box)

        lbl_info = Gtk.Label(
            label=(
                "<b>Elige un autor por defecto o "
                "escribe en el buscador:</b>"
            )
        )

        lbl_info.set_use_markup(True)
        main_box.pack_start(
            lbl_info,
            False,
            False,
            0
        )

        store = Gtk.ListStore(str)

        for autor in LISTA_AUTORES_COMPLETOS:
            store.append([autor])

        completion = Gtk.EntryCompletion()
        completion.set_model(store)
        completion.set_text_column(0)
        
        completion.set_inline_completion(False)
        completion.set_popup_completion(True)
        completion.set_minimum_key_length(1)
        
        def buscar_coincidencia(completion, key_string, iter_, data=None):
            autor = store.get_value(iter_, 0)
            texto = key_string.strip().casefold()
            if not texto:
                return False
            return autor.casefold().startswith(texto)
        
        completion.set_match_func(
            buscar_coincidencia,
            None
        )

        self.txt_search = Gtk.Entry()

        self.txt_search.set_placeholder_text(
            "Escribe cualquier autor (ej: Nikola Tesla)..."
        )

        self.txt_search.set_completion(completion)

        self.txt_search.connect(
            "activate",
            lambda w: self.confirmar(
                self.txt_search.get_text().strip()
            )
        )

        main_box.pack_start(
            self.txt_search,
            False,
            False,
            0
        )

        scrolled = Gtk.ScrolledWindow()

        scrolled.set_policy(
            Gtk.PolicyType.NEVER,
            Gtk.PolicyType.AUTOMATIC
        )

        flow = Gtk.FlowBox()

        flow.set_max_children_per_line(2)
        flow.set_selection_mode(Gtk.SelectionMode.SINGLE)

        for autor in LISTA_AUTORES_PRINCIPALES:

            btn = Gtk.Button(label=autor)

            btn.connect(
                "clicked",
                self.on_autor_btn_clicked,
                autor
            )

            flow.add(btn)

        scrolled.add(flow)

        main_box.pack_start(
            scrolled,
            True,
            True,
            0
        )

        btn_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10
        )

        btn_random = Gtk.Button(
            label="🎲 Aleatorio"
        )

        btn_random.connect(
            "clicked",
            lambda w: self.confirmar("")
        )

        btn_accept = Gtk.Button(
            label="✔ Confirmar Búsqueda"
        )

        btn_accept.connect(
            "clicked",
            lambda w: self.confirmar(
                self.txt_search.get_text().strip()
            )
        )

        btn_box.pack_start(
            btn_random,
            True,
            True,
            0
        )

        btn_box.pack_start(
            btn_accept,
            True,
            True,
            0
        )

        main_box.pack_start(
            btn_box,
            False,
            False,
            0
        )

    def on_autor_btn_clicked(self, widget, autor):
        self.confirmar(autor)

    def confirmar(self, autor_nombre):
        print(autor_nombre)
        Gtk.main_quit()

    def aplicar_estilos_css(self):

        css = b"""
        window {
            background-color: #0f172a;
            color: #f8fafc;
        }

        label {
            color: #f8fafc;
            font-size: 13px;
        }

        button {
            background-color: #1e293b;
            color: #ffffff;
            border: 1px solid #475569;
            border-radius: 6px;
            padding: 6px 10px;
        }

        button:hover {
            background-color: #334155;
        }

        entry {
            background-color: #1e293b;
            color: #ffffff;
            border: 1px solid #475569;
            border-radius: 6px;
            padding: 6px;
        }
        """

        provider = Gtk.CssProvider()

        provider.load_from_data(css)

        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )


if __name__ == "__main__":

    win = AuthorSelectionWindow()

    win.connect(
        "destroy",
        Gtk.main_quit
    )

    win.show_all()

    Gtk.main()
