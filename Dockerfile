FROM python:3.11-slim

# Instalar solo las dependencias esenciales para OpenCV
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libjpeg-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar los archivos de dependencias
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY . .

# Hacer ejecutable el script de inicio
RUN chmod +x start.sh

# Exponer el puerto
EXPOSE 8000

# Comando para ejecutar la aplicación usando variable PORT
CMD ["bash", "start.sh"]
