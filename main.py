import local_libs
import os
import sys
import json
import uvicorn
import anyio
import time
import shutil
import atexit
import signal
from typing import Optional, List
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Importar hardware si está disponible
try:
    from hadware import *
    from hadware import enviar_señal_wake, iniciar_procesamiento, terminar_procesamiento
    HARDWARE_DISPONIBLE = True
except ImportError:
    HARDWARE_DISPONIBLE = False
    def enviar_señal_wake(): pass
    def iniciar_procesamiento(): pass
    def terminar_procesamiento(): pass

# =============================================
# FUNCIONES DE LIMPIEZA DE ARCHIVOS TEMPORALES
# =============================================

def limpiar_archivos_temporales():
    """Limpia todos los archivos temporales en tmp/"""
    try:
        tmp_dir = "tmp"
        if os.path.exists(tmp_dir):
            archivos_eliminados = 0
            for archivo in os.listdir(tmp_dir):
                ruta_archivo = os.path.join(tmp_dir, archivo)
                try:
                    if os.path.isfile(ruta_archivo):
                        os.remove(ruta_archivo)
                        archivos_eliminados += 1
                    elif os.path.isdir(ruta_archivo):
                        shutil.rmtree(ruta_archivo)
                        archivos_eliminados += 1
                except Exception as e:
                    print(f"⚠️ No se pudo eliminar {archivo}: {e}")
            
            if archivos_eliminados > 0:
                print(f"✅ Limpiados {archivos_eliminados} archivos temporales")
    except Exception as e:
        print(f"⚠️ Error limpiando temporales: {e}")

def limpiar_archivos_audio():
    """Limpia archivos de audio temporales específicos"""
    archivos_audio = [
        "tmp/voz_temporal.mp3",
        "tmp/audio_temporal.mp3",
        "tmp/stream_temp.mp3",
        "tmp/respuesta_audio.mp3",
        "tmp/youtube_audio_temp.mp3"
    ]
    
    for archivo in archivos_audio:
        try:
            if os.path.exists(archivo):
                os.remove(archivo)
        except:
            pass
    
    try:
        if os.path.exists("tmp"):
            for archivo in os.listdir("tmp"):
                if archivo.endswith(('.mp3', '.wav', '.ogg', '.mp4', '.tmp')):
                    ruta = os.path.join("tmp", archivo)
                    try:
                        os.remove(ruta)
                    except:
                        pass
    except:
        pass

def limpieza_completa():
    """Ejecuta limpieza completa de todos los archivos temporales"""
    limpiar_archivos_audio()
    limpiar_archivos_temporales()

def signal_handler(sig, frame):
    """Manejador para Ctrl+C y otras señales"""
    print("\n\n🛑 Señal de interrupción recibida")
    limpieza_completa()
    print("👋 Servidor API cerrado correctamente")
    sys.exit(0)

# Registrar manejadores de señales
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
atexit.register(limpieza_completa)

# =============================================
# CONFIGURACIÓN
# =============================================

JSON_PAD = "sistemprot.json"

def cargar_configuracion(archivo_path=JSON_PAD):
    """Carga la configuración del sistema."""
    if not os.path.exists(archivo_path):
        config_inicial = {
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
        with open(archivo_path, 'w', encoding='utf-8') as f:
            json.dump(config_inicial, f, indent=2, ensure_ascii=False)
        return config_inicial
    
    with open(archivo_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# Carga inicial de configuración
config = cargar_configuracion()

# Intentamos importar las funciones de lógica y procesamiento externas
try:
    from ifs import procesar_logica_usuario
    print("✅ Funciones importadas correctamente desde ifs.py")
except ImportError as e:
    print(f"❌ Error al importar desde ifs.py: {e}")
    def procesar_logica_usuario(prompt):
        return f"Procesando: {prompt}"

# Intentar importar voz para respuestas por voz
try:
    from voz import hablar
    VOZ_DISPONIBLE = True
except:
    VOZ_DISPONIBLE = False
    def hablar(mensaje):
        print(f"[Voz]: {mensaje}")

# =============================================
# FASTAPI APP
# =============================================

app = FastAPI(
    title="Nova API",
    description="API del asistente inteligente Nova Alfa",
    version="1.0.0"
)

# =============================================
# MODELOS DE DATOS
# =============================================

class CompletionRequest(BaseModel):
    prompt: str
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    stop: List[str] = []
    stream: bool = False

class ChatRequest(BaseModel):
    texto: str
    modo: str = "texto"  # "texto" o "voz"

class WakeDetection(BaseModel):
    activado: bool
    confianza: float = 0.0

# =============================================
# FUNCIONES AUXILIARES
# =============================================

async def generate_stream(respuesta):
    """Generador que envía la respuesta en streaming."""
    yield f"data: {json.dumps({'choices': [{'text': respuesta}]})}\n\n"
    yield "data: [DONE]\n\n"

def procesar_chat(texto: str, modo: str = "texto") -> str:
    """Procesa el chat a través del sistema de intenciones"""
    try:
        print(f"📝 Procesando: {texto[:100]}...")
        
        # Enviar señal de procesamiento a hardware
        try:
            iniciar_procesamiento()
        except:
            pass
        
        # Procesar con la lógica existente de ifs.py
        resultado = procesar_logica_usuario(texto)
        
        # Si es modo voz y hay voz disponible, hablar la respuesta
        if modo == "voz" and resultado and VOZ_DISPONIBLE:
            try:
                hablar(resultado)
            except Exception as e:
                print(f"⚠️ Error al hablar: {e}")
        
        # Enviar señal de término a hardware
        try:
            terminar_procesamiento()
        except:
            pass
        
        return resultado
        
    except Exception as e:
        print(f"❌ Error procesando chat: {e}")
        return f"Error al procesar tu solicitud: {str(e)}"

# =============================================
# ENDPOINTS DE LA API
# =============================================

@app.on_event("startup")
async def startup_event():
    """Evento que se ejecuta al iniciar el servidor"""
    print("\n🚀 Servidor Nova API iniciado")
    if HARDWARE_DISPONIBLE:
        try:
            enviar_señal_wake()
        except:
            pass

@app.on_event("shutdown")
async def shutdown_event():
    """Evento que se ejecuta al cerrar el servidor"""
    print("\n🛑 Cerrando servidor Nova API...")

@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "nombre": "Nova API",
        "version": "1.0.0",
        "estado": "activo",
        "endpoints": [
            "/",
            "/health",
            "/status",
            "/chat",
            "/v1/completions",
            "/wake_detected"
        ]
    }

@app.get("/health")
async def health_check():
    """Endpoint de salud del sistema"""
    return {
        "status": "ok",
        "service": "Nova API",
        "timestamp": time.time()
    }

@app.get("/status")
async def system_status():
    """Endpoint para obtener estado completo del sistema"""
    return {
        "servidor": "activo",
        "config": {
            "temperature": config["parametros_modelo"]["temperature"],
            "max_tokens": config["parametros_modelo"]["max_tokens"],
            "top_p": config["parametros_modelo"]["top_p"],
            "n_ctx": config["parametros_modelo"]["n_ctx"]
        },
        "hardware": HARDWARE_DISPONIBLE,
        "voz": VOZ_DISPONIBLE
    }

@app.post("/chat")
async def chat(request: ChatRequest):
    """Endpoint principal para procesar mensajes de chat"""
    try:
        print(f"\n💬 Chat recibido - Modo: {request.modo}")
        print(f"   Texto: {request.texto[:100]}...")
        
        resultado = await anyio.to_thread.run_sync(
            procesar_chat, request.texto, request.modo
        )
        
        return {
            "respuesta": resultado,
            "modo": request.modo,
            "status": "success"
        }
        
    except Exception as e:
        print(f"❌ Error en /chat: {e}")
        return {
            "error": str(e),
            "status": "error"
        }

@app.post("/v1/completions")
async def completions(request: CompletionRequest):
    """Endpoint compatible con OpenAI para completions"""
    try:
        prompt = request.prompt
        stream = request.stream
        
        print(f"\n📨 Recibida petición de completions: {prompt[:100]}...")
        
        resultado = await anyio.to_thread.run_sync(procesar_chat, prompt, "texto")
        
        if stream:
            return StreamingResponse(
                generate_stream(resultado), 
                media_type="text/event-stream"
            )
        else:
            return {
                "choices": [
                    {
                        "text": resultado,
                        "index": 0,
                        "finish_reason": "stop"
                    }
                ],
                "model": "nova-alfa"
            }
            
    except Exception as e:
        print(f"❌ Error en /v1/completions: {e}")
        return {"error": str(e)}

@app.post("/wake_detected")
async def wake_detected(detection: WakeDetection):
    """Endpoint que recibe notificaciones de wakeword"""
    if detection.activado:
        print(f"\n🔊 Notificación de wakeword recibida")
        print(f"   Confianza: {detection.confianza:.2f}")
    
    return {
        "status": "ok",
        "mensaje": "Notificación recibida"
    }

@app.get("/config")
async def get_config():
    """Obtiene la configuración actual"""
    return {
        "system_prompt": config.get("system_prompt", ""),
        "contexto_maestro": config.get("contexto_maestro", {}),
        "parametros_modelo": config.get("parametros_modelo", {})
    }

@app.post("/config")
async def update_config(config_data: dict):
    """Actualiza la configuración (solo algunos parámetros)"""
    global config
    
    try:
        if "temperature" in config_data:
            config["parametros_modelo"]["temperature"] = config_data["temperature"]
        
        if "max_tokens" in config_data:
            config["parametros_modelo"]["max_tokens"] = config_data["max_tokens"]
        
        if "top_p" in config_data:
            config["parametros_modelo"]["top_p"] = config_data["top_p"]
        
        # Guardar en archivo
        with open(JSON_PAD, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        return {
            "status": "success",
            "mensaje": "Configuración actualizada",
            "config": config["parametros_modelo"]
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

# =============================================
# INICIO DEL SERVIDOR
# =============================================

def inicializar_api():
    """Inicializa la API"""
    params = config["parametros_modelo"]
    print(f"\n--- Nova API ---")
    print(f"📊 Configuración del modelo:")
    print(f"   🌡️  Temperature: {params['temperature']}")
    print(f"   📝 Max Tokens: {params['max_tokens']}")
    print(f"   🎯 Top P: {params['top_p']}")
    print(f"   📚 Contexto: {params.get('n_ctx', 10000)} tokens")
    print(f"🎤 Voz disponible: {'✅' if VOZ_DISPONIBLE else '❌'}")
    print(f"🔌 Hardware: {'✅' if HARDWARE_DISPONIBLE else '❌'}")
    print("--- API Lista ---\n")

def iniciar_servidor(host="0.0.0.0", port=8000):
    """Inicia el servidor FastAPI"""
    uvicorn.run(
        app, 
        host=host, 
        port=port, 
        log_level="warning", 
        access_log=False
    )

if __name__ == "__main__":
    inicializar_api()
    
    print("🔄 Iniciando servidor API...")
    print("📍 Endpoints disponibles:")
    print("   GET  /            - Información general")
    print("   GET  /health      - Estado de salud")
    print("   GET  /status      - Estado detallado")
    print("   POST /chat        - Chat principal")
    print("   POST /v1/completions - Compatible con OpenAI")
    print("   POST /wake_detected - Notificación de wakeword")
    print("   GET  /config      - Ver configuración")
    print("   POST /config      - Actualizar configuración")
    
    print("\n🎤 Servidor API listo para recibir peticiones")
    print("   (Presiona Ctrl+C para salir)\n")
    
    try:
        iniciar_servidor()
    except KeyboardInterrupt:
        print("\n🛑 Servidor detenido por el usuario")
        limpieza_completa()
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        sys.exit(1)