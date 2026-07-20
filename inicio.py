import local_libs
import os
import sys
import subprocess
import time
import threading
import shutil
import urllib.request
import urllib.error
import socket
from pathlib import Path
from datetime import datetime
import json

# Configuración de Rutas
VERSION_FILE = "txt/version.txt"
STATUS_FILE = "txt/estado_inicio.txt"
NETWORK_STATUS_FILE = "txt/estado_de_red.txt"
PERSONALIZACION_FILE = "txt/personalizacion.txt"
BACKUP_DIR = "backup"
BINARY_NAME = "nova_alfa.bin"

# URLs para actualizaciones
VERSION_URL = "https://actualizaciones.netlify.app/descargas_alfa/vercion.txt"
BINARY_URL = "https://actualizaciones.netlify.app/descargas_alfa/nova_alfa.bin"

# Intervalos de tiempo (en segundos)
INTERVALO_RED = 600  # 10 minutos = 600 segundos
INTERVALO_ACTUALIZACION = 600  # 10 minutos = 600 segundos

# Directorios necesarios para el funcionamiento
DIRECTORIOS_NECESARIOS = [
    "txt",
    "modelos",
    "notas",
    "backup",
    "tmp",
    "listas",
    "calendario",
    "sonidos"
]

# Archivos de configuración necesarios
ARCHIVOS_CONFIGURACION = [
    "sistemprot.json",
    "txt/estado_inicio.txt",
    "txt/estado_de_red.txt",
    "txt/requisitos.txt",
    "txt/version.txt",
    "txt/personalizacion.txt"
]

DEFAULT_VERSION = "1.0.0"

# Variables globales
actualizacion_en_progreso = False
asistente_ejecutandose = False
proceso_servidor_api = None
proceso_wake_detector = None
ultima_verificacion_red = None
ultima_verificacion_actualizacion = None


def verificar_y_actualizar_red():
    """Verifica la conexión y actualiza el archivo de estado. Retorna True/False."""
    global ultima_verificacion_red
    ultima_verificacion_red = datetime.now()
    
    try:
        hay_internet = False
        try:
            socket.setdefaulttimeout(3)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
            hay_internet = True
        except socket.error:
            try:
                socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("1.1.1.1", 53))
                hay_internet = True
            except:
                hay_internet = False
        
        os.makedirs(os.path.dirname(NETWORK_STATUS_FILE), exist_ok=True)
        estado = "true" if hay_internet else "false"
        with open(NETWORK_STATUS_FILE, "w") as f:
            f.write(estado)
        
        if os.path.exists(PERSONALIZACION_FILE):
            try:
                with open(PERSONALIZACION_FILE, 'r', encoding='utf-8') as f:
                    datos = json.load(f)
                datos["internet"] = hay_internet
                datos["ultima_verificacion_red"] = datetime.now().isoformat()
                if datos.get("primera_vez", True) and hay_internet:
                    datos["primera_vez"] = False
                with open(PERSONALIZACION_FILE, 'w', encoding='utf-8') as f:
                    json.dump(datos, f, indent=2, ensure_ascii=False)
            except:
                pass
        
        return hay_internet
    except:
        return False


def hay_red():
    """Lee el estado de red actual desde archivo."""
    try:
        if os.path.exists(NETWORK_STATUS_FILE):
            with open(NETWORK_STATUS_FILE, "r") as f:
                return f.read().strip().lower() == "true"
        return False
    except:
        return False


def conectar_wifi(ssid, contrasena=None):
    """Intenta conectar a una red Wi-Fi en Linux usando nmcli (NetworkManager)."""
    try:
        print(f"🔌 Conectando a {ssid}...")
        
        resultado = subprocess.run(["which", "nmcli"], capture_output=True)
        if resultado.returncode != 0:
            print("❌ nmcli no encontrado. Instala NetworkManager:")
            print("   sudo apt-get install network-manager")
            return False
        
        if contrasena:
            subprocess.run(
                ["nmcli", "device", "wifi", "connect", ssid, "password", contrasena],
                capture_output=True, text=True, timeout=15
            )
        else:
            subprocess.run(
                ["nmcli", "device", "wifi", "connect", ssid],
                capture_output=True, text=True, timeout=15
            )
        
        print(f"✅ Intentando conectar a {ssid}...")
        time.sleep(3)
        
        resultado_check = subprocess.run(
            ["nmcli", "connection", "show", "--active"],
            capture_output=True, text=True
        )
        
        if ssid in resultado_check.stdout:
            print(f"✅ ¡Conectado a {ssid} exitosamente!")
            return verificar_y_actualizar_red()
        else:
            print(f"⚠️ No se pudo conectar a {ssid}")
            return False
            
    except subprocess.TimeoutExpired:
        print("⏱️ Tiempo agotado al intentar conectar")
        return False
    except Exception as e:
        print(f"❌ Error al conectar: {e}")
        return False


def verificar_y_conectar_red():
    """Verifica la red y si no hay, intenta conectar a una red Wi-Fi en Linux."""
    if verificar_y_actualizar_red():
        print("✅ Ya hay conexión a internet")
        return True
    
    print("⚠️ Sin conexión a internet")
    hablar("No se detecta conexión a internet. Intentando conectar a una red Wi-Fi")
    
    try:
        try:
            resultado = subprocess.run(
                ["nmcli", "device", "wifi", "list"],
                capture_output=True, text=True, timeout=10
            )
            if resultado.stdout:
                print("\n" + resultado.stdout)
            else:
                print("⚠️ No se encontraron redes Wi-Fi")
                return False
        except FileNotFoundError:
            print("❌ nmcli no encontrado. Instala NetworkManager:")
            print("   sudo apt-get install network-manager")
            return False
        
        hablar("¿Deseas conectarte a una red Wi-Fi?")
        respuesta = input("\n¿Deseas conectarte a una red Wi-Fi? (s/N): ").lower().strip()
        
        if respuesta not in ['s', 'si', 'sí', 'yes', 'y']:
            print("⚠️ Continuando sin conexión de internet")
            return False
        
        hablar("Por favor, ingresa el nombre de la red Wi-Fi a la que deseas conectarte")
        ssid = input("Nombre de la red Wi-Fi (SSID): ").strip()
        
        if not ssid:
            print("❌ No se ingresó un SSID válido")
            return False
        
        tiene_contrasena = input("¿Esta red tiene contraseña? (s/N): ").lower().strip()
        contrasena = None
        
        if tiene_contrasena in ['s', 'si', 'sí', 'yes', 'y']:
            contrasena = input("Contraseña: ")
        
        hablar(f"Conectando a {ssid}. Por favor, espera...")
        exito = conectar_wifi(ssid, contrasena)
        
        if exito:
            hablar(f"Conexión a {ssid} establecida exitosamente")
            return True
        else:
            hablar("No se pudo establecer la conexión. Verifica los datos e intenta de nuevo")
            return False
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def cargar_version():
    try:
        if os.path.exists(VERSION_FILE):
            version_str = Path(VERSION_FILE).read_text().strip()
            if version_str:
                return version_str
        return DEFAULT_VERSION
    except Exception as e:
        print(f"⚠️ Error al cargar versión: {e}")
        return DEFAULT_VERSION


def crear_version_file(version=None):
    try:
        os.makedirs(os.path.dirname(VERSION_FILE), exist_ok=True)
        if version is None:
            version = DEFAULT_VERSION
        with open(VERSION_FILE, "w") as f:
            f.write(version)
        return True
    except Exception as e:
        print(f"⚠️ Error al crear archivo de versión: {e}")
        return False


def crear_archivo_personalizacion():
    try:
        os.makedirs(os.path.dirname(PERSONALIZACION_FILE), exist_ok=True)
        
        if not os.path.exists(PERSONALIZACION_FILE):
            datos_personalizacion = {
                "nombre_usuario": "Usuario",
                "idioma": "es-MX",
                "voz_tipo": "normal",
                "ubicacion": {
                    "ciudad": "Desconocida",
                    "region": "Desconocida",
                    "pais": "Desconocido",
                    "lat": "",
                    "lon": ""
                },
                "preferencias": {
                    "musica_por_defecto": "usb",
                    "volumen": 80,
                    "brillo": 100
                },
                "internet": False,
                "primera_vez": True,
                "ultima_verificacion_red": datetime.now().isoformat(),
                "ultima_actualizacion": datetime.now().isoformat()
            }
            
            with open(PERSONALIZACION_FILE, 'w', encoding='utf-8') as f:
                json.dump(datos_personalizacion, f, indent=2, ensure_ascii=False)
            
            print("📄 Archivo de personalización creado: txt/personalizacion.txt")
            return True
        else:
            print("📄 Archivo de personalización ya existe, no se sobrescribe")
            return False
            
    except Exception as e:
        print(f"⚠️ Error al crear archivo de personalización: {e}")
        return False


version_str = cargar_version()


def hablar(mensaje):
    try:
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        selected_voice = False
        
        for voice in voices:
            if "spanish" in voice.name.lower() or "es_ES" in voice.id or "es_MX" in voice.id:
                engine.setProperty('voice', voice.id)
                selected_voice = True
                break
        
        engine.setProperty('rate', 160)
        engine.setProperty('volume', 1.0)
        
        if not selected_voice:
            print(f"⚠️ Voz en español no detectada, usando sistema predeterminado. Mensaje: {mensaje}")

        engine.say(mensaje)
        engine.runAndWait()
        engine.stop()
    except ImportError:
        print(f"🔈 Voz (Texto): {mensaje} [pyttsx3 no instalado]")
    except Exception as e:
        print(f"🔈 Voz (Texto): {mensaje} [Error de audio: {e}]")


def cargar_personalizacion():
    try:
        if os.path.exists(PERSONALIZACION_FILE):
            with open(PERSONALIZACION_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    except:
        return None


def obtener_version_remota():
    if not verificar_y_actualizar_red():
        return None
    
    try:
        req = urllib.request.Request(VERSION_URL)
        req.add_header('User-Agent', 'NovaAlfa-Updater/1.0')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            version_remota = response.read().decode('utf-8').strip()
            return version_remota
    except:
        return None


def comparar_versiones(v1, v2):
    try:
        v1_parts = [int(x) for x in v1.split('.')]
        v2_parts = [int(x) for x in v2.split('.')]
        
        while len(v1_parts) < 3:
            v1_parts.append(0)
        while len(v2_parts) < 3:
            v2_parts.append(0)
        
        for i in range(3):
            if v1_parts[i] > v2_parts[i]:
                return 1
            elif v1_parts[i] < v2_parts[i]:
                return -1
        return 0
    except:
        return 0


def verificar_actualizacion_disponible(silencioso=False):
    global ultima_verificacion_actualizacion
    ultima_verificacion_actualizacion = datetime.now()
    
    if not silencioso:
        print("\n🔍 Verificando actualizaciones...")
    
    if not verificar_y_actualizar_red():
        if not silencioso:
            print("⚠️ Sin conexión a internet. No se pueden verificar actualizaciones.")
        return False, None
    
    version_remota = obtener_version_remota()
    if not version_remota:
        if not silencioso:
            print("⚠️ No se pudo obtener la versión remota.")
        return False, None
    
    if not silencioso:
        print(f"📌 Versión local: {version_str}")
        print(f"🌐 Versión remota: {version_remota}")
    
    comparacion = comparar_versiones(version_remota, version_str)
    
    if comparacion > 0:
        if not silencioso:
            print(f"✨ Nueva versión disponible: {version_remota}")
        return True, version_remota
    else:
        if not silencioso:
            print("✅ Ya tienes la última versión.")
        return False, None


def descargar_actualizacion(version_nueva):
    if not verificar_y_actualizar_red():
        print("❌ Sin conexión a internet para descargar actualización")
        return False
    
    try:
        print(f"\n📥 Descargando Nova Alfa v{version_nueva}...")
        
        temp_file = f"{BINARY_NAME}.download"
        backup_file = f"{BINARY_NAME}.backup"
        
        def reportar_progreso(block_num, block_size, total_size):
            descargado = block_num * block_size
            if total_size > 0:
                porcentaje = min(100, int(descargado * 100 / total_size))
                print(f"\r   Progreso: {porcentaje}% ({descargado}/{total_size} bytes)", end='')
        
        urllib.request.urlretrieve(BINARY_URL, temp_file, reporthook=reportar_progreso)
        print("\n✅ Descarga completada")
        
        if os.path.getsize(temp_file) == 0:
            print("❌ Error: El archivo descargado está vacío")
            os.remove(temp_file)
            return False
        
        print("🔧 Preparando actualización...")
        
        if os.path.exists(BINARY_NAME):
            if os.path.exists(backup_file):
                os.remove(backup_file)
            shutil.copy2(BINARY_NAME, backup_file)
            print(f"💾 Backup creado: {backup_file}")
        
        if os.path.exists(BINARY_NAME):
            os.remove(BINARY_NAME)
        
        os.rename(temp_file, BINARY_NAME)
        
        if sys.platform != "win32":
            os.chmod(BINARY_NAME, 0o755)
        
        crear_version_file(version_nueva)
        
        print(f"✅ Nova Alfa actualizado a v{version_nueva}")
        return True
        
    except Exception as e:
        print(f"\n❌ Error durante la descarga: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return False


def detener_componentes():
    """Detiene todos los componentes secundarios"""
    global proceso_servidor_api, proceso_wake_detector, asistente_ejecutandose
    
    print("🛑 Deteniendo todos los componentes...")
    
    if proceso_servidor_api:
        try:
            proceso_servidor_api.terminate()
            proceso_servidor_api.wait(timeout=5)
            print("   ✅ Servidor API detenido")
        except:
            try:
                proceso_servidor_api.kill()
                print("   ⚠️ Servidor API forzado")
            except:
                pass
        proceso_servidor_api = None
    
    if proceso_wake_detector:
        try:
            proceso_wake_detector.terminate()
            proceso_wake_detector.wait(timeout=5)
            print("   ✅ Detector wakeword detenido")
        except:
            try:
                proceso_wake_detector.kill()
                print("   ⚠️ Detector wakeword forzado")
            except:
                pass
        proceso_wake_detector = None
    
    asistente_ejecutandose = False


def reiniciar_sistema():
    global actualizacion_en_progreso
    
    print("\n🔄 Reiniciando sistema con la nueva versión...")
    
    try:
        detener_componentes()
        
        binario_path = os.path.abspath(BINARY_NAME)
        
        if sys.platform == "win32":
            subprocess.Popen([binario_path], creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen([binario_path], start_new_session=True)
        
        print("👋 Cerrando versión anterior...")
        sys.exit(0)
        
    except Exception as e:
        print(f"❌ Error al reiniciar: {e}")
        return False


def proceso_actualizacion():
    global actualizacion_en_progreso
    
    if actualizacion_en_progreso:
        return False
    
    actualizacion_en_progreso = True
    
    try:
        if not verificar_y_actualizar_red():
            print("⚠️ Sin conexión a internet para actualizar")
            hablar("No hay conexión a internet para buscar actualizaciones")
            actualizacion_en_progreso = False
            return False
        
        hay_actualizacion, version_nueva = verificar_actualizacion_disponible()
        
        if not hay_actualizacion:
            actualizacion_en_progreso = False
            return False
        
        print(f"\n🚀 Iniciando actualización a v{version_nueva}...")
        hablar(f"Actualizando a la versión {version_nueva}")
        
        if not descargar_actualizacion(version_nueva):
            hablar("Error al descargar la actualización")
            actualizacion_en_progreso = False
            return False
        
        hablar("Actualización completada. Reiniciando sistema.")
        
        time.sleep(2)
        
        reiniciar_sistema()
        
        return True
        
    except Exception as e:
        print(f"❌ Error en proceso de actualización: {e}")
        actualizacion_en_progreso = False
        return False


def crear_directorios():
    directorios_creados = []
    for directorio in DIRECTORIOS_NECESARIOS:
        try:
            if not os.path.exists(directorio):
                os.makedirs(directorio, exist_ok=True)
                directorios_creados.append(directorio)
                print(f"📁 Directorio creado: {directorio}")
        except Exception as e:
            print(f"⚠️ Error al crear directorio {directorio}: {e}")
    
    crear_version_file()
    crear_archivo_personalizacion()
    
    return directorios_creados


def inicializar_archivos_configuracion():
    try:
        if not os.path.exists("sistemprot.json"):
            config_default = {
                "sistema": {
                    "nombre": "Nova Alfa",
                    "version": version_str,
                    "configuracion_inicial": True,
                    "auto_update": True,
                    "ultima_verificacion": datetime.now().isoformat()
                }
            }
            with open("sistemprot.json", "w") as f:
                json.dump(config_default, f, indent=2)
            print("📄 Archivo de configuración creado: sistemprot.json")
        
        if not os.path.exists("txt/requisitos.txt"):
            with open("txt/requisitos.txt", "w") as f:
                f.write("# Requisitos de Nova Alfa\n")
                f.write("pyttsx3\n")
                f.write("speechrecognition\n")
            print("📄 Archivo de requisitos creado: txt/requisitos.txt")
        
        if not os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "w") as f:
                f.write("false")
            print("📄 Archivo de estado creado: txt/estado_inicio.txt")
        
        crear_archivo_personalizacion()
        
        verificar_y_actualizar_red()
        print("📄 Archivo de estado de red creado: txt/estado_de_red.txt")
        
        return True
    except Exception as e:
        print(f"⚠️ Error al inicializar archivos de configuración: {e}")
        return False


def gestionar_primera_ejecucion():
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    
    es_primera_vez = not os.path.exists(STATUS_FILE)
    
    if not es_primera_vez:
        try:
            with open(STATUS_FILE, "r") as f:
                contenido = f.read().strip().lower()
                if contenido == "false":
                    es_primera_vez = True
        except:
            es_primera_vez = True
    
    return es_primera_vez


def ejecucion_inicial():
    print("\n🎉 PRIMERA EJECUCIÓN DETECTADA")
    print("═" * 50)
    
    print("\n📁 Creando estructura de directorios...")
    directorios_creados = crear_directorios()
    if directorios_creados:
        print(f"✅ {len(directorios_creados)} directorios creados")
    
    print("\n📄 Inicializando archivos de configuración...")
    inicializar_archivos_configuracion()
    
    print("\n🌐 Verificando conectividad...")
    hablar("configurando red")
    hay_red = verificar_y_conectar_red()
    if hay_red:
        print("✅ Conexión a internet detectada")
    else:
        print("⚠️ Sin conexión a internet, algunas funciones no estarán disponibles")
    
    print("\n👤 Configuración inicial del asistente...")
    try:
        hablar("¿Cuál es tu nombre?")
        nombre = input("¿Cuál es tu nombre? (Enter para 'Usuario'): ").strip()
        if not nombre:
            nombre = "Usuario"
        
        if os.path.exists(PERSONALIZACION_FILE):
            with open(PERSONALIZACION_FILE, 'r', encoding='utf-8') as f:
                datos = json.load(f)
            datos["nombre_usuario"] = nombre
            datos["primera_vez"] = True
            with open(PERSONALIZACION_FILE, 'w', encoding='utf-8') as f:
                json.dump(datos, f, indent=2, ensure_ascii=False)
            print(f"Nombre configurado: {nombre}")

    except:
        print("⚠️ No se pudo configurar el nombre, usando 'Usuario'")
    
    hablar(f"Hola {nombre}, soy Nova Alfa versión {version_str}. Estoy configurando todo por primera vez, esto tardara unos minutos.")
    
    try:
        with open(STATUS_FILE, "w") as f:
            f.write("true")
    except Exception as e:
        print(f"⚠️ Error al guardar estado: {e}")
    
    print("\n✅ Configuración inicial completada")
    print("═" * 50)


def ejecucion_normal():
    print(f"\n🌟 Nova Alfa v{version_str} - Iniciando...")
    print("═" * 50)
    
    nombre_usuario = "Usuario"
    try:
        if os.path.exists(PERSONALIZACION_FILE):
            with open(PERSONALIZACION_FILE, 'r', encoding='utf-8') as f:
                datos = json.load(f)
                nombre_usuario = datos.get("nombre_usuario", "Usuario")
    except:
        pass
    
    print("\n🌐 Verificando conectividad...")
    estado_anterior = hay_red()
    hay_red_ahora = verificar_y_actualizar_red()
    
    if hay_red_ahora:
        print("✅ Conexión a internet activa")
        if not estado_anterior:
            hablar("Conexión a internet restablecida")
    else:
        print("⚠️ Sin conexión a internet")
        if estado_anterior:
            hablar("Se perdió la conexión a internet")
        
        print("🔧 Intentando restaurar conexión...")
        if verificar_y_conectar_red():
            hay_red_ahora = True
    
    if hay_red_ahora:
        hay_actualizacion, version_nueva = verificar_actualizacion_disponible()
        if hay_actualizacion:
            print(f"\n✨ Actualización disponible: v{version_nueva}")
            respuesta = input("¿Deseas actualizar ahora? (s/N): ").lower().strip()
            if respuesta in ['s', 'si', 'sí', 'yes', 'y']:
                hilo_actualizacion = threading.Thread(target=proceso_actualizacion, daemon=True)
                hilo_actualizacion.start()
                hilo_actualizacion.join()
                if actualizacion_en_progreso:
                    return
    
    hablar(f"Iniciando Nova Alfa versión {version_str}")
    
    print("\n✅ Sistema listo")
    print("═" * 50)


def ejecutar_asistente():
    """Ejecuta el servidor API y el detector wakeword en paralelo"""
    global proceso_servidor_api, proceso_wake_detector, asistente_ejecutandose
    
    print("\n🚀 Iniciando Nova Alfa...")
    
    try:
        # Iniciar servidor API en segundo plano
        if os.path.exists("main.py"):
            print("📡 Iniciando servidor API en segundo plano...")
            proceso_servidor_api = subprocess.Popen(
                [sys.executable, "main.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            print("✅ Servidor API iniciado (main.py)")
        else:
            proceso_servidor_api = None
            print("⚠️ No se encuentra main.py, omitiendo servidor API")
        
        # Iniciar detector wakeword
        if os.path.exists("wake.py"):
            print("🎤 Iniciando detector de wakeword...")
            proceso_wake_detector = subprocess.Popen(
                [sys.executable, "wake.py", "--servidor"],
                stdout=None,  # Mostrar en consola
                stderr=None,  # Mostrar en consola
                text=True
            )
            print("✅ Detector wakeword iniciado (wake.py)")
            print("   🎙️  Di 'jarvis' o 'Ok jarvis' para activar")
        else:
            proceso_wake_detector = None
            print("⚠️ No se encuentra wake.py, omitiendo detector")
        
        asistente_ejecutandose = True
        
        # Función para monitorear salida del servidor API
        def monitorear_servidor():
            if proceso_servidor_api:
                try:
                    for line in iter(proceso_servidor_api.stdout.readline, ""):
                        if line:
                            print(f"[API] {line.strip()}")
                        if not asistente_ejecutandose:
                            break
                except:
                    pass
        
        # Iniciar hilo de monitoreo
        hilo_monitoreo = threading.Thread(target=monitorear_servidor, daemon=True)
        hilo_monitoreo.start()
        
        return True
        
    except Exception as e:
        print(f"❌ Error al ejecutar el asistente: {e}")
        asistente_ejecutandose = False
        return False


def verificar_red_periodico():
    """Verifica el estado de red cada 10 minutos"""
    global asistente_ejecutandose
    
    print(f"🕐 Monitoreo de red iniciado (cada {INTERVALO_RED // 60} minutos)")
    
    while asistente_ejecutandose and not actualizacion_en_progreso:
        try:
            for _ in range(INTERVALO_RED):
                if not asistente_ejecutandose or actualizacion_en_progreso:
                    break
                time.sleep(1)
            
            if not asistente_ejecutandose or actualizacion_en_progreso:
                break
            
            estado_anterior = hay_red()
            estado_actual = verificar_y_actualizar_red()
            
            hora_actual = datetime.now().strftime("%H:%M:%S")
            
            if estado_actual != estado_anterior:
                if estado_actual:
                    print(f"\n🌐 [{hora_actual}] Conexión a internet RESTABLECIDA")
                    hablar("La conexión a internet se ha restablecido")
                else:
                    print(f"\n🌐 [{hora_actual}] Conexión a internet PERDIDA")
                    hablar("Se ha perdido la conexión a internet")
            else:
                if estado_actual:
                    print(f"\n🌐 [{hora_actual}] Conexión a internet: ACTIVA ✅")
                else:
                    print(f"\n🌐 [{hora_actual}] Conexión a internet: INACTIVA ❌")
                    
        except Exception as e:
            print(f"⚠️ Error en monitoreo de red: {e}")
            time.sleep(60)


def monitoreo_actualizaciones_periodico():
    """Verifica actualizaciones cada 10 minutos"""
    global asistente_ejecutandose
    
    print(f"🕐 Monitoreo de actualizaciones iniciado (cada {INTERVALO_ACTUALIZACION // 60} minutos)")
    
    while asistente_ejecutandose and not actualizacion_en_progreso:
        try:
            for _ in range(INTERVALO_ACTUALIZACION):
                if not asistente_ejecutandose or actualizacion_en_progreso:
                    break
                time.sleep(1)
            
            if not asistente_ejecutandose or actualizacion_en_progreso:
                break
            
            if verificar_y_actualizar_red():
                hora_actual = datetime.now().strftime("%H:%M:%S")
                print(f"\n🔍 [{hora_actual}] Verificando actualizaciones automáticamente...")
                
                hay_actualizacion, version_nueva = verificar_actualizacion_disponible(silencioso=False)
                
                if hay_actualizacion:
                    print(f"\n✨ [{hora_actual}] ¡Nueva versión disponible: v{version_nueva}!")
                    hablar(f"Hay una nueva versión disponible: {version_nueva}. Actualizando automáticamente.")
                    
                    hilo_update = threading.Thread(target=proceso_actualizacion, daemon=True)
                    hilo_update.start()
                    hilo_update.join(timeout=300)
                    break
                else:
                    try:
                        if os.path.exists("sistemprot.json"):
                            with open("sistemprot.json", "r") as f:
                                config_data = json.load(f)
                            config_data["sistema"]["ultima_verificacion"] = datetime.now().isoformat()
                            with open("sistemprot.json", "w") as f:
                                json.dump(config_data, f, indent=2)
                    except:
                        pass
            else:
                pass
                    
        except Exception as e:
            print(f"⚠️ Error en monitoreo de actualizaciones: {e}")
            time.sleep(60)


def lanzar_sistema():
    global asistente_ejecutandose, actualizacion_en_progreso
    
    try:
        print("\n" + "═" * 50)
        print("🤖 NOVA ALFA - ASISTENTE INTELIGENTE")
        print("═" * 50)
        
        es_primera_vez = gestionar_primera_ejecucion()
        
        if es_primera_vez:
            ejecucion_inicial()
        else:
            ejecucion_normal()
        
        if actualizacion_en_progreso:
            return True
        
        if not ejecutar_asistente():
            print("❌ No se pudo iniciar el asistente")
            return False
        
        # Iniciar monitoreos
        hilo_monitoreo_red = threading.Thread(target=verificar_red_periodico, daemon=True)
        hilo_monitoreo_red.start()
        
        hilo_monitoreo_actualizaciones = threading.Thread(target=monitoreo_actualizaciones_periodico, daemon=True)
        hilo_monitoreo_actualizaciones.start()
        
        print(f"\n📊 MONITOREO ACTIVO:")
        print(f"   • Red: cada {INTERVALO_RED // 60} minutos")
        print(f"   • Actualizaciones: cada {INTERVALO_ACTUALIZACION // 60} minutos")
        print("═" * 50)
        print("\n🎤 Sistema listo! Di 'Nova' para activar")
        print("   Presiona Ctrl+C para salir\n")
        
        # Mantener el programa vivo
        while asistente_ejecutandose:
            # Verificar si los procesos siguen vivos
            if proceso_servidor_api and proceso_servidor_api.poll() is not None:
                print("\n⚠️ El servidor API se detuvo")
                asistente_ejecutandose = False
                break
            
            if proceso_wake_detector and proceso_wake_detector.poll() is not None:
                print("\n⚠️ El detector wakeword se detuvo")
                asistente_ejecutandose = False
                break
            
            time.sleep(1)
        
        return True
        
    except KeyboardInterrupt:
        print("\n\n🛑 Sistema detenido por el usuario")
        detener_componentes()
        return True
    except Exception as e:
        print(f"\n❌ Error en el sistema: {e}")
        detener_componentes()
        return False


def mostrar_estado_sistema():
    global ultima_verificacion_red, ultima_verificacion_actualizacion
    
    print("\n📊 ESTADO DEL SISTEMA")
    print("═" * 50)
    print(f"📌 Versión: {version_str}")
    print(f"🎯 Primera ejecución: {'Sí' if gestionar_primera_ejecucion() else 'No'}")
    
    hay_red_ahora = verificar_y_actualizar_red()
    print(f"🌐 Internet: {'✅ Conectado' if hay_red_ahora else '❌ Desconectado'}")
    
    if ultima_verificacion_red:
        print(f"🕐 Última verificación red: {ultima_verificacion_red.strftime('%H:%M:%S')}")
    if ultima_verificacion_actualizacion:
        print(f"🕐 Última verificación actualización: {ultima_verificacion_actualizacion.strftime('%H:%M:%S')}")
    
    print(f"\n⏱️ Intervalos de monitoreo:")
    print(f"   • Red: cada {INTERVALO_RED // 60} minutos")
    print(f"   • Actualizaciones: cada {INTERVALO_ACTUALIZACION // 60} minutos")
    
    print(f"\n🤖 Servidor API: {'✅ Corriendo' if proceso_servidor_api and proceso_servidor_api.poll() is None else '⏸️ Detenido'}")
    print(f"🎤 Detector Wakeword: {'✅ Corriendo' if proceso_wake_detector and proceso_wake_detector.poll() is None else '⏸️ Detenido'}")
    
    datos = cargar_personalizacion()
    if datos:
        print(f"👤 Usuario: {datos.get('nombre_usuario', 'Desconocido')}")
        print(f"📍 Ubicación: {datos.get('ubicacion', {}).get('ciudad', 'Desconocida')}")
    
    print("\n📁 Directorios:")
    for directorio in DIRECTORIOS_NECESARIOS:
        existe = os.path.exists(directorio)
        print(f"   {'✅' if existe else '❌'} {directorio}/")
    
    print("\n📄 Archivos de configuración:")
    for archivo in ARCHIVOS_CONFIGURACION:
        existe = os.path.exists(archivo)
        print(f"   {'✅' if existe else '❌'} {archivo}")
    
    print("═" * 50)


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            if sys.argv[1] in ["--help", "-h"]:
                print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    Nova Alfa v{version_str:<28} ║
╠══════════════════════════════════════════════════════════════╣
║  Comandos disponibles:                                        ║
║    --help     : Muestra esta ayuda                           ║
║    --status   : Muestra el estado del sistema                ║
║    --update   : Fuerza la búsqueda de actualizaciones        ║
║    --repair   : Repara la estructura del sistema             ║
║    --version  : Muestra la versión                           ║
╠══════════════════════════════════════════════════════════════╣
║  Monitoreo automático:                                        ║
║    • Red: Cada 10 minutos                                    ║
║    • Actualizaciones: Cada 10 minutos                        ║
╠══════════════════════════════════════════════════════════════╣
║  Funcionamiento:                                              ║
║    • Ejecuta main.py (servidor API) en segundo plano        ║
║    • Ejecuta wake.py (detector wakeword) visible            ║
║    • Monitoreo: Verifica red y actualizaciones cada 10 min   ║
║    • Actualizaciones automáticas desde servidor              ║
╚══════════════════════════════════════════════════════════════╝
                """)
                sys.exit(0)
            elif sys.argv[1] == "--status":
                mostrar_estado_sistema()
                sys.exit(0)
            elif sys.argv[1] == "--update":
                print("🔍 Forzando búsqueda de actualizaciones...")
                proceso_actualizacion()
                sys.exit(0)
            elif sys.argv[1] == "--repair":
                print("🔧 Reparando sistema...")
                crear_directorios()
                inicializar_archivos_configuracion()
                print("✅ Reparación completada")
                sys.exit(0)
            elif sys.argv[1] == "--version":
                print(f"Nova Alfa v{version_str}")
                sys.exit(0)
        
        resultado = lanzar_sistema()
        
        if resultado:
            print("\n👋 Nova Alfa cerrado correctamente")
        else:
            print("\n❌ Nova Alfa finalizó con errores")
            sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n\n🛑 Nova Alfa detenido por el usuario")
        detener_componentes()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        detener_componentes()
        sys.exit(1)