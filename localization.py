from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QAbstractButton, QComboBox, QLabel, QMenu, QWidget

from data_storage import preferences_path

PRODUCT_NAME = "ANNA"
PRODUCT_SUBTITLE = "Interactive Video Activities for AAC"
PRODUCT_TITLE = f"{PRODUCT_NAME} — {PRODUCT_SUBTITLE}"
DEFAULT_LANGUAGE = "en-US"
SUPPORTED_LANGUAGES = ("en-US", "es")

EN_US = {
    "language.en_us": "English (United States)",
    "language.es": "Español",
    "menu.file": "File", "menu.mode": "Mode", "menu.research": "Research",
    "menu.language": "Language", "menu.help": "Help",
    "action.new_project": "New project", "action.open_project": "Open project…",
    "action.save": "Save", "action.save_as": "Save as…",
    "action.add_video": "Add video…", "action.delete_video": "Delete video",
    "action.replace_video": "Replace video…", "action.rename_video": "Rename video…",
    "action.exit": "Exit",
    "action.about": "About ANNA", "action.open_sample_project": "Open sample project",
    "action.research_toggle": "Enable / disable research",
    "action.manage_participants": "Manage participants…", "action.session_summary": "Session summary",
    "action.export_csv": "Export CSV…",
    "mode.professional": "Professional mode", "mode.user": "User mode",
    "label.research": "Research:", "label.selected_pause_none": "Selected pause: none",
    "label.supports": "Supports", "label.navigation": "Navigation",
    "label.show_hotspots": "Show hotspots", "label.no_participant": "No participant",
    "label.research_anonymous": "Research: anonymous session",
    "label.research_participant": "Research: {name}", "label.tools": "TOOLS",
    "label.selected_pause": "Selected pause: {time}", "label.active_pause": "Active pause: {time}",
    "tool.select_move": "Select/move", "tool.rectangle": "Rectangle", "tool.ellipse": "Ellipse",
    "tool.edit": "Edit", "tool.delete": "Delete",
    "tooltip.select_move": "Select and move a hotspot",
    "tooltip.draw_rectangle": "Draw a rectangular hotspot",
    "tooltip.draw_ellipse": "Draw an elliptical hotspot",
    "tooltip.edit_hotspot": "Edit the selected hotspot",
    "tooltip.delete_hotspot": "Delete the selected hotspot",
    "tooltip.switch_mode": "Switch between professional and user mode",
    "tooltip.return_edit": "Return to edit mode to use this tool",
    "tooltip.select_video": "Select {name}", "tooltip.go_start": "Go to the start of the video",
    "tooltip.continue_video": "Continue the video from the interactive pause",
    "button.start": "Go to start", "button.play": "Play", "button.pause": "Pause",
    "button.stop": "Stop", "button.continue": "Continue", "button.ok": "OK",
    "button.cancel": "Cancel", "button.close": "Close", "button.select": "Select",
    "button.add": "Add", "button.new": "New…", "button.edit": "Edit…",
    "button.deactivate": "Deactivate…", "button.reactivate": "Reactivate",
    "button.continue_without_user": "Continue without a user",
    "button.select_participant": "Select participant", "button.new_participant": "New participant…",
    "button.start_anonymous": "Start anonymous session", "button.copy_summary": "Copy summary",
    "button.delete": "Delete", "button.replace": "Replace", "button.delete_support": "Delete support",
    "button.select_audio": "Select audio…", "button.record": "Record",
    "button.listen": "Listen", "button.delete_audio": "Delete audio",
    "button.select_image": "Select image…", "button.delete_image": "Delete image",
    "button.change_color": "Change color…",
    "tooltip.current_hotspot_color": "Current hotspot color",
    "tooltip.choose_hotspot_color": "Choose from six hotspot colors",
    "tooltip.change_hotspot_color": "Change hotspot color",
    "tooltip.select_audio": "Select an audio file", "tooltip.record_audio": "Start audio recording",
    "tooltip.stop_recording": "Stop the current recording", "tooltip.listen_audio": "Listen to the prepared audio",
    "tooltip.delete_audio": "Delete the associated audio",
    "annotation.turn": "Turn", "annotation.appropriate": "Appropriate", "annotation.review": "Review",
    "dialog.hotspot_content": "Hotspot content", "dialog.configure_support": "Configure {name}",
    "dialog.participants": "Participants", "dialog.session_user": "Session user",
    "dialog.select_participant": "Select participant", "dialog.research": "Research",
    "dialog.session_summary": "Session summary", "dialog.export_csv": "Export CSV", "dialog.audio": "Audio",
    "dialog.add_video": "Add video", "dialog.replace_video": "Replace video", "dialog.rename_video": "Rename video",
    "label.video_name": "Video name:",
    "dialog.delete_video": "Delete video", "dialog.edit_hotspot": "Edit hotspot",
    "dialog.delete_hotspot": "Delete hotspot", "dialog.invalid_json": "Invalid JSON",
    "dialog.overlap": "Overlap not allowed", "dialog.empty_support": "Empty support",
    "dialog.select_pause": "Select a pause", "dialog.active_research": "Research active",
    "dialog.deactivate_participant": "Deactivate participant",
    "field.message": "Message", "field.font": "Font", "field.size_style": "Size and style",
    "field.text_color": "Text color", "field.text_background": "Text background",
    "field.background_opacity": "Background opacity", "field.category": "Word type/category",
    "field.color": "Color", "field.audio": "Audio", "field.text": "Text",
    "field.image": "Image", "field.participant": "Participant", "field.code": "Code",
    "field.status": "Status", "field.participant_name": "Participant name",
    "option.show_text": "Display text on screen", "option.bold": "Bold",
    "option.uppercase": "Display in uppercase",
    "option.tts": "Read the text aloud when no audio is available",
    "option.visible_user": "Visible in user mode", "option.visible": "Visible",
    "option.show_archived": "Show archived",
    "status.no_audio": "No audio", "status.audio_ready": "Audio ready",
    "status.recording": "Recording…", "status.no_image": "No image",
    "status.participant_archived": "Participant deactivated.",
    "status.turn_recorded": "Turn recorded", "status.appropriate_recorded": "Appropriate recorded",
    "status.review_recorded": "Review recorded",
    "status.archived": "Archived", "status.no_users": "No users have been created",
    "placeholder.new_user_name": "New user name",
    "category.unspecified": "Unspecified", "category.proper_person": "Person / proper name",
    "category.noun_object": "Noun / object", "category.verb_action": "Verb / action",
    "category.adjective": "Adjective", "category.adverb": "Adverb",
    "category.social_expression": "Social expression", "category.function_word": "Function word",
    "category.place": "Place", "category.other": "Other",
    "color.turquoise": "Turquoise", "color.blue": "Blue", "color.green": "Green",
    "color.orange": "Orange", "color.pink": "Pink", "color.red": "Red",
    "video.automatic_name": "Video {number}", "support.automatic_name": "Support {number}",
    "segment.title": "Segment", "segment.start": "Start", "segment.end": "End",
    "segment.apply": "Apply", "segment.reset": "Reset",
    "segment.invalid_title": "Invalid segment",
    "segment.invalid_format": "Enter time as HH:MM:SS.mmm.",
    "segment.invalid_start": "The start must be before the end and before the physical end of the video.",
    "segment.invalid_end": "The end must be after the start and cannot exceed the physical duration.",
    "segment.invalid_interval": "The segment must satisfy: 0 ≤ Start < End ≤ video duration.",
    "segment.pending_title": "Unsaved segment changes",
    "segment.pending_message": "The video segment has unconfirmed changes.",
    "segment.save_changes": "Apply changes", "segment.discard_changes": "Discard changes",
    "file.video_filter": "Video (*.mp4 *.mov *.m4v *.avi)",
    "file.audio_filter": "Audio (*.wav *.mp3 *.m4a *.aac)",
    "file.image_filter": "Image (*.png *.jpg *.jpeg *.bmp)", "file.json_filter": "JSON (*.json)",
    "message.export_csv_success": "CSV export completed successfully.\n\nDestination: {path}",
    "message.export_csv_error": "CSV export could not be completed.\n\n{error}",
    "message.about": "Interactive video activity editor for AAC.",
    "label.version": "Version", "label.license": "License",
    "message.participants_hint": "Select a registered participant or add a new one.",
    "message.research_participant": "Select the participant for this research session.",
    "message.session_user_title": "Select the user who will take part in the session",
    "message.session_user_hint": "You can also create a new user without leaving this window.",
    "message.participant_required": "Enter the participant's name.",
    "message.participant_duplicate": "A participant with that name already exists.",
    "message.participant_edit_none": "A participant must be selected before editing.",
    "message.participant_delete_none": "A participant must be selected before deactivating.",
    "message.participant_has_sessions": "This participant has recorded sessions. They will be hidden from the active list, but historical data will be preserved.",
    "message.participant_delete": "Do you want to permanently delete this participant?",
    "message.create_user_required": "Enter a name to create the user.",
    "message.select_or_create_user": "Select a user or create a new one.",
    "message.summary_intro": "Data from the active session or, if it has ended, the most recent session.",
    "message.select_hotspot": "Select a hotspot first.",
    "message.delete_hotspot": "Do you want to delete this hotspot?",
    "message.delete_last_hotspot": "Do you want to delete this hotspot? Because it is the last one at this pause, the pause will also be deleted.",
    "message.replace_video_content": "Replacing the video will delete its pauses, hotspots, and supports. Do you want to continue?",
    "message.replace_video_confirm": "This video contains pauses, hotspots, or supports. Replacing it will delete all associated content. Do you want to continue?",
    "message.delete_video_minimum": "The project must contain at least one video.",
    "message.delete_video_confirm": "This video and all its pauses, hotspots, and supports will be deleted. Do you want to continue?",
    "message.video_name_empty": "Enter a video name.",
    "message.video_name_too_long": "The video name cannot exceed 80 characters.",
    "message.video_name_duplicate": "Another video already uses that name.",
    "message.empty_support": "Configure the support before marking it as visible.",
    "message.select_pause": "Select or create a pause before configuring its supports.",
    "message.finish_research": "Finish the research session before changing the participant.",
    "message.overlap": "The hotspot cannot overlap another hotspot at this pause.",
    "message.audio_prepare_failed": "The selected audio file could not be prepared.",
    "message.no_microphone": "No microphone was detected.",
    "message.no_audio_to_play": "No audio is ready to play.",
    "message.max_characters": "Maximum {count} characters",
    "message.drag_video": "Drag to navigate through the video", "message.pause_at": "Pause {time}",
}

ES = {
    **EN_US,
    "menu.file": "Archivo", "menu.mode": "Modo", "menu.research": "Investigación",
    "menu.language": "Idioma", "menu.help": "Ayuda",
    "action.new_project": "Nuevo proyecto", "action.open_project": "Abrir proyecto…",
    "action.save": "Guardar", "action.save_as": "Guardar como…", "action.add_video": "Añadir vídeo…",
    "action.delete_video": "Eliminar vídeo", "action.replace_video": "Reemplazar vídeo…", "action.rename_video": "Renombrar vídeo…",
    "action.exit": "Salir",
    "action.about": "Acerca de ANNA", "action.open_sample_project": "Abrir proyecto de ejemplo",
    "action.research_toggle": "Activar / desactivar investigación",
    "action.manage_participants": "Gestionar participantes…", "action.session_summary": "Resumen de sesión",
    "action.export_csv": "Exportar CSV…",
    "mode.professional": "Modo terapeuta", "mode.user": "Modo usuario",
    "label.research": "Investigación:", "label.selected_pause_none": "Pausa seleccionada: ninguna",
    "label.supports": "Apoyos", "label.navigation": "Navegación", "label.show_hotspots": "Mostrar hotspots",
    "label.no_participant": "Sin participante", "label.research_anonymous": "Investigación: sesión anónima",
    "label.research_participant": "Investigación: {name}", "label.tools": "HERRAMIENTAS",
    "label.selected_pause": "Pausa seleccionada: {time}", "label.active_pause": "Pausa activa: {time}",
    "tool.select_move": "Seleccionar/mover", "tool.rectangle": "Rectángulo", "tool.ellipse": "Elipse",
    "tool.edit": "Editar", "tool.delete": "Eliminar",
    "tooltip.select_move": "Seleccionar y mover hotspot", "tooltip.draw_rectangle": "Dibujar hotspot rectangular",
    "tooltip.draw_ellipse": "Dibujar hotspot elíptico", "tooltip.edit_hotspot": "Editar contenido del hotspot seleccionado",
    "tooltip.delete_hotspot": "Eliminar hotspot seleccionado",
    "tooltip.switch_mode": "Cambiar entre modo terapeuta y modo usuario",
    "tooltip.return_edit": "Vuelve a edición para usar esta herramienta",
    "tooltip.select_video": "Seleccionar {name}", "tooltip.go_start": "Volver al inicio del vídeo",
    "tooltip.continue_video": "Continuar el vídeo desde la pausa interactiva",
    "button.start": "Ir al inicio", "button.play": "Reproducir", "button.pause": "Pausar",
    "button.stop": "Detener", "button.continue": "Continuar", "button.ok": "Aceptar",
    "button.cancel": "Cancelar", "button.close": "Cerrar", "button.select": "Seleccionar",
    "button.add": "Añadir", "button.new": "Nuevo…", "button.edit": "Editar…",
    "button.deactivate": "Dar de baja…", "button.reactivate": "Reactivar",
    "button.continue_without_user": "Continuar sin usuario", "button.select_participant": "Seleccionar participante",
    "button.new_participant": "Nuevo participante…", "button.start_anonymous": "Iniciar sesión anónima",
    "button.copy_summary": "Copiar resumen", "button.delete": "Eliminar", "button.replace": "Sustituir",
    "button.delete_support": "Eliminar apoyo", "button.select_audio": "Seleccionar audio…",
    "button.record": "Grabar", "button.listen": "Escuchar", "button.delete_audio": "Eliminar audio",
    "button.select_image": "Seleccionar imagen…", "button.delete_image": "Eliminar imagen",
    "button.change_color": "Cambiar color…",
    "tooltip.current_hotspot_color": "Color actual del hotspot",
    "tooltip.choose_hotspot_color": "Elegir entre seis colores del hotspot",
    "tooltip.change_hotspot_color": "Cambiar color del hotspot",
    "tooltip.select_audio": "Seleccionar un archivo de audio", "tooltip.record_audio": "Iniciar grabación de audio",
    "tooltip.stop_recording": "Detener la grabación actual", "tooltip.listen_audio": "Escuchar el audio preparado",
    "tooltip.delete_audio": "Eliminar el audio asociado",
    "annotation.turn": "Turno", "annotation.appropriate": "Adecuada", "annotation.review": "Revisar",
    "dialog.hotspot_content": "Contenido del hotspot", "dialog.configure_support": "Configurar {name}",
    "dialog.participants": "Participantes", "dialog.session_user": "Usuario de la sesión",
    "dialog.select_participant": "Seleccionar participante", "dialog.research": "Investigación",
    "dialog.session_summary": "Resumen de sesión", "dialog.export_csv": "Exportar CSV", "dialog.audio": "Audio",
    "dialog.add_video": "Añadir vídeo", "dialog.replace_video": "Reemplazar vídeo", "dialog.rename_video": "Renombrar vídeo",
    "label.video_name": "Nombre del vídeo:",
    "dialog.delete_video": "Eliminar vídeo", "dialog.edit_hotspot": "Editar hotspot",
    "dialog.delete_hotspot": "Eliminar hotspot", "dialog.invalid_json": "JSON no válido",
    "dialog.overlap": "Solapamiento no permitido", "dialog.empty_support": "Apoyo vacío",
    "dialog.select_pause": "Selecciona una pausa", "dialog.active_research": "Investigación activa",
    "dialog.deactivate_participant": "Dar de baja participante",
    "field.message": "Mensaje", "field.font": "Fuente", "field.size_style": "Tamaño y estilo",
    "field.text_color": "Color del texto", "field.text_background": "Fondo del texto",
    "field.background_opacity": "Opacidad del fondo", "field.category": "Tipo de palabra/categoría",
    "field.color": "Color", "field.audio": "Audio", "field.text": "Texto", "field.image": "Imagen",
    "field.participant": "Participante", "field.code": "Código", "field.status": "Estado",
    "field.participant_name": "Nombre del participante",
    "option.show_text": "Mostrar texto en pantalla", "option.bold": "Negrita",
    "option.uppercase": "Mostrar en mayúsculas", "option.tts": "Leer el texto en voz alta si no hay audio",
    "option.visible_user": "Visible en modo usuario", "option.visible": "Visible",
    "option.show_archived": "Mostrar archivados",
    "status.no_audio": "Sin audio", "status.audio_ready": "Audio preparado", "status.recording": "Grabando…",
    "status.no_image": "Sin imagen", "status.participant_archived": "Participante archivado.",
    "status.turn_recorded": "Turno registrado", "status.appropriate_recorded": "Respuesta adecuada registrada",
    "status.review_recorded": "Revisión registrada",
    "status.archived": "Archivado", "status.no_users": "No hay usuarios creados",
    "placeholder.new_user_name": "Nombre del nuevo usuario",
    "category.unspecified": "No especificado", "category.proper_person": "Persona / nombre propio",
    "category.noun_object": "Sustantivo / objeto", "category.verb_action": "Verbo / acción",
    "category.adjective": "Adjetivo", "category.adverb": "Adverbio",
    "category.social_expression": "Expresión social", "category.function_word": "Palabra funcional",
    "category.place": "Lugar", "category.other": "Otro",
    "color.turquoise": "Turquesa", "color.blue": "Azul", "color.green": "Verde",
    "color.orange": "Naranja", "color.pink": "Rosa", "color.red": "Rojo",
    "video.automatic_name": "Vídeo {number}", "support.automatic_name": "Apoyo {number}",
    "segment.title": "Segmento", "segment.start": "Inicio", "segment.end": "Fin",
    "segment.apply": "Aplicar", "segment.reset": "Restablecer",
    "segment.invalid_title": "Segmento no válido",
    "segment.invalid_format": "Introduce el tiempo como HH:MM:SS.mmm.",
    "segment.invalid_start": "El inicio debe ser anterior al fin y al final físico del vídeo.",
    "segment.invalid_end": "El fin debe ser posterior al inicio y no puede superar la duración física.",
    "segment.invalid_interval": "El segmento debe cumplir: 0 ≤ Inicio < Fin ≤ duración del vídeo.",
    "segment.pending_title": "Cambios de segmento sin guardar",
    "segment.pending_message": "El segmento de vídeo tiene cambios sin confirmar.",
    "segment.save_changes": "Aplicar cambios", "segment.discard_changes": "Descartar cambios",
    "file.video_filter": "Vídeo (*.mp4 *.mov *.m4v *.avi)",
    "file.audio_filter": "Audio (*.wav *.mp3 *.m4a *.aac)",
    "file.image_filter": "Imagen (*.png *.jpg *.jpeg *.bmp)", "file.json_filter": "JSON (*.json)",
    "message.export_csv_success": "La exportación CSV se ha completado correctamente.\n\nDestino: {path}",
    "message.export_csv_error": "No se ha podido completar la exportación CSV.\n\n{error}",
    "message.about": "Editor de actividades de vídeo interactivo para CAA.",
    "label.version": "Versión", "label.license": "Licencia",
    "message.participants_hint": "Selecciona un participante registrado o añade uno nuevo.",
    "message.research_participant": "Selecciona el participante de esta sesión de investigación.",
    "message.session_user_title": "Selecciona el usuario que participará en la sesión",
    "message.session_user_hint": "También puedes crear un usuario nuevo sin abandonar esta ventana.",
    "message.participant_required": "Escribe el nombre del participante.",
    "message.participant_duplicate": "Ya existe un participante con ese nombre.",
    "message.participant_edit_none": "Sin participante no se puede editar.",
    "message.participant_delete_none": "Sin participante no se puede eliminar.",
    "message.participant_has_sessions": "Este participante tiene sesiones registradas. Se ocultará de la lista activa, pero sus datos históricos se conservarán.",
    "message.participant_delete": "¿Quieres eliminar definitivamente a este participante?",
    "message.create_user_required": "Escribe un nombre para crear el usuario.",
    "message.select_or_create_user": "Selecciona un usuario o crea uno nuevo.",
    "message.summary_intro": "Datos de la sesión activa o, si ya terminó, de la sesión más reciente.",
    "message.select_hotspot": "Selecciona un hotspot primero.",
    "message.delete_hotspot": "¿Desea eliminar este hotspot?",
    "message.delete_last_hotspot": "¿Desea eliminar este hotspot? Al ser el último de esta pausa, también se eliminará la pausa.",
    "message.replace_video_content": "Al sustituir el vídeo se eliminarán sus pausas, hotspots y apoyos. ¿Quieres continuar?",
    "message.replace_video_confirm": "Este vídeo contiene pausas, hotspots o apoyos. Al reemplazarlo se eliminará todo su contenido asociado. ¿Desea continuar?",
    "message.delete_video_minimum": "El proyecto debe conservar al menos un vídeo.",
    "message.delete_video_confirm": "Se eliminarán este vídeo y todas sus pausas, hotspots y apoyos. ¿Desea continuar?",
    "message.video_name_empty": "Introduce un nombre para el vídeo.",
    "message.video_name_too_long": "El nombre del vídeo no puede superar los 80 caracteres.",
    "message.video_name_duplicate": "Otro vídeo ya utiliza ese nombre.",
    "message.empty_support": "Configura el apoyo antes de marcarlo como visible.",
    "message.select_pause": "Selecciona o crea una pausa antes de configurar sus apoyos.",
    "message.finish_research": "Finaliza la investigación antes de cambiar el participante.",
    "message.overlap": "El hotspot no puede superponerse con otro hotspot de esta pausa.",
    "message.audio_prepare_failed": "No se ha podido preparar el archivo de audio seleccionado.",
    "message.no_microphone": "No se ha detectado ningún micrófono.",
    "message.no_audio_to_play": "No hay audio preparado para escuchar.",
    "message.max_characters": "Máximo {count} caracteres",
    "message.drag_video": "Arrastra para navegar por el vídeo", "message.pause_at": "Pausa {time}",
}

CATALOGS = {"en-US": EN_US, "es": ES}
LANGUAGE_LABELS = {"en-US": EN_US["language.en_us"], "es": ES["language.es"]}
_language = DEFAULT_LANGUAGE


def validate_catalogs() -> None:
    if set(EN_US) != set(ES):
        missing_en = sorted(set(ES) - set(EN_US))
        missing_es = sorted(set(EN_US) - set(ES))
        raise RuntimeError(f"Localization catalog mismatch: en-US={missing_en}, es={missing_es}")


validate_catalogs()


def normalize_language(value: object) -> str:
    return str(value) if str(value) in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def set_language(value: object) -> str:
    global _language
    _language = normalize_language(value)
    return _language


def current_language() -> str:
    return _language


def tr(key: str, **values: object) -> str:
    catalog = CATALOGS[_language]
    if key not in catalog:
        raise KeyError(f"Missing localization key: {key}")
    return catalog[key].format(**values)


def settings_path(root: Path) -> Path:
    return preferences_path(root)


def load_language(root: Path) -> str:
    try:
        payload = json.loads(settings_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return set_language(DEFAULT_LANGUAGE)
    return set_language(payload.get("language"))


def save_language(root: Path, language: str) -> None:
    selected = set_language(language)
    path = settings_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"language": selected}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _key_for_text(text: str) -> str | None:
    for key in EN_US:
        if text == EN_US[key] or text == ES[key]:
            return key
    return None


def localize_widget_tree(widget: QWidget) -> None:
    objects = [widget, *widget.findChildren(QWidget), *widget.findChildren(QAction)]
    for obj in objects:
        if isinstance(obj, QMenu):
            key = _key_for_text(obj.title())
            if key:
                obj.setTitle(tr(key))
        elif isinstance(obj, QAction):
            key = _key_for_text(obj.text())
            if key:
                obj.setText(tr(key))
        elif isinstance(obj, QAbstractButton):
            key = _key_for_text(obj.text())
            if key:
                obj.setText(tr(key))
        elif isinstance(obj, QComboBox):
            for index in range(obj.count()):
                key = _key_for_text(obj.itemText(index))
                if key:
                    obj.setItemText(index, tr(key))
        elif isinstance(obj, QLabel):
            key = _key_for_text(obj.text())
            if key:
                obj.setText(tr(key))
        if hasattr(obj, "toolTip") and hasattr(obj, "setToolTip"):
            key = _key_for_text(obj.toolTip())
            if key:
                obj.setToolTip(tr(key))
        if hasattr(obj, "accessibleName") and hasattr(obj, "setAccessibleName"):
            key = _key_for_text(obj.accessibleName())
            if key:
                obj.setAccessibleName(tr(key))
