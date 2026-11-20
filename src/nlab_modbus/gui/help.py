"""Help mode: explainer texts for GUI elements (Qt "What's This", F1).

Texts are keyed by the widget object names from the .ui files, so a renamed
widget shows up as a failing test instead of silently losing its help.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget


def _html(title: str, *lines: str) -> str:
    return f"<b>{title}</b><br>" + "<br>".join(lines)


MAIN_WINDOW_HELP = {
    "groupBox": _html(
        "Local connection",
        "Boards on this PC's serial ports: the board's MicroUSB port or a USB-to-RS-485 adapter.",
    ),
    "port_select": _html(
        "Port",
        "Serial port with devices found by the last scan. You can also type a port name (COM3, /dev/ttyUSB0).",
    ),
    "local_id_select": _html(
        "Modbus address",
        "MicroUSB: always 1.",
        "RS-485: the board's <i>rs485_mb_addr</i> (default 1). Boards on one bus need distinct addresses.",
    ),
    "baudrate_select": _html(
        "Baud rate",
        "<i>Auto</i> uses the rate found by the scan, or tries 9600 then 115200.",
        "RS-485: must equal the board's <i>rs485_baud</i> (default 9600). MicroUSB: any rate works.",
    ),
    "local_type_select": _html(
        "Type",
        "Selects the register map. Filled in for scanned devices; if the board reports a different type "
        "you are asked before the tab opens.",
    ),
    "scan_local_btn": _html(
        "Scan local ports",
        "Probes every free serial port for Modbus addresses in the scan range (default 1–16). "
        "Ports already open in a tab are skipped.",
    ),
    "local_btn": _html(
        "Connect",
        "Opens a tab for the selected device after reading its type, revision and firmware version.",
    ),
    "groupBox_2": _html(
        "Remote connection",
        "Boards behind a digitizer gateway. ser2net forwards Modbus RTU between TCP and the gateway's "
        "RS-485 buses; the gateway fixes the bus baud rate (9600).",
    ),
    "host_select": _html(
        "Host",
        "Gateway IP address or host name. Digitizers advertising <i>nucliflare</i> via mDNS are listed automatically.",
    ),
    "remote_port_select": _html(
        "Port",
        "Gateway TCP port: 5001 = RS-485 bus 1, 5002 = bus 2.",
        "Only one client per port: a new connection from any program drops the previous one.",
    ),
    "remote_id_select": _html("Modbus address", "The board's <i>rs485_mb_addr</i> on that bus."),
    "remote_type_select": _html(
        "Type",
        "Selects the register map. Filled in for scanned devices; a mismatch with the board is reported before connecting.",
    ),
    "scan_remote_btn": _html(
        "Scan gateways",
        "Finds gateways via mDNS and probes both bus ports. Ports already open in a tab are skipped.",
    ),
    "remote_btn": _html(
        "Connect",
        "Opens a tab for the selected device after reading its type, revision and firmware version.",
    ),
    "devices_group": _html(
        "Devices",
        "One tab per connected device, titled with its link and address. Hover a tab title for the board identity.",
    ),
    "device_tabs": _html(
        "Devices",
        "One tab per connected device, titled with its link and address. Hover a tab title for the board identity.",
    ),
}

DEVICE_TAB_HELP = {
    "groupBox_3": _html("Device", "Board identity, polling intervals and connection controls."),
    "type_edit": _html(
        "Board identity",
        "Reported by the device: type, hardware revision and firmware version "
        "(newer firmware also reports register version and serial number).",
    ),
    "refresh_spinner": _html(
        "Input interval",
        "How often measurements are read. Shorter intervals load the bus more; "
        "at 9600 baud one full read takes about 65 ms.",
    ),
    "holding_refresh_spinner": _html(
        "Holding interval",
        "How often settings are re-read, so changes made by other programs appear here.",
    ),
    "clear_plot_btn": _html("Clear plot", "Deletes the plot history (the last 1000 samples per register)."),
    "tab_disconnect_btn": _html("Disconnect", "Stops polling and closes this device's connection."),
    "groupBox": _html(
        "Holding registers",
        "Device settings. Double-click a value to change it; it is checked against the firmware limits "
        "before it is written.",
        "Grey rows need the service password (<i>Connection → Service Mode</i>). "
        "Settings saved to EEPROM survive a power cycle.",
    ),
    "holding_table_view": _html(
        "Holding registers",
        "Device settings. Double-click a value to change it; it is checked against the firmware limits "
        "before it is written.",
        "Grey rows need the service password (<i>Connection → Service Mode</i>). "
        "Click a row in help mode for that register's details.",
    ),
    "groupBox_2": _html("Input registers", "Live measurements, read every input interval."),
    "input_table_view": _html(
        "Input registers",
        "Live measurements, read every input interval. Tick <i>Plot</i> to chart a register. "
        "Click a row in help mode for that register's details.",
    ),
    "input_plot": _html(
        "Plot",
        "Ticked input registers over time, in the units shown in the table.",
        "Wheel: zoom. Drag: pan. Right-click: options. <i>A</i> button: autoscale.",
    ),
}

COLUMN_HELP = {
    "ID": _html("ID", "Register address in the firmware table (0-based)."),
    "Register": _html("Register", "Name used by the Python library, e.g. <tt>device.read(\"vout_set\")</tt>."),
    "Value": _html("Value", "Physical value, or the raw register count when <i>View → Show raw values</i> is on."),
    "Unit": _html("Unit", "Physical unit. In the raw view: the factor that converts the count to the physical value."),
    "Plot": _html("Plot", "Tick to add the register to the plot."),
}

HELP_MODE_HINT = "Help mode: click any element to see what it does (Esc to cancel)."

STATUS_BAR_HELP = _html(
    "Status bar",
    "Latest message. Double-click for the full log; <i>View → Debug Mode</i> adds details.",
)


def apply_help(ui: object, texts: dict[str, str]) -> list[str]:
    """Set What's This texts on the named widgets of a generated UI; return names not found."""
    missing = []
    for name, text in texts.items():
        widget = getattr(ui, name, None)
        if isinstance(widget, QWidget):
            widget.setWhatsThis(text)
        else:
            missing.append(name)
    return missing


def register_help(name: str, tooltip: str) -> str:
    """Explainer for one register row: its name plus the tooltip details."""
    return _html(name, *(line for line in tooltip.splitlines() if line))
