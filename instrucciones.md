Actúa como desarrollador Python/Flask para un proyecto universitario de software veterinario. 
El enfoque principal del proyecto es la DOCUMENTACIÓN y la TRAZABILIDAD, por lo que el código debe ser lo más SENCILLO y DIRECTO posible (sin arquitecturas complejas, sin estilos avanzados, código en 1 o 2 archivos con Flask y SQLite).
REGLAS DE TRABAJO: 
1\. Genera código mínimo funcional para Flask (vistas sencillas en Jinja2/HTML plano, sqlite3 directo). 

# Detalle HU:
## HU 5 gestion de citas:
 como recepcionista me gustaria que la aplicacion tenga un gestor que me ayude a ver que horarios tienen disponibles los veterinarios para evitar malas asignaciones.
CA 5.1 (Vista visual de agenda): La pantalla debe mostrar una grilla o calendario indicando los bloques de tiempo libres y ocupados por cada veterinario[2].
CA 5.2 (Bloqueo de horas pasadas): El sistema no debe permitir seleccionar horas pasadas a la fecha/hora actual.
CA 5.3 (Actualización): Al agendar o cancelar una cita, el bloque de horario debe cambiar de color (ej. Verde = Libre, Rojo = Ocupado) en tiempo real.

## HU 6 historia clinica:
 Como veterinario me gustaria poder agregar a la historia clinica de cada paciente para poder tener un control mas detallado de el y hacerle seguimiento.
CA 6.1 (Control de acceso): Solo los usuarios logueados con el rol de Veterinario pueden agregar o editar notas en la historia clínica[4].
CA 6.2 (Registro médico): Permite ingresar Diagnóstico, Anamnesis, Observaciones y Fecha de atención.
CA 6.3 (Alerta médica): Si la mascota tiene alergias o condiciones registradas, el sistema debe mostrar una etiqueta roja o aviso destacado en la parte superior de la historia clínica[4].

## HU 7 recetas:
 como veterinatrio quiero poder emitir un receta medica a una mascota y que esta se pueda ver en recepcion para un correcto suministro de medicamentos.
CA 7.1 (Redacción de receta): El veterinario puede prescribir medicamentos, indicando dosis y duración del tratamiento.
CA 7.2 (Exportación a PDF): El sistema debe incluir un botón para descargar la receta en formato PDF mostrando el logo de la veterinaria y la firma digitalizada del médico[4].
CA 7.3 (Visibilidad en recepción): La receta emitida debe ser consultable inmediatamente por la recepcionista para coordinar la entrega o despacho de medicamentos

## HU 10 Notificaciones: 
Yo como usuario me gustaria que el sistema me notificara por algun medio las citas programadas o cualquier informacion importante.
CA 10.1 (Envío automático): Al confirmar una cita en el sistema, se debe enviar de forma automática un correo electrónico al cliente[4].
CA 10.2 (Contenido del correo): El mensaje debe incluir: Nombre del cliente, Mascota, Fecha, Hora, Nombre del Veterinario y Recordatorio de llegar 10 minutos antes[4].
CA 10.3 (Manejo de errores): Si el correo falla al enviarse, la cita de todos modos se guarda correctamente en la base de datos y se notifica la alerta al usuario.

3\. Al final de cada archivo o función que me entregues, ve paso a paso si consideras que sea necesaruio, dame SIEMPRE el comando exacto para hacer el commit en Git con el formato de trazabilidad:

- git commit -m "feat(TAREA-01): crear estructura inicial app flask" 
- git commit -m "feat(HU-01): agregar formulario de registro de dueños" 
- git commit -m "feat(HU-03): implementar agendamiento de citas y validacion"

Comienza entregándome el archivo principal \`app.py\` básico con la configuración inicial y las tablas necesarias.