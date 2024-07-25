from PyQt6.QtWidgets import QWidget, QMainWindow
from datetime import datetime
import threading
import os
import scipy.signal as signal
import numpy as np

# Helpful methods for the GUI program. Static class.
class OldDataParser():
    @staticmethod
    def parseData(window:QMainWindow, fileName:str, resolutionIndex:int) -> list:
        # Initialize variables
        resFactor = 1 if resolutionIndex == 0 else 2 if resolutionIndex == 1 else 10
        try: # Make sure files exists (in case user typed it)
            f = open(fileName, encoding="iso-8859-1")
        except:
            window.statusBar.showMessage("ERROR: Does that file exist?", 10)
        threads = []
        i = 0
        arr = []
        for x in f:
            if i < 6: # First 6 lines is always garbage
                pass
            else:
                if (i-6) % resFactor == 0:
                    arr.append(x)
            i += 1
        output = [[None]*len(arr), [None]*len(arr), [None]*len(arr), [None]*len(arr), [None]*len(arr)]
        # Process input (using multithreading)
        for k in range(0,os.cpu_count()):
            newThread = threading.Thread(None, OldDataParser.__oldDataLoopBody, None, [arr, k, output])
            threads.append(newThread)
            newThread.start()
        for e in threads:
            e.join()
        f.close()
        output.append("File 1") # Appends label
        return [output] # Needs to be in a list due to how data is processed
    
    @staticmethod
    def parseDateRange(startDate:float, endDate:float, resolutionIndex:int, logsDir:str) -> list:
        # Initialize search variables
        resFactor = 1 if resolutionIndex == 0 else 2 if resolutionIndex == 1 else 10
        startMonth = int(datetime.fromtimestamp(startDate).strftime("%m"))
        endMonth = int(datetime.fromtimestamp(endDate).strftime("%m"))
        startYear = int(datetime.fromtimestamp(startDate).strftime("%Y"))
        endYear = int(datetime.fromtimestamp(endDate).strftime("%Y"))
        # Empty arrays to append to later
        threads = []
        allArr = []
        arr = []
        eCount = 0
        while startMonth <= endMonth and startYear <= endYear:
            try:
                j = 1
                k = 0
                while True:
                    k = 0
                    ternState = startMonth if startMonth >= 10 else f"0{startMonth}" # I hate 3.10
                    f = open(f"{logsDir}/QSUM_TempLog_{ternState}.{startYear}_{j}.txt", encoding="iso-8859-1") # Standard file name for QSUM data logs
                    for x in f:
                        if k < 6: # First 6 lines of any file is garbage
                            k += 1
                        else:
                            # Tokenize, check date, append to list
                            tokens = x.split("\t")
                            convDateTime = datetime.strptime(f"{tokens[1]} {tokens[2]}", "%b %d %Y %H:%M:%S")
                            if convDateTime.timestamp() >= startDate and convDateTime.timestamp() <= endDate:
                                if eCount % resFactor == 0:
                                    arr.append(x)
                                eCount += 1
                            elif convDateTime.timestamp() > endDate: # Stop if outside date range
                                f.close()
                                allArr.append(arr)
                                arr = []
                                raise Exception
                            eCount += 1
                    f.close()
                    j += 1
                    allArr.append(arr)
                    arr = []
            # We count on trying to open a file that doesn't exist to get to the next one
            except Exception as err:
                startMonth += 1
                if startMonth > 12:
                    startMonth = 1
                    startYear += 1
        # Array for each file's processed output
        allOut = []
        i = 1
        for a in allArr:
            output = [[None]*len(a), [None]*len(a), [None]*len(a), [None]*len(a), [None]*len(a)]
            # Multithreaded to make faster
            for j in range(0,os.cpu_count()):
                newThread = threading.Thread(None, OldDataParser.__oldDataLoopBody, None, [a, j, output])
                threads.append(newThread)
                newThread.start()
            for e in threads: # Wait for all threads before moving to the next file
                e.join()
            output.append(f"File {i}") # Label for graph legend
            i+=1
            allOut.append(output)
            threads = []
        return allOut
    
    # Method used for both collection methods. Allows for multithreading
    @staticmethod
    def __oldDataLoopBody(arr, i, outArr):
        for j in range(i, len(arr), os.cpu_count()):
            x = arr[j]
            tokens = x.split("\t")
            dateString = tokens[1] + " " + tokens[2]
            convDateTime = datetime.strptime(dateString, "%b %d %Y %H:%M:%S")
            outArr[0][j] = convDateTime.timestamp()
            outArr[1][j] = float(tokens[3])
            outArr[2][j] = float(tokens[4])
            outArr[3][j] = tokens[5]
            outArr[4][j] = tokens[6][0:len(tokens[6])-1]
    
    # Perform + Display a PSD and Welch
    @staticmethod
    def psdAndWelch(window:QMainWindow, data:list, splitFactor:int, interval:int, axis:int) -> None:
        # We want the largest discrete chunk of data
        comboList = []
        for a in data:
            if len(a[1]) > len(comboList):
                comboList = a[1]

        f_p, P_p = signal.periodogram(comboList, fs=1/interval, window='hann', scaling='density')
        # Use a reverse list to reduce noise in lower and higher frequencies
        mirrorList = comboList
        mirrorList.reverse()
        distList = mirrorList + comboList + mirrorList

        # f_w, P_w = OldDataParser.__pseudo_welch(comboList, splitFactor, interval)
        f_w, P_w = signal.welch(distList, fs=1/interval, scaling='density', nperseg=len(distList)/splitFactor)

        # Frequencies get multiplied by 3600 to get 1/h (instead of 1/s)
        ## User may select which axis shows by default, switch statement to run matching method
        match axis:
            case 0:
                window.analysisMpl.axes.plot(f_p*3600, np.sqrt(P_p), label="PSD")
                window.analysisMpl.axes.plot(f_w*3600, np.sqrt(P_w), label="Welch")
            case 1:
                window.analysisMpl.axes.semilogx(f_p*3600, np.sqrt(P_p), label="PSD")
                window.analysisMpl.axes.semilogx(f_w*3600, np.sqrt(P_w), label="Welch")
            case 2:
                window.analysisMpl.axes.semilogy(f_p*3600, np.sqrt(P_p), label="PSD")
                window.analysisMpl.axes.semilogy(f_w*3600, np.sqrt(P_w), label="Welch")
            case 3:
                window.analysisMpl.axes.loglog(f_p*3600, np.sqrt(P_p), label="PSD")
                window.analysisMpl.axes.loglog(f_w*3600, np.sqrt(P_w), label="Welch")
        # Display results
        window.analysisMpl.axes.set_xlabel("1/3600 Hz")
        window.analysisMpl.axes.set_ylabel("C√h")
        window.analysisMpl.axes.grid(True)
        window.analysisMpl.axes.legend()
        window.analysisMpl.draw()
    
    # No longer used; splits data sets and averages the PSD of each split
    # Current problem: Noise reduction in high frequencies but not in low
    @staticmethod
    def __pseudo_welch(data, splitFactor, interval):
        maxData = len(data) - (len(data) % splitFactor)
        bins = [[]]*splitFactor
        for i in range(0, splitFactor):
            bins[i] = data[i:maxData:splitFactor]
        fws = None
        pws_avg = None
        for i in range(0,splitFactor):
            fws, pws = signal.periodogram(bins[i], fs=1/(interval*splitFactor), window='hann', scaling='density')
            if i == 0:
                pws_avg = pws
            else:
                pws_avg += pws
            
        return (fws, pws_avg/splitFactor)
