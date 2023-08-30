# Import necessary PyQt5 and pyqtgraph modules
from PyQt5.QtWidgets import (QApplication, QVBoxLayout, QPushButton, QWidget, QLabel, QHBoxLayout,
                             QTabWidget, QLineEdit, QFormLayout, QComboBox, QTableWidget, QScrollBar,
                             QTableWidgetItem, QAbstractScrollArea, QSizePolicy, QSplitter, QSpacerItem, QGridLayout, QCheckBox, QFrame)

from PyQt5.QtCore import QTimer, pyqtSignal, QThread, Qt
from PyQt5.QtGui import QFont
import pyqtgraph as pg
from PyQt5.QtWidgets import QFileDialog
# Import other necessary modules
import pyvisa
import threading
import time
import numpy as np
from unittest.mock import MagicMock
from scipy import constants, optimize
from scipy.stats import linregress
from numpy import polyfit
from scipy.optimize import curve_fit

def diode_equation(voltage, Rs, Rsh, n, Is):
    return Is * (np.exp((voltage + Rs * Is) / (n * 25.85)) - 1) - voltage / Rsh


class MockKeithley:
    def __init__(self):
        self.write = MagicMock()
        self.query = MagicMock(return_value='0.0')


class KeithleyApp(QWidget):
    def __init__(self):
        super().__init__()
        self.resize(800, 800)  # resize the main window
        self.plotWidget = None
        self.ivPlotWidget = None
        self.rm = pyvisa.ResourceManager()
        self.keithley = None
        self.stop = True
        self.worker = None
        self.initUI()


    def initUI(self):

        # Initialize UI elements here

        small_font = QFont()
        small_font.setPointSize(10)

        # Vertical Box Layout for Connect/Disconnect Buttons and Connection Status

        vbox = QVBoxLayout()
        hbox = QHBoxLayout()
        vbox2 = QVBoxLayout()
        hbox.setAlignment(Qt.AlignLeft)



        self.connectButton = QPushButton('Connect to Keithley', self)
        self.connectButton.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.connectButton.clicked.connect(self.connect_keithley)
        hbox.addWidget(self.connectButton)

        self.disconnectButton = QPushButton('Disconnect from Keithley', self)
        self.disconnectButton.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.disconnectButton.clicked.connect(self.disconnect_keithley)
        hbox.addWidget(self.disconnectButton)

        self.connectionStatus = QLabel('Not Connected', self)
        self.connectionStatus.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.connectionStatus.setStyleSheet("color: red")
        hbox.addWidget(self.connectionStatus)

        vbox.addLayout(vbox2)
        vbox = QVBoxLayout()
        vbox.addLayout(hbox)

        # Tab Widget

        self.tabWidget = QTabWidget()

        # Tab 1: Live Current Plot

        self.tab1 = QWidget()

        # Creating a Grid Layout for below the plot

        # Tab 2: IV Measurements

        self.tab2 = QWidget()
        self.tab2.layout = QVBoxLayout()
        plotHBox = QHBoxLayout()  # Create a new horizontal box layout for the plots
        self.ivPlotWidget = pg.PlotWidget(viewBox=pg.ViewBox(border='k'))
        self.ivPlotWidget.setBackground('w')
        self.ivPlotWidget.setTitle('IV Plot')
        self.ivPlotWidget.setSizePolicy(QSizePolicy.Expanding,
                                        QSizePolicy.Expanding)  # Let the plot expand both horizontally and vertically

        plotHBox.addWidget(self.ivPlotWidget)  # Add to the horizontal box layout

        self.powerPlotWidget = pg.PlotWidget(viewBox=pg.ViewBox(border='k'))
        self.powerPlotWidget.setTitle('Power Plot')
        self.powerPlotWidget.setBackground('w')
        self.powerPlotWidget.setSizePolicy(QSizePolicy.Expanding,
                                           QSizePolicy.Expanding)  # Let the plot expand both horizontally and vertically

        plotHBox.addWidget(self.powerPlotWidget)  # Add to the horizontal box layout

        self.tab2.layout.addLayout(plotHBox)  # Add the horizontal layout to the tab2's vertical layout
        self.layout_inputs = QGridLayout()
        self.layout_inputs.addWidget(QLabel('Start Voltage (V):'), 0, 0)
        self.startVoltageEdit = QLineEdit('-1')
        self.startVoltageEdit.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.layout_inputs.addWidget(self.startVoltageEdit, 0, 1)
        self.layout_inputs.addWidget(QLabel('Stop Voltage (V):'), 1, 0)
        self.stopVoltageEdit = QLineEdit('1')
        self.stopVoltageEdit.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.layout_inputs.addWidget(self.stopVoltageEdit, 1, 1)
        self.layout_inputs.addWidget(QLabel('Step Voltage (V):'), 2, 0)
        self.stepVoltageEdit = QLineEdit('0.05')
        self.stepVoltageEdit.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.layout_inputs.addWidget(self.stepVoltageEdit, 2, 1)
        horizontalSpacer = QSpacerItem(600, 1, QSizePolicy.Minimum)

        self.layout_inputs.addItem(horizontalSpacer, 0, 3)

        self.ivStartButton = QPushButton('Start IV Measurement', self)
        self.ivStartButton.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.ivStartButton.clicked.connect(self.start_iv_measurement)
        self.layout_inputs.addWidget(self.ivStartButton, 0, 2)

        self.ivStopButton = QPushButton('Stop IV Measurement', self)
        self.ivStopButton.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.ivStopButton.clicked.connect(self.stop_iv_measurement)
        self.layout_inputs.addWidget(self.ivStopButton, 1, 2)

        self.layout_inputs.addWidget(QLabel('Select IV Channel:'), 3, 0)
        self.ivStopButton.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.tab2ChannelComboBox = QComboBox()
        self.tab2ChannelComboBox.addItems(['A', 'B'])
        self.layout_inputs.addWidget(self.tab2ChannelComboBox, 3, 1)

        self.saveDataButton = QPushButton('Save Data', self)
        self.saveDataButton.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.saveDataButton.clicked.connect(self.save_data)
        self.layout_inputs.addWidget(self.saveDataButton, 2, 2)

        self.tab2.layout.addLayout(self.layout_inputs)
        self.vocDisplay = QLabel()
        self.tab2.layout.addWidget(self.vocDisplay)

        self.iscDisplay = QLabel()
        self.tab2.layout.addWidget(self.iscDisplay)

        self.ffDisplay = QLabel()
        self.tab2.layout.addWidget(self.ffDisplay)

        self.pceDisplay = QLabel()
        self.tab2.layout.addWidget(self.pceDisplay)

        self.mppDisplay = QLabel()
        self.tab2.layout.addWidget(self.mppDisplay)

        self.ivTableWidget = QTableWidget()
        self.ivTableWidget.setColumnCount(9)
        self.ivTableWidget.setHorizontalHeaderLabels(
            ['Voltage (V)', 'Current (A)', 'Voc', 'Isc', 'FF', 'Mpp', 'Vmp', 'Imp', 'PCE'])

        self.ivTableWidget.setVerticalScrollBar(QScrollBar())
        self.ivTableWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # self.tab2.layout.addWidget(self.ivTableWidget)

        self.layout_inputs.addWidget(self.ivTableWidget, 0, 3, 20, 20)
        self.layout_inputs.setColumnStretch(3, 5)
        self.tab2.setLayout(self.tab2.layout)

        vbox.addWidget(self.tabWidget)
        self.setLayout(vbox)
        self.setWindowTitle('Keithley SourceMeter Interface')

        # Added new input for irradiance

        self.layout_inputs.addWidget(QLabel('Irradiance (W/m2):'), 4, 0)
        self.irradianceEdit = QLineEdit('1000')  # Default irradiance value is set to 1000
        self.layout_inputs.addWidget(self.irradianceEdit, 4, 1)
        self.irradianceEdit.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # Added new input for irradiance

        self.layout_inputs.addWidget(QLabel('Area (m2):'), 5, 0)
        self.areaEdit = QLineEdit('0.00000484')  # Default irradiance value is set to 1000
        self.layout_inputs.addWidget(self.areaEdit, 5, 1)
        self.areaEdit.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.layout_inputs.setAlignment(Qt.AlignLeft)
        self.tabWidget.addTab(self.tab2, "IV Measurements")
        self.tabWidget.addTab(self.tab1, "F factor")
        self.layout_inputs.addWidget(QLabel('Measurement Direction:'), 6, 0)
        self.directionComboBox = QComboBox()
        self.directionComboBox.addItems(['Forward', 'Reverse', 'Both'])
        self.layout_inputs.addWidget(self.directionComboBox, 6, 1)

        # For IV plot

        self.clearIVPlotButton = QPushButton('Clear Plots', self)
        self.clearIVPlotButton.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.clearIVPlotButton.clicked.connect(self.clear_iv_plot)
        self.layout_inputs.addWidget(self.clearIVPlotButton, 3, 2)

        self.line2 = QFrame()
        self.line2.setFrameShape(QFrame.HLine)
        self.line2.setFrameShadow(QFrame.Sunken)
        self.layout_inputs.addWidget(self.line2, 7, 0, 1, 3)


        self.fFactorLabel = QLabel('F factor', self)
        self.fFactorLabel.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.fFactorLineEdit = QLineEdit(self)
        self.fFactorLineEdit.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.layout_inputs.addWidget(self.fFactorLabel, 9, 0)
        self.layout_inputs.addWidget(self.fFactorLineEdit, 9, 1)

        self.mFactorLabel = QLabel('M factor', self)
        self.mFactorLabel.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.mFactorLineEdit = QLineEdit(self)
        self.mFactorLineEdit.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.layout_inputs.addWidget(self.mFactorLabel, 10, 0)
        self.layout_inputs.addWidget(self.mFactorLineEdit, 10, 1)

        self.IscLabel = QLabel('Isc', self)
        self.IscLabel.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.IscLineEdit = QLineEdit(self)
        self.IscLineEdit.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.layout_inputs.addWidget(self.IscLabel, 11, 0)
        self.layout_inputs.addWidget(self.IscLineEdit, 11, 1)

        self.tab1ChannelComboBox = QComboBox()
        self.tab1channelLabel = QLabel('Select Current Channel', self)
        self.tab1channelLabel.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.tab1ChannelComboBox.addItems(['A', 'B'])
        self.tab1ChannelComboBox.setCurrentIndex(1)
        self.layout_inputs.addWidget(self.tab1channelLabel, 12, 0)
        self.layout_inputs.addWidget(self.tab1ChannelComboBox, 12, 1)

        # Start Button

        self.startButton = QPushButton('Start Current', self)
        self.startButton.clicked.connect(self.start_plotting)
        self.layout_inputs.addWidget(self.startButton, 9, 2)

        # Stop Button

        self.stopButton = QPushButton('Stop Current', self)
        self.layout_inputs.addWidget(self.stopButton, 10, 2)
        self.stopButton.clicked.connect(self.stop_plotting)

        hbox.addWidget(self.connectionStatus)

        # Adding a new line edit for displaying the Keithley's info
        self.keithleyInfoLineEdit = QLineEdit(self)
        self.keithleyInfoLineEdit.setReadOnly(True)  # make it read-only
        self.keithleyInfoLineEdit.setPlaceholderText("Keithley Info will be displayed here...")
        hbox.addWidget(self.keithleyInfoLineEdit)

        # Checkbox for using test dataset
        self.useTestDataCheckbox = QCheckBox("Use Test Dataset", self)
        self.useTestDataCheckbox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        hbox.addWidget(self.useTestDataCheckbox)

        self.FFactorCheckbox = QCheckBox("Use F Factor", self)
        self.FFactorCheckbox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.FFactorCheckbox.stateChanged.connect(self.use_F_Factor)
        self.layout_inputs.addWidget(self.FFactorCheckbox, 8, 0, 1, 3)
        self.FFactorCheckbox.setChecked(True)

    def clear_iv_plot(self):
        self.ivPlotWidget.clear()
        self.powerPlotWidget.clear()

    def use_F_Factor(self):
        if self.FFactorCheckbox.isChecked():
            self.IscLineEdit.setEnabled(True)
            self.IscLabel.setEnabled(True)
            self.fFactorLineEdit.setEnabled(True)
            self.mFactorLabel.setEnabled(True)
            self.tab1ChannelComboBox.setEnabled(True)
            self.tab1channelLabel.setEnabled(True)
            self.startButton.setEnabled(True)
            self.stopButton.setEnabled(True)
            self.mFactorLineEdit.setEnabled(True)
            self.fFactorLabel.setEnabled(True)
        else:
            self.IscLineEdit.setEnabled(False)
            self.IscLabel.setEnabled(False)
            self.fFactorLabel.setEnabled(False)
            self.mFactorLabel.setEnabled(False)
            self.tab1ChannelComboBox.setEnabled(False)
            self.tab1channelLabel.setEnabled(False)
            self.startButton.setEnabled(False)
            self.stopButton.setEnabled(False)
            self.fFactorLineEdit.setEnabled(False)
            self.mFactorLineEdit.setEnabled(False)

    def search_for_keithley(self):
        """Search for a Keithley device with a specific ID pattern."""
        keithley_id_pattern = "USB0::0x05E6::0x2614::*::INSTR"  # This pattern will match any Keithley device with the specified prefix

        # List all connected VISA resources
        resources = self.rm.list_resources()

        for resource in resources:
            if resource.startswith(keithley_id_pattern):
                return resource  # Return the found Keithley ID
        return None

    def connect_keithley(self):
        if self.useTestDataCheckbox.isChecked():
            # Use test dataset
            self.keithley = MockKeithley()
            self.keithley_1 = MockKeithley()
            if self.keithley:
                self.keithleyInfoLineEdit.setText('Testing with Mock keithley')
            else:
                pass

        else:
            # Use real dataset
            self.keithley = self.rm.open_resource('USB0::0x05E6::0x2614::4577888::INSTR')
            self.keithley_1 = self.rm.open_resource('USB0::0x05E6::0x2614::4577888::INSTR')
            if self.keithley:
                self.keithleyInfoLineEdit.setText('USB0::0x05E6::0x2614::4577888::INSTR')
            else:
                pass

        # self.keithley_1 = self.search_for_keithley()


        # self.keithley = self.rm.open_resource('USB0::0x05E6::0x2614::4577888::INSTR')
        #
        # self.keithley_1 = self.rm.open_resource('USB0::0x05E6::0x2614::4577888::INSTR')



        self.keithley.write("*RST")
        self.keithley.write('smua.reset()')
        self.keithley.write('smua.source.func = smua.OUTPUT_DCVOLTS')
        self.keithley.write('smua.source.levelv = 0')
        self.keithley.write('smua.source.limiti = 105e-6')
        self.keithley.write('smua.measure.autozero = smua.AUTOZERO_ONCE')
        self.keithley.write('smua.source.output = smua.OUTPUT_ON')
        self.connectionStatus.setText('Connected')
        self.connectionStatus.setStyleSheet("color: green")

        # Get the selected channel

        selected_channel_1 = self.tab2ChannelComboBox.currentText().lower()

        # Set the channel based on the selected channel

        self.keithley.write(f'smu{selected_channel_1}.reset()')
        self.keithley.write(f'smu{selected_channel_1}.source.func = smua.OUTPUT_DCVOLTS')
        self.keithley.write(f'smu{selected_channel_1}.source.levelv = 0')
        self.keithley.write(f'smu{selected_channel_1}.source.limiti = 105e-3')
        self.keithley.write(f'smu{selected_channel_1}.measure.autozero = smua.AUTOZERO_ONCE')
        self.keithley.write(f'smu{selected_channel_1}.source.output = smua.OUTPUT_ON')
        selected_channel_2 = self.tab1ChannelComboBox.currentText().lower()

        # self.keithley_1 = self.rm.open_resource('USB0::0x05E6::0x2614::4577888::INSTR')

        self.keithley_1.write(f'smub.reset()')
        self.keithley_1.write(f'smub.source.func = smu{selected_channel_2}.OUTPUT_DCVOLTS')
        self.keithley_1.write(f'smu{selected_channel_2}.source.levelv = 0')
        self.keithley_1.write(f'smu{selected_channel_2}.source.limiti = 105e-3')
        self.keithley_1.write(f'smu{selected_channel_2}.measure.autozero = smu{selected_channel_2}.AUTOZERO_ONCE')
        self.keithley_1.write(f'smu{selected_channel_2}.source.output = smu{selected_channel_2}.OUTPUT_ON')

    def start_plotting(self):

        selected_channel = self.tab1ChannelComboBox.currentText().lower()
        self.stop = False
        self.plot_thread = threading.Thread(target=self.plotting_loop)
        self.plot_thread.start()

    def stop_plotting(self):

        self.stop = True
        self.plot_thread.join()
        # self.keithley.close()

    def plotting_loop(self):

        while not self.stop:
            if self.tab1ChannelComboBox.currentText().lower() == 'a':

                current = float(self.mFactorLineEdit.text()) * float(

                self.keithley_1.query('print(smua.measure.i())')) / float(self.IscLineEdit.text())

            if self.tab1ChannelComboBox.currentText().lower() == 'b':

                current = float(self.mFactorLineEdit.text()) * float(

                self.keithley_1.query('print(smub.measure.i())')) / float(self.IscLineEdit.text())
            print(f'Measured current: {current} A')

            self.fFactorLineEdit.setText(str(current))
            time.sleep(1)

    def start_iv_measurement(self):

        selected_channel = self.tab2ChannelComboBox.currentText().lower()
        if self.worker is not None:
            self.worker.stop()
        start_voltage = float(self.startVoltageEdit.text())
        stop_voltage = float(self.stopVoltageEdit.text())
        step_voltage = float(self.stepVoltageEdit.text())
        measurement_direction = self.directionComboBox.currentText()
        self.worker = IVWorker(self.keithley, start_voltage, stop_voltage, step_voltage, measurement_direction)
        self.worker.data_acquired.connect(self.update_iv_plot)
        self.connect_keithley()
        self.worker.start()



    def update_iv_plot(self, data):

        # Calculate Voc, Isc, FF, PCE based on the measured IV curve

        # This is a very simplified calculation and might not be accurate for real devices


        self.data = data
        if self.useTestDataCheckbox.isChecked():
            # Use test dataset
            data = [[-1, -0.95918, -0.91837, -0.87755, -0.83673, -0.79592, -0.7551, -0.71429, -0.67347, -0.63265, -0.59184,
                     -0.55102, -0.5102, -0.46939, -0.42857, -0.38776, -0.34694, -0.30612, -0.26531, -0.22449, -0.18367,
                     -0.14286, -0.10204, -0.06122, -0.02041, 0, 0.02041, 0.06122, 0.10204, 0.14286, 0.18367, 0.22449,
                     0.26531,
                     0.30612, 0.34694, 0.38776, .42857, 0.45066, 0.46939, 0.5102, 0.55102, 0.59184, 0.63265, 0.67347,
                     0.71429,
                     0.7551, 0.79592, 0.83673, 0.87755, 0.91837, 0.95918, 1],
                    [-0.00129, -0.0013, -0.0013, -0.00129, -0.00129, -0.00129, -0.0013, -0.0013, -0.00129, -0.00129,
                     -0.00129, -0.00129, -0.00129, -0.00129, -0.00129, -0.00129, -0.00129, -0.00128, -0.00128, -0.00129,
                     -0.00129, -0.00128, -0.00128, -0.00128, -0.00128, -0.00127, -0.00128, -0.00127, -0.00126, -0.00125,
                     -0.00122, -0.00119, -0.00114, -0.00104, -9.00585E-4, -6.54968E-4, -2.74127E-4, 4.6524E-6, 2.94651E-4,
                     0.0011, 0.00215, 0.00351, 0.00522, 0.00742, 0.01038, 0.01445, 0.02002, 0.02744, 0.03681, 0.0481,
                     0.06119,
                     0.0759]]  # Store data for saving
        else:
            # Use real dataset
            pass

        voltages = np.array(data[0])
        currents = np.array(data[1])

        y_intercept = currents[np.argmin(np.abs(voltages))]
        x_intercept = voltages[np.argmin(np.abs(currents))]
        power = voltages * currents
        # voc = x_intercept  # Open-circuit voltage
        # isc = y_intercept  # Short-circuit current
        isc = currents[np.argmin(np.abs(voltages))]  # Short-circuit current
        voc = voltages[np.argmin(np.abs(currents))]  # Open-circuit voltage

        power = voltages * currents
        max_power = abs(np.min(power))  # Maximum power
        mpp_voltage = voltages[np.argmin(power)]  # Voltage at MPP
        mpp_current = currents[np.argmin(power)]  # Current at MPP
        ff = abs(max_power) / abs(voc * isc)  # Fill factor
        input_power = float(self.irradianceEdit.text())  # W/m^2
        area = float(self.areaEdit.text())
        pce = abs(ff*isc*voc) / abs(input_power*area) * 100  # Power conversion efficiency


        # Initial guess for parameters
        # initial_guess = [3, 766, 1, 1e-9]  # Rs, Rsh, n, Is
        #
        # # Fit the diode equation to the data
        # params, _ = curve_fit(diode_equation, voltages, currents, p0=initial_guess)
        #
        # Rs_fit, Rsh_fit, n_fit, Is_fit = params
        #
        # print("Rs:", Rs_fit)
        # print("Rsh:", Rsh_fit)

        # Update the IV plot and the parameter displays
        pen = pg.mkPen('b', width=3)
        self.ivPlotWidget.plot(voltages, currents, pen=pen)
        pen = pg.mkPen('g', width=3)
        self.powerPlotWidget.plot(voltages, power, pen=pen)
        # self.vocDisplay.setText(f'Voc: {voc:.9f} V')
        # self.iscDisplay.setText(f'Isc: {isc:.9f} A')
        # self.ffDisplay.setText(f'FF: {ff:.9f}')
        # self.pceDisplay.setText(f'PCE: {pce:.9f}')
        # self.mppDisplay.setText(f'MPP: {mpp_voltage:.9f} V, {mpp_current:.9f} A, {max_power:.9f} W')

        # Record data in the table

        self.ivTableWidget.setRowCount(len(voltages))
        for i, (voltage, current) in enumerate(zip(voltages, currents)):
            self.ivTableWidget.setItem(i, 0, QTableWidgetItem(str(voltage)))
            self.ivTableWidget.setItem(i, 1, QTableWidgetItem(str(current)))
            print(i)
        self.ivTableWidget.setItem(0, 2, QTableWidgetItem(str(voc)))
        self.ivTableWidget.setItem(0, 3, QTableWidgetItem(str(isc)))
        self.ivTableWidget.setItem(0, 4, QTableWidgetItem(str(ff)))
        self.ivTableWidget.setItem(0, 5, QTableWidgetItem(str(max_power)))
        self.ivTableWidget.setItem(0, 6, QTableWidgetItem(str(mpp_voltage)))
        self.ivTableWidget.setItem(0, 7, QTableWidgetItem(str(mpp_current)))
        self.ivTableWidget.setItem(0, 8, QTableWidgetItem(str(f'{pce:.3f}')))


    def stop_iv_measurement(self):

        if self.worker is not None:
            self.worker.stop()

    def save_data(self):
        if self.data is not None:
            # Create a dialog for the user to choose a filename and location
            options = QFileDialog.Options()
            fileName, _ = QFileDialog.getSaveFileName(self, "QFileDialog.getSaveFileName()", "IV.txt",
                                                      "All Files (*);;Text Files (*.txt)", options=options)
            if fileName:
                # Save data to a file
                with open(fileName, 'w') as f:
                    # Write Voltage and Current
                    column_names = ["Voltage", "Current"]
                    f.write('\t'.join(column_names) + '\n')  # write column names

                    for i in range(self.ivTableWidget.rowCount()):
                        voltage = self.ivTableWidget.item(i, 0).text()
                        current = self.ivTableWidget.item(i, 1).text()
                        f.write('\t'.join([voltage, current]) + '\n')

                    # Write Voc, Isc, FF, Max_Power, MPP_Voltage, MPP_Current, PCE
                    parameters = ["Voc", "Isc", "FF", "Max_Power", "MPP_Voltage", "MPP_Current", "PCE"]
                    for j, param in enumerate(parameters, start=2):
                        value = self.ivTableWidget.item(0, j).text()
                        f.write(f"{param}: {value}\n")

    def disconnect_keithley(self):

        if self.keithley:
            self.keithley.write('smua.source.output = smua.OUTPUT_OFF')
            self.keithley = None
            self.connectionStatus.setText('Not Connected')
            self.connectionStatus.setStyleSheet("color: red")
            self.keithleyInfoLineEdit.clear()


class IVWorker(QThread):
    data_acquired = pyqtSignal(list)

    def __init__(self, keithley, start_voltage, stop_voltage, step_voltage, direction):
        super().__init__()
        self.keithley = keithley
        self.start_voltage = start_voltage
        self.stop_voltage = stop_voltage
        self.step_voltage = step_voltage
        self.direction = direction
        self._running = False

    def run(self):
        self._running = True
        # Forward measurement
        if self.direction in ['Forward', 'Both']:
            current_values = []
            voltage_values = np.arange(self.start_voltage, self.stop_voltage, self.step_voltage)
            for voltage in voltage_values:
                print('Voltage', voltage)
                if not self._running:
                    break
                self.keithley.write(f'smua.source.levelv = {voltage}')
                time.sleep(0.5)  # Let the system stabilize; adjust the delay as necessary
                current = float(self.keithley.query('print(smua.measure.i())'))
                current_values.append(current)
                print('current', current)
                # self.keithley.write('smua.source.output = smua.OUTPUT_OFF')  # Turn off the output

            time.sleep(0.5)  # Wait for the system to stabilize after turning off the output
            self.data_acquired.emit([voltage_values[:len(current_values)], current_values])

        # Reverse measurement
        if self.direction in ['Reverse', 'Both']:
            current_values = []
            # Swap start and stop voltages
            temp = self.start_voltage
            self.start_voltage = self.stop_voltage
            self.stop_voltage = temp
            self.step_voltage = -self.step_voltage
            voltage_values = np.arange(self.start_voltage, self.stop_voltage, self.step_voltage)
            for voltage in voltage_values:
                print('Reverse Voltage', voltage)
                if not self._running:
                    break
                self.keithley.write(f'smua.source.levelv = {voltage}')
                time.sleep(0.5)  # Let the system stabilize; adjust the delay as necessary
                current = float(self.keithley.query('print(smua.measure.i())'))
                current_values.append(current)
                print('current', current)
                # self.keithley.write('smua.source.output = smua.OUTPUT_OFF')  # Turn off the output

            time.sleep(0.5)  # Wait for the system to stabilize after turning off the output
            self.data_acquired.emit([voltage_values[:len(current_values)], current_values])

        self.keithley.write('smua.source.output = smua.OUTPUT_OFF')  # Turn off the output
    def stop(self):
        self._running = False


def main():
    app = QApplication([])
    keithleyApp = KeithleyApp()
    keithleyApp.show()
    app.exec_()


if __name__ == '__main__':
    main()