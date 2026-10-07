from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QVBoxLayout

from hotspot_editor import EditorWindow


def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_segment_is_in_lower_controls_and_absent_from_right_panel() -> None:
    app()
    window = EditorWindow(auto_show=False)
    try:
        assert not window.support_panel.isAncestorOf(window.segment_controls)
        assert window.scroll_area.isAncestorOf(window.segment_controls)
        assert not hasattr(window, "support_panel_scroll")
        assert window.segment_controls.minimumHeight() == 0
        assert window.segment_controls.parentWidget() is window.playback_controls.parentWidget()
    finally:
        window.close()


def test_main_scroll_never_exposes_global_scrollbars() -> None:
    app()
    window = EditorWindow(auto_show=False)
    try:
        assert window.scroll_area.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        assert window.scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    finally:
        window.close()


def test_transport_and_timeline_remain_in_main_layout_outside_right_scroll() -> None:
    app()
    window = EditorWindow(auto_show=False)
    try:
        for widget in (window.home_btn, window.play_btn, window.stop_btn, window.continue_btn, window.timeline):
            assert not window.support_panel.isAncestorOf(widget)
            assert window.scroll_area.isAncestorOf(widget)
    finally:
        window.close()


def test_user_mode_removes_segment_from_right_panel_layout_without_window_resize() -> None:
    app()
    window = EditorWindow(auto_show=False)
    try:
        window.resize(1180, 720)
        original_size = window.size()
        window.preview_btn.setChecked(True)
        window.toggle_preview_mode()
        assert window.segment_controls.isHidden()
        assert window.size() == original_size
        window.preview_btn.setChecked(False)
        window.toggle_preview_mode()
        assert not window.segment_controls.isHidden()
        assert window.size() == original_size
    finally:
        window.close()


def test_compact_segment_uses_its_own_vertical_box() -> None:
    app()
    window = EditorWindow(auto_show=False)
    try:
        layout = window.segment_controls.layout()
        assert window.segment_controls.isAncestorOf(window.segment_start_value)
        assert window.segment_controls.isAncestorOf(window.segment_end_value)
        assert window.segment_controls.isAncestorOf(window.save_segment_btn)
        assert window.segment_controls.isAncestorOf(window.reset_segment_btn)
        assert not window.segment_start_value.isReadOnly()
        assert not window.segment_end_value.isReadOnly()
        assert isinstance(layout, QVBoxLayout)
        assert window.segment_start_value.maximumHeight() <= 28
        assert window.save_segment_btn.maximumHeight() <= 26
        assert window.reset_segment_btn.maximumHeight() <= 26
    finally:
        window.close()


def test_reference_window_size_keeps_all_lower_controls_visible_and_uncut() -> None:
    application = app()
    window = EditorWindow(auto_show=False)
    try:
        window.duration_ms = 213_000
        window.load_segment_draft()
        window.update_segment_controls()
        window.resize(1680, 945)
        window.show()
        application.processEvents()
        assert window.segment_controls.geometry().left() >= window.playback_controls.geometry().right()

        controls = (
            window.home_btn, window.play_btn, window.stop_btn, window.continue_btn,
            window.segment_start_value, window.segment_end_value,
            window.save_segment_btn, window.reset_segment_btn, window.timeline,
        )
        assert all(widget.isVisible() and widget.width() > 0 and widget.height() > 0 for widget in controls)
        controls_panel = window.segment_controls.parentWidget()
        assert controls_panel.rect().contains(window.segment_controls.geometry())
        assert controls_panel.rect().contains(window.timeline.geometry())
        for widget in (
            window.segment_start_value, window.segment_end_value,
            window.save_segment_btn, window.reset_segment_btn,
        ):
            assert window.segment_controls.rect().contains(widget.geometry())
        for field in (window.segment_start_value, window.segment_end_value):
            assert field.fontMetrics().horizontalAdvance(field.text()) < field.contentsRect().width()
        for button in (window.save_segment_btn, window.reset_segment_btn):
            assert button.fontMetrics().horizontalAdvance(button.text()) + 12 <= button.width()
        assert window.support_panel.isVisible()
        assert not window.scroll_area.verticalScrollBar().isVisible()
        assert not window.scroll_area.horizontalScrollBar().isVisible()
    finally:
        window.close()
