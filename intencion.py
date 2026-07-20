import local_libs
import joblib
import os
import pickle
import sys
import re
import logging
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any
import numpy as np

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constantes
RUTA_MODELO = "modelos/medin_alfa.pkl"
RUTA_VECTORIZER = "modelos/vectorizer.pkl"
mi_modelo = None
ultima_intencion = None
vectorizer = None
CONFIANZA_MINIMA = 0.35
HISTORIAL_INTENCIONES = []
MAX_HISTORIAL = 10

class IntencionProcessor:
    """Procesador principal de intenciones"""
    
    def __init__(self, ruta_modelo: str = RUTA_MODELO, confianza_minima: float = CONFIANZA_MINIMA):
        self.ruta_modelo = ruta_modelo
        self.confianza_minima = confianza_minima
        self.modelo = None
        self.vectorizer = None
        self.ultima_intencion = None
        self.historial = []
        
    def cargar_modelo(self) -> bool:
        """Carga el modelo desde el archivo"""
        if not os.path.exists(self.ruta_modelo):
            logger.error(f"No se encontró el archivo: {self.ruta_modelo}")
            return False
            
        logger.info(f"Cargando modelo desde: {self.ruta_modelo}")
        logger.info(f"Tamaño: {os.path.getsize(self.ruta_modelo)} bytes")
        
        # Intentar diferentes métodos de carga
        metodos = [
            ("joblib", lambda: joblib.load(self.ruta_modelo)),
            ("pickle utf-8", lambda: pickle.load(open(self.ruta_modelo, 'rb'), encoding='utf-8')),
            ("pickle latin1", lambda: pickle.load(open(self.ruta_modelo, 'rb'), encoding='latin1')),
            ("pickle normal", lambda: pickle.load(open(self.ruta_modelo, 'rb')))
        ]
        
        for nombre, metodo in metodos:
            try:
                resultado = metodo()
                
                # Procesar diferentes formatos
                if isinstance(resultado, dict):
                    self.modelo = resultado.get('modelo') or resultado.get('classifier')
                    self.vectorizer = resultado.get('vectorizer') or resultado.get('vec')
                    logger.info(f"Modelo cargado desde diccionario usando {nombre}")
                else:
                    self.modelo = resultado
                    logger.info(f"Modelo directo cargado usando {nombre}")
                
                if hasattr(self.modelo, 'predict'):
                    logger.info(f"✅ Modelo cargado exitosamente - Tipo: {type(self.modelo).__name__}")
                    return True
                    
            except Exception as e:
                logger.warning(f"Método {nombre} falló: {str(e)[:100]}")
                continue
        
        logger.error("No se pudo cargar el modelo con ningún método")
        return False
    
    def preprocesar(self, texto: str) -> str:
        """Preprocesa el texto para el modelo"""
        if not texto:
            return ""
        
        # Convertir a string y limpiar
        texto = str(texto).lower().strip()
        
        # Eliminar caracteres especiales pero mantener acentos
        texto = re.sub(r'[^\w\sáéíóúñü]', ' ', texto)
        
        # Eliminar espacios múltiples
        texto = re.sub(r'\s+', ' ', texto).strip()
        
        return texto
    
    def obtener_confianza(self, X) -> Tuple[float, Any, Optional[List]]:
        """Obtiene la confianza de la predicción"""
        try:
            # Asegurar formato correcto
            if isinstance(X, str):
                X = [X]
            
            # Para modelos con predict_proba
            if hasattr(self.modelo, 'predict_proba'):
                try:
                    probs = self.modelo.predict_proba(X)[0]
                    confianza = max(probs)
                    prediccion = self.modelo.predict(X)[0]
                    return confianza, prediccion, probs.tolist()
                except Exception as e:
                    logger.warning(f"Error en predict_proba: {e}")
            
            # Para modelos con decision_function
            if hasattr(self.modelo, 'decision_function'):
                try:
                    scores = self.modelo.decision_function(X)[0]
                    # Normalizar a probabilidades
                    exp_scores = np.exp(scores - np.max(scores))
                    probs = (exp_scores / exp_scores.sum()).tolist()
                    confianza = max(probs)
                    prediccion = self.modelo.predict(X)[0]
                    return confianza, prediccion, probs
                except Exception as e:
                    logger.warning(f"Error en decision_function: {e}")
            
            # Fallback simple
            prediccion = self.modelo.predict(X)[0]
            return 1.0, prediccion, None
            
        except Exception as e:
            logger.error(f"Error calculando confianza: {e}")
            return 0.0, None, None
    
    def procesar(self, texto: str, usar_vectorizer: bool = False) -> Dict[str, Any]:
        """Procesa el texto y retorna la intención con metadata"""
        # Validaciones
        if self.modelo is None:
            logger.error("Modelo no cargado")
            return self._respuesta_error("modelo_no_cargado")
        
        if not texto:
            logger.warning("Texto vacío")
            return self._respuesta_error("texto_vacio")
        
        # Preprocesar
        texto_limpio = self.preprocesar(texto)
        if not texto_limpio:
            return self._respuesta_error("texto_limpio_vacio")
        
        logger.info(f"Procesando: '{texto_limpio}'")
        
        try:
            # Transformar con vectorizador si es necesario
            if usar_vectorizer and self.vectorizer:
                X = self.vectorizer.transform([texto_limpio])
            else:
                X = [texto_limpio]
            
            # Obtener predicción y confianza
            confianza, intencion, probabilidades = self.obtener_confianza(X)
            
            # Verificar confianza mínima
            if confianza < self.confianza_minima:
                logger.warning(f"Confianza baja ({confianza:.2f}) para: {texto_limpio}")
                intencion = "conversacion_ai"
            
            # Actualizar historial
            self.ultima_intencion = intencion
            self._actualizar_historial(texto_limpio, intencion, confianza)
            
            # Preparar respuesta
            respuesta = {
                "exito": True,
                "texto_original": texto,
                "texto_procesado": texto_limpio,
                "intencion": intencion,
                "confianza": confianza,
                "probabilidades": probabilidades,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Intención: {intencion} (confianza: {confianza:.2f})")
            return respuesta
            
        except Exception as e:
            logger.error(f"Error crítico: {type(e).__name__}: {e}")
            return self._respuesta_error(str(e))
    
    def _respuesta_error(self, error_msg: str) -> Dict[str, Any]:
        """Genera respuesta de error"""
        return {
            "exito": False,
            "error": error_msg,
            "intencion": "conversacion_ai",
            "confianza": 0.0,
            "timestamp": datetime.now().isoformat()
        }
    
    def _actualizar_historial(self, texto: str, intencion: str, confianza: float):
        """Actualiza el historial de intenciones"""
        self.historial.append({
            "texto": texto,
            "intencion": intencion,
            "confianza": confianza,
            "timestamp": datetime.now().isoformat()
        })
        
        # Mantener tamaño limitado
        if len(self.historial) > MAX_HISTORIAL:
            self.historial.pop(0)
    
    def obtener_historial(self) -> List[Dict]:
        """Retorna el historial de intenciones"""
        return self.historial.copy()
    
    def obtener_ultima_intencion(self) -> Optional[str]:
        """Retorna la última intención procesada"""
        return self.ultima_intencion
    
    def obtener_info_modelo(self) -> Dict[str, Any]:
        """Retorna información del modelo"""
        if self.modelo is None:
            return {"cargado": False}
        
        info = {
            "cargado": True,
            "tipo": type(self.modelo).__name__,
            "tiene_predict_proba": hasattr(self.modelo, 'predict_proba'),
            "tiene_decision_function": hasattr(self.modelo, 'decision_function'),
            "vectorizer": type(self.vectorizer).__name__ if self.vectorizer else None,
            "confianza_minima": self.confianza_minima
        }
        
        # Intentar obtener clases si es clasificador
        if hasattr(self.modelo, 'classes_'):
            info["clases"] = self.modelo.classes_.tolist()
        
        return info

# Lista completa de intenciones soportadas
INTENCIONES_SOPORTADAS = {
    "informacion": ["hora", "fecha", "clima", "investigacion", "traductor"],
    "multimedia": ["musica_usb", "musica_usb_especifica", "musica_online", "detener_musica"],
    "recordatorios": ["alarma", "recordatorio", "guardar_nota", "leer_nota"],
    "listas": ["agregar_lista", "leer_lista", "quitar_lista", "limpiar_lista"],
    "agenda": ["agregar_evento", "consultar_agenda", "eliminar_evento"],
    "otros": ["smart_home", "conversacion_normal", "conversacion_ai"]
}

def listar_intenciones_soporte(detallado: bool = False) -> Dict[str, Any]:
    """Devuelve las intenciones soportadas por el modelo"""
    if detallado:
        return {
            "total": sum(len(v) for v in INTENCIONES_SOPORTADAS.values()),
            "categorias": INTENCIONES_SOPORTADAS
        }
    else:
        return [intencion for sublist in INTENCIONES_SOPORTADAS.values() for intencion in sublist]

# Instancia global del procesador
procesador = IntencionProcessor()

# Funciones de compatibilidad con el código original
def cargar_modelo_inicial() -> bool:
    """Funcióon de compatibilidad para cargar el modelo"""
    return procesador.cargar_modelo()

def verificar_modelo() -> bool:
    """Verifica si el modelo está cargado"""
    return procesador.modelo is not None

def obtener_ultima_intencion() -> Optional[str]:
    """Obtiene la última intención procesada"""
    return procesador.obtener_ultima_intencion()

def preprocesar_texto(texto: str) -> str:
    """Preprocesa texto (función de compatibilidad)"""
    return procesador.preprocesar(texto)

def procesar_intencion(texto_entrada: str) -> str:
    """Procesa intención y retorna el nombre de la intención"""
    resultado = procesador.procesar(texto_entrada)
    return resultado.get("intencion", "conversacion_ai")

def obtener_confianza(modelo, X) -> Tuple[float, Any, Optional[List]]:
    """Obtiene confianza (función de compatibilidad)"""
    return procesador.obtener_confianza(X)

def obtener_info_completa(texto: str) -> Dict[str, Any]:
    """Obtiene información completa del procesamiento"""
    return procesador.procesar(texto)

# Inicialización
print("🔧 Inicializando módulo de intenciones...")
cargar_modelo_inicial()

# Prueba si se ejecuta directamente
if __name__ == "__main__":
    print("\n" + "="*60)
    print("PRUEBA DEL MÓDULO DE INTENCIONES")
    print("="*60)
    
    if procesador.modelo is not None:
        print("✅ Modelo cargado correctamente")
        info = procesador.obtener_info_modelo()
        print(f"📊 Tipo: {info['tipo']}")
        print(f"🎯 Confianza mínima: {info['confianza_minima']:.0%}")
        
        if info.get('clases'):
            print(f"📚 Clases disponibles: {len(info['clases'])}")
        
        # Probar frases
        frases_prueba = [
            "qué hora es",
            "pon música de rock",
            "cómo está el clima en Madrid",
            "guarda esta nota importante",
            "programa una alarma para las 7am",
            "hola cómo estás",
            "qué opinas de la inteligencia artificial",
            "agrega pan a la lista de compras",
            "qué tengo en mi agenda para mañana",
            "enciende las luces del salón"
        ]
        
        print(f"\n🧪 Probando clasificación:")
        print("-" * 60)
        
        for frase in frases_prueba:
            resultado = procesador.procesar(frase)
            if resultado["exito"]:
                confianza_pct = resultado["confianza"] * 100
                print(f"📝 '{frase}'")
                print(f"   → {resultado['intencion']} (confianza: {confianza_pct:.1f}%)")
            else:
                print(f"❌ Error procesando '{frase}': {resultado.get('error')}")
            print()
        
        # Mostrar estadísticas
        print("="*60)
        print("📊 ESTADÍSTICAS")
        print("="*60)
        print(f"Historial de procesamiento: {len(procesador.obtener_historial())} items")
        
    else:
        print("❌ No se pudo cargar el modelo")
        print("\n📦 Soluciones posibles:")
        print("   1. Verifica que el archivo existe en 'modelos/medin_alfa.pkl'")
        print("   2. Instala dependencias: pip install hmmlearn scikit-learn joblib numpy")
        print("   3. Verifica permisos de lectura del archivo")
        print("   4. Reentrena el modelo si está corrupto")
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
