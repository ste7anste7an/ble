import bluetooth
import random
import struct
import time
import micropython
import sys
import gc
from hub import led, display, Image
from micropython import const

_IRQ_CENTRAL_CONNECT =        const(1<<0)
_IRQ_CENTRAL_DISCONNECT =    const(1<<1)
_IRQ_GATTS_WRITE =            const(1<<2)
_IRQ_GATTS_READ_REQUEST =    const(1<<3)
_IRQ_SCAN_RESULT =            const(1<<4)
_IRQ_SCAN_DONE =            const(1<<5)
_IRQ_PERIPHERAL_CONNECT =    const(1<<6)
_IRQ_PERIPHERAL_DISCONNECT =const(1<<7)
_IRQ_GATTC_WRITE_STATUS =    const(1<<12)
_IRQ_GATTC_NOTIFY =        const(1<<13) 

_ADV_IND =                    const(0x00)
_ADV_DIRECT_IND =            const(0x01)

_FLAG_READ =                const(0x0002)
_FLAG_WRITE_NO_RESPONSE =    const(0x0004)
_FLAG_WRITE =                const(0x0008)
_FLAG_NOTIFY =                const(0x0010)

_ADV_TYPE_FLAGS = const(0x01)
_ADV_TYPE_NAME = const(0x09)
_ADV_TYPE_UUID16_COMPLETE = const(0x3)
_ADV_TYPE_UUID32_COMPLETE = const(0x5)
_ADV_TYPE_UUID128_COMPLETE = const(0x7)
_ADV_TYPE_UUID16_MORE = const(0x2)
_ADV_TYPE_UUID32_MORE = const(0x4)
_ADV_TYPE_UUID128_MORE = const(0x6)
_ADV_TYPE_APPEARANCE = const(0x19)

_UART_SERVICE_UUID = bluetooth.UUID('6ee6d166-6084-11eb-ae93-0242ac130002')
_UART_RX_CHAR_UUID = bluetooth.UUID('6ee6d3e6-6084-11eb-ae93-0242ac130002')
_UART_TX_CHAR_UUID = bluetooth.UUID('6ee6d4cc-6084-11eb-ae93-0242ac130002')

_UART_UUID = _UART_SERVICE_UUID
_UART_TX = (
    _UART_TX_CHAR_UUID,
    _FLAG_READ | _FLAG_NOTIFY,
)
_UART_RX = (
    _UART_RX_CHAR_UUID,
    _FLAG_WRITE | _FLAG_WRITE_NO_RESPONSE,
)
_UART_SERVICE = (
    _UART_UUID,
    (_UART_TX, _UART_RX),
)

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

# Generate a payload to be passed to gap_advertise(adv_data=...).
def advertising_payload(limited_disc=False, br_edr=False, name=None, services=None, appearance=0):
    payload = bytearray()

    def _append(adv_type, value):
        nonlocal payload
        payload += struct.pack('BB', len(value) + 1, adv_type) + value

    _append(
        _ADV_TYPE_FLAGS,
        struct.pack('B', (0x01 if limited_disc else 0x02) + (0x18 if br_edr else 0x04)),
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
        _append(_ADV_TYPE_APPEARANCE, struct.pack('<h', appearance))

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
    return str(n[0], 'utf-8') if n else ''

def decode_services(payload):
    services = []
    for u in decode_field(payload, _ADV_TYPE_UUID16_COMPLETE):
        services.append(bluetooth.UUID(struct.unpack('<h', u)[0]))
    for u in decode_field(payload, _ADV_TYPE_UUID32_COMPLETE):
        services.append(bluetooth.UUID(struct.unpack('<d', u)[0]))
    for u in decode_field(payload, _ADV_TYPE_UUID128_COMPLETE):
        services.append(bluetooth.UUID(u))
    return services

def on_scan(self, addr_type, addr, connecting_device):
    if self._debug:
        print('on scan: ' + str(addr_type) + str(addr))
    if addr_type is not None:
        if self._debug:
            print('Found child: ', connecting_device)
        self.connect_device()
    else:
        self._not_found = True
        if self._debug:
            print('No child found.')

class BLEnetwork:
    def __init__(self, name, network, state=[], debug = False):
        if debug:
            print('init')
        self._ble = bluetooth.BLE()
        self._ble.active(True)
        self._debug = debug
        self._ble.irq(self._irq)
        self._not_found = False
        self._name = name
        self._network = network
        self._address = network[name]
        self._set_local_network()
        self.state = state
    
        self._scanning = False
        self._connecting_device = None

        ## Connection to Parent
        ((self._handle_tx, self._handle_rx),) = self._ble.gatts_register_services((_UART_SERVICE,))
        self._ble.gatts_write(self._handle_rx, bytes(100))#set max message size to 100 bytes
        self._ble.gatts_set_buffer(self._handle_rx, 100)
        self._ble.gatts_set_buffer(self._handle_tx, 100)        
        self._conn_handle_parent = None
        
        self._response_received = True
        self._write_callback = None
        self._payload = advertising_payload(name=name, services=[_UART_UUID])

        self._reset()

    def _reset(self):
        if self._debug:
            print(self._name+'reset')
        # Cached name and address from a successful scan.
        self._addr_type = None
        self._addr = None

        # Callbacks for completion of various operations.
        # These reset back to None after being invoked.
        self._scan_callback = None
        self._conn_callback = None
        self._read_callback = None

        # Persistent callback for when new data is notified from the device.
        self._notify_callback = None
        self._on_receive_callback = None
        
        self._tx_available = True

        # Connected device.
        self._conn_handle = [None] * self._nr_children
        self._tx_handle = 9
        self._rx_handle = 12
        
        if self._debug:
            print(self._name+'reset_complete')
        

    def _irq(self, event, data):
        ### Parent connect
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            if self._debug:
                print(self._name+' event: Central Connect')
                print('New connection', conn_handle)
            self._conn_handle_parent=conn_handle
            self._update_animation()
            
        ### Parent disconnect
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            if self._debug:
                print(self._name+' event: Central Disconnect')
                print('Disconnected', conn_handle)    
            self._conn_handle_parent=None
            self._update_animation()
            # Start advertising again to allow a new connection.
            self._advertise()
            
        ### Child receiving from Parent on rx
        elif event == _IRQ_GATTS_WRITE:
            if self._debug:
                print(self._name+' event: Write')
            conn_handle, value_handle = data
            value = self._ble.gatts_read(value_handle)
            if value_handle == self._handle_rx and self._write_callback:
                self._write_callback(value.decode())
        
        ### Parent scan found BLE device
        elif event == _IRQ_SCAN_RESULT:
            if self._debug:
                print(self._name+' event: scan result')
            addr_type, addr, adv_type, rssi, adv_data = data
            if adv_type in (_ADV_IND, _ADV_DIRECT_IND) and _UART_SERVICE_UUID in decode_services(adv_data) and (self._children is None or decode_name(adv_data) in self._children):
                # Found a potential device, remember it and stop scanning.
                if self._debug:
                    print('Child:', decode_name(adv_data), 'Recognized')
                self._connecting_device = decode_name(adv_data)
                self._addr_type = addr_type
                self._addr = bytes(
                    addr
                )
                # stop scanning to trigger scan_done
                self._ble.gap_scan(None)

        ### Parent found possible child
        elif event == _IRQ_SCAN_DONE:
            if self._debug:
                print(self._name+' event: scan done')
            if self._scan_callback:
                if self._addr:
                    # Found a device during the scan (and the scan was explicitly stopped).
                    self._scan_callback(self,self._addr_type, self._addr, self._connecting_device)
                    #self._scan_callback = None
                else:
                    # Scan timed out.
                    self._scan_callback(self,None, None, None)
                    self._not_found = True

        ### Child connected to Parent
        elif event == _IRQ_PERIPHERAL_CONNECT:
            if self._debug:
                print(self._name+' event: peripheral connect')
                
            conn_handle, addr_type, addr = data
            if addr_type == self._addr_type and addr == self._addr:            
                self._conn_handle[self._chld_idx[self._connecting_device]]=conn_handle
                
                print('Child ' + self._children[self._conn_handle.index(conn_handle)] + ' successfully connected')
                self._scanning = False
                self._update_animation()

        ### A child disconnected from Parent
        elif event == _IRQ_PERIPHERAL_DISCONNECT:
            # Disconnect (either initiated by us or the remote end).
            conn_handle, _, _ = data
            if self._debug:
                print(self._name+'event: child ' + self._children[self._conn_handle.index(conn_handle)] + ' disconnect')
            if conn_handle in self._conn_handle:
                # If it was initiated by us, it'll already be reset.
                #self._reset()
                self._conn_handle[self._conn_handle.index(conn_handle)] = None
                self._update_animation()
        
        ### A write from Parent to Child is completed
        elif event == _IRQ_GATTC_WRITE_STATUS:
            if self._debug:
                print(self._name+' event: write complete')
            conn_handle, value_handle, status = data
            self._tx_available = True

        ### Parent Receives Response from Child
        elif event == _IRQ_GATTC_NOTIFY:
            if self._debug:
                print(self._name+'event: notify')
            conn_handle, value_handle, notify_data= data
            self._response_received = True
            if self._debug:
                print(notify_data)
            if not self._parent:
                if conn_handle in self._conn_handle and value_handle == self._tx_handle:
                    if self._notify_callback:
                        self._notify_callback(notify_data.decode())
            else:
                self.route_respond_to_root(notify_data.decode())
        else:
            if self._debug:
                print('unknown event:' + str(event))
            
    def _set_local_network(self):
        
        self.address = self._network[self._name]
        max_level = len(self.address)

        if '0' in self.address:
            self._level = self.address.index('0')
        else:
            self._level = max_level
        
        if self._level > 0:
            self._parent_address = self.address[:self._level-1] + '0'*(max_level-self._level+1)
            self._parent = list(self._network.keys())[list(self._network.values()).index(self._parent_address)]
        else:
            self._parent_address = None
            self._parent = None
            
        if self._level < max_level:
            self._children_address = []
            for child_address in list(self._network.values()):
                if child_address[:self._level] == self._network[self._name][:self._level] and not (child_address == self._network[self._name]) and not child_address[self._level+1:]>'0'*max_level:
                    self._children_address.append(child_address)
            self._children = ['']*len(self._children_address)
            self._chld_idx = {}
            for i in range(len(self._children_address)):
                self._children[i]=list(self._network.keys())[list(self._network.values()).index(self._children_address[i])]
                self._chld_idx.update({self._children[i]:i})
            self._nr_children = len(self._children)
        else:
            self._children_address = []
            self._children = []
            self._chld_idx = {}
            self._nr_children = 0
            

    def parent_is_connected(self):
        return self._conn_handle_parent or (self._parent is None)

    def children_are_connected(self):
        return self._conn_handle.count(None) is 0
    # Returns true if we've successfully connected and discovered characteristics.
    def is_connected(self):
        return self.children_are_connected() and self.parent_is_connected()

    # Find a device advertising the environmental sensor service.
    def connect(self, callback=None):
        self._addr_type = None
        self._addr = None
        self._scan_callback = on_scan
        self._not_found=False
        
        self._update_animation()
        
        if not self.children_are_connected():
            print('Connect to children')
        while not self.children_are_connected():
            self._ble.gap_scan(20000,30000,30000)
            self._scanning = True
            children_to_connect = self._conn_handle.count(None)
            if self._debug:
                print(children_to_connect)
                print(self._conn_handle.count(None))
            while self._scanning:
                time.sleep_ms(200)
                if self._not_found:
                    self._scanning = False
                    
        if not self.parent_is_connected():
            if self._debug:
                print('connect parent')
            self._advertise()
            
            while not self.parent_is_connected():
                pass        
            
    ### Responding from child to parent
    def respond_to_client(self, v):
        gc.collect()
        data = {'_f':self._name, '_m':v}
        try:
            self._ble.gatts_write(self._handle_tx, str(data))
            self._ble.gatts_notify(self._conn_handle_parent, self._handle_tx)
        except:
            data = self._ble.gatts_read(self._handle_tx)
            if self._debug:
                print('read buffer')
                print(data)
            
    ### Route a response from child to parent        
    def route_respond_to_root(self, data):
        gc.collect()
        try:
            self._ble.gatts_write(self._handle_tx,data)
            self._ble.gatts_notify(self._conn_handle_parent, self._handle_tx)
        except:
            data = self._ble.gatts_read(self._handle_tx)
            if self._debug:
                print('read buffer')
                print(data)

    # Connect to the specified device (otherwise use cached address from a scan).
    def connect_device(self, addr_type=None, addr=None, callback=None):
        self._addr_type = addr_type or self._addr_type
        self._addr = addr or self._addr
        self._conn_callback = callback
        if self._addr_type is None or self._addr is None:
            return False
        self._ble.gap_connect(self._addr_type, self._addr)
        return True

# Disconnect children
    def disconnect(self): 
        for conn_handle in self._conn_handle:
            if not self._conn_handle[0]:
                return
            self._ble.gap_disconnect(conn_handle)
        self._reset()

    # Sending request from parent to children
    def request_child(self, child, message, wait_for_response = True):
        children = [child]
        if not self.is_connected():
            return
        
        for i in range(len(children)):
            data = {'_t': self._network[children[i]], '_f':self._name, '_m':message}
            if self._debug:
                print('send to: ', children[i])
            conn_handle = None
            if children[i] in self._children:
                conn_handle = self._conn_handle[self._chld_idx[children[i]]]
            else:
                for idx in range(len(self._children)):
                    if self._network[children[i]][:self._level+1] is self._children_address[idx][:self._level+1]:
                        if self._debug:
                            print('send via ', self._children[idx])
                        conn_handle = self._conn_handle[idx]
            if conn_handle:
                if self._debug:
                    print('wait for tx to be available')
                    led(1)
                while (not self._tx_available) and (not self._response_received):
                    pass
                if self._debug:
                    led(0)
                    print('tx available')
                    print('conn_handle: ', conn_handle)
                    print('data', str(data))
                try:
                    self._ble.gattc_write(conn_handle, self._rx_handle, str(data), 1)
                    self._tx_available = False
                    if wait_for_response:
                        self._response_received = False
                except:
                    print('Send to: ' + children[i] + ' failed')
            else:
                print('message cannot be send to this hub')

    # Set handler for when data is received over the UART.
    def set_on_response(self, callback):
        def on_rx(v):
            print(v)
            try:
                data = eval(v)
            except:
                print('A received message is probably to long, this data was collected:' + v)
                print('Try to reduce the message length')
                
            data.setdefault('_f', [])
            data.setdefault('_m', {})
            
            child= data['_f']
            message = data['_m']
                        
            callback(message,child)
        
        self._notify_callback = on_rx
        
    def set_on_request(self, callback):
            
        def on_rx(v):
            try:
                data = eval(v)
            except:
                print('A received message is probably to long, this data was collected:' + v)
                print('Try to reduce the message length')
                
            data.setdefault('_t', [])
            data.setdefault('_m', {})                

            if data['_t'] is self._address:    
                respond_message = callback(data['_m'])
                if self._debug:
                    print('respond message', respond_message)
                if respond_message:
                    self.respond_to_client(respond_message)
            else:
                idx_addressed_child = [idx for idx in range(len(self._children)) if data['_t'][:self._level+1] is self._children_address[idx][:self._level+1]]
                addressed_child_idx = []
                for idx in range(len(self._children)):
                    if self._children_address[idx][:self._level+1] == data['_t'][:self._level+1]:
                        addressed_child_idx.append(idx)
                        
                if len(addressed_child_idx)>0:                    
                    for idx in addressed_child_idx:
                        if self._debug:
                            print('route message to: ' + self._children[idx])
                        if self._conn_handle[idx]:
                            if self._debug:
                                print('wait for tx to be available')
                                led(1)
                            while (not self._tx_available) and (not self._response_received):
                                pass
                            if self._debug:
                                print('tx available')
                                led(0)
                            self._ble.gattc_write(self._conn_handle[idx], self._rx_handle, str(data), 1)
                            self._response_received = False
                            self._tx_available = False
                        else:
                            respond_message = {'_err': 'address: ' + data['_t'] + 'not connected'}
                            self.respond_to_client(respond_message)
                            if self._debug:
                                print(respond_message)
                                print('request received for child that is not connected')
                else:
                    respond_message = {'_err': 'address: ' + data['_t'] + 'cannot be reached'}
                    self.respond_to_client(respond_message)
                    if self._debug:
                        print(respond_message)
                        print('request received for child that cannot be reached from this hub')
                    
        self._write_callback = on_rx

    def _advertise(self, interval_us=500000):
        print('Connect to Parent')
        self._ble.gap_advertise(interval_us, adv_data=self._payload)
        
    def _update_animation(self):
        if self._debug:
            print('update animation')
        if self._parent and len(self._children)>0:
            if not self.children_are_connected() and not self.parent_is_connected():
                display.show(_CONNECT_ANIMATION_CP_SS, delay=100, wait=False, loop=True)
            elif self.parent_is_connected() and not self.children_are_connected():
                display.show(_CONNECT_ANIMATION_CP_SF, delay=100, wait=False, loop=True)
            elif not self.parent_is_connected() and self.children_are_connected():
                display.show(_CONNECT_ANIMATION_CP_FS, delay=100, wait=False, loop=True)
            else:
                display.show(_COMPLETE_IMG+_CONNECT_CHILDREN_FOUND_IMG+_CONNECT_PARENT_FOUND_IMG)
        elif self._parent:
            if not self.parent_is_connected():
                display.show(_CONNECT_ANIMATION_P_S, delay=100, wait=False, loop=True)
            else:
                display.show(_COMPLETE_IMG+_CONNECT_PARENT_FOUND_IMG)
        else:
            if not self.children_are_connected():
                display.show(_CONNECT_ANIMATION_C_S, delay=100, wait=False, loop=True)
            else:
                display.show(_COMPLETE_IMG+_CONNECT_CHILDREN_FOUND_IMG)

def version():
    return '0.0.3'
    
