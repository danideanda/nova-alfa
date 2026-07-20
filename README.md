# 🤖 Nova Alfa - Asistente Inteligente

Repositorio del dispositivo Nova Alfa, un asistente inteligente de código abierto creado por Daniel de Anda.

## 📋 Descripción

Nova Alfa es un sistema completo de asistente inteligente que integra:

- **Procesamiento de Voz**: Captura y análisis de audio continuo
- **Detección de Palabras Clave**: Sistema de activación mediante detección de wakeword
- **Procesamiento de Lenguaje Natural**: Lógica de intenciones y respuestas inteligentes
- **Síntesis de Voz**: Reproducción de respuestas en audio
- **Gestión de Configuración**: Sistema de personalización y configuración centralizado
- **Monitoreo del Sistema**: Control de conectividad, actualizaciones y estado general

## 🏗️ Estructura del Proyecto

```
nova-alfa/
├── main.py                 # Servidor principal del sistema
├── inicio.py              # Inicializador y gestor del ciclo de vida
├── cliente.py             # Interfaz cliente de usuario
├── funciones.py           # Funciones auxiliares y utilidades
├── audio.py              # Procesamiento y captura de audio
├── voz.py                # Síntesis de voz (TTS)
├── wake.py               # Detector de palabras clave
├── ifs.py                # Motor de procesamiento de intenciones
├── intencion.py          # Definición de intenciones
├── compilar.py           # Compilación de binarios
├── comunicacion.py       # Protocolo de comunicación
├── hadware.py            # Interfaz con hardware
├── errores.py            # Gestión de errores
├── local_libs.py         # Bibliotecas locales
├── sistemprot.json       # Configuración del sistema
├── txt/                  # Archivos de configuración y estado
│   ├── version.txt
│   ├── estado_inicio.txt
│   ├── estado_de_red.txt
│   └── personalizacion.txt
├── modelos/              # Modelos de ML para detección
├── modelo-es/            # Modelos en español
├── backup/               # Respaldos del sistema
└── tmp/                  # Archivos temporales
```

## 🚀 Características Principales

### 1. **Sistema de Inicio Automático** (`inicio.py`)
- Gestión de primera ejecución con configuración inicial
- Verificación periódica de conectividad
- Monitoreo automático de actualizaciones
- Respaldo y recuperación del sistema
- Control del ciclo de vida de componentes

### 2. **Captura de Audio Continua** (`audio.py`)
- Captura de audio en fragmentos de 2 segundos
- Procesamiento mediante características MFCC
- Detección basada en modelos de Machine Learning
- Análisis de energía y duración de voz
- Sistema de buffer para confirmación robusta

### 3. **Síntesis de Voz** (`voz.py`)
- Soporte para múltiples idiomas
- Respaldo offline con pyttsx3
- Reproducción online con edge-tts
- Manejo robusto de errores
- Diagnóstico del sistema de audio

### 4. **Procesamiento de Intenciones** (`ifs.py`, `intencion.py`)
- Motor de lógica para interpretación de comandos
- Sistema de intenciones configurables
- Respuestas contextuales e inteligentes
- Procesamiento de solicitudes del usuario

### 5. **Gestión de Configuración**
- Archivo centralizado de configuración (`sistemprot.json`)
- Personalización del usuario (nombre, idioma, ubicación)
- Parámetros ajustables del modelo
- Persistencia de estado

### 6. **Monitoreo del Sistema**
- Verificación de conectividad a internet
- Detección de cambios de estado de red
- Monitoreo periódico cada 10 minutos
- Manejo automático de desconexiones

### 7. **Control de Hardware** (`hadware.py`)
- Señales de activación/desactivación
- Control de procesamiento
- Integración con hardware específico

### 8. **Compilación a Binario** (`compilar.py`)
- Generación de ejecutables independientes
- Empaquetamiento del sistema
- Distribución optimizada

## 🔧 Componentes Técnicos

### Dependencias Principales
- **FastAPI**: Framework web para APIs
- **TensorFlow/Librosa**: Procesamiento de audio y ML
- **PyTTSX3**: Síntesis de voz offline
- **Edge-TTS**: Síntesis de voz online
- **SoundDevice**: Captura de audio
- **NetworkManager**: Gestión de conectividad

### Archivos de Configuración

**`sistemprot.json`** - Configuración del sistema:
```json
{
  "system_prompt": "Instrucciones del asistente",
  "contexto_maestro": {
    "nombre": "Nova",
    "idioma": "Español de México",
    "reglas": ["Responde de forma clara y concisa"]
  },
  "parametros_modelo": {
    "temperature": 0.2,
    "max_tokens": 212,
    "top_p": 0.9,
    "n_ctx": 10000
  }
}
```

**`txt/personalizacion.txt`** - Datos del usuario:
- Nombre del usuario
- Idioma y preferencias de voz
- Ubicación (ciudad, región, país)
- Preferencias de reproducción
- Estado de conectividad

### Parámetros del Sistema

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `SAMPLE_RATE` | 16000 Hz | Frecuencia de muestreo de audio |
| `DURATION` | 2.0 s | Duración de cada fragmento de audio |
| `BUFFER_SIZE` | 3 | Ventana de detección (últimas 3 lecturas) |
| `ACTIVATION_SCORE` | 300 | Umbral de puntuación para activación |
| `INTERVALO_RED` | 600 s | Verificación de conectividad cada 10 min |
| `INTERVALO_ACTUALIZACION` | 600 s | Verificación de actualizaciones cada 10 min |

## 🎯 Flujo de Operación

1. **Inicio del Sistema** (`inicio.py`)
   - Verificación de directorio de configuración
   - Cargar configuración del usuario
   - Verificar estado de conectividad
   - Iniciar componentes principales

2. **Captura de Audio** (`audio.py`, `wake.py`)
   - Bucle continuo de captura (fragmentos de 2s)
   - Extracción de características (MFCC)
   - Predicción con modelo ML
   - Confirmación con buffer

3. **Detección de Activación**
   - Comparar puntuación contra umbral
   - Verificar consistencia en buffer
   - Evaluar duración de voz
   - Activar cliente si coincide

4. **Procesamiento de Comando** (`ifs.py`, `cliente.py`)
   - Recibir entrada del usuario
   - Procesar lógica de intención
   - Generar respuesta contextual

5. **Síntesis y Reproducción** (`voz.py`)
   - Generar audio de respuesta
   - Reproducir mediante TTS
   - Actualizar estado del sistema

6. **Monitoreo Continuo**
   - Verificar conectividad cada 10 minutos
   - Verificar actualizaciones cada 10 minutos
   - Mantener estado del sistema sincronizado

## 📊 Estado del Sistema

El sistema mantiene información en archivos de texto:

- **`txt/version.txt`**: Versión actual instalada
- **`txt/estado_inicio.txt`**: Indica si es primera ejecución
- **`txt/estado_de_red.txt`**: Estado de conectividad (true/false)
- **`txt/personalizacion.txt`**: Configuración del usuario (JSON)

## 🔍 Diagnóstico

El sistema incluye funciones de diagnóstico:

```python
# En voz.py
diagnosticar_voz()  # Verifica todo el sistema de audio
```

Verifica:
- ✅ Disponibilidad de pyttsx3
- ✅ Instalación de edge-tts
- ✅ Reproductores de audio disponibles
- ✅ Estado de conectividad
- ✅ Configuración de idioma

## 🛡️ Manejo de Errores

El sistema implementa:

- Manejo robusto de excepciones en todos los módulos
- Recuperación automática ante fallos
- Fallback a modo offline cuando se pierde conexión
- Respuestas de error claras al usuario
- Logging informativo de eventos

## 📝 Notas de Desarrollo

### Estructura de Modelos
- Los modelos ML se almacenan en `modelos/` y `modelo-es/`
- Formato: `model.h5` (Keras) y `config.pkl` (configuración)
- MFCC: 40 coeficientes, 2048 FFT, 512 hop length

### Procesamiento de Audio
- Normalización de amplitud
- Extracción de características MFCC + deltas
- Padding automático para longitud consistente
- Análisis de energía para detección de voz

### Idiomas Soportados
- `es` - Español de España
- `es_MX` - Español de México
- `en` - Inglés
- `pt` - Portugués
- `fr` - Francés
- `de` - Alemán
- `it` - Italiano

## 📄 Licencia

Ver archivo LICENSE en el repositorio

---

**Creador**: Daniel de Anda  
**Versión**: 1.0.0  
**Última Actualización**: 2026
