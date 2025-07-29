"""
Manejadores de eventos y errores para SignaApi
"""

import logging
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

# Configurar logger específico para errores
error_logger = logging.getLogger("signaapi.errors")
error_logger.setLevel(logging.ERROR)

# Handler para archivo de errores
file_handler = logging.FileHandler("error_logs.log")
file_handler.setLevel(logging.ERROR)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
file_handler.setFormatter(formatter)
error_logger.addHandler(file_handler)

class SignaApiError(Exception):
    """Clase base para errores personalizados de SignaApi"""
    def __init__(self, message: str, error_code: str = None, details: Dict[str, Any] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

class ValidationError(SignaApiError):
    """Error de validación de datos"""
    pass

class DatabaseError(SignaApiError):
    """Error de base de datos"""
    pass

class AuthenticationError(SignaApiError):
    """Error de autenticación"""
    pass

class ResourceNotFoundError(SignaApiError):
    """Error de recurso no encontrado"""
    pass

class DuplicateResourceError(SignaApiError):
    """Error de recurso duplicado"""
    pass

def log_error(error: Exception, context: Dict[str, Any] = None):
    """Función para logging de errores con contexto"""
    error_data = {
        "timestamp": datetime.now().isoformat(),
        "error_type": type(error).__name__,
        "error_message": str(error),
        "traceback": traceback.format_exc(),
        "context": context or {}
    }
    
    error_logger.error(f"Error logged: {error_data}")
    return error_data

def create_error_response(
    error: Exception, 
    status_code: int = 500, 
    include_traceback: bool = False
) -> Dict[str, Any]:
    """Crear respuesta de error estandarizada"""
    error_data = {
        "error": type(error).__name__,
        "message": str(error),
        "timestamp": datetime.now().isoformat(),
        "status_code": status_code
    }
    
    if include_traceback:
        error_data["traceback"] = traceback.format_exc()
    
    if hasattr(error, 'details'):
        error_data["details"] = error.details
    
    return error_data

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Manejador de errores de validación"""
    error_data = log_error(exc, {
        "request_method": request.method,
        "request_url": str(request.url),
        "validation_errors": exc.errors()
    })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=create_error_response(
            exc, 
            status.HTTP_422_UNPROCESSABLE_ENTITY
        )
    )

async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Manejador de errores HTTP"""
    error_data = log_error(exc, {
        "request_method": request.method,
        "request_url": str(request.url),
        "status_code": exc.status_code
    })
    
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(
            exc, 
            exc.status_code
        )
    )

async def general_exception_handler(request: Request, exc: Exception):
    """Manejador de errores generales"""
    error_data = log_error(exc, {
        "request_method": request.method,
        "request_url": str(request.url),
        "client_host": request.client.host if request.client else "Unknown"
    })
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=create_error_response(
            exc, 
            status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    )

def validate_required_fields(data: Dict[str, Any], required_fields: list) -> None:
    """Validar campos requeridos"""
    missing_fields = []
    for field in required_fields:
        if field not in data or data[field] is None or str(data[field]).strip() == "":
            missing_fields.append(field)
    
    if missing_fields:
        raise ValidationError(
            f"Campos requeridos faltantes: {', '.join(missing_fields)}",
            "MISSING_FIELDS",
            {"missing_fields": missing_fields}
        )

def validate_email(email: str) -> None:
    """Validar formato de email"""
    if not email or '@' not in email or '.' not in email:
        raise ValidationError(
            "Formato de email inválido",
            "INVALID_EMAIL",
            {"email": email}
        )

def validate_age(edad: int) -> None:
    """Validar edad"""
    if not isinstance(edad, int) or edad < 0 or edad > 150:
        raise ValidationError(
            "La edad debe ser un número entre 0 y 150",
            "INVALID_AGE",
            {"edad": edad}
        )

def validate_string_length(value: str, field_name: str, min_length: int = 1, max_length: int = None) -> None:
    """Validar longitud de string"""
    if not value or len(value.strip()) < min_length:
        raise ValidationError(
            f"El campo {field_name} debe tener al menos {min_length} caracteres",
            "INVALID_LENGTH",
            {"field": field_name, "min_length": min_length, "value": value}
        )
    
    if max_length and len(value.strip()) > max_length:
        raise ValidationError(
            f"El campo {field_name} no puede tener más de {max_length} caracteres",
            "INVALID_LENGTH",
            {"field": field_name, "max_length": max_length, "value": value}
        )

def validate_file_upload(file, allowed_extensions: list, max_size_mb: int = 10) -> None:
    """Validar archivo subido"""
    if not file or not file.filename:
        raise ValidationError(
            "Archivo no válido",
            "INVALID_FILE",
            {"filename": file.filename if file else None}
        )
    
    # Validar extensión
    file_extension = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
    if file_extension not in allowed_extensions:
        raise ValidationError(
            f"Tipo de archivo no soportado. Formatos permitidos: {', '.join(allowed_extensions)}",
            "INVALID_FILE_TYPE",
            {"filename": file.filename, "extension": file_extension, "allowed": allowed_extensions}
        )
    
    # Validar tamaño (se valida después de leer el archivo)
    if hasattr(file, 'size') and file.size > max_size_mb * 1024 * 1024:
        raise ValidationError(
            f"El archivo es demasiado grande. Tamaño máximo: {max_size_mb}MB",
            "FILE_TOO_LARGE",
            {"filename": file.filename, "size": file.size, "max_size": max_size_mb * 1024 * 1024}
        )

def handle_database_operation(operation_name: str, operation_func, *args, **kwargs):
    """Wrapper para operaciones de base de datos con manejo de errores"""
    try:
        return operation_func(*args, **kwargs)
    except Exception as e:
        error_data = log_error(e, {
            "operation": operation_name,
            "args": args,
            "kwargs": kwargs
        })
        
        if "UNIQUE constraint failed" in str(e):
            raise DuplicateResourceError(
                "El recurso ya existe en la base de datos",
                "DUPLICATE_RESOURCE",
                {"operation": operation_name}
            )
        elif "FOREIGN KEY constraint failed" in str(e):
            raise ValidationError(
                "Referencia a recurso inexistente",
                "FOREIGN_KEY_ERROR",
                {"operation": operation_name}
            )
        else:
            raise DatabaseError(
                f"Error en operación de base de datos: {operation_name}",
                "DATABASE_ERROR",
                {"operation": operation_name, "original_error": str(e)}
            )

def create_success_response(data: Any, message: str = "Operación exitosa") -> Dict[str, Any]:
    """Crear respuesta de éxito estandarizada"""
    return {
        "message": message,
        "data": data,
        "timestamp": datetime.now().isoformat(),
        "success": True
    }

def create_list_response(items: list, item_name: str) -> Dict[str, Any]:
    """Crear respuesta para listas estandarizada"""
    return {
        "message": f"{len(items)} {item_name} encontrados",
        "data": items,
        "count": len(items),
        "timestamp": datetime.now().isoformat(),
        "success": True
    } 