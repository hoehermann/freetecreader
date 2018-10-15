#!/usr/bin/env python3

import hidapi
import binascii
import sys

def request(hd, addr = None, length = None, msg_bytes = None):
    if (not msg_bytes):
        suffix = addr//256+addr%256+length+1
        suffix = ("%02x"%(suffix))[-2:]
        addr = "%04x"%(addr)
        msg_bytes = binascii.unhexlify(
            "02060100"+addr+"%02x"%(length)+suffix
        )
    hd.write(msg_bytes)
    answer = hd.read(61, timeout_ms=timeout_ms)
    if (answer[0] != 0x01):
        raise IOError("First byte of answer is not 0x01.")
    answer = answer[2:] # TODO: find out what second byte means
    answer = answer[:length]
    return answer

if __name__ == "__main__":
    vendor_id = 0x10c4
    product_id = 0x8468
    timeout_ms = 1000
    hd = hidapi.Device(vendor_id=vendor_id, product_id=product_id)
    mmap = {
        "init ok"  : (0x00, 2),
        "model"    : (0x02, 2),
        "ID"       : (0x05, 4),
        "settings" : (0x09, 6)
    }
    
    #for field, (addr, length) in mmap.items():
    #    answer = request(hd, addr, length)
    #    print("%s: %s"%(field, binascii.b2a_hex(answer[:length])))

    length = 32
    first_addr = 0x0000
    last_addr = 0x2000 # actually 0xFFFF
    with open("dump.bin",'wb') as f:
        for addr in range(first_addr, last_addr, length):
            answer = request(hd, addr, length)
            f.write(answer)
            sys.stdout.write("\rReading from device… %d%%"%(int(addr/last_addr*100)))
    sys.stdout.write("\nDone.\n")

    #length = 16
    #for addr in range(0, 0x100, length):
    #    answer = request(hd, addr, length)
    #    print(binascii.b2a_hex(answer[:length]))
    #for addr in range(0x100, 0xD00, length):
    #    answer = request(hd, addr, length)
    #    print(binascii.b2a_hex(answer[:length]))
    #length = 0x27
    #for addr in range(0x0D00, 0x2000, length):
    #    answer = request(hd, addr, length)
    #    print(binascii.b2a_hex(answer[:length]))

    #0206010000500657
    #0206010000581b74
    #020601000058025b
    #02060100019c08a6
    #0206010001a408ae
    #020601000d9c24ce
    #020601000d002735
    #020601000d27275c # c_ paket 39
    #020601000d4e2783
    #020601000d7527aa
    #020601000dc027f5
    #020601000de7271c
    #020601000e0e2744
    #020601000e351256
