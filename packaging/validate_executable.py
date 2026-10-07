from __future__ import annotations

import ctypes
import os
import subprocess
import time
from ctypes import wintypes
from pathlib import Path

import pyautogui


USER32 = ctypes.windll.user32
ENUM_CALLBACK = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
SW_MAXIMIZE = 3


def visible_windows() -> list[tuple[int, str]]:
    windows: list[tuple[int, str]] = []

    def collect(handle: int, _parameter: int) -> bool:
        if USER32.IsWindowVisible(handle):
            length = USER32.GetWindowTextLengthW(handle)
            if length:
                buffer = ctypes.create_unicode_buffer(length + 1)
                USER32.GetWindowTextW(handle, buffer, length + 1)
                windows.append((handle, buffer.value))
        return True

    USER32.EnumWindows(ENUM_CALLBACK(collect), 0)
    return windows


def wait_for_window(predicate, timeout: float = 15.0) -> tuple[int, str]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        for handle, title in visible_windows():
            if predicate(title):
                return handle, title
        time.sleep(0.25)
    raise TimeoutError(f"window not found; visible={visible_windows()!r}")


def focus(handle: int, maximize: bool = False) -> None:
    if maximize:
        USER32.ShowWindow(handle, SW_MAXIMIZE)
    USER32.SetForegroundWindow(handle)
    time.sleep(0.5)


def file_dialog_path(path: Path) -> None:
    handle, _title = wait_for_window(
        lambda title: title in {"Save As", "Guardar como", "Open", "Abrir"}
    )
    focus(handle)
    pyautogui.hotkey("ctrl", "l")
    pyautogui.write(str(path), interval=0.001)
    pyautogui.press("enter")
    time.sleep(1.5)
    pyautogui.press("enter")
    time.sleep(2)


def main() -> int:
    distribution = Path(__file__).resolve().parents[1] / "dist" / "ANNA-1.0.0-Windows"
    executable = distribution / "ANNA.exe"
    demo = distribution / "demo_project" / "washing_hands.json"
    local_root = Path(os.environ["LOCALAPPDATA"]) / "ANNA"
    saved_project = local_root / "results" / "validation_empty.json"

    process = subprocess.Popen([str(executable)])
    try:
        handle, title = wait_for_window(
            lambda value: value.startswith("ANNA — Interactive Video Activities for AAC"),
            timeout=25,
        )
        focus(handle, maximize=True)
        pyautogui.screenshot(r"C:\tmp\anna_exe_blank.png")

        pyautogui.hotkey("ctrl", "s")
        file_dialog_path(saved_project)
        if not saved_project.is_file():
            raise RuntimeError(f"project was not saved: {saved_project}")

        focus(handle)
        pyautogui.hotkey("ctrl", "o")
        file_dialog_path(saved_project)

        focus(handle)
        pyautogui.hotkey("ctrl", "o")
        file_dialog_path(demo)
        time.sleep(5)
        pyautogui.screenshot(r"C:\tmp\anna_exe_demo.png")

        focus(handle)
        pyautogui.hotkey("alt", "h")
        pyautogui.press("enter")
        about_handle, about_title = wait_for_window(
            lambda value: value in {"About ANNA", "Acerca de ANNA"}
        )
        focus(about_handle)
        pyautogui.screenshot(r"C:\tmp\anna_exe_about.png")
        pyautogui.press("enter")

        print(f"window={title}")
        print(f"about={about_title}")
        print(f"saved={saved_project}")
        print(f"demo={demo}")
        return 0
    finally:
        process.terminate()
        process.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
