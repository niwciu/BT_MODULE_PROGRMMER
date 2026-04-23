from __future__ import annotations

from collections.abc import Callable
import time

import serial
from serial.tools import list_ports

from bt_programmer.models import PortConfig


class SerialError(RuntimeError):
    """Base serial communication error."""


class SerialTimeoutError(SerialError):
    """Raised when a module does not answer in time."""


LogCallback = Callable[[str, str], None]


class SerialClient:
    def __init__(
        self,
        port: str,
        config: PortConfig,
        log_callback: LogCallback | None = None,
        serial_factory: Callable[..., serial.Serial] | None = None,
    ) -> None:
        self.port = port
        self.config = config
        self.log_callback = log_callback
        self.serial_factory = serial_factory or serial.Serial
        self._serial: serial.Serial | None = None

    def open(self) -> None:
        self.close()
        self._serial = self.serial_factory(
            port=self.port,
            baudrate=self.config.baudrate,
            bytesize=self.config.bytesize,
            parity=self.config.parity,
            stopbits=self.config.stopbits,
            timeout=self.config.timeout,
            write_timeout=self.config.timeout,
        )
        self._log("INFO", f"Otwarto port {self.port} @ {self.config.baudrate} {self.config.bytesize}{self.config.parity}{int(self.config.stopbits)}")
        self.reset_buffers()

    def reset_buffers(self) -> None:
        serial_obj = self._require_open()
        serial_obj.reset_input_buffer()
        serial_obj.reset_output_buffer()

    def close(self) -> None:
        if self._serial is not None:
            try:
                if getattr(self._serial, "is_open", False):
                    self._serial.close()
            finally:
                self._serial = None

    def query(
        self,
        command: str,
        *,
        expected_tokens: tuple[str, ...],
        command_suffix: str = "\r\n",
        settle_delay: float = 0.15,
    ) -> str:
        serial_obj = self._require_open()
        payload = f"{command}{command_suffix}".encode("ascii")
        self._log("TX", command)
        serial_obj.write(payload)
        serial_obj.flush()
        original_timeout = serial_obj.timeout
        serial_obj.timeout = min(self.config.timeout, 0.2)

        chunks: list[bytes] = []
        overall_deadline = time.monotonic() + self.config.timeout
        quiet_deadline: float | None = None
        try:
            while True:
                chunk = serial_obj.read_until(b"\n")
                now = time.monotonic()
                if chunk:
                    chunks.append(chunk)
                    decoded = chunk.decode("ascii", errors="replace").rstrip("\r\n")
                    if decoded:
                        self._log("RX", decoded)
                    quiet_deadline = now + settle_delay
                    continue

                if chunks and quiet_deadline is not None and now >= quiet_deadline:
                    break
                if not chunks and now >= overall_deadline:
                    break
                if chunks and now >= overall_deadline:
                    break
                time.sleep(0.01)
        finally:
            serial_obj.timeout = original_timeout

        joined = b"".join(chunks).decode("ascii", errors="replace")
        if joined:
            if any(token in joined for token in expected_tokens):
                return joined
            raise SerialError(f"Nieoczekiwana odpowiedź modułu: {joined!r}")
        raise SerialTimeoutError(f"Brak odpowiedzi dla komendy {command!r}")

    def _require_open(self):
        if self._serial is None:
            raise SerialError("Port szeregowy nie jest otwarty.")
        return self._serial

    def _log(self, direction: str, message: str) -> None:
        if self.log_callback:
            self.log_callback(direction, message)


def list_serial_ports() -> list[str]:
    ports = [port.device for port in list_ports.comports()]
    return sorted(ports)
