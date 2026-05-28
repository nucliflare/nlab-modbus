from nlab_modbus.core.base_modbus_device import BaseModbusDevice
from nlab_modbus.core.enums import DeviceType
from nlab_modbus.maps.sipm_map import SIPM_REGISTER_MAP


class SiPMDevice(BaseModbusDevice):
    register_map = SIPM_REGISTER_MAP

    def __init__(self, client, device_id: int):
        super().__init__(client, device_id)
        self.device_type: DeviceType = DeviceType.SIPM

    # Holding register getters and setters
    def get_rs485_mb_addr(self) -> int:
        """Get RS485 Modbus address"""
        return self.read("rs485_mb_addr")

    def set_rs485_mb_addr(self, value: int) -> None:
        """Set RS485 Modbus address"""
        self.write("rs485_mb_addr", value)

    def get_rs485_baud(self) -> float:
        """Get RS485 baud rate"""
        return self.read("rs485_baud")

    def set_rs485_baud(self, value: int) -> None:
        """Set RS485 baud rate"""
        self.write("rs485_baud", value)

    def get_vout_pwr_en(self) -> bool:
        """Get output power enable status"""
        return self.read("vout_pwr_en")

    def set_vout_pwr_en(self, value: bool) -> None:
        """Set output power enable status"""
        self.write("vout_pwr_en", value)

    def get_vout_set(self) -> float:
        """Get output voltage setting"""
        return self.read("vout_set")

    def set_vout_set(self, value: float) -> None:
        """Set output voltage setting"""
        self.write("vout_set", value)

    def get_pid_p_vout(self) -> int:
        """Get PID P parameter for output voltage"""
        return self.read("pid_p_vout")

    def set_pid_p_vout(self, value: int) -> None:
        """Set PID P parameter for output voltage"""
        self.write("pid_p_vout", value)

    def get_pid_i_vout(self) -> int:
        """Get PID I parameter for output voltage"""
        return self.read("pid_i_vout")

    def set_pid_i_vout(self, value: int) -> None:
        """Set PID I parameter for output voltage"""
        self.write("pid_i_vout", value)

    def get_sipm_comp_en(self) -> bool:
        """Get SIPM compensation enable status"""
        return self.read("sipm_comp_en")

    def set_sipm_comp_en(self, value: bool) -> None:
        """Set SIPM compensation enable status"""
        self.write("sipm_comp_en", value)

    def get_sipm_comp_tref(self) -> float:
        """Get SIPM compensation reference temperature"""
        return self.read("sipm_comp_tref")

    def set_sipm_comp_tref(self, value: float) -> None:
        """Set SIPM compensation reference temperature"""
        self.write("sipm_comp_tref", value)

    def get_sipm_comp_ct(self) -> float:
        """Get SIPM compensation temperature coefficient"""
        return self.read("sipm_comp_ct")

    def set_sipm_comp_ct(self, value: float) -> None:
        """Set SIPM compensation temperature coefficient"""
        self.write("sipm_comp_ct", value)

    def get_vout_corr(self) -> float:
        """Get output voltage correction"""
        return self.read("vout_corr")

    def set_vout_corr(self, value: float) -> None:
        """Set output voltage correction"""
        self.write("vout_corr", value)

    def get_led_drv_enable(self) -> bool:
        """Get LED driver enable status"""
        return self.read("led_drv_enable")

    def set_led_drv_enable(self, value: bool) -> None:
        """Set LED driver enable status"""
        self.write("led_drv_enable", value)

    def get_led_drv_period_us(self) -> int:
        """Get LED driver period in microseconds"""
        return self.read("led_drv_period_us")

    def set_led_drv_period_us(self, value: int) -> None:
        """Set LED driver period in microseconds"""
        self.write("led_drv_period_us", value)

    def get_led_drv_duration_ns(self) -> float:
        """Get LED driver duration in nanoseconds"""
        return self.read("led_drv_duration_ns")

    def set_led_drv_duration_ns(self, value: float) -> None:
        """Set LED driver duration in nanoseconds"""
        self.write("led_drv_duration_ns", value)

    def get_led_drv_imod_reg(self) -> int:
        """Get LED driver modulation register value"""
        return self.read("led_drv_imod_reg")

    def set_led_drv_imod_reg(self, value: int) -> None:
        """Set LED driver modulation register value"""
        self.write("led_drv_imod_reg", value)

    def get_led_drv_ibias_reg(self) -> int:
        """Get LED driver bias register value"""
        return self.read("led_drv_ibias_reg")

    def set_led_drv_ibias_reg(self, value: int) -> None:
        """Set LED driver bias register value"""
        self.write("led_drv_ibias_reg", value)

    def get_pass_static(self) -> int:
        """Get pass static value"""
        return self.read("pass_static")

    def set_pass_static(self, value: int) -> None:
        """Set pass static value"""
        self.write("pass_static", value)

    # Input register getters
    def get_hardware_version(self) -> int:
        """Get hardware version"""
        return self.read("hardware_version")

    def get_firmware_version(self) -> int:
        """Get firmware version"""
        return self.read("firmware_version")

    def get_vout_overload(self) -> bool:
        """Get output overload status"""
        return self.read("vout_overload")

    def get_sipm_voltage_10mv(self) -> float:
        """Get SIPM voltage in 10mV units"""
        return self.read("sipm_voltage_10mv")

    def get_sipm_current_ua(self) -> float:
        """Get SIPM current in microamps"""
        return self.read("sipm_current_ua")

    def get_board_temp_adc(self) -> float:
        """Get board temperature from ADC"""
        return self.read("board_temp_adc")

    def get_usb_rx_frames_cnt(self) -> int:
        """Get USB received frames count"""
        return self.read("usb_rx_frames_cnt")

    def get_usb_rx_crc_err_cnt(self) -> int:
        """Get USB received CRC error count"""
        return self.read("usb_rx_crc_err_cnt")

    def get_usb_rx_bad_req_cnt(self) -> int:
        """Get USB received bad request count"""
        return self.read("usb_rx_bad_req_cnt")

    def get_cpu_temp(self) -> float:
        """Get CPU temperature"""
        return self.read("cpu_temp")

    def get_board_temp(self) -> float:
        """Get board temperature"""
        return self.read("board_temp")

    def get_eeprom_error(self) -> int:
        """Get EEPROM error status"""
        return self.read("eeprom_error")

    def get_supply_voltage(self) -> float:
        """Get supply voltage"""
        return self.read("supply_voltage")

    def get_adc_sipm_vout(self) -> float:
        """Get ADC SIPM output voltage"""
        return self.read("adc_sipm_vout")

    def get_sipm_board_temp(self) -> float:
        """Get SIPM board temperature"""
        return self.read("sipm_board_temp")

    def get_sipm_correct_voltage_mv(self) -> int:
        """Get SIPM corrected voltage in millivolts"""
        return self.read("sipm_correct_voltage_mv")

    def get_vout_supply_fault(self) -> bool:
        """Get output supply fault status"""
        return self.read("vout_supply_fault")

    def get_ext_amp_supply_fault(self) -> bool:
        """Get external amplifier supply fault status"""
        return self.read("ext_amp_supply_fault")

    def get_led_drv_temp(self) -> float:
        """Get LED driver temperature"""
        return self.read("led_drv_temp")

    def get_led_drv_status(self) -> int:
        """Get LED driver status"""
        return self.read("led_drv_status")

    def get_vout_ripple(self) -> float:
        """Get output voltage ripple in millivolts"""
        return self.read("vout_ripple")

    def get_pid_saturation(self) -> int:
        """Get PID saturation status"""
        return self.read("pid_saturation")
