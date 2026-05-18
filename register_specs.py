from dataclasses import dataclass
from enum import Enum


class RegisterType(Enum):
    HOLDING = "holding"
    INPUT = "input"


@dataclass(frozen=True)
class RegisterSpec:
    reg_type: RegisterType
    address: int
    dtype: str
    min: int
    max: int
    count: int = 1
    scale: float = 1.0
    unit: str | None = None


SIPM_REGISTER_MAP = {
    # Holding registers
    "rs485_mb_addr": RegisterSpec(reg_type=RegisterType.HOLDING, address=0, dtype="uint16", min=1, max=254),
    "rs485_baud": RegisterSpec(reg_type=RegisterType.HOLDING, address=1, dtype="uint16", min=100, max=10000, scale=100),
    "vout_pwr_en": RegisterSpec(reg_type=RegisterType.HOLDING, address=2, dtype="uint16", min=0, max=1),
    "vout_set": RegisterSpec(reg_type=RegisterType.HOLDING, address=3, dtype="uint16", min=1500, max=7800, unit="mV", scale=0.01),
    "pid_p_vout": RegisterSpec(reg_type=RegisterType.HOLDING, address=4, dtype="uint16", min=0, max=1000),
    "pid_i_vout": RegisterSpec(reg_type=RegisterType.HOLDING, address=5, dtype="uint16", min=0, max=1000),
    "sipm_comp_en": RegisterSpec(reg_type=RegisterType.HOLDING, address=6, dtype="uint16", min=0, max=1),
    "sipm_comp_tref": RegisterSpec(reg_type=RegisterType.HOLDING, address=7, dtype="int16", min=-5000, max=5000, scale=0.01, unit="*C"),
    "sipm_comp_ct": RegisterSpec(reg_type=RegisterType.HOLDING, address=8, dtype="int16", min=-100, max=100, unit="mv/*C"),
    "vout_corr": RegisterSpec(reg_type=RegisterType.HOLDING, address=9, dtype="int16", min=-1000, max=1000, scale=0.01),
    "led_drv_enable": RegisterSpec(reg_type=RegisterType.HOLDING, address=10, dtype="uint16", min=0, max=1),
    "led_drv_period_us": RegisterSpec(reg_type=RegisterType.HOLDING, address=11, dtype="uint16", min=1, max=650, unit="us"),
    "led_drv_duration_ns": RegisterSpec(reg_type=RegisterType.HOLDING, address=12, dtype="uint16", min=1, max=100, scale=10.0, unit="ns"),
    "led_drv_imod_reg": RegisterSpec(reg_type=RegisterType.HOLDING, address=13, dtype="uint16", min=0, max=0xFFF),
    "led_drv_ibias_reg": RegisterSpec(reg_type=RegisterType.HOLDING, address=14, dtype="uint16", min=0, max=0xFFF),
    "pass_static": RegisterSpec(reg_type=RegisterType.HOLDING, address=15, dtype="int16", min=-32767, max=32767),
    # Input registers
    "hardware_version": RegisterSpec(reg_type=RegisterType.INPUT, address=0, dtype="uint16", min=0, max=65535),
    "firmware_version": RegisterSpec(reg_type=RegisterType.INPUT, address=1, dtype="uint16", min=0, max=65535),
    "vout_overload": RegisterSpec(reg_type=RegisterType.INPUT, address=2, dtype="uint16", min=0, max=1),
    "sipm_voltage_10mv": RegisterSpec(reg_type=RegisterType.INPUT, address=3, dtype="uint16", min=0, max=65535, unit="V", scale=0.01),
    "sipm_current_ua": RegisterSpec(reg_type=RegisterType.INPUT, address=4, dtype="uint16", min=0, max=65535, unit="A", scale=0.000001),
    "board_temp_adc": RegisterSpec(reg_type=RegisterType.INPUT, address=5, dtype="int16", min=-32768, max=32767, unit="*C", scale=0.01),
    "usb_rx_frames_cnt": RegisterSpec(reg_type=RegisterType.INPUT, address=6, dtype="uint16", min=0, max=65535),
    "usb_rx_crc_err_cnt": RegisterSpec(reg_type=RegisterType.INPUT, address=7, dtype="uint16", min=0, max=65535),
    "usb_rx_bad_req_cnt": RegisterSpec(reg_type=RegisterType.INPUT, address=8, dtype="uint16", min=0, max=65535),
    "cpu_temp": RegisterSpec(reg_type=RegisterType.INPUT, address=9, dtype="int16", min=-32768, max=32767, unit="*C"),
    "board_temp": RegisterSpec(reg_type=RegisterType.INPUT, address=10, dtype="int16", min=-32768, max=32767, unit="*C", scale=0.01),
    "eeprom_error": RegisterSpec(reg_type=RegisterType.INPUT, address=11, dtype="uint16", min=0, max=2),
    "supply_voltage": RegisterSpec(reg_type=RegisterType.INPUT, address=12, dtype="uint16", min=0, max=65535, unit="V", scale=0.01),
    "adc_sipm_vout": RegisterSpec(reg_type=RegisterType.INPUT, address=13, dtype="uint16", min=0, max=65535, unit="V", scale=0.01),
    "sipm_board_temp": RegisterSpec(reg_type=RegisterType.INPUT, address=14, dtype="int16", min=-32768, max=32767, unit="*C", scale=0.01),
    "sipm_correct_voltage_mv": RegisterSpec(reg_type=RegisterType.INPUT, address=15, dtype="int16", min=-32768, max=32767, unit="mV"),
    "vout_supply_fault": RegisterSpec(reg_type=RegisterType.INPUT, address=16, dtype="uint16", min=0, max=1),
    "ext_amp_supply_fault": RegisterSpec(reg_type=RegisterType.INPUT, address=17, dtype="uint16", min=0, max=1),
    "led_drv_temp": RegisterSpec(reg_type=RegisterType.INPUT, address=18, dtype="int16", min=-32768, max=32767, unit="*C"),
    "led_drv_status": RegisterSpec(reg_type=RegisterType.INPUT, address=19, dtype="uint16", min=0, max=65535),
    "vout_ripple": RegisterSpec(reg_type=RegisterType.INPUT, address=20, dtype="uint16", min=0, max=65535, unit="mV"),
    "pid_saturation": RegisterSpec(reg_type=RegisterType.INPUT, address=21, dtype="uint16", min=0, max=65535),
}

GEIGER_REGISTER_MAP = {
    # Holding registers
    "rs485_mb_addr": RegisterSpec(reg_type=RegisterType.HOLDING, address=0, dtype="uint16", min=1, max=254),
    "rs485_baud": RegisterSpec(reg_type=RegisterType.HOLDING, address=1, dtype="uint16", min=96, max=10000, scale=100),
    "pwm_enable": RegisterSpec(reg_type=RegisterType.HOLDING, address=2, dtype="uint16", min=0, max=1),
    "pwm_set_voltage": RegisterSpec(reg_type=RegisterType.HOLDING, address=3, dtype="uint16", min=50, max=650, unit="V"),
    "dac_vout_mv": RegisterSpec(reg_type=RegisterType.HOLDING, address=4, dtype="uint16", min=0, max=2500, unit="mV"),
    "dac_vout_mv_2": RegisterSpec(reg_type=RegisterType.HOLDING, address=5, dtype="uint16", min=0, max=2500, unit="mV"),
    "pwm_freq_khz": RegisterSpec(reg_type=RegisterType.HOLDING, address=6, dtype="uint16", min=10, max=500, unit="kHz"),
    "pwm_max_duty": RegisterSpec(reg_type=RegisterType.HOLDING, address=7, dtype="uint16", min=0, max=90, unit="%"),
    "pwm_outvolt_comp": RegisterSpec(reg_type=RegisterType.HOLDING, address=8, dtype="int16", min=-1000, max=1000, scale=0.01, unit="%"),
    "dac_vout_mv_3": RegisterSpec(reg_type=RegisterType.HOLDING, address=9, dtype="uint16", min=0, max=2500, unit="mV"),
    "scale_coeff_p1_a2": RegisterSpec(reg_type=RegisterType.HOLDING, address=10, dtype="int16", min=-32000, max=32000),
    "scale_exp_p1_a2": RegisterSpec(reg_type=RegisterType.HOLDING, address=11, dtype="int16", min=-9, max=9),
    "scale_coeff_p1_a1": RegisterSpec(reg_type=RegisterType.HOLDING, address=12, dtype="int16", min=-32000, max=32000),
    "scale_exp_p1_a1": RegisterSpec(reg_type=RegisterType.HOLDING, address=13, dtype="int16", min=-9, max=9),
    "scale_coeff_p1_a0": RegisterSpec(reg_type=RegisterType.HOLDING, address=14, dtype="int16", min=-32000, max=32000),
    "scale_exp_p1_a0": RegisterSpec(reg_type=RegisterType.HOLDING, address=15, dtype="int16", min=-9, max=9),
    "scale_coeff_th": RegisterSpec(reg_type=RegisterType.HOLDING, address=16, dtype="int16", min=-32000, max=32000),
    "scale_exp_th": RegisterSpec(reg_type=RegisterType.HOLDING, address=17, dtype="int16", min=-9, max=9),
    "scale_coeff_p2_a2": RegisterSpec(reg_type=RegisterType.HOLDING, address=18, dtype="int16", min=-32000, max=32000),
    "scale_exp_p2_a2": RegisterSpec(reg_type=RegisterType.HOLDING, address=19, dtype="int16", min=-9, max=9),
    "scale_coeff_p2_a1": RegisterSpec(reg_type=RegisterType.HOLDING, address=20, dtype="int16", min=-32000, max=32000),
    "scale_exp_p2_a1": RegisterSpec(reg_type=RegisterType.HOLDING, address=21, dtype="int16", min=-9, max=9),
    "scale_coeff_p2_a0": RegisterSpec(reg_type=RegisterType.HOLDING, address=22, dtype="int16", min=-32000, max=32000),
    "scale_exp_p2_a0": RegisterSpec(reg_type=RegisterType.HOLDING, address=23, dtype="int16", min=-9, max=9),
    "pid_p_vout": RegisterSpec(reg_type=RegisterType.HOLDING, address=24, dtype="uint16", min=0, max=1000),
    "pid_i_vout": RegisterSpec(reg_type=RegisterType.HOLDING, address=25, dtype="uint16", min=0, max=1000),
    "adc_freq_khz": RegisterSpec(reg_type=RegisterType.HOLDING, address=26, dtype="uint16", min=1, max=20, unit="kHz"),
    "adc_filter_coeff": RegisterSpec(reg_type=RegisterType.HOLDING, address=27, dtype="uint16", min=0, max=100),
    "pass_static": RegisterSpec(reg_type=RegisterType.HOLDING, address=28, dtype="int16", min=-32767, max=32767),
    # Input registers
    "hardware_version": RegisterSpec(reg_type=RegisterType.INPUT, address=0, dtype="uint16", min=0, max=65535),
    "firmware_version": RegisterSpec(reg_type=RegisterType.INPUT, address=1, dtype="uint16", min=0, max=65535),
    "pulses": RegisterSpec(reg_type=RegisterType.INPUT, address=2, dtype="uint32", min=0, max=4294967295),
    "pulses_per_sec": RegisterSpec(reg_type=RegisterType.INPUT, address=3, dtype="uint32", min=0, max=4294967295, unit="cps"),
    "dose_level_msvh": RegisterSpec(reg_type=RegisterType.INPUT, address=4, dtype="int32", min=-2147483648, max=2147483647, unit="mSv/h"),
    "dose_msv": RegisterSpec(reg_type=RegisterType.INPUT, address=5, dtype="int32", min=-2147483648, max=2147483647, unit="mSv"),
    "usb_rx_frames_cnt": RegisterSpec(reg_type=RegisterType.INPUT, address=6, dtype="uint16", min=0, max=65535),
    "usb_rx_crc_err_cnt": RegisterSpec(reg_type=RegisterType.INPUT, address=7, dtype="uint16", min=0, max=65535),
    "usb_rx_bad_req_cnt": RegisterSpec(reg_type=RegisterType.INPUT, address=8, dtype="uint16", min=0, max=65535),
    "cpu_temp": RegisterSpec(reg_type=RegisterType.INPUT, address=9, dtype="int16", min=-32768, max=32767, unit="*C"),
    "board_temp": RegisterSpec(reg_type=RegisterType.INPUT, address=10, dtype="int16", min=-32768, max=32767, unit="*C", scale=0.01),
    "eeprom_error": RegisterSpec(reg_type=RegisterType.INPUT, address=11, dtype="uint16", min=0, max=2),
    "supply_voltage": RegisterSpec(reg_type=RegisterType.INPUT, address=12, dtype="uint16", min=0, max=65535, unit="V", scale=0.01),
    "hv_voltage": RegisterSpec(reg_type=RegisterType.INPUT, address=13, dtype="uint16", min=0, max=65535, unit="V", scale=0.01),
    "pulse_integer": RegisterSpec(reg_type=RegisterType.INPUT, address=14, dtype="int16", min=-32768, max=32767, unit="mV"),
    "gm_supply_fault": RegisterSpec(reg_type=RegisterType.INPUT, address=15, dtype="uint16", min=0, max=1),
    "pwm_duty": RegisterSpec(reg_type=RegisterType.INPUT, address=16, dtype="uint16", min=0, max=1000, scale=0.1, unit="%"),
    "vout_ripple": RegisterSpec(reg_type=RegisterType.INPUT, address=17, dtype="uint16", min=0, max=65535, unit="mV"),
    "pwm_cmpss_action": RegisterSpec(reg_type=RegisterType.INPUT, address=18, dtype="uint16", min=0, max=65535),
    "pid_saturation": RegisterSpec(reg_type=RegisterType.INPUT, address=19, dtype="uint16", min=0, max=65535),
}

HV_REGISTER_MAP = {
    # Holding registers
    "rs485_mb_addr": RegisterSpec(reg_type=RegisterType.HOLDING, address=0, dtype="uint16", min=1, max=254),
    "rs485_baud": RegisterSpec(reg_type=RegisterType.HOLDING, address=1, dtype="uint16", min=96, max=10000, scale=100),
    "pwm_enable": RegisterSpec(reg_type=RegisterType.HOLDING, address=2, dtype="uint16", min=0, max=1),
    "pwm_set_voltage": RegisterSpec(reg_type=RegisterType.HOLDING, address=3, dtype="uint16", min=50, max=1500, unit="V"),
    "pwm_freq_khz": RegisterSpec(reg_type=RegisterType.HOLDING, address=4, dtype="uint16", min=10, max=100, unit="kHz"),
    "pwm_max_duty": RegisterSpec(reg_type=RegisterType.HOLDING, address=5, dtype="uint16", min=0, max=60, unit="%"),
    "pwm_outvolt_comp": RegisterSpec(reg_type=RegisterType.HOLDING, address=6, dtype="int16", min=-1000, max=1000, scale=0.01, unit="%"),
    "pid_p_vout": RegisterSpec(reg_type=RegisterType.HOLDING, address=7, dtype="uint16", min=0, max=1000),
    "pid_i_vout": RegisterSpec(reg_type=RegisterType.HOLDING, address=8, dtype="uint16", min=0, max=1000),
    "adc_freq_khz": RegisterSpec(reg_type=RegisterType.HOLDING, address=9, dtype="uint16", min=1, max=20, unit="kHz"),
    "adc_filter_coeff": RegisterSpec(reg_type=RegisterType.HOLDING, address=10, dtype="uint16", min=0, max=100),
    "pass_static": RegisterSpec(reg_type=RegisterType.HOLDING, address=11, dtype="int16", min=-32767, max=32767),
    # Input registers
    "hardware_version": RegisterSpec(reg_type=RegisterType.INPUT, address=0, dtype="uint16", min=0, max=65535),
    "firmware_version": RegisterSpec(reg_type=RegisterType.INPUT, address=1, dtype="uint16", min=0, max=65535),
    "usb_rx_frames_cnt": RegisterSpec(reg_type=RegisterType.INPUT, address=2, dtype="uint16", min=0, max=65535),
    "usb_rx_crc_err_cnt": RegisterSpec(reg_type=RegisterType.INPUT, address=3, dtype="uint16", min=0, max=65535),
    "usb_rx_bad_req_cnt": RegisterSpec(reg_type=RegisterType.INPUT, address=4, dtype="uint16", min=0, max=65535),
    "cpu_temp": RegisterSpec(reg_type=RegisterType.INPUT, address=5, dtype="int16", min=-32768, max=32767, unit="*C"),
    "board_temp": RegisterSpec(reg_type=RegisterType.INPUT, address=6, dtype="int16", min=-32768, max=32767, unit="*C"),
    "eeprom_error": RegisterSpec(reg_type=RegisterType.INPUT, address=7, dtype="uint16", min=0, max=2),
    "supply_voltage": RegisterSpec(reg_type=RegisterType.INPUT, address=8, dtype="uint16", min=0, max=65535, unit="V", scale=0.01),
    "hv_voltage": RegisterSpec(reg_type=RegisterType.INPUT, address=9, dtype="uint16", min=0, max=65535, unit="V"),
    "pwm_duty": RegisterSpec(reg_type=RegisterType.INPUT, address=10, dtype="uint16", min=0, max=1000, scale=0.1, unit="%"),
    "hv_current": RegisterSpec(reg_type=RegisterType.INPUT, address=11, dtype="uint16", min=0, max=65535, unit="uA"),
    "vout_ripple": RegisterSpec(reg_type=RegisterType.INPUT, address=12, dtype="uint16", min=0, max=65535, unit="mV"),
    "pwm_cmpss_action": RegisterSpec(reg_type=RegisterType.INPUT, address=13, dtype="uint16", min=0, max=65535),
    "pid_saturation": RegisterSpec(reg_type=RegisterType.INPUT, address=14, dtype="uint16", min=0, max=65535),
    "pmt_temp": RegisterSpec(reg_type=RegisterType.INPUT, address=15, dtype="int16", min=-32768, max=32767, unit="*C"),
}
