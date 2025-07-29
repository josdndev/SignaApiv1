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

## Ejecución Local
1. Instala dependencias:
   ```bash
   pip install -r requirements.txt
   ```
2. Ejecuta el servidor:
   ```bash
   uvicorn api.main:app --reload
   ```
3. Accede a la documentación interactiva en:
   - http://localhost:8000/docs

## Despliegue en Railway

### Requisitos
- Cuenta en Railway (https://railway.app)
- Repositorio Git (GitHub, GitLab, Bitbucket)

### Pasos para desplegar

1. **Preparar el repositorio:**
   - Asegúrate de que todos los archivos estén en tu repositorio Git
   - Los archivos necesarios ya están incluidos:
     - `Procfile`: Configuración para Railway
     - `requirements.txt`: Dependencias de Python
     - `runtime.txt`: Versión de Python

2. **Conectar con Railway:**
   - Ve a [Railway Dashboard](https://railway.app/dashboard)
   - Haz clic en "New Project"
   - Selecciona "Deploy from Git Repo"
   - Autoriza Railway para acceder a tu repositorio
   - Selecciona tu repositorio

3. **Configuración automática:**
   - Railway detectará automáticamente que es una aplicación Python
   - Usará el `Procfile` para iniciar la aplicación
   - Instalará las dependencias del `requirements.txt`

4. **Variables de entorno (opcional):**
   - Si necesitas configurar variables de entorno, puedes hacerlo en la sección "Variables" de tu proyecto en Railway

5. **Acceso a la aplicación:**
   - Una vez desplegada, Railway te proporcionará una URL pública
   - La documentación estará disponible en: `https://tu-app.railway.app/docs`

### Notas importantes
- La base de datos SQLite se reiniciará en cada despliegue. Para producción, considera usar PostgreSQL o MySQL
- Railway asignará automáticamente el puerto a través de la variable de entorno `$PORT`
- El archivo `Procfile` ya está configurado para usar `api.main:app`

## Contacto
Para dudas o soporte, contacta al equipo de desarrollo.
