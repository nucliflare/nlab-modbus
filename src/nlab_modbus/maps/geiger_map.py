"""Geiger-Mueller board registers (firmware BOARD_GM, register tables v1/v1).

Mirrors ``modbus_reg.c``; tests/fixtures/firmware_registers.json cross-checks it.
Boards with pre-July 2026 firmware stop at holding 28 / input 19; the device
class detects the actual table length when connecting.

Dose calibration coefficients are (mantissa, exponent) pairs:
``value = mantissa * 10**exponent`` (see nlab_modbus.calibration).
"""

from nlab_modbus.core.register_specs import holding_register as H
from nlab_modbus.core.register_specs import input_register as I
from nlab_modbus.core.register_specs import temperature_register as T

REGISTER_VERSION = (1, 1)  # (holding, input) as reported by modbus_reg_version


def _coefficient(address: int, label: str, default: int) -> dict:
    """Mantissa/exponent register pair of one dose-calibration coefficient."""
    return {
        f"scale_coeff_{label}": H(address, min=-32000, max=32000, default=default, eeprom=True, password=True,
                                  description=f"Dose calibration {label} mantissa"),
        f"scale_exp_{label}": H(address + 1, min=-9, max=9, default=0, eeprom=True, password=True,
                                description=f"Dose calibration {label} exponent"),
    }


GEIGER_REGISTER_MAP = {
    # Holding registers
    "rs485_mb_addr": H(0, min=1, max=254, default=1, eeprom=True, description="Modbus address on the RS-485 port"),
    "rs485_baud": H(1, min=96, max=10000, default=96, scale=100, unit="bps", eeprom=True, description="RS-485 baud rate (96 = 9600 bps)"),
    "pwm_enable": H(2, min=0, max=1, default=1, eeprom=True, description="GM tube HV supply enable"),
    "pwm_set_voltage": H(3, min=50, max=650, default=550, unit="V", eeprom=True, description="GM tube HV setpoint"),
    "pulse_trig_level_mv": H(4, min=0, max=2500, default=200, unit="mV", eeprom=True, password=True, description="GM pulse comparator threshold"),
    "dummy_1": H(5, min=0, max=0, default=0, eeprom=True, description="Reserved"),
    "pwm_freq_khz": H(6, min=10, max=500, default=200, unit="kHz", eeprom=True, password=True, description="HV converter switching frequency"),
    "pwm_max_duty": H(7, min=0, max=90, default=50, unit="%", eeprom=True, password=True, description="HV converter maximum duty cycle"),
    "pwm_outvolt_comp": H(8, min=-1000, max=1000, default=0, scale=0.01, unit="%", eeprom=True, password=True, description="HV setpoint calibration correction"),
    "dummy_2": H(9, min=0, max=0, default=0, eeprom=True, description="Reserved"),
    **_coefficient(10, "p1_a2", 0),
    **_coefficient(12, "p1_a1", 0),
    **_coefficient(14, "p1_a0", 1),
    **_coefficient(16, "th", 0),
    **_coefficient(18, "p2_a2", 0),
    **_coefficient(20, "p2_a1", 0),
    **_coefficient(22, "p2_a0", 1),
    "pid_p_vout": H(24, min=0, max=1000, default=200, eeprom=True, password=True, description="Output voltage PID proportional gain"),
    "pid_i_vout": H(25, min=0, max=1000, default=500, eeprom=True, password=True, description="Output voltage PID integral gain"),
    "adc_freq_khz": H(26, min=1, max=20, default=10, unit="kHz", eeprom=True, password=True, description="HV control loop frequency"),
    "adc_filter_coeff": H(27, min=0, max=100, default=10, eeprom=True, password=True, description="HV measurement filter coefficient"),
    "pass_static": H(28, min=-32767, max=32767, default=-4345, description="Service password"),
    "reset_device_command": H(29, min=-32767, max=32767, default=0, description="Write 999 to reset the device"),
    "pwm_max_width_ns": H(30, min=10, max=1000, default=300, scale=10, unit="ns", eeprom=True, password=True, description="HV converter maximum pulse width"),
    # Input registers
    "hardware_version": I(0, dtype="uint16", description="Hardware TYPE.REVISION (high/low byte)"),
    "firmware_version": I(1, dtype="uint16", description="Firmware MAJOR.MINOR (high/low byte)"),
    "pulses": I(2, dtype="uint16", description="GM pulse counter (wraps at 65535)"),
    "pulses_per_sec": I(3, dtype="uint16", unit="cps", description="GM pulse rate"),
    "dose_level_msvh": I(4, unit="mSv/h", description="Dose rate from the calibration curve (integer)"),
    "dose_msv": I(5, unit="mSv", description="Dose accumulated since power-up (integer)"),
    "rs485_rx_frames_cnt": I(6, dtype="uint16", description="RS-485 Modbus frames received"),
    "rs485_rx_crc_err_cnt": I(7, dtype="uint16", description="RS-485 Modbus frames with CRC errors"),
    "rs485_rx_bad_req_cnt": I(8, dtype="uint16", description="RS-485 invalid Modbus requests"),
    "cpu_temp": I(9, unit="degC", description="CPU temperature"),
    "board_temp": T(10, description="PCB temperature"),
    "eeprom_error": I(11, description="EEPROM error: 1 = hardware, 2 = CRC"),
    "supply_voltage": I(12, scale=0.01, unit="V", description="5 V supply voltage"),
    "hv_voltage": I(13, unit="V", description="Measured HV output"),
    "pulse_integer": I(14, unit="mV", description="GM pulse integrator voltage"),
    "gm_supply_fault": I(15, description="HV converter supply overload/overtemperature"),
    "pwm_duty": I(16, scale=0.1, unit="%", description="HV converter duty cycle"),
    "vout_ripple": I(17, unit="mV", description="HV ripple over the last second"),
    "pwm_cmpss_action": I(18, description="Hardware HV protection tripped (clears after 1 s)"),
    "pid_saturation": I(19, description="PID integrator saturation"),
    "modbus_reg_version": I(20, dtype="uint16", description="Register table version HOLDING.INPUT (high/low byte)"),
    "serial_number_hi": I(21, dtype="uint16", description="Device serial number, high word"),
    "serial_number_lo": I(22, dtype="uint16", description="Device serial number, low word"),
    "pwm_pulse_width_ns": I(23, scale=10, unit="ns", description="HV converter pulse width"),
}
