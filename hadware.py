import local_libs
import local_libs
import os
import time
import threading

# ---------------------------------
# DETECTAR SI ES RASPBERRY PI
# ---------------------------------

PI_AVAILABLE = False

try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    PI_AVAILABLE = True
    print("GPIO activo (Raspberry Pi)")
except Exception:
    PI_AVAILABLE = False
    print("GPIO desactivado (modo PC)")


# ---------------------------------
# SI NO HAY PI, DESACTIVAR HARDWARE
# ---------------------------------

if not PI_AVAILABLE:

    def iniciar_hardware():
        print("Hardware desactivado porque no es Raspberry Pi")
    
    def enviar_señal_wake():
        """Stub: no hace nada en PC"""
        pass
    
    def iniciar_procesamiento():
        """Stub: no hace nada en PC"""
        pass
    
    def terminar_procesamiento():
        """Stub: no hace nada en PC"""
        pass

else:

    # Pines de entrada (botones)
    PIN_APAGAR = 17
    PIN_SUSPENDER_AI = 27
    PIN_STOP_MUSICA = 22
    
    # Pines de salida (señales de estado)
    PIN_WAKE_DETECTADO = 5      # GPIO 5: Señal cuando se detecta wake
    PIN_PROCESANDO = 6          # GPIO 6: Señal cuando está procesando


    def monitor_botones():

        # Configurar pines de entrada
        GPIO.setup(PIN_APAGAR, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(PIN_SUSPENDER_AI, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(PIN_STOP_MUSICA, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        # Configurar pines de salida
        GPIO.setup(PIN_WAKE_DETECTADO, GPIO.OUT)
        GPIO.setup(PIN_PROCESANDO, GPIO.OUT)
        
        # Asegurar que estén apagados al inicio
        GPIO.output(PIN_WAKE_DETECTADO, GPIO.LOW)
        GPIO.output(PIN_PROCESANDO, GPIO.LOW)

        print("Sistema de botones iniciado")

        while True:

            if GPIO.input(PIN_APAGAR) == GPIO.LOW:
                os.system("shutdown now")

            if GPIO.input(PIN_SUSPENDER_AI) == GPIO.LOW:
                os.system("pkill -f uvicorn")

            if GPIO.input(PIN_STOP_MUSICA) == GPIO.LOW:
                try:
                    import pygame
                    pygame.mixer.music.stop()
                except:
                    pass

            time.sleep(0.2)


    def enviar_señal_wake():
        """Enciende GPIO 5 para indicar que se detectó wake"""
        try:
            GPIO.output(PIN_WAKE_DETECTADO, GPIO.HIGH)
            time.sleep(0.5)  # Mantener la señal por 500ms
            GPIO.output(PIN_WAKE_DETECTADO, GPIO.LOW)
        except Exception as e:
            print(f"⚠️ Error enviando señal wake: {e}")
    
    def iniciar_procesamiento():
        """Enciende GPIO 6 para indicar que está procesando"""
        try:
            GPIO.output(PIN_PROCESANDO, GPIO.HIGH)
        except Exception as e:
            print(f"⚠️ Error iniciando GPIO procesamiento: {e}")
    
    def terminar_procesamiento():
        """Apaga GPIO 6 al terminar el procesamiento"""
        try:
            GPIO.output(PIN_PROCESANDO, GPIO.LOW)
        except Exception as e:
            print(f"⚠️ Error terminando GPIO procesamiento: {e}")

    def iniciar_hardware():

        hilo = threading.Thread(
            target=monitor_botones,
            daemon=True
        )

        hilo.start()

if __name__ == "__main__":

    iniciar_hardware()

    while True:
        time.sleep(1)
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
