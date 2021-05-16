
import time
import ubluetooth
import ubinascii
from micropython import const

MAC_SPIKE=b'\x40\xbd\x32\x42\xeb\x54'
MAC_MICRO=b'\xFA\x35\x2F\x6C\x13\xf8'
MAC_MICRO=b'\xFA\x35\x2F\x6C\x13\xf8'
MAC_M5=b'\x50\x02\x91\x8d\x17\x26'
#fa352f6c13f8
_IRQ_SCAN_RESULT = const(5)

_IRQ_SCAN_DONE = const(6)
mac=None

def bt_irq(event, data):
    global mac
    if event == _IRQ_SCAN_RESULT:
        addr_type, addr, adv_type, rssi, adv_data = data
    # if rssi>-70:
    #     print('type:{} addr:{} adv_type: {} rssi:{} data:{}'.format(addr_type, ubinascii.hexlify(addr), adv_type,rssi,ubinascii.hexlify(adv_data)))
	if addr==MAC_M5:
		mac=addr
		print('type:{} addr:{} adv_type: {} rssi:{} data:{}'.format(addr_type, ubinascii.hexlify(addr), adv_type,rssi,ubinascii.hexlify(adv_data)))
	elif event == _IRQ_SCAN_DONE:
		print("complete")


ble = ubluetooth.BLE()
ble.active(True)
ble.irq(bt_irq)
ble.gap_scan(30000,30000,30000)
while mac is None:
	time.sleep_ms(100)
