# Usar una imagen base oficial de Python
FROM python:3.9-slim

# Instalar dependencias del sistema necesarias para Chrome y Selenium
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    xvfb \
    chromium \
    chromium-driver

# Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiar el código Python y el archivo de dependencias al contenedor
COPY Cadiz_WS.py .
COPY install_dependencies.py .

# Ejecutar el script para instalar las dependencias de Python
RUN python install_dependencies.py

# Configurar las variables de entorno para Chrome y ChromeDriver
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROME_DRIVER=/usr/bin/chromedriver

# Establecer el comando predeterminado, que tomará una URL como argumento
CMD ["python", "Cadiz_WS.py"]
