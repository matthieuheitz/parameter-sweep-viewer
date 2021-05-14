#!/usr/bin/env python3

import os
import sys
import time
import json
from collections import OrderedDict
import glob



from PyQt5 import QtCore, QtWidgets, uic
from PyQt5.QtCore import Qt, QRect, QRectF, QPoint, QPointF, QSize
from PyQt5.QtWidgets import QLabel, QFileDialog, QComboBox, QGraphicsPixmapItem, QDesktopWidget, QGraphicsTextItem
from PyQt5.QtGui import QPixmap, QPen, QColor, QImage, QPainter, QFont


# TODO
#  - Add font size factor spinbox
#  - Add automatic file naming when saving
#  - Add name pattern that support taking last file of the matches
#  - Find individual folders by combination index
#  - In grid mode, select a subset of values to plot
#  - PDF support
#  - Zoom in on the figures


# Because I use a "trick" to hide items of a QComboBox through its QListView,
# scrolling on a normal QComboBox lets me select items that are hidden, which is
# not desirable. So we override the class to prevent that.
class MyQComboBox(QComboBox):
    def wheelEvent(self, event):
        increment = 1 if event.angleDelta().y() < 0 else -1
        index = self.currentIndex()+increment
        if not (0 <= index < self.count()): return
        lv = self.view()
        while lv.isRowHidden(index) and 0 < index < self.count()-1:
            index += increment
        # If we got out of the loop and new index is hidden, we are on a hidden boundary item, so don't increment.
        if not lv.isRowHidden(index):
            self.setCurrentIndex(index)


class Ui(QtWidgets.QMainWindow):
    def __init__(self):
        super(Ui, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi('mainwindow.ui', self)   # Load the .ui file

        # Place window in the center of the screen, and make it a bit smaller
        screenRect = QDesktopWidget().availableGeometry()
        windowRect = QRect()
        windowRect.setSize(screenRect.size()*0.75)
        windowRect.moveCenter(screenRect.center())
        self.setGeometry(windowRect)

        # Data
        self.mainFolder = ""
        self.configFile = ""
        self.defaultConfigFile = "sweep.txt"
        self.paramDict = OrderedDict()     # Holds current values of parameters to display
        self.fullParamDict = OrderedDict()     # Holds all possible values of each parameter
        self.allParamNames = []
        self.paramControlType = "combobox"   # "slider" or "combobox"
        self.comboBox_noneChoice = "--None--"
        self.xaxis = self.comboBox_noneChoice
        self.yaxis = self.comboBox_noneChoice
        self.filePattern = ""

        # Output
        self.defaultSaveFileName = "output.png"
        self.lineEdit_saveFile.setText(self.defaultSaveFileName)

        # View
        self.paramControlWidgetList = []
        # Set up X and Y axis comboboxes
        nRows = self.gridLayout_display.rowCount()
        self.gridLayout_display.addWidget(QLabel("X axis"), nRows, 0)
        self.gridLayout_display.addWidget(QLabel("Y axis"), nRows+1, 0)
        self.comboBox_xaxis = MyQComboBox()
        self.comboBox_yaxis = MyQComboBox()
        self.comboBox_xaxis.addItem(self.comboBox_noneChoice)
        self.comboBox_yaxis.addItem(self.comboBox_noneChoice)
        self.gridLayout_display.addWidget(self.comboBox_xaxis, nRows, 1)
        self.gridLayout_display.addWidget(self.comboBox_yaxis, nRows+1, 1)
        self.imageSpacing = [0,0]   # x and y spacing between images
        self.imageCrop = [0,0,0,0]  # how much to crop images in percentage [left,bottom,right,top]
        self.doubleSpinBox_cropList = [self.doubleSpinBox_cropL,self.doubleSpinBox_cropB,
                                       self.doubleSpinBox_cropR,self.doubleSpinBox_cropT]
        self.imageFrameLineWidth = 0
        self.imageFrameColor = "black"

        self.scene = QtWidgets.QGraphicsScene()
        # self.graphicsView.scale(1,-1) # Flip the y axis, but it also flips images
        self.graphicsView.setScene(self.scene)
        self.show() # Show the GUI

        # Connect widgets
        self.lineEdit_mainFolder.editingFinished.connect(self.mainFolder_changed)
        self.lineEdit_configFile.editingFinished.connect(self.configFile_changed)
        self.lineEdit_filePattern.editingFinished.connect(self.filePattern_changed)
        self.pushButton_mainFolder.pressed.connect(self.mainFolder_browse)
        self.pushButton_configFile.pressed.connect(self.configFile_browse)
        self.pushButton_clearLog.pressed.connect(self.log_clear)
        self.comboBox_xaxis.currentIndexChanged.connect(self.comboBoxAxis_changed)
        self.comboBox_yaxis.currentIndexChanged.connect(self.comboBoxAxis_changed)
        [w.valueChanged.connect(self.crop_changed) for w in self.doubleSpinBox_cropList]
        self.spinBox_spacingX.valueChanged.connect(self.spacing_changed)
        self.spinBox_spacingY.valueChanged.connect(self.spacing_changed)
        self.spinBox_frameLineWidth.valueChanged.connect(self.frameLineWidth_changed)
        self.lineEdit_frameColor.textChanged.connect(self.frameColor_changed)
        self.pushButton_saveFileBrowse.pressed.connect(self.saveFile_browse)
        self.pushButton_saveFile.pressed.connect(self.saveFile_save)
        self.doubleSpinBox_ImageReduction.valueChanged.connect(self.imageReduction_changed)

        # This changes the limit of the current view, ie what we see of the scene through the widget.
        # s = 100
        # self.graphicsView.fitInView(-s, -s, s, s, Qt.KeepAspectRatio)

        # The scene rectangle defines the extent of the scene, and in the view's case,
        # this means the area of the scene that you can navigate using the scroll bars.
        # If the view is larger than the provided rect, it doesn't change anything.
        # If the provided rect is larger than the view, it will add scrollbars to see the entire rectangle
        # self.graphicsView.setSceneRect(-500, -500, 1000, 1000)

        # Commands to change the widget size. They need to be called after self.show(), otherwise the widget size
        # is the default (100,30).
        # self.graphicsView.setFixedSize(100, 100)  # Changes the size of the widget
        # self.print(str(self.graphicsView.size()))   # Prints the size of the widget, not the scene bounding box coordinates
        # self.print(str(self.graphicsView.viewport().size()))    # Prints the size of the widget, not the scene bounding box coordinates

        # DEBUG
        self.lineEdit_mainFolder.setText("/home/matthieu/Work/Postdoc-UBC/Projects/trajectory_inference/DGCG_scRNAseq/examples/results_reprog_umap_2d_ss10__sig_ab_multistart")
        self.mainFolder_changed()
        time.sleep(0.5)
        self.lineEdit_filePattern.setText("iter_001_insertion.png")
        self.filePattern_changed()
        # self.lineEdit_filePattern.setText("iter_*_insertion.png[-1]")


    def resizeEvent(self, event):   # This is an overloaded function
        QtWidgets.QMainWindow.resizeEvent(self, event)
        # Redraw when window is resized
        self.draw_graphics()

    def print(self,txt):
        self.text_log.appendPlainText(txt)

    def log_clear(self):
        self.text_log.clear()

    def mainFolder_browse(self):
        dir = str(QFileDialog.getExistingDirectory(self, "Select directory"))
        if dir:
            self.mainFolder = dir
        self.lineEdit_mainFolder.setText(self.mainFolder)
        self.mainFolder_changed()

    def mainFolder_changed(self):
        path = self.lineEdit_mainFolder.text()
        # Check if it's a valid folder
        if not os.path.isdir(path):
            self.lineEdit_mainFolder.setStyleSheet("color: red;")
            self.mainFolder = ""
            self.draw_graphics()
            return
        self.lineEdit_mainFolder.setStyleSheet("color: black;")
        self.mainFolder = path
        # Check if there is a config file
        if os.path.isfile(os.path.join(self.mainFolder,self.defaultConfigFile)):
            self.lineEdit_configFile.setText(os.path.join(self.mainFolder,self.defaultConfigFile))
            self.configFile_changed()
        else:
            self.print("No config file 'sweep.txt' found in %s. Please provide it manually."%self.mainFolder)
            return
        # Redraw
        self.draw_graphics()

    def configFile_browse(self):
        # file = str(QFileDialog.getOpenFileUrl(self, "Select file..."))
        file = QFileDialog.getOpenFileName(self, "Select file...")[0]
        if file:
            self.configFile = file
        self.lineEdit_configFile.setText(self.configFile)
        self.configFile_changed()

    def configFile_invalid(self):
        self.lineEdit_configFile.setStyleSheet("color: red;")
        self.fullParamDict = {}
        self.paramDict = {}
        self.allParamNames = []
        self.paramControlWidgetList.clear()
        # Delete all parameter control widgets
        # https://stackoverflow.com/a/13103617/4195725
        for i in reversed(range(self.gridLayout_paramControl.count())):
            self.gridLayout_paramControl.itemAt(i).widget().setParent(None)
        # Reset comboboxes
        self.comboBox_xaxis.blockSignals(True)
        self.comboBox_yaxis.blockSignals(True)
        self.comboBox_xaxis.clear()
        self.comboBox_yaxis.clear()
        self.comboBox_xaxis.addItem(self.comboBox_noneChoice)
        self.comboBox_yaxis.addItem(self.comboBox_noneChoice)
        self.comboBox_xaxis.blockSignals(False)
        self.comboBox_yaxis.blockSignals(False)
        # Redraw
        self.draw_graphics()

    def configFile_changed(self):
        path = self.lineEdit_configFile.text()
        # Check if it's a valid file
        if not os.path.isfile(path):
            self.configFile_invalid()
            return
        # First clear all parameter controls and axis comboboxes
        self.configFile_invalid()
        # Then redo everything with the new config file
        self.lineEdit_configFile.setStyleSheet("color: black;")
        self.configFile = path
        # Read parameters from file and keep their order
        try:
            self.fullParamDict = json.load(open(self.configFile, 'r'), object_pairs_hook=OrderedDict)
        except:
            self.print("Error: the config file should be a json file")
            self.configFile_invalid()
            return
        # Check if there are viewer parameters
        if "viewer_cropLBRT" in self.fullParamDict:
            self.set_cropLBRT(self.fullParamDict["viewer_cropLBRT"])
            del self.fullParamDict["viewer_cropLBRT"]

        # Get list of all parameter names
        self.allParamNames = list(self.fullParamDict.keys())
        # Populate the parameter controls
        self.populate_parameterControls()
        # Populate the axis comboboxes
        self.comboBox_xaxis.addItems(self.allParamNames)
        self.comboBox_yaxis.addItems(self.allParamNames)
        # Redraw
        self.draw_graphics()

    def populate_parameterControls(self):
        for i, (param,values) in enumerate(self.fullParamDict.items()):
            textWidget = controlWidget = None
            if self.paramControlType == "combobox":
                textWidget = QLabel(param)
                controlWidget = QComboBox()
                controlWidget.addItems([str(v) for v in values])
            else:
                print("Not implemented")
            self.paramControlWidgetList.append(controlWidget)
            self.gridLayout_paramControl.addWidget(textWidget, i, 0)
            self.gridLayout_paramControl.addWidget(controlWidget, i, 1)
            # Connect signals
            self.paramControlWidgetList[i].currentIndexChanged.connect(self.paramControl_changed)
            # Initialize paramDict with first value of each parameter
            self.paramDict[param] = [values[0]]

    def comboBoxAxis_changed(self, index):
        #  If xaxis has changed
        #   If xaxis is a parameter other than None:
        #   - Remove param from paramDict, the control widgets and the combobox of yaxis
        #   If previous value was a parameter other than None:
        #   - Restore the previous param to paramDict, the control widgets and the combobox of yaxis
        #   Finally, store the new selection in xaxis
        #  Else if yaxis has change
        #   Vice versa

        def update_xyComboBox(combo_current, prev_param, combo_other):
            # If the new selection is not None, hide it where necessary
            param = combo_current.currentText()
            if param != self.comboBox_noneChoice:
                param_index = self.allParamNames.index(param)
                self.paramDict[param] = self.fullParamDict[param]
                self.paramControlWidgetList[param_index].setEnabled(False)
                combo_other.view().setRowHidden(param_index+1, True)
            # If the previous selection was not None, restore it where necessary
            if prev_param != self.comboBox_noneChoice:
                param_index = self.allParamNames.index(prev_param)
                self.paramDict[prev_param] = [self.fullParamDict[prev_param][self.paramControlWidgetList[param_index].currentIndex()]]  # Restore to previous value
                self.paramControlWidgetList[param_index].setEnabled(True)
                combo_other.view().setRowHidden(param_index+1, False)

        if self.sender() is self.comboBox_xaxis:
            update_xyComboBox(self.comboBox_xaxis, self.xaxis, self.comboBox_yaxis)
            self.xaxis = self.comboBox_xaxis.currentText()
        elif self.sender() is self.comboBox_yaxis:
            update_xyComboBox(self.comboBox_yaxis, self.yaxis, self.comboBox_xaxis)
            self.yaxis = self.comboBox_yaxis.currentText()

        # Redraw
        self.draw_graphics()

    def filePattern_changed(self):
        self.filePattern = self.lineEdit_filePattern.text()
        # Redraw
        self.draw_graphics()

    # @QtCore.pyqtSlot()
    def paramControl_changed(self, index):
        # Identify the sender
        id_sender = self.paramControlWidgetList.index(self.sender())
        # Get parameter name
        param = self.allParamNames[id_sender]
        # Change current parameter
        self.paramDict[param] = [self.fullParamDict[param][index]]
        # Redraw
        self.draw_graphics()

    def crop_changed(self, value):
        # Update the variable
        self.imageCrop = [w.value()/100 for w in self.doubleSpinBox_cropList]
        self.draw_graphics()

    def set_cropLBRT(self, cropLBRT):
        self.imageCrop = cropLBRT
        # Block signals
        [w.blockSignals(True) for i, w in enumerate(self.doubleSpinBox_cropList)]
        [w.setValue(cropLBRT[i]) for i,w in enumerate(self.doubleSpinBox_cropList)]
        [w.blockSignals(False) for i, w in enumerate(self.doubleSpinBox_cropList)]
        # Call the slot only once
        self.crop_changed(0)

    def spacing_changed(self, value):
        # Update the variable
        self.imageSpacing = [self.spinBox_spacingX.value(),self.spinBox_spacingY.value()]
        self.draw_graphics()

    def getImageCroppingRect(self, pixmap):
        return QRect(int(self.imageCrop[0] * pixmap.width()), int(self.imageCrop[3] * pixmap.height()),
                     int((1 - self.imageCrop[2]) * pixmap.width() - self.imageCrop[0] * pixmap.width()),
                     int((1 - self.imageCrop[1]) * pixmap.height() - self.imageCrop[3] * pixmap.height()))

    def frameLineWidth_changed(self, value):
        self.imageFrameLineWidth = value
        self.draw_graphics()

    def frameColor_changed(self, text):
        self.imageFrameColor = text
        self.draw_graphics()

    def draw_graphics(self):
        # print("Draw!")
        # Clear the scene before drawing
        self.scene.clear()
        # Check if any information is missing
        if not self.mainFolder or not self.paramDict or not self.filePattern:
            return
        alldirs = [os.path.basename(f) for f in os.scandir(self.mainFolder) if f.is_dir()]

        # This handles all configurations of the X and Y axis boxes
        xrange = self.paramDict[self.xaxis] if self.xaxis != self.comboBox_noneChoice else [None]
        yrange = self.paramDict[self.yaxis] if self.yaxis != self.comboBox_noneChoice else [None]
        nValuesX = len(xrange)
        nValuesY = len(yrange)
        used_dirs = alldirs.copy()
        # Find dirs that match all single parameters
        for param, value in self.paramDict.items():
            if len(value) == 1:
                used_dirs = [d for d in used_dirs if param+str(value[0]) in d]
        imWidth = 0
        imHeight = 0
        for i, ival in enumerate(yrange):
            for j, jval in enumerate(xrange):
                # Find the correct folder
                dirs = used_dirs.copy()
                if ival is not None: dirs = [d for d in dirs if self.yaxis+str(ival) in d]
                if jval is not None: dirs = [d for d in dirs if self.xaxis+str(jval) in d]
                if len(dirs) == 0: self.print("Error: no folder matches the set of parameters"); pass
                if len(dirs) > 1: self.print("Error: multiple folders match the set of parameters:", dirs); pass
                currentDir = dirs[0]
                # Check if file exists
                file = os.path.join(self.mainFolder, currentDir, self.filePattern)
                if not os.path.isfile(file):
                    self.print("Error: no file in the folder matches the pattern.")
                    pass
                # Load the image
                p = QPixmap(file)
                # This way of drawing assumes all images have the size of the first image
                # Crop the image
                cropRect = self.getImageCroppingRect(p)
                pc = p.copy(cropRect)

                if i == 0 and j == 0:
                    # Get image dimension
                    imWidth = pc.width()
                    imHeight = pc.height()

                    # Get dimensions
                    viewSize = self.graphicsView.size()
                    sceneSize = QSize(nValuesX*(imWidth+self.imageSpacing[0]), nValuesY*(imHeight+self.imageSpacing[1]))
                    maxViewSize = max(viewSize.width(), viewSize.height())
                    maxSceneSize = max(sceneSize.width(), sceneSize.height())
                    # print("Image size:",sceneSize)
                    # print("View size:",self.graphicsView.size())
                    # print("Point size:",txt.font().pointSize())
                    # It's very difficult to find a formula that gives a good font size in all situations, because it
                    # depends on the size of the images, and the number of images (so the size of the drawing).
                    # But for confortable viewing, it should also depend on how large the graphicsview widget is, even
                    # though the content of that window should be agnostic to the size of the window we visualize it in.
                    # fontSize = 60
                    # fontSize = int(maxSceneSize/40)
                    fontSize = int(maxSceneSize / maxViewSize * 20)
                    # Spacing between labels and images
                    # labelSpacing = max(imWidth,imHeight)/20
                    labelSpacing = fontSize*0.75

                # Draw the image
                imageItem = QGraphicsPixmapItem(pc)
                imagePos = QPointF(j*(imWidth + self.imageSpacing[0]), i*(imHeight + self.imageSpacing[1]))
                imageItem.setOffset(imagePos)
                self.scene.addItem(imageItem)

                # Draw top labels if X axis is not None
                if jval is not None and i == 0:
                    textItem = QGraphicsTextItem()
                    textItem.setFont(QFont("Sans Serif",pointSize=fontSize))
                    textItem.setPlainText(self.xaxis+"="+str(jval))
                    textBR = textItem.sceneBoundingRect()
                    # height/10 is the arbitary spacing that separates labels from images
                    # Substract textBR.height() on Y so that the bottom of the text is always imHeight/10 from the image
                    textItem.setPos(imagePos + QPointF(imWidth/2 - textBR.width()/2, -labelSpacing - textBR.height()))
                    self.scene.addItem(textItem)

                # Draw left labels if Y axis is not None
                if ival is not None and j == 0:
                    textItem = QGraphicsTextItem()
                    textItem.setFont(QFont("Sans Serif", pointSize=fontSize))
                    textItem.setPlainText(self.yaxis+"="+str(ival))
                    textItem.setRotation(-90)
                    textBR = textItem.sceneBoundingRect()
                    textItem.setPos(imagePos + QPointF(-labelSpacing - textBR.width(), imHeight/2 + textBR.height()/2))
                    self.scene.addItem(textItem)

                # Draw frames
                if self.imageFrameLineWidth != 0:
                    frameRect = QRectF(cropRect)
                    frameRect.moveTopLeft(imagePos)
                    self.scene.addRect(frameRect,QPen(QColor(self.imageFrameColor),self.imageFrameLineWidth))


        # Add main title
        # Compute view rectangle
        viewRect = self.scene.itemsBoundingRect()
        # self.scene.addRect(viewRect)  # Plot the view rectangle
        textItem = QGraphicsTextItem()
        textItem.setFont(QFont("Sans Serif", pointSize=fontSize))
        text = ""
        for param,value in self.paramDict.items():
            if len(value) == 1: text += param + "=" + str(value[0]) + ", "
        if text: text = text[:-2]   # Remove trailing ", " if not empty
        textItem.setPlainText(text)
        textBR = textItem.sceneBoundingRect()
        textItem.setPos(viewRect.center() - QPointF(textBR.width()/2, viewRect.height()/2 + labelSpacing + textBR.height()))
        self.scene.addItem(textItem)

        # Recompute view rectangle
        viewRect = self.scene.itemsBoundingRect()
        # self.scene.addRect(viewRect)  # Plot the view rectangle
        # Readjust the view
        self.graphicsView.fitInView(viewRect, Qt.KeepAspectRatio)
        # Readjust the scrolling area
        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        # Update show image size
        self.printImageSizesInLabel()

    def saveFile_browse(self):
        file = (QFileDialog.getSaveFileName(self, "Save view"))[0]
        if file:
            self.lineEdit_saveFile.setText(file)
        return

    def printImageSizesInLabel(self):
        sceneSize = self.scene.sceneRect().size()
        text = "Scene size: \t %dx%d\n"%(sceneSize.width(),sceneSize.height())
        outSize = (sceneSize*self.doubleSpinBox_ImageReduction.value()).toSize()
        text += "Output image size: %dx%d"%(outSize.width(),outSize.height())
        self.label_imageSize.setText(text)

    def imageReduction_changed(self, value):
        self.printImageSizesInLabel()

    def saveFile_save(self):
        file = self.lineEdit_saveFile.text()
        # If file is a relative path, we save it in the input folder.
        if not file.startswith('/'):
            file = os.path.join(self.mainFolder,file)
        # Save the scene
        # From https://stackoverflow.com/a/11642517/4195725
        self.scene.clearSelection()
        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        image = QImage((self.scene.sceneRect().size()*self.doubleSpinBox_ImageReduction.value()).toSize(),QImage.Format_ARGB32)
        # image.fill(Qt.transparent)
        image.fill(Qt.white)
        painter = QPainter(image)
        self.scene.render(painter)
        image.save(file)
        del painter

        return


if __name__ == '__main__':

    app = QtWidgets.QApplication(sys.argv) # Create an instance of QtWidgets.QApplication
    window = Ui() # Create an instance of our class
    app.exec_() # Start the application

