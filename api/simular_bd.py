import os
import random
from datetime import datetime, timedelta
from sqlmodel import Session, create_engine
from api.models import Doctor, Paciente, HistoriaClinica, Visita, Diagnostico

# Usar la variable de entorno DATABASE_URL para conectar a la base de datos correcta
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///database.db")
engine = create_engine(DATABASE_URL)

print(f"Conectando a la base de datos: {DATABASE_URL}")

doctores = [
    {"nombre": "Dr. Juan Cardona", "email": "juan.cardona@gmail.com", "google_id": "1001", "especialidad": "Cardiología"},
    {"nombre": "Dra. Ana Torres", "email": "ana.torres@gmail.com", "google_id": "1002", "especialidad": "Pediatría"},
    {"nombre": "Dr. Luis Mendoza", "email": "luis.mendoza@gmail.com", "google_id": "1003", "especialidad": "Medicina General"}
]

nombres = [
    "Juan Perez", "Maria Gomez", "Carlos Ruiz", "Ana Torres", "Luis Mendoza", "Sofia Castro", "Pedro Diaz", "Lucia Fernandez", "Miguel Lopez", "Laura Morales",
    "Jorge Herrera", "Valentina Rios", "Andres Vargas", "Camila Suarez", "Ricardo Soto", "Paula Jimenez", "Fernando Silva", "Gabriela Ortiz", "Diego Romero", "Isabel Navarro",
    "Sebastian Cruz", "Monica Salazar", "Hector Paredes", "Patricia Aguirre", "Oscar Castillo", "Daniela Ponce", "Raul Cordero", "Carolina Espinoza", "Julio Zamora", "Estefania Leon"
]

triaje = ["Rojo", "Amarillo", "Verde"]

try:
    with Session(engine) as session:
        # Doctores
        for doc in doctores:
            doctor = Doctor(**doc)
            session.add(doctor)
        session.commit()
        print("Doctores insertados")
        # Pacientes
        for i in range(30):
            paciente = Paciente(
                nombre=nombres[i],
                cedula=f"V{random.randint(10000000,99999999)}",
                edad=random.randint(1, 99)
            )
            session.add(paciente)
            session.commit()
            session.refresh(paciente)
            # Historia clínica
            historia = HistoriaClinica(paciente_id=paciente.id, fecha=(datetime(2025,7,27) - timedelta(days=random.randint(0,365))).strftime('%Y-%m-%d'))
            session.add(historia)
            session.commit()
            session.refresh(historia)
            # Visitas y Diagnósticos
            for v in range(random.randint(1,2)):
                visita = Visita(
                    historia_id=historia.id,
                    hora_entrada=f"2025-07-27T{random.randint(8,18)}:{random.randint(0,59):02d}",
                    evaluacion_triaje=random.choice(triaje),
                    prediagnostico=f"Prediagnóstico automático {v+1}",
                    especialidad=random.choice([d["especialidad"] for d in doctores]),
                    numero_visita=v+1
                )
                session.add(visita)
                session.commit()
                session.refresh(visita)
                for d in range(random.randint(1,2)):
                    diag = Diagnostico(
                        visita_id=visita.id,
                        diagnostico=random.choice(["Hipertensión", "Resfriado", "Migraña", "Dermatitis", "Arritmia", "Sin diagnóstico"]),
                        resultado_rppg=f"HR:{random.randint(60,100)} RR:{random.randint(12,20)} SDNN:{random.randint(20,80)} RMSSD:{random.randint(20,80)}",
                        informe_prediagnostico=f"Informe generado automáticamente para {paciente.nombre} en visita {v+1}."
                    )
                    session.add(diag)
        session.commit()
    print("Base de datos simulada con doctores, pacientes, historias, visitas y diagnósticos.")
except Exception as e:
    print(f"Error al poblar la base de datos: {e}")
