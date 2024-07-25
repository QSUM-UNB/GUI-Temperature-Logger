from ctypes import *
from PyQt6 import QtWidgets
import time, datetime
import threading
import os
import math

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

# Subclass of thread. Allows for GUI interaction + logging/live data
class DeviceReader(threading.Thread):
    def __init__(self, window, interval, isAveraging, fileName, isLogging):
        threading.Thread.__init__(self, daemon=True)
        self.window = window
        self.interval = interval
        self.isAveraging = isAveraging
        self.fileName = fileName
        self.isLogging = isLogging
    def run(self):
        # Allow for live data with or without logging
        if self.isLogging:
            self.__openFile()
        curMonth = int(datetime.datetime.now(datetime.timezone.utc).strftime("%m"))
        lib = cdll.LoadLibrary("C:\Program Files\IVI Foundation\VISA\Win64\Bin\TLTSPB_64.dll")

        #Find out if there are devices connected.
        deviceCount = c_ulong()
        lib.TLTSPB_findRsrc(0, byref(deviceCount))

        #If there are devices connected, determine their names.
        if deviceCount.value >= 1:

            deviceName=create_string_buffer(256)
            
            #If there is only one device, it will be opened. Otherwise, ask which one should be connected.
            if deviceCount.value ==1:
                lib.TLTSPB_getRsrcName(0, 0, deviceName)
            else:
                print("Which device?")
                for i in range(deviceCount.value):
                    lib.TLTSPB_getRsrcName(0, i, deviceName)
                    print('#' + str(i+1) + " " + deviceName.value)
                device_num = input(">>>")
                lib.TLTSPB_getRsrcName(0, (device_num-1), deviceName)
            try:
                t_0 = math.floor(datetime.datetime.now(datetime.timezone.utc).timestamp())
                prevData = [[],[]]
                prevCh1Data = []
                #Initialize the device.
                sessionHandle=c_ulong(0)
                lib.TLTSPB_init(deviceName, 0, 0, byref(sessionHandle))
                while True:
                    if self.isLogging and curMonth < int(datetime.datetime.now(datetime.timezone.utc).strftime("%m")):
                        curDate = datetime.datetime.now(datetime.timezone.utc).strftime("%m.%Y")
                        self.fileName = f"{os.getcwd()}/logs/QSUM_TempLog_{curDate}_1.txt"
                        self.window.browseSaveLine.setText(self.fileName)
                        self.__openFile()
                    #Declare variables and constants for measurements
                    #See TLTSP_Defines.h and TLTSPB.h for definitions of constants
                    temperature=c_longdouble(0.0)
                    humidity=c_longdouble(0.0)
                    resistance = c_double(0.0)
                    attribute = c_short(0)
                    ch_intern = c_ushort(11)
                    ch1_extern = c_ushort(12)

                    #Returns the temperature measured by the internal sensor in the TSP01 in °C.
                    lib.TLTSPB_getTemperatureData(sessionHandle, ch_intern, attribute, byref(temperature))
                    temp = temperature.value

                    #Channel 1
                    #Check if the channel is connected by verifying the resistance is not zero.
                    lib.TLTSPB_getThermRes(sessionHandle, ch1_extern, attribute, byref(resistance))
                    if resistance.value > 0.0:
                        #Returns the temperature measured by external sensor on Ch 1.
                        lib.TLTSPB_measTemperature(sessionHandle, ch1_extern, byref(temperature))

                    #This returns the humidity measured by the internal sensor in the TSP01.
                    lib.TLTSPB_getHumidityData(sessionHandle, attribute, byref(humidity))

                    humid = humidity.value
                    tch1 = round(temperature.value, 2)
                    # Live data display
                    self.window.curTempNumber.display("{:.2f}".format(temp))
                    self.window.curHumidNumber.display("{:.2f}".format(humid))
                    self.window.ch1Number.display("{:.2f}".format(tch1))
                    # Logging procedure
                    if self.isLogging:
                        # Used for averaging (if enabled)
                        prevData[0].append(temp)
                        prevData[1].append(humid)
                        prevCh1Data.append(tch1)
                    # Make sure one interval has passed
                    if self.isLogging and (datetime.datetime.now(datetime.timezone.utc).timestamp() - t_0) >= self.interval:
                        t_0 = math.floor(datetime.datetime.now(datetime.timezone.utc).timestamp())
                        curTime = datetime.datetime.fromtimestamp(t_0).strftime("%b %d %Y\t%H:%M:%S")
                        if self.isAveraging:
                            # Average Interval/0.5 data points
                            avgT = 0
                            avgH = 0
                            avgCh1 = 0
                            # Average
                            for i in range(0, len(prevData[0])):
                                avgT += prevData[0][i]
                                avgH += prevData[1][i]
                                avgCh1 += prevCh1Data[i]
                            avgT /= len(prevData[0])
                            avgH /= len(prevData[1])
                            avgCh1 /= len(prevCh1Data)
                            stdDevT = 0
                            stdDevH = 0
                            stdDevCh1 = 0
                            # Std. Dev
                            for i in range(0, len(prevData[0])):
                                stdDevT += (prevData[0][i] - avgT)**2
                                stdDevH += (prevData[1][i] - avgH)**2
                                stdDevCh1 += (prevCh1Data[i] - avgCh1)**2
                            stdDevT = math.sqrt(stdDevT / len(prevData[0]))
                            stdDevH = math.sqrt(stdDevH / len(prevData[1]))
                            stdDevCh1 = math.sqrt(stdDevCh1 / len(prevCh1Data))
                            # Write into file
                            self.f.write(f"New\t{curTime}\t{avgT:.2f}\t{avgH:.2f}\t{avgCh1:.2f}\t--\t{stdDevT}\t{stdDevH}\t{stdDevCh1}\n")
                        else:
                            # Write into file (with no average)
                            self.f.write(f"New\t{curTime}\t{temp:.2f}\t{humid:.2f}\t{tch1:.2f}\t--\t--\t--\n")
                        # Push all changes to the file
                        self.f.flush()
                        # Reset averaging data
                        prevData = [[],[]]
                        prevCh1Data = []
            finally: # If an exception is thrown to stop the thread
                if self.isLogging:
                    self.f.close()
                #Close the connection to the TSP01 Rev. B.
                lib.TLTSPB_close(sessionHandle)
        else:
            self.window.statusBar.showMessage("No connected TSP01 Rev. B devices were detected. Check connections and installed drivers.", 10)
    def __openFile(self): # Default process to open a file
        if os.path.exists(self.fileName): # Append to an existing file
            self.f = open(self.fileName, "a")
        else: # Prepare a new file
            self.f = open(self.fileName, "w")
            self.f.write("QSUM Temperature and Humidity Monitor Log\n")
            self.f.write("Device:TSP01B\n")
            self.f.write("S/N:M00995273\n")
            self.f.write(f"Measurement Interval:{self.interval}\n")
            self.f.write(f"Begin Data Table\n")
            self.f.write("Time [s]\tDate\tTime\tTemperature[°C]\tHumidity[%]\tTH1[°C]\tTH2[°C]\tStd. Dev Temp\t Std. Dev Humid\t Std. Dev Ch1\n")
            self.f.flush()
            
    # Threading stuff
    def get_id(self):
        if hasattr(self, '_thread_id'):
            return self._thread_id
        for id, thread in threading._active.items():
            if thread is self:
                return id
    def raise_exception(self):
        thread_id = self.get_id()
        res = pythonapi.PyThreadState_SetAsyncExc(thread_id, py_object(SystemExit))
        if res > 1:
            pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
            print('Exception raise failure')