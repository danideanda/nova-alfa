import local_libs
import local_libs
import os
import re
import time
import threading
import json
import requests
import random
import subprocess
import sys
from datetime import datetime, timedelta

# Intentar importar voz
try:
    from voz import hablar
except ImportError:
    print("❌ Módulo 'voz' no encontrado")
    def hablar(texto):
        print(f"Voz: {texto}")

# Intentar importar groq para uso online
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    print("⚠️ groq no disponible, la conexión online no será utilizada")
    GROQ_AVAILABLE = False

# Intentar importar pygame para música
try:
    import pygame
    if not pygame.mixer.get_init():
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    PYGAME_AVAILABLE = True
except ImportError:
    print("⚠️ Pygame no disponible, funciones de música deshabilitadas")
    pygame = None
    PYGAME_AVAILABLE = False

# Intentar importar yt-dlp para música online
try:
    from yt_dlp import YoutubeDL
    YTDLP_AVAILABLE = True
    print("✅ yt-dlp disponible para música online")
except ImportError:
    print("⚠️ yt-dlp no disponible. Instalar con: pip install yt-dlp")
    YTDLP_AVAILABLE = False

# Intentar importar dateparser
try:
    import dateparser
    DATEPARSER_AVAILABLE = True
except ImportError:
    print("⚠️ dateparser no disponible, algunas funciones de alarma limitadas")
    dateparser = None
    DATEPARSER_AVAILABLE = False

# Intentar importar googletrans para traducción
try:
    from googletrans import Translator
    translator = Translator()
    TRANSLATOR_AVAILABLE = True
except ImportError:
    print("⚠️ googletrans no disponible, funciones de traducción deshabilitadas")
    translator = None
    TRANSLATOR_AVAILABLE = False

# Importar llama_cpp para el modelo de lenguaje
try:
    from llama_cpp import Llama
    LLAMA_AVAILABLE = True
except ImportError:
    print("❌ llama_cpp no está instalado. Ejecuta: pip install llama-cpp-python")
    LLAMA_AVAILABLE = False
    exit(1)

# Intentar importar geocoder para ubicación
try:
    import geocoder
    GEOCODER_AVAILABLE = True
except ImportError:
    print("⚠️ geocoder no disponible, ubicación limitada")
    GEOCODER_AVAILABLE = False

# -----------------------------
# VARIABLES GLOBALES Y CONFIGURACIÓN
# -----------------------------

# Rutas y archivos
MODELO_PATH = "modelos/kamutini.gguf"
JSON_PAD = "sistemprot.json"
NETWORK_STATUS_FILE = "txt/estado_de_red.txt"
PERSONALIZACION_FILE = "txt/personalizacion.txt"
AUDIO_TMP = "tmp/audio_temporal.mp3"
NOTAS_DIR = "notas"
LISTAS_DIR = "listas"
CALENDARIO_FILE = "calendario/eventos.json"

# APIs y claves
api_clima = os.getenv("API_CLIMA")
api_investigar = os.getenv("API_INVESTIGAR")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL_ID = "openai/gpt-oss-120b"

# Variables del modelo
llm = None
SYSTEM_BASE = ""
params = {}

# Almacenar alarmas programadas
alarmas = []
listas_compras = {}
eventos_calendario = []

# Variable para controlar reproducción de música
musica_detener = False

# Crear directorios necesarios
for directorio in ["tmp", "notas", "txt", "listas", "calendario", "sonidos"]:
    if not os.path.exists(directorio):
        os.makedirs(directorio)

# -----------------------------
# FUNCIONES DE PERSONALIZACIÓN (SOLO LECTURA/MODIFICACIÓN)
# -----------------------------

def cargar_personalizacion():
    """
    Carga los datos de personalización.
    Esta función SOLO LEE, no crea el archivo.
    El archivo solo lo crea inicio.py en primera ejecución.
    """
    try:
        if os.path.exists(PERSONALIZACION_FILE):
            with open(PERSONALIZACION_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    except Exception as e:
        print(f"⚠️ Error al cargar personalización: {e}")
        return None

def guardar_personalizacion(datos):
    """Guarda los datos de personalización."""
    try:
        with open(PERSONALIZACION_FILE, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"⚠️ Error al guardar personalización: {e}")
        return False

def actualizar_ubicacion(ciudad, region, pais, lat=None, lon=None):
    """Actualiza SOLO la ubicación en personalización"""
    datos = cargar_personalizacion()
    if datos:
        datos["ubicacion"] = {
            "ciudad": ciudad,
            "region": region,
            "pais": pais,
            "lat": str(lat) if lat else "",
            "lon": str(lon) if lon else ""
        }
        return guardar_personalizacion(datos)
    return False

def obtener_nombre_usuario():
    """Obtiene el nombre del usuario desde personalización"""
    datos = cargar_personalizacion()
    if datos:
        return datos.get("nombre_usuario", "Usuario")
    return "Usuario"

def verificar_estado_red():
    """Verifica si hay conexión a internet leyendo el archivo de estado."""
    try:
        if os.path.exists(NETWORK_STATUS_FILE):
            with open(NETWORK_STATUS_FILE, "r", encoding="utf-8") as f:
                return f.read().strip().lower() == "true"
        return False
    except Exception:
        return False

# -----------------------------
# CARGA DE CONFIGURACIÓN
# -----------------------------
print("🔄 Cargando configuración del sistema...")

if os.path.exists(JSON_PAD):
    with open(JSON_PAD, 'r', encoding='utf-8') as f:
        config = json.load(f)
else:
    # Configuración inicial si no existe el archivo
    config = {
        "system_prompt": "Eres nova, un asistente inteligente de codigo abierto creado por Daniel de Anda basado en el modelo de ai kamutini que tambien fue creado por daniel. Tu función es asistir con tareas diarias, investigación clima musica y abrir apps, respondiendo de forma clara y concisa.",
        "contexto_maestro": {
            "nombre": "Nova",
            "idioma": "Español de México",
            "reglas": ["Responde de forma clara y concisa", "Asistir en tareas diarias, investigación, clima y música"]
        },
        "parametros_modelo": {
            "temperature": 0.2,
            "max_tokens": 212,
            "top_p": 0.9,
            "n_ctx": 10000
        }
    }
    with open(JSON_PAD, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

contexto_json = config.get("contexto_maestro", {})
reglas_str = "\n".join([f"- {r}" for r in contexto_json.get("reglas", [])])

# Construir el SYSTEM_BASE
SYSTEM_BASE = f"""
[IDENTIDAD]
Nombre: {contexto_json.get("nombre", "Nova")}
Idioma: {contexto_json.get("idioma", "Español de México")}

[INSTRUCCIONES]
{reglas_str}
{config.get("system_prompt", "")}
"""

# Parámetros del modelo
params = config.get("parametros_modelo", {})

# -----------------------------
# CARGAR MODELO UNA VEZ AL INICIO
# -----------------------------
if LLAMA_AVAILABLE:
    if not os.path.exists(MODELO_PATH):
        print(f"❌ Modelo no encontrado en: {MODELO_PATH}")
        print(f"   Asegúrate de que el archivo existe en la ruta correcta")
        exit(1)
    
    try:
        print(f"🔄 Cargando modelo desde: {MODELO_PATH}")
        hablar("procesando")
        print("   Esto puede tomar unos segundos...")
        
        # Cargar el modelo UNA VEZ al inicio del programa
        llm = Llama(
            model_path=MODELO_PATH,
            n_ctx=params.get("n_ctx", 10000),
            n_gpu_layers=0,
            verbose=False
        )
        
        print("✅ Modelo de lenguaje cargado correctamente con llama_cpp")
        print(f"   Contexto: {params.get('n_ctx', 10000)} tokens")
        print(f"   Temperatura: {params.get('temperature', 0.2)}")
        print(f"   Max tokens: {params.get('max_tokens', 212)}")
        print(f"   Top P: {params.get('top_p', 0.9)}")
        
    except Exception as e:
        print(f"❌ Error al cargar el modelo: {e}")
        exit(1)
else:
    print("❌ llama_cpp no disponible")
    exit(1)

# =============================================
# FUNCIONES DE ALARMA Y RECORDATORIOS
# =============================================

def ejecutar_alarma(segundos, mensaje):
    """Ejecuta la alarma después del tiempo especificado.

    Parámetros:
    - segundos: tiempo a esperar (float)
    - mensaje: etiqueta legible de la alarma (por ejemplo: 'mañana a las 16:00' o 'recordatorio: sacar la ropa')
    """
    try:
        time.sleep(max(0, float(segundos)))
    except Exception:
        time.sleep(0)

    # Intentar reproducir un sonido de alarma
    reproducir_sonido_alarma()

    # Anunciar la alarma de forma concisa
    try:
        hablar(f"Alarma: {mensaje}")
    except Exception:
        print(f"🔔 Alarma: {mensaje}")

def programar_alarma(texto):
    """
    Procesa el texto para detectar tiempos relativos (5 min) o 
    fechas/horas exactas (mañana a las 10:00).
    """
    texto_limpio = texto.lower()
    
    # Limpieza de palabras basura
    palabras_quitar = ["pon ", " una", " un", " el", " la", "asistente", "nova", "ponme", "ajusta", "alarma", "para"]
    for p in palabras_quitar:
        texto_limpio = texto_limpio.replace(p, "").strip()

    ahora = datetime.now()
    fecha_objetivo = None

    # Detectar patrones absolutos de hora en español: 'para las 4', 'a las 16:00', '11:26', 'hoy a las 4'
    m = re.search(
        r"\b(?:para\s+las?|a\s+las?|a\s+la|para\s+la)?\s*(\d{1,2})(?:(?:[:\.h])(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?\b",
        texto_limpio
    )
    if m:
        try:
            hora = int(m.group(1))
            minuto = int(m.group(2)) if m.group(2) else 0
            ampm = m.group(3)
            if ampm:
                ampm = ampm.replace('.', '').lower()
                if ampm in ('pm', 'p m', 'p.m', 'p.m.') and hora < 12:
                    hora += 12
                if ampm in ('am', 'a m', 'a.m', 'a.m.') and hora == 12:
                    hora = 0

            # Normalizar hora al rango 0-23
            hora = hora % 24

            fecha_objetivo = ahora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
            if fecha_objetivo <= ahora:
                fecha_objetivo = fecha_objetivo + timedelta(days=1)
        except Exception:
            fecha_objetivo = None

    # Si no se detectó patrón absoluto, intentar dateparser
    # Opción A: Usar dateparser para lenguaje natural
    if fecha_objetivo is None and DATEPARSER_AVAILABLE and dateparser is not None:
        try:
            fecha_objetivo = dateparser.parse(
                texto_limpio,
                languages=['es'],
                settings={'PREFER_DATES_FROM': 'future', 'RELATIVE_BASE': ahora}
            )
        except Exception as e:
            print(f"Error parseando fecha: {e}")

    # Opción B: Lógica manual
    if not fecha_objetivo:
        # Buscar números en el texto
        numeros = re.findall(r'\d+', texto_limpio)
        if numeros:
            if len(numeros) == 2:
                hora = int(numeros[0])
                minuto = int(numeros[1])
                if 0 <= hora <= 23 and 0 <= minuto <= 59:
                    fecha_objetivo = ahora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
                    if fecha_objetivo <= ahora:
                        fecha_objetivo = fecha_objetivo + timedelta(days=1)
            if fecha_objetivo is None:
                valor = int(numeros[0])
                if len(numeros) == 1 and 100 <= valor <= 2359:
                    posible_hora = valor // 100
                    posible_minuto = valor % 100
                    if 0 <= posible_hora <= 23 and 0 <= posible_minuto <= 59:
                        fecha_objetivo = ahora.replace(hour=posible_hora, minute=posible_minuto, second=0, microsecond=0)
                        if fecha_objetivo <= ahora:
                            fecha_objetivo = fecha_objetivo + timedelta(days=1)
                elif "hora" in texto_limpio:
                    fecha_objetivo = ahora + timedelta(hours=valor)
                elif "segundo" in texto_limpio:
                    fecha_objetivo = ahora + timedelta(seconds=valor)
                elif "dia" in texto_limpio or "día" in texto_limpio:
                    fecha_objetivo = ahora + timedelta(days=valor)
                else:
                    # Por defecto minutos
                    fecha_objetivo = ahora + timedelta(minutes=valor)

    if not fecha_objetivo or fecha_objetivo <= ahora:
        return "no pude entender cuándo quieres la alarma o la fecha ya pasó"

    # Calcular cuántos segundos faltan
    segundos_faltantes = (fecha_objetivo - ahora).total_seconds()

    # Formatear respuesta para el usuario
    tiempo_legible = fecha_objetivo.strftime("%H:%M")
    if fecha_objetivo.date() > ahora.date():
        if (fecha_objetivo.date() - ahora.date()).days == 1:
            confirmacion = f"entendido, alarma programada para mañana a las {tiempo_legible}"
        else:
            confirmacion = f"entendido, alarma programada para el {fecha_objetivo.strftime('%d/%m')} a las {tiempo_legible}"
    else:
        confirmacion = f"entendido, alarma programada para las {tiempo_legible}"

    # No anunciar desde el backend: el cliente que hizo la petición debe reproducir la confirmación.

    # Crear una etiqueta legible para la alarma (no el comando completo del usuario)
    etiqueta = f"programada para las {tiempo_legible}"

    # Lanzar el hilo de alarma que reproducirá sonido y anuncio al activarse
    hilo_alarma = threading.Thread(
        target=ejecutar_alarma,
        args=(segundos_faltantes, etiqueta),
        daemon=True
    )
    hilo_alarma.start()

    return confirmacion


def reproducir_sonido_alarma():
    """Intenta reproducir un sonido de alarma sin bloquear la entrada del usuario."""
    ruta_sonido = os.path.join('sonidos', 'alarma.mp3')
    # Si existe archivo de alarma, reproducirlo con ffplay/aplay/paplay
    if os.path.exists(ruta_sonido) and os.path.getsize(ruta_sonido) > 0:
        try:
            # USAR Popen en lugar de run - NO bloquea el stdin
            subprocess.Popen(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", ruta_sonido],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL
            )
            return True
        except FileNotFoundError:
            try:
                subprocess.Popen(
                    ["aplay", "-q", ruta_sonido],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return True
            except FileNotFoundError:
                try:
                    subprocess.Popen(
                        ["paplay", ruta_sonido],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    return True
                except Exception:
                    pass
        except Exception:
            pass

    # Si no hay archivo o reproductor, emitir un beep repetido
    try:
        for _ in range(3):
            print('\a', end='', flush=True)
            time.sleep(0.5)
        return True
    except Exception:
        return False

def nota_tiempo(nota):
    """
    Función para recordatorios temporales.
    Ejemplos:
    - "recuerdame comprar pan en 5 minutos"
    - "recuerdame comprar pan mañana"
    - "recuerdame comprar pan cada día"
    """
    nota_limpia = re.sub(r'(recuerdame|recuérdame|recordar|recuerda)', '', nota, flags=re.IGNORECASE).strip()
    
    # Detectar si es un recordatorio recurrente
    if any(palabra in nota.lower() for palabra in ["cada dia", "cada día", "diario", "todos los dias"]):
        # Recordatorio diario
        return programar_recordatorio_diario(nota_limpia)
    
    # Detectar tiempo específico
    ahora = datetime.now()
    fecha_objetivo = None
    
    if DATEPARSER_AVAILABLE and dateparser is not None:
        try:
            fecha_objetivo = dateparser.parse(
                nota.lower(),
                languages=['es'],
                settings={'PREFER_DATES_FROM': 'future', 'RELATIVE_BASE': ahora}
            )
        except:
            pass
    
    if not fecha_objetivo:
        # Buscar números de minutos
        numeros = re.findall(r'(\d+)\s*(?:minuto|min|m)', nota.lower())
        if numeros:
            minutos = int(numeros[0])
            fecha_objetivo = ahora + timedelta(minutes=minutos)
        else:
            # Por defecto, 5 minutos
            fecha_objetivo = ahora + timedelta(minutes=5)
    
    segundos = (fecha_objetivo - ahora).total_seconds()
    
    if segundos > 0:
        hilo = threading.Thread(target=ejecutar_alarma, args=(segundos, nota_limpia), daemon=True)
        hilo.start()
        return f"recordatorio programado: {nota_limpia}"
    
    return "no pude programar el recordatorio"

def programar_recordatorio_diario(nota):
    """Programa un recordatorio diario."""
    def recordatorio_diario():
        while True:
            hablar(f"recordatorio: {nota}")
            time.sleep(86400)  # 24 horas
    
    hilo = threading.Thread(target=recordatorio_diario, daemon=True)
    hilo.start()
    return f"recordatorio diario programado: {nota}"

# =============================================
# FUNCIONES BÁSICAS (HORA, FECHA)
# =============================================

def obtener_hora():
    """Retorna la hora actual en formato natural."""
    hora_actual = datetime.now()
    hora = hora_actual.hour
    minuto = hora_actual.minute
    
    if hora > 12:
        hora = hora - 12
    if hora == 0:
        hora = 12
    
    if minuto == 0:
        return f"la hora actual es las {hora} en punto"
    elif minuto == 1:
        return f"la hora actual es las {hora} y un minuto"
    else:
        return f"la hora actual es las {hora} con {minuto} minutos"

def obtener_fecha():
    """Retorna la fecha actual en formato natural."""
    DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
    MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio",
             "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")
    f = datetime.now()
    return f"hoy es {DIAS[f.weekday()]}, {f.day} de {MESES[f.month-1]} de {f.year}"

# =============================================
# FUNCIONES DE MÚSICA USB (CON FALLBACK A INTERNET)
# =============================================

def limpiar_nombre_cancion(texto):
    """Limpia el nombre de la canción de palabras comunes."""
    palabras_quitar = [
        "pon", "reproduce", "reproducir", "coloca", "musica", "música", 
        "la cancion", "la canción", "cancion", "canción", "audio", 
        "de ", "en ", "el ", "la ", "los", "las", "un", "una", "unos", "unas",
        "por favor", "online", "internet", "usb", "memoria", "disco", 
        "archivo", "porfavor", "toca", "ponme", "reproducime", "colocame"
    ]
    
    texto_limpio = texto.lower()
    for palabra in palabras_quitar:
        texto_limpio = texto_limpio.replace(palabra, "")
    
    # Eliminar espacios múltiples
    texto_limpio = re.sub(r'\s+', ' ', texto_limpio).strip()
    
    return texto_limpio

def musica_usb(cancion_especifica=None):
    """Reproduce música desde USB con fallback a internet si el usuario lo permite."""
    if not PYGAME_AVAILABLE or pygame is None:
        return "el reproductor de música no está disponible"
    
    extensiones = ('.mp3', '.wav', '.ogg', ".mp4")
    canciones = []
    
    # Verificar si existe el directorio /media (donde se montan USBs en Linux)
    if not os.path.exists("/media"):
        hablar("No se detecta dispositivo USB conectado")
        
        # Preguntar si quiere buscar en internet
        if cancion_especifica:
            if verificar_estado_red():
                hablar(f"¿Deseas buscar '{cancion_especifica}' en internet?")
                respuesta = input(f"\n🎵 No se encontró USB. ¿Buscas '{cancion_especifica}' en internet? (s/N): ").strip().lower()
                if respuesta in ['s', 'si', 'sí', 'yes', 'y']:
                    hablar(f"Buscando {cancion_especifica} en streaming...")
                    return musica_online(cancion_especifica)
        else:
            if verificar_estado_red():
                hablar("¿Deseas buscar música en internet?")
                respuesta = input("\n🎵 No se encontró USB. ¿Buscas música en internet? (s/N): ").strip().lower()
                if respuesta in ['s', 'si', 'sí', 'yes', 'y']:
                    hablar("Buscando música en streaming...")
                    return musica_online()
        
        return "no se detectó dispositivo USB"
    
    # Buscar música en la USB
    for raiz, _, archivos in os.walk("/media"):
        for f in archivos:
            if f.lower().endswith(extensiones):
                canciones.append(os.path.join(raiz, f))
    
    # Si se pidió una canción específica
    if cancion_especifica:
        cancion_buscar = cancion_especifica.lower()
        for ruta in canciones:
            nombre_archivo = os.path.basename(ruta).lower()
            if cancion_buscar in nombre_archivo or nombre_archivo in cancion_buscar:
                try:
                    pygame.mixer.music.load(ruta)
                    pygame.mixer.music.play()
                    print(f"🎵 Reproduciendo: {os.path.basename(ruta)}")
                    
                    while pygame.mixer.music.get_busy():
                        if not os.path.exists(ruta):
                            raise OSError("USB Desconectada")
                        time.sleep(0.5)
                    
                    return f"reproducción finalizada: {cancion_especifica}"
                except (pygame.error, OSError):
                    pygame.mixer.music.stop()
                    return "la USB se desconectó durante la reproducción"
        
        # No encontrada en USB, preguntar por internet
        if verificar_estado_red():
            hablar(f"No encontré '{cancion_especifica}' en la USB. ¿Buscas en internet?")
            respuesta = input(f"\n🎵 ¿Buscas '{cancion_especifica}' en internet? (s/N): ").strip().lower()
            if respuesta in ['s', 'si', 'sí', 'yes', 'y']:
                return musica_online(cancion_especifica)
        return f"canción '{cancion_especifica}' no encontrada en la USB"
    
    # Si no hay canciones en la USB
    if not canciones:
        hablar("No se encontró música en la USB")
        
        if verificar_estado_red():
            hablar("¿Deseas buscar música en internet?")
            respuesta = input("\n🎵 No hay música en la USB. ¿Buscas música en internet? (s/N): ").strip().lower()
            if respuesta in ['s', 'si', 'sí', 'yes', 'y']:
                hablar("Buscando música en streaming...")
                return musica_online()
        else:
            hablar("No hay conexión a internet para buscar música online")
        
        return "no se encontró música en la USB"
    
    # Reproducir todas las canciones de la USB
    for ruta in canciones:
        global musica_detener
        if musica_detener:
            musica_detener = False
            break
            
        try:
            pygame.mixer.music.load(ruta)
            pygame.mixer.music.play()
            
            nombre_archivo = os.path.basename(ruta)
            print(f"🎵 Reproduciendo: {nombre_archivo}")
            
            while pygame.mixer.music.get_busy():
                if musica_detener:
                    pygame.mixer.music.stop()
                    musica_detener = False
                    return "reproducción detenida"
                if not os.path.exists(ruta):
                    raise OSError("USB Desconectada")
                time.sleep(0.5)
                
        except (pygame.error, OSError):
            pygame.mixer.music.stop()
            hablar("La USB se desconectó durante la reproducción")
            return "la USB se desconectó, reproducción interrumpida"
    
    return "reproducción de USB finalizada"

def reproduccion_especifica_usb(nombre_cancion):
    """Reproduce una canción específica desde USB con fallback a internet."""
    return musica_usb(nombre_cancion)

# =============================================
# FUNCIONES DE MÚSICA ONLINE CON YT-DLP (CORREGIDA)
# =============================================

def extraer_nombre_cancion(texto_original):
    """
    Extrae el nombre real de la canción del texto del usuario.
    Ejemplo: "pon una noche mas de esteman y adrian bello" -> "noche mas esteman adrian bello"
    """
    # Palabras que indican acción musical
    palabras_accion = [
        "pon", "reproduce", "reproducir", "coloca", "toca", "ponme", 
        "reproducime", "colocame", "tocame", "musica", "música", 
        "la cancion", "la canción", "cancion", "canción"
    ]
    
    texto = texto_original.lower()
    
    # Eliminar palabras de acción
    for palabra in palabras_accion:
        texto = texto.replace(palabra, "")
    
    # Eliminar palabras comunes
    palabras_comunes = [
        "de ", " y ", " la ", " el ", " los ", " las ", " un ", " una ", " unos ", " unas",
        " por", " para", " con", " sin", " sobre", " tras", " durante", " mediante",
        " a", " ante", " bajo", " cabe", " contra", " desde", " en", " entre", " hacia",
        " hasta", " según", " via", " vs", " por favor", " online", " internet"
    ]
    
    for palabra in palabras_comunes:
        texto = texto.replace(f" {palabra} ", " ")
        texto = texto.replace(f" {palabra} ", " ")
    
    # Limpiar espacios múltiples
    texto = re.sub(r'\s+', ' ', texto).strip()
    
    # Si después de limpiar está vacío, devolver None
    if not texto or len(texto) < 2:
        return None
    
    return texto

def musica_online(nombre_cancion=None):
    """
    Reproduce música desde YouTube usando yt-dlp.
    AHORA CORREGIDO: reconoce correctamente los nombres de canciones.
    """
    
    if not PYGAME_AVAILABLE or pygame is None:
        return "el reproductor de música no está disponible"
    
    if not verificar_estado_red():
        return "no hay conexión a internet para reproducir música online"
    
    if not YTDLP_AVAILABLE:
        return "yt-dlp no está instalado. Ejecuta: pip install yt-dlp"
    
    # CORRECCIÓN PRINCIPAL: Si se pasó un nombre, usarlo; si no, usar búsqueda por defecto
    if nombre_cancion and nombre_cancion.strip() and nombre_cancion:
        # Limpiar el nombre de la canción de palabras basura
        busqueda = limpiar_nombre_cancion(nombre_cancion)
        
        # Si después de limpiar queda vacío, buscar por defecto
        if not busqueda or len(busqueda) < 2:
            busqueda = "música popular"
            print("⚠️ Nombre de canción no reconocido, usando búsqueda por defecto")
    else:
        # Búsqueda por defecto
        busqueda = "música popular"
    
    print(f"🔍 Buscando en YouTube: {busqueda}")
    hablar(f"Buscando {busqueda} en YouTube music")
    
    # Archivo temporal para el audio
    os.makedirs("tmp", exist_ok=True)
    output_file = "tmp/youtube_audio_temp.mp3"
    
    # Eliminar archivo temporal anterior si existe
    if os.path.exists(output_file):
        try:
            os.remove(output_file)
        except:
            pass
    
    # Configuración mejorada de yt-dlp
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'default_search': 'ytsearch',
        'max_downloads': 1,
        'outtmpl': output_file.replace('.mp3', '.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }],
        'ffmpeg_location': '/usr/bin/ffmpeg' if os.path.exists('/usr/bin/ffmpeg') else None,
        'cookiefile': None,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'extractor_args': {
            'youtube': {
                'skip': ['dash', 'hls'],
                'player_client': ['android', 'web'],
            }
        }
    }
    
    # MÉTODO 1: Usar YoutubeDL directamente
    try:
        with YoutubeDL(ydl_opts) as ydl:
            # Construir la consulta de búsqueda
            search_query = f"ytsearch1:{busqueda} audio"
            info = ydl.extract_info(search_query, download=True)
            
            # Buscar el archivo descargado
            archivo_descargado = None
            for archivo in os.listdir("tmp"):
                if archivo.endswith(".mp3"):
                    ruta_archivo = os.path.join("tmp", archivo)
                    if os.path.getsize(ruta_archivo) > 10000:
                        archivo_descargado = ruta_archivo
                        break
            
            if archivo_descargado and os.path.exists(archivo_descargado):
                file_size = os.path.getsize(archivo_descargado)
                titulo = info.get('entries', [{}])[0].get('title', busqueda) if 'entries' in info else busqueda
                print(f"✅ Audio descargado: {titulo[:50]} ({file_size} bytes)")
                hablar(f"Reproduciendo {titulo[:50]}")
                
                # Renombrar al nombre estándar
                if archivo_descargado != output_file:
                    os.rename(archivo_descargado, output_file)
                
                # Reproducir
                pygame.mixer.music.load(output_file)
                pygame.mixer.music.play()
                
                while pygame.mixer.music.get_busy():
                    global musica_detener
                    if musica_detener:
                        pygame.mixer.music.stop()
                        musica_detener = False
                        try:
                            os.remove(output_file)
                        except:
                            pass
                        return "reproducción detenida"
                    time.sleep(0.5)
                
                # Limpiar
                try:
                    os.remove(output_file)
                except:
                    pass
                
                return f"reproducción finalizada: {titulo[:100]}"
            else:
                return "no se encontró el archivo descargado"
                
    except Exception as e:
        print(f"⚠️ Error método 1: {e}")
        
        # MÉTODO 2: Usar subprocess con cookies
        try:
            return musica_online_subprocess(busqueda)
        except Exception as e2:
            print(f"⚠️ Error método 2: {e2}")
            
            # MÉTODO 3: Usar fallback simple
            return musica_online_fallback(busqueda)

def musica_online_subprocess(busqueda):
    """Método alternativo usando subprocess con yt-dlp."""
    
    output_file = "tmp/youtube_audio_temp.mp3"
    
    # Comando mejorado con opciones para evitar errores de JavaScript
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "128K",
        "--output", output_file,
        "--no-playlist",
        "--no-warnings",
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "--extractor-args", "youtube:player_client=android",
        f"ytsearch1:{busqueda}"
    ]
    
    try:
        print("🔄 Intentando descarga con subprocess...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        
        if result.returncode == 0:
            # Buscar archivo descargado
            archivo_mp3 = None
            for archivo in os.listdir("tmp"):
                if archivo.endswith(".mp3"):
                    ruta = os.path.join("tmp", archivo)
                    if os.path.getsize(ruta) > 10000:
                        archivo_mp3 = ruta
                        break
            
            if archivo_mp3 and os.path.exists(archivo_mp3):
                file_size = os.path.getsize(archivo_mp3)
                print(f"✅ Audio descargado: {file_size} bytes")
                hablar(f"Reproduciendo {busqueda}")
                
                # Asegurar nombre consistente
                if archivo_mp3 != output_file:
                    if os.path.exists(output_file):
                        os.remove(output_file)
                    os.rename(archivo_mp3, output_file)
                
                pygame.mixer.music.load(output_file)
                pygame.mixer.music.play()
                
                while pygame.mixer.music.get_busy():
                    global musica_detener
                    if musica_detener:
                        pygame.mixer.music.stop()
                        musica_detener = False
                        try:
                            os.remove(output_file)
                        except:
                            pass
                        return "reproducción detenida"
                    time.sleep(0.5)
                
                try:
                    os.remove(output_file)
                except:
                    pass
                
                return f"reproducción finalizada: {busqueda}"
            else:
                return "no se encontró el archivo de audio descargado"
        else:
            error_msg = result.stderr[:200] if result.stderr else "Error desconocido"
            return f"error en descarga: {error_msg}"
            
    except subprocess.TimeoutExpired:
        return "tiempo de espera agotado al descargar"
    except Exception as e:
        return f"error en subprocess: {str(e)}"

def musica_online_fallback(busqueda):
    """Fallback simple que informa el problema y sugiere soluciones."""
    
    # Intentar con un nombre más simple
    busqueda_simple = busqueda.split()[0] if busqueda else "music"
    
    return f"""No se pudo reproducir '{busqueda}' por problemas con YouTube.
    
Posibles soluciones:
1. Actualiza yt-dlp: pip install --upgrade yt-dlp
2. Instala ffmpeg: sudo apt install ffmpeg -y
3. Prueba con una USB que tenga música
4. Busca '{busqueda_simple}' manualmente en YouTube

¿Deseas que busque otra canción?"""

def detener():
    """Detiene la reproducción de música."""
    global musica_detener
    if PYGAME_AVAILABLE and pygame and pygame.mixer.get_init():
        musica_detener = True
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
        return "SISTEMA: Música detenida."
    return "SISTEMA: Nada que detener."

# =============================================
# FUNCIONES DE NOTAS
# =============================================

def tomar_nota(nota):
    """Guarda una nota."""
    try:
        nota_limpia = re.sub(r'(toma nota|guardar nota|nota|anota|recuerda|recuerdame)', '', nota, flags=re.IGNORECASE).strip()
        
        if not nota_limpia:
            return "no especificaste qué nota quieres guardar"
        
        if not os.path.exists(NOTAS_DIR):
            os.makedirs(NOTAS_DIR)
        
        ruta_nota = os.path.join(NOTAS_DIR, "nota_1.txt")
        with open(ruta_nota, 'w', encoding='utf-8') as archivo:
            archivo.write(nota_limpia)
        hablar("nota guardada")
        return f"nota guardada: {nota_limpia}"
    
    except Exception as e:
        return f"error al guardar la nota: {str(e)}"

def leer_nota():
    """Lee la nota guardada."""
    try:
        ruta_nota = os.path.join(NOTAS_DIR, "nota_1.txt")
        
        if not os.path.exists(ruta_nota):
            return "no hay ninguna nota guardada"
        
        with open(ruta_nota, 'r', encoding='utf-8') as archivo:
            contenido = archivo.read().strip()
        
        if contenido:
            hablar(f"la nota dice: {contenido}")
            return f"la nota dice: {contenido}"
        else:
            return "las notas están vacías"
    
    except Exception as e:
        return f"error al leer la nota: {str(e)}"

# =============================================
# FUNCIÓN DE CONVERSACIÓN AI
# =============================================

def conversacion_ai(entrada):
    """Función de conversación optimizada que usa el modelo ya cargado."""
    global llm

    estado_red = "false"
    try:
        if os.path.exists(NETWORK_STATUS_FILE):
            with open(NETWORK_STATUS_FILE, "r", encoding="utf-8") as f:
                estado_red = f.read().strip().lower()
    except Exception as e:
        print(f"⚠️ No se pudo leer el estado de red: {e}")

    # Intentar usar Groq si hay conexión
    if estado_red == "true" and GROQ_AVAILABLE and GROQ_API_KEY:
        try:
            client = Groq(api_key=GROQ_API_KEY)
            response = client.chat.completions.create(
                model=GROQ_MODEL_ID,
                messages=[
                    {"role": "system", "content": SYSTEM_BASE},
                    {"role": "user", "content": entrada}
                ],
                temperature=params.get("temperature", 0.2),
                max_tokens=params.get("max_tokens", 212),
                top_p=params.get("top_p", 0.9)
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"⚠️ Error usando Groq: {e}")

    # Usar modelo local
    if llm is None:
        return "error: el modelo de lenguaje no está disponible"

    try:
        full_prompt = (
            f"<|im_start|>system\n{SYSTEM_BASE}<|im_end|>\n"
            f"<|im_start|>user\n{entrada}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
        
        print(f"🤖 Generando respuesta con llama_cpp para: {entrada[:50]}...")
        
        response = llm(
            full_prompt,
            stream=False,
            max_tokens=params.get("max_tokens", 212),
            temperature=params.get("temperature", 0.2),
            top_p=params.get("top_p", 0.9),
            stop=["<|im_end|>", "<|im_start|>"]
        )
        
        respuesta = response["choices"][0]["text"].strip()
        
        if respuesta:
            print(f"Respuesta generada: {respuesta[:100]}...")
            return respuesta
        else:
            return "lo siento, no pude generar una respuesta en este momento"
            
    except Exception as e:
        print(f"❌ Error en conversacion_ai: {e}")
        return f"ocurrió un error al procesar tu solicitud: {str(e)}"

# =============================================
# FUNCIONES QUE REQUIEREN RED
# =============================================

def obtener_ubicacion():
    """
    Detecta la ubicación actual usando GPS o IP.
    Retorna un diccionario con ciudad, región y país.
    """
    ubicacion = {
        "ciudad": "Desconocida",
        "region": "Desconocida",
        "pais": "Desconocido",
        "lat": None,
        "lon": None
    }
    
    if GEOCODER_AVAILABLE:
        try:
            # Intentar obtener ubicación por IP
            g = geocoder.ip('me')
            if g.ok:
                ubicacion["ciudad"] = g.city or "Desconocida"
                ubicacion["region"] = g.state or "Desconocida"
                ubicacion["pais"] = g.country or "Desconocido"
                ubicacion["lat"] = g.latlng[0] if g.latlng else None
                ubicacion["lon"] = g.latlng[1] if g.latlng else None
                
                # Guardar ubicación en personalización
                actualizar_ubicacion(
                    ubicacion["ciudad"],
                    ubicacion["region"],
                    ubicacion["pais"],
                    ubicacion["lat"],
                    ubicacion["lon"]
                )
                
                return ubicacion
        except Exception as e:
            print(f"⚠️ Error obteniendo ubicación por IP: {e}")
    
    # Fallback: intentar por API de ipinfo.io
    try:
        response = requests.get("https://ipinfo.io/json", timeout=5)
        if response.status_code == 200:
            data = response.json()
            ubicacion["ciudad"] = data.get("city", "Desconocida")
            ubicacion["region"] = data.get("region", "Desconocida")
            ubicacion["pais"] = data.get("country", "Desconocido")
            loc = data.get("loc", "").split(",")
            if len(loc) == 2:
                ubicacion["lat"] = float(loc[0])
                ubicacion["lon"] = float(loc[1])
            
            # Guardar ubicación en personalización
            actualizar_ubicacion(
                ubicacion["ciudad"],
                ubicacion["region"],
                ubicacion["pais"],
                ubicacion["lat"],
                ubicacion["lon"]
            )
    except Exception as e:
        print(f"⚠️ Error obteniendo ubicación por API: {e}")
    
    return ubicacion

def obtener_clima(ciudad=None):
    """
    Obtiene el clima actual. Si no se especifica ciudad, usa la ubicación guardada
    o detecta la ubicación actual.
    """
    if not api_clima:
        return "SISTEMA: API del clima no configurada."
    
    # Si no se especifica ciudad, intentar usar la guardada o detectar
    if not ciudad:
        datos = cargar_personalizacion()
        if datos and datos.get("ubicacion"):
            ubicacion = datos["ubicacion"]
            ciudad = ubicacion.get("ciudad", "Tepatitlan")
            
            if ubicacion.get("lat") and ubicacion.get("lon"):
                url = f"http://api.openweathermap.org/data/2.5/weather?lat={ubicacion['lat']}&lon={ubicacion['lon']}&appid={api_clima}&units=metric&lang=es"
            else:
                url = f"http://api.openweathermap.org/data/2.5/weather?q={ciudad}&appid={api_clima}&units=metric&lang=es"
        else:
            # Detectar ubicación
            ubicacion = obtener_ubicacion()
            ciudad = ubicacion.get("ciudad", "Tepatitlan")
            
            if ubicacion.get("lat") and ubicacion.get("lon"):
                url = f"http://api.openweathermap.org/data/2.5/weather?lat={ubicacion['lat']}&lon={ubicacion['lon']}&appid={api_clima}&units=metric&lang=es"
            else:
                url = f"http://api.openweathermap.org/data/2.5/weather?q={ciudad}&appid={api_clima}&units=metric&lang=es"
    else:
        # Limpiar nombre de ciudad
        ciudad_limpia = ciudad.lower().replace("clima", "").replace("en", "").strip()
        if ciudad_limpia:
            ciudad = ciudad_limpia
        url = f"http://api.openweathermap.org/data/2.5/weather?q={ciudad}&appid={api_clima}&units=metric&lang=es"
    
    try:
        data = requests.get(url, timeout=5).json()
        
        if data.get("cod") != 200:
            return f"SISTEMA: No se encontró la ciudad '{ciudad}'."
        
        temp = data["main"]["temp"]
        temp_min = data["main"]["temp_min"]
        temp_max = data["main"]["temp_max"]
        humedad = data["main"]["humidity"]
        desc = data["weather"][0]["description"]
        viento = data["wind"]["speed"]
        nombre_ciudad = data["name"]
        
        return f"DATOS_PARA_IA: En {nombre_ciudad} el clima es {desc} con {temp}°C (mín {temp_min}°C, máx {temp_max}°C), humedad del {humedad}% y viento de {viento} m/s. Resume esto para el usuario."
    
    except Exception as e:
        return f"SISTEMA: Error al obtener el clima: {str(e)}"

def investigar_tema(tema):
    """Busca información sobre un tema."""
    tema = tema.replace("investiga", "").replace("busca", "").strip()
    
    if not tema:
        return "SISTEMA: No especificaste qué tema investigar."
    
    return f"DATOS_PARA_IA: El usuario quiere información sobre '{tema}'. Proporciona un resumen útil basado en tu conocimiento."

def traductor_ingles(texto):
    """Traduce texto a inglés."""
    if not TRANSLATOR_AVAILABLE or translator is None:
        return "SISTEMA: Traductor no disponible."
    
    # Limpiar palabras basura
    basura = ["que significa", "qué significa", "traduce", "traductor", "en ingles", "en inglés"]
    for b in basura:
        texto = texto.replace(b, "")
    texto = texto.strip()
    
    if not texto:
        return "SISTEMA: No especificaste qué texto traducir."
    
    try:
        r = translator.translate(texto, src="es", dest="en")
        return f"DATOS_PARA_IA: '{texto}' en inglés es '{r.text}'."
    except Exception as e:
        return f"SISTEMA: Error en traducción: {str(e)}"

def abrir_roku(intencion):
    """Abre aplicaciones en Roku."""
    APPS_ROKU = {"youtube": "837", "netflix": "12", "spotify": "19977"}
    app = intencion.replace("abrir_app_", "")
    
    if app in APPS_ROKU:
        return f"DATOS_PARA_IA: Abriendo {app} en Roku."
    return "SISTEMA: Aplicación no soportada en Roku."

# =============================================
# FUNCIONES DE LISTA DE COMPRAS
# =============================================

def cargar_listas():
    """Carga las listas de compras desde archivo."""
    global listas_compras
    listas_file = os.path.join(LISTAS_DIR, "listas_compras.json")
    
    if os.path.exists(listas_file):
        try:
            with open(listas_file, 'r', encoding='utf-8') as f:
                listas_compras = json.load(f)
        except:
            listas_compras = {}
    else:
        listas_compras = {"principal": []}

def guardar_listas():
    """Guarda las listas de compras en archivo."""
    listas_file = os.path.join(LISTAS_DIR, "listas_compras.json")
    with open(listas_file, 'w', encoding='utf-8') as f:
        json.dump(listas_compras, f, indent=2, ensure_ascii=False)

def agregar_a_lista(texto):
    """
    Agrega items a la lista de compras.
    Ejemplo: "agrega leche, pan y huevos a la lista de compras"
    """
    cargar_listas()
    
    # Limpiar texto
    texto_limpio = re.sub(r'(agrega|añade|pon|agregar|añadir|a la lista|de compras|de super)', '', texto, flags=re.IGNORECASE).strip()
    
    if not texto_limpio:
        return "no especificaste qué agregar a la lista"
    
    # Separar por comas o "y"
    items = re.split(r',|\sy\s', texto_limpio)
    items = [item.strip() for item in items if item.strip()]
    
    if "principal" not in listas_compras:
        listas_compras["principal"] = []
    
    for item in items:
        if item not in listas_compras["principal"]:
            listas_compras["principal"].append(item)
    
    guardar_listas()
    
    items_str = ", ".join(items)
    hablar(f"agregué {items_str} a la lista de compras")
    return f"agregado a la lista: {items_str}"

def leer_lista():
    """Lee la lista de compras actual."""
    cargar_listas()
    
    if "principal" not in listas_compras or not listas_compras["principal"]:
        return "la lista de compras está vacía"
    
    items = listas_compras["principal"]
    items_str = ", ".join(items)
    hablar(f"tu lista de compras tiene: {items_str}")
    return f"lista de compras: {items_str}"

def quitar_de_lista(texto):
    """Quita items de la lista de compras."""
    cargar_listas()
    
    texto_limpio = re.sub(r'(quita|elimina|borra|remover|de la lista|de compras)', '', texto, flags=re.IGNORECASE).strip()
    
    if not texto_limpio:
        return "no especificaste qué quitar de la lista"
    
    if "principal" not in listas_compras:
        return "la lista está vacía"
    
    # Buscar el item a eliminar
    for item in listas_compras["principal"][:]:
        if texto_limpio.lower() in item.lower():
            listas_compras["principal"].remove(item)
            guardar_listas()
            hablar(f"eliminé {item} de la lista")
            return f"eliminado de la lista: {item}"
    
    return f"no encontré '{texto_limpio}' en la lista"

def limpiar_lista():
    """Limpia toda la lista de compras."""
    cargar_listas()
    listas_compras["principal"] = []
    guardar_listas()
    hablar("lista de compras limpiada")
    return "lista de compras limpiada"

# =============================================
# FUNCIONES DE CALENDARIO Y PLANIFICACIÓN
# =============================================

def cargar_calendario():
    """Carga los eventos del calendario."""
    global eventos_calendario
    
    if os.path.exists(CALENDARIO_FILE):
        try:
            with open(CALENDARIO_FILE, 'r', encoding='utf-8') as f:
                eventos_calendario = json.load(f)
        except:
            eventos_calendario = []
    else:
        eventos_calendario = []

def guardar_calendario():
    """Guarda los eventos del calendario."""
    with open(CALENDARIO_FILE, 'w', encoding='utf-8') as f:
        json.dump(eventos_calendario, f, indent=2, ensure_ascii=False)

def agregar_evento(texto):
    """
    Agrega un evento al calendario.
    Ejemplo: "agenda cita con doctor mañana a las 3 de la tarde"
    """
    cargar_calendario()
    
    texto_limpio = re.sub(r'(agenda|agregar evento|nuevo evento|programa|cita)', '', texto, flags=re.IGNORECASE).strip()
    
    if not texto_limpio:
        return "no especificaste el evento a agendar"
    
    ahora = datetime.now()
    fecha_evento = None
    descripcion = texto_limpio
    
    # Intentar extraer fecha con dateparser
    if DATEPARSER_AVAILABLE and dateparser:
        try:
            fecha_evento = dateparser.parse(
                texto_limpio,
                languages=['es'],
                settings={'PREFER_DATES_FROM': 'future', 'RELATIVE_BASE': ahora}
            )
            
            # Extraer descripción (lo que no es fecha)
            if fecha_evento:
                descripcion = texto_limpio
        except:
            pass
    
    if not fecha_evento:
        # Por defecto, mañana a las 9:00
        fecha_evento = ahora + timedelta(days=1)
        fecha_evento = fecha_evento.replace(hour=9, minute=0, second=0, microsecond=0)
    
    evento = {
        "descripcion": descripcion.strip(),
        "fecha": fecha_evento.strftime("%Y-%m-%d %H:%M"),
        "timestamp": fecha_evento.timestamp()
    }
    
    eventos_calendario.append(evento)
    eventos_calendario.sort(key=lambda x: x["timestamp"])
    guardar_calendario()
    
    fecha_str = fecha_evento.strftime("%d/%m a las %H:%M")
    hablar(f"evento agendado: {descripcion} para el {fecha_str}")
    return f"evento agendado: {descripcion} - {fecha_str}"

def consultar_agenda(texto=""):
    """Consulta los eventos del calendario."""
    cargar_calendario()
    
    if not eventos_calendario:
        return "no tienes eventos agendados"
    
    ahora = datetime.now()
    
    # Filtrar eventos futuros
    if "hoy" in texto.lower():
        eventos_filtrados = [e for e in eventos_calendario 
                           if datetime.fromtimestamp(e["timestamp"]).date() == ahora.date()]
        prefijo = "hoy"
    elif "mañana" in texto.lower():
        manana = ahora.date() + timedelta(days=1)
        eventos_filtrados = [e for e in eventos_calendario 
                           if datetime.fromtimestamp(e["timestamp"]).date() == manana]
        prefijo = "mañana"
    elif "semana" in texto.lower():
        fin_semana = ahora + timedelta(days=7)
        eventos_filtrados = [e for e in eventos_calendario 
                           if ahora.timestamp() <= e["timestamp"] <= fin_semana.timestamp()]
        prefijo = "esta semana"
    else:
        eventos_filtrados = [e for e in eventos_calendario 
                           if e["timestamp"] >= ahora.timestamp()]
        prefijo = "próximos"
    
    if not eventos_filtrados:
        return f"no tienes eventos {prefijo}"
    
    respuesta = f"eventos {prefijo}:\n"
    for i, evento in enumerate(eventos_filtrados[:5], 1):
        fecha = datetime.fromtimestamp(evento["timestamp"])
        fecha_str = fecha.strftime("%d/%m %H:%M")
        respuesta += f"{i}. {evento['descripcion']} - {fecha_str}\n"
    
    hablar(f"tienes {len(eventos_filtrados)} eventos {prefijo}")
    return respuesta.strip()

def eliminar_evento(texto):
    """Elimina un evento del calendario."""
    cargar_calendario()
    
    texto_limpio = re.sub(r'(elimina|borra|cancela|quita|evento)', '', texto, flags=re.IGNORECASE).strip()
    
    if not eventos_calendario:
        return "no hay eventos para eliminar"
    
    # Buscar evento por descripción
    for evento in eventos_calendario[:]:
        if texto_limpio.lower() in evento["descripcion"].lower():
            eventos_calendario.remove(evento)
            guardar_calendario()
            hablar(f"evento eliminado: {evento['descripcion']}")
            return f"evento eliminado: {evento['descripcion']}"
    
    return f"no encontré un evento que contenga '{texto_limpio}'"

# =============================================
# FUNCIONES DE SMART HOME BÁSICO
# =============================================

def controlar_dispositivo(texto):
    """
    Controla dispositivos smart home básicos.
    Soporta: luces, enchufes (simulación)
    """
    texto_lower = texto.lower()
    
    # Mapeo de dispositivos simulados
    dispositivos = {
        "luz": {"estado": False, "ubicacion": "sala"},
        "luces": {"estado": False, "ubicacion": "toda la casa"},
        "enchufe": {"estado": False, "ubicacion": "cocina"}
    }
    
    accion = None
    dispositivo = None
    
    # Detectar acción
    if any(word in texto_lower for word in ["enciende", "prende", "activa"]):
        accion = "encender"
    elif any(word in texto_lower for word in ["apaga", "desactiva", "corta"]):
        accion = "apagar"
    
    # Detectar dispositivo
    for disp in dispositivos:
        if disp in texto_lower:
            dispositivo = disp
            break
    
    if not accion or not dispositivo:
        return "SISTEMA: No entendí qué dispositivo controlar o qué acción realizar."
    
    # Simular control
    if accion == "encender":
        dispositivos[dispositivo]["estado"] = True
        ubicacion = dispositivos[dispositivo]["ubicacion"]
        hablar(f"{dispositivo} de {ubicacion} encendido")
        return f"DATOS_PARA_IA: {dispositivo} encendido en {ubicacion}."
    else:
        dispositivos[dispositivo]["estado"] = False
        ubicacion = dispositivos[dispositivo]["ubicacion"]
        hablar(f"{dispositivo} de {ubicacion} apagado")
        return f"DATOS_PARA_IA: {dispositivo} apagado en {ubicacion}."

# =============================================
# FUNCIÓN PRINCIPAL DE PROCESAMIENTO DE INTENCIONES (CORREGIDA)
# =============================================

def procesar_intencion(entrada_usuario):
    """
    Procesa la entrada del usuario y determina la intención.
    CORREGIDO: Ahora extrae correctamente los nombres de canciones.
    """
    entrada = entrada_usuario.lower().strip()
    
    print(f"📝 Procesando: '{entrada_usuario}'")
    
    # 1. MÚSICA - CORREGIDO
    if any(palabra in entrada for palabra in ["pon", "reproduce", "toca", "coloca", "musica", "música", "cancion", "canción"]):
        print("🎯 Intención detectada: musica")
        
        # Extraer el nombre de la canción usando la función mejorada
        nombre_cancion = extraer_nombre_cancion(entrada_usuario)
        
        print(f"🎵 Canción extraída: '{nombre_cancion}'")
        
        # Verificar si hay internet para música online
        if verificar_estado_red() and YTDLP_AVAILABLE:
            if nombre_cancion:
                return musica_online(nombre_cancion)
            else:
                return musica_online()  # Música por defecto
        else:
            if nombre_cancion:
                return musica_usb(nombre_cancion)
            else:
                return musica_usb()
    
    # 2. HORA
    elif any(palabra in entrada for palabra in ["hora", "qué hora", "que hora"]):
        print("🎯 Intención detectada: hora")
        return obtener_hora()
    
    # 3. FECHA
    elif any(palabra in entrada for palabra in ["fecha", "qué día", "que dia", "día es hoy", "dia es hoy"]):
        print("🎯 Intención detectada: fecha")
        return obtener_fecha()
    
    # 4. ALARMA
    elif any(palabra in entrada for palabra in ["alarma", "despiértame", "despiertame"]):
        print("🎯 Intención detectada: alarma")
        return programar_alarma(entrada_usuario)
    
    # 5. RECORDATORIO
    elif any(palabra in entrada for palabra in ["recordatorio", "recuerdame", "recuérdame", "recordar"]):
        print("🎯 Intención detectada: recordatorio")
        return nota_tiempo(entrada_usuario)
    
    # 6. NOTAS
    elif any(palabra in entrada for palabra in ["toma nota", "guardar nota", "anota"]):
        print("🎯 Intención detectada: tomar nota")
        return tomar_nota(entrada_usuario)
    
    # 7. LEER NOTA
    elif any(palabra in entrada for palabra in ["lee la nota", "leer nota", "qué dice la nota", "que dice la nota", "dime la nota"]):
        print("🎯 Intención detectada: leer nota")
        return leer_nota()
    
    # 8. LISTA DE COMPRAS
    elif any(palabra in entrada for palabra in ["lista de compras", "lista del super", "lista super"]):
        print("🎯 Intención detectada: lista compras")
        if any(palabra in entrada for palabra in ["agrega", "añade", "pon"]):
            return agregar_a_lista(entrada_usuario)
        elif any(palabra in entrada for palabra in ["quita", "elimina", "borra"]):
            return quitar_de_lista(entrada_usuario)
        elif "limpiar" in entrada or "vaciar" in entrada:
            return limpiar_lista()
        else:
            return leer_lista()
    
    # 9. CLIMA
    elif any(palabra in entrada for palabra in ["clima", "temperatura", "tiempo"]):
        print("🎯 Intención detectada: clima")
        if verificar_estado_red():
            # Extraer ciudad si se menciona
            ciudad = None
            palabras = entrada.split()
            for i, palabra in enumerate(palabras):
                if palabra in ["en", "de", "para"] and i+1 < len(palabras):
                    ciudad = palabras[i+1]
                    break
            return obtener_clima(ciudad)
        else:
            return "no hay conexión a internet para obtener el clima"
    
    # 10. TRADUCCIÓN
    elif any(palabra in entrada for palabra in ["traduce", "qué significa", "que significa", "en ingles", "en inglés"]):
        print("🎯 Intención detectada: traducción")
        return traductor_ingles(entrada_usuario)
    
    # 11. INVESTIGAR
    elif any(palabra in entrada for palabra in ["investiga", "busca información", "que es", "qué es"]):
        print("🎯 Intención detectada: investigar")
        if verificar_estado_red():
            tema = entrada.replace("investiga", "").replace("busca información", "").strip()
            return investigar_tema(tema)
        else:
            return "no hay conexión a internet para investigar"
    
    # 12. CALENDARIO / AGENDA
    elif any(palabra in entrada for palabra in ["agenda", "evento", "cita", "recordatorio calendario"]):
        print("🎯 Intención detectada: calendario")
        if "agrega" in entrada or "nuevo" in entrada or "programa" in entrada:
            return agregar_evento(entrada_usuario)
        elif "elimina" in entrada or "borra" in entrada or "cancela" in entrada:
            return eliminar_evento(entrada_usuario)
        else:
            return consultar_agenda(entrada_usuario)
    
    # 13. SMART HOME
    elif any(palabra in entrada for palabra in ["luz", "luces", "enchufe", "prende", "apaga"]):
        print("🎯 Intención detectada: smart home")
        return controlar_dispositivo(entrada_usuario)
    
    # 14. DETENER MÚSICA
    elif any(palabra in entrada for palabra in ["detener", "para", "deten", "stop", "silencia"]):
        print("🎯 Intención detectada: detener música")
        return detener()
    
    # 15. CONVERSACIÓN GENERAL (usar IA)
    else:
        print("🎯 Intención detectada: conversación general")
        return conversacion_ai(entrada_usuario)

# =============================================
# BUCLE PRINCIPAL
# =============================================

def main():
    """Función principal del asistente."""
    global musica_detener
    
    print("\n" + "="*50)
    print("🎤 NOVA - Asistente Inteligente")
    print("="*50)
    print("Comandos disponibles:")
    print("  • Música: 'pon [canción]' - Reproduce música (USB o internet)")
    print("  • Hora: 'qué hora es'")
    print("  • Fecha: 'qué fecha es'")
    print("  • Alarma: 'alarma en 5 minutos'")
    print("  • Recordatorio: 'recuerdame algo en 10 minutos'")
    print("  • Notas: 'toma nota...', 'lee la nota'")
    print("  • Lista compras: 'agrega leche a la lista', 'lee la lista'")
    print("  • Clima: 'clima en [ciudad]'")
    print("  • Traducción: 'qué significa [palabra] en inglés'")
    print("  • Calendario: 'agenda cita mañana', 'qué eventos tengo'")
    print("  • Smart home: 'prende la luz', 'apaga el enchufe'")
    print("  • Detener: 'detener música'")
    print("  • Salir: 'salir' o 'exit'")
    print("="*50)
    
    hablar(f"Hola {obtener_nombre_usuario()}, soy Nova. ¿En qué puedo ayudarte?")
    
    while True:
        try:
            # Entrada del usuario
            entrada = input("\n👤 Tú: ").strip()
            
            if not entrada:
                continue
            
            # Comando para salir
            if entrada.lower() in ["salir", "exit", "quit", "adiós", "adios"]:
                hablar("Hasta luego, que tengas un buen día")
                print("👋 Saliendo...")
                break
            
            # Procesar intención
            respuesta = procesar_intencion(entrada)
            
            # Mostrar respuesta
            if respuesta and not respuesta.startswith("DATOS_PARA_IA"):
                # Limpiar marcadores especiales si los hay
                respuesta_limpia = respuesta.replace("DATOS_PARA_IA:", "").strip()
                if respuesta_limpia:
                    print(f"🤖 Nova: {respuesta_limpia}")
                    # No volver a hablar si ya se habló en la función
                    if not any(func in respuesta for func in ["reproduciendo", "agregué", "eliminé", "evento agendado"]):
                        hablar(respuesta_limpia)
            elif respuesta and respuesta.startswith("DATOS_PARA_IA:"):
                # Las respuestas de clima/investigar se procesan con IA
                respuesta_ia = conversacion_ai(respuesta)
                print(f"🤖 Nova: {respuesta_ia}")
                hablar(respuesta_ia)
            elif respuesta:
                print(f"🤖 Nova: {respuesta}")
                hablar(respuesta)
            
        except KeyboardInterrupt:
            print("\n👋 Interrupción detectada. Saliendo...")
            break
        except Exception as e:
            print(f"❌ Error inesperado: {e}")
            hablar("Ocurrió un error inesperado")

if __name__ == "__main__":
    main()
# === CÓDIGO DE EXPORTACIÓN PARA BINARIO ===
if __name__ == "__main__":
    import sys
    import json
    
    if "--export-funciones" in sys.argv:
        # Extraer todas las funciones definidas
        funciones = {}
        for name, obj in list(globals().items()):
            if callable(obj) and not name.startswith("_"):
                try:
                    import inspect
                    funciones[name] = inspect.getsource(obj)
                except:
                    pass
        print(json.dumps(funciones))
        sys.exit(0)


# === AUTO-EXPORTACIÓN PARA BINARIO ===
if __name__ == "__main__":
    import sys
    import json
    
    if "--list-funciones" in sys.argv:
        # Listar todas las funciones disponibles
        funciones = [name for name, obj in globals().items() 
                    if callable(obj) and not name.startswith("_")]
        print(json.dumps(funciones))
        sys.exit(0)
    
    elif "--call" in sys.argv:
        # Ejecutar una función específica
        idx = sys.argv.index("--call")
        if idx + 1 < len(sys.argv):
            func_name = sys.argv[idx + 1]
            args = sys.argv[idx + 2:] if idx + 2 < len(sys.argv) else []
            if func_name in globals() and callable(globals()[func_name]):
                resultado = globals()[func_name](*args)
                print(resultado)
        sys.exit(0)
