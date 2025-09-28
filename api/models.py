from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List

class Doctor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str
    email: str
    cedula: str = Field(unique=True, index=True)
    password_hash: str
    google_id: Optional[str] = Field(default=None)
    especialidad: Optional[str] = Field(default=None)
    role: str = Field(default="doctor")  # "super" or "doctor"
    active: bool = Field(default=True)

class Paciente(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str
    cedula: str
    edad: int
    historias: List["HistoriaClinica"] = Relationship(back_populates="paciente")
    sensor_readings: List["SensorReading"] = Relationship(back_populates="paciente")

class HistoriaClinica(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    paciente_id: int = Field(foreign_key="paciente.id")
    fecha: str
    visitas: List["Visita"] = Relationship(back_populates="historia")
    paciente: Optional[Paciente] = Relationship(back_populates="historias")

class Visita(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    historia_id: int = Field(foreign_key="historiaclinica.id")
    hora_entrada: str
    evaluacion_triaje: str
    prediagnostico: str
    especialidad: str
    numero_visita: int
    diagnosticos: List["Diagnostico"] = Relationship(back_populates="visita")
    sensor_readings: List["SensorReading"] = Relationship(back_populates="visita")
    historia: Optional[HistoriaClinica] = Relationship(back_populates="visitas")

class Diagnostico(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    visita_id: int = Field(foreign_key="visita.id")
    diagnostico: str
    resultado_rppg: str
    informe_prediagnostico: str
    visita: Optional[Visita] = Relationship(back_populates="diagnosticos")

class SensorReading(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    device_id: str = Field(index=True)
    paciente_id: Optional[int] = Field(default=None, foreign_key="paciente.id")
    visita_id: Optional[int] = Field(default=None, foreign_key="visita.id")
    sensor_type: str
    heart_rate: Optional[int] = Field(default=None)
    timestamp: str
    paciente: Optional[Paciente] = Relationship(back_populates="sensor_readings")
    visita: Optional[Visita] = Relationship(back_populates="sensor_readings")
