#!/usr/bin/env python3

import hidapi
import binascii
import sys
import datetime

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

def create_dump(hd):
    length = 32
    first_addr = 0x0000
    last_addr = 0xFFFF
    answer = b''
    for addr in range(first_addr, last_addr, length):
        answer += request(hd, addr, length)
        sys.stderr.write("\rReading from device… %d%%"%(int(addr/last_addr*100)))
    sys.stderr.write("\nDone.\n")
    return answer


mmap = {
    "init_ok"       : (0x00, 2),
    "model"         : (0x02, 2),
    "ID"            : (0x05, 4),
    "settings"      : (0x09, 6),
    "unknown"       : (0x50, 6),
    "series_counts" : (0x58, 323), # TODO: find out actual length (this is a guess)
    "series_dates"  : (0x19C, 2915), # TODO: find out actual length (this is a guess)
    "series"        : (0xD00, 0xFFFF-0xD00) # TODO: find out actual length (this is a guess)
}
def get_field(data, field):
    addr, length = mmap[field]
    return data[addr:addr+length]

def get_chunks(data, size):
    return (data[i*size:(i+1)*size] for i in range(len(data)//size))
    
def get_series_dates(data):
    def convert_dates(series_dates):
        for date in get_chunks(series_dates, 8):
            date = date[:-2] # TODO: find out what these bytes do (always b'012c')
            date = [binascii.b2a_hex(bytes([b])).decode("ascii") for b in date] # TODO: make this less ugly
            year, month, day, hour, minute, second = [int(d) for d in date]
            yield(datetime.datetime(2000+year, month, day, hour, minute, second))
    return convert_dates(get_field(data, "series_dates"))
    
def convert_measurement(measurement):
    humidity = int(measurement[0])-20
    temperature = int.from_bytes(measurement[1:3], byteorder='big')*0.1-50
    return (humidity, temperature)

if __name__ == "__main__":
    vendor_id = 0x10c4
    product_id = 0x8468
    timeout_ms = 1000
    sample_interval_minutes = 5 # TODO: read from datasets
    hd = hidapi.Device(vendor_id=vendor_id, product_id=product_id)

    if (len(sys.argv) == 2):
        #with open("dump.bin",'wb') as f:
        #    f.write(data)
        data = open(sys.argv[1],'rb').read()
    else:
        data = create_dump(hd)

    if (int.from_bytes(get_field(data, "init_ok"), byteorder='big') != 0x55aa):
        raise RuntimeError("Incorrect device ROM magic number. This software is not meant to be used with your device.")
    if (int.from_bytes(get_field(data, "model"), byteorder='big') != 0x0201):
         raise RuntimeError("Unknown model number.")
    
    sys.stderr.write("Device ID: %s\n"%(binascii.b2a_hex(get_field(data, "ID")).decode("ascii")))
    if (binascii.b2a_hex(get_field(data, "settings")) != b'2d012c006414'):
        sys.stderr.write("WARNING: Unknown settings detected (only the exact combination of 24h format, degrees celsius, and 5 minute sample interval was tested). Expect havoc.\n"%())

    if False:
        for field in mmap.keys():
            if "series" not in field:
                print("%s: %s"%(field, binascii.b2a_hex(get_field(data, field)).decode("ascii")))

    series_counts = get_field(data, "series_counts")
    series_counts = [sc for sc in series_counts if sc != 0xFF]
    series_dates = get_series_dates(data)
    measurements = get_chunks(data[mmap["series"][0]:], 3)
    number = 0
    print("Nummer	Aufzeichnungszeit	Temperatur(°C)	Luftfeuchtigkeit(%)\r")
    for series_count, series_start_date in zip(series_counts, series_dates):
        for i in range(64):
            humidity, temperature = convert_measurement(next(measurements))
            if (i <= series_count):
                number += 1
                measurement_date = series_start_date+datetime.timedelta(
                    minutes=sample_interval_minutes*i
                )
                print(" %d\t %s\t %.1f\t %d\r"%(number, measurement_date, temperature, humidity))
