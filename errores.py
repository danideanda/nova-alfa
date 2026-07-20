import local_libs
import local_libs
import os
import sys
import subprocess
import importlib.util
import socket

# ---------------------------------------------------------
# 1. COMPROBACIÓN DE HARDWARE (RASPBERRY PI)
# ---------------------------------------------------------

GPIO_disponible = False

try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO_disponible = True
    print("Estás en una Raspberry Pi ✅")
except (ImportError, RuntimeError):
    print("No estás en una Raspberry Pi o falta RPi.GPIO ❌")


# ---------------------------------------------------------
# 2. VERIFICACIÓN DE INTERNET
# ---------------------------------------------------------

def hay_internet():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False


# ---------------------------------------------------------
# 3. SISTEMA DE RESUCITACIÓN
# ---------------------------------------------------------

def verificar_y_reparar():

    librerias_proyecto = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "python-dotenv": "dotenv",
        "llama-cpp-python": "llama_cpp",
        "scikit-learn": "sklearn",
        "joblib": "joblib",
        "numpy": "numpy",
        "pygame": "pygame",
        "pyttsx3": "pyttsx3",
        "sounddevice": "sounddevice",
        "requests": "requests",
        "googletrans": "googletrans",
        "pyserial": "serial",
        "anyio": "anyio"
    }

    # Solo agregamos GPIO si estamos en Raspberry
    if GPIO_disponible:
        librerias_proyecto["RPi.GPIO"] = "RPi.GPIO"

    faltantes = []

    for pip_name, import_name in librerias_proyecto.items():

        if importlib.util.find_spec(import_name) is None:
            faltantes.append(pip_name)

    if not faltantes:
        print("✔ Todas las librerías están instaladas")
        return

    print("\n⚠️ Faltan librerías:")
    for lib in faltantes:
        print(" -", lib)

    if not hay_internet():
        print("\n❌ No hay conexión a internet. No se pueden instalar dependencias.")
        return

    print("\n🔄 Instalando dependencias faltantes...")

    try:

        subprocess.check_call([
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "pip"
        ])

        subprocess.check_call([
            sys.executable,
            "-m",
            "pip",
            "install",
            *faltantes
        ])

        print("\n✅ Reparación completada")

    except Exception as e:
        print("\n❌ Error durante instalación:", e)


# ---------------------------------------------------------
# 4. EJECUCIÓN AUTOMÁTICA
# ---------------------------------------------------------

verificar_y_reparar()
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
