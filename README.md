# optica_appointment
# optica_appointment

Módulo Odoo 17 para gestionar citas de pacientes de una óptica.

## Arquitectura

- **Modelo backend**: `optica.appointment` concentra la agenda y hereda de `mail.thread` y `mail.activity.mixin` para disponer de chatter, seguimiento de cambios y actividades.
- **Fecha y hora separadas**: se guardan en `appointment_date` y `appointment_time` para mantener un formulario simple; además se calcula `appointment_datetime` para vistas de calendario, ordenación y filtros.
- **Website público**: el controlador expone `/agendar-cita` para GET/POST y `/agendar-cita/gracias` como confirmación. La creación se realiza con `sudo()` porque el usuario público no debe tener acceso directo al modelo.
- **Estado inicial frontend**: las citas creadas desde el sitio web se registran como `Confirmada` para un flujo rápido. El equipo puede cancelarlas, marcarlas realizadas o devolverlas a borrador desde backend.
- **Seguridad**: los usuarios internos tienen permisos CRUD sobre citas mediante `ir.model.access.csv`; el visitante público solo puede usar el formulario controlado por HTTP.

## Archivos principales

- `__manifest__.py`: metadatos, dependencias y carga de datos/assets.
- `models/optica_appointment.py`: modelo, campos, estado, cálculo de fecha/hora y acciones de estado.
- `controllers/main.py`: rutas públicas, validación básica y creación de citas.
- `views/optica_appointment_views.xml`: vistas lista, formulario, calendario, búsqueda, acción y menús.
- `views/website_appointment_templates.xml`: formulario responsive y página de éxito.
- `security/ir.model.access.csv`: permisos para usuarios internos.
- `static/src/scss/appointment.scss`: estilos ligeros del formulario web.
