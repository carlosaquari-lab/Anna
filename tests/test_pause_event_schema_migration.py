from copy import deepcopy
import sys
import types

qtcore = types.ModuleType('PySide6.QtCore')
qtgui = types.ModuleType('PySide6.QtGui')

class QRectF:
    def __init__(self, *args, **kwargs):
        pass

class _Rect:
    def width(self): return 0
    def height(self): return 0

class QPainterPath:
    def __init__(self, *args, **kwargs): pass
    def addEllipse(self, *args, **kwargs): pass
    def addRect(self, *args, **kwargs): pass
    def intersected(self, other): return self
    def boundingRect(self): return _Rect()
    def isEmpty(self): return True

qtcore.QRectF = QRectF
qtgui.QPainterPath = QPainterPath
pyside = types.ModuleType('PySide6')
sys.modules.setdefault('PySide6', pyside)
sys.modules.setdefault('PySide6.QtCore', qtcore)
sys.modules.setdefault('PySide6.QtGui', qtgui)

from hotspot_model import (
    SCHEMA_VERSION,
    Hotspot,
    PauseEvent,
    PausePoint,
    default_project,
    migrate_project_payload,
    serialize_project,
    videos_from_project_payload,
)


def test_pause_point_is_compatibility_alias_for_pause_event():
    assert PausePoint is PauseEvent


def test_new_serialization_uses_pause_events_and_current_schema():
    event = PauseEvent('event-1', 10_000, [Hotspot('h1')])
    payload = serialize_project(default_project(), [event], duration_ms=20_000)
    assert payload['schema_version'] == SCHEMA_VERSION
    assert payload['pause_events'][0]['event_id'] == 'event-1'
    assert payload['videos'][0]['pause_events'][0]['event_id'] == 'event-1'


def test_legacy_payload_migrates_without_mutating_input():
    legacy = {
        'schema_version': '0.3.0-temporal-hotspot-editor',
        'video': {'source': '../../circular.mp4', 'frame_width': 1536, 'frame_height': 864},
        'pauses': [{'pause_id': 'p1', 'time_ms': 4000, 'hotspots': [], 'supports': []}],
    }
    original = deepcopy(legacy)
    migrated = migrate_project_payload(legacy)
    assert legacy == original
    assert migrated['schema_version'] == SCHEMA_VERSION
    assert migrated['pause_events'][0]['event_id'] == 'p1'
    videos = videos_from_project_payload(legacy)
    assert videos[0].pauses[0].pause_id == 'p1'
