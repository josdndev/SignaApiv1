from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import tempfile, os
import numpy as np
from .rppg_core import read_video_with_face_detection_and_FS, CHROME_DEHAAN, extract_heart_rate
from .vitails import extract_respiratory_rate, calculate_hrv
from sqlmodel import SQLModel, Session, create_engine, select
from .models import Doctor, Paciente, HistoriaClinica, Visita, Diagnostico

app = FastAPI()
engine = create_engine("sqlite:///database.db")
SQLModel.metadata.create_all(engine)

# Endpoint para registrar doctor
@app.post("/doctores/")
def crear_doctor(nombre: str, email: str, google_id: str = None, especialidad: str = None):
    doctor = Doctor(nombre=nombre, email=email, google_id=google_id, especialidad=especialidad)
    with Session(engine) as session:
        session.add(doctor)
        session.commit()
        session.refresh(doctor)
    return doctor

# Endpoint para consultar doctores
@app.get("/doctores/")
def listar_doctores():
    with Session(engine) as session:
        doctores = session.exec(select(Doctor)).all()
    return doctores

# Endpoint para registrar paciente
@app.post("/pacientes/")
def crear_paciente(nombre: str, cedula: str, edad: int, especialista: str, hora_entrada: str, estado_triaje: str):
    paciente = Paciente(nombre=nombre, cedula=cedula, edad=edad, especialista=especialista, hora_entrada=hora_entrada, estado_triaje=estado_triaje)
    with Session(engine) as session:
        session.add(paciente)
        session.commit()
        session.refresh(paciente)
    return paciente

# Endpoint para consultar pacientes
@app.get("/pacientes/")
def listar_pacientes():
    with Session(engine) as session:
        pacientes = session.exec(select(Paciente)).all()
    return pacientes

# Endpoint para registrar historia clínica
@app.post("/historias/")
def crear_historia(paciente_id: int, fecha: str):
    historia = HistoriaClinica(paciente_id=paciente_id, fecha=fecha)
    with Session(engine) as session:
        session.add(historia)
        session.commit()
        session.refresh(historia)
    return historia

# Endpoint para consultar historias clínicas
@app.get("/historias/")
def listar_historias():
    with Session(engine) as session:
        historias = session.exec(select(HistoriaClinica)).all()
    return historias

# Endpoint para registrar visita
@app.post("/visitas/")
def crear_visita(historia_id: int, hora_entrada: str, evaluacion_triaje: str, prediagnostico: str, especialidad: str, numero_visita: int):
    visita = Visita(
        historia_id=historia_id,
        hora_entrada=hora_entrada,
        evaluacion_triaje=evaluacion_triaje,
        prediagnostico=prediagnostico,
        especialidad=especialidad,
        numero_visita=numero_visita
    )
    with Session(engine) as session:
        session.add(visita)
        session.commit()
        session.refresh(visita)
    return visita

# Endpoint para consultar visitas
@app.get("/visitas/")
def listar_visitas():
    with Session(engine) as session:
        visitas = session.exec(select(Visita)).all()
    return visitas

# Endpoint para obtener todas las visitas con los datos del paciente
@app.get("/visitas_con_pacientes/")
def listar_visitas_con_pacientes():
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
        
        return resultado

@app.post("/rppg/")
async def analyze_video(file: UploadFile = File(...)):
    # Crear un archivo temporal
    with tempfile.NamedTemporaryFile(delete=True) as tmp:
        # Guardar el archivo subido en el archivo temporal
        tmp.write(await file.read())
        tmp.flush()

        # Leer el video y detectar la cara
        fps, time, sig, bvp, ibi, hr = read_video_with_face_detection_and_FS(tmp.name, CHROME_DEHAAN)

        # Calcular la tasa de respiración
        respiratory_rate = extract_respiratory_rate(sig, fps)

        # Calcular la variabilidad de la frecuencia cardíaca (HRV)
        hrv = calculate_hrv(ibi)

        # Retornar los resultados
        return JSONResponse(content={
            "message": "Video processed successfully",
            "fps": fps,
            "time": time,
            "sig": sig.tolist(),
            "bvp": bvp.tolist(),
            "ibi": ibi.tolist(),
            "hr": hr.tolist(),
            "respiratory_rate": respiratory_rate,
            "hrv": hrv
        })

# Endpoint para registrar diagnostico
@app.post("/diagnosticos/")
def crear_diagnostico(visita_id: int, diagnostico: str, resultado_rppg: str, informe_prediagnostico: str):
    diag = Diagnostico(
        visita_id=visita_id,
        diagnostico=diagnostico,
        resultado_rppg=resultado_rppg,
        informe_prediagnostico=informe_prediagnostico
    )
    with Session(engine) as session:
        session.add(diag)
        session.commit()
        session.refresh(diag)
    return diag

@app.get("/diagnosticos/")
def listar_diagnosticos():
    with Session(engine) as session:
        diagnosticos = session.exec(select(Diagnostico)).all()
    return diagnosticos