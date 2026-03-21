#!/bin/bash

# Cargar variables de entorno desde .env si existe
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Obtener el puerto de la variable de entorno o usar 8000 por defecto
PORT=${PORT:-8000}

echo "Starting SignaApi on port $PORT"

# Ejecutar la aplicación
exec uvicorn api.main:app --host 0.0.0.0 --port $PORT --log-level info
