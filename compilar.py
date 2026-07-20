#!/usr/bin/env python3
"""
Script completo que:
1. Compila solo los archivos .py del proyecto (no librerías)
2. Ejecuta main.bin
3. Crea nova_unificado.py eliminando imports de archivos compilados
"""

import os
import sys
import subprocess
import shutil
import glob
import re
import time

# ============================================
# CONFIGURACIÓN
# ============================================

# Archivos a compilar (solo los del proyecto, NO librerías)
ARCHIVOS_A_COMPILAR = [
    "voz.py",
    "local_libs.py",
    "funciones.py",
    "intencion.py",
    "comunicacion.py",
    "hadware.py",
    "wake.py",
    "cliente.py",
    "errores.py",
    "ifs.py",
    "audio.py",
    "main.py"
]

# Archivos que se sabe que tienen problemas (compilar por separado)
ARCHIVOS_PROBLEMATICOS = [
    "funciones.py",
    "wake.py"
]

# Excluir estos archivos
EXCLUIR = {
    "compilar.py", "unificar.py", "crear_binarios.py", 
    "organizar_proyecto.py", "setup.py", "config.py"
}

# ============================================
# FUNCIÓN 1: COMPILAR BINARIOS
# ============================================

def instalar_pyinstaller():
    """Instala PyInstaller si no está disponible"""
    try:
        __import__('PyInstaller')
        print("✅ PyInstaller ya instalado")
        return True
    except ImportError:
        print("📦 Instalando PyInstaller...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller", "--quiet"], 
                         capture_output=True, check=True, timeout=60)
            print("✅ PyInstaller instalado")
            return True
        except:
            print("❌ No se pudo instalar PyInstaller")
            return False

def limpiar_compilaciones_anteriores():
    """Limpia compilaciones anteriores"""
    print("\n🗑️  Limpiando compilaciones anteriores...")
    carpetas = ["dist", "build", "__pycache__"]
    for carpeta in carpetas:
        if os.path.exists(carpeta):
            shutil.rmtree(carpeta, ignore_errors=True)
    
    for archivo in glob.glob("*.spec"):
        os.remove(archivo)

def compilar_binario(archivo, timeout=300):
    """Compila un archivo .py a binario con timeout más largo"""
    nombre = os.path.splitext(archivo)[0]
    print(f"   🔨 Compilando: {archivo} -> {nombre}.bin")
    
    # Para archivos problemáticos, usar menos optimizaciones
    if archivo in ARCHIVOS_PROBLEMATICOS:
        cmd = [
            "pyinstaller",
            "--onefile",
            "--name", f"{nombre}.bin",
            "--distpath", "dist",
            "--workpath", "build",
            "--specpath", "build",
            "--log-level", "WARN",
            "--noconfirm",
            "--noupx",  # No comprimir (más rápido)
            archivo
        ]
    else:
        cmd = [
            "pyinstaller",
            "--onefile",
            "--name", f"{nombre}.bin",
            "--distpath", "dist",
            "--workpath", "build",
            "--specpath", "build",
            "--log-level", "ERROR",
            "--noconfirm",
            archivo
        ]
    
    try:
        # Aumentar timeout a 5 minutos para archivos grandes
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        
        if result.returncode == 0:
            # Verificar que se creó el binario
            posibles_rutas = [
                f"dist/{nombre}.bin",
                f"dist/{nombre}",
                f"dist/{nombre}.exe"
            ]
            for ruta in posibles_rutas:
                if os.path.exists(ruta):
                    if not ruta.endswith('.bin'):
                        os.rename(ruta, f"dist/{nombre}.bin")
                    os.chmod(f"dist/{nombre}.bin", 0o755)
                    print(f"      ✅ {nombre}.bin creado")
                    return True
            
            print(f"      ⚠️ Binario no encontrado después de compilar")
            return False
        else:
            print(f"      ❌ Error: {result.stderr[:200] if result.stderr else 'Error desconocido'}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"      ⏰ Timeout ({timeout}s) - {archivo} es muy grande")
        print(f"      💡 Intenta compilarlo manualmente:")
        print(f"         pyinstaller --onefile {archivo}")
        return False
    except Exception as e:
        print(f"      ❌ Excepción: {e}")
        return False

def compilar_binario_separado(archivo):
    """Compila un archivo por separado con manejo especial"""
    nombre = os.path.splitext(archivo)[0]
    print(f"\n   🔧 Compilando por separado: {archivo}")
    
    # Usar subprocess directamente sin capturar salida
    cmd = f'pyinstaller --onefile --name {nombre}.bin --noconfirm {archivo}'
    
    try:
        # Usar shell=True para mejor compatibilidad
        result = subprocess.run(cmd, shell=True, timeout=600)
        
        if result.returncode == 0:
            if os.path.exists(f"dist/{nombre}.bin"):
                os.chmod(f"dist/{nombre}.bin", 0o755)
                print(f"      ✅ {nombre}.bin creado")
                return True
        return False
    except Exception as e:
        print(f"      ❌ Error: {e}")
        return False

def compilar_todos_binarios():
    """Compila todos los archivos del proyecto"""
    print("\n🔨 COMPILANDO BINARIOS")
    print("="*50)
    
    # Filtrar archivos que existen
    archivos_existentes = []
    for archivo in ARCHIVOS_A_COMPILAR:
        if os.path.exists(archivo) and archivo not in EXCLUIR:
            archivos_existentes.append(archivo)
        else:
            print(f"⚠️ No existe: {archivo}")
    
    print(f"\n📦 Archivos a compilar: {len(archivos_existentes)}")
    for a in archivos_existentes:
        print(f"   - {a}")
    
    # Crear directorio dist
    os.makedirs("dist", exist_ok=True)
    
    # Compilar cada archivo
    exitosos = []
    fallidos = []
    
    for archivo in archivos_existentes:
        # Para archivos problemáticos, usar método separado
        if archivo in ARCHIVOS_PROBLEMATICOS:
            if compilar_binario_separado(archivo):
                exitosos.append(archivo)
            else:
                fallidos.append(archivo)
        else:
            if compilar_binario(archivo):
                exitosos.append(archivo)
            else:
                fallidos.append(archivo)
        time.sleep(1)  # Pequeña pausa entre compilaciones
    
    print(f"\n✅ Compilados: {len(exitosos)}/{len(archivos_existentes)} binarios")
    
    if fallidos:
        print(f"\n⚠️ Fallaron: {len(fallidos)}")
        for f in fallidos:
            print(f"   - {f}")
    
    # Listar binarios creados
    print("\n📁 Binarios en dist/:")
    binarios_lista = []
    if os.path.exists("dist"):
        for binario in sorted(os.listdir("dist")):
            if binario.endswith(".bin"):
                tamaño = os.path.getsize(f"dist/{binario}") / 1024 / 1024
                binarios_lista.append(binario)
                print(f"   - {binario} ({tamaño:.1f} MB)")
    
    return exitosos, binarios_lista

# ============================================
# FUNCIÓN 2: EJECUTAR MAIN.BIN
# ============================================

def ejecutar_main_bin():
    """Ejecuta el binario principal main.bin"""
    print("\n🚀 EJECUTANDO MAIN.BIN")
    print("="*50)
    
    ruta_main_bin = "dist/main.bin"
    
    if not os.path.exists(ruta_main_bin):
        # Buscar alternativas
        alternativas = ["dist/main", "main.bin", "main.exe"]
        for alt in alternativas:
            if os.path.exists(alt):
                ruta_main_bin = alt
                break
        else:
            print("❌ No se encontró main.bin")
            print("   Asegúrate de que main.py se compiló correctamente")
            return False
    
    print(f"▶️ Ejecutando: {ruta_main_bin}")
    print("   (Para salir, escribe 'salir' o presiona Ctrl+C)")
    print("-"*50)
    
    try:
        # Ejecutar el binario
        subprocess.run([ruta_main_bin], check=False)
        return True
    except KeyboardInterrupt:
        print("\n\n👋 Ejecución interrumpida")
        return True
    except Exception as e:
        print(f"❌ Error al ejecutar: {e}")
        return False

# ============================================
# FUNCIÓN 3: CREAR NOVA_UNIFICADO.PY
# ============================================

def obtener_archivos_locales():
    """Obtiene todos los archivos .py locales (no librerías)"""
    archivos = []
    for archivo in os.listdir("."):
        if archivo.endswith(".py"):
            if archivo not in EXCLUIR:
                if archivo not in ARCHIVOS_A_COMPILAR:
                    archivos.append(archivo)
    return archivos

def obtener_nombres_binarios(binarios_lista):
    """Obtiene los nombres de los binarios compilados"""
    nombres = set()
    for binario in binarios_lista:
        nombre = binario.replace(".bin", "")
        nombres.add(nombre)
    return nombres

def limpiar_imports_locales(contenido, nombres_binarios):
    """Elimina imports de archivos que ya están compilados a binarios"""
    lineas = contenido.split('\n')
    nuevas_lineas = []
    imports_eliminados = []
    
    for linea in lineas:
        # Buscar imports de módulos locales
        match = re.match(r'^import\s+(\w+)$', linea.strip())
        if match:
            nombre = match.group(1)
            if nombre in nombres_binarios:
                imports_eliminados.append(nombre)
                nuevas_lineas.append(f"# {linea}  # Eliminado - usa {nombre}.bin")
                continue
        
        match = re.match(r'^from\s+(\w+)\s+import\s+(.+)$', linea.strip())
        if match:
            nombre = match.group(1)
            if nombre in nombres_binarios:
                imports_eliminados.append(nombre)
                nuevas_lineas.append(f"# {linea}  # Eliminado - usa {nombre}.bin")
                continue
        
        nuevas_lineas.append(linea)
    
    return '\n'.join(nuevas_lineas), imports_eliminados

def extraer_definiciones(contenido):
    """Extrae solo definiciones de funciones y clases"""
    lineas = contenido.split('\n')
    definiciones = []
    en_definicion = False
    definicion_actual = []
    indentacion_base = 0
    
    for i, linea in enumerate(lineas):
        if re.match(r'^(def |class )', linea):
            en_definicion = True
            definicion_actual = [linea]
            indentacion_base = len(linea) - len(linea.lstrip())
        elif en_definicion:
            definicion_actual.append(linea)
            # Verificar fin
            if i + 1 < len(lineas):
                sig = lineas[i + 1]
                if sig and not sig[0].isspace() and not re.match(r'^(def |class |@)', sig):
                    definiciones.extend(definicion_actual)
                    en_definicion = False
                    definicion_actual = []
    
    return '\n'.join(definiciones)

def crear_nova_unificado(binarios_exitosos, binarios_lista):
    """Crea el archivo nova_unificado.py"""
    
    print("\n📝 CREANDO NOVA_UNIFICADO.PY")
    print("="*50)
    
    archivos_locales = obtener_archivos_locales()
    nombres_binarios = obtener_nombres_binarios(binarios_lista)
    
    print(f"📦 Binarios disponibles: {len(nombres_binarios)}")
    for b in sorted(nombres_binarios):
        print(f"   - {b}.bin")
    
    print(f"📄 Archivos locales restantes: {len(archivos_locales)}")
    
    salida = "nova_unificado.py"
    
    with open(salida, 'w', encoding='utf-8') as out:
        out.write('#!/usr/bin/env python3\n')
        out.write('"""\n')
        out.write('NOVA - Asistente Inteligente (Unificado)\n')
        out.write('Los módulos compilados a binarios han sido eliminados\n')
        out.write('"""\n\n')
        
        out.write('# ============================================\n')
        out.write('# IMPORTS ESTÁNDAR\n')
        out.write('# ============================================\n')
        out.write('import os\n')
        out.write('import sys\n')
        out.write('import time\n')
        out.write('import json\n')
        out.write('import re\n')
        out.write('import threading\n')
        out.write('import subprocess\n')
        out.write('from datetime import datetime, timedelta\n\n')
        
        out.write('# ============================================\n')
        out.write('# FUNCIÓN DE VOZ\n')
        out.write('# ============================================\n')
        out.write('def hablar(texto):\n')
        out.write('    print(f"🔊 Nova: {texto}")\n\n')
        
        out.write('# ============================================\n')
        out.write('# CÓDIGO DE MÓDULOS LOCALES\n')
        out.write('# ============================================\n')
        
        for archivo in archivos_locales:
            out.write(f'\n# ========== {archivo} ==========\n')
            
            with open(archivo, 'r', encoding='utf-8') as f:
                contenido = f.read()
            
            # Limpiar imports
            contenido, eliminados = limpiar_imports_locales(contenido, nombres_binarios)
            
            if eliminados:
                out.write(f'# Imports eliminados: {", ".join(eliminados)}\n')
            
            # Limpiar shebang
            lineas = contenido.split('\n')
            lineas_limpias = []
            for linea in lineas:
                if not linea.startswith('#!/usr/bin/env'):
                    if not linea.startswith('# -*- coding:'):
                        lineas_limpias.append(linea)
            
            contenido = '\n'.join(lineas_limpias)
            definiciones = extraer_definiciones(contenido)
            
            if definiciones.strip():
                out.write(definiciones)
                out.write('\n')
        
        out.write('\n# ============================================\n')
        out.write('# FUNCIÓN PRINCIPAL\n')
        out.write('# ============================================\n')
        out.write('def main():\n')
        out.write('    print("\\n" + "="*50)\n')
        out.write('    print("🎤 NOVA - Asistente Inteligente")\n')
        out.write('    print("="*50)\n')
        out.write('    print("Comandos: hora, fecha, salir")\n')
        out.write('    print("="*50))\n\n')
        out.write('    hablar("Hola, soy Nova")\n\n')
        out.write('    while True:\n')
        out.write('        try:\n')
        out.write('            entrada = input("\\n👤 Tú: ").strip()\n')
        out.write('            if not entrada:\n')
        out.write('                continue\n')
        out.write('            if entrada.lower() in ["salir", "exit", "quit"]:\n')
        out.write('                hablar("Hasta luego")\n')
        out.write('                break\n')
        out.write('            print(f"🤖 Nova: Recibí: {entrada}")\n')
        out.write('        except KeyboardInterrupt:\n')
        out.write('            print("\\n👋 Saliendo...")\n')
        out.write('            break\n\n')
        
        out.write('if __name__ == "__main__":\n')
        out.write('    main()\n')
    
    print(f"\n✅ Creado: {salida}")
    
    with open(salida, 'r') as f:
        lineas = len(f.readlines())
    tamaño = os.path.getsize(salida) / 1024
    print(f"📊 Estadísticas: {lineas} líneas, {tamaño:.1f} KB")
    
    return salida

# ============================================
# FUNCIÓN PRINCIPAL
# ============================================

def main():
    print("🚀 SCRIPT COMPLETO DE NOVA")
    print("="*50)
    print("\nEste script:")
    print("   1. Compila binarios (con timeout de 5 minutos)")
    print("   2. Ejecuta main.bin")
    print("   3. Crea nova_unificado.py")
    print()
    
    input("Presiona Enter para continuar...")
    
    if not instalar_pyinstaller():
        print("❌ No se puede continuar")
        return
    
    limpiar_compilaciones_anteriores()
    exitosos, binarios_lista = compilar_todos_binarios()
    
    if exitosos:
        respuesta = input("\n¿Deseas ejecutar main.bin? (s/N): ").strip().lower()
        if respuesta in ['s', 'si', 'sí', 'yes', 'y']:
            ejecutar_main_bin()
    
    respuesta = input("\n¿Deseas crear nova_unificado.py? (s/N): ").strip().lower()
    if respuesta in ['s', 'si', 'sí', 'yes', 'y']:
        crear_nova_unificado(exitosos, binarios_lista)
    
    print("\n" + "="*50)
    print("✅ PROCESO COMPLETADO")
    print("="*50)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Proceso cancelado")