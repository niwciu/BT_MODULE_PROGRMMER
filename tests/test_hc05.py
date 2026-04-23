from bt_programmer.modules.hc05 import HC05Module


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.commands = []

    def query(self, command, **_kwargs):
        self.commands.append(command)
        return self.responses[command]


def test_hc05_reads_expected_fields():
    module = HC05Module()
    client = FakeClient(
        {
            "AT+UART?": "+UART:38400,0,0\r\nOK\r\n",
            "AT+INQM?": "+INQM:1,9,48\r\nOK\r\n",
            "AT+NAME?": "+NAME:HC-05\r\nOK\r\n",
            "AT+ROLE?": "+ROLE:0\r\nOK\r\n",
            "AT+PSWD?": "+PSWD:1234\r\nOK\r\n",
            "AT+CMODE?": "+CMODE:1\r\nOK\r\n",
            "AT+BIND?": "+BIND:1234,56,abcdef\r\nOK\r\n",
            "AT+CLASS?": "+CLASS:1f00\r\nOK\r\n",
            "AT+IAC?": "+IAC:9e8b33\r\nOK\r\n",
            "AT+VERSION?": "+VERSION:2.0-20100601\r\nOK\r\n",
            "AT+ADDR?": "+ADDR:1234:56:abcdef\r\nOK\r\n",
        }
    )

    values = module.read_settings(client)

    assert values["name"] == "HC-05"
    assert values["uart_baud"] == "38400"
    assert values["uart_stop_bits"] == "0"
    assert values["uart_parity"] == "0"
    assert values["inqm_mode"] == "1"
    assert values["address"] == "1234:56:abcdef"


def test_hc05_programs_commands_in_expected_order():
    module = HC05Module()
    recorded = []

    class RecorderClient:
        def query(self, command, **_kwargs):
            recorded.append(command)
            return "OK\r\n"

    module.program_settings(
        RecorderClient(),
        {
            "name": "MyHC05",
            "role": "1",
            "password": "1234",
            "uart_baud": "38400",
            "uart_stop_bits": "0",
            "uart_parity": "0",
            "cmode": "1",
            "bind": "1234,56,abcdef",
            "class": "1f00",
            "iac": "9e8b33",
            "inqm_mode": "1",
            "inqm_max_devices": "9",
            "inqm_timeout": "48",
        },
    )

    assert recorded[0] == "AT+NAME=MyHC05"
    assert "AT+INQM=1,9,48" in recorded
    assert recorded[-1] == "AT+PSWD=1234"


def test_hc05_reads_inqm_with_exact_response_reported_by_device():
    module = HC05Module()
    client = FakeClient(
        {
            "AT+UART?": "+UART:38400,0,0\r\nOK\r\n",
            "AT+INQM?": "+INQM:1,1,48\r\nOK\r\n",
            "AT+NAME?": "+NAME:HC-05\r\nOK\r\n",
            "AT+ROLE?": "+ROLE:0\r\nOK\r\n",
            "AT+PSWD?": "+PSWD:1234\r\nOK\r\n",
            "AT+CMODE?": "+CMODE:1\r\nOK\r\n",
            "AT+BIND?": "+BIND:1234,56,abcdef\r\nOK\r\n",
            "AT+CLASS?": "+CLASS:1f00\r\nOK\r\n",
            "AT+IAC?": "+IAC:9e8b33\r\nOK\r\n",
            "AT+VERSION?": "+VERSION:2.0-20100601\r\nOK\r\n",
            "AT+ADDR?": "+ADDR:1234:56:abcdef\r\nOK\r\n",
        }
    )

    values = module.read_settings(client)

    assert values["inqm_mode"] == "1"
    assert values["inqm_max_devices"] == "1"
    assert values["inqm_timeout"] == "48"


def test_hc05_keeps_reading_when_inqm_query_returns_only_ok():
    module = HC05Module()
    client = FakeClient(
        {
            "AT+UART?": "+UART:38400,0,0\r\nOK\r\n",
            "AT+INQM?": "OK\r\n",
            "AT+NAME?": "+NAME:HC-05\r\nOK\r\n",
            "AT+ROLE?": "+ROLE:0\r\nOK\r\n",
            "AT+PSWD?": "+PSWD:1234\r\nOK\r\n",
            "AT+CMODE?": "+CMODE:1\r\nOK\r\n",
            "AT+BIND?": "+BIND:1234,56,abcdef\r\nOK\r\n",
            "AT+CLASS?": "+CLASS:1f00\r\nOK\r\n",
            "AT+IAC?": "+IAC:9e8b33\r\nOK\r\n",
            "AT+VERSION?": "+VERSION:2.0-20100601\r\nOK\r\n",
            "AT+ADDR?": "+ADDR:1234:56:abcdef\r\nOK\r\n",
        }
    )

    values = module.read_settings(client)

    assert values["name"] == "HC-05"
    assert values["uart_baud"] == "38400"
    assert "inqm_mode" not in values
    assert "AT+INQM?" in values["_warning"]


def test_hc05_keeps_reading_when_role_query_returns_only_ok():
    module = HC05Module()
    client = FakeClient(
        {
            "AT+UART?": "+UART:38400,0,0\r\nOK\r\n",
            "AT+INQM?": "OK\r\n",
            "AT+NAME?": "+NAME:HC-05\r\nOK\r\n",
            "AT+ROLE?": "OK\r\n",
            "AT+PSWD?": "+PSWD:1234\r\nOK\r\n",
            "AT+CMODE?": "+CMODE:1\r\nOK\r\n",
            "AT+BIND?": "+BIND:1234,56,abcdef\r\nOK\r\n",
            "AT+CLASS?": "+CLASS:1f00\r\nOK\r\n",
            "AT+IAC?": "+IAC:9e8b33\r\nOK\r\n",
            "AT+VERSION?": "+VERSION:2.0-20100601\r\nOK\r\n",
            "AT+ADDR?": "+ADDR:1234:56:abcdef\r\nOK\r\n",
        }
    )

    values = module.read_settings(client)

    assert values["name"] == "HC-05"
    assert "role" not in values
    assert values["password"] == "1234"
    assert "AT+ROLE?" in values["_warning"]


def test_hc05_reads_password_when_firmware_uses_pin_prefix():
    module = HC05Module()
    client = FakeClient(
        {
            "AT+UART?": "+UART:38400,0,0\r\nOK\r\n",
            "AT+INQM?": "OK\r\n",
            "AT+NAME?": "+NAME:HC-05\r\nOK\r\n",
            "AT+ROLE?": "+ROLE:0\r\nOK\r\n",
            "AT+PSWD?": "+PIN:\"1234\"\r\nOK\r\n",
            "AT+CMODE?": "+CMODE:1\r\nOK\r\n",
            "AT+BIND?": "+BIND:1234,56,abcdef\r\nOK\r\n",
            "AT+CLASS?": "+CLASS:1f00\r\nOK\r\n",
            "AT+IAC?": "+IAC:9e8b33\r\nOK\r\n",
            "AT+VERSION?": "+VERSION:2.0-20100601\r\nOK\r\n",
            "AT+ADDR?": "+ADDR:1234:56:abcdef\r\nOK\r\n",
        }
    )

    values = module.read_settings(client)

    assert values["password"] == "1234"


def test_hc05_reads_version_without_plus_prefix():
    module = HC05Module()
    client = FakeClient(
        {
            "AT+UART?": "+UART:38400,0,0\r\nOK\r\n",
            "AT+INQM?": "OK\r\n",
            "AT+NAME?": "+NAME:HC-05\r\nOK\r\n",
            "AT+ROLE?": "+ROLE:0\r\nOK\r\n",
            "AT+PSWD?": "+PIN:\"1234\"\r\nOK\r\n",
            "AT+CMODE?": "+CMODE:1\r\nOK\r\n",
            "AT+BIND?": "+BIND:0:0:0\r\nOK\r\n",
            "AT+CLASS?": "+CLASS:1f00\r\nOK\r\n",
            "AT+IAC?": "+IAC:9E8B33\r\nOK\r\n",
            "AT+VERSION?": "VERSION:3.0-20170601\r\nOK\r\n",
            "AT+ADDR?": "+ADDR:1234:56:abcdef\r\nOK\r\n",
        }
    )

    values = module.read_settings(client)

    assert values["version"] == "3.0-20170601"
    assert values["bind"] == "0,0,0"


def test_hc05_program_normalizes_bind_with_colons():
    module = HC05Module()
    recorded = []

    class RecorderClient:
        def query(self, command, **_kwargs):
            recorded.append(command)
            return "OK\r\n"

    module.program_settings(
        RecorderClient(),
        {
            "name": "MyHC05",
            "role": "1",
            "password": "1234",
            "uart_baud": "38400",
            "uart_stop_bits": "0",
            "uart_parity": "0",
            "cmode": "1",
            "bind": "0:0:0",
            "class": "1f00",
            "iac": "9e8b33",
            "inqm_mode": "1",
            "inqm_max_devices": "9",
            "inqm_timeout": "48",
        },
    )

    assert "AT+BIND=0,0,0" not in recorded


def test_hc05_program_sends_bind_only_for_cmode_zero_and_real_address():
    module = HC05Module()
    recorded = []

    class RecorderClient:
        def query(self, command, **_kwargs):
            recorded.append(command)
            return "OK\r\n"

    module.program_settings(
        RecorderClient(),
        {
            "name": "MyHC05",
            "role": "1",
            "password": "1234",
            "uart_baud": "38400",
            "uart_stop_bits": "0",
            "uart_parity": "0",
            "cmode": "0",
            "bind": "1234:56:abcdef",
            "class": "1f00",
            "iac": "9e8b33",
            "inqm_mode": "1",
            "inqm_max_devices": "9",
            "inqm_timeout": "48",
        },
    )

    assert "AT+BIND=1234,56,abcdef" in recorded


def test_hc05_program_retries_password_with_quotes_for_newer_firmware():
    module = HC05Module()
    recorded = []

    class RetryClient:
        def query(self, command, **_kwargs):
            recorded.append(command)
            if command == "AT+PSWD=1234":
                from bt_programmer.serial_comm import SerialError

                raise SerialError("Nieoczekiwana odpowiedź modułu: 'ERROR:(1D)\\r\\n'")
            return "OK\r\n"

    module.program_settings(
        RetryClient(),
        {
            "name": "MyHC05",
            "role": "1",
            "password": "1234",
            "uart_baud": "38400",
            "uart_stop_bits": "0",
            "uart_parity": "0",
            "cmode": "1",
            "bind": "0:0:0",
            "class": "1f00",
            "iac": "9e8b33",
            "inqm_mode": "1",
            "inqm_max_devices": "9",
            "inqm_timeout": "48",
        },
    )

    assert "AT+PSWD=1234" in recorded
    assert 'AT+PSWD="1234"' in recorded
