"""Communication and Ethernet configuration."""

from __future__ import annotations

import ipaddress

from .base import Subsystem
from ..util import bool_token, ensure_range


class CommunicationsSubsystem(Subsystem):
    @property
    def serial_message_timeout_ms(self) -> int:
        return self._query_int("SYST:COMM:TIME?")

    @serial_message_timeout_ms.setter
    def serial_message_timeout_ms(self, value: int) -> None:
        value = int(ensure_range(value, 5, 65535, "serial message timeout ms"))
        self._write(f"SYST:COMM:TIME {value}")

    @property
    def modbus_enabled(self) -> bool:
        token = self._query("SYST:COMM:PROT:MODB?").strip().upper()
        return token in {"1", "ON", "ENABLE", "ENABLED"}

    @modbus_enabled.setter
    def modbus_enabled(self, enabled: bool) -> None:
        self._write(f"SYST:COMM:PROT:MODB {'ENABLE' if enabled else 'DISABLE'}")

    def set_modbus_enabled(self, enabled: bool) -> None:
        self.modbus_enabled = enabled

    @property
    def interface_code(self) -> int:
        return self._query_int("SYST:COMM:INT:CODE?")

    @property
    def interface_type(self) -> str:
        return self._query("SYST:COMM:INT:TYPE?").strip().strip('"')

    @property
    def interface_serial(self) -> str:
        return self._query("SYST:COMM:INT:SER?").strip().strip('"')

    @property
    def interface_baud_index(self) -> int:
        return self._query_int("SYST:COMM:INT:BAUD?")

    @interface_baud_index.setter
    def interface_baud_index(self, value: int) -> None:
        value = int(ensure_range(value, 0, 9, "interface baud index"))
        self._write(f"SYST:COMM:INT:BAUD {value}")

    def set_interface_address(self, value: int) -> None:
        value = int(ensure_range(value, 1, 127, "Profibus/CANopen node address"))
        self._write(f"SYST:COMM:INT:ADDR {value}")

    @property
    def interface_address(self) -> int:
        return self._query_int("SYST:COMM:INT:ADDR?")

    def _set_tag(self, command: str, value: str, maximum: int, name: str) -> None:
        if len(value) > maximum:
            raise ValueError(f"{name} is limited to {maximum} characters")
        escaped = value.replace('"', "'")
        self._write(f'{command} "{escaped}"')

    def set_function_tag(self, value: str) -> None:
        self._set_tag("SYST:COMM:PROF:FTAG", value, 32, "function tag")

    def set_location_tag(self, value: str) -> None:
        self._set_tag("SYST:COMM:PROF:LTAG", value, 22, "location tag")

    def set_installation_date(self, value: str) -> None:
        self._set_tag("SYST:COMM:PROF:DATE", value, 40, "installation date")

    def set_interface_description(self, value: str) -> None:
        self._set_tag("SYST:COMM:PROF:DESC", value, 54, "interface description")

    def set_station_name(self, value: str) -> None:
        self._set_tag("SYST:COMM:PROF:NAME", value, 200, "station name")

    def configure_can(
        self,
        *,
        node_id: int | None = None,
        broadcast_id: int | None = None,
        extended_id: bool | None = None,
        dlc_always_8: bool | None = None,
        termination: bool | None = None,
    ) -> None:
        if extended_id is not None:
            self._write(f"SYST:COMM:CAN:FORM {'EXT' if extended_id else 'BASE'}")
        max_id = 0x1FFFFFFF if extended_id else 0x7FF
        if node_id is not None:
            value = int(ensure_range(node_id, 0, max_id, "CAN base/node ID"))
            self._write(f"SYST:COMM:CAN:NODE {value}")
        if broadcast_id is not None:
            value = int(ensure_range(broadcast_id, 0, max_id, "CAN broadcast ID"))
            self._write(f"SYST:COMM:CAN:BRO {value}")
        if dlc_always_8 is not None:
            self._write(f"SYST:COMM:CAN:DLC {'FILL' if dlc_always_8 else 'AUTO'}")
        if termination is not None:
            self._write(f"SYST:COMM:CAN:TERM {'ON' if termination else 'OFF'}")

    def set_can_cyclic_read_ms(self, group: str, interval_ms: int) -> None:
        group_token = group.strip().upper().replace("-", "_")
        commands = {
            "ACTUAL": "ACT",
            "LIMITS_UI": "ALIM",
            "LIMITS_PR": "BLIM",
            "SINK_LIMITS": "CLIM",
            "SETPOINTS": "SETS",
            "SINK_SETPOINTS": "BSETS",
            "STATUS": "STAT",
        }
        if group_token not in commands:
            raise ValueError(f"unsupported CAN cyclic-read group {group!r}; choose {', '.join(commands)}")
        value = int(interval_ms)
        if value != 0 and not 20 <= value <= 5000:
            raise ValueError("CAN cyclic-read interval must be 0 or 20..5000 ms")
        self._write(f"SYST:COMM:CAN:READ:{commands[group_token]} {value}")

    def set_can_read_base_id(self, value: int) -> None:
        self._write(f"SYST:COMM:CAN:READ:NODE {int(value)}")

    def set_can_send_base_id(self, value: int) -> None:
        self._write(f"SYST:COMM:CAN:SEND:NODE {int(value)}")

    def select_lan(self, index: int = 2) -> None:
        if index not in {1, 2}:
            raise ValueError("PSB 10000 LAN index must be 1 (slot) or 2 (built-in)")
        self._write(f"SYST:COMM:LAN:IND {index}")

    @property
    def lan_index(self) -> int:
        return self._query_int("SYST:COMM:LAN:IND?")

    @property
    def ip_address(self) -> str:
        return self._query("SYST:COMM:LAN:ADDR?").strip().strip('"')

    @ip_address.setter
    def ip_address(self, value: str) -> None:
        ipaddress.ip_address(value)
        self._write(f"SYST:COMM:LAN:ADDR {value}")

    @property
    def subnet_mask(self) -> str:
        return self._query("SYST:COMM:LAN:SMAS?").strip().strip('"')

    @subnet_mask.setter
    def subnet_mask(self, value: str) -> None:
        ipaddress.ip_address(value)
        self._write(f"SYST:COMM:LAN:SMAS {value}")

    @property
    def gateway(self) -> str:
        return self._query("SYST:COMM:LAN:GAT?").strip().strip('"')

    @gateway.setter
    def gateway(self, value: str) -> None:
        ipaddress.ip_address(value)
        self._write(f"SYST:COMM:LAN:GAT {value}")

    @property
    def tcp_port(self) -> int:
        return self._query_int("SYST:COMM:LAN:CONT?")

    @tcp_port.setter
    def tcp_port(self, value: int) -> None:
        value = int(ensure_range(value, 0, 65535, "TCP port"))
        if value in {502, 537}:
            raise ValueError("Port is reserved by the instrument")
        self._write(f"SYST:COMM:LAN:CONT {value}")

    @property
    def dhcp(self) -> bool:
        return self._query_bool("SYST:COMM:LAN:DHCP?")

    @dhcp.setter
    def dhcp(self, enabled: bool) -> None:
        self._write(f"SYST:COMM:LAN:DHCP {bool_token(enabled)}")

    @property
    def keepalive(self) -> bool:
        return self._query_bool("SYST:COMM:LAN:KEEP?")

    @keepalive.setter
    def keepalive(self, enabled: bool) -> None:
        self._write(f"SYST:COMM:LAN:KEEP {bool_token(enabled)}")

    @property
    def ethernet_timeout_s(self) -> int:
        return self._query_int("SYST:COMM:LAN:TIME?")

    @ethernet_timeout_s.setter
    def ethernet_timeout_s(self, value: int) -> None:
        value = int(value)
        if value != 0 and not 5 <= value <= 65535:
            raise ValueError("Ethernet timeout must be 0 or 5..65535 seconds")
        self._write(f"SYST:COMM:LAN:TIME {value}")

    @property
    def hostname(self) -> str:
        return self._query("SYST:COMM:LAN:HOST?").strip().strip('"')

    @hostname.setter
    def hostname(self, value: str) -> None:
        if not value or len(value) > 54:
            raise ValueError("hostname must contain 1..54 characters")
        self._write(f'SYST:COMM:LAN:HOST "{value}"')

    @property
    def domain(self) -> str:
        return self._query("SYST:COMM:LAN:DOM?").strip().strip('"')

    @domain.setter
    def domain(self, value: str) -> None:
        if len(value) > 54:
            raise ValueError("domain must be at most 54 characters")
        self._write(f'SYST:COMM:LAN:DOM "{value}"')

    @property
    def mac_address(self) -> str:
        return self._query("SYST:COMM:LAN:MAC?").strip().strip('"')

    def set_dns(self, primary: str, secondary: str | None = None) -> None:
        ipaddress.ip_address(primary)
        self._write(f"SYST:COMM:LAN:DNS1 {primary}")
        if secondary is not None:
            ipaddress.ip_address(secondary)
            self._write(f"SYST:COMM:LAN:DNS2 {secondary}")
