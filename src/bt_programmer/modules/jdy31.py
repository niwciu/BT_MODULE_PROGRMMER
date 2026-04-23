from __future__ import annotations

from dataclasses import dataclass

from bt_programmer.models import ComboOption, FieldKind, PortConfig, SettingField
from bt_programmer.modules.base import ModuleProtocolError, ModuleSpec, ProgressCallback
from bt_programmer.serial_comm import SerialClient


JDY31_BAUD_OPTIONS = (
    ComboOption("4", "9600 bps"),
    ComboOption("5", "19200 bps"),
    ComboOption("6", "38400 bps"),
    ComboOption("7", "57600 bps"),
    ComboOption("8", "115200 bps"),
    ComboOption("9", "128000 bps"),
)

JDY31_ENLOG_OPTIONS = (
    ComboOption("0", "Wyłącz log statusu"),
    ComboOption("1", "Włącz log statusu"),
)


def _parse_equals_value(response: str, prefix: str) -> str:
    normalized = response.replace("\r", "")
    for line in normalized.split("\n"):
        line = line.strip()
        if line.startswith(prefix):
            return line.split(prefix, 1)[1]
    raise ModuleProtocolError(f"Nie udało się sparsować odpowiedzi: {response!r}")


def _validate_pin(value: str) -> None:
    if len(value) != 4 or not value.isdigit():
        raise ValueError("PIN modułu JDY-31 musi mieć dokładnie 4 cyfry.")


@dataclass(frozen=True)
class JDY31Module(ModuleSpec):
    key: str = "jdy31"
    display_name: str = "JDY-31"
    default_port_config: PortConfig = PortConfig(baudrate=9600, bytesize=8, stopbits=1.0, parity="N", timeout=1.0)
    probe_baudrates: tuple[int, ...] = (9600, 19200, 38400, 57600, 115200, 128000)

    def fields(self) -> tuple[SettingField, ...]:
        return (
            SettingField("name", "Name", FieldKind.TEXT, placeholder="JDY-31-SPP"),
            SettingField("pin", "PIN", FieldKind.TEXT, placeholder="1234", validator=_validate_pin),
            SettingField("baud", "UART Baud", FieldKind.COMBO, options=JDY31_BAUD_OPTIONS),
            SettingField("enlog", "Serial Status Log", FieldKind.COMBO, options=JDY31_ENLOG_OPTIONS),
            SettingField("version", "Firmware Version", FieldKind.READONLY, read_only=True),
            SettingField("address", "MAC Address", FieldKind.READONLY, read_only=True),
        )

    def probe(self, client: SerialClient) -> str:
        response = client.query("AT+VERSION", expected_tokens=("+VERSION=",))
        if "+VERSION=" not in response:
            raise ModuleProtocolError(f"JDY-31 nie odpowiedział poprawnie na AT+VERSION: {response!r}")
        return response

    def read_step_count(self, selected_keys: set[str] | None = None) -> int:
        selected = selected_keys or {field.key for field in self.fields()}
        return len({"version", "address", "pin", "baud", "name", "enlog"}.intersection(selected))

    def program_step_count(self, values: dict[str, str], selected_keys: set[str] | None = None) -> int:
        selected = selected_keys or {field.key for field in self.fields() if not field.read_only}
        return len({"pin", "baud", "name", "enlog"}.intersection(selected))

    def read_settings(
        self,
        client: SerialClient,
        progress_callback: ProgressCallback | None = None,
        selected_keys: set[str] | None = None,
    ) -> dict[str, str]:
        step = 0
        selected = selected_keys or {field.key for field in self.fields()}
        total = self.read_step_count(selected)

        def read_value(command: str, prefix: str, key: str) -> str:
            nonlocal step
            step += 1
            self._report_progress(progress_callback, step, total, f"Odczyt {command}")
            return _parse_equals_value(client.query(command, expected_tokens=(prefix,)), prefix).strip()

        values: dict[str, str] = {}
        mapping = (
            ("version", "AT+VERSION", "+VERSION="),
            ("address", "AT+LADDR", "+LADDR="),
            ("pin", "AT+PIN", "+PIN="),
            ("baud", "AT+BAUD", "+BAUD="),
            ("name", "AT+NAME", "+NAME="),
            ("enlog", "AT+ENLOG", "+ENLOG="),
        )
        for key, command, prefix in mapping:
            if key in selected:
                values[key] = read_value(command, prefix, key)
        return values

    def program_settings(
        self,
        client: SerialClient,
        values: dict[str, str],
        progress_callback: ProgressCallback | None = None,
        selected_keys: set[str] | None = None,
    ) -> None:
        selected = selected_keys or {field.key for field in self.fields() if not field.read_only}
        field = next(item for item in self.fields() if item.key == "pin")
        if "pin" in selected and field.validator:
            field.validator(values["pin"])

        step = 0
        total = self.program_step_count(values, selected)
        commands = tuple(
            command
            for key, command in (
                ("pin", f"AT+PIN{values['pin']}"),
                ("baud", f"AT+BAUD{values['baud']}"),
                ("name", f"AT+NAME{values['name']}"),
                ("enlog", f"AT+ENLOG{values['enlog']}"),
            )
            if key in selected
        )
        for command in commands:
            step += 1
            self._report_progress(progress_callback, step, total, f"Zapis {command}")
            client.query(command, expected_tokens=("OK", "+OK"))
