"""SiPM bias board registers (firmware BOARD_SIPM, register tables v2/v1).

Mirrors ``modbus_reg.c``; tests/fixtures/firmware_registers.json cross-checks it.
Boards with pre-July 2026 firmware stop at holding 15 / input 21; the device
class detects the actual table length when connecting.
"""

from nlab_modbus.core.register_specs import holding_register as H
from nlab_modbus.core.register_specs import input_register as I
from nlab_modbus.core.register_specs import temperature_register as T

REGISTER_VERSION = (2, 1)  # (holding, input) as reported by modbus_reg_version

SIPM_REGISTER_MAP = {
    # Holding registers
    "rs485_mb_addr": H(0, min=1, max=254, default=1, eeprom=True, description="Modbus address on the RS-485 port"),
    "rs485_baud": H(1, min=96, max=10000, default=96, scale=100, unit="bps", eeprom=True, description="RS-485 baud rate (96 = 9600 bps)"),
    "vout_pwr_en": H(2, min=0, max=1, default=0, description="SiPM bias output enable"),
    "vout_set": H(3, min=1500, max=7800, default=1500, scale=0.01, unit="V", eeprom=True, description="SiPM output voltage setpoint"),
    "pid_p_vout": H(4, min=0, max=1000, default=100, eeprom=True, password=True, description="Output voltage PID proportional gain"),
    "pid_i_vout": H(5, min=0, max=1000, default=100, eeprom=True, password=True, description="Output voltage PID integral gain"),
    "sipm_comp_en": H(6, min=0, max=1, default=0, eeprom=True, description="Temperature compensation enable"),
    "sipm_comp_tref": H(7, min=-5000, max=5000, default=2000, scale=0.01, unit="degC", eeprom=True, description="Compensation reference temperature"),
    "sipm_comp_ct": H(8, min=-100, max=100, default=0, unit="mV/degC", eeprom=True, description="Temperature compensation coefficient"),
    "vout_corr": H(9, min=-1000, max=1000, default=0, scale=0.01, unit="%", eeprom=True, password=True, description="Output voltage calibration correction"),
    "led_drv_enable": H(10, min=0, max=1, default=0, eeprom=True, description="Calibration LED driver enable"),
    "led_drv_period_us": H(11, min=1, max=650, default=1, unit="us", eeprom=True, password=True, description="Calibration LED pulse period"),
    "led_drv_duration_ns": H(12, min=1, max=100, default=1, scale=10, unit="ns", eeprom=True, password=True, description="Calibration LED pulse duration"),
    "led_drv_imod_reg": H(13, min=0, max=0xFFF, default=0xFF, eeprom=True, password=True, description="LED driver modulation current register"),
    "led_drv_ibias_reg": H(14, min=0, max=0xFFF, default=0, eeprom=True, password=True, description="LED driver bias current register"),
    "pass_static": H(15, min=-32767, max=32767, default=-4345, description="Service password"),
    "reset_device_command": H(16, min=-32767, max=32767, default=0, description="Write 999 to reset the device"),
    # Input registers
    "hardware_version": I(0, dtype="uint16", description="Hardware TYPE.REVISION (high/low byte)"),
    "firmware_version": I(1, dtype="uint16", description="Firmware MAJOR.MINOR (high/low byte)"),
    "vout_overload": I(2, description="SiPM supply overload status"),
    "sipm_voltage_10mv": I(3, scale=0.01, unit="V", description="SiPM output voltage"),
    "sipm_current_ua": I(4, unit="uA", description="SiPM output current"),
    "board_temp_adc": T(5, description="Current sensor temperature"),
    "rs485_rx_frames_cnt": I(6, dtype="uint16", description="RS-485 Modbus frames received"),
    "rs485_rx_crc_err_cnt": I(7, dtype="uint16", description="RS-485 Modbus frames with CRC errors"),
    "rs485_rx_bad_req_cnt": I(8, dtype="uint16", description="RS-485 invalid Modbus requests"),
    "cpu_temp": I(9, unit="degC", description="CPU temperature"),
    "board_temp": T(10, description="PCB temperature"),
    "eeprom_error": I(11, description="EEPROM error: 1 = hardware, 2 = CRC"),
    "supply_voltage": I(12, scale=0.01, unit="V", description="5 V supply voltage"),
    "adc_sipm_vout": I(13, scale=0.01, unit="V", description="SiPM output voltage (control ADC, low precision)"),
    "sipm_board_temp": T(14, description="External SiPM module temperature"),
    "sipm_correct_voltage_mv": I(15, unit="mV", description="Temperature compensation correction"),
    "vout_supply_fault": I(16, description="SiPM converter supply overload/overtemperature"),
    "ext_amp_supply_fault": I(17, description="External amplifier supply fault"),
    "led_drv_temp": T(18, scale=1, description="LED driver temperature"),
    "led_drv_status": I(19, description="LED driver status (LTC5100 datasheet p. 42)"),
    "vout_ripple": I(20, unit="mV", description="Output ripple over the last second"),
    "pid_saturation": I(21, description="PID integrator saturation"),
    "modbus_reg_version": I(22, dtype="uint16", description="Register table version HOLDING.INPUT (high/low byte)"),
    "serial_number_hi": I(23, dtype="uint16", description="Device serial number, high word"),
    "serial_number_lo": I(24, dtype="uint16", description="Device serial number, low word"),
}
