Actúa como desarrollador Python/Flask para un proyecto universitario de software veterinario. 
El enfoque principal del proyecto es la DOCUMENTACIÓN y la TRAZABILIDAD, por lo que el código debe ser lo más SENCILLO y DIRECTO posible (sin arquitecturas complejas, sin estilos avanzados, código en 1 o 2 archivos con Flask y SQLite).
REGLAS DE TRABAJO: 
1\. Genera código mínimo funcional para Flask (vistas sencillas en Jinja2/HTML plano, sqlite3 directo). 
2\. Desarrolla las funciones básicas según las tarjetas de Jira: 
- Registro de Dueños (HU-1) 
- Ficha de Mascotas (HU-2) 
- Agendamiento de Citas con validación de horario no duplicado (HU-3) 
- Consulta de Citas (HU-4) 

# Detalle HU:
## - HU 1 (Registro dueños) 
como recepcionista deseo ingresar los datos de cada duelo de una o varias mascotas, donde contenga su informacion fundmental como nombre, telefono, direccion y un correo.
### Criterios de Aceptación:
- CA 1.1 (Campos obligatorios): El formulario debe requerir obligatoriamente: Nombre completo, Teléfono, Dirección y Correo electrónico.
- CA 1.2 (Validación básica): El campo de correo debe validar que tenga formato correcto (ejemplo: usuario@dominio.com) y el teléfono debe aceptar solo números.

## - HU 2 (registro mascotas) 
como recepcionista de mascotas quiero tener la ficha de cada una donde tenga su nombre, especie, raza, edad, peso y una descripcion de la mascota
### Criterios de Aceptación:
- CA 2.1 (Registro de datos): Debe permitir registrar Nombre, Especie (ej. Perro, Gato), Raza, Edad, Peso y una Descripción opcional[1].
- CA 2.2 (Vinculación con dueño): Permite seleccionar y asociar a la mascota con un dueño previamente registrado (búsqueda por número de documento o nombre)

## - HU 3 (Citas) 
yo como recepcionista deseo asignarle una cita a un dueño con alguno de los veterinarios que tengan disponible en ese momento
### Criterios de Aceptación:
- CA 3.1 (Formulario de reserva): Debe permitir seleccionar Dueño/Mascota, Veterinario, Fecha y Bloque de horario.
- CA 3.2 (Validación de no colisión): El sistema debe bloquear la asignación e impedir guardar si el veterinario seleccionado ya tiene una cita a esa misma hora[4].
- CA 3.3 (Estado): La cita creada debe guardarse inicialmente en estado Programada.

## - HU 4 citas: 
yo como dueño de una o mas mascotas quiero poder ver informacion de la cita fecha, hora y veterinario
### Criterios de Aceptación:
- CA 4.1 (Vista de cliente): El cliente puede ver el listado de sus citas agendadas desde su vista pública o panel.
- CA 4.2 (Detalle visible): Cada cita debe mostrar claramente: Fecha, Hora, Nombre de la Mascota y Veterinario asignado[2].
- CA 4.3 (Sin registros): Si el cliente no tiene citas pendientes, debe mostrarse el mensaje "No registra citas programadas".

3\. Al final de cada archivo o función que me entregues, ve paso a paso si consideras que sea necesaruio, dame SIEMPRE el comando exacto para hacer el commit en Git con el formato de trazabilidad:

- git commit -m "feat(TAREA-01): crear estructura inicial app flask" 
- git commit -m "feat(HU-01): agregar formulario de registro de dueños" 
- git commit -m "feat(HU-03): implementar agendamiento de citas y validacion"

Comienza entregándome el archivo principal \`app.py\` básico con la configuración inicial y las tablas necesarias.