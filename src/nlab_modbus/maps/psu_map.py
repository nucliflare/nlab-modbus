from nlab_modbus.core.register_specs import RegisterSpec, RegisterType

PSU_REGISTER_MAP = {
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
