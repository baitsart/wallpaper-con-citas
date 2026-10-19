#!/bin/bash


# Matar otras instancias previas de ciclar.sh para evitar bucles duplicados
# (Excluimos el proceso actual usando $$)
for pid in $(pgrep -f "ciclar.sh"); do
    if [ "$pid" != "$$" ]; then
        kill -9 "$pid" 2>/dev/null
    fi
done

CONFIG_FILE="/usr/share/wallpaper_manager/Buenas_imágenes_citas/ciclar_render.config"

TIEMPO=$(grep -i "tiempo =" "$CONFIG_FILE" | cut -d '=' -f2 | tr -d ' "')
CITAS=$(grep -i "cita =" "$CONFIG_FILE" | cut -d '=' -f2 | tr -d ' "')
CICLAR_ESTADO=$(grep -i "ciclar =" "$CONFIG_FILE" | cut -d '=' -f2 | tr -d ' "')
FOLDER=$(grep -i "directorio =" "$CONFIG_FILE" | cut -d '=' -f2 | tr -d '"' | tr -d "'" | xargs)
AUTOR=$(grep -i "autor =" "$CONFIG_FILE" | cut -d '=' -f2 | tr -d '"' | tr -d "'" | xargs)
LANG=$(grep -i "Lang =" "$CONFIG_FILE" | cut -d '=' -f2 | tr -d ' "')
ULTIMA_IMG=$(grep -i "ultima_imagen =" "$CONFIG_FILE" | cut -d '=' -f2- | tr -d '"' | tr -d "'" | xargs)
IMAGE_MODE=$(grep -i "image =" "$CONFIG_FILE" | cut -d '=' -f2 | tr -d ' "')
IMAGE_STATE=$(grep -i "image_state =" "$CONFIG_FILE" | cut -d '=' -f2 | tr -d ' "')
IMG_FOLDER=$(xdg-user-dir PICTURES 2>/dev/null)
[ -z "$IMG_FOLDER" ] && IMG_FOLDER="$HOME/Imágenes"

# Si en la config la ruta está vacía o apunta a /usr/share por error, la redirigimos a la carpeta del usuario
if [ -z "$FOLDER" ] || [ "${FOLDER#*"/usr/share"}" != "$FOLDER" ]; then
    FOLDER="$IMG_FOLDER/wallpaper manager_citas"
fi

# Valores por defecto si están vacíos
[ -z "$TIEMPO" ] && TIEMPO=5
[ -z "$LANG" ] && LANG="es"
if [ -z "$AUTOR" ] || [ "$AUTOR" = "0" ]; then
    AUTOR=$(grep "\"nombre\":" "/usr/share/wallpaper_manager/Buenas_imágenes_citas/autores_completos_db.json" | grep -v "Prem Rawat\|Sadhguru\|Sri Sri Ravi Shankar\|Siva P." | shuf -n1 | cut -d'"' -f4)
    [ -z "$AUTOR" ] && AUTOR="Prem Rawat"
fi
[ -z "$FOLDER" ] && FOLDER="$IMG_FOLDER/wallpaper manager_citas"

if gsettings get org.gnome.desktop.interface color-scheme | grep -q 'prefer-dark'; then 
    mode="-dark"
else
    mode=""
fi

# 1. Leer el estado actual de image_state y de image
IMAGE_STATE=$(grep -i "image_state =" "$CONFIG_FILE" | cut -d '=' -f2 | tr -d ' "')
IMAGE_MODE=$(grep -i "image =" "$CONFIG_FILE" | cut -d '=' -f2 | tr -d ' "')

# 2. LÓGICA ONE-SHOT: Si está en false, se ejecuta el cambio único y se actualiza a true
if [ "$IMAGE_STATE" = "false" ]; then
    IMAGE_MODE="true"
    if grep -q "image_state" "$CONFIG_FILE"; then
        sed -i 's/image_state[[:space:]]*=[[:space:]]*false/image_state = true/gi' "$CONFIG_FILE"
    fi
fi

# --- LÓGICA SEGÚN TUS REGLAS DE IMAGEN (Evitando carpetas Generadas) ---
if [ "$IMAGE_MODE" = "true" ]; then
    # Ciclar imágenes al toque (buscando solo originales, excluyendo Generadas)
    file=$(find "$FOLDER" -maxdepth 2 -not -path "*/Generadas*" -regex ".*\(.jpg\|.JPG\|.jpeg\|.JPEG\|.gif\|.GIF\|.png\|.PNG\|.svg\|.SVG\|.bmp\|.BMP\)" | grep -vF "$ULTIMA_IMG" | shuf -n 1)
    [ -z "$file" ] && file=$(find "$FOLDER" -maxdepth 2 -not -path "*/Generadas*" -regex ".*\(.jpg\|.JPG\|.jpeg\|.JPEG\|.gif\|.GIF\|.png\|.PNG\|.svg\|.SVG\|.bmp\|.BMP\)" | shuf -n 1)
else
    # Mantener la imagen fija: SIEMPRE la original limpia
    if [ -f "$ULTIMA_IMG" ] && [[ "$ULTIMA_IMG" != *"Generadas"* ]]; then
        file="$ULTIMA_IMG"
    else
        # Intentamos rescatar la que está puesta actualmente en el escritorio
        current_uri=$(gsettings get org.gnome.desktop.background picture-uri 2>/dev/null | tr -d "'")
        [ -z "$current_uri" ] && current_uri=$(gsettings get org.gnome.desktop.background picture-uri-dark 2>/dev/null | tr -d "'")
        file="${current_uri#file://}"
        
        # Si la actual es generada o no existe, cogemos la primera que halle (sin shuf aleatorio constante)
        if [ ! -f "$file" ] || [[ "$file" == *"Generadas"* ]]; then
            file=$(find "$FOLDER" -maxdepth 2 -not -path "*/Generadas*" -regex ".*\(.jpg\|.JPG\|.jpeg\|.JPEG\|.gif\|.GIF\|.png\|.PNG\|.svg\|.SVG\|.bmp\|.BMP\)" | head -n 1)
        fi
    fi
    
    # ¡CLAVE! Actualizamos ULTIMA_IMG en memoria para que en el siguiente ciclo use EXACTAMENTE esta misma foto base
    ULTIMA_IMG="$file"
fi

if [ ! -f "$file" ]; then
    exit 1
fi

if [ "$CITAS" = "false" ]; then
    gsettings set org.gnome.desktop.background picture-uri"$mode" file:///"$file"
    if [ -f /usr/share/wallpaper_manager/w_m/actions/ir-prev.sh ]; then
        sh /usr/share/wallpaper_manager/w_m/actions/ir-prev.sh
    fi

    sleep "${TIEMPO}m" && bash /usr/share/wallpaper_manager/Buenas_imágenes_citas/ciclar.sh
    exit 0
fi

TEXTO=""

AUTOR_LOWER=$(echo "$AUTOR" | tr '[:upper:]' '[:lower:]')

case "$AUTOR_LOWER" in
    *prem*rawat*)
        # INTENTO 1: Buscar en el idioma oficial seleccionado
        TEXTO=$(python3 /usr/share/wallpaper_manager/Buenas_imágenes_citas/prem_rawat_quotes.py "$LANG")
        
        # INTENTO 2 (Respaldo): Si está vacío, reintentar con 'en'
        if [ -z "$TEXTO" ] && [ "$LANG" != "en" ]; then
            TEXTO=$(python3 /usr/share/wallpaper_manager/Buenas_imágenes_citas/prem_rawat_quotes.py "en")
        fi
        AUTOR="Prem Rawat"
        ;;
    *sadhguru*)
        # INTENTO 1: Buscar en el idioma oficial seleccionado
        TEXTO=$(python3 /usr/share/wallpaper_manager/Buenas_imágenes_citas/sadhguru_quotes.py "$LANG")
        
        # INTENTO 2 (Respaldo): Si está vacío, reintentar con 'en'
        if [ -z "$TEXTO" ] && [ "$LANG" != "en" ]; then
            TEXTO=$(python3 /usr/share/wallpaper_manager/Buenas_imágenes_citas/sadhguru_quotes.py "en")
        fi
        AUTOR="Sadhguru"
        ;;
    *sri*sri*|*ravi*shankar*)
        if [ "$LANG" = "es" ]; then
            TEXTO=$(grep "]" /usr/share/wallpaper_manager/Buenas_imágenes_citas/Quotes/"Citas de Sri Sri Ravi Shankar.txt" | cut -d ']' -f2 | shuf -n 1)
        else
            TEXTO=$(grep "]" /usr/share/wallpaper_manager/Buenas_imágenes_citas/Quotes/"Sri Sri Ravi Shankar quotes.txt" | cut -d ']' -f2 | shuf -n 1)
        fi
        AUTOR="Sri Sri Ravi Shankar"
        ;;
    *siva*)
        if [ "$LANG" = "es" ]; then
            TEXTO=$(grep "“" /usr/share/wallpaper_manager/Buenas_imágenes_citas/Quotes/"Las enseñanzas del Dr Siva.txt" | cut -d '“' -f2 | shuf -n 1)
        else
            TEXTO=$(grep "“" /usr/share/wallpaper_manager/Buenas_imágenes_citas/Quotes/"Dr Siva P s teachings.txt" | cut -d '“' -f2 | shuf -n 1)
        fi
        AUTOR="Dr. Siva P."
        ;;
    *)
        # Obtener la salida de others_authors.py y aplicar el corte por ']' como pediste
        RAW_TEXTO=$(python3 /usr/share/wallpaper_manager/Buenas_imágenes_citas/others_authors.py "$AUTOR")
        
        if echo "$RAW_TEXTO" | grep -q "\]"; then
            TEXTO=$(echo "$RAW_TEXTO" | grep "]" | cut -d ']' -f2- | xargs)
        else
            TEXTO=$(echo "$RAW_TEXTO" | xargs)
        fi
        
        # Traducir si el idioma no es inglés
        if [ "$LANG" != "en" ] && [ -n "$TEXTO" ] && [ -f /usr/share/wallpaper_manager/Buenas_imágenes_citas/auto-translate.py ]; then
            # Solo intenta traducir si hay internet y el script de traducción existe
            if [ -f /usr/share/wallpaper_manager/Buenas_imágenes_citas/auto-translate.py ] && ping -c 1 8.8.8.8 &>/dev/null; then
                TEXTO=$(python3 /usr/share/wallpaper_manager/Buenas_imágenes_citas/auto-translate.py "$TEXTO" "$LANG" | tail -n 1 | sed 's/Destino (es): //')
                fi
        fi
        ;;
esac

# SOPORTE PARA OTROS IDIOMAS (solo si no es Prem Rawat ni Sadhguru, que ya manejan sus idiomas oficiales)
if [[ "$AUTOR_LOWER" != *prem*rawat* ]] && [[ "$AUTOR_LOWER" != *sadhguru* ]]; then
    if [ "$LANG" != "es" ] && [ "$LANG" != "en" ] && [ -f /usr/share/wallpaper_manager/Buenas_imágenes_citas/auto-translate.py ]; then
        if [ -f /usr/share/wallpaper_manager/Buenas_imágenes_citas/auto-translate.py ] && ping -c 1 8.8.8.8 &>/dev/null; then
                TEXTO=$(python3 /usr/share/wallpaper_manager/Buenas_imágenes_citas/auto-translate.py "$TEXTO" "$LANG" | tail -n 1 | sed 's/Destino (es): //')
                fi
    fi
fi

# Guardar los valores generados para que el script de renderizado los lea
echo "Cita: $TEXTO" > /usr/share/wallpaper_manager/Buenas_imágenes_citas/valores_del_render
echo "Autor: $AUTOR" >> /usr/share/wallpaper_manager/Buenas_imágenes_citas/valores_del_render
echo "Imagen: $file" >> /usr/share/wallpaper_manager/Buenas_imágenes_citas/valores_del_render

# 1. Llamar al script de renderizado gráfico por Python
python3 /usr/share/wallpaper_manager/Buenas_imágenes_citas/render_guardado.py

# 2. Definir la ruta exacta de la imagen recién renderizada
NOMBRE_BASE=$(basename "$file")
IMG_FINAL="$IMG_FOLDER/wallpaper manager_citas/Generadas/render_quote_${NOMBRE_BASE}"

# 3. APLICAR COMO FONDO DE PANTALLA EN GNOME
if [ -f "$IMG_FINAL" ]; then
    gsettings set org.gnome.desktop.background picture-uri "file://$IMG_FINAL"
    gsettings set org.gnome.desktop.background picture-uri-dark "file://$IMG_FINAL"
    if [ -f "/usr/share/wallpaper_manager/w_m/actions/ir-prev.sh" ]; then
        sh /usr/share/wallpaper_manager/w_m/actions/ir-prev.sh
    fi
fi

# 4. Esperar el tiempo configurado y reiniciar el ciclo
sleep "${TIEMPO}m" && bash /usr/share/wallpaper_manager/Buenas_imágenes_citas/ciclar.sh
