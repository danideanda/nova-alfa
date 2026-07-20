#!/usr/bin/env python3
"""
Sistema de Wake Word Detection - Nova Assistant
MODO HIPER-SENSIBLE CON ANIMACIÓN RADAR
USANDO OPENWAKEWORD - VERSIÓN COMPATIBLE CON ANIMACIÓN
"""

import os
import sys
import time
import json
import argparse
import threading
import queue
import subprocess
import numpy as np
import pyaudio
from collections import deque
import voz
import shutil
import math

# ============================================
# IMPORTAR OPENWAKEWORD
# ============================================
try:
    from openwakeword.model import Model
    OPENWAKEWORD_AVAILABLE = True
    print("✅ OpenWakeWord cargado correctamente")
except ImportError:
    print("❌ OpenWakeWord no instalado. Ejecuta: pip install openwakeword")
    OPENWAKEWORD_AVAILABLE = False

# Intentar importar webrtcvad
try:
    import webrtcvad
    WEBRTC_VAD_AVAILABLE = True
    print("✅ WebRTC VAD disponible")
except ImportError:
    print("⚠️ WebRTC VAD no instalado (usando detección por energía)")
    WEBRTC_VAD_AVAILABLE = False

# ============================================
# CONFIGURACIÓN
# ============================================
voz.hablar("asistente jarvis iniciado")

class Config:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))
    
    SAMPLE_RATE = 16000
    CHUNK = int(SAMPLE_RATE * 0.02)
    
    BUFFER_SIZE = 2
    MIN_ACTIVACIONES = 1
    COOLDOWN_SEGUNDOS = 1.0
    
    VAD_AGGRESSIVENESS = 1
    ENERGY_THRESHOLD = 0.0005
    MIN_SPEECH_DURATION = 0.1
    MAX_SILENCE_DURATION = 0.3
    
    OWW_THRESHOLD = 0.30
    
config = Config()

# ============================================
# ANIMADOR VISUAL - RADAR/PULSO COMPLETO
# ============================================

class VisualAnimator:
    """Animación tipo radar/pulso para el detector"""
    
    # Colores ANSI
    COLORS = {
        'reset': '\033[0m',
        'bold': '\033[1m',
        'dim': '\033[2m',
        'red': '\033[38;5;196m',
        'orange': '\033[38;5;208m',
        'yellow': '\033[38;5;226m',
        'green': '\033[38;5;46m',
        'cyan': '\033[38;5;51m',
        'blue': '\033[38;5;33m',
        'purple': '\033[38;5;129m',
        'pink': '\033[38;5;206m',
        'white': '\033[38;5;255m',
        'gray': '\033[38;5;240m',
    }
    
    def __init__(self):
        self.terminal_width = shutil.get_terminal_size().columns
        self.terminal_height = shutil.get_terminal_size().lines
        self.frame = 0
        self.energy = 0
        self.prediction = 0
        self.threshold = 0.3
        self.is_speech = False
        self.is_detected = False
        self.is_processing = False
        self.last_detection_time = 0
        
        # Animación
        self.radar_angle = 0
        self.pulse_size = 0
        
        # Limpiar pantalla
        self.clear()
    
    def clear(self):
        """Limpia la pantalla"""
        sys.stdout.write('\033[2J\033[H')
        sys.stdout.flush()
    
    def _get_color_by_value(self, value, max_value=1.0):
        """Obtiene un color según el valor"""
        ratio = min(1.0, value / max_value)
        if ratio < 0.2:
            return self.COLORS['gray']
        elif ratio < 0.4:
            return self.COLORS['green']
        elif ratio < 0.6:
            return self.COLORS['cyan']
        elif ratio < 0.8:
            return self.COLORS['orange']
        else:
            return self.COLORS['red']
    
    def _draw_radar(self, energy, prediction):
        """Dibuja un radar/pulso animado"""
        # Actualizar ángulo del radar
        self.radar_angle = (self.radar_angle + 0.15) % (2 * math.pi)
        self.pulse_size = (self.pulse_size + 0.5) % 20
        
        # Tamaño del radar
        radar_size = 12
        center_x = radar_size
        center_y = radar_size // 2
        
        # Crear lienzo
        canvas = [[' ' for _ in range(radar_size * 2 + 4)] for _ in range(radar_size + 2)]
        
        # Dibujar círculos concéntricos
        for radius in range(3, radar_size, 3):
            color = self.COLORS['dim']
            for angle in np.linspace(0, 2*math.pi, 20):
                x = int(center_x + radius * math.cos(angle))
                y = int(center_y + radius * math.sin(angle) / 2)
                if 0 <= y < len(canvas) and 0 <= x < len(canvas[0]):
                    canvas[y][x] = f"{color}·{self.COLORS['reset']}"
        
        # Dibujar líneas de radar
        for angle in np.linspace(0, 2*math.pi, 6):
            x = int(center_x + radar_size * math.cos(angle))
            y = int(center_y + radar_size * math.sin(angle) / 2)
            color = self.COLORS['dim']
            for r in range(0, radar_size, 2):
                cx = int(center_x + r * math.cos(angle))
                cy = int(center_y + r * math.sin(angle) / 2)
                if 0 <= cy < len(canvas) and 0 <= cx < len(canvas[0]):
                    if r % 4 == 0:
                        canvas[cy][cx] = f"{color}·{self.COLORS['reset']}"
        
        # Dibujar pulso de energía
        pulse_radius = int((self.pulse_size % 15) + 2)
        energy_radius = int(3 + energy * 8)
        pulse_color = self._get_color_by_value(energy)
        
        # Pulso exterior
        for angle in np.linspace(0, 2*math.pi, 30):
            r = max(energy_radius, pulse_radius)
            x = int(center_x + r * math.cos(angle))
            y = int(center_y + r * math.sin(angle) / 2)
            if 0 <= y < len(canvas) and 0 <= x < len(canvas[0]):
                if r > 2:
                    canvas[y][x] = f"{pulse_color}◈{self.COLORS['reset']}"
        
        # Dibujar punto central
        canvas[center_y][center_x] = f"{self.COLORS['bold']}{self.COLORS['white']}◉{self.COLORS['reset']}"
        
        # Dibujar línea del radar (barrido)
        sweep_x = int(center_x + (radar_size - 1) * math.cos(self.radar_angle))
        sweep_y = int(center_y + (radar_size - 1) * math.sin(self.radar_angle) / 2)
        if 0 <= sweep_y < len(canvas) and 0 <= sweep_x < len(canvas[0]):
            canvas[sweep_y][sweep_x] = f"{self.COLORS['cyan']}◈{self.COLORS['reset']}"
        
        # Si hay detección, dibujar explosión
        if self.is_detected:
            explosion_colors = [self.COLORS['red'], self.COLORS['orange'], self.COLORS['yellow']]
            for i, color in enumerate(explosion_colors):
                radius = 5 + i * 3
                for angle in np.linspace(0, 2*math.pi, 20):
                    x = int(center_x + radius * math.cos(angle + self.frame * 0.1))
                    y = int(center_y + radius * math.sin(angle + self.frame * 0.1) / 2)
                    if 0 <= y < len(canvas) and 0 <= x < len(canvas[0]):
                        canvas[y][x] = f"{color}✦{self.COLORS['reset']}"
        
        # Imprimir canvas
        for row in canvas:
            print(''.join(row))
    
    def _draw_status(self, energy, prediction):
        """Dibuja la barra de estado y métricas"""
        # Determinar estado
        if self.is_detected:
            status = f"{self.COLORS['bold']}{self.COLORS['red']}⚡ ¡JARVIS DETECTADO! ⚡{self.COLORS['reset']}"
        elif self.is_processing:
            status = f"{self.COLORS['bold']}{self.COLORS['orange']}🌀 PROCESANDO...{self.COLORS['reset']}"
        elif self.is_speech:
            status = f"{self.COLORS['bold']}{self.COLORS['cyan']}🔊 VOZ DETECTADA{self.COLORS['reset']}"
        else:
            status = f"{self.COLORS['dim']}🎤 ESCUCHANDO{self.COLORS['reset']}"
        
        # Barras de energía
        bar_len = 30
        energy_bars = int(bar_len * min(1.0, energy * 3))
        energy_bar = '█' * energy_bars + '░' * (bar_len - energy_bars)
        energy_color = self._get_color_by_value(energy * 3)
        
        # Barras de predicción
        pred_bars = int(bar_len * prediction)
        pred_bar = '█' * pred_bars + '░' * (bar_len - pred_bars)
        pred_color = self._get_color_by_value(prediction)
        
        # Mostrar estado
        print(f"\n{status}")
        print(f"{self.COLORS['dim']}▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀{self.COLORS['reset']}")
        
        # Energía
        print(f"{self.COLORS['dim']}🔊 Energía:{self.COLORS['reset']} {energy_color}{energy_bar}{self.COLORS['reset']} {energy:.4f}")
        
        # Predicción
        print(f"{self.COLORS['dim']}🎯 Predicción:{self.COLORS['reset']} {pred_color}{pred_bar}{self.COLORS['reset']} {prediction:.3f}")
        
        # Umbral
        threshold_color = self.COLORS['green'] if prediction >= self.threshold else self.COLORS['dim']
        print(f"{self.COLORS['dim']}🎯 Umbral:{self.COLORS['reset']} {threshold_color}{self.threshold:.3f}{self.COLORS['reset']}")
        
        # Sensibilidad
        sensitivity = "HIPER-SENSIBLE" if self.threshold < 0.4 else "SENSIBLE"
        print(f"{self.COLORS['dim']}⚡ Modo:{self.COLORS['reset']} {self.COLORS['yellow']}{sensitivity}{self.COLORS['reset']}")
        
        # Detecciones
        print(f"{self.COLORS['dim']}📊 Detecciones:{self.COLORS['reset']} {self.COLORS['bold']}{self.detecciones or 0}{self.COLORS['reset']}")
        
        # Mostrar motor
        print(f"{self.COLORS['dim']}🧠 Motor:{self.COLORS['reset']} {self.COLORS['cyan']}OpenWakeWord{self.COLORS['reset']}")
        print(f"{self.COLORS['dim']}🗣️  Palabra:{self.COLORS['reset']} {self.COLORS['yellow']}'Hey Jarvis'{self.COLORS['reset']}")
        
        print(f"{self.COLORS['dim']}▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀{self.COLORS['reset']}")
    
    def update(self, energy=0, prediction=0, threshold=0.3, 
               is_speech=False, is_detected=False, is_processing=False, 
               detecciones=0):
        """Actualiza y dibuja la animación"""
        self.energy = energy
        self.prediction = prediction
        self.threshold = threshold
        self.is_speech = is_speech
        self.is_detected = is_detected
        self.is_processing = is_processing
        self.frame += 1
        self.detecciones = detecciones
        
        # Mover cursor al inicio
        sys.stdout.write('\033[H')
        
        # Dibujar radar
        self._draw_radar(energy, prediction)
        
        # Dibujar estado
        self._draw_status(energy, prediction)
        
        sys.stdout.flush()

# ============================================
# VAD (Voice Activity Detection)
# ============================================

class VoiceActivityDetector:
    """Detector de actividad de voz - MODO HIPER-SENSIBLE"""
    
    def __init__(self):
        self.vad = None
        self.is_speech = False
        self.speech_counter = 0
        self.energy_history = deque(maxlen=5)
        self.speech_start_time = 0
        
        if WEBRTC_VAD_AVAILABLE:
            try:
                self.vad = webrtcvad.Vad(config.VAD_AGGRESSIVENESS)
            except:
                self.vad = None
    
    def is_voice_activity(self, audio_chunk):
        """Detecta actividad de voz - Muy sensible"""
        if not audio_chunk or len(audio_chunk) == 0:
            return False
        
        # Calcular energía
        energy = np.mean(audio_chunk ** 2)
        self.energy_history.append(energy)
        
        # Umbral de energía MUY BAJO para ser sensible
        if energy < config.ENERGY_THRESHOLD:
            return False
        
        # Usar WebRTC VAD si está disponible
        if self.vad:
            try:
                audio_bytes = (audio_chunk * 32767).astype(np.int16).tobytes()
                sample_count = len(audio_chunk)
                
                if sample_count in [160, 320, 480, 640, 800]:
                    is_speech = self.vad.is_speech(audio_bytes, config.SAMPLE_RATE)
                    if is_speech or energy > config.ENERGY_THRESHOLD * 2:
                        return True
                else:
                    if energy > config.ENERGY_THRESHOLD * 3:
                        return True
            except Exception:
                pass
        
        # Fallback: detección por energía
        if len(self.energy_history) >= 3:
            energy_avg = np.mean(list(self.energy_history))
            if energy > config.ENERGY_THRESHOLD * 2:
                return True
            if energy > energy_avg * 1.5 and energy > config.ENERGY_THRESHOLD:
                return True
        
        return False
    
    def process_audio(self, audio_chunk):
        """Procesa audio y retorna si hay voz"""
        if len(audio_chunk.shape) > 1:
            audio_chunk = np.mean(audio_chunk, axis=1)
        
        if np.max(np.abs(audio_chunk)) > 0:
            audio_chunk = audio_chunk / np.max(np.abs(audio_chunk))
        
        is_voice = self.is_voice_activity(audio_chunk)
        
        if is_voice:
            self.speech_counter += 1
            self.is_speech = True
        else:
            self.speech_counter = max(0, self.speech_counter - 1)
            if self.speech_counter < 5:
                self.is_speech = False
        
        return is_voice, self.is_speech

# ============================================
# DETECTOR DE WAKE WORD - CON ANIMACIÓN
# ============================================

class WakeWordDetector:
    def __init__(self):
        self.animator = VisualAnimator()
        
        if not OPENWAKEWORD_AVAILABLE:
            print("❌ OpenWakeWord no está disponible")
            sys.exit(1)
        
        self.oww_model = None
        self.threshold = config.OWW_THRESHOLD
        self.prediction_buffer = deque(maxlen=config.BUFFER_SIZE)
        self.corriendo = False
        self.audio_interface = None
        self.stream = None
        self.frame_queue = queue.Queue()
        self.ultima_deteccion = 0
        self.cooldown = config.COOLDOWN_SEGUNDOS
        self.detecciones_totales = 0
        self.proceso_cliente = None
        self.cliente_activo = False
        self.energia_anterior = 0
        self.vad = VoiceActivityDetector()
        self.audio_buffer = []
        self.frame_count = 0
        
        self.inicializar_openwakeword()
    
    def inicializar_openwakeword(self):
        """Inicializa OpenWakeWord - Versión compatible"""
        try:
            print("📥 Cargando modelo OpenWakeWord...")
            
            # Intentar diferentes formas de carga
            metodos = [
                {"tipo": "model_paths", "args": {"model_paths": ["modelos/jarvis.onnx"]}},
                {"tipo": "wakeword_models", "args": {"wakeword_models": ["hey_jarvis"]}},
                {"tipo": "models", "args": {"models": {"hey_jarvis": "modelos/jarvis.onnx"}}},
                {"tipo": "default", "args": {}}
            ]
            
            for metodo in metodos:
                try:
                    print(f"  Intentando: {metodo['tipo']}...")
                    self.oww_model = Model(**metodo['args'])
                    print(f"✅ Modelo cargado con: {metodo['tipo']}")
                    
                    # Verificar modelo
                    test_audio = np.zeros(config.SAMPLE_RATE, dtype=np.float32)
                    test_pred = self.oww_model.predict(test_audio)
                    if isinstance(test_pred, dict):
                        print(f"📦 Modelos disponibles: {list(test_pred.keys())}")
                    else:
                        print(f"📦 Modelo cargado correctamente")
                    
                    print(f"🎯 Umbral: {self.threshold}")
                    print(f"🔥 Modo: HIPER-SENSIBLE")
                    return True
                    
                except Exception as e:
                    print(f"  Falló: {e}")
                    continue
            
            print("❌ No se pudo cargar el modelo con ningún método")
            return False
            
        except Exception as e:
            print(f"❌ Error cargando modelo: {e}")
            return False
    
    def get_adaptive_threshold(self, prediction, is_speech, energy):
        """Umbral adaptativo - SIEMPRE MUY BAJO"""
        if is_speech:
            if energy > 0.005:
                return self.threshold * 0.7
            else:
                return self.threshold * 0.8
        else:
            if energy < 0.0005:
                return self.threshold * 1.2
            else:
                return self.threshold
    
    def should_activate(self, prediction: float, energy: float = 0, is_speech: bool = False) -> bool:
        """Detección HIPER-SENSIBLE"""
        adaptive_threshold = self.get_adaptive_threshold(prediction, is_speech, energy)
        self.current_threshold = adaptive_threshold
        
        if is_speech:
            prediction = min(1.0, prediction + 0.2)
        
        aumento_energia = energy - self.energia_anterior
        self.energia_anterior = energy
        
        if aumento_energia > 0.01 and is_speech:
            prediction = min(1.0, prediction + 0.25)
        
        self.prediction_buffer.append(prediction)
        
        if len(self.prediction_buffer) < config.BUFFER_SIZE:
            return False
        
        positives = sum(1 for p in self.prediction_buffer if p > adaptive_threshold)
        
        if positives >= config.MIN_ACTIVACIONES:
            return True
        
        return False
    
    def ejecutar_cliente_voz(self):
        """Ejecuta el cliente de voz cuando se detecta JARVIS"""
        if self.cliente_activo:
            return
        
        self.cliente_activo = True
        
        try:
            print("\n" + "="*50)
            print("🔊 ¡JARVIS DETECTADO! Iniciando asistente...")
            print("="*50 + "\n")
            
            self.proceso_cliente = subprocess.Popen(
                [sys.executable, "cliente.py", "--modo", "voz", "--una-vez"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            def monitorear_cliente():
                self.proceso_cliente.wait()
                self.cliente_activo = False
                self.animator.is_processing = False
                print("\n🎤 Asistente finalizado, volviendo a escuchar...")
            
            threading.Thread(target=monitorear_cliente, daemon=True).start()
            
        except Exception as e:
            print(f"❌ Error ejecutando cliente: {e}")
            self.cliente_activo = False
    
    def callback_audio(self, in_data, frame_count, time_info, status):
        if not self.corriendo:
            return (None, pyaudio.paComplete)
        
        try:
            if self.frame_queue.qsize() < 100:
                self.frame_queue.put_nowait(in_data)
            else:
                try:
                    self.frame_queue.get_nowait()
                    self.frame_queue.put_nowait(in_data)
                except:
                    pass
        except:
            pass
        return (None, pyaudio.paContinue)
    
    def predecir_openwakeword(self, audio_segment):
        """Predicción con OpenWakeWord"""
        if self.oww_model is None:
            return 0.5
        
        try:
            if audio_segment.dtype != np.float32:
                audio_segment = audio_segment.astype(np.float32)
            
            if np.max(np.abs(audio_segment)) > 0:
                audio_segment = audio_segment / np.max(np.abs(audio_segment))
            
            predictions = self.oww_model.predict(audio_segment)
            
            # Obtener predicción
            if isinstance(predictions, dict):
                first_key = list(predictions.keys())[0]
                prediction = predictions[first_key][0]
            else:
                prediction = float(predictions[0])
            
            energy = np.mean(audio_segment ** 2)
            if energy > 0.001:
                prediction = min(1.0, prediction * 1.3)
            
            return max(0.0, min(1.0, prediction))
            
        except Exception as e:
            return 0.5
    
    def procesar_audio(self):
        """Procesa audio usando OpenWakeWord con animación"""
        speech_counter = 0
        min_speech_frames = int(config.MIN_SPEECH_DURATION / (config.CHUNK / config.SAMPLE_RATE))
        
        while self.corriendo:
            try:
                frame_data = self.frame_queue.get(timeout=0.5)
                audio_chunk = np.frombuffer(frame_data, dtype=np.int16).astype(np.float32) / 32768.0
                
                self.audio_buffer.extend(audio_chunk)
                
                max_buffer = int(config.SAMPLE_RATE * 1.5)
                if len(self.audio_buffer) > max_buffer:
                    self.audio_buffer = self.audio_buffer[-max_buffer:]
                
                is_voice, is_speaking = self.vad.process_audio(audio_chunk)
                
                if is_voice:
                    speech_counter += 1
                else:
                    speech_counter = max(0, speech_counter - 2)
                
                current_is_speech = speech_counter >= max(1, min_speech_frames // 2)
                
                if len(self.audio_buffer) >= int(config.SAMPLE_RATE * 0.5):
                    audio_segment = np.array(self.audio_buffer[-config.SAMPLE_RATE:])
                    energy = np.mean(audio_segment ** 2)
                    prediction = self.predecir_openwakeword(audio_segment)
                    
                    tiempo_actual = time.time()
                    is_detected = False
                    
                    if (tiempo_actual - self.ultima_deteccion) > self.cooldown:
                        if self.should_activate(prediction, energy, current_is_speech):
                            self.ultima_deteccion = tiempo_actual
                            self.detecciones_totales += 1
                            is_detected = True
                            
                            self.animator.is_detected = True
                            self.animator.update(energy, prediction, self.current_threshold, 
                                                current_is_speech, True, self.cliente_activo,
                                                self.detecciones_totales)
                            
                            print(f"\n🎯 ¡JARVIS DETECTADO! (confianza: {np.mean(list(self.prediction_buffer)):.3f})")
                            print(f"🧠 Motor: OpenWakeWord")
                            print(f"🗣️  Palabra: 'Hey Jarvis'")
                            
                            self.prediction_buffer.clear()
                            self.ejecutar_cliente_voz()
                            time.sleep(0.2)
                            self.animator.is_detected = False
                    
                    # Actualizar animación cada 2 frames
                    if self.frame_count % 2 == 0:
                        self.animator.is_speech = current_is_speech
                        self.animator.is_processing = self.cliente_activo
                        self.animator.update(energy, prediction, 
                                            getattr(self, 'current_threshold', self.threshold),
                                            current_is_speech, is_detected, self.cliente_activo,
                                            self.detecciones_totales)
                    
                    self.frame_count += 1
                    
            except queue.Empty:
                continue
            except Exception as e:
                if self.corriendo:
                    pass
    
    def iniciar(self):
        """Inicia el detector con animación"""
        if self.oww_model is None:
            print("❌ No hay modelo OpenWakeWord cargado")
            return False
        
        self.corriendo = True
        self.frame_count = 0
        
        try:
            self.audio_interface = pyaudio.PyAudio()
            self.stream = self.audio_interface.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=config.SAMPLE_RATE,
                input=True,
                frames_per_buffer=config.CHUNK,
                stream_callback=self.callback_audio
            )
            self.stream.start_stream()
            
            # Mostrar información inicial con animación
            self.animator.clear()
            print(f"{self.animator.COLORS['bold']}{self.animator.COLORS['cyan']}")
            print("╔══════════════════════════════════════════════╗")
            print("║     🚀 JARVIS - OPENWAKEWORD                ║")
            print("╠══════════════════════════════════════════════╣")
            print(f"║  🧠 Motor: OpenWakeWord                    ║")
            print(f"║  🗣️  Palabra: 'Hey Jarvis'                ║")
            print(f"║  🎯 Umbral: {self.threshold:.3f} (MUY BAJO)     ║")
            print(f"║  🎯 Buffer: {config.BUFFER_SIZE} detecciones      ║")
            print(f"║  ⚡ Activaciones mínimas: {config.MIN_ACTIVACIONES}      ║")
            print(f"║  🗣️  VAD: {'WebRTC' if WEBRTC_VAD_AVAILABLE else 'Energía'}     ║")
            print(f"║  🔥 Sensibilidad: EXTREMA                  ║")
            print("╚══════════════════════════════════════════════╝")
            print(f"{self.animator.COLORS['reset']}")
            print("\n" * 15)
            
            hilo = threading.Thread(target=self.procesar_audio, daemon=True)
            hilo.start()
            
            return True
            
        except Exception as e:
            print(f"❌ Error iniciando: {e}")
            self.corriendo = False
            return False
    
    def detener(self):
        """Detiene el detector"""
        self.corriendo = False
        
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        
        if self.audio_interface:
            self.audio_interface.terminate()
        
        if self.proceso_cliente:
            try:
                self.proceso_cliente.terminate()
            except:
                pass
        
        self.animator.clear()
        print(f"\n📊 Detecciones totales: {self.detecciones_totales}")
        print("👋 Detector JARVIS detenido")

# ============================================
# MAIN
# ============================================

def modo_servidor():
    """Modo servidor - detector continuo con animación"""
    if not OPENWAKEWORD_AVAILABLE:
        print("❌ OpenWakeWord no está instalado")
        print("📥 Instala con: pip install openwakeword")
        sys.exit(1)
    
    detector = WakeWordDetector()
    
    if detector.iniciar():
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n🛑 Deteniendo detector JARVIS...")
        finally:
            detector.detener()

def modo_test():
    """Modo test - prueba de micrófono"""
    print("🎤 Probando micrófono...")
    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=config.SAMPLE_RATE,
        input=True,
        frames_per_buffer=config.CHUNK
    )
    
    vad = VoiceActivityDetector()
    animator = VisualAnimator()
    animator.clear()
    
    print("🔊 Escuchando... (Ctrl+C para salir)\n")
    
    try:
        while True:
            data = stream.read(config.CHUNK)
            audio = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            energy = np.mean(audio ** 2)
            
            is_voice, is_speaking = vad.process_audio(audio)
            
            animator.is_speech = is_speaking
            animator.update(energy, 0.5, 0.30, is_speaking, False, False, 0)
            
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n\n✅ Prueba finalizada")
    finally:
        stream.close()
        p.terminate()
        animator.clear()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JARVIS Assistant - OpenWakeWord con Animación")
    parser.add_argument("--servidor", action="store_true", help="Modo detector")
    parser.add_argument("--test", action="store_true", help="Probar micrófono")
    parser.add_argument("--umbral", type=float, defau#!/usr/bin/env python3
"""
Sistema de Wake Word Detection - JARVIS Assistant
MODO HIPER-SENSIBLE - CON ANIMACIÓN NUMÉRICA
USANDO ONNX RUNTIME - CORREGIDO PARA RANGO 3
"""

import os
import sys
import time
import json
import argparse
import threading
import queue
import subprocess
import numpy as np
import pyaudio
import pickle
from collections import deque
import math
import traceback

try:
    import voz
    VOZ_AVAILABLE = True
except ImportError:
    VOZ_AVAILABLE = False

# ============================================
# IMPORTAR ONNX RUNTIME
# ============================================
try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
    print("✅ ONNX Runtime cargado correctamente")
except ImportError:
    print("❌ ONNX Runtime no instalado")
    sys.exit(1)

try:
    import librosa
    LIBROSA_AVAILABLE = True
    print("✅ Librosa cargado correctamente")
except ImportError:
    print("⚠️ Librosa no instalado")
    LIBROSA_AVAILABLE = False

try:
    import webrtcvad
    WEBRTC_VAD_AVAILABLE = True
    print("✅ WebRTC VAD disponible")
except ImportError:
    print("⚠️ WebRTC VAD no instalado")
    WEBRTC_VAD_AVAILABLE = False

# ============================================
# CONFIGURACIÓN
# ============================================

class Config:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))
    MODEL_PATH = os.path.join(BASE_PATH, "modelos/")
    
    SAMPLE_RATE = 16000
    DURATION = 1.5
    N_MFCC = 13
    HOP_LENGTH = 512
    N_FFT = 2048
    
    BUFFER_SIZE = 5
    MIN_ACTIVACIONES = 3
    CHUNK = int(SAMPLE_RATE * 0.02)
    COOLDOWN_SEGUNDOS = 1.5
    
    VAD_AGGRESSIVENESS = 1
    ENERGY_THRESHOLD = 0.0008
    MIN_SPEECH_DURATION = 0.15
    MAX_SILENCE_DURATION = 0.3
    
    THRESHOLD = 0.25
    
config = Config()

# ============================================
# VAD (Voice Activity Detection)
# ============================================

class VoiceActivityDetector:
    def __init__(self):
        self.vad = None
        self.is_speech = False
        self.speech_counter = 0
        self.energy_history = deque(maxlen=10)
        
        if WEBRTC_VAD_AVAILABLE:
            try:
                self.vad = webrtcvad.Vad(config.VAD_AGGRESSIVENESS)
            except:
                self.vad = None
    
    def is_voice_activity(self, audio_chunk):
        if audio_chunk is None:
            return False
        
        if len(audio_chunk) == 0:
            return False
        
        if hasattr(audio_chunk, 'size') and audio_chunk.size == 0:
            return False
        
        energy = np.mean(audio_chunk ** 2)
        self.energy_history.append(energy)
        
        if energy < config.ENERGY_THRESHOLD:
            return False
        
        if self.vad:
            try:
                audio_bytes = (audio_chunk * 32767).astype(np.int16).tobytes()
                sample_count = len(audio_chunk)
                if sample_count in [160, 320, 480, 640, 800]:
                    is_speech = self.vad.is_speech(audio_bytes, config.SAMPLE_RATE)
                    if is_speech:
                        return True
                else:
                    if energy > config.ENERGY_THRESHOLD * 3:
                        return True
            except Exception:
                pass
        
        if len(self.energy_history) >= 5:
            energy_avg = np.mean(list(self.energy_history))
            if energy > energy_avg * 1.8 and energy > config.ENERGY_THRESHOLD:
                return True
        
        return False
    
    def process_audio(self, audio_chunk):
        if audio_chunk is None:
            return False, False
        
        if len(audio_chunk) == 0:
            return False, False
        
        if hasattr(audio_chunk, 'size') and audio_chunk.size == 0:
            return False, False
        
        if len(audio_chunk.shape) > 1:
            audio_chunk = np.mean(audio_chunk, axis=1)
        
        max_val = np.max(np.abs(audio_chunk))
        if max_val > 0:
            audio_chunk = audio_chunk / max_val
        
        is_voice = self.is_voice_activity(audio_chunk)
        
        if is_voice:
            self.speech_counter = min(self.speech_counter + 1, 20)
            self.is_speech = True
        else:
            self.speech_counter = max(0, self.speech_counter - 2)
            if self.speech_counter < 3:
                self.is_speech = False
        
        return is_voice, self.is_speech

# ============================================
# PROCESADOR DE AUDIO - CORREGIDO
# ============================================

class AudioProcessor:
    def __init__(self):
        self.target_length = int(config.SAMPLE_RATE * config.DURATION)
        self.feature_length = None
        self.use_librosa = LIBROSA_AVAILABLE
        print(f"📊 Usando Librosa: {self.use_librosa}")
        
    def extract_features(self, audio):
        """
        Extrae características en formato (time_steps, features)
        El modelo espera (batch, time_steps, features)
        """
        if not self.use_librosa:
            return self._extract_simple_features(audio)
        
        try:
            if len(audio) < self.target_length:
                audio = np.pad(audio, (0, self.target_length - len(audio)))
            else:
                audio = audio[:self.target_length]
            
            # Extraer MFCCs (13 coeficientes)
            mfcc = librosa.feature.mfcc(
                y=audio, 
                sr=config.SAMPLE_RATE,
                n_mfcc=13,
                n_fft=config.N_FFT,
                hop_length=config.HOP_LENGTH
            )
            
            # Calcular deltas y delta-deltas
            mfcc_delta = librosa.feature.delta(mfcc)
            mfcc_delta2 = librosa.feature.delta(mfcc, order=2)
            
            # Concatenar: (13 + 13 + 13) = 39 características por frame
            features = np.vstack([mfcc, mfcc_delta, mfcc_delta2]).T  # (time, 39)
            
            # Normalizar características
            features = (features - np.mean(features)) / (np.std(features) + 1e-6)
            
            return features.astype(np.float32)
            
        except Exception as e:
            print(f"⚠️ Error en librosa: {e}")
            return self._extract_simple_features(audio)
    
    def _extract_simple_features(self, audio):
        """Extrae características simples como fallback"""
        try:
            if len(audio) < self.target_length:
                audio = np.pad(audio, (0, self.target_length - len(audio)))
            else:
                audio = audio[:self.target_length]
            
            # Calcular FFT
            fft = np.abs(np.fft.rfft(audio))
            freqs = np.fft.rfftfreq(len(audio), 1/config.SAMPLE_RATE)
            
            # Dividir en bandas de frecuencia
            n_bands = 13
            features = []
            
            for i in range(n_bands):
                low_freq = i * (config.SAMPLE_RATE / 2 / n_bands)
                high_freq = (i + 1) * (config.SAMPLE_RATE / 2 / n_bands)
                
                mask = np.logical_and(freqs >= low_freq, freqs < high_freq)
                
                if np.any(mask):
                    band_fft = fft[mask]
                    if len(band_fft) > 0:
                        band_energy = np.sum(band_fft ** 2)
                        features.append(np.log(band_energy + 1e-6))
                    else:
                        features.append(0.0)
                else:
                    features.append(0.0)
            
            # Repetir para simular deltas
            features_39 = np.tile(features, 3)
            
            # Crear array de forma (time_steps, features)
            # Usamos 1 time step con 39 features
            features_array = np.array(features_39, dtype=np.float32).reshape(1, -1)
            
            return features_array
            
        except Exception as e:
            print(f"⚠️ Error en features simples: {e}")
            return np.zeros((1, 39), dtype=np.float32)
    
    def normalize_audio(self, audio):
        if np.max(np.abs(audio)) > 0:
            audio = audio / np.max(np.abs(audio))
        return audio

# ============================================
# DETECTOR DE WAKE WORD - CORREGIDO
# ============================================

class WakeWordDetector:
    def __init__(self):
        self.processor = AudioProcessor()
        self.ort_session = None
        self.input_name = None
        self.output_name = None
        self.input_shape = None
        
        self.threshold = config.THRESHOLD
        self.prediction_buffer = deque(maxlen=config.BUFFER_SIZE)
        self.corriendo = False
        self.audio_interface = None
        self.stream = None
        self.frame_queue = queue.Queue()
        self.ultima_deteccion = 0
        self.cooldown = config.COOLDOWN_SEGUNDOS
        self.detecciones_totales = 0
        self.proceso_cliente = None
        self.cliente_activo = False
        self.energia_anterior = 0
        self.vad = VoiceActivityDetector()
        self.frame_count = 0
        self.ultimo_estado = ""
        
        # Variables para animación numérica
        self.energia_display = 0
        self.pred_display = 0
        self.confianza_promedio = 0
        self.deteccion_confirmada = False
        self.modelo_cargado = False
        self.ultima_prediccion = 0.5
        
        if VOZ_AVAILABLE:
            try:
                voz.hablar("Sistema Jarvis iniciado")
            except:
                pass
        
        self.cargar_modelo_onnx()
    
    def cargar_modelo_onnx(self):
        """Carga el modelo ONNX"""
        posibles_rutas = [
            os.path.join(config.MODEL_PATH, "jarvis.onnx"),
            os.path.join(config.MODEL_PATH, "hey_jarvis.onnx"),
            os.path.join(config.MODEL_PATH, "hey_jarvis_v0.1.onnx"),
            os.path.join(config.MODEL_PATH, "hey_jarvis_v1.onnx"),
            "modelos/jarvis.onnx",
            "modelos/hey_jarvis.onnx",
            "modelos/hey_jarvis_v1.onnx",
            os.path.expanduser("~/.cache/openwakeword/models/hey_jarvis.onnx"),
        ]
        
        model_path = None
        for ruta in posibles_rutas:
            if os.path.exists(ruta):
                model_path = ruta
                print(f"✅ Modelo encontrado en: {ruta}")
                break
        
        if not model_path:
            print("❌ No se encontró ningún modelo ONNX")
            print("📥 Descarga el modelo desde:")
            print("   https://huggingface.co/WCPDR-AI/voice-models/blob/main/wake/hey_jarvis_v1.onnx")
            print("   Colócalo en: modelos/hey_jarvis_v1.onnx")
            return False
        
        try:
            # Configurar sesión ONNX
            providers = ['CPUExecutionProvider']
            self.ort_session = ort.InferenceSession(model_path, providers=providers)
            
            # Obtener información de entrada
            input_info = self.ort_session.get_inputs()[0]
            self.input_name = input_info.name
            self.input_shape = input_info.shape
            self.output_name = self.ort_session.get_outputs()[0].name
            
            print(f"✅ Modelo ONNX cargado")
            print(f"📊 Entrada: {self.input_name} -> {self.input_shape}")
            print(f"📊 Salida: {self.output_name}")
            print(f"🎯 Umbral: {self.threshold}")
            
            # Probar modelo con datos de prueba
            # El modelo espera (batch, time_steps, features)
            # Crear datos de prueba: 1 batch, 1 time_step, 39 features
            test_input = np.random.randn(1, 1, 39).astype(np.float32)
            
            # Si el modelo espera más time_steps, ajustar
            if len(self.input_shape) == 3 and self.input_shape[1] is not None:
                if self.input_shape[1] > 1:
                    test_input = np.random.randn(1, self.input_shape[1], 39).astype(np.float32)
            
            test_output = self.ort_session.run(
                [self.output_name], 
                {self.input_name: test_input}
            )
            
            print(f"✅ Modelo verificado correctamente")
            self.modelo_cargado = True
            return True
            
        except Exception as e:
            print(f"❌ Error cargando modelo: {e}")
            traceback.print_exc()
            return False
    
    def predecir_onnx(self, features):
        """
        Predice usando el modelo ONNX
        features debe ser (time_steps, features)
        """
        if self.ort_session is None:
            return 0.5
        
        try:
            # Asegurar que features tiene la forma correcta
            if features.ndim == 2:
                # (time_steps, features) -> añadir batch dimension
                input_data = features[np.newaxis, ...].astype(np.float32)  # (1, time_steps, features)
            elif features.ndim == 3:
                # Ya tiene batch dimension
                input_data = features.astype(np.float32)
            else:
                # Si es 1D, reshape a (1, 1, features)
                input_data = features.reshape(1, 1, -1).astype(np.float32)
            
            # Verificar dimensiones con lo que espera el modelo
            if len(self.input_shape) == 3:
                expected_time = self.input_shape[1]
                expected_features = self.input_shape[2]
                
                # Ajustar time_steps si es necesario
                if expected_time is not None and input_data.shape[1] != expected_time:
                    if input_data.shape[1] > expected_time:
                        input_data = input_data[:, :expected_time, :]
                    else:
                        pad_time = expected_time - input_data.shape[1]
                        input_data = np.pad(input_data, ((0, 0), (0, pad_time), (0, 0)), mode='constant')
                
                # Ajustar features si es necesario
                if expected_features is not None and input_data.shape[2] != expected_features:
                    if input_data.shape[2] > expected_features:
                        input_data = input_data[:, :, :expected_features]
                    else:
                        pad_features = expected_features - input_data.shape[2]
                        input_data = np.pad(input_data, ((0, 0), (0, 0), (0, pad_features)), mode='constant')
            
            # Ejecutar inferencia
            outputs = self.ort_session.run(
                [self.output_name],
                {self.input_name: input_data}
            )
            
            # Obtener predicción
            if len(outputs[0].shape) > 1:
                prediction = float(outputs[0][0][0])
            else:
                prediction = float(outputs[0][0])
            
            # Aplicar sigmoid si es necesario
            if prediction > 1 or prediction < 0:
                prediction = 1 / (1 + np.exp(-prediction))
            
            self.ultima_prediccion = max(0.0, min(1.0, prediction))
            return self.ultima_prediccion
            
        except Exception as e:
            print(f"⚠️ Error en predicción: {e}")
            return 0.5
    
    def should_activate(self, prediction, energy, is_speech):
        if is_speech and energy > config.ENERGY_THRESHOLD:
            prediction = min(1.0, prediction + 0.15)
        
        if energy > 0.01:
            prediction = min(1.0, prediction + 0.1)
        
        self.prediction_buffer.append(prediction)
        
        if len(self.prediction_buffer) < config.BUFFER_SIZE:
            return False
        
        avg_pred = np.mean(list(self.prediction_buffer))
        self.confianza_promedio = avg_pred
        
        if avg_pred > self.threshold:
            return True
        
        positives = sum(1 for p in self.prediction_buffer if p > self.threshold)
        if positives >= config.MIN_ACTIVACIONES:
            return True
        
        return False
    
    def mostrar_estado(self, energy, prediction, is_speech, is_detected, detecciones):
        """Muestra estado con ANIMACIÓN NUMÉRICA"""
        # Actualizar valores suavizados
        self.energia_display = self.energia_display * 0.7 + energy * 0.3
        self.pred_display = self.pred_display * 0.7 + prediction * 0.3
        
        if is_detected:
            self.deteccion_confirmada = True
        
        os.system('clear' if os.name == 'posix' else 'cls')
        
        print("=" * 70)
        print("🔊 JARVIS DETECTOR - ANIMACIÓN NUMÉRICA")
        print("=" * 70)
        
        print("\n" + "=" * 70)
        print("📊 ANIMACIÓN NUMÉRICA")
        print("=" * 70)
        
        # 1. Energía
        energia_num = self.energia_display * 10000
        energia_barras = int(min(50, energia_num / 2))
        print(f"\n🔊 ENERGÍA:")
        print(f"   {energia_num:8.2f}  [{'█' * energia_barras}{'░' * (50 - energia_barras)}]")
        
        # 2. Predicción
        pred_porcentaje = self.pred_display * 100
        pred_barras = int(min(50, pred_porcentaje * 2))
        print(f"\n🎯 PREDICCIÓN:")
        print(f"   {pred_porcentaje:6.1f}%  [{'█' * pred_barras}{'░' * (50 - pred_barras)}]")
        
        # 3. Umbral
        umbral_porcentaje = self.threshold * 100
        umbral_barras = int(min(50, umbral_porcentaje * 2))
        print(f"\n⚡ UMBRAL:")
        print(f"   {umbral_porcentaje:6.1f}%  [{'█' * umbral_barras}{'░' * (50 - umbral_barras)}]")
        
        # 4. Confianza promedio
        if len(self.prediction_buffer) > 0:
            avg_pred = np.mean(list(self.prediction_buffer)) * 100
            print(f"\n📈 CONFIANZA PROMEDIO:")
            print(f"   {avg_pred:6.1f}%  [{len(self.prediction_buffer)} muestras]")
        
        # 5. Estado del modelo
        print(f"\n🧠 MODELO: {'✅ CARGADO' if self.modelo_cargado else '❌ NO CARGADO'}")
        print(f"📊 FORMA: {self.input_shape}")
        
        # 6. Estado de voz
        print(f"\n🗣️  VOZ: {'🔊 ACTIVA' if is_speech else '🔇 INACTIVA'}")
        
        # 7. Detecciones
        print(f"\n📌 DETECCIONES: {detecciones}")
        
        # 8. Estado de detección
        print("\n" + "=" * 70)
        if self.deteccion_confirmada:
            print("🎯 ¡JARVIS DETECTADO! ✅")
            self.deteccion_confirmada = False
        elif self.cliente_activo:
            print("🌀 PROCESANDO ASISTENTE...")
        else:
            print("🎤 ESCUCHANDO...")
        
        print("=" * 70)
        
        if len(self.prediction_buffer) > 0:
            pred_list = list(self.prediction_buffer)
            pred_str = " | ".join([f"{p:.3f}" for p in pred_list])
            print(f"\n📈 Últimas: [{pred_str}]")
            print(f"📊 Promedio: {np.mean(pred_list):.3f}")
        
        print("\n" + "=" * 70)
        print("🔄 Presiona Ctrl+C para salir")
        print("=" * 70)
    
    def ejecutar_cliente_voz(self):
        """Ejecuta cliente.py cuando se detecta la wake word"""
        if self.cliente_activo:
            return
        
        self.cliente_activo = True
        
        try:
            print("\n" + "="*70)
            print("🔊 ¡JARVIS DETECTADO! Iniciando asistente...")
            print("="*70 + "\n")
            
            # Verificar si cliente.py existe
            if not os.path.exists("cliente.py"):
                print("❌ No se encontró cliente.py")
                self.cliente_activo = False
                return
            
            # Ejecutar cliente.py
            self.proceso_cliente = subprocess.Popen(
                [sys.executable, "cliente.py", "--modo", "voz", "--una-vez"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            def monitorear_cliente():
                try:
                    self.proceso_cliente.wait()
                except:
                    pass
                self.cliente_activo = False
                print("\n🎤 Asistente finalizado, volviendo a escuchar...")
            
            threading.Thread(target=monitorear_cliente, daemon=True).start()
            
        except Exception as e:
            print(f"❌ Error ejecutando cliente: {e}")
            self.cliente_activo = False
    
    def callback_audio(self, in_data, frame_count, time_info, status):
        if not self.corriendo:
            return (None, pyaudio.paComplete)
        
        try:
            if self.frame_queue.qsize() < 100:
                self.frame_queue.put_nowait(in_data)
        except:
            pass
        return (None, pyaudio.paContinue)
    
    def procesar_audio(self):
        buffer_audio = []
        frames_needed = int(config.SAMPLE_RATE * config.DURATION / config.CHUNK)
        speech_counter = 0
        min_speech_frames = int(config.MIN_SPEECH_DURATION / (config.CHUNK / config.SAMPLE_RATE))
        frame_counter = 0
        
        while self.corriendo:
            try:
                frame_data = self.frame_queue.get(timeout=0.5)
                audio_chunk = np.frombuffer(frame_data, dtype=np.int16).astype(np.float32) / 32768.0
                buffer_audio.extend(audio_chunk)
                
                is_voice, is_speaking = self.vad.process_audio(audio_chunk)
                
                if is_voice:
                    speech_counter += 1
                else:
                    speech_counter = max(0, speech_counter - 2)
                
                current_is_speech = speech_counter >= max(1, min_speech_frames // 2)
                
                if len(buffer_audio) >= config.SAMPLE_RATE * config.DURATION:
                    audio_segment = np.array(buffer_audio[:frames_needed * config.CHUNK])
                    buffer_audio = buffer_audio[config.CHUNK:]
                    
                    energy = np.mean(audio_segment ** 2)
                    
                    audio_norm = self.processor.normalize_audio(audio_segment)
                    features = self.processor.extract_features(audio_norm)
                    
                    prediction = self.predecir_onnx(features)
                    
                    tiempo_actual = time.time()
                    is_detected = False
                    
                    if (tiempo_actual - self.ultima_deteccion) > self.cooldown:
                        if self.should_activate(prediction, energy, current_is_speech):
                            self.ultima_deteccion = tiempo_actual
                            self.detecciones_totales += 1
                            is_detected = True
                            self.deteccion_confirmada = True
                            
                            print(f"\n🎯 ¡JARVIS DETECTADO! (confianza: {prediction:.3f})")
                            print(f"🧠 Motor: ONNX Runtime")
                            print(f"🔊 Energía: {energy:.6f}")
                            
                            self.prediction_buffer.clear()
                            self.ejecutar_cliente_voz()
                            time.sleep(0.2)
                    
                    if frame_counter % 2 == 0:
                        self.mostrar_estado(energy, prediction, current_is_speech, 
                                           is_detected, self.detecciones_totales)
                    
                    frame_counter += 1
                    
            except queue.Empty:
                continue
            except Exception as e:
                if self.corriendo:
                    print(f"⚠️ Error en procesamiento: {e}")
                    traceback.print_exc()
    
    def iniciar(self):
        if self.ort_session is None:
            print("❌ No hay modelo ONNX cargado")
            return False
        
        self.corriendo = True
        
        try:
            self.audio_interface = pyaudio.PyAudio()
            self.stream = self.audio_interface.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=config.SAMPLE_RATE,
                input=True,
                frames_per_buffer=config.CHUNK,
                stream_callback=self.callback_audio
            )
            self.stream.start_stream()
            
            self.mostrar_estado(0, 0, False, False, 0)
            
            hilo = threading.Thread(target=self.procesar_audio, daemon=True)
            hilo.start()
            
            return True
            
        except Exception as e:
            print(f"❌ Error iniciando: {e}")
            self.corriendo = False
            return False
    
    def detener(self):
        self.corriendo = False
        
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        
        if self.audio_interface:
            self.audio_interface.terminate()
        
        if self.proceso_cliente:
            try:
                self.proceso_cliente.terminate()
            except:
                pass
        
        print(f"\n📊 Detecciones totales: {self.detecciones_totales}")
        print("👋 Detector JARVIS detenido")

# ============================================
# MAIN
# ============================================

def modo_servidor():
    detector = WakeWordDetector()
    
    if detector.iniciar():
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n🛑 Deteniendo detector...")
        finally:
            detector.detener()

def modo_test():
    print("🎤 Probando micrófono...")
    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=config.SAMPLE_RATE,
        input=True,
        frames_per_buffer=config.CHUNK
    )
    
    vad = VoiceActivityDetector()
    
    print("🔊 Escuchando... (Ctrl+C para salir)\n")
    print("=" * 60)
    print("📊 MONITOR DE MICRÓFONO")
    print("=" * 60)
    
    try:
        while True:
            data = stream.read(config.CHUNK)
            audio = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            energy = np.mean(audio ** 2)
            
            is_voice, is_speaking = vad.process_audio(audio)
            
            os.system('clear' if os.name == 'posix' else 'cls')
            print("=" * 60)
            print("🎤 TEST DE MICRÓFONO")
            print("=" * 60)
            
            if is_speaking:
                print("\n🔊 ¡VOZ DETECTADA!")
                color = "\033[92m"
            else:
                print("\n🔇 Silencio")
                color = "\033[90m"
            
            print(f"\n{color}🔊 Energía: {energy:.6f}\033[0m")
            
            bar_len = 40
            bars = int(bar_len * min(1.0, energy * 100))
            bar = "█" * bars + "░" * (bar_len - bars)
            print(f"\n   [{bar}]")
            
            print("\n" + "=" * 60)
            print("Presiona Ctrl+C para salir")
            
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n\n✅ Prueba finalizada")
    finally:
        stream.close()
        p.terminate()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JARVIS Assistant - ONNX Runtime")
    parser.add_argument("--servidor", action="store_true", help="Modo detector")
    parser.add_argument("--test", action="store_true", help="Probar micrófono")
    parser.add_argument("--umbral", type=float, default=0.25, help="Umbral (0.1-0.9)")
    
    args = parser.parse_args()
    
    if args.umbral:
        config.THRESHOLD = args.umbral
    
    if args.test:
        modo_test()
    else:
        modo_servidor()lt=0.30, help="Umbral (0.1-0.9)")
    parser.add_argument("--buffer", type=int, default=2, help="Tamaño buffer")
    parser.add_argument("--min-activaciones", type=int, default=1, help="Mínimo activaciones")
    
    args = parser.parse_args()
    
    if args.umbral:
        config.OWW_THRESHOLD = args.umbral
    if args.buffer:
        config.BUFFER_SIZE = args.buffer
    if args.min_activaciones:
        config.MIN_ACTIVACIONES = args.min_activaciones
    
    if args.test:
        modo_test()
    else:
        modo_servidor()