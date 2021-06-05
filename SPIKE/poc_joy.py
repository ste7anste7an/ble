# This example demonstrates a UART periperhal.

from spike import PrimeHub
from spike import Motor
from hub import led, display, Image
    # Do something
hubprime = PrimeHub()
#import hub

def light(n):
    x=n%5
    y=n//5
    hubprime.light_matrix.set_pixel(x, y)

_CONNECT_IMG_1 = Image('00000:09000:09000:09000:00000')
_CONNECT_IMG_2 = Image('00000:00900:00900:00900:00000')
_CONNECT_IMG_3 = Image('00000:00090:00090:00090:00000')

_COMPLETE_IMG = Image('00000:05550:05950:05550:00000')

_CONNECT_PARENT_SEARCH_IMG = Image('00055:00005:00005:00005:00055')
_CONNECT_CHILDREN_SEARCH_IMG = Image('55000:50000:50000:50000:55000')

_CONNECT_PARENT_FOUND_IMG = Image('00099:00009:00009:00009:00099')
_CONNECT_CHILDREN_FOUND_IMG = Image('99000:90000:90000:90000:99000')

_CONNECT_ANIMATION_P_S = [_CONNECT_IMG_1+_CONNECT_PARENT_SEARCH_IMG,
                        _CONNECT_IMG_2+_CONNECT_PARENT_SEARCH_IMG,
                        _CONNECT_IMG_3+_CONNECT_PARENT_SEARCH_IMG]

_CONNECT_ANIMATION_C_S = [_CONNECT_IMG_1+_CONNECT_CHILDREN_SEARCH_IMG,
                        _CONNECT_IMG_2+_CONNECT_CHILDREN_SEARCH_IMG,
                        _CONNECT_IMG_3+_CONNECT_CHILDREN_SEARCH_IMG]

_CONNECT_ANIMATION_CP_SS = [_CONNECT_IMG_1+_CONNECT_CHILDREN_SEARCH_IMG+_CONNECT_PARENT_SEARCH_IMG,
                        _CONNECT_IMG_2+_CONNECT_CHILDREN_SEARCH_IMG+_CONNECT_PARENT_SEARCH_IMG,
                        _CONNECT_IMG_3+_CONNECT_CHILDREN_SEARCH_IMG+_CONNECT_PARENT_SEARCH_IMG]

_CONNECT_ANIMATION_CP_SF = [_CONNECT_IMG_1+_CONNECT_CHILDREN_SEARCH_IMG+_CONNECT_PARENT_FOUND_IMG,
                        _CONNECT_IMG_2+_CONNECT_CHILDREN_SEARCH_IMG+_CONNECT_PARENT_FOUND_IMG,
                        _CONNECT_IMG_3+_CONNECT_CHILDREN_SEARCH_IMG+_CONNECT_PARENT_FOUND_IMG]

_CONNECT_ANIMATION_CP_FS = [_CONNECT_IMG_1+_CONNECT_CHILDREN_FOUND_IMG+_CONNECT_PARENT_SEARCH_IMG,
                        _CONNECT_IMG_2+_CONNECT_CHILDREN_FOUND_IMG+_CONNECT_PARENT_SEARCH_IMG,
                        _CONNECT_IMG_3+_CONNECT_CHILDREN_FOUND_IMG+_CONNECT_PARENT_SEARCH_IMG]



import bluetooth
import random
import struct
import time
from time import sleep_ms
#from ble_advertising import advertising_payload

# Helpers for generating BLE advertising payloads.

from micropython import const
import struct
import bluetooth

# Advertising payloads are repeated packets of the following form:
#1 byte data length (N + 1)
#1 byte type (see constants below)
#N bytes type-specific data

_ADV_TYPE_FLAGS = const(0x01)
_ADV_TYPE_NAME = const(0x09)
_ADV_TYPE_UUID16_COMPLETE = const(0x3)
_ADV_TYPE_UUID32_COMPLETE = const(0x5)
_ADV_TYPE_UUID128_COMPLETE = const(0x7)
_ADV_TYPE_UUID16_MORE = const(0x2)
_ADV_TYPE_UUID32_MORE = const(0x4)
_ADV_TYPE_UUID128_MORE = const(0x6)
_ADV_TYPE_APPEARANCE = const(0x19)


# Generate a payload to be passed to gap_advertise(adv_data=...).
def advertising_payload(limited_disc=False, br_edr=False, name=None, services=None, appearance=0):
    payload = bytearray()

    def _append(adv_type, value):
        nonlocal payload
        payload += struct.pack("BB", len(value) + 1, adv_type) + value

    _append(
        _ADV_TYPE_FLAGS,
        struct.pack("B", (0x01 if limited_disc else 0x02) + (0x18 if br_edr else 0x04)),
    )

    if name:
        _append(_ADV_TYPE_NAME, name)

    if services:
        for uuid in services:
            b = bytes(uuid)
            if len(b) == 2:
                _append(_ADV_TYPE_UUID16_COMPLETE, b)
            elif len(b) == 4:
                _append(_ADV_TYPE_UUID32_COMPLETE, b)
            elif len(b) == 16:
                _append(_ADV_TYPE_UUID128_COMPLETE, b)

    # See org.bluetooth.characteristic.gap.appearance.xml
    if appearance:
        _append(_ADV_TYPE_APPEARANCE, struct.pack("<h", appearance))

    return payload


def decode_field(payload, adv_type):
    i = 0
    result = []
    while i + 1 < len(payload):
        if payload[i + 1] == adv_type:
            result.append(payload[i + 2 : i + payload[i] + 1])
        i += 1 + payload[i]
    return result


def decode_name(payload):
    n = decode_field(payload, _ADV_TYPE_NAME)
    return str(n[0], "utf-8") if n else ""


def decode_services(payload):
    services = []
    for u in decode_field(payload, _ADV_TYPE_UUID16_COMPLETE):
        services.append(bluetooth.UUID(struct.unpack("<h", u)[0]))
    for u in decode_field(payload, _ADV_TYPE_UUID32_COMPLETE):
        services.append(bluetooth.UUID(struct.unpack("<d", u)[0]))
    for u in decode_field(payload, _ADV_TYPE_UUID128_COMPLETE):
        services.append(bluetooth.UUID(u))
    return services


from micropython import const

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
#_IRQ_GATTS_WRITE = const(3)
_IRQ_GATTS_WRITE =            const(1<<2)
_FLAG_READ = const(0x0002)
_FLAG_WRITE_NO_RESPONSE = const(0x0004)
_FLAG_WRITE = const(0x0008)
_FLAG_NOTIFY = const(0x0010)

_UART_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
_UART_TX = (
    bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E"),
    _FLAG_READ | _FLAG_NOTIFY,
)
_UART_RX = (
    bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E"),
    _FLAG_WRITE | _FLAG_WRITE_NO_RESPONSE,
)
_UART_SERVICE = (
    _UART_UUID,
    (_UART_TX, _UART_RX),
)


class BLESimplePeripheral:
    def __init__(self, ble, name="spike"):
        self._n=12
        self._x=100
        self._y=100
        self._ble = ble
        self._ble.active(True)
        self._ble.irq(self._irq)
        ((self._handle_tx, self._handle_rx),) = self._ble.gatts_register_services((_UART_SERVICE,))
        self._connections = set()
        self._connected=False
        self._write_callback = None
        self._payload = advertising_payload(name=name, services=[_UART_UUID])
        self._advertise()

    def _irq(self, event, data):
        # Track connections so we can send notifications.
        #print("event",event)
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            print("New connection", conn_handle)
            self._connections.add(conn_handle)
            self._connected=True
            self._update_animation()
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            print("Disconnected", conn_handle)
            self._connections.remove(conn_handle)
            self._connected=False
            self._update_animation()
            # Start advertising again to allow a new connection.
            self._advertise()
        elif event == _IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            #print("WRITE",data)
            value = self._ble.gatts_read(value_handle)
            #print("value=",value)
            if value_handle == self._handle_rx and self._write_callback:
                self._write_callback(value)

    def send(self, data):
        for conn_handle in self._connections:
            self._ble.gatts_notify(conn_handle, self._handle_tx, data)

    def is_connected(self):
        return len(self._connections) > 0

    def _advertise(self, interval_us=100000):
        print("Starting advertising")
        self._ble.gap_advertise(interval_us, adv_data=self._payload)

    def on_write(self, callback):
        self._write_callback = callback

    def _update_animation(self):
        if not self._connected:
            display.show(_CONNECT_ANIMATION_C_S, delay=100, wait=False, loop=True)
        else:
            display.show(_COMPLETE_IMG+_CONNECT_CHILDREN_FOUND_IMG)

def demo():
    ble = bluetooth.BLE()
    p = BLESimplePeripheral(ble)
    p._update_animation()

    def on_rx(v):
        #print("RX", v)
        if v[0]==88:
            x=v[1]
            y=v[2]
            #print("x,y=",x,y)
            ax=int(y/200.*5)
            ay=int(x/200.*5)
            if p._x!=ax or p._y!=ay:
                hubprime.light_matrix.set_pixel(p._y%5, p._x%5,brightness=0)
                p._x=ax
                p._y=ay
            hubprime.light_matrix.set_pixel(ay%5, ax%5)
        #light(p._n)

    p.on_write(on_rx)

    i = 0
    clear=False
    while True:
        if p.is_connected():
            if clear==False:
                hubprime.light_matrix.off()
                clear=True

            # Short burst of queued notifications.
            for _ in range(1):
                data = str(i) + "_"
                #print("TX", data)
                p.send(data)
                i += 1
        time.sleep_ms(300)
        

demo()