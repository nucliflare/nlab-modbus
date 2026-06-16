from nlab_modbus.core.base_modbus_device import BaseModbusDevice
from nlab_modbus.core.enums import DeviceType
from nlab_modbus.core.register_specs import RegisterType, build_register_index, decode_register_block
from nlab_modbus.maps.geiger_map import GEIGER_REGISTER_MAP


class GeigerDevice(BaseModbusDevice):
    """Geiger-Mueller radiation probe controller.

    Generates the detector high voltage (50 – 650 V) via a PWM-driven
    boost converter and counts pulses from the GM tube.  Converts raw
    counts per second to dose rate (mSv/h) and cumulative dose (mSv) using
    a two-stage piecewise polynomial calibration curve stored in holding
    registers.  Also exposes three DAC outputs for external signal processing.

    Hardware version register value: 513 (DeviceType.GEIGER).
    """

    REGISTER_MAP = GEIGER_REGISTER_MAP
    READOUT_START = 3
    READOUT_STOP = 20

    def __init__(
        self,
        client,
        device_id: int,
    ):
        super().__init__(client, device_id)
        self.device_type: DeviceType = DeviceType.GEIGER
        self._register_index = build_register_index(GeigerDevice.REGISTER_MAP)

    def read_snapshot(self) -> dict[str, int | float]:
        """Read the key input registers (addresses 3–19) in one FC04 transaction.

        Skips hardware_version and firmware_version (addresses 0–1) and the
        raw pulse counter (address 2) which overflows frequently and is instead
        tracked via pulses_per_sec.  Returns a dict of name → engineering value.
        """
        count = GeigerDevice.READOUT_STOP - GeigerDevice.READOUT_START
        registers = self.read_raw_block(address=GeigerDevice.READOUT_START, count=count)

        return decode_register_block(
            registers,
            start_address=GeigerDevice.READOUT_START,
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

    def get_dac_vout_mv(self) -> int:
        """Get DAC output voltage in millivolts"""
        return self.read("dac_vout_mv")

    def set_dac_vout_mv(self, value: int) -> None:
        """Set DAC output voltage in millivolts"""
        self.write("dac_vout_mv", value)

    def get_dac_vout_mv_2(self) -> int:
        """Get DAC output voltage 2 in millivolts"""
        return self.read("dac_vout_mv_2")

    def set_dac_vout_mv_2(self, value: int) -> None:
        """Set DAC output voltage 2 in millivolts"""
        self.write("dac_vout_mv_2", value)

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

    def get_dac_vout_mv_3(self) -> int:
        """Get DAC output voltage 3 in millivolts"""
        return self.read("dac_vout_mv_3")

    def set_dac_vout_mv_3(self, value: int) -> None:
        """Set DAC output voltage 3 in millivolts"""
        self.write("dac_vout_mv_3", value)

    def get_scale_coeff_p1_a2(self) -> int:
        """Get scale coefficient P1 A2"""
        return self.read("scale_coeff_p1_a2")

    def set_scale_coeff_p1_a2(self, value: int) -> None:
        """Set scale coefficient P1 A2"""
        self.write("scale_coeff_p1_a2", value)

    def get_scale_exp_p1_a2(self) -> int:
        """Get scale exponent P1 A2"""
        return self.read("scale_exp_p1_a2")

    def set_scale_exp_p1_a2(self, value: int) -> None:
        """Set scale exponent P1 A2"""
        self.write("scale_exp_p1_a2", value)

    def get_scale_coeff_p1_a1(self) -> int:
        """Get scale coefficient P1 A1"""
        return self.read("scale_coeff_p1_a1")

    def set_scale_coeff_p1_a1(self, value: int) -> None:
        """Set scale coefficient P1 A1"""
        self.write("scale_coeff_p1_a1", value)

    def get_scale_exp_p1_a1(self) -> int:
        """Get scale exponent P1 A1"""
        return self.read("scale_exp_p1_a1")

    def set_scale_exp_p1_a1(self, value: int) -> None:
        """Set scale exponent P1 A1"""
        self.write("scale_exp_p1_a1", value)

    def get_scale_coeff_p1_a0(self) -> int:
        """Get scale coefficient P1 A0"""
        return self.read("scale_coeff_p1_a0")

    def set_scale_coeff_p1_a0(self, value: int) -> None:
        """Set scale coefficient P1 A0"""
        self.write("scale_coeff_p1_a0", value)

    def get_scale_exp_p1_a0(self) -> int:
        """Get scale exponent P1 A0"""
        return self.read("scale_exp_p1_a0")

    def set_scale_exp_p1_a0(self, value: int) -> None:
        """Set scale exponent P1 A0"""
        self.write("scale_exp_p1_a0", value)

    def get_scale_coeff_th(self) -> int:
        """Get scale coefficient threshold"""
        return self.read("scale_coeff_th")

    def set_scale_coeff_th(self, value: int) -> None:
        """Set scale coefficient threshold"""
        self.write("scale_coeff_th", value)

    def get_scale_exp_th(self) -> int:
        """Get scale exponent threshold"""
        return self.read("scale_exp_th")

    def set_scale_exp_th(self, value: int) -> None:
        """Set scale exponent threshold"""
        self.write("scale_exp_th", value)

    def get_scale_coeff_p2_a2(self) -> int:
        """Get scale coefficient P2 A2"""
        return self.read("scale_coeff_p2_a2")

    def set_scale_coeff_p2_a2(self, value: int) -> None:
        """Set scale coefficient P2 A2"""
        self.write("scale_coeff_p2_a2", value)

    def get_scale_exp_p2_a2(self) -> int:
        """Get scale exponent P2 A2"""
        return self.read("scale_exp_p2_a2")

    def set_scale_exp_p2_a2(self, value: int) -> None:
        """Set scale exponent P2 A2"""
        self.write("scale_exp_p2_a2", value)

    def get_scale_coeff_p2_a1(self) -> int:
        """Get scale coefficient P2 A1"""
        return self.read("scale_coeff_p2_a1")

    def set_scale_coeff_p2_a1(self, value: int) -> None:
        """Set scale coefficient P2 A1"""
        self.write("scale_coeff_p2_a1", value)

    def get_scale_exp_p2_a1(self) -> int:
        """Get scale exponent P2 A1"""
        return self.read("scale_exp_p2_a1")

    def set_scale_exp_p2_a1(self, value: int) -> None:
        """Set scale exponent P2 A1"""
        self.write("scale_exp_p2_a1", value)

    def get_scale_coeff_p2_a0(self) -> int:
        """Get scale coefficient P2 A0"""
        return self.read("scale_coeff_p2_a0")

    def set_scale_coeff_p2_a0(self, value: int) -> None:
        """Set scale coefficient P2 A0"""
        self.write("scale_coeff_p2_a0", value)

    def get_scale_exp_p2_a0(self) -> int:
        """Get scale exponent P2 A0"""
        return self.read("scale_exp_p2_a0")

    def set_scale_exp_p2_a0(self, value: int) -> None:
        """Set scale exponent P2 A0"""
        self.write("scale_exp_p2_a0", value)

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

    def get_pulses(self) -> int:
        """Get total pulses count"""
        return self.read("pulses")

    def get_pulses_per_sec(self) -> int:
        """Get pulses per second"""
        return int(self.read("pulses_per_sec"))

    def get_dose_level_msvh(self) -> float:
        """Get dose level in mSv/h"""
        return self.read("dose_level_msvh")

    def get_dose_msv(self) -> float:
        """Get dose in mSv"""
        return self.read("dose_msv")

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

    def get_pulse_integer(self) -> int:
        """Get pulse integer value in millivolts"""
        return self.read("pulse_integer")

    def get_gm_supply_fault(self) -> bool:
        """Get GM supply fault status"""
        return self.read("gm_supply_fault")

    def get_pwm_duty(self) -> float:
        """Get PWM duty cycle"""
        return self.read("pwm_duty")

    def get_vout_ripple(self) -> int:
        """Get output voltage ripple in millivolts"""
        return self.read("vout_ripple")

    def get_pwm_cmpss_action(self) -> int:
        """Get PWM CMPSS action status"""
        return self.read("pwm_cmpss_action")

    def get_pid_saturation(self) -> int:
        """Get PID saturation status"""
        return self.read("pid_saturation")
