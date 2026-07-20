#!/usr/bin/env python3
"""
Cliente de voz para Nova Assistant
Convierte voz a texto usando modelos locales y envía a la API
"""

import os
import sys
import time
import json
import argparse
import requests
import pyaudio
import wave
import numpy as np
import threading
import queue
from pathlib import Path
import tempfile

# ============================================
# IMPORTAR MODELOS DE VOZ A TEXTO
# ============================================

# Intentar importar whisper
try:
    import whisper
    WHISPER_AVAILABLE = True
    print("✅ Whisper cargado correctamente")
except ImportError:
    WHISPER_AVAILABLE = False
    print("⚠️ Whisper no instalado")

# Intentar importar faster-whisper
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
    print("✅ Faster-Whisper disponible")
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    print("⚠️ Faster-Whisper no instalado")

# Intentar importar Vosk
try:
    import vosk
    VOSK_AVAILABLE = True
    print("✅ Vosk disponible")
except ImportError:
    VOSK_AVAILABLE = False
    print("⚠️ Vosk no instalado")

# Intentar importar speech_recognition
try:
    import speech_recognition as sr
    SR_AVAILABLE = True
    print("✅ SpeechRecognition disponible")
except ImportError:
    SR_AVAILABLE = False
    print("⚠️ SpeechRecognition no instalado")

# Intentar importar voz para salida
try:
    import voz
    VOZ_AVAILABLE = True
except ImportError:
    VOZ_AVAILABLE = False

# ============================================
# CONFIGURACIÓN
# ============================================

class Config:
    API_URL = "http://localhost:8000/chat"
    SAMPLE_RATE = 16000
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    
    # Configuración del modelo
    MODEL_PATH = "model_es"
    WHISPER_MODEL = "small"  # tiny, base, small, medium, large
    VOSK_MODEL = "model_es"
    
    # Duración de grabación
    SILENCE_THRESHOLD = 0.005
    SILENCE_DURATION = 1.0  # segundos de silencio para detener
    MAX_DURATION = 10.0  # duración máxima de grabación
    MIN_DURATION = 1.0  # duración mínima para procesar
    
    # Umbral de confianza
    CONFIDENCE_THRESHOLD = 0.5

config = Config()

# ============================================
# DETECTOR DE SILENCIO
# ============================================

class SilenceDetector:
    """Detecta silencio en el audio"""
    
    def __init__(self, threshold=0.005, silence_duration=1.0):
        self.threshold = threshold
        self.silence_duration = silence_duration
        self.silence_start = None
        self.is_speaking = False
        self.energy_history = []
    
    def process_chunk(self, audio_chunk):
        """Procesa un chunk de audio y detecta silencio"""
        if len(audio_chunk) == 0:
            return False
        
        # Calcular energía
        if isinstance(audio_chunk, np.ndarray):
            energy = np.mean(np.abs(audio_chunk))
        else:
            audio_np = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32)
            energy = np.mean(np.abs(audio_np)) / 32768.0
        
        # Guardar historial
        self.energy_history.append(energy)
        if len(self.energy_history) > 10:
            self.energy_history.pop(0)
        
        # Energía promedio
        avg_energy = np.mean(self.energy_history) if self.energy_history else 0
        
        # Detectar si hay voz
        if energy > self.threshold or avg_energy > self.threshold:
            self.is_speaking = True
            self.silence_start = None
            return True
        else:
            if self.silence_start is None:
                self.silence_start = time.time()
            elif time.time() - self.silence_start > self.silence_duration:
                self.is_speaking = False
                return False
            return True

# ============================================
# TRANSCRIPCIÓN DE VOZ A TEXTO
# ============================================

class VoiceToText:
    """Convierte voz a texto usando modelos locales"""
    
    def __init__(self):
        self.model = None
        self.model_type = None
        self.audio_interface = None
        self.stream = None
        self.recording = False
        self.audio_queue = queue.Queue()
        self.result_callback = None
        
        # Cargar modelo
        self.cargar_modelo()
    
    def cargar_modelo(self):
        """Carga el modelo de voz a texto"""
        
        # 1. Intentar Vosk primero (ligero y rápido)
        if VOSK_AVAILABLE:
            try:
                model_path = os.path.join(config.MODEL_PATH, config.VOSK_MODEL)
                if os.path.exists(model_path):
                    self.model = vosk.Model(model_path)
                    self.model_type = "vosk"
                    print(f"✅ Modelo Vosk cargado desde: {model_path}")
                    return True
                else:
                    print(f"⚠️ Modelo Vosk no encontrado en: {model_path}")
            except Exception as e:
                print(f"⚠️ Error cargando Vosk: {e}")
        
        # 2. Intentar Faster-Whisper
        if FASTER_WHISPER_AVAILABLE:
            try:
                self.model = WhisperModel(
                    config.WHISPER_MODEL,
                    device="cpu",
                    compute_type="int8"
                )
                self.model_type = "faster_whisper"
                print(f"✅ Faster-Whisper cargado con modelo: {config.WHISPER_MODEL}")
                return True
            except Exception as e:
                print(f"⚠️ Error cargando Faster-Whisper: {e}")
        
        # 3. Intentar Whisper normal
        if WHISPER_AVAILABLE:
            try:
                self.model = whisper.load_model(config.WHISPER_MODEL)
                self.model_type = "whisper"
                print(f"✅ Whisper cargado con modelo: {config.WHISPER_MODEL}")
                return True
            except Exception as e:
                print(f"⚠️ Error cargando Whisper: {e}")
        
        # 4. Intentar SpeechRecognition (fallback)
        if SR_AVAILABLE:
            try:
                self.model = sr.Recognizer()
                self.model_type = "speech_recognition"
                print("✅ SpeechRecognition cargado")
                return True
            except Exception as e:
                print(f"⚠️ Error cargando SpeechRecognition: {e}")
        
        print("❌ No se pudo cargar ningún modelo de voz a texto")
        return False
    
    def transcribir_audio(self, audio_data, sample_rate=16000):
        """Transcribe audio a texto"""
        if self.model is None:
            return None, 0.0
        
        try:
            if self.model_type == "vosk":
                return self._transcribir_vosk(audio_data, sample_rate)
            elif self.model_type == "faster_whisper":
                return self._transcribir_faster_whisper(audio_data, sample_rate)
            elif self.model_type == "whisper":
                return self._transcribir_whisper(audio_data, sample_rate)
            elif self.model_type == "speech_recognition":
                return self._transcribir_sr(audio_data, sample_rate)
            else:
                return None, 0.0
        except Exception as e:
            print(f"❌ Error transcribiendo: {e}")
            return None, 0.0
    
    def _transcribir_vosk(self, audio_data, sample_rate):
        """Transcribe con Vosk"""
        try:
            rec = vosk.KaldiRecognizer(self.model, sample_rate)
            
            if isinstance(audio_data, np.ndarray):
                audio_bytes = (audio_data * 32767).astype(np.int16).tobytes()
            else:
                audio_bytes = audio_data
            
            if rec.AcceptWaveform(audio_bytes):
                result = json.loads(rec.Result())
                text = result.get("text", "")
                confidence = result.get("confidence", 0.0)
                return text if text else None, confidence
            else:
                # Obtener parcial
                partial = json.loads(rec.PartialResult())
                text = partial.get("partial", "")
                if text:
                    return text, 0.5
                return None, 0.0
        except Exception as e:
            print(f"⚠️ Error en Vosk: {e}")
            return None, 0.0
    
    def _transcribir_faster_whisper(self, audio_data, sample_rate):
        """Transcribe con Faster-Whisper"""
        try:
            if isinstance(audio_data, np.ndarray):
                audio = audio_data.astype(np.float32)
            else:
                audio = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            segments, info = self.model.transcribe(
                audio,
                beam_size=5,
                language="es",
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    threshold=0.5
                )
            )
            
            text = ""
            confidence = 0.0
            for segment in segments:
                text += segment.text + " "
                confidence = max(confidence, segment.avg_logprob)
            
            if text.strip():
                return text.strip(), float(confidence)
            return None, 0.0
        except Exception as e:
            print(f"⚠️ Error en Faster-Whisper: {e}")
            return None, 0.0
    
    def _transcribir_whisper(self, audio_data, sample_rate):
        """Transcribe con Whisper"""
        try:
            if isinstance(audio_data, np.ndarray):
                audio = audio_data.astype(np.float32)
            else:
                audio = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            result = self.model.transcribe(
                audio,
                language="es",
                fp16=False,
                task="transcribe"
            )
            
            text = result["text"].strip()
            confidence = result.get("segments", [{}])[0].get("confidence", 0.0)
            
            if text:
                return text, confidence
            return None, 0.0
        except Exception as e:
            print(f"⚠️ Error en Whisper: {e}")
            return None, 0.0
    
    def _transcribir_sr(self, audio_data, sample_rate):
        """Transcribe con SpeechRecognition"""
        try:
            if isinstance(audio_data, np.ndarray):
                audio_bytes = (audio_data * 32767).astype(np.int16).tobytes()
            else:
                audio_bytes = audio_data
            
            # Guardar temporalmente
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                with wave.open(f.name, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(audio_bytes)
                
                with sr.AudioFile(f.name) as source:
                    audio = self.model.record(source)
                    text = self.model.recognize_google(audio, language="es-ES")
                    return text, 0.8
            
        except sr.UnknownValueError:
            return None, 0.0
        except Exception as e:
            print(f"⚠️ Error en SpeechRecognition: {e}")
            return None, 0.0
    
    def grabar_audio(self, duracion=None):
        """Graba audio desde el micrófono"""
        try:
            self.audio_interface = pyaudio.PyAudio()
            
            # Abrir stream
            self.stream = self.audio_interface.open(
                format=config.FORMAT,
                channels=config.CHANNELS,
                rate=config.SAMPLE_RATE,
                input=True,
                frames_per_buffer=config.CHUNK
            )
            
            frames = []
            silence_detector = SilenceDetector(
                threshold=config.SILENCE_THRESHOLD,
                silence_duration=config.SILENCE_DURATION
            )
            
            start_time = time.time()
            max_duration = duracion or config.MAX_DURATION
            min_duration = config.MIN_DURATION
            
            print("🎤 Escuchando... (habla ahora)")
            
            while True:
                data = self.stream.read(config.CHUNK, exception_on_overflow=False)
                frames.append(data)
                
                # Convertir a numpy para análisis
                audio_np = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                
                # Detectar silencio
                has_voice = silence_detector.process_chunk(audio_np)
                
                elapsed = time.time() - start_time
                
                # Mostrar feedback visual
                if has_voice:
                    sys.stdout.write("\r🔊 Escuchando... " + "█" * int(20 * min(1, elapsed / max_duration)))
                else:
                    sys.stdout.write("\r🔇 Silencio...   " + "░" * int(20 * min(1, elapsed / max_duration)))
                sys.stdout.flush()
                
                # Condiciones de parada
                if not has_voice and elapsed > min_duration and silence_detector.is_speaking == False:
                    if len(frames) > 0:
                        print("\n✅ Detenido por silencio")
                        break
                
                if elapsed > max_duration:
                    print("\n⏰ Tiempo máximo alcanzado")
                    break
            
            # Cerrar stream
            self.stream.stop_stream()
            self.stream.close()
            self.audio_interface.terminate()
            
            # Convertir frames a numpy
            audio_data = np.frombuffer(b''.join(frames), dtype=np.int16).astype(np.float32) / 32768.0
            
            return audio_data
            
        except Exception as e:
            print(f"❌ Error grabando: {e}")
            if self.stream:
                self.stream.close()
            if self.audio_interface:
                self.audio_interface.terminate()
            return None

# ============================================
# CLIENTE NOVA
# ============================================

class NovaVoiceClient:
    """Cliente que conecta voz a texto con la API Nova"""
    
    def __init__(self, api_url=None):
        self.api_url = api_url or config.API_URL
        self.vtt = VoiceToText()
        self.modo_voz = True
        self.ejecutando = False
    
    def enviar_a_api(self, texto):
        """Envía el texto a la API de Nova"""
        if not texto or len(texto.strip()) == 0:
            return None
        
        try:
            print(f"\n📤 Enviando a API: {texto[:100]}...")
            
            payload = {
                "texto": texto,
                "modo": "voz" if self.modo_voz else "texto"
            }
            
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                respuesta = data.get("respuesta", "")
                print(f"\n📨 Respuesta: {respuesta}")
                
                # Hablar respuesta si está disponible
                if self.modo_voz and VOZ_AVAILABLE:
                    try:
                        voz.hablar(respuesta)
                    except:
                        print(f"\n🔊 (voz) {respuesta}")
                
                return respuesta
            else:
                print(f"❌ Error API: {response.status_code}")
                return None
                
        except requests.exceptions.ConnectionError:
            print("❌ Error: No se puede conectar a la API")
            print("   Asegúrate que el servidor está corriendo en:", self.api_url)
            return None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    def ciclo_principal(self):
        """Ciclo principal de escucha y procesamiento"""
        self.ejecutando = True
        
        print("\n" + "="*50)
        print("🎤 Nova Voice Client")
        print("="*50)
        print(f"📡 API: {self.api_url}")
        print(f"🧠 Modelo: {self.vtt.model_type}")
        print("="*50)
        
        if VOZ_AVAILABLE:
            try:
                voz.hablar("Asistente de voz listo")
            except:
                pass
        
        while self.ejecutando:
            try:
                # Grabar audio
                audio_data = self.vtt.grabar_audio()
                
                if audio_data is None or len(audio_data) < config.SAMPLE_RATE * 0.5:
                    print("⏳ Audio demasiado corto, esperando...")
                    continue
                
                # Transcribir
                print("\n📝 Transcribiendo...")
                texto, confianza = self.vtt.transcribir_audio(audio_data, config.SAMPLE_RATE)
                
                if texto and len(texto.strip()) > 0 and confianza > config.CONFIDENCE_THRESHOLD:
                    print(f"\n✅ Texto: {texto}")
                    print(f"📊 Confianza: {confianza:.2f}")
                    
                    # Enviar a API
                    respuesta = self.enviar_a_api(texto)
                    
                else:
                    if texto:
                        print(f"⚠️ Confianza baja ({confianza:.2f}), ignorando")
                    else:
                        print("⚠️ No se pudo transcribir el audio")
                
                # Pequeña pausa entre ciclos
                time.sleep(0.5)
                
            except KeyboardInterrupt:
                print("\n🛑 Deteniendo cliente...")
                break
            except Exception as e:
                print(f"❌ Error en ciclo: {e}")
                time.sleep(1)
    
    def detener(self):
        """Detiene el cliente"""
        self.ejecutando = False

# ============================================
# MODO DE UNA VEZ (para wakeword)
# ============================================

def modo_una_vez():
    """Modo de una sola vez para wakeword"""
    client = NovaVoiceClient()
    
    print("\n🎤 Escuchando una vez...")
    
    # Grabar audio
    audio_data = client.vtt.grabar_audio(duracion=5.0)
    
    if audio_data is None or len(audio_data) < config.SAMPLE_RATE * 0.3:
        print("⏳ Audio demasiado corto")
        return
    
    # Transcribir
    print("📝 Transcribiendo...")
    texto, confianza = client.vtt.transcribir_audio(audio_data, config.SAMPLE_RATE)
    
    if texto and len(texto.strip()) > 0 and confianza > config.CONFIDENCE_THRESHOLD:
        print(f"✅ Texto: {texto}")
        print(f"📊 Confianza: {confianza:.2f}")
        
        # Enviar a API
        respuesta = client.enviar_a_api(texto)
    else:
        print("⚠️ No se pudo transcribir el audio")

# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nova Voice Client")
    parser.add_argument("--modo", type=str, default="voz", 
                       choices=["voz", "texto", "una-vez"],
                       help="Modo de operación")
    parser.add_argument("--api", type=str, default=config.API_URL,
                       help="URL de la API")
    parser.add_argument("--modelo", type=str, default="small",
                       choices=["tiny", "base", "small", "medium", "large"],
                       help="Modelo de Whisper a usar")
    parser.add_argument("--silence", type=float, default=1.0,
                       help="Duración de silencio para detener (segundos)")
    parser.add_argument("--max-duration", type=float, default=10.0,
                       help="Duración máxima de grabación (segundos)")
    parser.add_argument("--threshold", type=float, default=0.005,
                       help="Umbral de energía para detección de voz")
    
    args = parser.parse_args()
    
    # Actualizar configuración
    config.API_URL = args.api
    config.WHISPER_MODEL = args.modelo
    config.SILENCE_DURATION = args.silence
    config.MAX_DURATION = args.max_duration
    config.SILENCE_THRESHOLD = args.threshold
    
    if args.modo == "una-vez":
        # Modo una vez (usado por wakeword)
        modo_una_vez()
    else:
        # Modo continuo
        client = NovaVoiceClient(api_url=args.api)
        client.modo_voz = (args.modo == "voz")
        
        try:
            client.ciclo_principal()
        except KeyboardInterrupt:
            print("\n👋 Cliente detenido")