from mcculw import ul
from mcculw.enums import ULRange
from mcculw.ul import ULError
from PyQt6 import QtWidgets
import threading
import ctypes
import time, datetime
import math
import os

# Obsolete and probably very inaccurate
# Uses USB-201 DAQ by Measurement Computing

class ThermistorData(threading.Thread):
    def __init__(self, window, interval, isAveraging, fileName, isLogging):
        threading.Thread.__init__(self, daemon=True)
        self.window = window
        self.interval = interval
        self.isAveraging = isAveraging
        self.fileName = fileName
        self.isLogging = isLogging
    def run(self):
        f = None
        self.__openFile(f)
        curMonth = int(datetime.datetime.now(datetime.timezone.utc).strftime("%m"))
        try:
            t_0 = math.floor(datetime.datetime.now(datetime.timezone.utc).timestamp())
            board_num = 0
            channel = 0
            ai_range = ULRange.BIP10VOLTS
            prevData = []
            while True:
                if curMonth < int(datetime.datetime.now(datetime.timezone.utc).strftime("%m")):
                    curDate = datetime.datetime.now(datetime.timezone.utc).strftime("%m.%Y")
                    self.fileName = self.__openFile(f"{os.getcwd()}/logs/QSUM_TempLog_{curDate}.txt")
                    self.window.browseSaveLine.setText(self.fileName)
                    self.__openFile(f)
                try:
                    # Get a value from the device
                    value = ul.a_in(board_num, channel, ai_range)
                    # Convert the raw value to engineering units
                    eng_units_value = ul.to_eng_units(board_num, ai_range, value)
                    temp = 3988/math.log((10000*((5/eng_units_value)-1))/(10000*math.exp(-3988/298.15))) - 273.15
                    self.window.curTempNumber.display("{:.2f}".format(temp))
                    if self.isLogging:
                        prevData.append(temp)
                    if self.isLogging and (datetime.datetime.now(datetime.timezone.utc).timestamp() - t_0) >= self.interval:
                        t_0 = math.floor(datetime.datetime.now(datetime.timezone.utc).timestamp())
                        curTime = datetime.datetime.fromtimestamp(t_0).strftime("%b %d %Y\t%H:%M:%S")
                        if self.isAveraging:
                            avg = 0
                            avg2 = 0
                            for e in prevData:
                                avg += e
                            avg /= len(prevData)
                            stdDev = 0
                            for e in prevData:
                                stdDev += (e - avg)**2
                            stdDev = math.sqrt(stdDev / len(prevData))
                            f.write(f"New\t{curTime}\t{avg:.2f}\t{0.0:.2f}\t--\t--\t{stdDev}\n")
                        else:
                            f.write(f"New\t{curTime}\t{temp:.2f}\t{0.0:.2f}\t--\t--\t--\n")
                        f.flush()
                        prevData = []
                except ULError as e:
                    # Display the error
                    print("A UL error occurred. Code: " + str(e.errorcode)
                          + " Message: " + e.message)
                except (ValueError, ZeroDivisionError) as e:
                    print("ValueError occurred. Is the Thermistor properly seated? " + e.__str__())
                time.sleep(0.5)
        except Exception as e:
            print("Error occurred. Did you enter the right file name?", e.__str__())
        finally:
            f.close()
    def __openFile(self, f):
        if os.path.exists(self.fileName):
            f = open(self.fileName, "a")
        else:
            f = open(self.fileName, "w")
            f.write("QSUM Temperature and Humidity Monitor Log\n")
            f.write("Device:TSP01B\n")
            f.write("S/N:M00995273\n")
            f.write(f"Measurement Interval:{self.interval}\n")
            f.write(f"Begin Data Table\n")
            f.write("Time [s]\tDate\tTime\tTemperature[°C]\tHumidity[%]\tTH1[°C]\tTH2[°C]\tStd. Dev\n")
            f.flush()
    def get_id(self):
        if hasattr(self, '_thread_id'):
            return self._thread_id
        for id, thread in threading._active.items():
            if thread is self:
                return id
    def raise_exception(self):
        thread_id = self.get_id()
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, ctypes.py_object(SystemExit))
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
            print('Exception raise failure')