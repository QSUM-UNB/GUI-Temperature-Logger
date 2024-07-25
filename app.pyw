from PyQt6 import QtCore, QtWidgets, uic
import matplotlib.axes
import matplotlib.figure
import matplotlib.pyplot
import matplotlib.dates as mdates
from CustomGuiUtils import OldDataParser
from DeviceReader import DeviceReader
from datetime import datetime, timezone
import threading
import pyqtgraph as pg
import sys
import os
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

# TODO
# - Switch from threading to multiprocessing: We gain better speedup across multiple cores at the cost of shared memory
# (some instances should still use threading but data grabbing, for example, benefits from multiprocessing)
# - Implement live data plotting

class MplCanvas(FigureCanvasQTAgg):
    def __init__(self, parent=None, width=100, height=100, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        uic.loadUi("mainwindow.ui", self)
        # ======= Widget Setup =======
        # Analysis Tab
        self.analysisMpl = MplCanvas(self)
        toolbar = NavigationToolbar2QT(self.analysisMpl, self)
        self.analysisWidget.addWidget(toolbar)
        self.analysisWidget.addWidget(self.analysisMpl)
        self.analysisButton.pressed.connect(self.genButtonPressed)
        self.intervalSpin.setValue(10)
        # Hold on to data
        self.curData = None
        self.lines = [[], []]
        self.isLive = True
        # Pre-populate file selection
        curDate = datetime.now(timezone.utc).strftime("%m.%Y")
        self.browseSaveLine.setText(f"{os.getcwd()}/logs/QSUM_TempLog_{curDate}_1.txt")
        self.browseLoadLine.setText(f"{os.getcwd()}/logs/QSUM_TempLog_{curDate}_1.txt")
        # Graph tab
        self.tempLayout.addWidget(NavigationToolbar2QT(self.tempWidget, self))
        self.humidLayout.addWidget(NavigationToolbar2QT(self.humidWidget, self))
        # All Options widgets setup
        self.saveFileButton.pressed.connect(self.saveFile)
        self.loadFileButton.pressed.connect(self.loadFile)
        self.browseSave.pressed.connect(self.browseSavePressed)
        self.browseLoad.pressed.connect(self.browseLoadPressed)
        self.loadFileWidget.setEnabled(False)
        self.loadDateWidget.setEnabled(False)
        self.loadFileRadio.toggled.connect(self.loadFileHasChanged)
        self.loadDateRadio.toggled.connect(self.loadDateHasChanged)
        self.loadFileRadio.toggle()
        self.stopButton.pressed.connect(self.stopButtonPressed)
        # Start live data without logging
        self.dataThread = DeviceReader(self, 10, self.averageCheck.isChecked(), self.browseSaveLine.text(), False)
        self.dataThread.start()
        self.loadThread = None
    def displayData(self):
        # ======= Reset Graphs =======
        self.tempWidget.axes.clear()
        self.humidWidget.axes.clear()
        self.tempWidget.draw()
        self.humidWidget.draw()
        self.lines = [[], []]
        # ======= Reset Table =======
        self.tableWidget.clearContents()
        self.tableWidget.setRowCount(0)
        # ======= Data Collection =======
        resolution = self.resolutionCombo.currentIndex()
        if self.loadDateRadio.isChecked():
            data = OldDataParser.parseDateRange(datetime.strptime(self.startDate.date().toPyDate().strftime("%Y-%m-%d 00:00:00"), "%Y-%m-%d %H:%M:%S").timestamp(), datetime.strptime(self.endDate.date().toPyDate().strftime("%Y-%m-%d 23:59:59"), "%Y-%m-%d %H:%M:%S").timestamp(), resolution, f"{os.getcwd()}/logs")
        else:
            data = OldDataParser.parseData(self, self.browseLoadLine.text(), resolution)
        self.curData = data
        # ======= Table Entry =======
        self.tableWidget.setHorizontalHeaderLabels(["Time [yyyy-mm-dd hh:mm:ss]", "Temperature [°C]", "rel. Humidity [%]", "TH1 [°C]", "TH2 [°C]"])
        # Helper method for threading
        def __tableThreaded(i, arr, offset):
            for k in range(i, len(arr[0]), os.cpu_count()):
                dateItem = QtWidgets.QTableWidgetItem(datetime.fromtimestamp(arr[0][k]).strftime("%Y-%m-%d %H:%M:%S"))
                dateItem.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
                self.tableWidget.setItem(k+offset,0,dateItem)
                arr[0][k] = datetime.fromtimestamp(arr[0][k])
                for j in range(1,5):
                    newItem = QtWidgets.QTableWidgetItem(str(arr[j][k]))
                    newItem.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
                    self.tableWidget.setItem(k+offset,j,newItem)
        totalLen = 0
        for a in data:
            totalLen += len(a[0])
        self.tableWidget.setRowCount(totalLen)
        # Create as many threads as "cpus" detected by the system
        threads = []
        totalLen = 0
        for a in data:
            for i in range(0,os.cpu_count()):
                newThread = threading.Thread(None, __tableThreaded, None, [i, a, totalLen])
                threads.append(newThread)
                newThread.start()
            for e in threads:
                e.join()
            self.plot(a[0], a[1], a[2], a[len(a)-1])
            threads = []
            totalLen += len(a[0])
        # Setup toggle legend
        self.map_legend_to_temp = {}
        self.map_legend_to_humid = {}
        pickradius = 5
        for legend_line, ax_line in zip(self.tempWidget.axes.legend_.get_lines(), self.lines[0]):
            legend_line.set_picker(pickradius)
            self.map_legend_to_temp[legend_line] = ax_line
        for legend_line, ax_line in zip(self.humidWidget.axes.legend_.get_lines(), self.lines[1]):
            legend_line.set_picker(pickradius)
            self.map_legend_to_humid[legend_line] = ax_line
        self.tempWidget.mpl_connect('pick_event', self.on_pick_temp)
        self.humidWidget.mpl_connect('pick_event', self.on_pick_humid)
        self.tempWidget.axes.legend_.set_draggable(True)
        self.humidWidget.axes.legend_.set_draggable(True)
        # Finished
        self.statusBar.clearMessage()
        self.loadThread = None
    # Routine for plotting a set of data
    def plot(self, date, temp, humid, label):
        if len(date) == 0:
            return
        (line1, ) = self.tempWidget.axes.plot(date, temp, label=label)
        (line2, ) = self.humidWidget.axes.plot(date, humid, label=label)
        self.lines[0].append(line1)
        self.lines[1].append(line2)
        self.tempWidget.axes.legend(fancybox=True, shadow=True)
        self.humidWidget.axes.legend(fancybox=True, shadow=True)
        self.tempWidget.axes.grid(True)
        self.humidWidget.axes.grid(True)
        self.tempWidget.draw()
        self.humidWidget.draw()
    # If a Temperature graph line is toggled
    def on_pick_temp(self, event):
        legend_line = event.artist
        if legend_line not in self.map_legend_to_temp:
            return
        ax_line = self.map_legend_to_temp[legend_line]
        visible = not ax_line.get_visible()
        ax_line.set_visible(visible)
        legend_line.set_alpha(1.0 if visible else 0.2)
        self.tempWidget.draw()
    # If a Humidity graph line is toggled
    def on_pick_humid(self, event):
        legend_line = event.artist
        if legend_line not in self.map_legend_to_humid:
            return
        ax_line = self.map_legend_to_humid[legend_line]
        visible = not ax_line.get_visible()
        ax_line.set_visible(visible)
        legend_line.set_alpha(1.0 if visible else 0.2)
        self.humidWidget.draw()
    # Loading a file radio
    def loadFileHasChanged(self, s):
        self.loadFileWidget.setEnabled(s)
    # Loading a date range radio
    def loadDateHasChanged(self, s):
        self.loadDateWidget.setEnabled(s)
    # Start logging button
    def saveFile(self):
        if not self.dataThread == None:
            self.dataThread.raise_exception()
            self.dataThread.join()
        self.dataThread = DeviceReader(self, self.intervalSpin.value(), self.averageCheck.isChecked(), self.browseSaveLine.text(), True)
        self.dataThread.start()
        self.statusLabel.setText("Logging in progress...")
    # Save settings (loading) button
    def loadFile(self):
        if (self.loadThread != None):
            self.statusBar.showMessage("Please wait for data to finish plotting...")
            return
        self.statusBar.showMessage("Plotting data...")
        self.loadThread = threading.Thread(None, self.displayData, None, [])
        self.loadThread.start()
    # Browse for a file in save area
    def browseSavePressed(self):
        getFile = QtWidgets.QFileDialog.getOpenFileName(self, "Save As...", f"{os.getcwd()}/logs", "Text files (*.txt)")
        if len(getFile[0]) > 0:
            self.browseSaveLine.setText(getFile[0])
    # Browse for a file in load area
    def browseLoadPressed(self):
        getFile = QtWidgets.QFileDialog.getOpenFileName(self, "Open...", f"{os.getcwd()}/logs", "Text files (*.txt)")
        if len(getFile[0]) > 0:
            self.browseLoadLine.setText(getFile[0])
    # PSD + Welch button
    def genButtonPressed(self):
        if not self.curData == None:
            self.analysisMpl.axes.clear()
            newThread = threading.Thread(None, OldDataParser.psdAndWelch, None, [self, self.curData, int(self.welchCombo.currentText()), self.intervalSpin.value(), self.axisCombo.currentIndex()])
            newThread.start()
        else: # If no data has been loaded
            QtWidgets.QMessageBox.warning(
                self,
                "Analysis Warning",
                "No data has been loaded. Please load data before using the Analysis tab.",
                buttons=QtWidgets.QMessageBox.StandardButton.Ok,
                defaultButton=QtWidgets.QMessageBox.StandardButton.Ok
            )
    # Stop logging, switch to live only
    def stopButtonPressed(self):
        if not self.dataThread == None:
            self.dataThread.raise_exception()
            self.dataThread.join()
            self.dataThread = None
            self.curTempNumber.display("0")
            self.curHumidNumber.display("0")
        self.dataThread = DeviceReader(self, self.intervalSpin.value(), self.averageCheck.isChecked(), self.browseSaveLine.text(), False)
        self.dataThread.start()
        self.statusLabel.setText("Logging stopped.")

# Starting up stuff
def main():
    app = QtWidgets.QApplication(sys.argv)
    main = MainWindow()
    main.show()
    app.exec()

if __name__ == '__main__':
    main()
