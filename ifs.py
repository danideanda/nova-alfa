import local_libs
import local_libs
import time
import sys
import os
from voz import hablar

llm = None
SYSTEM_BASE = None
params = None

def verificar_red():
    try:
        if os.path.exists("txt/estado_de_red.txt"):
            with open("txt/estado_de_red.txt", "r") as f:
                return f.read().strip().lower() == "true"
        return False
    except:
        return False

def inicializar_modelo(modelo, system_prompt, parametros):
    global llm, SYSTEM_BASE, params
    llm = modelo
    SYSTEM_BASE = system_prompt
    params = parametros
    print("✅ Modelo inicializado en ifs.py")

def procesar_logica_usuario(input_usuario):
    from intencion import procesar_intencion
    from funciones import ( 
        musica_usb,
        musica_online,
        reproduccion_especifica_usb,
        obtener_hora,
        obtener_fecha,
        tomar_nota,
        leer_nota,
        conversacion_ai,
        obtener_clima,
        investigar_tema,
        traductor_ingles,
        abrir_roku,
        programar_alarma,
        nota_tiempo,
        detener,
        agregar_a_lista,
        leer_lista,
        quitar_de_lista,
        limpiar_lista,
        agregar_evento,
        consultar_agenda,
        eliminar_evento,
        controlar_dispositivo
    )
    
    input_limpio = input_usuario.lower().strip()
    hay_red = verificar_red()
    
    intencion = procesar_intencion(input_limpio)
    
    if intencion == "hora":
        print("intención: obtener hora")
        return obtener_hora()
    
    elif intencion == "fecha":
        print("intención: obtener fecha")
        return obtener_fecha()
    
    elif intencion == "musica_usb":
        print("intención: reproducir música USB")
        return musica_usb()
    
    elif intencion == "musica_usb_especifica":
        print("intención: reproducir canción específica USB")
        return reproduccion_especifica_usb(input_limpio)
    
    elif intencion == "musica":
        print("intención: reproducir música online")
        if not hay_red:
            hablar("no tengo conexión a internet, buscando en usb conectada")
            musica_usb(input_limpio)
        return musica_online(input_limpio)
    
    elif intencion == "clima":
        print("intención: consultar clima")
        if not hay_red:
            return "sin conexión a internet, no puedo consultar el clima"
        return obtener_clima()
    
    elif intencion == "investigacion":
        print("intención: investigar tema")
        if not hay_red:
            return conversacion_ai(input_limpio)
        return investigar_tema(input_limpio)
    
    elif intencion == "traductor":
        print("intención: traducir a inglés")
        if not hay_red:
            return "sin conexión a internet, no puedo traducir"
        return traductor_ingles(input_limpio)
    
    elif intencion == "abrir_roku":
        print("intención: abrir app en Roku")
        if not hay_red:
            return "sin conexión a internet, no puedo controlar el Roku"
        return abrir_roku(intencion)
    
    elif intencion == "alarma_generar":
        print("intención: programar alarma")
        return programar_alarma(input_limpio)
    
    elif intencion == "recordatorio":
        print("intención: programar recordatorio")
        return nota_tiempo(input_limpio)
    
    elif intencion == "guardar_nota":
        print("intención: guardar nota")
        return tomar_nota(input_limpio)
    
    elif intencion == "leer_nota":
        print("intención: leer nota guardada")
        return leer_nota()
    
    elif intencion == "detener_musica":
        print("intención: detener música")
        return detener()
    
    elif intencion == "agregar_lista":
        print("intención: agregar a lista de compras")
        return agregar_a_lista(input_limpio)
    
    elif intencion == "leer_lista":
        print("intención: leer lista de compras")
        return leer_lista()
    
    elif intencion == "quitar_lista":
        print("intención: quitar de lista de compras")
        return quitar_de_lista(input_limpio)
    
    elif intencion == "limpiar_lista":
        print("intención: limpiar lista de compras")
        return limpiar_lista()
    
    elif intencion == "agregar_evento":
        print("intención: agregar evento")
        return agregar_evento(input_limpio)
    
    elif intencion == "consultar_agenda":
        print("intención: consultar agenda")
        return consultar_agenda(input_limpio)
    
    elif intencion == "eliminar_evento":
        print("intención: eliminar evento")
        return eliminar_evento(input_limpio)
    
    elif intencion == "smart_home":
        print("intención: controlar dispositivo")
        return controlar_dispositivo(input_limpio)
    
    elif intencion == "conversacion_ai":
        print("intención: conversación con IA")
        return conversacion_ai(input_limpio)
    
    else:
        print(f"intención no reconocida: {intencion}")
        return conversacion_ai(input_limpio)

def procesar_respuesta_ia(texto):
    return texto.strip() if texto else ""
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
