#!/usr/bin/env python3

import hidapi
import binascii
import sys
import datetime
import argparse
#from itertools import islice

# TODO: read lazily everywhere

class FreeTecDevice():
    
    def __init__(self, vendor_id = 0x10c4, product_id = 0x8468, timeout_ms = 1000, data = b'', debug = False):
        self.debug = debug
        self.data = data
        self.hd = None
        if (not self.data):
            self.timeout_ms = timeout_ms
            self.hd = hidapi.Device(vendor_id=vendor_id, product_id=product_id)
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
        #self.current_interval_seconds = int.from_bytes(self.settings[1:3], byteorder='big') # not actually used anywhere – measurement series store the interval they were recorded at
        # TODO: move this offset into memory_map?
        if (self.settings[0] != 0x2d or self.settings[3:] != binascii.unhexlify('006414')):
            sys.stderr.write("WARNING: Unknown settings detected (only 24h format with degrees celsius was tested). Expect havoc.\n")
        
    def _generator(self):
        length = 32
        first_addr = 0x0000
        last_addr = 0xFFFF
        if (self.hd):
            for addr in range(first_addr, last_addr, length):
                if (self.debug):
                    sys.stderr.write("\rReading from device… %d%%"%(int(addr/last_addr*100)))
                data = self._request(addr, length)
                self.data += data
                yield data
            if (self.debug):
                sys.stderr.write("\nDone.\n")
        else:
            if (self.debug):
                sys.stderr.write("\rReading from dump…\n")
            for addr in range(first_addr, last_addr, length):
                yield self.data[addr:addr+length]

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
        "unknown_1"     : (0x50, 6),
        "series_counts" : (0x58, 324), # adjusted with help from kollokollo at https://github.com/hoehermann/freetecreader/issues/2
        "series_dates"  : (0x19C, 2592), # see above
        "unknown_2"     : (0xBBC, 324), # see above
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
        series_dates = self._get_series_properties()
        measurements = self._get_chunks(self.get_field("series"), 3)
        def convert_measurement(measurement):
            humidity = int(measurement[0])-20
            temperature = int.from_bytes(measurement[1:3], byteorder='big')*0.1-50
            return (humidity, temperature)
        for series_count, (series_start_date, series_interval) in zip(series_counts, series_dates):
            for i in range(64):
                humidity, temperature = convert_measurement(next(measurements))
                if (i <= series_count):
                    measurement_date = series_start_date+series_interval*i
                    yield (measurement_date, temperature, humidity)

    def _get_series_properties(self):
        def convert_dates(series_dates):
            for date_interval in self._get_chunks(series_dates, 8):
                # thanks to kollokollo for https://github.com/hoehermann/freetecreader/issues/1
                interval = date_interval[-2:]
                interval = int.from_bytes(interval, byteorder='big')
                interval = datetime.timedelta(seconds=interval)
                date = date_interval[:-2]
                date = ["%02x"%(b) for b in date]
                year, month, day, hour, minute, second = [int(d) for d in date]
                date = datetime.datetime(2000+year, month, day, hour, minute, second)
                yield (date, interval)
        return convert_dates(self.get_field("series_dates"))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", help="Dump raw binary to file", action="store_true")
    parser.add_argument("--csv", help="Write interpreted csv to file", action="store_true")
    parser.add_argument("--noindex", help="Do not write explicit index into csv", action="store_true")
    parser.add_argument("--suffix", help="Suffix to add to output filenames", type=str, default="")
    parser.add_argument("--data", help="Read raw binary dump", type=str)
    parser.add_argument("--debug", help="Have debug output on stderr", action="store_true")
    args = parser.parse_args()
    
    data = b''
    if (args.data):
        data = open(args.data,'rb').read()
    ftd = FreeTecDevice(data = data, debug = args.debug)
    sys.stderr.write(
        "Device ID: %s\n"%(ftd.id_str)
    )
    if (args.csv):
        with open('%s%s.csv'%(ftd.id_str, args.suffix),'w') as f:
            if (not args.noindex):
                f.write("Nummer	")
            f.write("Aufzeichnungszeit	Temperatur(°C)	Luftfeuchtigkeit(%)\r\n")
            for i, m in enumerate(sorted(ftd.get_measurements(), key=lambda m:m[0])):
                if (not args.noindex):
                    f.write(" %d\t"%(i+1))
                f.write(" %s\t %.1f\t %d\r\n"%m)
    if (args.dump):
        with open('%s%s.bin'%(ftd.id_str, args.suffix),'wb') as f:
            f.write(ftd.data)

    if False:
        for field in memory_map.keys():
            if "series" not in field:
                print("%s: %s"%(
                    field, 
                    binascii.hexlify(get_field(data, field)).decode("ascii")
                ))

    
