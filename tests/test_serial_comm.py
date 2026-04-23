from bt_programmer.models import PortConfig
from bt_programmer.serial_comm import SerialClient, SerialTimeoutError


class FakeSerial:
    def __init__(self, *_, **kwargs):
        self.timeout = kwargs.get("timeout")
        self.is_open = True
        self._reads = [b"OK\r\n"]
        self.written = []

    def reset_input_buffer(self):
        return None

    def reset_output_buffer(self):
        return None

    def write(self, payload):
        self.written.append(payload)
        return len(payload)

    def flush(self):
        return None

    def read_until(self, _separator):
        if self._reads:
            return self._reads.pop(0)
        return b""

    def close(self):
        self.is_open = False


def test_serial_client_sends_command_with_crlf():
    client = SerialClient(
        "COM1",
        PortConfig(baudrate=9600),
        serial_factory=FakeSerial,
    )
    client.open()

    response = client.query("AT", expected_tokens=("OK",))

    assert response == "OK\r\n"
    assert client._serial.written == [b"AT\r\n"]


def test_serial_client_raises_timeout_without_response():
    class NoReplySerial(FakeSerial):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._reads = []

    client = SerialClient(
        "COM1",
        PortConfig(baudrate=9600),
        serial_factory=NoReplySerial,
    )
    client.open()

    try:
        client.query("AT", expected_tokens=("OK",))
    except SerialTimeoutError:
        assert True
    else:
        assert False, "Expected SerialTimeoutError"


def test_serial_client_waits_for_delayed_data_before_returning():
    class DelayedSerial(FakeSerial):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._reads = [b"OK\r\n", b"+ROLE:0\r\n", b"OK\r\n"]

    client = SerialClient(
        "COM1",
        PortConfig(baudrate=9600, timeout=0.2),
        serial_factory=DelayedSerial,
    )
    client.open()

    response = client.query("AT+ROLE?", expected_tokens=("+ROLE:", "OK"), settle_delay=0.01)

    assert "+ROLE:0" in response
