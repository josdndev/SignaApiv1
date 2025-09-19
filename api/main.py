from fastapi import FastAPI, UploadFile, File, HTTPException, Request, status, Body, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import tempfile, os
import numpy as np
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import traceback
from pydantic import BaseModel
import os
import bcrypt
from jose import JWTError, jwt
from datetime import datetime, timedelta

# Configuración JWT
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Importar manejadores de eventos y errores
from .error_handlers import (
    validation_exception_handler,
    http_exception_handler,
    general_exception_handler,
    validate_required_fields,
    validate_email,
    validate_age,
    validate_string_length,
    validate_file_upload,
    handle_database_operation,
    create_success_response,
    create_list_response,
    SignaApiError,
    ValidationError,
    DatabaseError,
    ResourceNotFoundError,
    DuplicateResourceError
)

from .middleware import (
    EventMonitoringMiddleware,
    SecurityMiddleware,
    PerformanceMiddleware,
    set_event_middleware
)

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Importar módulos con manejo de errores
try:
    from .rppg_core import read_video_with_face_detection_and_FS, CHROME_DEHAAN, extract_heart_rate
    RPPG_AVAILABLE = True
    logger.info("RPPG module loaded successfully")
except ImportError as e:
    logger.warning(f"RPPG module not available: {e}")
    RPPG_AVAILABLE = False

try:
    from .vitails import extract_respiratory_rate, calculate_hrv
    VITALS_AVAILABLE = True
    logger.info("Vitals module loaded successfully")
except ImportError as e:
    logger.warning(f"Vitals module not available: {e}")
    VITALS_AVAILABLE = False

from sqlmodel import SQLModel, Session, create_engine, select
from .models import Doctor, Paciente, HistoriaClinica, Visita, Diagnostico

app = FastAPI(
    title="SignaApi",
    description="API clínica para gestión de pacientes, doctores, historias clínicas, visitas y diagnósticos",
    version="1.0.0"
)

# Configurar middlewares
app.add_middleware(EventMonitoringMiddleware)
app.add_middleware(SecurityMiddleware)
app.add_middleware(PerformanceMiddleware)

# Configurar CORS - DEBE ir ANTES de los exception handlers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios específicos
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Configurar exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Configurar base de datos
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///database.db")
engine = create_engine(DATABASE_URL)
SQLModel.metadata.create_all(engine)

# Modelos Pydantic para validación de entrada
class DoctorCreate(BaseModel):
    nombre: str
    email: str
    google_id: Optional[str] = None
    especialidad: Optional[str] = None

class PacienteCreate(BaseModel):
    nombre: str
    cedula: str
    edad: int

class HistoriaCreate(BaseModel):
    paciente_id: int
    fecha: str

class VisitaCreate(BaseModel):
    historia_id: int
    hora_entrada: str
    evaluacion_triaje: str
    prediagnostico: str
    especialidad: str
    numero_visita: int

class DiagnosticoCreate(BaseModel):
    visita_id: int
    diagnostico: str
    resultado_rppg: str
    informe_prediagnostico: str

# Modelos Pydantic para autenticación
class DoctorAuthCreate(BaseModel):
    nombre: str
    email: str
    cedula: str
    password: str
    especialidad: Optional[str] = None

class DoctorLogin(BaseModel):
    cedula: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    cedula: Optional[str] = None

# Middleware para logging de requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    
    # Log request
    logger.info(f"Request: {request.method} {request.url}")
    logger.info(f"Client: {request.client.host if request.client else 'Unknown'}")
    
    try:
        response = await call_next(request)
        
        # Log response
        process_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Response: {response.status_code} - {process_time:.3f}s")
        
        return response
    except Exception as e:
        # Log error
        process_time = (datetime.now() - start_time).total_seconds()
        logger.error(f"Error: {str(e)} - {process_time:.3f}s")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "message": "Los datos enviados no son válidos",
            "details": exc.errors(),
            "timestamp": datetime.now().isoformat()
        }
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger.error(f"HTTP error {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP Error",
            "message": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now().isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {str(exc)}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "Ha ocurrido un error interno del servidor",
            "timestamp": datetime.now().isoformat()
        }
    )

# Función helper para manejo de sesiones de base de datos
def get_db_session():
    try:
        with Session(engine) as session:
            yield session
    except Exception as e:
        logger.error(f"Database session error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de conexión con la base de datos"
        )

# Función helper para validar datos
def validate_doctor_data(nombre: str, email: str, especialidad: Optional[str] = None) -> Dict[str, Any]:
    errors = []
    
    if not nombre or len(nombre.strip()) < 2:
        errors.append("El nombre debe tener al menos 2 caracteres")
    
    if not email or '@' not in email:
        errors.append("El email no es válido")
    
    if especialidad and len(especialidad.strip()) < 2:
        errors.append("La especialidad debe tener al menos 2 caracteres")
    
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Datos inválidos", "errors": errors}
        )
    
    return {"nombre": nombre.strip(), "email": email.strip(), "especialidad": especialidad.strip() if especialidad else None}

def validate_paciente_data(nombre: str, cedula: str, edad: int) -> Dict[str, Any]:
    errors = []
    
    if not nombre or len(nombre.strip()) < 2:
        errors.append("El nombre debe tener al menos 2 caracteres")
    
    if not cedula or len(cedula.strip()) < 5:
        errors.append("La cédula debe tener al menos 5 caracteres")
    
    if not isinstance(edad, int) or edad < 0 or edad > 150:
        errors.append("La edad debe ser un número entre 0 y 150")
    
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Datos inválidos", "errors": errors}
        )
    
    return {"nombre": nombre.strip(), "cedula": cedula.strip(), "edad": edad}

# Funciones helper para auth
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verificar_password(password_plana: str, hash: str) -> bool:
    return bcrypt.checkpw(password_plana.encode('utf-8'), hash.encode('utf-8'))

def crear_token_acceso(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def authenticate_doctor(cedula: str, password: str):
    with Session(engine) as session:
        doctor = session.exec(select(Doctor).where(Doctor.cedula == cedula)).first()
        if not doctor:
            return False
        if not verificar_password(password, doctor.password_hash):
            return False
        return doctor

# Endpoints de autenticación
@app.post("/auth/login", response_model=Token)
def login_doctor(login_data: DoctorLogin):
    doctor = authenticate_doctor(login_data.cedula, login_data.password)
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cédula o contraseña incorrecta",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = crear_token_acceso(data={"sub": doctor.cedula})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/auth/register-doctor")
def register_new_doctor(
    doctor_data: DoctorAuthCreate,
    secret: str = Query(...)
):
    if secret != "medicos2024":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clave secreta incorrecta"
        )

    errors = []
    if not doctor_data.nombre or len(doctor_data.nombre.strip()) < 2:
        errors.append("El nombre debe tener al menos 2 caracteres")
    if not doctor_data.email or '@' not in doctor_data.email:
        errors.append("El email no es válido")
    if not doctor_data.cedula or len(doctor_data.cedula.strip()) < 5:
        errors.append("La cédula debe tener al menos 5 caracteres")
    if not doctor_data.password or len(doctor_data.password) < 6:
        errors.append("La contraseña debe tener al menos 6 caracteres")

    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Datos inválidos", "errors": errors}
        )

    with Session(engine) as session:
        existing_doctor = session.exec(
            select(Doctor).where(
                (Doctor.email == doctor_data.email) | (Doctor.cedula == doctor_data.cedula)
            )
        ).first()
        if existing_doctor:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un doctor con este email o cédula"
            )

        password_hash = hash_password(doctor_data.password)
        new_doctor = Doctor(
            nombre=doctor_data.nombre.strip(),
            email=doctor_data.email.strip(),
            cedula=doctor_data.cedula.strip(),
            password_hash=password_hash,
            especialidad=doctor_data.especialidad.strip() if doctor_data.especialidad else None,
            role="doctor",
            active=True
        )

        session.add(new_doctor)
        session.commit()
        session.refresh(new_doctor)

        logger.info(f"Doctor registrado: {new_doctor.cedula}")
        return {
            "message": "Doctor registrado exitosamente",
            "doctor": {
                "id": new_doctor.id,
                "nombre": new_doctor.nombre,
                "email": new_doctor.email,
                "cedula": new_doctor.cedula,
                "especialidad": new_doctor.especialidad,
                "role": new_doctor.role
            },
            "timestamp": datetime.now().isoformat()
        }

@app.post("/auth/create-super")
def create_super_user(
    nombre: str,
    email: str,
    cedula: str,
    password: str,
    secret: str = Query(...)
):
    if secret != "super2024":
        raise HTTPException(status_code=400, detail="Clave secreta incorrecta")

    with Session(engine) as session:
        existing_super = session.exec(select(Doctor).where(Doctor.role == "super")).first()
        if existing_super:
            raise HTTPException(status_code=409, detail="Ya existe un super usuario")

        password_hash = hash_password(password)
        super_user = Doctor(
            nombre=nombre,
            email=email,
            cedula=cedula,
            password_hash=password_hash,
            especialidad="Administrador",
            role="super",
            active=True
        )

        session.add(super_user)
        session.commit()
        session.refresh(super_user)

    return {"message": "Super usuario creado", "doctor": super_user}

# DEPENDENCY para obtener doctor actual
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends

def get_current_doctor(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        cedula: str = payload.get("sub")
        if cedula is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    with Session(engine) as session:
        doctor = session.exec(select(Doctor).where(Doctor.cedula == cedula)).first()
    if doctor is None:
        raise credentials_exception
    return doctor

@app.get("/auth/me")
def read_doctor_me(current_doctor: Doctor = Depends(get_current_doctor)):
    return {
        "doctor": {
            "id": current_doctor.id,
            "nombre": current_doctor.nombre,
            "email": current_doctor.email,
            "cedula": current_doctor.cedula,
            "especialidad": current_doctor.especialidad,
            "role": current_doctor.role
        },
        "timestamp": datetime.now().isoformat()
    }

# Endpoint de healthcheck
@app.get("/")
def health_check():
    try:
        # Verificar conexión a la base de datos
        with Session(engine) as session:
            session.exec(select(Doctor)).first()
        
        return {
            "status": "healthy", 
            "message": "SignaApi is running",
            "timestamp": datetime.now().isoformat(),
            "modules": {
                "rppg": RPPG_AVAILABLE,
                "vitals": VITALS_AVAILABLE
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio no disponible"
        )

# Endpoint de healthcheck alternativo
@app.get("/health")
def health_check_alt():
    return health_check()

# Endpoint de prueba para CORS
@app.get("/test-cors")
def test_cors():
    return {
        "message": "CORS test successful",
        "timestamp": datetime.now().isoformat(),
        "cors_enabled": True
    }

# Endpoint para métricas y monitoreo
@app.get("/metrics")
def get_metrics():
    try:
        from .middleware import get_event_middleware
        
        event_middleware = get_event_middleware()
        metrics = event_middleware.get_metrics() if event_middleware else {}
        
        return {
            "metrics": metrics,
            "system_info": {
                "rppg_available": RPPG_AVAILABLE,
                "vitals_available": VITALS_AVAILABLE,
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error getting metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error obteniendo métricas"
        )

# Endpoint para registrar doctor
@app.post("/doctores/")
def crear_doctor(doctor_data: DoctorCreate):
    try:
        # Validar datos
        validated_data = validate_doctor_data(doctor_data.nombre, doctor_data.email, doctor_data.especialidad)
        
        # Verificar si el email ya existe
        with Session(engine) as session:
            existing_doctor = session.exec(
                select(Doctor).where(Doctor.email == validated_data["email"])
            ).first()
            
            if existing_doctor:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Ya existe un doctor con este email"
                )
            
            # Crear doctor
            doctor = Doctor(
                nombre=validated_data["nombre"],
                email=validated_data["email"],
                google_id=doctor_data.google_id,
                especialidad=validated_data["especialidad"]
            )
            
            session.add(doctor)
            session.commit()
            session.refresh(doctor)
            
            logger.info(f"Doctor creado: {doctor.email}")
            return {
                "message": "Doctor creado exitosamente",
                "doctor": doctor,
                "timestamp": datetime.now().isoformat()
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creando doctor: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

# Endpoint para consultar doctores
@app.get("/doctores/")
def listar_doctores():
    try:
        with Session(engine) as session:
            doctores = session.exec(select(Doctor)).all()
            
        logger.info(f"Listados {len(doctores)} doctores")
        return {
            "doctores": doctores,
            "count": len(doctores),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error listando doctores: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

# Endpoint para registrar paciente
@app.post("/pacientes/")
def crear_paciente(paciente_data: PacienteCreate):
    try:
        # Validar datos
        validated_data = validate_paciente_data(paciente_data.nombre, paciente_data.cedula, paciente_data.edad)
        
        # Verificar si la cédula ya existe
        with Session(engine) as session:
            existing_paciente = session.exec(
                select(Paciente).where(Paciente.cedula == validated_data["cedula"])
            ).first()
            
            if existing_paciente:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Ya existe un paciente con esta cédula"
                )
            
            # Crear paciente
            paciente = Paciente(
                nombre=validated_data["nombre"],
                cedula=validated_data["cedula"],
                edad=validated_data["edad"]
            )
            
            session.add(paciente)
            session.commit()
            session.refresh(paciente)
            
            logger.info(f"Paciente creado: {paciente.cedula}")
            return {
                "message": "Paciente creado exitosamente",
                "paciente": paciente,
                "timestamp": datetime.now().isoformat()
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creando paciente: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

# Endpoint para consultar pacientes
@app.get("/pacientes/")
def listar_pacientes():
    try:
        with Session(engine) as session:
            pacientes = session.exec(select(Paciente)).all()
            
        logger.info(f"Listados {len(pacientes)} pacientes")
        return {
            "pacientes": pacientes,
            "count": len(pacientes),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error listando pacientes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

# Endpoint para registrar historia clínica
@app.post("/historias/")
def crear_historia(historia_data: HistoriaCreate):
    try:
        # Validar datos
        if not historia_data.fecha or len(historia_data.fecha.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La fecha es requerida"
            )
        
        with Session(engine) as session:
            # Verificar que el paciente existe
            paciente = session.exec(select(Paciente).where(Paciente.id == historia_data.paciente_id)).first()
            if not paciente:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Paciente no encontrado"
                )
            
            # Crear historia
            historia = HistoriaClinica(
                paciente_id=historia_data.paciente_id,
                fecha=historia_data.fecha.strip()
            )
            
            session.add(historia)
            session.commit()
            session.refresh(historia)
            
            logger.info(f"Historia clínica creada para paciente {historia_data.paciente_id}")
            return {
                "message": "Historia clínica creada exitosamente",
                "historia": historia,
                "timestamp": datetime.now().isoformat()
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creando historia clínica: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

# Endpoint para consultar historias clínicas
@app.get("/historias/")
def listar_historias():
    try:
        with Session(engine) as session:
            historias = session.exec(select(HistoriaClinica)).all()
            
        logger.info(f"Listadas {len(historias)} historias clínicas")
        return {
            "historias": historias,
            "count": len(historias),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error listando historias: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

# Endpoint para registrar visita
@app.post("/visitas/")
def crear_visita(visita_data: VisitaCreate):
    try:
        # Validar datos
        if not visita_data.hora_entrada or len(visita_data.hora_entrada.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La hora de entrada es requerida"
            )
        
        if not visita_data.evaluacion_triaje or len(visita_data.evaluacion_triaje.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La evaluación de triaje es requerida"
            )
        
        if not visita_data.especialidad or len(visita_data.especialidad.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La especialidad es requerida"
            )
        
        if not isinstance(visita_data.numero_visita, int) or visita_data.numero_visita < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El número de visita debe ser un número positivo"
            )
        
        with Session(engine) as session:
            # Verificar que la historia existe
            historia = session.exec(select(HistoriaClinica).where(HistoriaClinica.id == visita_data.historia_id)).first()
            if not historia:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Historia clínica no encontrada"
                )
            
            # Crear visita
            visita = Visita(
                historia_id=visita_data.historia_id,
                hora_entrada=visita_data.hora_entrada.strip(),
                evaluacion_triaje=visita_data.evaluacion_triaje.strip(),
                prediagnostico=visita_data.prediagnostico.strip(),
                especialidad=visita_data.especialidad.strip(),
                numero_visita=visita_data.numero_visita
            )
            
            session.add(visita)
            session.commit()
            session.refresh(visita)
            
            logger.info(f"Visita creada para historia {visita_data.historia_id}")
            return {
                "message": "Visita creada exitosamente",
                "visita": visita,
                "timestamp": datetime.now().isoformat()
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creando visita: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

# Endpoint para consultar visitas
@app.get("/visitas/")
def listar_visitas():
    try:
        with Session(engine) as session:
            visitas = session.exec(select(Visita)).all()
            
        logger.info(f"Listadas {len(visitas)} visitas")
        return {
            "visitas": visitas,
            "count": len(visitas),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error listando visitas: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

# Endpoint para obtener todas las visitas con los datos del paciente
@app.get("/visitas_con_pacientes/")
def listar_visitas_con_pacientes():
    try:
        with Session(engine) as session:
            visitas = session.exec(
                select(Visita, Paciente)
                .join(HistoriaClinica, HistoriaClinica.id == Visita.historia_id)
                .join(Paciente, Paciente.id == HistoriaClinica.paciente_id)
            ).all()
            
            resultado = [
                {
                    "visita": {
                        "id": visita.Visita.id,
                        "hora_entrada": visita.Visita.hora_entrada,
                        "evaluacion_triaje": visita.Visita.evaluacion_triaje,
                        "prediagnostico": visita.Visita.prediagnostico,
                        "especialidad": visita.Visita.especialidad,
                        "numero_visita": visita.Visita.numero_visita
                    },
                    "paciente": {
                        "id": visita.Paciente.id,
                        "nombre": visita.Paciente.nombre,
                        "cedula": visita.Paciente.cedula,
                        "edad": visita.Paciente.edad
                    }
                }
                for visita in visitas
            ]
            
            logger.info(f"Listadas {len(resultado)} visitas con datos de pacientes")
            return {
                "visitas_con_pacientes": resultado,
                "count": len(resultado),
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error listando visitas con pacientes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@app.post("/rppg/")
async def analyze_video(file: UploadFile = File(...)):
    if not RPPG_AVAILABLE or not VITALS_AVAILABLE:
        logger.error("RPPG processing requested but not available")
        return JSONResponse(
            status_code=503,
            content={
                "error": "RPPG processing is not available. OpenCV or related dependencies are not properly installed.",
                "message": "Please check the server configuration.",
                "timestamp": datetime.now().isoformat()
            }
        )
    
    try:
        # Validar archivo
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Archivo no válido"
            )
        
        # Validar tipo de archivo
        allowed_extensions = ['.mp4', '.avi', '.mov', '.mkv']
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de archivo no soportado. Formatos permitidos: {', '.join(allowed_extensions)}"
            )
        
        # Crear un archivo temporal
        with tempfile.NamedTemporaryFile(delete=True, suffix=file_extension) as tmp:
            # Guardar el archivo subido en el archivo temporal
            content = await file.read()
            if len(content) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El archivo está vacío"
                )
            
            tmp.write(content)
            tmp.flush()

            logger.info(f"Procesando video: {file.filename}")

            # Leer el video y detectar la cara
            fps, time, sig, bvp, ibi, hr = read_video_with_face_detection_and_FS(tmp.name, CHROME_DEHAAN)

            # Calcular la tasa de respiración
            respiratory_rate = extract_respiratory_rate(sig, fps)

            # Calcular la variabilidad de la frecuencia cardíaca (HRV)
            hrv = calculate_hrv(ibi)

            logger.info(f"Video procesado exitosamente: {file.filename}")

            # Retornar los resultados
            return JSONResponse(content={
                "message": "Video processed successfully",
                "filename": file.filename,
                "fps": fps,
                "time": time,
                "sig": sig.tolist(),
                "bvp": bvp.tolist(),
                "ibi": ibi.tolist(),
                "hr": hr.tolist(),
                "respiratory_rate": respiratory_rate,
                "hrv": hrv,
                "timestamp": datetime.now().isoformat()
            })
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing video: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Error processing video",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

# Endpoint para registrar diagnostico
@app.post("/diagnosticos/")
def crear_diagnostico(diagnostico_data: DiagnosticoCreate):
    try:
        # Validar datos
        if not diagnostico_data.diagnostico or len(diagnostico_data.diagnostico.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El diagnóstico es requerido"
            )
        
        if not diagnostico_data.resultado_rppg or len(diagnostico_data.resultado_rppg.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El resultado RPGP es requerido"
            )
        
        with Session(engine) as session:
            # Verificar que la visita existe
            visita = session.exec(select(Visita).where(Visita.id == diagnostico_data.visita_id)).first()
            if not visita:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Visita no encontrada"
                )
            
            # Crear diagnóstico
            diag = Diagnostico(
                visita_id=diagnostico_data.visita_id,
                diagnostico=diagnostico_data.diagnostico.strip(),
                resultado_rppg=diagnostico_data.resultado_rppg.strip(),
                informe_prediagnostico=diagnostico_data.informe_prediagnostico.strip()
            )
            
            session.add(diag)
            session.commit()
            session.refresh(diag)
            
            logger.info(f"Diagnóstico creado para visita {diagnostico_data.visita_id}")
            return {
                "message": "Diagnóstico creado exitosamente",
                "diagnostico": diag,
                "timestamp": datetime.now().isoformat()
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creando diagnóstico: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@app.get("/diagnosticos/")
def listar_diagnosticos():
    try:
        with Session(engine) as session:
            diagnosticos = session.exec(select(Diagnostico)).all()
            
        logger.info(f"Listados {len(diagnosticos)} diagnósticos")
        return {
            "diagnosticos": diagnosticos,
            "count": len(diagnosticos),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error listando diagnósticos: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

# Endpoint protegido para poblar la base de datos con datos simulados
@app.post("/populate-db")
def populate_db(secret: str = Query(...)):
    SECRET_KEY = "supersecret"  # Cambia esto por una clave segura
    if secret != SECRET_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    import random
    from datetime import datetime, timedelta
    from sqlmodel import Session
    from .models import Doctor, Paciente, HistoriaClinica, Visita, Diagnostico

    default_password_hash = hash_password("password123")

    especialidades = [
        "Cardiología", "Pediatría", "Medicina General", "Neurología", "Ginecología",
        "Traumatología", "Dermatología", "Oftalmología", "Otorrinolaringología", "Psiquiatría",
        "Endocrinología", "Nefrología", "Hematología", "Oncología", "Radiología"
    ]

    doctores = []
    for i in range(15):
        nombre = f"Dr. {random.choice(['Juan', 'Carlos', 'Luis', 'Miguel', 'José', 'Antonio', 'Francisco', 'Javier', 'Manuel', 'Pedro', 'Ángel', 'David', 'José Luis', 'Jesús', 'Alejandro'])} {random.choice(['García', 'Rodríguez', 'González', 'Fernández', 'López', 'Martínez', 'Sánchez', 'Pérez', 'Martín', 'Ruiz', 'Hernández', 'Jiménez', 'Díaz', 'Moreno', 'Álvarez'])}"
        if random.choice([True, False]):
            nombre = nombre.replace("Dr.", "Dra.")
        email = f"{nombre.lower().replace(' ', '.').replace('dr.', '').replace('dra.', '')}@hospital.com"
        cedula = f"DOC{i+1:03d}"
        especialidad = random.choice(especialidades)
        doctores.append({
            "nombre": nombre,
            "email": email,
            "cedula": cedula,
            "password_hash": default_password_hash,
            "google_id": f"{1000+i}",
            "especialidad": especialidad,
            "role": "doctor",
            "active": True
        })

    nombres_comunes = [
        "María", "José", "Juan", "Ana", "Luis", "Carlos", "Antonio", "Francisco", "Javier", "Manuel",
        "Pedro", "Ángel", "David", "José Luis", "Jesús", "Alejandro", "Miguel", "Rafael", "Fernando", "Pablo",
        "Daniel", "Sergio", "Jorge", "Alberto", "Diego", "Rubén", "Enrique", "Víctor", "Adrián", "Óscar",
        "Carmen", "Isabel", "Dolores", "Pilar", "Teresa", "Ana María", "Cristina", "Mónica", "Francisca", "Laura",
        "Mercedes", "Antonia", "Rosa", "Concepción", "Encarnación", "María José", "María Dolores", "María Carmen", "María Pilar", "María Teresa"
    ]

    apellidos_comunes = [
        "García", "Rodríguez", "González", "Fernández", "López", "Martínez", "Sánchez", "Pérez", "Martín", "Ruiz",
        "Hernández", "Jiménez", "Díaz", "Moreno", "Álvarez", "Muñoz", "Romero", "Navarro", "Torres", "Domínguez",
        "Gil", "Vázquez", "Serrano", "Ramos", "Blanco", "Sanz", "Castro", "Ortega", "Delgado", "Rubio"
    ]

    diagnosticos_posibles = [
        "Hipertensión", "Diabetes Mellitus", "Resfriado Común", "Migraña", "Dermatitis Atópica",
        "Arritmia Cardíaca", "Bronquitis", "Gastritis", "Artrosis", "Depresión",
        "Anemia", "Hipotiroidismo", "Asma", "Cálculos Renales", "Sinusitis",
        "Varices", "Hemorragia Nasal", "Tendinitis", "Conjuntivitis", "Otitis",
        "Sin diagnóstico específico", "Seguimiento", "Chequeo rutinario"
    ]

    triaje = ["Rojo", "Amarillo", "Verde"]

    try:
        with Session(engine) as session:
            # Doctores - verificar si ya existen antes de agregar
            for doc in doctores:
                existing_doctor = session.exec(
                    select(Doctor).where(Doctor.cedula == doc["cedula"])
                ).first()
                if not existing_doctor:
                    doctor = Doctor(**doc)
                    session.add(doctor)
            session.commit()

            # Pacientes (150 pacientes)
            pacientes_creados = []
            for i in range(150):
                nombre = f"{random.choice(nombres_comunes)} {random.choice(apellidos_comunes)} {random.choice(apellidos_comunes)}"
                paciente = Paciente(
                    nombre=nombre,
                    cedula=f"V{random.randint(10000000,99999999)}",
                    edad=random.randint(1, 99)
                )
                session.add(paciente)
                session.commit()
                session.refresh(paciente)
                pacientes_creados.append(paciente)

                # Historia clínica (80% tienen historia)
                if random.random() < 0.8:
                    historia = HistoriaClinica(
                        paciente_id=paciente.id,
                        fecha=(datetime.now() - timedelta(days=random.randint(0,730))).strftime('%Y-%m-%d')
                    )
                    session.add(historia)
                    session.commit()
                    session.refresh(historia)

                    # Visitas (1-5 visitas por historia)
                    num_visitas = random.randint(1, 5)
                    for v in range(num_visitas):
                        fecha_visita = datetime.now() - timedelta(days=random.randint(0, 365))
                        visita = Visita(
                            historia_id=historia.id,
                            hora_entrada=fecha_visita.strftime('%Y-%m-%dT%H:%M'),
                            evaluacion_triaje=random.choice(triaje),
                            prediagnostico=f"Evaluación inicial - Visita {v+1}",
                            especialidad=random.choice(especialidades),
                            numero_visita=v+1
                        )
                        session.add(visita)
                        session.commit()
                        session.refresh(visita)

                        # Diagnósticos (1-3 por visita)
                        num_diag = random.randint(1, 3)
                        for d in range(num_diag):
                            diag = Diagnostico(
                                visita_id=visita.id,
                                diagnostico=random.choice(diagnosticos_posibles),
                                resultado_rppg=f"HR:{random.randint(50,120)} RR:{random.randint(10,25)} SDNN:{random.randint(15,100)} RMSSD:{random.randint(15,100)}",
                                informe_prediagnostico=f"Informe médico generado para {paciente.nombre}. Visita {v+1}, diagnóstico {d+1}."
                            )
                            session.add(diag)
            session.commit()
        return {"message": "Base de datos simulada con doctores, pacientes, historias, visitas y diagnósticos."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al poblar la base de datos: {e}")
