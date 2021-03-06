# This example finds and connects to a peripheral running the
# UART service (e.g. ble_simple_peripheral.py).
from spike import PrimeHub
from spike import Motor

    # Do something
hub = PrimeHub()


import bluetooth
import random
import struct
import time
import micropython
import ubinascii


def light(n):
    x=n%5
    y=n//5
    hub.light_matrix.set_pixel(x, y)


from micropython import const




_IRQ_CENTRAL_CONNECT                = const(1 << 0)
_IRQ_CENTRAL_DISCONNECT            = const(1 << 1)
_IRQ_GATTS_WRITE                    = const(1 << 2)
_IRQ_GATTS_READ_REQUEST            = const(1 << 3)
_IRQ_SCAN_RESULT                    = const(1 << 4)
_IRQ_SCAN_DONE                    = const(1 << 5)
_IRQ_PERIPHERAL_CONNECT            = const(1 << 6)
_IRQ_PERIPHERAL_DISCONNECT        = const(1 << 7)
_IRQ_GATTC_SERVICE_RESULT            = const(1 << 8)
_IRQ_GATTC_CHARACTERISTIC_RESULT    = const(1 << 9)
_IRQ_GATTC_DESCRIPTOR_RESULT        = const(1 << 10)
_IRQ_GATTC_READ_RESULT            = const(1 << 11)
_IRQ_GATTC_WRITE_STATUS            = const(1 << 12)
_IRQ_GATTC_NOTIFY                    = const(1 << 13)
_IRQ_GATTC_INDICATE                = const(1 << 14)

_IRQ_GATTC_SERVICE_DONE = const(10)

_ADV_IND = const(0x00)
_ADV_DIRECT_IND = const(0x01)
_ADV_SCAN_IND = const(0x02)
_ADV_NONCONN_IND = const(0x03)

_NOTIFY_ENABLE = const(1)
_INDICATE_ENABLE = const(2)


_ACC_SERVICE_UUID =    bluetooth.UUID("E95D0753-251D-470A-A062-FA1922DFA9A8")
_ACC_DATA_UUID =       bluetooth.UUID("E95DCA4B-251D-470A-A062-FA1922DFA9A8")
_ACC_DESCR_UUID=       bluetooth.UUID(0x2902)

_BUTTON_SERVICE_UUID = bluetooth.UUID("E95D9882-251D-470A-A062-FA1922DFA9A8")

_BUTTON_A_STATE_UUID = bluetooth.UUID("E95DDA90-251D-470A-A062-FA1922DFA9A8")
_BUTTON_B_STATE_UUID = bluetooth.UUID("E95DDA91-251D-470A-A062-FA1922DFA9A8")

_LED_SERVICE_UUID =    bluetooth.UUID("E95DD91D-251D-470A-A062-FA1922DFA9A8")
_LED_MATRIX_UUID =     bluetooth.UUID("E95D7B77-251D-470A-A062-FA1922DFA9A8")
_LED_TEXT_UUID =       bluetooth.UUID("E95D93EE-251D-470A-A062-FA1922DFA9A8")
_LED_DELAY_UUID =      bluetooth.UUID("E95D0D2D-251D-470A-A062-FA1922DFA9A8")


"""
public static String ACCELEROMETERSERVICE_SERVICE_UUID = "E95D0753251D470AA062FA1922DFA9A8";
public static String ACCELEROMETERDATA_CHARACTERISTIC_UUID = "E95DCA4B251D470AA062FA1922DFA9A8";
public static String ACCELEROMETERPERIOD_CHARACTERISTIC_UUID = "E95DFB24251D470AA062FA1922DFA9A8";
"""
MAC_MICRO=b'\xFA\x35\x2F\x6C\x13\xf8'


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







class BLESimpleCentral:
    def __init__(self, ble):
        self._ble = ble
        self._ble.active(True)
        self._ble.irq(self._irq)

        self._reset()

    def _reset(self):
        # Cached name and address from a successful scan.
        self._name = None
        self._addr_type = None
        self._addr = None

        # Callbacks for completion of various operations.
        # These reset back to None after being invoked.
        self._scan_callback = None
        self._conn_callback = None
        self._read_callback = None

        # Persistent callback for when new data is notified from the device.
        self._notify_callback = None

        # Connected device.
        self._conn_handle = None
        self._start_handle = None
        self._end_handle = None
        self._tx_handle = None
        self._rx_handle = None
        self._acc_handle = None
        self._buta_handle = None
        self._butb_handle = None
        self._led_matrix_handle = None
        self._led_text_handle = None
        self._led_delay_handle = None
        self._n=0

    def _irq(self, event, data):
        # if eventin (_IRQ_PERIPHERAL_DISCONNECT,
        #                _IRQ_GATTC_CHARACTERISTIC_RESULT,_IRQ_GATTC_DESCRIPTOR_RESULT,_IRQ_GATTC_READ_RESULT,_IRQ_GATTC_WRITE_STATUS,
        #                _IRQ_GATTC_NOTIFY):
        #    print("event:",event, hex(event))
        if event in (_IRQ_GATTC_SERVICE_DONE,_IRQ_GATTC_WRITE_STATUS):
            print("event:",event, hex(event))

        if event == _IRQ_SCAN_RESULT:
            addr_type, addr, adv_type, rssi, adv_data = data
            if addr == MAC_MICRO:
                #print('type:{} addr:{} adv_type: {} rssi:{} data:{}'.format(addr_type, ubinascii.hexlify(addr), adv_type,rssi,ubinascii.hexlify(adv_data)))
                #print("service",decode_services(adv_data))
                # if adv_type in (_ADV_IND, _ADV_DIRECT_IND) and _ACC_SERVICE_UUID in decode_services(
                #    adv_data
                # ):
                # Found a potential device, remember it and stop scanning.
                self._addr_type = addr_type
                self._addr = bytes(
                    addr
                )# Note: addr buffer is owned by caller so need to copy it.
                self._name = decode_name(adv_data) or "?"
                self._ble.gap_scan(None)

        elif event == _IRQ_SCAN_DONE:
            if self._scan_callback:
                if self._addr:
                    # Found a device during the scan (and the scan was explicitly stopped).
                    self._scan_callback(self._addr_type, self._addr, self._name)
                    self._scan_callback = None
                else:
                    # Scan timed out.
                    self._scan_callback(None, None, None)

        elif event == _IRQ_PERIPHERAL_CONNECT:
            # Connect successful.
            conn_handle, addr_type, addr = data
            if addr_type == self._addr_type and addr == self._addr:
                self._conn_handle = conn_handle
                self._ble.gattc_discover_services(self._conn_handle)

        elif event == _IRQ_PERIPHERAL_DISCONNECT:
            # Disconnect (either initiated by us or the remote end).
            conn_handle, _, _ = data
            if conn_handle == self._conn_handle:
                # If it was initiated by us, it'll already be reset.
                self._reset()
                print("disconnected")

        elif event == _IRQ_GATTC_SERVICE_RESULT:
            # Connected device returned a service.
            conn_handle, start_handle, end_handle, uuid = data
            #print("service", data)
            light(self._n)
            self._n+=1
            if conn_handle == self._conn_handle and uuid == _ACC_SERVICE_UUID:
                self._start_handle, self._end_handle = start_handle, end_handle
                #print("service",data)
                self._ble.gattc_discover_characteristics(self._conn_handle, 35,48)
                #self._ble.gattc_discover_characteristics(self._conn_handle, start_handle, end_handle)
            if conn_handle == self._conn_handle and uuid == _BUTTON_SERVICE_UUID:
                self._start_handle, self._end_handle = start_handle, end_handle
                #print("service",data)
                #self._ble.gattc_discover_characteristics(self._conn_handle, start_handle, end_handle)
            if conn_handle == self._conn_handle and uuid == _LED_SERVICE_UUID:
                self._start_handle, self._end_handle = start_handle, end_handle
                #print("service",data)
                #self._ble.gattc_discover_characteristics(self._conn_handle, start_handle, end_handle)
                self._n+=1
                self._ble.gattc_discover_characteristics(self._conn_handle, 5, 100)

        elif event == _IRQ_GATTC_SERVICE_DONE:
            #print("service_done")
            # Service query complete.
            if self._start_handle and self._end_handle:
                self._ble.gattc_discover_characteristics(
                    self._conn_handle, self._start_handle, self._end_handle
                )
            else:
                print("Failed to find uart service.")

        elif event == _IRQ_GATTC_CHARACTERISTIC_RESULT:
            light(self._n)
            self._n+=1
            # Connected device returned a characteristic.
            conn_handle, def_handle, value_handle, properties, uuid = data
            #print('gattc_char',data)
            if conn_handle == self._conn_handle:
                if uuid == _ACC_DATA_UUID:
                    self._rx_handle = value_handle
                elif uuid == _BUTTON_A_STATE_UUID:
                    #print("buta state")
                    self._buta_handle = value_handle
                elif uuid == _BUTTON_B_STATE_UUID:
                    self._butb_handle = value_handle
                    #print("butb state")
                elif uuid == _LED_MATRIX_UUID:
                    #print(uuid)
                    self._led_matrix_handle = value_handle
                elif uuid == _LED_TEXT_UUID:
                    self._led_text_handle = value_handle
                elif uuid == _LED_DELAY_UUID:
                    self._led_delay_handle = value_handle

                #print("_IRQ_GATTC_CHARACTERISTIC_RESULT, handle",value_handle)
                #self._ble.gattc_discover_descriptors(conn_handle, def_handle, value_handle)
                #self._ble.gatts_notify(conn_handle, value_handle )
            # if conn_handle == self._conn_handle and uuid == _UART_TX_CHAR_UUID:
            #    self._tx_handle = value_handle

        # elif event == _IRQ_GATTC_CHARACTERISTIC_DONE:
        #    # Characteristic query complete.
        #    #if self._tx_handle is not None and self._rx_handle is not None:
        #    if self._rx_handle is not None:
        #        # We've finished connecting and discovering device, fire the connect callback.
        #        print("CHARACTERISTIC_DONE")
        #        self._ble.gattc_discover_descriptors(self._conn_handle, self._start_handle, self._end_handle)

        #        if self._conn_callback:
        #            self._conn_callback()
        #    else:
        #        print("Failed to find uart rx characteristic.")

        elif event == _IRQ_GATTC_DESCRIPTOR_RESULT:
            # Connected device returned a descriptor.
            conn_handle,value_handle, uuid = data
            #print('desciptor_result',data)
            if conn_handle == self._conn_handle and uuid == _ACC_DESCR_UUID:
                #print("set acc_handle",value_handle)
                self._acc_handle = value_handle

        # elif event == _IRQ_GATTC_DESCRIPTOR_DONE:
        #    print('descriptor done',data)

        # elif event == _IRQ_GATTC_WRITE_DONE:
        #    conn_handle, value_handle, status = data
        #    print("TX complete")

        elif event == _IRQ_GATTC_NOTIFY:
            #print("_IRQ_GATTC_NOTIFY")
            conn_handle, value_handle, notify_data = data
            notify_data=bytes(notify_data)
            #print("data:",notify_data)

            if conn_handle == self._conn_handle and value_handle == self._rx_handle:
                if self._notify_callback:
                    self._notify_callback(value_handle,bytes(notify_data))

        elif event == _IRQ_GATTC_READ_RESULT:
            #print("_IRQ_GATTC_READ_RESULT")
            # A read completed successfully.
            conn_handle, value_handle, char_data = data
            if conn_handle == self._conn_handle and value_handle in (self._rx_handle,self._buta_handle,self._butb_handle):
                #print("handle,READ data",value_handle,bytes(char_data))
                self._read_callback(value_handle,bytes(char_data))

        # elif event == _IRQ_GATTC_READ_DONE:
        #    print("_IRQ_GATTC_READ_DONE")
        #    # Read completed (no-op).
        #    conn_handle, value_handle, status = data

    # Returns true if we've successfully connected and discovered characteristics.
    def is_connected(self):
        return (
            self._conn_handle is not None
            #and self._tx_handle is not None
            and self._rx_handle is not None
            #and self._acc_handle is not None
        )

    # Find a device advertising the environmental sensor service.
    def scan(self, callback=None):
        self._addr_type = None
        self._addr = None
        self._scan_callback = callback
        self._ble.gap_scan(20000, 30000, 30000)

    # Connect to the specified device (otherwise use cached address from a scan).
    def connect(self, addr_type=None, addr=None, callback=None):
        self._addr_type = addr_type or self._addr_type
        self._addr = addr or self._addr
        self._conn_callback = callback
        if self._addr_type is None or self._addr is None:
            return False
        self._ble.gap_connect(self._addr_type, self._addr)
        return True

    # Disconnect from current device.
    def disconnect(self):
        if not self._conn_handle:
            return
        self._ble.gap_disconnect(self._conn_handle)
        self._reset()

    # Send data over the UART
    def write(self, handle, v, response=False):
        if not self.is_connected():
            return
        self._ble.gattc_write(self._conn_handle, handle, v, 1 if response else 0)

    def enable_notify(self):
        if not self.is_connected():
            return
        print("enable notify")
        #self._ble.gattc_write(self._conn_handle, self._acc_handle, struct.pack('<h', _NOTIFY_ENABLE), 0)
        for i in range(38,49):
            self._ble.gattc_write(self._conn_handle, i, struct.pack('<h', _NOTIFY_ENABLE), 0)
            time.sleep_ms(50)
        print("notified enabled")
    def read(self,handle,callback):
        if not self.is_connected():
            return
        self._read_callback = callback
        try:
            self._ble.gattc_read(self._conn_handle, handle)
        except:
            pass
            #print("gattc_read failed")


    # Set handler for when data is received over the UART.
    def on_notify(self, callback):
        self._notify_callback = callback


#motor_drive = Motor("B")
#motor_steer = Motor("A")

def demo():
    print("starting BLE")
    ble = bluetooth.BLE()
    central = BLESimpleCentral(ble)

    not_found = False

    def on_scan(addr_type, addr, name):
        if addr_type is not None:
            print("Found peripheral:", addr_type, addr, name)
            central.connect()
        else:
            nonlocal not_found
            not_found = True
            print("No peripheral found.")
    print("start scanning")
    central.scan(callback=on_scan)

    # Wait for connection...
    while not central.is_connected():
        time.sleep_ms(100)
        if not_found:
            return

    print("Connected")

    def on_rx(handle,v):
        if handle == central._rx_handle:
            if len(v)==6:
                ax,ay,az=struct.unpack("3h",v)
            #print("RX", ax,ay,az)
            aax=int((ax+1000)/2000.*5)
            aay=int((ay+1000)/2000.*5)
            hub.light_matrix.set_pixel(aax%5, aay%5)
            #motor_drive.start(int(ay/1000.*100))
            steer = int(ax/1000.*20)
            if steer!=0:
                sign=int(steer/abs(steer))
            else:
                sign=0
            #motor_steer.run_to_position(abs(steer),speed=20*sign)
        elif handle in (central._buta_handle, central._butb_handle):
            if handle == central._buta_handle:
                hub.light_matrix.set_pixel(4,0,brightness=ord(v)*49)
            elif handle == central._butb_handle:
                hub.light_matrix.set_pixel(4,4,brightness=ord(v)*49)
    
            

    central.on_notify(on_rx)

    with_response = False
    # while central._acc_handle == None:
    #    time.sleep_ms(100)
    try:
        pass
        #central.enable_notify()
        #central.read(on_rx)
    except:
        print("TX failed")
    #print("handles",central._rx_handle,central._led_matrix_handle,central._led_text_handle,central._led_delay_handle)
    i = 0
    time.sleep_ms(1000)
    central.write(central._led_matrix_handle,b'\x01\x03\x07\x0f\x1f')
    time.sleep_ms(50)
    central.write(central._rx_handle+1,b'\x01\x00')# enable notify
    # time.sleep_ms(50)
    # central.write(central._rx_handle+2,b'\x01\x00')# enable notify
    time.sleep_ms(1000)

    while central.is_connected():
        i += 1
        #central.read()
        #time.sleep_ms(400 if with_response else 30)
        #time.sleep_ms(4000)
        hub.light_matrix.off()
        #try:
        #central.read(central._rx_handle,on_rx)
        time.sleep_ms(100)
        central.write(central._led_matrix_handle,b'\x01\x03\x07\x0f\x1f')
        
        time.sleep_ms(100)
        central.write(central._led_matrix_handle,b'\x1f\x0f\x07\x03\x01')
        time.sleep_ms(100)
        central.write(central._rx_handle+1,b'\x01\x00')# enable notify
        #central.write(central._led_text_handle,b'Stefan')

        #if i%3==1: central.read(central._buta_handle,on_rx)
        #if i%3==2: central.read(central._butb_handle,on_rx)
        #except:
        #    pass
        #    print("reading failed")
        if hub.left_button.is_pressed():
            central.disconnect()
            break
    print("Disconnected")



demo()

