from pycomm3 import CIPDriver


class OmronNX:

    def __init__(self, ip_address="192.168.250.1"):
        self.ip = ip_address
        self.plc = None

    def connect(self):
        self.plc = CIPDriver(self.ip)
        self.plc.open()

    def disconnect(self):
        if self.plc:
            self.plc.close()

    # ------------------------
    # BOOL
    # ------------------------

    def read_bool(self, tag):
        return bool(self.plc.read(tag).value)

    def write_bool(self, tag, value):
        self.plc.write((tag, bool(value)))

    # ------------------------
    # INT
    # ------------------------

    def read_int(self, tag):
        return int(self.plc.read(tag).value)

    def write_int(self, tag, value):
        self.plc.write((tag, int(value)))

    # ------------------------
    # REAL (FLOAT)
    # ------------------------

    def read_real(self, tag):
        return float(self.plc.read(tag).value)

    def write_real(self, tag, value):
        self.plc.write((tag, float(value)))

    # ------------------------
    # ARRAY
    # ------------------------

    def read_array(self, tag):
        return self.plc.read(tag).value

    def write_array(self, tag, values):
        self.plc.write((tag, values))

    # ------------------------
    # GENERICO
    # ------------------------

    def read(self, tag):
        return self.plc.read(tag).value

    def write(self, tag, value):
        self.plc.write((tag, value))