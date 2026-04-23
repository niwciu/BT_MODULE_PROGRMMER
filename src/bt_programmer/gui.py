from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QCheckBox,
    QProgressDialog,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from bt_programmer.models import ConnectionResult, FieldKind, PortConfig, SettingField
from bt_programmer.modules import AVAILABLE_MODULES
from bt_programmer.modules.base import ModuleSpec
from bt_programmer.serial_comm import SerialClient, list_serial_ports


PARITY_OPTIONS = (
    ("N", "None"),
    ("E", "Even"),
    ("O", "Odd"),
)

STOP_BITS_OPTIONS = (
    (1.0, "1"),
    (1.5, "1.5"),
    (2.0, "2"),
)

BYTE_SIZE_OPTIONS = (
    (8, "8"),
    (7, "7"),
)


class ModuleTab(QWidget):
    @dataclass
    class FieldControls:
        editor: QWidget
        enabled_checkbox: QCheckBox

    def __init__(self, module: ModuleSpec) -> None:
        super().__init__()
        self.module = module
        self.editors: dict[str, QWidget] = {}
        self.controls: dict[str, ModuleTab.FieldControls] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)

        form_group = QGroupBox("Parametry modułu")
        form_layout = QGridLayout(form_group)
        form_layout.addWidget(QLabel("Parametr"), 0, 0)
        form_layout.addWidget(QLabel("Wartość"), 0, 1)
        form_layout.addWidget(QLabel("R/W"), 0, 2, alignment=Qt.AlignmentFlag.AlignCenter)

        for row, field in enumerate(self.module.fields(), start=1):
            editor = self._build_editor(field)
            self.editors[field.key] = editor
            if field.helper_text:
                field_label = QLabel(f"{field.label}\n{field.helper_text}")
            else:
                field_label = QLabel(field.label)
            enabled_checkbox = QCheckBox()
            enabled_checkbox.setChecked(True)
            self.controls[field.key] = ModuleTab.FieldControls(editor, enabled_checkbox)
            form_layout.addWidget(field_label, row, 0)
            form_layout.addWidget(editor, row, 1)
            form_layout.addWidget(enabled_checkbox, row, 2, alignment=Qt.AlignmentFlag.AlignCenter)

        buttons_group = QGroupBox("Operacje")
        buttons_layout = QVBoxLayout(buttons_group)
        self.connect_button = QPushButton("Połącz")
        self.read_button = QPushButton("Odczytaj ustawienia")
        self.program_button = QPushButton("Zaprogramuj")
        self.refresh_defaults_button = QPushButton("Załaduj domyślne portu")
        for button in (
            self.connect_button,
            self.read_button,
            self.program_button,
            self.refresh_defaults_button,
        ):
            button.setMinimumHeight(40)
            buttons_layout.addWidget(button)
        buttons_layout.addStretch(1)

        form_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        buttons_group.setFixedWidth(240)
        layout.addWidget(form_group, stretch=1)
        layout.addWidget(buttons_group)

    def _build_editor(self, field: SettingField) -> QWidget:
        if field.kind == FieldKind.TEXT:
            editor = QLineEdit()
            editor.setPlaceholderText(field.placeholder)
            return editor
        if field.kind == FieldKind.COMBO:
            combo = QComboBox()
            for option in field.options:
                combo.addItem(option.label, option.value)
            return combo
        editor = QLineEdit()
        editor.setReadOnly(True)
        return editor

    def set_values(self, values: dict[str, str]) -> None:
        for key, value in values.items():
            editor = self.editors.get(key)
            if editor is None:
                continue
            if isinstance(editor, QComboBox):
                index = editor.findData(value)
                if index >= 0:
                    editor.setCurrentIndex(index)
                else:
                    editor.addItem(f"{value} (raw)", value)
                    editor.setCurrentIndex(editor.count() - 1)
            elif isinstance(editor, QLineEdit):
                editor.setText(value)

    def get_values(self) -> dict[str, str]:
        values: dict[str, str] = {}
        for field in self.module.fields():
            editor = self.editors[field.key]
            if isinstance(editor, QComboBox):
                values[field.key] = str(editor.currentData())
            elif isinstance(editor, QLineEdit):
                values[field.key] = editor.text().strip()
        return values

    def selected_read_keys(self) -> set[str]:
        return {key for key, control in self.controls.items() if control.enabled_checkbox.isChecked()}

    def selected_write_keys(self) -> set[str]:
        return {
            key
            for key, control in self.controls.items()
            if control.enabled_checkbox.isChecked()
        }


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("BT Module Programmer")
        self.resize(1200, 820)
        self._client: SerialClient | None = None
        self.tabs_by_index: dict[int, ModuleTab] = {}
        self._build_ui()
        self.refresh_ports()
        self.apply_module_defaults()
        self.append_terminal("INFO", f"Uruchomiono GUI z modułu: {Path(__file__).resolve()}")

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setSpacing(12)

        root_layout.addWidget(self._build_port_group())

        self.tab_widget = QTabWidget()
        for module in AVAILABLE_MODULES.values():
            tab = ModuleTab(module)
            index = self.tab_widget.addTab(tab, module.display_name)
            self.tabs_by_index[index] = tab
            tab.connect_button.clicked.connect(self.connect_module)
            tab.read_button.clicked.connect(self.read_settings)
            tab.program_button.clicked.connect(self.program_settings)
            tab.refresh_defaults_button.clicked.connect(self.apply_module_defaults)

        self.tab_widget.currentChanged.connect(self.apply_module_defaults)
        root_layout.addWidget(self.tab_widget, stretch=3)
        root_layout.addWidget(self._build_terminal_group(), stretch=2)

        self.setCentralWidget(root)

    def _build_port_group(self) -> QWidget:
        group = QGroupBox("Port programowania")
        layout = QGridLayout(group)

        self.port_combo = QComboBox()
        self.refresh_ports_button = QPushButton("Odśwież porty")
        self.refresh_ports_button.clicked.connect(self.refresh_ports)
        self.baud_combo = QComboBox()
        for value in (9600, 19200, 38400, 57600, 115200, 128000):
            self.baud_combo.addItem(str(value), value)
        self.bytesize_combo = QComboBox()
        for value, label in BYTE_SIZE_OPTIONS:
            self.bytesize_combo.addItem(label, value)
        self.stopbits_combo = QComboBox()
        for value, label in STOP_BITS_OPTIONS:
            self.stopbits_combo.addItem(label, value)
        self.parity_combo = QComboBox()
        for value, label in PARITY_OPTIONS:
            self.parity_combo.addItem(label, value)
        self.timeout_edit = QLineEdit("1.0")

        layout.addWidget(QLabel("Port"), 0, 0)
        layout.addWidget(self.port_combo, 0, 1)
        layout.addWidget(self.refresh_ports_button, 0, 2)
        layout.addWidget(QLabel("Baud"), 1, 0)
        layout.addWidget(self.baud_combo, 1, 1)
        layout.addWidget(QLabel("Data bits"), 1, 2)
        layout.addWidget(self.bytesize_combo, 1, 3)
        layout.addWidget(QLabel("Stop bits"), 2, 0)
        layout.addWidget(self.stopbits_combo, 2, 1)
        layout.addWidget(QLabel("Parity"), 2, 2)
        layout.addWidget(self.parity_combo, 2, 3)
        layout.addWidget(QLabel("Timeout [s]"), 3, 0)
        layout.addWidget(self.timeout_edit, 3, 1)

        self.connection_status = QLabel("Niepołączono")
        self.connection_status.setStyleSheet("font-weight: 600; color: #9f1239;")
        layout.addWidget(QLabel("Status"), 3, 2)
        layout.addWidget(self.connection_status, 3, 3)
        return group

    def _build_terminal_group(self) -> QWidget:
        group = QGroupBox("Podgląd komunikacji UART")
        layout = QVBoxLayout(group)
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.terminal.setPlaceholderText("Tutaj pojawi się komunikacja TX/RX oraz logi diagnostyczne.")

        controls = QHBoxLayout()
        clear_button = QPushButton("Wyczyść podgląd")
        clear_button.clicked.connect(self.terminal.clear)
        controls.addStretch(1)
        controls.addWidget(clear_button)

        layout.addWidget(self.terminal)
        layout.addLayout(controls)
        return group

    def current_tab(self) -> ModuleTab:
        return self.tabs_by_index[self.tab_widget.currentIndex()]

    def current_module(self) -> ModuleSpec:
        return self.current_tab().module

    def apply_module_defaults(self, *_args) -> None:
        module = self.current_module()
        config = module.default_port_config
        self._set_combo_data(self.baud_combo, config.baudrate)
        self._set_combo_data(self.bytesize_combo, config.bytesize)
        self._set_combo_data(self.stopbits_combo, config.stopbits)
        self._set_combo_data(self.parity_combo, config.parity)
        self.timeout_edit.setText(str(config.timeout))
        self.append_terminal("INFO", f"Załadowano domyślne ustawienia portu dla {module.display_name}.")

    def refresh_ports(self) -> None:
        current = self.port_combo.currentText()
        ports = list_serial_ports()
        self.port_combo.clear()
        self.port_combo.addItems(ports)
        if current:
            index = self.port_combo.findText(current)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)
        if not ports:
            self.append_terminal("WARN", "Nie wykryto żadnych portów szeregowych.")

    def connect_module(self) -> None:
        port = self.port_combo.currentText().strip()
        if not port:
            self.show_error("Najpierw wybierz port szeregowy.")
            return

        module = self.current_module()
        config = self.read_port_config()
        self.append_terminal("INFO", f"Rozpoczynam łączenie z modułem {module.display_name} na porcie {port}.")
        self.disconnect_current_client()
        progress = self._create_progress_dialog(
            "Łączenie z modułem...",
            module.connect_step_count(config),
        )
        try:
            client, result = module.connect_with_probe(
                port=port,
                selected_config=config,
                client_factory=lambda selected_port, selected_config: SerialClient(
                    selected_port,
                    selected_config,
                    log_callback=self.append_terminal,
                ),
                progress_callback=self._make_progress_callback(progress),
            )
        except Exception as exc:
            progress.close()
            self.connection_status.setText("Niepołączono")
            self.connection_status.setStyleSheet("font-weight: 600; color: #9f1239;")
            self.show_error(str(exc))
            return
        progress.setValue(progress.maximum())
        progress.close()

        self._client = client
        self.connection_status.setText(f"Połączono: {module.display_name} @ {result.matched_baud}")
        self.connection_status.setStyleSheet("font-weight: 600; color: #166534;")
        self.apply_detected_config(result)
        self.append_terminal("INFO", f"Połączono z modułem {module.display_name}. Odpowiedź probe: {result.probe_response.strip()}")

    def read_settings(self) -> None:
        client = self.require_client()
        if client is None:
            return
        selected_keys = self.current_tab().selected_read_keys()
        if not selected_keys:
            self.show_error("Zaznacz przynajmniej jedno pole `R`, aby wykonać odczyt.")
            return
        progress = self._create_progress_dialog(
            "Odczyt ustawień modułu...",
            self.current_module().read_step_count(selected_keys),
        )
        try:
            values = self.current_module().read_settings(
                client,
                progress_callback=self._make_progress_callback(progress),
                selected_keys=selected_keys,
            )
        except Exception as exc:
            progress.close()
            self.show_error(f"Nie udało się odczytać ustawień: {exc}")
            return
        progress.setValue(progress.maximum())
        progress.close()
        warning = values.pop("_warning", None)
        self.current_tab().set_values(values)
        self.append_terminal("INFO", "Ustawienia modułu zostały odczytane do formularza.")
        if warning:
            self.append_terminal("WARN", warning)

    def program_settings(self) -> None:
        client = self.require_client()
        if client is None:
            return
        values = self.current_tab().get_values()
        selected_keys = self.current_tab().selected_write_keys()
        if not selected_keys:
            self.show_error("Zaznacz przynajmniej jedno pole `W`, aby wykonać zapis.")
            return
        progress = self._create_progress_dialog(
            "Programowanie modułu...",
            self.current_module().program_step_count(values, selected_keys),
        )
        try:
            self.current_module().program_settings(
                client,
                values,
                progress_callback=self._make_progress_callback(progress),
                selected_keys=selected_keys,
            )
        except Exception as exc:
            progress.close()
            self.show_error(f"Programowanie nie powiodło się: {exc}")
            return
        progress.setValue(progress.maximum())
        progress.close()
        self.append_terminal("INFO", "Programowanie zakończone pomyślnie.")
        QMessageBox.information(self, "Sukces", "Ustawienia modułu zostały zapisane.")

    def require_client(self) -> SerialClient | None:
        if self._client is None:
            self.show_error("Najpierw kliknij 'Połącz'.")
            return None
        return self._client

    def disconnect_current_client(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def closeEvent(self, event) -> None:  # noqa: N802
        self.disconnect_current_client()
        super().closeEvent(event)

    def read_port_config(self) -> PortConfig:
        timeout = float(self.timeout_edit.text().strip() or "1.0")
        return PortConfig(
            baudrate=int(self.baud_combo.currentData()),
            bytesize=int(self.bytesize_combo.currentData()),
            stopbits=float(self.stopbits_combo.currentData()),
            parity=str(self.parity_combo.currentData()),
            timeout=timeout,
        )

    def apply_detected_config(self, result: ConnectionResult) -> None:
        self._set_combo_data(self.baud_combo, result.detected_config.baudrate)
        self._set_combo_data(self.bytesize_combo, result.detected_config.bytesize)
        self._set_combo_data(self.stopbits_combo, result.detected_config.stopbits)
        self._set_combo_data(self.parity_combo, result.detected_config.parity)
        self.timeout_edit.setText(str(result.detected_config.timeout))

    def append_terminal(self, direction: str, message: str) -> None:
        color_map = {
            "TX": QColor("#0f766e"),
            "RX": QColor("#1d4ed8"),
            "INFO": QColor("#374151"),
            "WARN": QColor("#b45309"),
        }
        cursor = self.terminal.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(color_map.get(direction, QColor("#111827")))
        if direction in {"TX", "RX"}:
            fmt.setFontWeight(700)
        cursor.insertText(f"[{direction}] {message}\n", fmt)
        self.terminal.setTextCursor(cursor)
        self.terminal.ensureCursorVisible()

    def _set_combo_data(self, combo: QComboBox, value) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def show_error(self, message: str) -> None:
        self.append_terminal("WARN", message)
        QMessageBox.critical(self, "Błąd", message)

    def _create_progress_dialog(self, title: str, maximum: int) -> QProgressDialog:
        dialog = QProgressDialog(title, None, 0, max(1, maximum), self)
        dialog.setWindowTitle("Postęp operacji")
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.setMinimumWidth(520)
        dialog.setValue(0)
        dialog.show()
        dialog.resize(max(dialog.width(), 560), dialog.height())
        QApplication.processEvents()
        return dialog

    def _make_progress_callback(self, dialog: QProgressDialog):
        def update_progress(current: int, total: int, message: str) -> None:
            dialog.setMaximum(max(1, total))
            dialog.setLabelText(message)
            dialog.setValue(min(current, dialog.maximum()))
            QApplication.processEvents()

        return update_progress


def launch() -> int:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
