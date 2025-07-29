# 🛡️ Manejadores de Eventos y Errores - SignaApi

## 📋 Resumen

Se han implementado manejadores de eventos robustos y completos para la API de SignaApi, incluyendo:

- ✅ **Manejo de errores HTTP** con códigos de estado apropiados
- ✅ **Validación de datos** en todos los endpoints
- ✅ **Logging detallado** de eventos y errores
- ✅ **Middleware de monitoreo** para métricas y rendimiento
- ✅ **Seguridad básica** con headers de protección
- ✅ **Respuestas estandarizadas** para éxito y error
- ✅ **Manejo de excepciones personalizadas**

## 🏗️ Arquitectura de Manejadores

### 1. **Error Handlers** (`api/error_handlers.py`)

#### Clases de Error Personalizadas:
```python
class SignaApiError(Exception)          # Error base
class ValidationError(SignaApiError)    # Errores de validación
class DatabaseError(SignaApiError)      # Errores de base de datos
class AuthenticationError(SignaApiError) # Errores de autenticación
class ResourceNotFoundError(SignaApiError) # Recurso no encontrado
class DuplicateResourceError(SignaApiError) # Recurso duplicado
```

#### Funciones de Validación:
- `validate_required_fields()` - Campos obligatorios
- `validate_email()` - Formato de email
- `validate_age()` - Rango de edad válido
- `validate_string_length()` - Longitud de strings
- `validate_file_upload()` - Archivos subidos

#### Funciones de Respuesta:
- `create_success_response()` - Respuestas de éxito
- `create_list_response()` - Respuestas de listas
- `create_error_response()` - Respuestas de error

### 2. **Middleware de Eventos** (`api/middleware.py`)

#### EventMonitoringMiddleware:
- 📊 **Métricas en tiempo real**: Contadores de requests, errores, tiempos de respuesta
- 📝 **Logging detallado**: Cada request se registra con contexto completo
- 🆔 **Request IDs**: Identificación única para cada request
- ⏱️ **Tiempos de respuesta**: Monitoreo de rendimiento

#### SecurityMiddleware:
- 🛡️ **Headers de seguridad**: X-Content-Type-Options, X-Frame-Options, etc.
- 🤖 **Detección de bots**: Logging de user agents sospechosos
- 🚫 **Protección básica**: Headers de seguridad estándar

#### PerformanceMiddleware:
- ⚡ **Requests lentos**: Detección automática de requests > 2 segundos
- 📈 **Métricas de rendimiento**: Tiempos de respuesta promedio, máximo, mínimo
- ⚠️ **Alertas**: Logging de requests que exceden umbrales

## 🔧 Implementación en Endpoints

### Ejemplo de Endpoint Mejorado:

```python
@app.post("/doctores/")
def crear_doctor(nombre: str, email: str, google_id: Optional[str] = None, especialidad: Optional[str] = None):
    try:
        # Validación de datos
        validated_data = validate_doctor_data(nombre, email, especialidad)
        
        # Verificación de duplicados
        with Session(engine) as session:
            existing_doctor = session.exec(
                select(Doctor).where(Doctor.email == validated_data["email"])
            ).first()
            
            if existing_doctor:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Ya existe un doctor con este email"
                )
            
            # Creación con logging
            doctor = Doctor(**validated_data)
            session.add(doctor)
            session.commit()
            session.refresh(doctor)
            
            logger.info(f"Doctor creado: {doctor.email}")
            return create_success_response(doctor, "Doctor creado exitosamente")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creando doctor: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )
```

## 📊 Métricas y Monitoreo

### Endpoint de Métricas: `/metrics`

```json
{
  "metrics": {
    "total_requests": 1250,
    "total_errors": 23,
    "success_rate": 98.16,
    "average_response_time": 0.245,
    "max_response_time": 2.1,
    "min_response_time": 0.012,
    "timestamp": "2024-01-15T10:30:00"
  },
  "system_info": {
    "rppg_available": true,
    "vitals_available": true,
    "timestamp": "2024-01-15T10:30:00"
  }
}
```

### Archivos de Log:
- `error_logs.log` - Errores detallados con contexto
- `api_events.log` - Eventos de requests y respuestas

## 🚨 Códigos de Error HTTP

| Código | Descripción | Uso |
|--------|-------------|-----|
| 400 | Bad Request | Datos inválidos o faltantes |
| 401 | Unauthorized | Autenticación requerida |
| 403 | Forbidden | Acceso prohibido |
| 404 | Not Found | Recurso no encontrado |
| 409 | Conflict | Recurso duplicado |
| 422 | Unprocessable Entity | Validación fallida |
| 500 | Internal Server Error | Error interno del servidor |
| 503 | Service Unavailable | Servicio no disponible |

## 🔍 Validaciones Implementadas

### Doctores:
- ✅ Nombre: mínimo 2 caracteres
- ✅ Email: formato válido
- ✅ Especialidad: mínimo 2 caracteres (opcional)
- ✅ Email único en la base de datos

### Pacientes:
- ✅ Nombre: mínimo 2 caracteres
- ✅ Cédula: mínimo 5 caracteres, única
- ✅ Edad: entre 0 y 150 años

### Historias Clínicas:
- ✅ Paciente debe existir
- ✅ Fecha requerida

### Visitas:
- ✅ Historia clínica debe existir
- ✅ Todos los campos requeridos
- ✅ Número de visita positivo

### Diagnósticos:
- ✅ Visita debe existir
- ✅ Diagnóstico y resultado RPGP requeridos

### Archivos (RPPG):
- ✅ Tipos permitidos: .mp4, .avi, .mov, .mkv
- ✅ Archivo no vacío
- ✅ Tamaño máximo: 10MB

## 📈 Beneficios Implementados

### 1. **Robustez**:
- Manejo completo de errores en todos los niveles
- Validaciones exhaustivas de datos
- Recuperación graceful de errores

### 2. **Observabilidad**:
- Logging detallado de todos los eventos
- Métricas en tiempo real
- Trazabilidad completa de requests

### 3. **Seguridad**:
- Headers de seguridad estándar
- Validación de entrada estricta
- Protección contra ataques básicos

### 4. **Rendimiento**:
- Monitoreo de requests lentos
- Métricas de tiempo de respuesta
- Optimización basada en datos

### 5. **Mantenibilidad**:
- Código modular y reutilizable
- Respuestas estandarizadas
- Documentación completa

## 🚀 URLs de Acceso

- **API Principal**: https://signaapiv1-production.up.railway.app/
- **Health Check**: https://signaapiv1-production.up.railway.app/health
- **Métricas**: https://signaapiv1-production.up.railway.app/metrics
- **Documentación**: https://signaapiv1-production.up.railway.app/docs

## 🔧 Configuración

### Variables de Entorno:
```bash
# Logging
LOG_LEVEL=INFO
LOG_FILE=api_events.log
ERROR_LOG_FILE=error_logs.log

# Performance
SLOW_REQUEST_THRESHOLD=2.0
MAX_FILE_SIZE_MB=10

# Security
ALLOWED_ORIGINS=*
```

### Middleware Order:
1. EventMonitoringMiddleware
2. SecurityMiddleware  
3. PerformanceMiddleware
4. CORSMiddleware

## 📝 Ejemplos de Uso

### Crear Doctor con Validación:
```bash
curl -X POST "https://signaapiv1-production.up.railway.app/doctores/" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Dr. Juan Pérez",
    "email": "juan.perez@hospital.com",
    "especialidad": "Cardiología"
  }'
```

### Respuesta de Error:
```json
{
  "error": "ValidationError",
  "message": "El email no es válido",
  "timestamp": "2024-01-15T10:30:00",
  "status_code": 400,
  "details": {
    "email": "invalid-email"
  }
}
```

### Respuesta de Éxito:
```json
{
  "message": "Doctor creado exitosamente",
  "data": {
    "id": 1,
    "nombre": "Dr. Juan Pérez",
    "email": "juan.perez@hospital.com",
    "especialidad": "Cardiología"
  },
  "timestamp": "2024-01-15T10:30:00",
  "success": true
}
```

## 🎯 Próximas Mejoras

1. **Rate Limiting**: Implementar límites de requests por IP
2. **Autenticación JWT**: Sistema de autenticación completo
3. **Caché Redis**: Mejorar rendimiento con caché
4. **Métricas Avanzadas**: Dashboard de monitoreo
5. **Alertas**: Notificaciones automáticas de errores
6. **Backup Automático**: Respaldo de base de datos
7. **Tests Automatizados**: Cobertura completa de tests

---

**Estado**: ✅ **Implementado y Funcionando**
**Última Actualización**: Enero 2024
**Versión**: 1.0.0 