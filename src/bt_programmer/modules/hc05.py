from __future__ import annotations

from dataclasses import dataclass

from bt_programmer.models import ComboOption, FieldKind, PortConfig, SettingField
from bt_programmer.modules.base import ModuleProtocolError, ModuleSpec, ProgressCallback
from bt_programmer.serial_comm import SerialClient, SerialError


ROLE_OPTIONS = (
    ComboOption("0", "Slave"),
    ComboOption("1", "Master"),
    ComboOption("2", "Loopback"),
)

CMODE_OPTIONS = (
    ComboOption("0", "Połącz tylko z adresem BIND"),
    ComboOption("1", "Połącz z dowolnym adresem"),
    ComboOption("2", "Slave-loop"),
)

UART_BAUD_OPTIONS = tuple(
    ComboOption(str(value), f"{value} bps")
    for value in (1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600, 1382400)
)

STOP_BITS_OPTIONS = (
    ComboOption("0", "1 bit stopu"),
    ComboOption("1", "2 bity stopu"),
)

PARITY_OPTIONS = (
    ComboOption("0", "Brak"),
    ComboOption("1", "Nieparzystość"),
    ComboOption("2", "Parzystość"),
)

INQM_MODE_OPTIONS = (
    ComboOption("0", "Standard"),
    ComboOption("1", "RSSI"),
)

IAC_OPTIONS = (
    ComboOption("9e8b33", "GIAC 0x9E8B33"),
    ComboOption("9e8b00", "LIAC 0x9E8B00"),
)


def _validate_password(value: str) -> None:
    if len(value) != 4 or not value.isdigit():
        raise ValueError("PIN/PSWD modułu HC-05 musi mieć dokładnie 4 cyfry.")


def _validate_hex24(value: str) -> None:
    normalized = value.replace("0x", "").lower()
    if len(normalized) != 6 or any(char not in "0123456789abcdef" for char in normalized):
        raise ValueError("Wartość musi być 24-bitowym zapisem hex, np. 9e8b33.")


def _validate_bind(value: str) -> None:
    parts = _normalize_bind(value).split(",")
    if len(parts) != 3 or not all(parts):
        raise ValueError("Adres musi mieć format NAP,UAP,LAP, np. 1234,56,abcdef.")
    if not all(all(ch in "0123456789abcdefABCDEF" for ch in part) for part in parts):
        raise ValueError("Adres BIND/PAIR może zawierać tylko cyfry hex.")


def _normalize_bind(value: str) -> str:
    normalized = value.strip().replace(":", ",")
    parts = [part.strip() for part in normalized.split(",")]
    if len(parts) != 3 or not all(parts):
        raise ValueError("Adres musi mieć format NAP,UAP,LAP, np. 1234,56,abcdef.")
    return ",".join(parts)


def _parse_prefixed_value(response: str, prefix: str) -> str:
    normalized = response.replace("\r", "").strip()
    compact_prefix = prefix.strip()
    for line in normalized.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.upper() == "OK":
            continue
        if line.startswith(compact_prefix):
            return line[len(compact_prefix) :]
    raise ModuleProtocolError(f"Nie udało się sparsować odpowiedzi: {response!r}")


def _parse_first_matching_prefix(response: str, prefixes: tuple[str, ...]) -> str:
    for prefix in prefixes:
        try:
            return _parse_prefixed_value(response, prefix).strip()
        except ModuleProtocolError:
            continue
    raise ModuleProtocolError(f"Nie udało się sparsować odpowiedzi: {response!r}")


def _read_optional_prefixed_value(client: SerialClient, command: str, prefixes: str | tuple[str, ...]) -> str | None:
    if isinstance(prefixes, str):
        prefixes = (prefixes,)
    response = client.query(command, expected_tokens=(*prefixes, "OK"))
    try:
        return _parse_first_matching_prefix(response, prefixes)
    except ModuleProtocolError:
        normalized = response.replace("\r", "").strip().upper()
        if normalized == "OK":
            return None
        raise


def _set_if_present(values: dict[str, str], key: str, value: str | None) -> None:
    if value is not None and value != "":
        values[key] = value


def _is_zero_bind(value: str) -> bool:
    normalized = _normalize_bind(value)
    return all(part == "0" for part in normalized.split(","))


def _run_command_variants(client: SerialClient, commands: tuple[str, ...]) -> None:
    last_error: Exception | None = None
    for command in commands:
        try:
            client.query(command, expected_tokens=("OK",))
            return
        except SerialError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error


@dataclass(frozen=True)
class HC05Module(ModuleSpec):
    key: str = "hc05"
    display_name: str = "HC-05"
    default_port_config: PortConfig = PortConfig(baudrate=38400, bytesize=8, stopbits=1.0, parity="N", timeout=1.0)
    probe_baudrates: tuple[int, ...] = (38400, 9600, 19200, 57600, 115200)

    def fields(self) -> tuple[SettingField, ...]:
        return (
            SettingField("name", "Name", FieldKind.TEXT, placeholder="HC-05"),
            SettingField("role", "Role", FieldKind.COMBO, options=ROLE_OPTIONS),
            SettingField("password", "PIN / PSWD", FieldKind.TEXT, placeholder="1234", validator=_validate_password),
            SettingField("uart_baud", "UART Baud", FieldKind.COMBO, options=UART_BAUD_OPTIONS),
            SettingField("uart_stop_bits", "UART Stop Bits", FieldKind.COMBO, options=STOP_BITS_OPTIONS),
            SettingField("uart_parity", "UART Parity", FieldKind.COMBO, options=PARITY_OPTIONS),
            SettingField("cmode", "Connection Mode", FieldKind.COMBO, options=CMODE_OPTIONS),
            SettingField("bind", "Bind Address", FieldKind.TEXT, placeholder="1234,56,abcdef", validator=_validate_bind),
            SettingField("class", "Class", FieldKind.TEXT, placeholder="1f00", helper_text="Hex class value"),
            SettingField("iac", "Inquiry Access Code", FieldKind.COMBO, options=IAC_OPTIONS),
            SettingField("inqm_mode", "Inquiry Mode", FieldKind.COMBO, options=INQM_MODE_OPTIONS),
            SettingField("inqm_max_devices", "Inquiry Max Devices", FieldKind.TEXT, placeholder="9"),
            SettingField("inqm_timeout", "Inquiry Timeout", FieldKind.TEXT, placeholder="48"),
            SettingField("version", "Firmware Version", FieldKind.READONLY, read_only=True),
            SettingField("address", "Bluetooth Address", FieldKind.READONLY, read_only=True),
        )

    def probe(self, client: SerialClient) -> str:
        response = client.query("AT", expected_tokens=("OK",))
        if "OK" not in response:
            raise ModuleProtocolError(f"HC-05 nie odpowiedział poprawnie na komendę testową: {response!r}")
        return response

    def read_step_count(self, selected_keys: set[str] | None = None) -> int:
        selected = selected_keys or {field.key for field in self.fields()}
        count = 0
        single_keys = {"name", "role", "password", "cmode", "bind", "class", "iac", "version", "address"}
        count += len(single_keys.intersection(selected))
        if {"uart_baud", "uart_stop_bits", "uart_parity"}.intersection(selected):
            count += 1
        if {"inqm_mode", "inqm_max_devices", "inqm_timeout"}.intersection(selected):
            count += 1
        return count

    def program_step_count(self, values: dict[str, str], selected_keys: set[str] | None = None) -> int:
        selected = selected_keys or {field.key for field in self.fields() if not field.read_only}
        count = 0
        for key in ("name", "role", "cmode", "class", "iac"):
            if key in selected:
                count += 1
        if {"uart_baud", "uart_stop_bits", "uart_parity"}.intersection(selected):
            count += 1
        if {"inqm_mode", "inqm_max_devices", "inqm_timeout"}.intersection(selected):
            count += 1
        if "bind" in selected and values["cmode"] == "0" and not _is_zero_bind(values["bind"]):
            count += 1
        if "password" in selected:
            count += 1
        return count

    def read_settings(
        self,
        client: SerialClient,
        progress_callback: ProgressCallback | None = None,
        selected_keys: set[str] | None = None,
    ) -> dict[str, str]:
        values: dict[str, str] = {}
        warnings: list[str] = []
        selected = selected_keys or {field.key for field in self.fields()}
        step = 0
        total = self.read_step_count(selected)

        single_value_fields = (
            ("name", "AT+NAME?", "+NAME:", lambda value: value),
            ("role", "AT+ROLE?", "+ROLE:", lambda value: value),
            ("password", "AT+PSWD?", ("+PSWD:", "+PIN:"), lambda value: value.strip('"')),
            ("cmode", "AT+CMODE?", "+CMODE:", lambda value: value),
            ("bind", "AT+BIND?", "+BIND:", _normalize_bind),
            ("class", "AT+CLASS?", "+CLASS:", lambda value: value),
            ("iac", "AT+IAC?", "+IAC:", lambda value: value.lower()),
            ("version", "AT+VERSION?", ("+VERSION:", "VERSION:"), lambda value: value),
            ("address", "AT+ADDR?", "+ADDR:", lambda value: value),
        )

        for key, command, prefix, transform in single_value_fields:
            if key not in selected:
                continue
            step += 1
            self._report_progress(progress_callback, step, total, f"Odczyt {command}")
            value = _read_optional_prefixed_value(client, command, prefix)
            if value is None:
                warnings.append(f"Firmware HC-05 nie zwraca danych dla {command}.")
                continue
            _set_if_present(values, key, transform(value))

        if {"uart_baud", "uart_stop_bits", "uart_parity"}.intersection(selected):
            step += 1
            self._report_progress(progress_callback, step, total, "Odczyt AT+UART?")
            uart = _read_optional_prefixed_value(client, "AT+UART?", "+UART:")
            if uart:
                uart_parts = [part.strip() for part in uart.split(",")]
                if len(uart_parts) == 3:
                    if "uart_baud" in selected:
                        values["uart_baud"] = uart_parts[0]
                    if "uart_stop_bits" in selected:
                        values["uart_stop_bits"] = uart_parts[1]
                    if "uart_parity" in selected:
                        values["uart_parity"] = uart_parts[2]
                else:
                    warnings.append(f"Nieoczekiwany format odpowiedzi AT+UART?: {uart}")
            else:
                warnings.append("Firmware HC-05 nie zwraca danych dla AT+UART?.")

        if {"inqm_mode", "inqm_max_devices", "inqm_timeout"}.intersection(selected):
            step += 1
            self._report_progress(progress_callback, step, total, "Odczyt AT+INQM?")
            inqm = _read_optional_prefixed_value(client, "AT+INQM?", "+INQM:")
            if inqm:
                inqm_parts = [part.strip() for part in inqm.split(",")]
                if len(inqm_parts) == 3:
                    if "inqm_mode" in selected:
                        values["inqm_mode"] = inqm_parts[0]
                    if "inqm_max_devices" in selected:
                        values["inqm_max_devices"] = inqm_parts[1]
                    if "inqm_timeout" in selected:
                        values["inqm_timeout"] = inqm_parts[2]
                else:
                    warnings.append(f"Nieoczekiwany format odpowiedzi AT+INQM?: {inqm}")
            else:
                warnings.append("Firmware HC-05 nie zwraca danych dla AT+INQM?.")

        if warnings:
            values["_warning"] = " ".join(warnings)
        return values

    def program_settings(
        self,
        client: SerialClient,
        values: dict[str, str],
        progress_callback: ProgressCallback | None = None,
        selected_keys: set[str] | None = None,
    ) -> None:
        selected = selected_keys or {field.key for field in self.fields() if not field.read_only}
        for validator_key in ("password", "bind"):
            if validator_key not in selected:
                continue
            field = next(item for item in self.fields() if item.key == validator_key)
            if field.validator:
                field.validator(values[validator_key])
        if "iac" in selected:
            _validate_hex24(values["iac"])
        bind_value = _normalize_bind(values["bind"]) if "bind" in selected else "0,0,0"
        step = 0
        total = self.program_step_count(values, selected)

        commands = [
            *( [f"AT+NAME={values['name']}"] if "name" in selected else [] ),
            *( [f"AT+ROLE={values['role']}"] if "role" in selected else [] ),
            *( [f"AT+UART={values['uart_baud']},{values['uart_stop_bits']},{values['uart_parity']}"] if {"uart_baud", "uart_stop_bits", "uart_parity"}.intersection(selected) else [] ),
            *( [f"AT+CMODE={values['cmode']}"] if "cmode" in selected else [] ),
            *( [f"AT+CLASS={values['class']}"] if "class" in selected else [] ),
            *( [f"AT+IAC={values['iac']}"] if "iac" in selected else [] ),
            *( [f"AT+INQM={values['inqm_mode']},{values['inqm_max_devices']},{values['inqm_timeout']}"] if {"inqm_mode", "inqm_max_devices", "inqm_timeout"}.intersection(selected) else [] ),
        ]
        if "bind" in selected and values["cmode"] == "0" and not _is_zero_bind(bind_value):
            commands.append(f"AT+BIND={bind_value}")
        for command in commands:
            step += 1
            self._report_progress(progress_callback, step, total, f"Zapis {command}")
            client.query(command, expected_tokens=("OK",))
        if "password" in selected:
            step += 1
            self._report_progress(progress_callback, step, total, "Zapis PIN/PSWD")
            _run_command_variants(
                client,
                (
                    f"AT+PSWD={values['password']}",
                    f'AT+PSWD="{values["password"]}"',
                ),
            )
