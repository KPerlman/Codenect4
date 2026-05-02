import time
import adafruit_tcs34725

try:
    from adafruit_extended_bus import ExtendedI2C
except ImportError:
    ExtendedI2C = None

try:
    from smbus2 import SMBus
except ImportError:
    SMBus = None


class TCS34725Raw:
    ADDRESS = 0x29
    COMMAND = 0x80

    REG_ENABLE = 0x00
    REG_ATIME = 0x01
    REG_CONTROL = 0x0F
    REG_CDATAL = 0x14
    REG_RDATAL = 0x16
    REG_GDATAL = 0x18
    REG_BDATAL = 0x1A

    def __init__(self, busnum, integration_time_ms=100, gain=4):
        if SMBus is None:
            raise RuntimeError("smbus2 is required for software I2C")
        self.bus = SMBus(busnum)
        self._write8(self.REG_ENABLE, 0x03)
        self._write8(self.REG_ATIME, self._atime_from_ms(integration_time_ms))
        self._write8(self.REG_CONTROL, self._gain_to_reg(gain))
        time.sleep(0.01)

    def _write8(self, reg, value):
        self.bus.write_byte_data(self.ADDRESS, self.COMMAND | reg, value)

    def _read16(self, reg):
        low = self.bus.read_byte_data(self.ADDRESS, self.COMMAND | reg)
        high = self.bus.read_byte_data(self.ADDRESS, self.COMMAND | (reg + 1))
        return (high << 8) | low

    def _atime_from_ms(self, ms):
        atime = int(256 - (ms / 2.4))
        return max(0, min(255, atime))

    def _gain_to_reg(self, gain):
        if gain == 1:
            return 0x00
        if gain == 4:
            return 0x01
        if gain == 16:
            return 0x02
        if gain == 60:
            return 0x03
        return 0x01

    @property
    def color_raw(self):
        c = self._read16(self.REG_CDATAL)
        r = self._read16(self.REG_RDATAL)
        g = self._read16(self.REG_GDATAL)
        b = self._read16(self.REG_BDATAL)
        return (r, g, b, c)

    @property
    def color_rgb_bytes(self):
        r, g, b, _ = self.color_raw
        return (min(255, r >> 8), min(255, g >> 8), min(255, b >> 8))


def open_tcs34725(busnum, integration_time_ms=100, gain=4):
    if ExtendedI2C is not None:
        try:
            sensor = adafruit_tcs34725.TCS34725(ExtendedI2C(busnum))
            sensor.integration_time = integration_time_ms
            sensor.gain = gain
            return sensor
        except Exception:
            pass

    if SMBus is not None:
        return TCS34725Raw(busnum, integration_time_ms, gain)

    raise RuntimeError("Install adafruit-extended-bus or smbus2")
