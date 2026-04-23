from bt_programmer.modules.hc05 import HC05Module
from bt_programmer.modules.jdy31 import JDY31Module

AVAILABLE_MODULES = {
    "hc05": HC05Module(),
    "jdy31": JDY31Module(),
}

__all__ = ["AVAILABLE_MODULES", "HC05Module", "JDY31Module"]
