# SignaApi Backend

## Descripción
API clínica para gestión de pacientes, doctores, historias clínicas, visitas y diagnósticos. Compatible con autenticación de doctores vía Google.

## Estructura de la base de datos
- **Doctor**: id, nombre, email, google_id, especialidad
- **Paciente**: id, nombre, cedula, edad
- **HistoriaClinica**: id, paciente_id, fecha
- **Visita**: id, historia_id, hora_entrada, evaluacion_triaje, prediagnostico, especialidad, numero_visita
- **Diagnostico**: id, visita_id, diagnostico, resultado_rppg, informe_prediagnostico

## Endpoints principales
- POST/GET /doctores/
- POST/GET /pacientes/
- POST/GET /historias/
- POST/GET /visitas/
- POST/GET /diagnosticos/

## Simulación de datos
Ejecuta:
```bash
python -m api.simular_bd
```
para poblar la base de datos con datos de prueba.

## Integración Frontend
### Next.js / React
- Utiliza fetch/axios para consumir los endpoints REST.
- Ejemplo:
```js
const res = await fetch('http://localhost:8000/pacientes/');
const pacientes = await res.json();
```
- Puedes mapear los datos en tablas, cards o formularios según la entidad.

### Astro
- Usa la API fetch en server-side o client-side para consumir los endpoints.
- Ejemplo:
```js
const response = await fetch('http://localhost:8000/doctores/');
const doctores = await response.json();
```

## Autenticación Google
- El modelo Doctor soporta google_id/email.
- Integra NextAuth.js (Next.js) o Auth.js (Astro) para login con Google y vincula el email/google_id con la base de datos.

## Ejecución
1. Instala dependencias:
   ```bash
   pip install fastapi sqlmodel uvicorn
   ```
2. Ejecuta el servidor:
   ```bash
   uvicorn api.main:app --reload
   ```
3. Accede a la documentación interactiva en:
   - http://localhost:8000/docs

## Contacto
Para dudas o soporte, contacta al equipo de desarrollo.
