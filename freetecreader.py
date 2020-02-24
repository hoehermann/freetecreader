#!/usr/bin/env python3

import hidapi
import binascii
import sys
import datetime
#from itertools import islice

# TODO: read lazily everywhere

class FreeTecDevice():
    
    def __init__(self, vendor_id = 0x10c4, product_id = 0x8468, timeout_ms = 1000, data = b''):
        self.timeout_ms = timeout_ms
        self.hd = hidapi.Device(vendor_id=vendor_id, product_id=product_id)
        self.data = data
        self.generator = self._generator()
        first_chunk = next(self.generator)
        init_ok = int.from_bytes(self.get_field("init_ok"), byteorder='big')
        if (init_ok != 0x55aa):
            raise RuntimeError("Incorrect device ROM magic number (is %04x, should be 55aa). Try again without re-connecting the device. If the error persists, this software is not meant to be used with your device."%(init_ok))
        self.model = int.from_bytes(self.get_field("model"), byteorder='big')
        if (self.model != 0x0201):
             raise RuntimeError("Unknown model number.")
        self.id = self.get_field("ID")
        self.id_str = binascii.hexlify(self.id).decode("ascii")
        self.settings = self.get_field("settings")
        if (self.settings != binascii.unhexlify('2d012c006414')):
            sys.stderr.write("WARNING: Unknown settings detected (only the exact combination of 24h format, degrees celsius, and 5 minute sample interval was tested). Expect havoc.\n")
        self.sample_interval_minutes = 5 # TODO: read interval from settings (or datasets if possible)
        
    def _generator(self):
        length = 32
        first_addr = 0x0000
        last_addr = 0xFFFF
        for addr in range(first_addr, last_addr, length):
            #sys.stderr.write("\rReading from device… %d%%"%(int(addr/last_addr*100)))
            data = self._request(addr, length)
            self.data += data
            yield data
        #sys.stderr.write("\nDone.\n")

    def _request(self, addr = None, length = None, msg_bytes = None):
        if (not msg_bytes):
            suffix = addr//256+addr%256+length+1
            suffix = ("%02x"%(suffix))[-2:]
            addr = "%04x"%(addr)
            msg_bytes = binascii.unhexlify(
                "02060100"+addr+"%02x"%(length)+suffix
            )
        self.hd.write(msg_bytes)
        answer = self.hd.read(61, timeout_ms=self.timeout_ms)
        if (answer[0] != 0x01):
            raise IOError("First byte of answer is not 0x01.")
        answer = answer[2:] # TODO: find out what second byte means
        answer = answer[:length]
        return answer

    memory_map = {
        "init_ok"       : (0x00, 2),
        "model"         : (0x02, 2),
        "ID"            : (0x05, 4),
        "settings"      : (0x09, 6),
        "unknown"       : (0x50, 6),
        "series_counts" : (0x58, 323), # TODO: find out actual length (this is a guess)
        "series_dates"  : (0x19C, 2915), # TODO: find out actual length (this is a guess)
        "series"        : (0xD00, 0xFFFF-0xD00) # TODO: find out actual length (this is a guess)
    }
    def get_field(self, field):
        addr, length = self.memory_map[field]
        while (len(self.data) < addr+length):
            next(self.generator)
        return self.data[addr:addr+length]

    @staticmethod
    def _get_chunks(data, size):
        return (data[i*size:(i+1)*size] for i in range(len(data)//size))

    def get_measurements(self):
        series_counts = self.get_field("series_counts")
        series_counts = [sc for sc in series_counts if sc != 0xFF]
        series_dates = self._get_series_dates()
        measurements = self._get_chunks(self.get_field("series"), 3)
        def convert_measurement(measurement):
            humidity = int(measurement[0])-20
            temperature = int.from_bytes(measurement[1:3], byteorder='big')*0.1-50
            return (humidity, temperature)
        number = 0
        for series_count, series_start_date in zip(series_counts, series_dates):
            for i in range(64):
                humidity, temperature = convert_measurement(next(measurements))
                if (i <= series_count):
                    number += 1
                    measurement_date = series_start_date+datetime.timedelta(
                        minutes=self.sample_interval_minutes*i
                    )
                    yield (number, measurement_date, temperature, humidity)

    def _get_series_dates(self):
        def convert_dates(series_dates):
            for date in self._get_chunks(series_dates, 8):
                date = date[:-2] # TODO: find out what these bytes do (always b'012c')
                date = ["%02x"%(b) for b in date]
                year, month, day, hour, minute, second = [int(d) for d in date]
                yield datetime.datetime(2000+year, month, day, hour, minute, second)
        return convert_dates(self.get_field("series_dates"))

if __name__ == "__main__":
    data = b''
    if (len(sys.argv) == 2):
        data = open(sys.argv[1],'rb').read()
    ftd = FreeTecDevice(data = data)
    sys.stderr.write(
        "Device ID: %s\n"%(ftd.id_str)
    )
    with open('%s.csv'%(ftd.id_str),'w') as f:
        f.write("Nummer	Aufzeichnungszeit	Temperatur(°C)	Luftfeuchtigkeit(%)\r")
        for m in ftd.get_measurements():
            f.write(" %d\t %s\t %.1f\t %d\r"%m)
    if (len(sys.argv) == 1):
        with open('%s.bin'%(ftd.id_str),'wb') as f:
            f.write(ftd.data)

    if False:
        for field in memory_map.keys():
            if "series" not in field:
                print("%s: %s"%(
                    field, 
                    binascii.hexlify(get_field(data, field)).decode("ascii")
                ))

    
