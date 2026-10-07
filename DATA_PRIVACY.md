# Privacidad y estructura de datos de ANNA

Este documento resume cómo ANNA separa proyectos, participantes y sesiones de investigación.

## Proyecto

El archivo JSON del proyecto describe el material de trabajo: vídeos, pausas temporales, hotspots, apoyos, estilos, tiempos, audios e imágenes asociados al proyecto. No debe guardar participantes, selección activa de participante, sesiones, métricas históricas ni datos clínicos.

Los recursos creados o importados dentro de ANNA se guardan como rutas relativas al entorno del proyecto cuando es posible. Si un vídeo procede de una ubicación externa, debe tratarse como recurso local del profesional y no incluirse en exportaciones de investigación.

## Participantes

Los participantes se guardan localmente en `anna_data/users.csv`. El identificador interno estable es `id`; el nombre visible se guarda en `name`; `active` permite archivar o reactivar. Los campos heredados `notes` y `group` se conservan solo por compatibilidad con CSV antiguos, no se muestran en la interfaz ni se rellenan automáticamente.

Las preferencias locales de idioma se guardan en `anna_data/preferences.json`.

Para mantener compatibilidad, cuando `anna_data` todavía no existe ANNA puede copiar desde `emma_data` o `lola_data` un `preferences.json` válido y un `users.csv` con cabecera válida. Las carpetas legacy nunca se borran ni se mueven automáticamente. Si la carpeta canónica ya existe, `anna_data` es autoritativa: no se fusionan ni sobrescriben archivos y cualquier conflicto se registra como advertencia técnica. En la aplicación empaquetada, una raíz `%LOCALAPPDATA%\Emma` preexistente se copia una sola vez a `%LOCALAPPDATA%\ANNA` si esta última todavía no existe; la raíz legacy se conserva intacta.

ANNA no solicita diagnóstico, dirección, teléfono, correo, fecha de nacimiento, documento de identidad, historia clínica ni notas clínicas libres.

## Sesiones

Cada sesión de investigación se guarda en:

```text
results/
  sessions/
    <session_id>/
      session.json
      events.jsonl
      summary.json
```

`session_id` se genera de forma técnica y no incluye nombres de participantes. La sesión guarda el participante de esa sesión o la condición anónima, eventos, tiempos, vídeos, pausas, hotspots, apoyos, marcas profesionales, resumen descriptivo y versión de esquema.

Las sesiones no deben contener rutas absolutas del equipo, información clínica no solicitada, datos de otros participantes, selección global de la aplicación ni copias completas del proyecto.

## Exportaciones

La exportación local completa puede incluir `participant_id` y `participant_name`. La exportación anonimizada conserva `participant_id` y excluye los nombres visibles (`participant_name`, `user_name`). Los campos heredados `notes` y `group` se excluyen de las exportaciones.

Antes de escribir CSV, los valores que parecen rutas absolutas personales se sustituyen por un valor vacío. La codificación usada es UTF-8.

## Logs técnicos

`results/editor_hotspots_log.jsonl` es un log técnico de depuración y uso interno. No forma parte de los resultados de investigación y no debe presentarse como datos de sesión. Los logs técnicos no deben incluir participantes ni rutas completas salvo en un contexto de depuración estrictamente local.

## Limitaciones conocidas

Los proyectos antiguos, incluidos los creados con Lola, pueden contener rutas externas de vídeo si fueron creados antes de aplicar estas reglas. En ese caso, ANNA debe poder abrirlos por compatibilidad, pero las exportaciones de investigación deben evitar publicar esas rutas.
