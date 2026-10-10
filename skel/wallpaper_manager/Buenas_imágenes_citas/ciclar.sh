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
FOLDER=$(grep -i "directorio =" "$CONFIG_FILE" | cut -d '=' -f2 | tr -d '"' | tr -d "'" | xargs)
AUTOR=$(grep -i "autor =" "$CONFIG_FILE" | cut -d '=' -f2 | tr -d '"' | tr -d "'" | xargs)
LANG=$(grep -i "Lang =" "$CONFIG_FILE" | cut -d '=' -f2 | tr -d ' "')

IMG_FOLDER=$(xdg-user-dir PICTURES 2>/dev/null)
[ -z "$IMG_FOLDER" ] && IMG_FOLDER="$HOME/Imágenes"

# Si en la config la ruta está vacía o apunta a /usr/share por error, la redirigimos a la carpeta del usuario
if [ -z "$FOLDER" ] || [ "${FOLDER#*"/usr/share"}" != "$FOLDER" ]; then
    FOLDER="$IMG_FOLDER/wallpaper manager_citas"
fi

# Valores por defecto si están vacíos
[ -z "$TIEMPO" ] && TIEMPO=5
[ -z "$LANG" ] && LANG="es"
[ -z "$AUTOR" ] && AUTOR="Prem Rawat"
[ -z "$FOLDER" ] && FOLDER="$IMG_FOLDER/wallpaper manager_citas"

if gsettings get org.gnome.desktop.interface color-scheme | grep -q 'prefer-dark'; then 
    mode="-dark"
else
    mode=""
fi

file=$(find "$FOLDER" -regex ".*\(.jpg\|.JPG\|.jpeg\|.JPEG\|.gif\|.GIF\|.png\|.PNG\|.svg\|.SVG\|.bmp\|.BMP\)" | shuf -n 1)

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
        TEXTO=$(python3 /usr/share/wallpaper_manager/Buenas_imágenes_citas/others_authors.py "$AUTOR")
        ;;
esac

# SOPORTE PARA OTROS IDIOMAS (solo si no es Prem Rawat ni Sadhguru, que ya manejan sus idiomas oficiales)
if [[ "$AUTOR_LOWER" != *prem*rawat* ]] && [[ "$AUTOR_LOWER" != *sadhguru* ]]; then
    if [ "$LANG" != "es" ] && [ "$LANG" != "en" ] && [ -f /usr/share/wallpaper_manager/Buenas_imágenes_citas/auto-translate.py ]; then
        TEXTO=$(python3 /usr/share/wallpaper_manager/Buenas_imágenes_citas/auto-translate.py "$TEXTO" "$LANG")
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
fi

# 4. Esperar el tiempo configurado y reiniciar el ciclo
sleep "${TIEMPO}m" && bash /usr/share/wallpaper_manager/Buenas_imágenes_citas/ciclar.sh
