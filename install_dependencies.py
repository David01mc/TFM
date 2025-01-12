import subprocess
import sys

# Lista de paquetes que queremos comprobar e instalar si es necesario
required_packages = [
    'requests',
    'beautifulsoup4',
    'selenium',
    'google-generativeai',
    'ibm-watson',
    'pymongo'
]

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

for package in required_packages:
    try:
        __import__(package)
        print(f'{package} ya está instalado.')
    except ImportError:
        print(f'{package} no está instalado. Instalando...')
        install(package)
