from sqlmodel import Session
from .models import Paciente
from .main import engine
import random

nombres = [
    "Juan Perez", "Maria Gomez", "Carlos Ruiz", "Ana Torres", "Luis Mendoza", "Sofia Castro", "Pedro Diaz", "Lucia Fernandez", "Miguel Lopez", "Laura Morales",
    "Jorge Herrera", "Valentina Rios", "Andres Vargas", "Camila Suarez", "Ricardo Soto", "Paula Jimenez", "Fernando Silva", "Gabriela Ortiz", "Diego Romero", "Isabel Navarro",
    "Sebastian Cruz", "Monica Salazar", "Hector Paredes", "Patricia Aguirre", "Oscar Castillo", "Daniela Ponce", "Raul Cordero", "Carolina Espinoza", "Julio Zamora", "Estefania Leon"
]

especialistas = ["Cardiología", "Pediatría", "Medicina General", "Neurología", "Dermatología"]
triaje = ["Rojo", "Amarillo", "Verde"]

with Session(engine) as session:
    for i in range(30):
        paciente = Paciente(
            nombre=nombres[i],
            cedula=f"V{random.randint(10000000,99999999)}",
            edad=random.randint(1, 99),
            especialista=random.choice(especialistas),
            hora_entrada=f"2025-07-27T{random.randint(8,18)}:{random.randint(0,59):02d}",
            estado_triaje=random.choice(triaje)
        )
        session.add(paciente)
    session.commit()
print("30 pacientes simulados creados.")
