# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main_window.ui'
##
## Created by: Qt User Interface Compiler version 6.11.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QComboBox, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QSpacerItem, QTabWidget, QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1238, 612)
        self.verticalLayout_2 = QVBoxLayout(MainWindow)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.groupBox = QGroupBox(MainWindow)
        self.groupBox.setObjectName(u"groupBox")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.groupBox.sizePolicy().hasHeightForWidth())
        self.groupBox.setSizePolicy(sizePolicy)
        self.gridLayout = QGridLayout(self.groupBox)
        self.gridLayout.setObjectName(u"gridLayout")
        self.label_3 = QLabel(self.groupBox)
        self.label_3.setObjectName(u"label_3")

        self.gridLayout.addWidget(self.label_3, 0, 2, 1, 1)

        self.label = QLabel(self.groupBox)
        self.label.setObjectName(u"label")

        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)

        self.parity_select = QComboBox(self.groupBox)
        self.parity_select.addItem("")
        self.parity_select.addItem("")
        self.parity_select.addItem("")
        self.parity_select.setObjectName(u"parity_select")

        self.gridLayout.addWidget(self.parity_select, 1, 3, 1, 1)

        self.label_5 = QLabel(self.groupBox)
        self.label_5.setObjectName(u"label_5")

        self.gridLayout.addWidget(self.label_5, 0, 4, 1, 1)

        self.baudrate_select = QComboBox(self.groupBox)
        self.baudrate_select.addItem("")
        self.baudrate_select.addItem("")
        self.baudrate_select.addItem("")
        self.baudrate_select.addItem("")
        self.baudrate_select.addItem("")
        self.baudrate_select.setObjectName(u"baudrate_select")

        self.gridLayout.addWidget(self.baudrate_select, 1, 1, 1, 1)

        self.label_2 = QLabel(self.groupBox)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout.addWidget(self.label_2, 1, 0, 1, 1)

        self.label_4 = QLabel(self.groupBox)
        self.label_4.setObjectName(u"label_4")

        self.gridLayout.addWidget(self.label_4, 1, 2, 1, 1)

        self.port_select = QComboBox(self.groupBox)
        self.port_select.setObjectName(u"port_select")
        self.port_select.setEditable(True)

        self.gridLayout.addWidget(self.port_select, 0, 1, 1, 1)

        self.stopbit_select = QComboBox(self.groupBox)
        self.stopbit_select.addItem("")
        self.stopbit_select.addItem("")
        self.stopbit_select.setObjectName(u"stopbit_select")

        self.gridLayout.addWidget(self.stopbit_select, 0, 3, 1, 1)

        self.local_btn = QPushButton(self.groupBox)
        self.local_btn.setObjectName(u"local_btn")

        self.gridLayout.addWidget(self.local_btn, 1, 6, 1, 1)

        self.local_select = QComboBox(self.groupBox)
        self.local_select.setObjectName(u"local_select")

        self.gridLayout.addWidget(self.local_select, 0, 5, 1, 1)


        self.horizontalLayout.addWidget(self.groupBox)

        self.groupBox_2 = QGroupBox(MainWindow)
        self.groupBox_2.setObjectName(u"groupBox_2")
        sizePolicy.setHeightForWidth(self.groupBox_2.sizePolicy().hasHeightForWidth())
        self.groupBox_2.setSizePolicy(sizePolicy)
        self.gridLayout_2 = QGridLayout(self.groupBox_2)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.label_8 = QLabel(self.groupBox_2)
        self.label_8.setObjectName(u"label_8")

        self.gridLayout_2.addWidget(self.label_8, 0, 2, 1, 1)

        self.label_6 = QLabel(self.groupBox_2)
        self.label_6.setObjectName(u"label_6")

        self.gridLayout_2.addWidget(self.label_6, 0, 0, 1, 1)

        self.remote_select = QComboBox(self.groupBox_2)
        self.remote_select.setObjectName(u"remote_select")

        self.gridLayout_2.addWidget(self.remote_select, 0, 3, 1, 1)

        self.label_7 = QLabel(self.groupBox_2)
        self.label_7.setObjectName(u"label_7")

        self.gridLayout_2.addWidget(self.label_7, 1, 0, 1, 1)

        self.remote_btn = QPushButton(self.groupBox_2)
        self.remote_btn.setObjectName(u"remote_btn")

        self.gridLayout_2.addWidget(self.remote_btn, 1, 4, 1, 1)

        self.host_select = QComboBox(self.groupBox_2)
        self.host_select.setObjectName(u"host_select")
        self.host_select.setEditable(True)

        self.gridLayout_2.addWidget(self.host_select, 0, 1, 1, 1)

        self.remote_port_select = QComboBox(self.groupBox_2)
        self.remote_port_select.addItem("")
        self.remote_port_select.addItem("")
        self.remote_port_select.setObjectName(u"remote_port_select")
        self.remote_port_select.setEditable(True)

        self.gridLayout_2.addWidget(self.remote_port_select, 1, 1, 1, 1)


        self.horizontalLayout.addWidget(self.groupBox_2)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)


        self.verticalLayout_2.addLayout(self.horizontalLayout)

        self.devices_group = QGroupBox(MainWindow)
        self.devices_group.setObjectName(u"devices_group")
        self.devices_group.setEnabled(True)
        self.devices_group.setFlat(False)
        self.verticalLayout = QVBoxLayout(self.devices_group)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.device_tabs = QTabWidget(self.devices_group)
        self.device_tabs.setObjectName(u"device_tabs")
        self.device_tabs.setTabPosition(QTabWidget.TabPosition.West)

        self.verticalLayout.addWidget(self.device_tabs)


        self.verticalLayout_2.addWidget(self.devices_group)

        self.verticalSpacer = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_2.addItem(self.verticalSpacer)

        self.verticalLayout_2.setStretch(1, 1)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Form", None))
        self.groupBox.setTitle(QCoreApplication.translate("MainWindow", u"Local connection", None))
        self.label_3.setText(QCoreApplication.translate("MainWindow", u"Stop bit", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"Port", None))
        self.parity_select.setItemText(0, QCoreApplication.translate("MainWindow", u"None", None))
        self.parity_select.setItemText(1, QCoreApplication.translate("MainWindow", u"Odd", None))
        self.parity_select.setItemText(2, QCoreApplication.translate("MainWindow", u"Even", None))

        self.label_5.setText(QCoreApplication.translate("MainWindow", u"Device ID", None))
        self.baudrate_select.setItemText(0, QCoreApplication.translate("MainWindow", u"115200", None))
        self.baudrate_select.setItemText(1, QCoreApplication.translate("MainWindow", u"57600", None))
        self.baudrate_select.setItemText(2, QCoreApplication.translate("MainWindow", u"38400", None))
        self.baudrate_select.setItemText(3, QCoreApplication.translate("MainWindow", u"19200", None))
        self.baudrate_select.setItemText(4, QCoreApplication.translate("MainWindow", u"9600", None))

        self.label_2.setText(QCoreApplication.translate("MainWindow", u"Bandwith", None))
        self.label_4.setText(QCoreApplication.translate("MainWindow", u"Parity", None))
        self.stopbit_select.setItemText(0, QCoreApplication.translate("MainWindow", u"1", None))
        self.stopbit_select.setItemText(1, QCoreApplication.translate("MainWindow", u"2", None))

        self.local_btn.setText(QCoreApplication.translate("MainWindow", u"Connect", None))
        self.groupBox_2.setTitle(QCoreApplication.translate("MainWindow", u"Remote connection", None))
        self.label_8.setText(QCoreApplication.translate("MainWindow", u"Device ID", None))
        self.label_6.setText(QCoreApplication.translate("MainWindow", u"Host", None))
        self.label_7.setText(QCoreApplication.translate("MainWindow", u"Port", None))
        self.remote_btn.setText(QCoreApplication.translate("MainWindow", u"Connect", None))
        self.remote_port_select.setItemText(0, QCoreApplication.translate("MainWindow", u"5001", None))
        self.remote_port_select.setItemText(1, QCoreApplication.translate("MainWindow", u"5002", None))

        self.devices_group.setTitle(QCoreApplication.translate("MainWindow", u"Devices", None))
    # retranslateUi

