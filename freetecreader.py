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
    last_addr = 0x2000 # actually 0xFFFF
    answer = b''
    for addr in range(first_addr, last_addr, length):
        answer += request(hd, addr, length)
        sys.stdout.write("\rReading from device… %d%%"%(int(addr/last_addr*100)))
    sys.stdout.write("\nDone.\n")
    return answer


mmap = {
    "init ok"       : (0x00, 2),
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
            date = date[:-2]
            date = [binascii.b2a_hex(bytes([b])).decode("ascii") for b in date]
            year, month, day, hour, minute, second = [int(d) for d in date]
            yield(datetime.datetime(2000+year, month, day, hour, minute, second))
            #yield("20%s-%s-%s %s:%s:%s"%tuple(date))
    return convert_dates(get_field(data, "series_dates"))

if __name__ == "__main__":
    vendor_id = 0x10c4
    product_id = 0x8468
    timeout_ms = 1000
    hd = hidapi.Device(vendor_id=vendor_id, product_id=product_id)

    #data = create_dump(hd)
    #with open("dump.bin",'wb') as f:
    #    f.write(data)
    data = open("dump.bin",'rb').read()

    #for field in mmap.keys():
    #    if "series" not in field:
    #        print("%s: %s"%(field, binascii.b2a_hex(get_field(data,field)).decode("ascii")))

    series_counts = get_field(data, "series_counts")
    series_counts = [sc for sc in series_counts if sc != 0xFF]
    series_dates = get_series_dates(data)
    #for byte in series_counts:
    #    print(byte)
    #for date in series_dates:
    #    print(date)
    #print(list(zip(series_dates, series_counts)))
    def convert_measurement(measurement):
        humidity = int(measurement[0])-20
        temperature = int.from_bytes(measurement[1:3], byteorder='big')*0.1-50
        return (humidity, temperature)
    measurements = get_chunks(data[mmap["series"][0]:], 3)
    number = 0
    print("Nummer	Aufzeichnungszeit	Temperatur(°C)	Luftfeuchtigkeit(%)\r")
    for series_count, series_start_date in zip(series_counts, series_dates):
        for i in range(64):
            humidity, temperature = convert_measurement(next(measurements))
            #print(number, series_start_date, i, binascii.b2a_hex(next(measurements)))
            if (i > series_count):
                pass
                #print("^^ ignored")
            else:
                pass
                number += 1
                measurement_date = series_start_date+datetime.timedelta(minutes=5*i)
                print(" %d\t %s\t %.1f\t %d\r"%(number, measurement_date, temperature, humidity))
                
                
