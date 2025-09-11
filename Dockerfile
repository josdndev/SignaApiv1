# Usa una imagen base de Python 3.11 optimizada
FROM python:3.11-slim

# Instala las dependencias del sistema necesarias para OpenCV y otras bibliotecas.
# Se han actualizado los nombres de los paquetes para la compatibilidad con Debian Bookworm.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libgtk-3-0 \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libxvidcore-dev \
    libx264-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libatlas3-base \
    gfortran \
    && rm -rf /var/lib/apt/lists/*

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copia los archivos de dependencias de Python
COPY requirements.txt .

# Instala las dependencias de Python especificadas en requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código de la aplicación
COPY . .

# Hace que el script de inicio sea ejecutable
RUN chmod +x start.sh

# Expone el puerto por el que se ejecutará la aplicación
EXPOSE 8000

# Define el comando principal para ejecutar la aplicación
CMD ["./start.sh"]