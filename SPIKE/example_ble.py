import utime
import ubluetooth
import ubinascii
import struct
from micropython import const

_IRQ_CENTRAL_CONNECT = const(1 << 0)
_IRQ_CENTRAL_DISCONNECT = const(1 << 1)
_IRQ_GATTS_WRITE = const(1 << 2)
_IRQ_GATTS_READ_REQUEST = const(1 << 3)
_IRQ_SCAN_RESULT = const(1 << 4)
_IRQ_SCAN_COMPLETE = const(1 << 5)
_IRQ_PERIPHERAL_CONNECT = const(1 << 6)
_IRQ_PERIPHERAL_DISCONNECT = const(1 << 7)
_IRQ_GATTC_SERVICE_RESULT = const(1 << 8)
_IRQ_GATTC_CHARACTERISTIC_RESULT = const(1 << 9)
_IRQ_GATTC_DESCRIPTOR_RESULT = const(1 << 10)
_IRQ_GATTC_READ_RESULT = const(1 << 11)
_IRQ_GATTC_WRITE_STATUS = const(1 << 12)
_IRQ_GATTC_NOTIFY = const(1 << 13)
_IRQ_GATTC_INDICATE = const(1 << 14)

_IRQ_GATTC_SERVICE_DONE = const(10)


_ADV_TYPE_UUID16_COMPLETE = const(0x3)
_ADV_TYPE_UUID32_COMPLETE = const(0x5)
_ADV_TYPE_UUID128_COMPLETE = const(0x7)

_COMPANY_IDENTIFIER_CODES = {
    "0397": "LEGO System A/S"
}

_LEGO_SERVICE_UUID = ubluetooth.UUID("00001623-1212-EFDE-1623-785FEABCD123")
_LEGO_SERVICE_CHAR = ubluetooth.UUID("00001624-1212-EFDE-1623-785FEABCD123")

class PowerUPRemote:
    """Class to deal with LEGO(R) PowerUp(TM) Remote Control for Spike Prime"""

    def __init__(self):
        self._ble = ubluetooth.BLE()
        self._ble.active(True)
        self._ble.irq(handler=self._irq)
        self._decoder = Decoder()
        self._reset()

    def _reset(self):
        self._addr = None
        self._addr_type = None
        self._adv_type = None
        self._services = None
        self._man_data = None
        self._name = None
        self._conn = None
        self._value = None

    # start scan for ble devices
    def scan_start(self, timeout):
        self._ble.gap_scan(timeout, 30000, 30000)

    # stop current scan
    def scan_stop(self):
        self._ble.gap_scan(None)

    # connect to ble device
    def connect(self, addr_type, addr):
        self._ble.gap_connect(addr_type, addr)

    # disconnect from ble device
    def disconnect(self):
        if not self._conn:
            return
        self._ble.gap_disconnect(1025)
        self._reset()

    def read(self):
        self._ble.gattc_read(self._conn, self._value)

    # ble event handler
    def _irq(self, event, data):
        # called for every result of a ble scan
        if event == _IRQ_SCAN_RESULT:
            addr_type, addr, adv_type, rssi, adv_data = data
            self._addr_type = addr_type
            self._addr = bytes(addr)
            self._adv_type = adv_type
            self._name = self._decoder.decode_name(adv_data)
            self._services = self._decoder.decode_services(adv_data)
            self._man_data = self._decoder.decode_manufacturer(adv_data)

        # called after a ble scan is finished
        elif event == _IRQ_SCAN_COMPLETE:
            print("scan finished!")

        # called if a peripheral device is connected
        elif event == _IRQ_PERIPHERAL_CONNECT:
            print("connected peripheral device")
            conn, addr_type, addr = data
            self._conn = conn
            self._ble.gattc_discover_services(self._conn)

        # called if a peripheral device is disconnected
        elif event == _IRQ_PERIPHERAL_DISCONNECT:
            conn, _, _ = data
            print("disconnected peripheral device")

        elif event == _IRQ_GATTC_SERVICE_RESULT:
            # Connected device returned a service.
            conn, start_handle, end_handle, uuid = data
            print("service", data, "uuid", uuid, "Conn", conn)
            if conn == self._conn and uuid == _LEGO_SERVICE_UUID:
                self._ble.gattc_discover_characteristics(self._conn, start_handle, end_handle)

        elif event == _IRQ_GATTC_CHARACTERISTIC_RESULT:
            # Connected device returned a characteristic.
            conn, def_handle, value_handle, properties, uuid = data
            print("Got Charachterisitic", uuid, value_handle)
            if conn == self._conn and uuid == _LEGO_SERVICE_CHAR:
                self._value = value_handle

        elif event == _IRQ_GATTC_READ_RESULT:
            # A read completed successfully.
            conn_handle, value_handle, char_data = data
            print("Got Data Read", data, ubinascii.hexlify(char_data))

        # called on notification
        elif event == _IRQ_GATTC_NOTIFY:
            conn, value_handle, notify_data = data
            print("Notification")


class Decoder:
    """Class to decode BLE adv_data"""

    def decode_manufacturer(self, payload):
        man_data = []
        n = self._decode_field(payload, const(0xff))
        if not n:
            return []
        company_identifier = ubinascii.hexlify(struct.pack('<h', *struct.unpack('>h', n[0])))
        company_name = _COMPANY_IDENTIFIER_CODES.get(company_identifier.decode(), "?")
        company_data = ubinascii.hexlify(n[0][2:])
        man_data.append(company_identifier.decode())
        man_data.append(company_name)
        man_data.append(company_data)
        return man_data

    def decode_name(self, payload):
        n = self._decode_field(payload, const(0x09))
        return str(n[0], "utf-8") if n else "parsing failed!"

    def decode_services(self, payload):
        services = []
        for u in self._decode_field(payload, _ADV_TYPE_UUID16_COMPLETE):
            services.append(ubluetooth.UUID(struct.unpack("<h", u)[0]))
        for u in self._decode_field(payload, _ADV_TYPE_UUID32_COMPLETE):
            services.append(ubluetooth.UUID(struct.unpack("<d", u)[0]))
        for u in self._decode_field(payload, _ADV_TYPE_UUID128_COMPLETE):
            services.append(ubluetooth.UUID(u))
        return services

    def _decode_field(self, payload, adv_type):
        i = 0
        result = []
        while i + 1 < len(payload):
            if payload[i + 1] == adv_type:
                result.append(payload[i + 2: i + payload[i] + 1])
            i += 1 + payload[i]
        return result


remote = PowerUPRemote()
remote.connect(0, b'\x00\x81\xf9\xea\xc1\x9f')
utime.sleep(10)
print("Start Read")
while True:
    remote.read()
    utime.sleep(0.100)
#remote.disconnect()