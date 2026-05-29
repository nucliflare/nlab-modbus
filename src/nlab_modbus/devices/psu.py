from nlab_modbus.core.base_modbus_device import BaseModbusDevice
from nlab_modbus.core.enums import DeviceType
from nlab_modbus.core.register_specs import RegisterType, build_register_index, decode_register_block
from nlab_modbus.maps.psu_map import PSU_REGISTER_MAP


class PSUDevice(BaseModbusDevice):
    REGISTER_MAP = PSU_REGISTER_MAP
    READOUT_START = 3
    READOUT_STOP = 16

    def __init__(self, client, device_id: int):
        super().__init__(client, device_id)
        self.device_type: DeviceType = DeviceType.PSU
        self._register_index = build_register_index(PSUDevice.REGISTER_MAP)

    def read_snapshot(self) -> dict[str, int | float]:
        count = PSUDevice.READOUT_STOP - PSUDevice.READOUT_START
        registers = self.read_raw_block(address=PSUDevice.READOUT_START, count=count)

        return decode_register_block(
            registers,
            start_address=PSUDevice.READOUT_START,
            register_type=RegisterType.INPUT,
            register_index=self._register_index,
        )

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

    def set_rs485_baud(self, value: float) -> None:
        """Set RS485 baud rate"""
        self.write("rs485_baud", value)

    def get_pwm_enable(self) -> bool:
        """Get PWM enable status"""
        return self.read("pwm_enable")

    def set_pwm_enable(self, value: bool) -> None:
        """Set PWM enable status"""
        self.write("pwm_enable", value)

    def get_pwm_set_voltage(self) -> float:
        """Get PWM set voltage"""
        return self.read("pwm_set_voltage")

    def set_pwm_set_voltage(self, value: float) -> None:
        """Set PWM set voltage"""
        self.write("pwm_set_voltage", value)

    def get_pwm_freq_khz(self) -> float:
        """Get PWM frequency in kHz"""
        return self.read("pwm_freq_khz")

    def set_pwm_freq_khz(self, value: float) -> None:
        """Set PWM frequency in kHz"""
        self.write("pwm_freq_khz", value)

    def get_pwm_max_duty(self) -> float:
        """Get PWM maximum duty cycle"""
        return self.read("pwm_max_duty")

    def set_pwm_max_duty(self, value: float) -> None:
        """Set PWM maximum duty cycle"""
        self.write("pwm_max_duty", value)

    def get_pwm_outvolt_comp(self) -> float:
        """Get PWM output voltage compensation"""
        return self.read("pwm_outvolt_comp")

    def set_pwm_outvolt_comp(self, value: float) -> None:
        """Set PWM output voltage compensation"""
        self.write("pwm_outvolt_comp", value)

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

    def get_adc_freq_khz(self) -> float:
        """Get ADC frequency in kHz"""
        return self.read("adc_freq_khz")

    def set_adc_freq_khz(self, value: float) -> None:
        """Set ADC frequency in kHz"""
        self.write("adc_freq_khz", value)

    def get_adc_filter_coeff(self) -> int:
        """Get ADC filter coefficient"""
        return self.read("adc_filter_coeff")

    def set_adc_filter_coeff(self, value: int) -> None:
        """Set ADC filter coefficient"""
        self.write("adc_filter_coeff", value)

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

    def get_hv_voltage(self) -> float:
        """Get high voltage"""
        return self.read("hv_voltage")

    def get_pwm_duty(self) -> float:
        """Get PWM duty cycle"""
        return self.read("pwm_duty")

    def get_hv_current(self) -> float:
        """Get high voltage current in microamps"""
        return self.read("hv_current")

    def get_vout_ripple(self) -> float:
        """Get output voltage ripple in millivolts"""
        return self.read("vout_ripple")

    def get_pwm_cmpss_action(self) -> int:
        """Get PWM CMPSS action status"""
        return self.read("pwm_cmpss_action")

    def get_pid_saturation(self) -> int:
        """Get PID saturation status"""
        return self.read("pid_saturation")

    def get_pmt_temp(self) -> float:
        """Get PMT temperature"""
        return self.read("pmt_temp")
