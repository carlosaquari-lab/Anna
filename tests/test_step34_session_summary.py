from __future__ import annotations

import json

from research_session import ResearchSessionManager
from research_summary import format_duration, format_research_summary


def test_session_summary_prioritizes_professional_information_and_relegates_navigation():
    summary = {
        "schema_version": 2,
        "started_at": "2026-07-29T18:02:35.000+00:00",
        "duration_ms": 86000,
        "user_name": "Ana",
        "is_anonymous": False,
        "videos_used": ["video-1", "video-2"],
        "pauses_presented": 2,
        "repeated_presentations": 1,
        "professional_turn_marked": 1,
        "response_marked_adequate": 0,
        "review_marked": 0,
        "continue_presses": 1,
        "hotspots_available": 2,
        "hotspots_activated": 1,
        "distinct_hotspots_activated": 1,
        "supports_available": 0,
        "supports_activated": 0,
        "manual_seeks": 1,
        "backward_seeks": 1,
        "forward_seeks": 0,
        "go_to_start_seeks": 1,
        "video_changes": 1,
        "hotspot_activity": [
            {
                "video_name": "Vídeo 1",
                "text": "nnn",
                "typology": "unspecified",
                "count": 1,
            }
        ],
        "support_activity": [],
        "per_video": [
            {
                "video_name": "Vídeo 1",
                "time_ms": 73000,
                "pauses_presented": 2,
                "repeated_presentations": 1,
                "hotspots_available": 2,
                "hotspots_activated": 1,
                "supports_available": 0,
                "supports_activated": 0,
                "professional_turn_marked": 1,
                "response_marked_adequate": 0,
                "review_marked": 0,
            },
            {
                "video_name": "Vídeo 2",
                "time_ms": 13000,
                "pauses_presented": 0,
                "repeated_presentations": 0,
                "hotspots_available": 0,
                "hotspots_activated": 0,
                "supports_available": 0,
                "supports_activated": 0,
                "professional_turn_marked": 0,
                "response_marked_adequate": 0,
                "review_marked": 0,
            },
        ],
    }

    text = format_research_summary(summary)

    assert text.index("RESUMEN DE LA SESIÓN") < text.index("INTERACCIÓN PROFESIONAL")
    assert text.index("INTERACCIÓN PROFESIONAL") < text.index("HOTSPOTS")
    assert text.index("DESGLOSE POR VÍDEO") < text.index("DETALLES TÉCNICOS")
    assert "Participante: Ana" in text
    assert "Fecha: 29/07/2026" in text
    assert "Duración: 1 min 26 s" in text
    assert "Vídeos trabajados: 2 vídeos" in text
    assert "Pausas presentadas: 2 pausas" in text
    assert "Pausas repetidas: 1 pausa" in text
    assert "Turnos: 1 turno" in text
    assert "Respuestas adecuadas: 0 respuestas" in text
    assert "Elementos para revisar: 0 elementos" in text
    assert "No se marcaron elementos para revisar." in text
    assert "Continuar: 1 pulsación" in text
    assert "Hotspots presentados: 2 hotspots" in text
    assert "Hotspots activados: 1 hotspot" in text
    assert "Activaciones de hotspots: 1 activación" in text
    assert "Tipología: No especificado" in text
    assert "Activaciones: 1 activación" in text
    assert "No se presentaron apoyos durante esta sesión." in text
    assert "Tiempo trabajado: 1 min 13 s" in text
    assert "Pausas presentadas: Ninguna" in text
    assert "Hotspots: 2 hotspots presentados, 1 activado" in text
    assert "Hotspots: 0 hotspots presentados, 0 activados" in text
    assert "Apoyos: 0 apoyos presentados, 0 activados" in text
    assert "Cambios de vídeo: 1" in text
    assert "Retrocesos temporales: 1" in text
    assert "Uso de Inicio: 1" in text
    assert "Navegaciones hacia atrás" not in text
    assert "Tipo: participant" not in text
    assert "Estado: active" not in text
    assert "0 pausas" not in text
    assert "porcentaje" not in text.casefold()
    assert "diagnóstico" not in text.casefold()


def test_session_summary_handles_anonymous_zero_values_and_legacy_summary():
    anonymous_text = format_research_summary(
        {
            "started_at": "2026-07-29T18:02:35+00:00",
            "duration_ms": 38000,
            "is_anonymous": True,
            "videos_used": ["video-1"],
            "pauses_presented": 0,
            "hotspots_available": 0,
            "hotspots_activated": 0,
            "supports_available": 1,
            "supports_activated": 0,
            "support_activity": [],
        }
    )

    assert "Participante: Sesión anónima" in anonymous_text
    assert "Duración: 38 s" in anonymous_text
    assert "Vídeos trabajados: 1 vídeo" in anonymous_text
    assert "No se activaron hotspots." in anonymous_text
    assert "No se activaron apoyos." in anonymous_text
    assert "Pausas presentadas: Ninguna" in anonymous_text
    assert "Pausas repetidas: Ninguna" in anonymous_text
    assert "0 pausas" not in anonymous_text

    legacy_text = format_research_summary({"duration_ms": 60000, "user_name": "PX-01"})
    assert "Participante: PX-01" in legacy_text
    assert "Duración: 1 min" in legacy_text
    assert "Tipo: participant" not in legacy_text


def test_duration_formatting_plural_edges():
    assert format_duration(0) == "0 s"
    assert format_duration(60_000) == "1 min"
    assert format_duration(86_000) == "1 min 26 s"
    assert format_duration(4_328_000) == "1 h 12 min 8 s"


def test_summary_json_is_preserved_and_support_audio_tts_counts_are_available(tmp_path):
    manager = ResearchSessionManager(tmp_path / "sessions")
    session = manager.start_session(project_id="demo", project_name="Proyecto", video_id="video-1", video_name="Vídeo 1", user_id="1", user_name="Ana")
    manager.present_pause(
        pause_event_id="pause-1",
        video_id="video-1",
        video_name="Vídeo 1",
        scheduled_time_ms=1000,
        activated_position_ms=1000,
        hotspots_present=[],
        supports_present=[{"support_id": "support-1", "text": "Ayuda", "visible": True}],
    )
    manager.record_support_activation("support-1", support_text="Ayuda", typology="unspecified", audio_played=True, tts_played=False, support_type="audio")
    summary = manager.finish_session(video_id="video-1", video_name="Vídeo 1", video_position_ms=1000)
    summary_path = tmp_path / "sessions" / session.session_id / "summary.json"

    assert summary_path.exists()
    loaded = json.loads(summary_path.read_text(encoding="utf-8"))
    assert loaded["support_activity"][0]["audio_played_count"] == 1
    text = format_research_summary(summary)
    assert "Uso: audio 1 vez" in text


def test_same_text_activated_items_are_disambiguated_by_pause_without_internal_ids():
    text = format_research_summary(
        {
            "started_at": "2026-07-29T18:02:35+00:00",
            "duration_ms": 120000,
            "user_name": "Ana",
            "videos_used": ["video-1"],
            "hotspots_available": 2,
            "hotspots_activated": 3,
            "distinct_hotspots_activated": 2,
            "supports_available": 2,
            "supports_activated": 2,
            "distinct_supports_activated": 2,
            "hotspot_activity": [
                {
                    "video_name": "Vídeo 1",
                    "hotspot_id": "hotspot-a",
                    "text": "más",
                    "typology": "request",
                    "count": 2,
                    "scheduled_time_ms": 1000,
                },
                {
                    "video_name": "Vídeo 1",
                    "hotspot_id": "hotspot-b",
                    "text": "más",
                    "typology": "request",
                    "count": 1,
                    "scheduled_time_ms": 2500,
                },
            ],
            "support_activity": [
                {
                    "video_name": "Vídeo 1",
                    "support_id": "support-a",
                    "text": "ayuda",
                    "count": 1,
                    "scheduled_time_ms": 1000,
                },
                {
                    "video_name": "Vídeo 1",
                    "support_id": "support-b",
                    "text": "ayuda",
                    "count": 1,
                    "scheduled_time_ms": 2500,
                },
            ],
        }
    )

    assert "Hotspots activados: 2 hotspots" in text
    assert "Activaciones de hotspots: 3 activaciones" in text
    assert "Apoyos activados: 2 apoyos" in text
    assert "Activaciones de apoyos: 2 activaciones" in text
    assert "Vídeo 1: más (pausa 1 s)" in text
    assert "Vídeo 1: más (pausa 2 s)" in text
    assert "Vídeo 1: ayuda (pausa 1 s)" in text
    assert "Vídeo 1: ayuda (pausa 2 s)" in text
    assert "hotspot-a" not in text
    assert "support-a" not in text
