from bt_programmer.modules.jdy31 import JDY31Module


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.commands = []

    def query(self, command, **_kwargs):
        self.commands.append(command)
        return self.responses[command]


def test_jdy31_reads_expected_fields():
    module = JDY31Module()
    client = FakeClient(
        {
            "AT+VERSION": "+VERSION=JDY-31-V1.3,Bluetooth V3.0\r\n",
            "AT+LADDR": "+LADDR=AA:BB:CC:DD:EE:FF\r\n",
            "AT+PIN": "+PIN=1234\r\n",
            "AT+BAUD": "+BAUD=4\r\n",
            "AT+NAME": "+NAME=JDY-31-SPP\r\n",
            "AT+ENLOG": "+ENLOG=1\r\n",
        }
    )

    values = module.read_settings(client)

    assert values["version"].startswith("JDY-31-V1.3")
    assert values["baud"] == "4"
    assert values["name"] == "JDY-31-SPP"


def test_jdy31_programs_commands():
    module = JDY31Module()
    recorded = []

    class RecorderClient:
        def query(self, command, **_kwargs):
            recorded.append(command)
            return "OK\r\n"

    module.program_settings(
        RecorderClient(),
        {
            "pin": "1234",
            "baud": "6",
            "name": "TEST",
            "enlog": "0",
        },
    )

    assert recorded == [
        "AT+PIN1234",
        "AT+BAUD6",
        "AT+NAMETEST",
        "AT+ENLOG0",
    ]
