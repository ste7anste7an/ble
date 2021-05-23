# This example finds and connects to a peripheral running the
# UART service (e.g. ble_simple_peripheral.py).

import bluetooth
import random
import struct
import time
import micropython
import ubinascii

from ble_advertising import decode_services, decode_name

from micropython import const



_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)
_IRQ_GATTS_READ_REQUEST = const(4)
_IRQ_SCAN_RESULT = const(5)
_IRQ_SCAN_DONE = const(6)
_IRQ_PERIPHERAL_CONNECT = const(7)
_IRQ_PERIPHERAL_DISCONNECT = const(8)
_IRQ_GATTC_SERVICE_RESULT = const(9)
_IRQ_GATTC_SERVICE_DONE = const(10)
_IRQ_GATTC_CHARACTERISTIC_RESULT = const(11)
_IRQ_GATTC_CHARACTERISTIC_DONE = const(12)
_IRQ_GATTC_DESCRIPTOR_RESULT = const(13)
_IRQ_GATTC_DESCRIPTOR_DONE = const(14)
_IRQ_GATTC_READ_RESULT = const(15)
_IRQ_GATTC_READ_DONE = const(16)
_IRQ_GATTC_WRITE_DONE = const(17)
_IRQ_GATTC_NOTIFY = const(18)
_IRQ_GATTC_INDICATE = const(19)

_ADV_IND = const(0x00)
_ADV_DIRECT_IND = const(0x01)
_ADV_SCAN_IND = const(0x02)
_ADV_NONCONN_IND = const(0x03)

_NOTIFY_ENABLE = const(1)
_INDICATE_ENABLE = const(2)


_ACC_SERVICE_UUID = bluetooth.UUID("E95D0753-251D-470A-A062-FA1922DFA9A8")
_ACC_DATA_UUID = bluetooth.UUID("E95DCA4B-251D-470A-A062-FA1922DFA9A8")
_ACC_DESCR_UUID= bluetooth.UUID(0x2902)

"""
public static String ACCELEROMETERSERVICE_SERVICE_UUID = "E95D0753251D470AA062FA1922DFA9A8";
public static String ACCELEROMETERDATA_CHARACTERISTIC_UUID = "E95DCA4B251D470AA062FA1922DFA9A8";
public static String ACCELEROMETERPERIOD_CHARACTERISTIC_UUID = "E95DFB24251D470AA062FA1922DFA9A8";
"""
MAC_MICRO=b'\xFA\x35\x2F\x6C\x13\xf8'

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

    def _irq(self, event, data):
        if event == _IRQ_SCAN_RESULT:
            addr_type, addr, adv_type, rssi, adv_data = data
            if addr == MAC_MICRO:
                print('type:{} addr:{} adv_type: {} rssi:{} data:{}'.format(addr_type, ubinascii.hexlify(addr), adv_type,rssi,ubinascii.hexlify(adv_data)))
                print("service",decode_services(adv_data))
                # if adv_type in (_ADV_IND, _ADV_DIRECT_IND) and _ACC_SERVICE_UUID in decode_services(
                #     adv_data
                # ):
                # Found a potential device, remember it and stop scanning.
                self._addr_type = addr_type
                self._addr = bytes(
                    addr
                )  # Note: addr buffer is owned by caller so need to copy it.
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

        elif event == _IRQ_GATTC_SERVICE_RESULT:
            # Connected device returned a service.
            conn_handle, start_handle, end_handle, uuid = data
            print("service", data)
            if conn_handle == self._conn_handle and uuid == _ACC_SERVICE_UUID:
                self._start_handle, self._end_handle = start_handle, end_handle
                #self._ble.gattc_discover_characteristics(self._conn_handle, start_handle, end_handle)
                
        elif event == _IRQ_GATTC_SERVICE_DONE:
            # Service query complete.
            if self._start_handle and self._end_handle:
                self._ble.gattc_discover_characteristics(
                    self._conn_handle, self._start_handle, self._end_handle
                )
            else:
                print("Failed to find uart service.")

        elif event == _IRQ_GATTC_CHARACTERISTIC_RESULT:
            # Connected device returned a characteristic.
            conn_handle, def_handle, value_handle, properties, uuid = data
            print('gattc_char',data)
            if conn_handle == self._conn_handle and uuid == _ACC_DATA_UUID:
                self._rx_handle = value_handle
                print("_IRQ_GATTC_CHARACTERISTIC_RESULT, handle",value_handle)
                #self._ble.gatts_notify(conn_handle, value_handle )
            # if conn_handle == self._conn_handle and uuid == _UART_TX_CHAR_UUID:
            #     self._tx_handle = value_handle

        elif event == _IRQ_GATTC_CHARACTERISTIC_DONE:
            # Characteristic query complete.
            #if self._tx_handle is not None and self._rx_handle is not None:
            if self._rx_handle is not None:
                # We've finished connecting and discovering device, fire the connect callback.
                print("CHARACTERISTIC_DONE")
                self._ble.gattc_discover_descriptors(self._conn_handle, self._start_handle, self._end_handle)

                if self._conn_callback:
                    self._conn_callback()
            else:
                print("Failed to find uart rx characteristic.")

        elif event == _IRQ_GATTC_DESCRIPTOR_RESULT:
            # Connected device returned a descriptor.
            conn_handle,  value_handle, uuid = data
            print('desciptor_result',data)
            if conn_handle == self._conn_handle and uuid == _ACC_DESCR_UUID:
                print("set acc_handle",value_handle)
                self._acc_handle = value_handle
            
        elif event == _IRQ_GATTC_DESCRIPTOR_DONE:
            print('descriptor done',data)
            
        elif event == _IRQ_GATTC_WRITE_DONE:
            conn_handle, value_handle, status = data
            print("TX complete")

        elif event == _IRQ_GATTC_NOTIFY:
            print("_IRQ_GATTC_NOTIFY")
            conn_handle, value_handle, notify_data = data
            notify_data=bytes(notify_data)
            print("data:",notify_data)
            
            if conn_handle == self._conn_handle and value_handle == self._rx_handle:
                if self._notify_callback:
                    self._notify_callback(notify_data)
        elif event == _IRQ_GATTC_READ_RESULT:
            print("_IRQ_GATTC_READ_RESULT")
            # A read completed successfully.
            conn_handle, value_handle, char_data = data
            if conn_handle == self._conn_handle and value_handle == self._value_handle:
                print("READ data",bytes(char_data))

        elif event == _IRQ_GATTC_READ_DONE:
            print("_IRQ_GATTC_READ_DONE")
            # Read completed (no-op).
            conn_handle, value_handle, status = data
 
    # Returns true if we've successfully connected and discovered characteristics.
    def is_connected(self):
        return (
            self._conn_handle is not None
            #and self._tx_handle is not None
            and self._rx_handle is not None
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
    def write(self, v, response=False):
        if not self.is_connected():
            return
        self._ble.gattc_write(self._conn_handle, self._rx_handle, v, 1 if response else 0)

    def enable_notify(self):
        if not self.is_connected():
            return
        self._ble.gattc_write(self._conn_handle, self._acc_handle, struct.pack('<h', _NOTIFY_ENABLE), 0)
    def read(self):
        if not self.is_connected():
            return
        #self._read_callback = callback
        print("reading handle",self._conn_handle,self._rx_handle)
        self._ble.gattc_read(self._conn_handle, self._rx_handle)
 
    # Set handler for when data is received over the UART.
    def on_notify(self, callback):
        self._notify_callback = callback


def demo():
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

    central.scan(callback=on_scan)

    # Wait for connection...
    while not central.is_connected():
        time.sleep_ms(100)
        if not_found:
            return

    print("Connected")

    def on_rx(v):
        if len(v)==6:
            ax,ay,az=struct.unpack("3h",v)
        print("RX", ax,ay,az)

    central.on_notify(on_rx)

    with_response = False
    while central._acc_handle == None:
        time.sleep_ms(100)
    try:
        pass 
        central.enable_notify()
        #central.read()
    except:
        print("TX failed")
        
    i = 0
    while central.is_connected():
        i += 1
        #central.read()
        time.sleep_ms(400 if with_response else 30)

    print("Disconnected")


if __name__ == "__main__":
    demo()

