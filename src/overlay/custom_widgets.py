from typing import Optional

from PyQt5 import QtCore, QtGui, QtWidgets


class CustomKeySequenceEdit(QtWidgets.QKeySequenceEdit):
    key_changed = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super(CustomKeySequenceEdit, self).__init__(parent)

    def keyPressEvent(self, QKeyEvent):
        super(CustomKeySequenceEdit, self).keyPressEvent(QKeyEvent)
        value = self.keySequence()
        self.setKeySequence(QtGui.QKeySequence(value))
        self.key_changed.emit(value.toString())

    @staticmethod
    def convert_hotkey(hotkey: str) -> str:
        """ Converts hotkey to the format usable by the keyboard module"""
        replace_dict = {
            "Num+": "",
            "scrolllock": 'scroll lock',
            "ScrollLock": 'scroll lock'
        }
        for item, nitem in replace_dict.items():
            hotkey = hotkey.replace(item, nitem)
        return hotkey

    def get_hotkey_string(self) -> str:
        """ Returns the hotkey string usable by the keyboard module"""
        return self.convert_hotkey(self.keySequence().toString())


class VerticalLabel(QtWidgets.QLabel):
    def __init__(self, text: str, color: QtGui.QColor, min_width: int = 20):
        super().__init__()
        self.setMinimumWidth(min_width)
        self.textlabel = text
        self.color = color

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setPen(self.color)
        painter.rotate(-90)
        rect = QtCore.QRect(-self.height(), 0, self.height(), self.width())
        painter.drawText(rect, QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter,
                         self.textlabel)
        painter.end()


class OverlayWidget(QtWidgets.QWidget):
    """Custom overlay widget"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.fixed: bool = True
        self._move_mode_size: Optional[QtCore.QSize] = None
        self._tracked_window: Optional[QtGui.QWindow] = None
        self.set_state(translucent=True)

    def show_hide(self):
        self.hide() if self.isVisible() else self.show()

    def save_geometry(self):
        raise NotImplementedError

    def set_state(self, translucent: bool):
        if translucent:
            self.setWindowFlags(QtCore.Qt.Tool
                                | QtCore.Qt.FramelessWindowHint
                                | QtCore.Qt.WindowTransparentForInput
                                | QtCore.Qt.WindowStaysOnTopHint
                                | QtCore.Qt.NoDropShadowWindowHint
                                | QtCore.Qt.WindowDoesNotAcceptFocus)
            self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        else:
            self.setWindowFlags(QtCore.Qt.Tool
                                | QtCore.Qt.WindowTitleHint
                                | QtCore.Qt.WindowStaysOnTopHint)
            self.setAttribute(QtCore.Qt.WA_TranslucentBackground, False)

    def showEvent(self, event: QtGui.QShowEvent):
        super().showEvent(event)
        self._track_window_handle()

    def _track_window_handle(self):
        window = self.windowHandle()
        if window is self._tracked_window:
            return

        if self._tracked_window is not None:
            try:
                self._tracked_window.screenChanged.disconnect(
                    self._handle_screen_changed)
            except (TypeError, RuntimeError):
                pass

        self._tracked_window = window
        if window is not None:
            window.screenChanged.connect(self._handle_screen_changed)

    def _handle_screen_changed(self, _screen: QtGui.QScreen):
        if not self.fixed and self._move_mode_size is not None:
            QtCore.QTimer.singleShot(0, self._restore_move_mode_size)

    def _restore_move_mode_size(self):
        if self.fixed or self._move_mode_size is None:
            return
        if self.size() != self._move_mode_size:
            self.resize(self._move_mode_size)

    def change_state(self):
        """ Changes the widget to be movable or not"""
        geometry = QtCore.QRect(self.geometry())
        self.show()
        if self.fixed:
            self.fixed = False
            self.set_state(translucent=False)
        else:
            self.fixed = True
            self.set_state(translucent=True)
        self.show()
        self._track_window_handle()
        self.setGeometry(geometry)
        if self.fixed:
            self._move_mode_size = None
            self.save_geometry()
        else:
            self._move_mode_size = QtCore.QSize(geometry.size())
