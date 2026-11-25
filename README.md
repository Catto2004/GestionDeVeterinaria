# GestionDeVeterinaria

Proyecto web para la gestion de dueños, mascotas y citas veterinarias.

## Inicio rapido

```bash
conda activate AdministracionSoftware
pip install -r requirements.txt
python app.py
```

La aplicación estará disponible en `http://127.0.0.1:5000`.

Registra dueños, mascotas y veterinarios antes de agendar citas. Para consultar
las citas programadas, ingresa el documento del dueño.

## Sprint 2

- Consulta `/schedule` para ver disponibilidad por veterinario. Las citas se
  pueden cancelar desde la agenda; los cambios se actualizan automáticamente.
- Registra un veterinario y usa **Crear cuenta veterinaria** para habilitar el
  acceso a historias clínicas y emisión de recetas. El alta abierta es una
  decisión para este prototipo universitario, no una política segura para
  producción.
- Las recetas pueden consultarse desde recepción y descargarse como PDF. El PDF
  usa un encabezado provisional y una línea de firma; aún no incluye imágenes
  reales de logo ni firma digitalizada.
- Para enviar confirmaciones de cita, configura `SMTP_HOST`, `SMTP_PORT`,
  `SMTP_FROM`, `SMTP_USER` y `SMTP_PASSWORD`. `SMTP_USE_TLS` usa STARTTLS
  (predeterminado); configura `SMTP_USE_SSL=true` si tu servidor requiere SSL.
  Sin SMTP, la cita se guarda igualmente y se muestra una alerta.
- Define `FLASK_SECRET_KEY` antes de usar las sesiones fuera de desarrollo.

## Sprint 3

- En `/inventory` registra medicamentos, alimentos y juguetes, consulta stock y
  precio unitario, y registra reposiciones. Los medicamentos con menos de cinco
  unidades aparecen resaltados.
- `/procedures` muestra el catálogo inicial (consulta general, vacunación,
  desparasitación y cirugía). Al crear un servicio, un precio vacío indica tarifa
  variable; un precio informado queda fijo.
- En `/procedures/new` registra la mascota, el veterinario, el servicio y el
  valor cobrado. Indica los insumos usados para que el stock se descuente en la
  misma transacción; si se asocia una cita programada, queda completada.
- El historial queda disponible en `/procedure-history` y también aparece en
  la historia clínica de la mascota.

Para ejecutar las pruebas:

```bash
python -m unittest -v
```