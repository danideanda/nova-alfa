import os
import sys

DEFAULT_LOCAL_LIBS = "libs:lib:pythonlibs"


def setup_local_libs():
    paths = os.environ.get("LOCAL_PY_LIBS", DEFAULT_LOCAL_LIBS)
    for lib_dir in paths.split(":"):
        if not lib_dir:
            continue
        lib_path = os.path.abspath(lib_dir)
        if os.path.isdir(lib_path) and lib_path not in sys.path:
            sys.path.insert(0, lib_path)


setup_local_libs()

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
