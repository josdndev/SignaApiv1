"""
Middleware para monitoreo de eventos y métricas de SignaApi
"""

import time
import logging
from datetime import datetime
from typing import Dict, Any
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import json

# Configurar logger para eventos
event_logger = logging.getLogger("signaapi.events")
event_logger.setLevel(logging.INFO)

# Handler para archivo de eventos
event_file_handler = logging.FileHandler("api_events.log")
event_file_handler.setLevel(logging.INFO)
event_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
event_file_handler.setFormatter(event_formatter)
event_logger.addHandler(event_file_handler)

class EventMonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware para monitoreo de eventos y métricas"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.request_count = 0
        self.error_count = 0
        self.response_times = []
    
    async def dispatch(self, request: Request, call_next):
        # Incrementar contador de requests
        self.request_count += 1
        
        # Registrar inicio de request
        start_time = time.time()
        request_id = f"req_{self.request_count}_{int(start_time)}"
        
        # Log del evento de inicio
        self.log_request_start(request, request_id)
        
        try:
            # Procesar request
            response = await call_next(request)
            
            # Calcular tiempo de respuesta
            process_time = time.time() - start_time
            self.response_times.append(process_time)
            
            # Log del evento de éxito
            self.log_request_success(request, response, request_id, process_time)
            
            # Agregar headers de métricas
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(process_time)
            response.headers["X-Request-Count"] = str(self.request_count)
            
            return response
            
        except Exception as e:
            # Incrementar contador de errores
            self.error_count += 1
            
            # Calcular tiempo de respuesta
            process_time = time.time() - start_time
            
            # Log del evento de error
            self.log_request_error(request, e, request_id, process_time)
            
            # Re-lanzar la excepción
            raise
    
    def log_request_start(self, request: Request, request_id: str):
        """Log del inicio de un request"""
        event_data = {
            "event_type": "request_start",
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "method": request.method,
            "url": str(request.url),
            "client_host": request.client.host if request.client else "Unknown",
            "user_agent": request.headers.get("user-agent", "Unknown"),
            "content_type": request.headers.get("content-type", "Unknown")
        }
        
        event_logger.info(f"Request started: {json.dumps(event_data)}")
    
    def log_request_success(self, request: Request, response: Response, request_id: str, process_time: float):
        """Log del éxito de un request"""
        event_data = {
            "event_type": "request_success",
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "method": request.method,
            "url": str(request.url),
            "status_code": response.status_code,
            "process_time": process_time,
            "content_length": response.headers.get("content-length", "Unknown")
        }
        
        event_logger.info(f"Request completed: {json.dumps(event_data)}")
    
    def log_request_error(self, request: Request, error: Exception, request_id: str, process_time: float):
        """Log del error de un request"""
        event_data = {
            "event_type": "request_error",
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "method": request.method,
            "url": str(request.url),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "process_time": process_time
        }
        
        event_logger.error(f"Request failed: {json.dumps(event_data)}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Obtener métricas del middleware"""
        avg_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0
        max_response_time = max(self.response_times) if self.response_times else 0
        min_response_time = min(self.response_times) if self.response_times else 0
        
        return {
            "total_requests": self.request_count,
            "total_errors": self.error_count,
            "success_rate": ((self.request_count - self.error_count) / self.request_count * 100) if self.request_count > 0 else 0,
            "average_response_time": avg_response_time,
            "max_response_time": max_response_time,
            "min_response_time": min_response_time,
            "timestamp": datetime.now().isoformat()
        }

class SecurityMiddleware(BaseHTTPMiddleware):
    """Middleware para seguridad básica"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        # Verificar headers de seguridad
        self.check_security_headers(request)
        
        # Procesar request
        response = await call_next(request)
        
        # Agregar headers de seguridad
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response
    
    def check_security_headers(self, request: Request):
        """Verificar headers de seguridad en requests"""
        # Log de requests sospechosos
        user_agent = request.headers.get("user-agent", "")
        if "bot" in user_agent.lower() or "crawler" in user_agent.lower():
            event_logger.warning(f"Suspicious user agent detected: {user_agent}")
        
        # Verificar rate limiting básico (implementación simple)
        client_host = request.client.host if request.client else "Unknown"
        # Aquí se podría implementar rate limiting más sofisticado

class PerformanceMiddleware(BaseHTTPMiddleware):
    """Middleware para monitoreo de rendimiento"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.slow_requests = []
        self.slow_threshold = 2.0  # 2 segundos
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Procesar request
        response = await call_next(request)
        
        # Calcular tiempo de respuesta
        process_time = time.time() - start_time
        
        # Registrar requests lentos
        if process_time > self.slow_threshold:
            slow_request_data = {
                "timestamp": datetime.now().isoformat(),
                "method": request.method,
                "url": str(request.url),
                "process_time": process_time,
                "status_code": response.status_code
            }
            self.slow_requests.append(slow_request_data)
            
            event_logger.warning(f"Slow request detected: {json.dumps(slow_request_data)}")
        
        return response
    
    def get_slow_requests(self) -> list:
        """Obtener lista de requests lentos"""
        return self.slow_requests

# Instancia global del middleware de eventos
event_middleware = None

def get_event_middleware() -> EventMonitoringMiddleware:
    """Obtener instancia del middleware de eventos"""
    global event_middleware
    return event_middleware

def set_event_middleware(middleware: EventMonitoringMiddleware):
    """Establecer instancia del middleware de eventos"""
    global event_middleware
    event_middleware = middleware 