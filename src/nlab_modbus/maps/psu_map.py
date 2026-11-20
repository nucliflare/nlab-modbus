"""PMT high-voltage supply registers (firmware BOARD_HV, register tables v1/v1).

Mirrors ``modbus_reg.c``; tests/fixtures/firmware_registers.json cross-checks it.
Boards with pre-July 2026 firmware stop at holding 11 / input 15; the device
class detects the actual table length when connecting.
"""

from nlab_modbus.core.register_specs import holding_register as H
from nlab_modbus.core.register_specs import input_register as I
from nlab_modbus.core.register_specs import temperature_register as T

REGISTER_VERSION = (1, 1)  # (holding, input) as reported by modbus_reg_version

PSU_REGISTER_MAP = {
    # Holding registers
    "rs485_mb_addr": H(0, min=1, max=254, default=1, eeprom=True, description="Modbus address on the RS-485 port"),
    "rs485_baud": H(1, min=96, max=10000, default=96, scale=100, unit="bps", eeprom=True, description="RS-485 baud rate (96 = 9600 bps)"),
    "pwm_enable": H(2, min=0, max=1, default=0, description="HV output enable"),
    "pwm_set_voltage": H(3, min=50, max=1500, default=100, unit="V", eeprom=True, description="HV output setpoint"),
    "pwm_freq_khz": H(4, min=10, max=100, default=40, unit="kHz", eeprom=True, password=True, description="HV converter switching frequency"),
    "pwm_max_duty": H(5, min=0, max=60, default=50, unit="%", eeprom=True, password=True, description="HV converter maximum duty cycle"),
    "pwm_outvolt_comp": H(6, min=-1000, max=1000, default=0, scale=0.01, unit="%", eeprom=True, password=True, description="HV setpoint calibration correction"),
    "pid_p_vout": H(7, min=0, max=1000, default=15, eeprom=True, password=True, description="Output voltage PID proportional gain"),
    "pid_i_vout": H(8, min=0, max=1000, default=200, eeprom=True, password=True, description="Output voltage PID integral gain"),
    "adc_freq_khz": H(9, min=1, max=20, default=10, unit="kHz", eeprom=True, password=True, description="HV control loop frequency"),
    "adc_filter_coeff": H(10, min=0, max=100, default=10, eeprom=True, password=True, description="HV measurement filter coefficient"),
    "pass_static": H(11, min=-32767, max=32767, default=-4345, description="Service password"),
    "reset_device_command": H(12, min=-32767, max=32767, default=0, description="Write 999 to reset the device"),
    "pwm_max_width_ns": H(13, min=10, max=1000, default=300, scale=10, unit="ns", eeprom=True, password=True, description="HV converter maximum pulse width"),
    # Input registers
    "hardware_version": I(0, dtype="uint16", description="Hardware TYPE.REVISION (high/low byte)"),
    "firmware_version": I(1, dtype="uint16", description="Firmware MAJOR.MINOR (high/low byte)"),
    "rs485_rx_frames_cnt": I(2, dtype="uint16", description="RS-485 Modbus frames received"),
    "rs485_rx_crc_err_cnt": I(3, dtype="uint16", description="RS-485 Modbus frames with CRC errors"),
    "rs485_rx_bad_req_cnt": I(4, dtype="uint16", description="RS-485 invalid Modbus requests"),
    "cpu_temp": I(5, unit="degC", description="CPU temperature"),
    "board_temp": T(6, description="PCB temperature"),
    "eeprom_error": I(7, description="EEPROM error: 1 = hardware, 2 = CRC"),
    "supply_voltage": I(8, scale=0.01, unit="V", description="5 V supply voltage"),
    "hv_voltage": I(9, unit="V", description="Measured HV output"),
    "pwm_duty": I(10, scale=0.1, unit="%", description="HV converter duty cycle"),
    "hv_current": I(11, unit="uA", description="Measured HV output current"),
    "vout_ripple": I(12, unit="mV", description="HV ripple over the last second"),
    "pwm_cmpss_action": I(13, description="Hardware HV protection tripped (clears after 1 s)"),
    "pid_saturation": I(14, description="PID integrator saturation"),
    "pmt_temp": T(15, description="PMT module temperature"),
    "modbus_reg_version": I(16, dtype="uint16", description="Register table version HOLDING.INPUT (high/low byte)"),
    "serial_number_hi": I(17, dtype="uint16", description="Device serial number, high word"),
    "serial_number_lo": I(18, dtype="uint16", description="Device serial number, low word"),
    "pwm_pulse_width_ns": I(19, scale=10, unit="ns", description="HV converter pulse width"),
}
