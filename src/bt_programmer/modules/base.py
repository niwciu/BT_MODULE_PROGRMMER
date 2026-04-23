from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable

from bt_programmer.models import ConnectionResult, PortConfig, SettingField
from bt_programmer.serial_comm import SerialClient, SerialError


class ModuleProtocolError(SerialError):
    """Raised when a module returns an unexpected response."""


ProgressCallback = Callable[[int, int, str], None]


@dataclass(frozen=True)
class ModuleSpec(ABC):
    key: str
    display_name: str
    default_port_config: PortConfig
    probe_baudrates: tuple[int, ...]

    @abstractmethod
    def fields(self) -> tuple[SettingField, ...]:
        raise NotImplementedError

    @abstractmethod
    def probe(self, client: SerialClient) -> str:
        raise NotImplementedError

    @abstractmethod
    def read_settings(
        self,
        client: SerialClient,
        progress_callback: ProgressCallback | None = None,
        selected_keys: set[str] | None = None,
    ) -> dict[str, str]:
        raise NotImplementedError

    @abstractmethod
    def program_settings(
        self,
        client: SerialClient,
        values: dict[str, str],
        progress_callback: ProgressCallback | None = None,
        selected_keys: set[str] | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def read_step_count(self, selected_keys: set[str] | None = None) -> int:
        raise NotImplementedError

    @abstractmethod
    def program_step_count(self, values: dict[str, str], selected_keys: set[str] | None = None) -> int:
        raise NotImplementedError

    def connect_step_count(self, selected_config: PortConfig) -> int:
        return len(self._baud_candidates(selected_config))

    def _baud_candidates(self, selected_config: PortConfig) -> list[int]:
        baud_candidates: list[int] = []
        if selected_config.baudrate not in baud_candidates:
            baud_candidates.append(selected_config.baudrate)
        for baud in self.probe_baudrates:
            if baud not in baud_candidates:
                baud_candidates.append(baud)
        return baud_candidates

    def _report_progress(
        self,
        progress_callback: ProgressCallback | None,
        current: int,
        total: int,
        message: str,
    ) -> None:
        if progress_callback:
            progress_callback(current, total, message)

    def connect_with_probe(
        self,
        port: str,
        selected_config: PortConfig,
        client_factory,
        progress_callback: ProgressCallback | None = None,
    ) -> tuple[SerialClient, ConnectionResult]:
        last_error: Exception | None = None
        attempted_baudrates: list[int] = []
        baud_candidates = self._baud_candidates(selected_config)
        total = len(baud_candidates)

        for index, baud in enumerate(baud_candidates, start=1):
            attempted_baudrates.append(baud)
            self._report_progress(progress_callback, index, total, f"Próba połączenia @ {baud} bps")
            config = PortConfig(
                baudrate=baud,
                bytesize=selected_config.bytesize,
                stopbits=selected_config.stopbits,
                parity=selected_config.parity,
                timeout=selected_config.timeout,
            )
            client = client_factory(port, config)
            try:
                client.open()
                response = self.probe(client)
                result = ConnectionResult(
                    detected_config=config,
                    matched_baud=baud,
                    probe_response=response,
                    notes=[f"Sprawdzono baudrate: {', '.join(str(item) for item in attempted_baudrates)}"],
                )
                return client, result
            except Exception as exc:
                last_error = exc
                client.close()

        details = f"Nie udało się wykryć modułu {self.display_name}. Przetestowane baudrate: {attempted_baudrates}."
        if last_error:
            details = f"{details} Ostatni błąd: {last_error}"
        raise ModuleProtocolError(details)
