from __future__ import annotations

from functools import lru_cache
import re
from typing import Any, Dict, Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from overlay.custom_widgets import OverlayWidget, VerticalLabel
from overlay.helper_func import file_path, zeroed
from overlay.settings import settings

PIXMAP_CACHE = {}


def _default_overlay_rect() -> QtCore.QRect:
    screen = QtGui.QGuiApplication.primaryScreen()
    available = screen.availableGeometry() if screen else QtCore.QRect(
        0, 0, 1920, 1080)
    width = min(700, available.width())
    height = min(400, available.height())
    rect = QtCore.QRect(0, 0, width, height)
    rect.moveTopRight(available.topRight() + QtCore.QPoint(-20, 20))
    return rect


def _legacy_overlay_rect() -> Optional[QtCore.QRect]:
    geometry = settings.overlay_geometry
    if not isinstance(geometry, list) or len(geometry) != 4:
        return None
    try:
        x, y, width, height = (int(value) for value in geometry)
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return QtCore.QRect(x, y, width, height)


def _restore_saved_geometry(widget: QtWidgets.QWidget):
    geometry = settings.overlay_geometry
    if isinstance(geometry, str):
        widget.restoreGeometry(
            QtCore.QByteArray.fromBase64(geometry.encode("ascii")))
        return

    legacy_rect = _legacy_overlay_rect()
    if legacy_rect is not None:
        widget.setGeometry(legacy_rect)


def set_pixmap(civ: str, widget: QtWidgets.QWidget):
    """ Sets civ pixmap to a widget. Handles caching."""
    if civ in PIXMAP_CACHE:
        widget.setPixmap(PIXMAP_CACHE[civ])
        return
    path = file_path(f"img/flags/{civ}.webp")
    pixmap = QtGui.QPixmap(path)
    pixmap = pixmap.scaled(widget.width(), widget.height())
    PIXMAP_CACHE[civ] = pixmap
    widget.setPixmap(pixmap)


def set_country_flag(country_code: str, widget: QtWidgets.QLabel):
    """ Sets country flag to a widget. Handles caching."""
    if not country_code:
        widget.clear()
        return
    if country_code in PIXMAP_CACHE:
        widget.setPixmap(PIXMAP_CACHE[country_code])
        return
    path = file_path(f"img/countries/{country_code}.png")  # PNG format
    pixmap = QtGui.QPixmap(path)
    pixmap = pixmap.scaled(widget.width(), widget.height(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
    PIXMAP_CACHE[country_code] = pixmap
    widget.setPixmap(pixmap)


def _pixmap_cache_key(path: str, size: QtCore.QSize) -> str:
    return f"{path}|{size.width()}x{size.height()}"


def _normalize_country_code(country_code: str) -> str:
    return (country_code or "").strip().lower()


@lru_cache(maxsize=1)
def _country_names_by_code() -> Dict[str, str]:
    country_names: Dict[str, str] = {}
    locales = QtCore.QLocale.matchingLocales(QtCore.QLocale.AnyLanguage,
                                             QtCore.QLocale.AnyScript,
                                             QtCore.QLocale.AnyCountry)
    for locale in locales:
        locale_name = locale.name().split("_")
        if len(locale_name) < 2:
            continue
        country_code = locale_name[-1].lower()
        if len(country_code) != 2:
            continue
        country = locale.country()
        if country == QtCore.QLocale.AnyCountry:
            continue
        country_names.setdefault(country_code,
                                 QtCore.QLocale.countryToString(country))
    return country_names


def set_league_icon(icon_path: str, widget: QtWidgets.QLabel):
    """Sets league pixmap to a widget. Handles caching and smooth scaling."""
    key = _pixmap_cache_key(icon_path, widget.size())
    if key in PIXMAP_CACHE:
        widget.setPixmap(PIXMAP_CACHE[key])
        return
    pixmap = QtGui.QPixmap(icon_path)
    pixmap = pixmap.scaled(widget.width(), widget.height(), QtCore.Qt.KeepAspectRatio,
                           QtCore.Qt.SmoothTransformation)
    PIXMAP_CACHE[key] = pixmap
    widget.setPixmap(pixmap)


def country_name(country_code: str) -> str:
    """Best-effort human-readable label for a 2-letter country code."""
    normalized = _normalize_country_code(country_code)
    if not normalized:
        return ""
    return _country_names_by_code().get(normalized, normalized.upper())


LEAGUE_ELO_RANGES = (
    # (min_inclusive, max_exclusive, league_file_stem)
    (0, 400, "bronze_1"),
    (400, 450, "bronze_2"),
    (450, 500, "bronze_3"),
    (500, 600, "silver_1"),
    (600, 650, "silver_2"),
    (650, 700, "silver_3"),
    (700, 800, "gold_1"),
    (800, 900, "gold_2"),
    (900, 1000, "gold_3"),
    (1000, 1100, "platinum_1"),
    (1100, 1150, "platinum_2"),
    (1150, 1200, "platinum_3"),
    (1200, 1300, "diamond_1"),
    (1300, 1350, "diamond_2"),
    (1350, 1400, "diamond_3"),
    (1400, 1500, "conquerer_1"),
    (1500, 1600, "conquerer_2"),
    (1600, None, "conquerer_3"),
)


def parse_elo(rating_text: str) -> Optional[int]:
    """Best-effort conversion of rating text to an int Elo.

    Returns None when Elo is not available (empty, non-numeric, or <= 0).
    """
    if not rating_text:
        return None
    m = re.search(r"\d+", str(rating_text))
    if not m:
        return None
    try:
        elo = int(m.group(0))
    except ValueError:
        return None
    return elo if elo > 0 else None


def league_icon_path(elo: Optional[int]) -> str:
    """Maps Elo to the appropriate league SVG icon file path."""
    prefix = "solo_"

    if elo is None:
        return file_path(f"img/leagues/{prefix}unranked.svg")

    for min_elo, max_elo, league in LEAGUE_ELO_RANGES:
        if elo < min_elo:
            continue
        if max_elo is None or elo < max_elo:
            return file_path(f"img/leagues/{prefix}{league.replace('conquerer', 'conqueror')}.svg")

    # Fallback, should not be reached
    return file_path(f"img/leagues/{prefix}unranked.svg")


class PlayerWidget:
    """ Player widget shown on the overlay"""

    def __init__(self, row: int, toplayout: QtWidgets.QGridLayout):
        self.hiding_civ_stats: bool = True
        self.team: int = 0
        self.civ: str = ""
        self.visible = True
        self.create_widgets()
        self.name.setStyleSheet("font-weight: bold")
        self.name.setContentsMargins(5, 0, 10, 0)
        self.rating.setStyleSheet("color: #7ab6ff; font-weight: bold")
        self.winrate.setStyleSheet("color: #fffb78")
        self.wins.setStyleSheet("color: #48bd21")
        self.losses.setStyleSheet("color: red")
        for widget in (self.civ_games, self.civ_winrate, self.civ_median_wins):
            widget.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
            widget.setStyleSheet(f"color: {settings.civ_stats_color}")

        offset = 0
        for column, widget in enumerate(
            (self.flag, self.name, self.country, self.rating_container, self.rank, self.winrate,
             self.wins, self.losses, self.civ_games, self.civ_winrate,
             self.civ_median_wins)):

            if widget == self.civ_games:
                offset = 1
            toplayout.addWidget(widget, row, column + offset)

    def create_widgets(self):
        # Separated so this can be changed in a child inner overlay for editing
        self.flag = QtWidgets.QLabel()
        self.flag.setFixedSize(QtCore.QSize(60, 30))
        self.create_country_widget()

        self.name = QtWidgets.QLabel()

        # Rating with league icon
        self.league = QtWidgets.QLabel()
        # Square size so the icon stays readable; scaled with aspect ratio
        self.league.setFixedSize(QtCore.QSize(26, 26))

        self.rating = QtWidgets.QLabel()
        self.rating.setSizePolicy(QtWidgets.QSizePolicy.Fixed,
                                  QtWidgets.QSizePolicy.Preferred)
        self.rating_container = QtWidgets.QWidget()
        self.rating_container.setSizePolicy(QtWidgets.QSizePolicy.Fixed,
                                            QtWidgets.QSizePolicy.Preferred)
        rating_layout = QtWidgets.QHBoxLayout(self.rating_container)
        rating_layout.setContentsMargins(0, 0, 0, 0)
        rating_layout.setSpacing(5)
        rating_layout.addWidget(self.league)
        rating_layout.addWidget(self.rating)

        self.rank = QtWidgets.QLabel()
        self.winrate = QtWidgets.QLabel()
        self.wins = QtWidgets.QLabel()
        self.losses = QtWidgets.QLabel()
        self.civ_games = QtWidgets.QLabel()
        self.civ_winrate = QtWidgets.QLabel()
        self.civ_median_wins = QtWidgets.QLabel()

    def create_country_widget(self):
        self.country_code = ""
        self.country_flag = QtWidgets.QLabel()
        self.country_flag.setFixedSize(QtCore.QSize(25, 14))
        self.country_text = QtWidgets.QLabel()
        self.country_text.setAlignment(QtCore.Qt.AlignLeft
                                       | QtCore.Qt.AlignVCenter)
        self.country = QtWidgets.QWidget()
        self.country.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
                                   QtWidgets.QSizePolicy.Preferred)
        country_layout = QtWidgets.QHBoxLayout(self.country)
        country_layout.setContentsMargins(0, 0, 0, 0)
        country_layout.setSpacing(6)
        country_layout.addWidget(self.country_flag)
        country_layout.addWidget(self.country_text)


    def show(self, show: bool = True):
        self.visible = show
        """ Shows or hides all widgets in this class """
        for widget in (self.flag, self.name, self.country, self.rating_container, self.rank,
                       self.winrate, self.wins, self.losses, self.civ_games,
                       self.civ_winrate, self.civ_median_wins):
            widget.show() if show else widget.hide()

    def update_name_color(self):
        color = settings.team_colors[(self.team - 1) %
                                     len(settings.team_colors)]
        color = tuple(color)
        self.name.setStyleSheet("font-weight: bold; "
                                "background: QLinearGradient("
                                "x1: 0, y1: 0,"
                                "x2: 1, y2: 0,"
                                f"stop: 0 rgba{color},"
                                f"stop: 0.8 rgba{color},"
                                "stop: 1 rgba(0,0,0,0))")

    def update_flag(self, ):
        set_pixmap(self.civ, self.flag)

    def update_country_flag(self, country_code: str):
        self.country_code = _normalize_country_code(country_code)
        set_country_flag(self.country_code, self.country_flag)
        self.country_text.setText(country_name(self.country_code))

    def update_player(self, player_data: Dict[str, Any]):
        # Flag
        self.civ = player_data['civ']
        self.update_flag()

        self.update_country_flag(player_data['country'])
        # Indicate team with background color
        self.team = zeroed(player_data['team'])
        self.update_name_color()

        # Fill the rest
        self.name.setText(player_data['name'])
        self.rating.setText(player_data['rating'])

        # League icon next to Elo
        elo = parse_elo(player_data.get('rating', ''))
        icon_path = league_icon_path(elo)
        set_league_icon(icon_path, self.league)

        self.rank.setText(player_data['rank'])
        self.winrate.setText(player_data['winrate'])
        self.wins.setText(str(player_data['wins']))
        self.losses.setText(player_data['losses'])
        self.civ_games.setText(player_data['civ_games'])
        self.civ_winrate.setText(player_data['civ_winrate'])
        self.civ_median_wins.setText(player_data['civ_win_length_median'])
        self.show(show=bool(player_data['name']))

        # Hide civ specific data when there are none
        if not player_data['civ_games'] and self.hiding_civ_stats:
            for widget in (self.civ_games, self.civ_winrate,
                           self.civ_median_wins):
                widget.hide()

    def get_data(self) -> Dict[str, Any]:
        return {
            'civ': self.civ,
            'name': self.name.text(),
            'team': self.team,
            'country': self.country_code,
            'rating': self.rating.text(),
            'rank': self.rank.text(),
            'wins': self.wins.text(),
            'losses': self.losses.text(),
            'winrate': self.winrate.text(),
            'civ_games': self.civ_games.text(),
            'civ_winrate': self.civ_winrate.text(),
            'civ_win_length_median': self.civ_median_wins.text(),
        }


class AoEOverlay(OverlayWidget):
    """Overlay widget showing AOE4 information """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hiding_civ_stats: bool = True
        self.players = []
        self.setup_as_overlay()
        self.initUI()

    def setup_as_overlay(self):
        self.setGeometry(_default_overlay_rect())
        _restore_saved_geometry(self)

        self.setWindowTitle('AoE IV: Overlay')

    def initUI(self):
        # Layouts & inner frame
        layout = QtWidgets.QVBoxLayout()
        layout.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTop)
        self.setLayout(layout)

        self.inner_frame = QtWidgets.QFrame()
        self.inner_frame.setObjectName("inner_frame")
        layout.addWidget(self.inner_frame)
        self.playerlayout = QtWidgets.QGridLayout()
        self.playerlayout.setContentsMargins(10, 20, 20, 10)
        self.playerlayout.setHorizontalSpacing(10)
        self.playerlayout.setAlignment(QtCore.Qt.AlignRight
                                       | QtCore.Qt.AlignTop)
        self.playerlayout.setColumnStretch(1, 1)
        self.inner_frame.setLayout(self.playerlayout)
        self.update_style(settings.font_size)

        # Map
        self.map = QtWidgets.QLabel()
        self.map.setStyleSheet(
            "font-weight: bold; font-style: italic; color: #f2ea54")
        self.map.setAlignment(QtCore.Qt.AlignCenter)
        self.playerlayout.addWidget(self.map, 0, 0, 1, 2)
        # Header
        country = QtWidgets.QLabel("Country")
        rating = QtWidgets.QLabel("Elo")
        rating.setStyleSheet("color: #7ab6ff; font-weight: bold")
        rank = QtWidgets.QLabel("Rank")
        winrate = QtWidgets.QLabel("Winrate")
        winrate.setStyleSheet("color: #fffb78")
        wins = QtWidgets.QLabel("Wins")
        wins.setStyleSheet("color: #48bd21")
        losses = QtWidgets.QLabel("Losses")
        losses.setStyleSheet("color: red")

        self.civ_games = QtWidgets.QLabel("Games")
        self.civ_winrate = QtWidgets.QLabel("Winrate")
        self.civ_med_wins = QtWidgets.QLabel("Wintime")

        for widget in (self.civ_games, self.civ_winrate, self.civ_med_wins):
            widget.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
            widget.setStyleSheet(f"color: {settings.civ_stats_color}")

        offset = 0
        for column, widget in enumerate(
            (country, rating, rank, winrate, wins, losses, self.civ_games,
             self.civ_winrate, self.civ_med_wins)):
            if widget == self.civ_games:
                offset = 1
                self.civ_stats_label = VerticalLabel(
                    "CIV STATS", QtGui.QColor(settings.civ_stats_color))
                self.playerlayout.addWidget(self.civ_stats_label, 0,
                                            column + 2, 10, 1)

            self.playerlayout.addWidget(widget, 0, column + offset + 2)

        # Add players
        self.init_players()

    def init_players(self):
        for i in range(8):
            self.players.append(PlayerWidget(i + 1, self.playerlayout))

    def update_style(self, font_size: int):
        self.setStyleSheet(
            f"QLabel {{font-size: {font_size}px; color: white }}"
            "QFrame#inner_frame"
            "{"
            "background: QLinearGradient("
            "x1: 0, y1: 0,"
            "x2: 1, y2: 0,"
            "stop: 0 rgba(0,0,0,0),"
            "stop: 0.1 rgba(0,0,0,0.5),"
            "stop: 1 rgba(0,0,0,1))"
            "}")

    def update_data(self, game_data: Dict[str, Any]):
        self.map.setText(game_data['map'])
        for player in self.players:
            player.show(False)

        show_civ_stats = False
        for i, player in enumerate(game_data['players']):
            if i >= len(self.players):
                break

            self.players[i].update_player(player)

            if player['civ_games']:
                show_civ_stats = True

        # Show or hide civilization stats
        for widget in (self.civ_games, self.civ_winrate, self.civ_med_wins,
                       self.civ_stats_label):
            if self.hiding_civ_stats and not show_civ_stats:
                widget.hide()
            else:
                widget.show()

        if settings.open_overlay_on_new_game:
            self.show()

    def save_geometry(self):
        """ Saves overlay geometry into settings"""
        settings.overlay_geometry = bytes(self.saveGeometry().toBase64()).decode(
            "ascii")

    def closeEvent(self, event: QtGui.QCloseEvent):
        self.save_geometry()
        super().closeEvent(event)

    def get_data(self) -> Dict[str, Any]:
        result = {"map": self.map.text(), "players": []}
        for player in self.players:
            if player.visible:
                result["players"].append(player.get_data())
        return result
