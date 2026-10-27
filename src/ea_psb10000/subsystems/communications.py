# Writer: Jeff Michaelis
# Project: EA-PSB 10000 Python Driver
# Python compatibility: Python 3.8+
# Purpose: Built-in LAN, protocol, optional-interface, Profibus/Profinet, and CAN configuration.

"""Communication and Ethernet configuration."""

from __future__ import annotations

import ipaddress
from typing import Optional

from .base import Subsystem
from ..util import bool_token, ensure_range


class CommunicationsSubsystem(Subsystem):
    """SCPI communication/interface configuration.

    Long-form SCPI headers are intentionally used here. EA documents both long
    and short SCPI forms, but using the documented long spelling avoids parser
    ambiguity across firmware revisions and makes diagnostics easier to read.
    """

    @property
    def serial_message_timeout_ms(self) -> int:
        # Documented keyword is TIMeout.  The previous driver used :TIME,
        # which is neither the documented short form (:TIM) nor the long form.
        """Read and return the current serial/USB inter-byte message timeout from the
        instrument or driver state.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:TIMeout?``."""

        return self._query_int("SYSTem:COMMunicate:TIMeout?")

    @serial_message_timeout_ms.setter
    def serial_message_timeout_ms(self, value: int) -> None:
        """Validate and write the serial/USB inter-byte message timeout to the instrument.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:TIMeout {value}``,
        ``SYSTem:COMMunicate:TIMeout``."""

        value = int(ensure_range(value, 5, 65535, "serial message timeout ms"))
        self._write(f"SYSTem:COMMunicate:TIMeout {value}")

    @property
    def modbus_enabled(self) -> bool:
        """Read and return the current ModBus protocol enabled state from the instrument or
        driver state.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:PROTocol:MODBus?``."""

        token = self._query("SYSTem:COMMunicate:PROTocol:MODBus?").strip().upper()
        return token in {"1", "ON", "ENABLE", "ENABLED"}

    @modbus_enabled.setter
    def modbus_enabled(self, enabled: bool) -> None:
        """Validate and write the ModBus protocol enabled state to the instrument.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:PROTocol:MODBus {value}``,
        ``SYSTem:COMMunicate:PROTocol:MODBus``."""

        self._write(
            f"SYSTem:COMMunicate:PROTocol:MODBus "
            f"{'ENABle' if enabled else 'DISable'}"
        )

    def set_modbus_enabled(self, enabled: bool) -> None:
        """Validate and write modbus enabled."""

        self.modbus_enabled = enabled

    @property
    def interface_code(self) -> int:
        """Read and return the current optional-interface code from the instrument or driver
        state.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:INTerface:CODe?``."""

        return self._query_int("SYSTem:COMMunicate:INTerface:CODe?")

    @property
    def interface_type(self) -> str:
        """Read and return the current optional-interface type from the instrument or driver
        state.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:INTerface:TYPe?``."""

        return self._query("SYSTem:COMMunicate:INTerface:TYPe?").strip().strip('"')

    @property
    def interface_serial(self) -> str:
        """Read and return the current optional-interface serial number from the instrument or
        driver state.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:INTerface:SERial?``."""

        return self._query("SYSTem:COMMunicate:INTerface:SERial?").strip().strip('"')

    @property
    def interface_baud_index(self) -> int:
        """Read and return the current optional-interface baud index from the instrument or
        driver state.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:INTerface:BAUD?``."""

        return self._query_int("SYSTem:COMMunicate:INTerface:BAUD?")

    @interface_baud_index.setter
    def interface_baud_index(self, value: int) -> None:
        """Validate and write the optional-interface baud index to the instrument.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:INTerface:BAUD {value}``,
        ``SYSTem:COMMunicate:INTerface:BAUD``."""

        value = int(ensure_range(value, 0, 9, "interface baud index"))
        self._write(f"SYSTem:COMMunicate:INTerface:BAUD {value}")

    def set_interface_address(self, value: int) -> None:
        """Validate and write interface address.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:INTerface:ADDRess {value}``,
        ``SYSTem:COMMunicate:INTerface:ADDRess``."""

        value = int(ensure_range(value, 1, 127, "Profibus/CANopen node address"))
        self._write(f"SYSTem:COMMunicate:INTerface:ADDRess {value}")

    @property
    def interface_address(self) -> int:
        """Read and return the current optional-interface node address from the instrument or
        driver state.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:INTerface:ADDRess?``."""

        return self._query_int("SYSTem:COMMunicate:INTerface:ADDRess?")

    def _set_tag(self, command: str, value: str, maximum: int, name: str) -> None:
        if len(value) > maximum:
            raise ValueError(f"{name} is limited to {maximum} characters")
        escaped = value.replace('"', "'")
        self._write(f'{command} "{escaped}"')

    def set_function_tag(self, value: str) -> None:
        """Validate and write function tag.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:PROFibus:FTAG``."""

        self._set_tag("SYSTem:COMMunicate:PROFibus:FTAG", value, 32, "function tag")

    def set_location_tag(self, value: str) -> None:
        """Validate and write location tag.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:PROFibus:LTAG``."""

        self._set_tag("SYSTem:COMMunicate:PROFibus:LTAG", value, 22, "location tag")

    def set_installation_date(self, value: str) -> None:
        """Validate and write installation date.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:PROFibus:DATe``."""

        self._set_tag("SYSTem:COMMunicate:PROFibus:DATe", value, 40, "installation date")

    def set_interface_description(self, value: str) -> None:
        """Validate and write interface description.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:PROFibus:DESCription``."""

        self._set_tag("SYSTem:COMMunicate:PROFibus:DESCription", value, 54, "interface description")

    def set_station_name(self, value: str) -> None:
        """Validate and write station name.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:PROFibus:NAMe``."""

        self._set_tag("SYSTem:COMMunicate:PROFibus:NAMe", value, 200, "station name")

    def configure_can(
        self,
        *,
        node_id: Optional[int] = None,
        broadcast_id: Optional[int] = None,
        extended_id: Optional[bool] = None,
        dlc_always_8: Optional[bool] = None,
        termination: Optional[bool] = None,
    ) -> None:
        """Configure selected CAN interface parameters. Only parameters supplied by the caller
        are modified.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:CAN:FORMat {value}``,
        ``SYSTem:COMMunicate:CAN:NODe {value}``, ``SYSTem:COMMunicate:CAN:BROadcast
        {value}``, ``SYSTem:COMMunicate:CAN:DLC {value}``,
        ``SYSTem:COMMunicate:CAN:TERMination {value}``, ``SYSTem:COMMunicate:CAN:FORMat``,
        ``SYSTem:COMMunicate:CAN:NODe``, ``SYSTem:COMMunicate:CAN:BROadcast``."""

        if extended_id is not None:
            self._write(f"SYSTem:COMMunicate:CAN:FORMat {'EXT' if extended_id else 'BASE'}")
        max_id = 0x1FFFFFFF if extended_id else 0x7FF
        if node_id is not None:
            value = int(ensure_range(node_id, 0, max_id, "CAN base/node ID"))
            self._write(f"SYSTem:COMMunicate:CAN:NODe {value}")
        if broadcast_id is not None:
            value = int(ensure_range(broadcast_id, 0, max_id, "CAN broadcast ID"))
            self._write(f"SYSTem:COMMunicate:CAN:BROadcast {value}")
        if dlc_always_8 is not None:
            self._write(f"SYSTem:COMMunicate:CAN:DLC {'FILL' if dlc_always_8 else 'AUTO'}")
        if termination is not None:
            self._write(f"SYSTem:COMMunicate:CAN:TERMination {'ON' if termination else 'OFF'}")

    def set_can_cyclic_read_ms(self, group: str, interval_ms: int) -> None:
        """Set the cyclic CAN read period for one documented data group; use 0 to disable that
        cyclic group.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:CAN:READ:{value} {value}``,
        ``SYSTem:COMMunicate:CAN:READ:``."""

        group_token = group.strip().upper().replace("-", "_")
        commands = {
            "ACTUAL": "ACTual",
            "LIMITS_UI": "ALIMits",
            "LIMITS_PR": "BLIMits",
            "SINK_LIMITS": "CLIMits",
            "SETPOINTS": "SETS",
            "SINK_SETPOINTS": "BSETs",
            "STATUS": "STAT",
        }
        if group_token not in commands:
            raise ValueError(f"unsupported CAN cyclic-read group {group!r}; choose {', '.join(commands)}")
        value = int(interval_ms)
        if value != 0 and not 20 <= value <= 5000:
            raise ValueError("CAN cyclic-read interval must be 0 or 20..5000 ms")
        self._write(f"SYSTem:COMMunicate:CAN:READ:{commands[group_token]} {value}")

    def set_can_read_base_id(self, value: int) -> None:
        """Validate and write can read base id.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:CAN:READ:NODe {value}``,
        ``SYSTem:COMMunicate:CAN:READ:NODe``."""

        self._write(f"SYSTem:COMMunicate:CAN:READ:NODe {int(value)}")

    def set_can_send_base_id(self, value: int) -> None:
        """Validate and write can send base id.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:CAN:SEND:NODe {value}``,
        ``SYSTem:COMMunicate:CAN:SEND:NODe``."""

        self._write(f"SYSTem:COMMunicate:CAN:SEND:NODe {int(value)}")

    def select_lan(self, index: int = 2) -> None:
        """Select which documented LAN interface index subsequent LAN configuration
        queries/writes address. Built-in RJ45 is normally index 2 on PSB 10000 hardware.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:LAN:INDex {value}``,
        ``SYSTem:COMMunicate:LAN:INDex``."""

        if index not in {1, 2}:
            raise ValueError("PSB 10000 LAN index must be 1 (slot) or 2 (built-in)")
        self._write(f"SYSTem:COMMunicate:LAN:INDex {index}")

    @property
    def lan_index(self) -> int:
        """Read and return the current selected LAN index from the instrument or driver state.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:LAN:INDex?``."""

        return self._query_int("SYSTem:COMMunicate:LAN:INDex?")

    @property
    def ip_address(self) -> str:
        """Read and return the current LAN IP address from the instrument or driver state.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:LAN:ADDRess?``."""

        return self._query("SYSTem:COMMunicate:LAN:ADDRess?").strip().strip('"')

    @ip_address.setter
    def ip_address(self, value: str) -> None:
        """Validate and write the LAN IP address to the instrument.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:LAN:ADDRess {value}``,
        ``SYSTem:COMMunicate:LAN:ADDRess``."""

        ipaddress.ip_address(value)
        self._write(f"SYSTem:COMMunicate:LAN:ADDRess {value}")

    @property
    def subnet_mask(self) -> str:
        """Read and return the current LAN subnet mask from the instrument or driver state.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:LAN:SMASk?``."""

        return self._query("SYSTem:COMMunicate:LAN:SMASk?").strip().strip('"')

    @subnet_mask.setter
    def subnet_mask(self, value: str) -> None:
        """Validate and write the LAN subnet mask to the instrument.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:LAN:SMASk {value}``,
        ``SYSTem:COMMunicate:LAN:SMASk``."""

        ipaddress.ip_address(value)
        self._write(f"SYSTem:COMMunicate:LAN:SMASk {value}")

    @property
    def gateway(self) -> str:
        """Read and return the current LAN gateway from the instrument or driver state.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:LAN:GATeway?``."""

        return self._query("SYSTem:COMMunicate:LAN:GATeway?").strip().strip('"')

    @gateway.setter
    def gateway(self, value: str) -> None:
        """Validate and write the LAN gateway to the instrument.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:LAN:GATeway {value}``,
        ``SYSTem:COMMunicate:LAN:GATeway``."""

        ipaddress.ip_address(value)
        self._write(f"SYSTem:COMMunicate:LAN:GATeway {value}")

    @property
    def tcp_port(self) -> int:
        """Read and return the current LAN TCP control port from the instrument or driver
        state.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:LAN:CONTrol?``."""

        return self._query_int("SYSTem:COMMunicate:LAN:CONTrol?")

    @tcp_port.setter
    def tcp_port(self, value: int) -> None:
        """Validate and write the LAN TCP control port to the instrument.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:LAN:CONTrol {value}``,
        ``SYSTem:COMMunicate:LAN:CONTrol``."""

        value = int(ensure_range(value, 0, 65535, "TCP port"))
        if value in {502, 537}:
            raise ValueError("Port is reserved by the instrument")
        self._write(f"SYSTem:COMMunicate:LAN:CONTrol {value}")

    @property
    def dhcp(self) -> bool:
        """Read and return the current LAN DHCP state from the instrument or driver state.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:LAN:DHCP?``."""

        return self._query_bool("SYSTem:COMMunicate:LAN:DHCP?")

    @dhcp.setter
    def dhcp(self, enabled: bool) -> None:
        """Validate and write the LAN DHCP state to the instrument.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:LAN:DHCP {value}``,
        ``SYSTem:COMMunicate:LAN:DHCP``."""

        self._write(f"SYSTem:COMMunicate:LAN:DHCP {bool_token(enabled)}")

    @property
    def keepalive(self) -> bool:
        """Read and return the current LAN TCP keepalive state from the instrument or driver
        state.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:LAN:KEEPalive?``."""

        return self._query_bool("SYSTem:COMMunicate:LAN:KEEPalive?")

    @keepalive.setter
    def keepalive(self, enabled: bool) -> None:
        """Validate and write the LAN TCP keepalive state to the instrument.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:LAN:KEEPalive {value}``,
        ``SYSTem:COMMunicate:LAN:KEEPalive``."""

        self._write(f"SYSTem:COMMunicate:LAN:KEEPalive {bool_token(enabled)}")

    @property
    def ethernet_timeout_s(self) -> int:
        # Documented keyword is TIMeout.  Previous :TIME spelling caused
        # command errors/timeouts on the user's PSB 10060-60 firmware.
        """Read and return the current LAN socket timeout from the instrument or driver state.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:LAN:TIMeout?``."""

        return self._query_int("SYSTem:COMMunicate:LAN:TIMeout?")

    @ethernet_timeout_s.setter
    def ethernet_timeout_s(self, value: int) -> None:
        """Validate and write the LAN socket timeout to the instrument.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:LAN:TIMeout {value}``,
        ``SYSTem:COMMunicate:LAN:TIMeout``."""

        value = int(value)
        if value != 0 and not 5 <= value <= 65535:
            raise ValueError("Ethernet timeout must be 0 or 5..65535 seconds")
        self._write(f"SYSTem:COMMunicate:LAN:TIMeout {value}")

    @property
    def hostname(self) -> str:
        """Read and return the current LAN host name from the instrument or driver state.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:LAN:HOSTname?``."""

        return self._query("SYSTem:COMMunicate:LAN:HOSTname?").strip().strip('"')

    @hostname.setter
    def hostname(self, value: str) -> None:
        """Validate and write the LAN host name to the instrument.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:LAN:HOSTname "{value}"``,
        ``SYSTem:COMMunicate:LAN:HOSTname "``."""

        if not value or len(value) > 54:
            raise ValueError("hostname must contain 1..54 characters")
        self._write(f'SYSTem:COMMunicate:LAN:HOSTname "{value}"')

    @property
    def domain(self) -> str:
        """Read and return the current LAN domain from the instrument or driver state.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:LAN:DOMain?``."""

        return self._query("SYSTem:COMMunicate:LAN:DOMain?").strip().strip('"')

    @domain.setter
    def domain(self, value: str) -> None:
        """Validate and write the LAN domain to the instrument.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:LAN:DOMain "{value}"``,
        ``SYSTem:COMMunicate:LAN:DOMain "``."""

        if len(value) > 54:
            raise ValueError("domain must be at most 54 characters")
        self._write(f'SYSTem:COMMunicate:LAN:DOMain "{value}"')

    @property
    def mac_address(self) -> str:
        """Read and return the current LAN MAC address from the instrument or driver state.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:LAN:MAC?``."""

        return self._query("SYSTem:COMMunicate:LAN:MAC?").strip().strip('"')

    def set_dns(self, primary: str, secondary: Optional[str] = None) -> None:
        """Validate and write dns.
        
        Underlying SCPI used here: ``SYSTem:COMMunicate:LAN:DNS1 {value}``,
        ``SYSTem:COMMunicate:LAN:DNS1``, ``SYSTem:COMMunicate:LAN:DNS2 {value}``,
        ``SYSTem:COMMunicate:LAN:DNS2``."""

        ipaddress.ip_address(primary)
        self._write(f"SYSTem:COMMunicate:LAN:DNS1 {primary}")
        if secondary is not None:
            ipaddress.ip_address(secondary)
            self._write(f"SYSTem:COMMunicate:LAN:DNS2 {secondary}")
