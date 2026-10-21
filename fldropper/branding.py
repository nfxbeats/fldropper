"""Packaged artwork and isolated Windows titlebar/taskbar icon handling."""
import os
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QPixmap

ASSETS = Path(__file__).parent / "assets"
WINDOW_ICON = ASSETS / "FL_Dropper.ico"
APP_IMAGE = ASSETS / "FL_Dropper.png"


def set_windows_app_id() -> None:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        setter = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        setter.argtypes = [wintypes.LPCWSTR]
        setter.restype = ctypes.c_long
        setter("FLDropper.Desktop")


class WindowsIcons:
    """Own only the native icon handles we create, never Qt's icon handles."""
    def __init__(self):
        self.handles = []

    def apply(self, hwnd: int, scale: float = 1.0) -> None:
        if os.name != "nt" or self.handles:
            return
        import ctypes
        from ctypes import wintypes
        user = ctypes.windll.user32
        user.IsWindow.argtypes = [wintypes.HWND]
        user.IsWindow.restype = wintypes.BOOL
        if not user.IsWindow(hwnd):  # Qt offscreen platform has no native HWND.
            return
        user.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                                   ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user.LoadImageW.restype = wintypes.HANDLE
        user.CreateIconFromResourceEx.argtypes = [ctypes.POINTER(wintypes.BYTE), wintypes.DWORD,
            wintypes.BOOL, wintypes.DWORD, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user.CreateIconFromResourceEx.restype = wintypes.HANDLE
        user.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user.SendMessageW.restype = ctypes.c_ssize_t
        small_size = max(16, round(16 * scale))
        small = user.LoadImageW(None, str(WINDOW_ICON), 1, small_size, small_size, 0x10)
        # Windows can create HICON directly from PNG resource bytes. Resize in
        # memory to a conventional 256px icon; the supplied asset stays intact.
        pixmap = QPixmap(str(APP_IMAGE)).scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation)
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buffer, "PNG")
        png = bytes(buffer.data())
        data = (wintypes.BYTE * len(png)).from_buffer_copy(png)
        big = user.CreateIconFromResourceEx(data, len(png), True, 0x00030000, 256, 256, 0)
        for kind, handle in ((0, small), (1, big)):
            if handle:
                user.SendMessageW(hwnd, 0x0080, kind, handle)  # WM_SETICON: small=titlebar, big=taskbar/Alt-Tab.
                self.handles.append(handle)

    def release(self, *_args) -> None:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            destroy = ctypes.windll.user32.DestroyIcon
            destroy.argtypes = [wintypes.HANDLE]
            destroy.restype = wintypes.BOOL
            for handle in self.handles:
                destroy(handle)
            self.handles.clear()
