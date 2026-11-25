Actúa como desarrollador Python/Flask para un proyecto universitario de software veterinario. 
El enfoque principal del proyecto es la DOCUMENTACIÓN y la TRAZABILIDAD, por lo que el código debe ser lo más SENCILLO y DIRECTO posible (sin arquitecturas complejas, sin estilos avanzados, código en 1 o 2 archivos con Flask y SQLite).
REGLAS DE TRABAJO: 
1\. Genera código mínimo funcional para Flask (vistas sencillas en Jinja2/HTML plano, sqlite3 directo). 

# Detalle HU:
## HU 8
 como encargado me gustaria tener un inventario de todos lo elementos de la veterinaria, medicamentos, alimentos, juguetes etc.
CA 8.1 (Tabla de insumos): Muestra una tabla con Nombre del producto, Categoría (Medicamentos, Alimentos, Juguetes), Stock actual y Precio unitario[2].
CA 8.2 (Descuento automático de stock): Al finalizar una consulta médica o registrar un procedimiento donde se usen medicamentos e insumos, el sistema debe restar automáticamente la cantidad utilizada del inventario general[4].
CA 8.3 (Alerta de stock mínimo): Muestra un aviso en amarillo si la cantidad de un medicamento es inferior a 5 unidades.

## HU 9:
Como encargado me gustaria tener un registro de todos los procedimientos y elementos de la veterinaria. como no todos los procedimientos tienen un valor fijo este lo asignara el recepcionista.
CA 9.1 (Catálogo de procedimientos): Listado de servicios (ej. Consulta general, Vacunación, Desparasitación, Cirugía).
CA 9.2 (Tarifas variables): En procedimientos con precio no fijo, el sistema debe habilitar un campo editable para que la recepcionista ingrese el monto cobrado[2].
CA 9.3 (Historial): El procedimiento ejecutado debe quedar registrado en la atención del paciente.

3\. Al final de cada archivo o función que me entregues, ve paso a paso si consideras que sea necesaruio, dame SIEMPRE el comando exacto para hacer el commit en Git con el formato de trazabilidad:

- git commit -m "feat(TAREA-01): crear estructura inicial app flask" 
- git commit -m "feat(HU-01): agregar formulario de registro de dueños" 
- git commit -m "feat(HU-03): implementar agendamiento de citas y validacion"

Comienza entregándome el archivo principal \`app.py\` básico con la configuración inicial y las tablas necesarias.