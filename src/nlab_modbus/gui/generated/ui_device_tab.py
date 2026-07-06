# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'device_tab.ui'
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
from PySide6.QtWidgets import (QAbstractScrollArea, QApplication, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QSizePolicy, QSpinBox, QTableView,
    QVBoxLayout, QWidget)

from pyqtgraph import GraphicsView

class Ui_DeviceTab(object):
    def setupUi(self, DeviceTab):
        if not DeviceTab.objectName():
            DeviceTab.setObjectName(u"DeviceTab")
        DeviceTab.resize(989, 632)
        self.horizontalLayout_2 = QHBoxLayout(DeviceTab)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.groupBox_3 = QGroupBox(DeviceTab)
        self.groupBox_3.setObjectName(u"groupBox_3")
        self.gridLayout = QGridLayout(self.groupBox_3)
        self.gridLayout.setObjectName(u"gridLayout")
        self.clear_plot_btn = QPushButton(self.groupBox_3)
        self.clear_plot_btn.setObjectName(u"clear_plot_btn")

        self.gridLayout.addWidget(self.clear_plot_btn, 2, 2, 1, 1)

        self.type_edit = QLineEdit(self.groupBox_3)
        self.type_edit.setObjectName(u"type_edit")
        self.type_edit.setEnabled(False)

        self.gridLayout.addWidget(self.type_edit, 0, 1, 1, 2)

        self.refresh_spinner = QSpinBox(self.groupBox_3)
        self.refresh_spinner.setObjectName(u"refresh_spinner")
        self.refresh_spinner.setMinimum(100)
        self.refresh_spinner.setMaximum(10000)
        self.refresh_spinner.setValue(250)

        self.gridLayout.addWidget(self.refresh_spinner, 1, 2, 1, 1)

        self.label = QLabel(self.groupBox_3)
        self.label.setObjectName(u"label")

        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)

        self.label_3 = QLabel(self.groupBox_3)
        self.label_3.setObjectName(u"label_3")

        self.gridLayout.addWidget(self.label_3, 1, 0, 1, 1)

        self.tab_disconnect_btn = QPushButton(self.groupBox_3)
        self.tab_disconnect_btn.setObjectName(u"tab_disconnect_btn")

        self.gridLayout.addWidget(self.tab_disconnect_btn, 3, 2, 1, 1)


        self.verticalLayout.addWidget(self.groupBox_3)

        self.groupBox = QGroupBox(DeviceTab)
        self.groupBox.setObjectName(u"groupBox")
        self.verticalLayout_2 = QVBoxLayout(self.groupBox)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.holding_table_view = QTableView(self.groupBox)
        self.holding_table_view.setObjectName(u"holding_table_view")
        self.holding_table_view.setMinimumSize(QSize(311, 0))
        self.holding_table_view.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        self.holding_table_view.horizontalHeader().setMinimumSectionSize(0)
        self.holding_table_view.verticalHeader().setDefaultSectionSize(24)

        self.verticalLayout_2.addWidget(self.holding_table_view)


        self.verticalLayout.addWidget(self.groupBox)

        self.groupBox_2 = QGroupBox(DeviceTab)
        self.groupBox_2.setObjectName(u"groupBox_2")
        self.horizontalLayout = QHBoxLayout(self.groupBox_2)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.input_table_view = QTableView(self.groupBox_2)
        self.input_table_view.setObjectName(u"input_table_view")
        self.input_table_view.setMinimumSize(QSize(311, 0))
        self.input_table_view.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        self.input_table_view.verticalHeader().setMinimumSectionSize(0)
        self.input_table_view.verticalHeader().setDefaultSectionSize(24)

        self.horizontalLayout.addWidget(self.input_table_view)


        self.verticalLayout.addWidget(self.groupBox_2)


        self.horizontalLayout_2.addLayout(self.verticalLayout)

        self.input_plot = GraphicsView(DeviceTab)
        self.input_plot.setObjectName(u"input_plot")
        self.input_plot.setMinimumSize(QSize(500, 300))
        self.input_plot.setAcceptDrops(True)

        self.horizontalLayout_2.addWidget(self.input_plot)

        self.horizontalLayout_2.setStretch(1, 1)

        self.retranslateUi(DeviceTab)

        QMetaObject.connectSlotsByName(DeviceTab)
    # setupUi

    def retranslateUi(self, DeviceTab):
        DeviceTab.setWindowTitle(QCoreApplication.translate("DeviceTab", u"Form", None))
        self.groupBox_3.setTitle(QCoreApplication.translate("DeviceTab", u"Device", None))
        self.clear_plot_btn.setText(QCoreApplication.translate("DeviceTab", u"Clear plot", None))
        self.label.setText(QCoreApplication.translate("DeviceTab", u"Type", None))
        self.label_3.setText(QCoreApplication.translate("DeviceTab", u"Refresh rate (ms)", None))
        self.tab_disconnect_btn.setText(QCoreApplication.translate("DeviceTab", u"Disconnect", None))
        self.groupBox.setTitle(QCoreApplication.translate("DeviceTab", u"Holding registers (R/W)", None))
        self.groupBox_2.setTitle(QCoreApplication.translate("DeviceTab", u"Input registers (R)", None))
    # retranslateUi

