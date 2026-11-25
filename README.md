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

Para ejecutar las pruebas:

```bash
python -m unittest -v
```