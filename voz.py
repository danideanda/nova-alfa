import local_libs
import local_libs
import os
import json
import asyncio
import subprocess
import re
import threading
import tempfile
from pathlib import Path

VOCES_EDGE_TTS = {
    "es": "es-ES-AlvaroNeural",
    "es_MX": "es-MX-JorgeNeural",
    "en": "en-US-AriaNeural",
    "pt": "pt-BR-BrendaNeural",
    "fr": "fr-FR-AlainNeural",
    "de": "de-DE-AmalaNeural",
    "it": "it-IT-IsabellaNeural",
}

# Variable global para el engine de pyttsx3
_tts_engine = None
_tts_lock = threading.Lock()


def verificar_pyttsx3():
    """Verifica si pyttsx3 funciona correctamente"""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        engine.stop()
        # Limpiar correctamente
        try:
            del engine
        except:
            pass
        return len(voices) > 0
    except Exception as e:
        print(f"⚠️ pyttsx3 no funciona: {e}")
        print("   Solución: instalar 'sudo apt-get install espeak-ng'")
        return False


def obtener_engine_tts():
    """Obtiene o crea el engine de pyttsx3 (singleton)"""
    global _tts_engine
    
    with _tts_lock:
        if _tts_engine is None:
            try:
                import pyttsx3
                _tts_engine = pyttsx3.init()
                _tts_engine.setProperty("rate", 160)
                _tts_engine.setProperty("volume", 1.0)
                
                # Configurar voz en español
                try:
                    voices = _tts_engine.getProperty('voices')
                    for voice in voices:
                        if "spanish" in voice.name.lower() or "es_" in voice.id.lower() or "es-" in voice.id.lower():
                            _tts_engine.setProperty('voice', voice.id)
                            break
                except:
                    pass
            except Exception as e:
                print(f"❌ Error inicializando pyttsx3: {e}")
                return None
    return _tts_engine


def limpiar_engine_tts():
    """Limpia el engine de pyttsx3 correctamente"""
    global _tts_engine
    
    with _tts_lock:
        if _tts_engine is not None:
            try:
                _tts_engine.stop()
            except:
                pass
            try:
                _tts_engine = None
            except:
                pass


def hablar_con_pyttsx3(mensaje):
    """Reproduce mensaje usando pyttsx3 (offline) con manejo robusto"""
    engine = None
    try:
        engine = obtener_engine_tts()
        if engine is None:
            return False
        
        # Si el mensaje es muy largo (> 300 caracteres), dividir
        if len(mensaje) > 300:
            # Dividir por oraciones
            oraciones = re.split(r'([.!?;:]+)', mensaje)
            frases = []
            for i in range(0, len(oraciones) - 1, 2):
                if i + 1 < len(oraciones):
                    frases.append(oraciones[i] + oraciones[i + 1])
            if len(oraciones) % 2 == 1:
                frases.append(oraciones[-1])
            
            # Reproducir cada frase
            for i, frase in enumerate(frases):
                if frase.strip():
                    engine.say(frase.strip())
                    engine.runAndWait()
                    if i < len(frases) - 1:
                        time.sleep(0.1)
        else:
            engine.say(mensaje)
            engine.runAndWait()
        
        print(f"🔈 Nova: {mensaje[:80]}{'...' if len(mensaje) > 80 else ''}")
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error en pyttsx3: {error_msg}")
        
        # Mensajes de ayuda específicos
        if "espeak" in error_msg.lower():
            print("   💡 SOLUCIÓN: Ejecuta 'sudo apt-get install espeak-ng'")
        
        # Si hay error, reiniciar el engine
        limpiar_engine_tts()
        return False


def hablar_con_edge_tts(mensaje, idioma):
    """Reproduce mensaje usando edge-tts (online)"""
    try:
        import edge_tts
        
        voz = VOCES_EDGE_TTS.get(idioma, VOCES_EDGE_TTS["es"])
        
        # Usar archivo temporal con contexto
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_file:
            archivo_mp3 = tmp_file.name
        
        async def generar():
            communicate = edge_tts.Communicate(mensaje, voz)
            await communicate.save(archivo_mp3)
        
        # Ejecutar la generación del audio
        asyncio.run(generar())
        
        if os.path.exists(archivo_mp3) and os.path.getsize(archivo_mp3) > 0:
            # Reproducir con ffplay o aplay/paplay
            try:
                # Intentar ffplay primero
                subprocess.run(
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", archivo_mp3],
                    check=False,
                    timeout=len(mensaje) * 0.1 + 5
                )
            except FileNotFoundError:
                # Si no hay ffplay, intentar con aplay (Linux)
                try:
                    subprocess.run(
                        ["aplay", "-q", archivo_mp3],
                        check=False,
                        timeout=len(mensaje) * 0.1 + 5
                    )
                except FileNotFoundError:
                    # Último intento con paplay (PulseAudio)
                    try:
                        subprocess.run(
                            ["paplay", archivo_mp3],
                            check=False,
                            timeout=len(mensaje) * 0.1 + 5
                        )
                    except:
                        print("⚠️ No se encontró reproductor de audio (ffplay, aplay o paplay)")
                        return False
            
            print(f"🔊 Nova: {mensaje[:80]}{'...' if len(mensaje) > 80 else ''}")
            
            # Limpiar archivo temporal
            try:
                os.unlink(archivo_mp3)
            except:
                pass
            return True
        else:
            print("⚠️ Archivo MP3 vacío o no generado")
            return False
            
    except ImportError:
        print("⚠️ edge_tts no instalado (pip install edge-tts)")
        return False
    except Exception as e:
        print(f"⚠️ Error en Edge TTS: {e}")
        return False


def hablar(mensaje):
    """Reproduce el mensaje - Edge TTS (online) o pyttsx3 (offline)"""
    
    if not mensaje or not mensaje.strip():
        return

    # Limpiar el mensaje
    mensaje = mensaje.strip()
    mensaje = mensaje.replace('\n', ' ')
    mensaje = re.sub(r'\s+', ' ', mensaje)

    # Leer configuración de idioma
    idioma = "es"
    try:
        if os.path.exists("txt/personalizacion.txt"):
            with open("txt/personalizacion.txt", "r", encoding="utf-8") as f:
                config = json.load(f)
                idioma = config.get("idioma", "es")
    except Exception as e:
        print(f"⚠️ Error leyendo personalizacion.txt: {e}")

    # Leer estado de red
    estado_red = True
    try:
        if os.path.exists("txt/estado_de_red.txt"):
            with open("txt/estado_de_red.txt", "r", encoding="utf-8") as f:
                estado_red = (f.read().strip().lower() == "true")
    except Exception:
        pass

    # Si el proceso indica que no debe reproducir audio (por ejemplo, servidor API), solo imprimir y no reproducir
    if os.getenv('NOVA_SILENCE_BACKEND', 'false').lower() in ('1', 'true', 'yes'):
        print(f"[SILENCED-VOZ] Nova: {mensaje}")
        return False

    # ==========================================
    # EDGE TTS: AUDIO COMPLETO (CON INTERNET)
    # ==========================================
    if estado_red:
        if hablar_con_edge_tts(mensaje, idioma):
            return

    # ==========================================
    # PYTTSX3 (OFFLINE) - COMO RESPALDO
    # ==========================================
    hablar_con_pyttsx3(mensaje)


def limpiar_recursos_voz():
    """Limpia todos los recursos de voz al cerrar el programa"""
    limpiar_engine_tts()


# Función para diagnosticar el sistema de voz
def diagnosticar_voz():
    """Diagnóstico completo del sistema de voz"""
    print("\n" + "=" * 50)
    print("🔍 DIAGNÓSTICO DEL SISTEMA DE VOZ")
    print("=" * 50)
    
    # Verificar pyttsx3
    print("\n1. Verificando pyttsx3:")
    if verificar_pyttsx3():
        print("   ✅ pyttsx3 funciona correctamente")
    else:
        print("   ❌ pyttsx3 NO funciona")
        print("   💡 Ejecuta: sudo apt-get install espeak-ng")
    
    # Verificar edge-tts
    print("\n2. Verificando edge-tts:")
    try:
        import edge_tts
        print("   ✅ edge-tts instalado")
    except ImportError:
        print("   ❌ edge-tts no instalado")
        print("   💡 Ejecuta: pip install edge-tts")
    
    # Verificar reproductores de audio
    print("\n3. Verificando reproductores de audio:")
    reproductores = ["ffplay", "aplay", "paplay"]
    for repro in reproductores:
        try:
            subprocess.run([repro, "--version"], capture_output=True, check=False)
            print(f"   ✅ {repro} disponible")
        except FileNotFoundError:
            print(f"   ❌ {repro} no disponible")
    
    # Verificar estado de red
    print("\n4. Estado de red:")
    estado_red = False
    try:
        if os.path.exists("txt/estado_de_red.txt"):
            with open("txt/estado_de_red.txt", "r") as f:
                estado_red = f.read().strip().lower() == "true"
        print(f"   {'✅ Conectado' if estado_red else '❌ Desconectado'}")
    except:
        print("   ❌ No se pudo leer estado de red")
    
    # Configuración de idioma
    print("\n5. Configuración de idioma:")
    try:
        if os.path.exists("txt/personalizacion.txt"):
            with open("txt/personalizacion.txt", "r") as f:
                config = json.load(f)
                idioma = config.get("idioma", "es")
                print(f"   📝 Idioma configurado: {idioma}")
                print(f"   🎤 Voz Edge TTS: {VOCES_EDGE_TTS.get(idioma, 'es-ES-AlvaroNeural')}")
    except:
        print("   ⚠️ No se pudo leer personalizacion.txt")
    
    print("\n" + "=" * 50)


if __name__ == "__main__":
    import time
    
    # Diagnóstico
    diagnosticar_voz()
    
    # Probar reproducción
    print("\n🎵 Probando reproducción de voz...")
    hablar("Hola, esta es una prueba del sistema de voz")
    time.sleep(1)
    hablar("Si escuchaste esto, el sistema funciona correctamente")
    
    # Limpiar recursos al salir
    limpiar_recursos_voz()
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
