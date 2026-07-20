#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nova Assistant - Captura CONSTANTE de audio en fragmentos de 2 segundos
"""

import os
import sys
import json
import time
import threading
import signal
import atexit
import numpy as np
from collections import deque
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn
import anyio

# =============================================
# SILENCIAR MENSAGES MOLESTOS
# =============================================

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# =============================================
# IMPORTACIONES
# =============================================

try:
    import tensorflow as tf
    import librosa
    import sounddevice as sd
    TENSORFLOW_DISPONIBLE = True
except ImportError as e:
    TENSORFLOW_DISPONIBLE = False
    print(f"❌ Error imports: {e}")

try:
    from voz import hablar
except:
    def hablar(mensaje): pass

try:
    from ifs import procesar_logica_usuario
except:
    def procesar_logica_usuario(prompt): return f"Procesando: {prompt}"

try:
    from hadware import enviar_señal_wake, iniciar_procesamiento, terminar_procesamiento
except:
    def enviar_señal_wake(): pass
    def iniciar_procesamiento(): pass
    def terminar_procesamiento(): pass

# =============================================
# CONFIGURACIÓN
# =============================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELOS_DIR = os.path.join(BASE_DIR, "modelos")
WAKE_MODEL_PATH = os.path.join(MODELOS_DIR, "model.h5")
WAKE_CONFIG_PATH = os.path.join(MODELOS_DIR, "config.pkl")

SAMPLE_RATE = 16000
DURATION = 2.0  # 2 SEGUNDOS por fragmento
BUFFER_SIZE = 3  # Ventana de detección (últimas 3 lecturas)
ACTIVATION_SCORE = 300

# =============================================
# DETECTOR CON BUCLE CONSTANTE
# =============================================

class DetectorConstante:
    """Detector que CAPTURA AUDIO CONSTANTEMENTE en fragmentos de 2 segundos"""
    
    def __init__(self):
        self.model = None
        self.audio_processor = None
        self.activation_score = ACTIVATION_SCORE
        self.score_buffer = deque(maxlen=BUFFER_SIZE)
        self.capturando = True
        self.callback = None
        self.fragmentos_procesados = 0
        self._cargar_modelo()
    
    def _cargar_modelo(self):
        """Carga el modelo"""
        if not TENSORFLOW_DISPONIBLE:
            return False
        
        if not os.path.exists(WAKE_MODEL_PATH):
            return False
        
        try:
            self.model = tf.keras.models.load_model(WAKE_MODEL_PATH)
            
            import pickle
            if os.path.exists(WAKE_CONFIG_PATH):
                with open(WAKE_CONFIG_PATH, 'rb') as f:
                    config_data = pickle.load(f)
                    self.activation_score = config_data.get('activation_score', ACTIVATION_SCORE)
            
            self._init_audio_processor()
            return True
        except:
            return False
    
    def _init_audio_processor(self):
        """Procesador de audio"""
        class AudioProcessor:
            def __init__(self):
                self.target_length = int(SAMPLE_RATE * DURATION)
                self.n_mfcc = 40
                self.hop_length = 512
                self.n_fft = 2048
                self.feature_length = None
            
            def extract_features(self, audio):
                if len(audio) < self.target_length:
                    audio = np.pad(audio, (0, self.target_length - len(audio)))
                else:
                    audio = audio[:self.target_length]
                
                mfcc = librosa.feature.mfcc(
                    y=audio, sr=SAMPLE_RATE,
                    n_mfcc=self.n_mfcc,
                    n_fft=self.n_fft,
                    hop_length=self.hop_length
                )
                
                mfcc_delta = librosa.feature.delta(mfcc)
                mfcc_delta2 = librosa.feature.delta(mfcc, order=2)
                features = np.vstack([mfcc, mfcc_delta, mfcc_delta2]).T
                
                if self.feature_length is None:
                    self.feature_length = features.shape[0]
                elif features.shape[0] != self.feature_length:
                    if features.shape[0] > self.feature_length:
                        features = features[:self.feature_length, :]
                    else:
                        pad = self.feature_length - features.shape[0]
                        features = np.pad(features, ((0, pad), (0, 0)), mode='constant')
                
                return features
            
            def normalize(self, audio):
                if np.max(np.abs(audio)) > 0:
                    audio = audio / np.max(np.abs(audio))
                return audio
        
        self.audio_processor = AudioProcessor()
    
    def iniciar_bucle_constante(self, callback):
        """
        Bucle INFINITO que captura audio CONSTANTEMENTE
        Cada iteración = 2 segundos de audio
        """
        if not self.model:
            return False
        
        self.callback = callback
        
        def bucle_infinito():
            """Este bucle NUNCA se detiene mientras el programa corre"""
            print("\n" + "=" * 60)
            print("🎤 BUCLE CONSTANTE DE CAPTURA DE AUDIO")
            print(f"⚡ Fragmentos de {DURATION} segundos")
            print(f"🎯 Umbral de activación: {self.activation_score} puntos")
            print("=" * 60)
            
            while self.capturando:
                try:
                    # ==========================================
                    # 1. CAPTURAR AUDIO (2 segundos)
                    # ==========================================
                    audio = sd.rec(
                        int(DURATION * SAMPLE_RATE),
                        samplerate=SAMPLE_RATE,
                        channels=1,
                        dtype='float32'
                    )
                    sd.wait()  # Espera a que terminen los 2 segundos
                    audio = audio.flatten()
                    self.fragmentos_procesados += 1
                    
                    # ==========================================
                    # 2. PROCESAR AUDIO
                    # ==========================================
                    audio_norm = self.audio_processor.normalize(audio)
                    features = self.audio_processor.extract_features(audio_norm)
                    features = np.expand_dims(features, axis=0)
                    
                    # ==========================================
                    # 3. PREDECIR
                    # ==========================================
                    probabilidad = self.model.predict(features, verbose=0)[0][0]
                    puntuacion = probabilidad * 1000
                    
                    # ==========================================
                    # 4. VERIFICAR ENERGÍA (no silencio)
                    # ==========================================
                    energia = np.mean(audio ** 2)
                    
                    # ==========================================
                    # 5. VERIFICAR DURACIÓN DE VOZ
                    # ==========================================
                    es_voz = False
                    envelope = np.abs(audio)
                    if np.max(envelope) > 0:
                        umbral = 0.1 * np.max(envelope)
                        above = envelope > umbral
                        if np.any(above):
                            inicio = np.argmax(above)
                            fin = len(audio) - 1 - np.argmax(above[::-1])
                            duracion_voz = (fin - inicio) / SAMPLE_RATE
                            es_voz = 0.2 < duracion_voz < 1.2
                    
                    # ==========================================
                    # 6. DETECCIÓN CON BUFFER
                    # ==========================================
                    if energia > 0.0005 and puntuacion > self.activation_score and es_voz:
                        self.score_buffer.append(puntuacion)
                        
                        if len(self.score_buffer) >= BUFFER_SIZE:
                            altas = sum(1 for s in self.score_buffer if s > self.activation_score)
                            
                            if altas >= 2:  # Al menos 2 de 3 fragmentos
                                desviacion = np.std(list(self.score_buffer))
                                if desviacion < 150:  # Consistente
                                    # ✅ ACTIVAR!
                                    if self.callback:
                                        self.callback(puntuacion)
                                    time.sleep(1.5)  # Cooldown
                    
                    # Pequeña pausa para no saturar CPU
                    # (la grabación ya toma ~2 segundos, esto es mínimo)
                    time.sleep(0.01)
                    
                except Exception as e:
                    # Error silencioso, el bucle continúa
                    pass
            
            print("🛑 Bucle de captura detenido")
        
        # Iniciar el bucle en un hilo DAEMON
        hilo = threading.Thread(target=bucle_infinito, daemon=True)
        hilo.start()
        return True
    
    def detener(self):
        """Detiene el bucle"""
        self.capturando = False

# =============================================
# VARIABLES GLOBALES
# =============================================

detector = None
cliente_activo = False
ultima_activacion = 0
COOLDOWN = 2  # Segundos entre activaciones

# =============================================
# API FASTAPI
# =============================================

app = FastAPI(title="Nova API")

class ChatRequest(BaseModel):
    texto: str
    modo: str = "texto"

# =============================================
# FUNCIONES
# =============================================

def iniciar_cliente_voz():
    """Inicia el cliente de voz"""
    global cliente_activo
    
    if cliente_activo:
        return
    
    cliente_activo = True
    
    try:
        enviar_señal_wake()
    except:
        pass
    
    import subprocess
    if os.path.exists("cliente.py"):
        proceso = subprocess.Popen(
            [sys.executable, "cliente.py", "--modo", "voz", "--una-vez"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        def monitorear():
            global cliente_activo
            proceso.wait()
            cliente_activo = False
        
        threading.Thread(target=monitorear, daemon=True).start()

def procesar_chat(texto: str, modo: str = "texto") -> str:
    try:
        iniciar_procesamiento()
        resultado = procesar_logica_usuario(texto)
        if modo == "voz" and resultado:
            hablar(resultado)
        terminar_procesamiento()
        return resultado
    except:
        return "Error procesando"

def on_deteccion(puntuacion):
    """Callback cuando se detecta Nova"""
    global cliente_activo, ultima_activacion
    
    ahora = time.time()
    if ahora - ultima_activacion < COOLDOWN:
        return
    
    ultima_activacion = ahora
    
    if not cliente_activo:
        print(f"\n🔊 ¡NOVA DETECTADA! (puntuación: {puntuacion:.1f})")
        threading.Thread(target=iniciar_cliente_voz, daemon=True).start()

# =============================================
# ENDPOINTS
# =============================================

@app.on_event("startup")
async def startup_event():
    global detector
    
    print("\n" + "=" * 50)
    print("🎙️ NOVA - BUCLE CONSTANTE DE AUDIO")
    print("=" * 50)
    
    detector = DetectorConstante()
    
    if detector.model:
        detector.iniciar_bucle_constante(on_deteccion)
        print(f"✅ Bucle constante ACTIVADO")
        print(f"📊 Fragmentos: {DURATION} segundos")
        print(f"🎯 Umbral: {detector.activation_score} puntos")
    else:
        print("⚠️ Modelo no encontrado en modelos/")
        print("   Ejecuta entrenamiento primero")
    
    print("=" * 50)

@app.on_event("shutdown")
async def shutdown_event():
    if detector:
        detector.detener()

@app.post("/chat")
async def chat(request: ChatRequest):
    resultado = await anyio.to_thread.run_sync(procesar_chat, request.texto, request.modo)
    return {"respuesta": resultado, "modo": request.modo}

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "nombre": "Nova",
        "modelo_cargado": detector.model is not None if detector else False,
        "cliente_activo": cliente_activo,
        "fragmentos": detector.fragmentos_procesados if detector else 0
    }

# =============================================
# INICIO
# =============================================

if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("🎙️ NOVA - CAPTURA CONSTANTE")
    print("=" * 50)
    print("📍 API: http://localhost:8000")
    print("🎤 Di 'Nova' para activar")
    print("⚡ Capturando audio en fragmentos de 2 segundos")
    print("=" * 50)
    print("\n✨ INICIANDO...\n")
    
    try:
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
    except KeyboardInterrupt:
        print("\n👋 Nova cerrado")
    finally:
        if detector:
            detector.detener()