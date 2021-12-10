#!/usr/bin/python
# -*- coding: utf-8 -*

from sys import argv, exit
from os import environ, mkdir, remove
from os.path import dirname, exists, join, splitext

import PyQt5
from PyQt5.QtCore import Qt, QRect, QTimer, QSize
from PyQt5.QtGui import QPalette, QColor, QFont, QKeySequence
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QTableWidget, QTableWidgetItem, QHBoxLayout, QVBoxLayout, QStyle, \
    QFrame, QSlider, QPushButton, QComboBox, QFileDialog, QMessageBox, QLabel, QShortcut, QHeaderView, QAbstractItemView

from vlc import MediaPlayer, Media

from pandas import DataFrame, read_csv
from datetime import datetime, timedelta

pyqt5dpath = dirname(PyQt5.__file__)
for filename in ("Qt5", "Qt"):
    plugindpath = join(pyqt5dpath, filename, "plugins", "platforms")
    if exists(plugindpath):
        environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = plugindpath
        print(plugindpath)

# Defines column headings for annotation and label files
annothdg = ["video_file", "start_time", "end_time", "label"]
labelhdg = ["label"]

class KeyboardShortcuts(QMainWindow):
    def __init__(self, parent=None):
        super(KeyboardShortcuts, self).__init__(parent)
        self.setWindowTitle("Keyboard shortcuts")

        self._shortcut_menu()

    def _shortcut_menu(self):
        shortcutmenuwidget = QWidget(self)
        shortcutmenuwidget.setGeometry(QRect(0, 0, 320, 600))

        vshortcutbox = QVBoxLayout()

        title = QLabel()
        title.setText("Keyboard shortcuts")
        font = QFont()
        font.setBold(True)
        title.setFont(font)
        vshortcutbox.addWidget(title)

        videoplayershortcuts = {"Spacebar " : "Play/Pause",
                "Right arrow" : "Fast forward 5s",
                "Left arrow" : "Rewind 5s"}

        tableshortcuts = {"Ctrl++" : "Add row",
                "Ctrl+-" : "Delete selected row",
                "Arrows" : "Move between cells",
                "Tab/Backtab" : "Move to next/previous cell",
                "Spacebar" : "Edit selected cell",
                "Ins" : "Insert current time",
                "Ctrl+F" : "Play from selected time",
                "Ctrl+X" : "Cut",
                "Ctrl+C": "Copy",
                "Ctrl+V" : "Paste",
                "Ctrl+Z" : "Undo",
                "Del" : "Delete cell content",
                "Esc" : "Deselect cell",
                "Ctrl+S" : "Save"}

        for shortcuts in (videoplayershortcuts, tableshortcuts):
            for key in shortcuts.keys():
                hshortcutbox = QHBoxLayout()

                shortcut = QLabel()
                shortcut.setText(key)
                hshortcutbox.addWidget(shortcut, 1)

                desc = QLabel()
                desc.setText(shortcuts[key])
                hshortcutbox.addWidget(desc, 2)

                vshortcutbox.addLayout(hshortcutbox)

            if shortcuts == videoplayershortcuts:
                newline = QLabel()
                newline.setText("")
                vshortcutbox.addWidget(newline)

        shortcutmenuwidget.setLayout(vshortcutbox)

class VideoAnnotator(QMainWindow):
    def __init__(self, videodpath=None, annotdpath=None, labeldpath=None, parent=None):
        super(VideoAnnotator, self).__init__(parent)
        self.setWindowTitle("Video Annotator")

        # Creates video player object
        self.videoplayer = MediaPlayer()

        # Adds video information
        self.videodpath = videodpath
        self.videofname = None
        self.currtime = 0
        self.duration = 0
        self.ispaused = False

        # Adds annotation information
        self.annotdpath = annotdpath
        self.annot = DataFrame(columns=annothdg)

        # Adds backup file information
        self.backupdpath = "temp"
        self.backupfpath = None

        # Adds label information
        self.labeldpath = labeldpath
        self.label = None
        self.labelbackup = None
        self.undostate = -1

        # Checks folders exist
        for dpath in (self.videodpath, self.annotdpath, self.labeldpath):
            if not exists(dpath):
                mkdir(dpath)

        # Creates UI
        self._video_player_ui()
        self._btn_panel_ui()
        self._annot_table_ui()
        self._add_shortcut()

    def _create_new_backup_file(self):
        if not exists(self.backupdpath):
            mkdir(self.backupdpath)

        self.backupfpath = join(self.backupdpath, datetime.now().strftime("%y%m%d%H%M%S") + ".csv")
        self.annot.to_csv(self.backupfpath, index=False)

    def _video_player_ui(self):
        videoplayerwidget = QWidget(self)
        videoplayerwidget.setGeometry(QRect(0, 0, 720, 600))

        # Video frame
        self.videoframe = QFrame()
        palette = self.videoframe.palette()
        palette.setColor(QPalette.Window, QColor(0,0,0))
        self.videoframe.setPalette(palette)
        self.videoframe.setAutoFillBackground(True)
        self.videoplayer.set_hwnd(self.videoframe.winId())

        # Seek bar
        self.seekbar = QSlider(Qt.Horizontal, self)
        self.seekbar.setToolTip("Seek")
        self.seekbarmax = 1000
        self.seekbar.setMaximum(self.seekbarmax)
        self.seekbar.sliderMoved.connect(self._set_position)

        # Play/Pause button
        self.playbtn = QPushButton()
        self.playbtn.setEnabled(False)
        self.playbtn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.playbtn.clicked.connect(self._play_pause)

        # New video button
        self.newvideobtn = QPushButton("New video")
        self.newvideobtn.clicked.connect(self._import_video)

        # Current time
        self.time = QLabel()
        self._print_time()

        # Volume control
        self.volume = QLabel()
        pixmap = self.style().standardIcon(QStyle.SP_MediaVolume).pixmap(QSize(64, 64))
        self.volume.setPixmap(pixmap)

        self.volumectrl = QSlider(Qt.Horizontal, self)
        self.volumectrl.setMaximum(100)
        self.volumectrl.setValue(self.videoplayer.audio_get_volume())
        self.volumectrl.valueChanged.connect(self._set_volume)

        hbtnbox = QHBoxLayout()
        hbtnbox.addWidget(self.playbtn)
        hbtnbox.addWidget(self.newvideobtn)
        hbtnbox.addWidget(self.time)
        hbtnbox.addStretch(1)
        hbtnbox.addWidget(self.volume)
        hbtnbox.addWidget(self.volumectrl)

        vboxlayout = QVBoxLayout()
        vboxlayout.addWidget(self.videoframe)
        vboxlayout.addWidget(self.seekbar)
        vboxlayout.addLayout(hbtnbox)
        videoplayerwidget.setLayout(vboxlayout)

        # Timer
        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self._update_position)

    def _btn_panel_ui(self):
        btnpanelwidget = QWidget(self)
        btnpanelwidget.setGeometry(QRect(1480, 0, 320, 600))

        self.addrowbtn = QPushButton("Add row")
        self.addrowbtn.setEnabled(False)
        self.addrowbtn.clicked.connect(self._add_row)

        self.inserttimebtn = QPushButton("Insert current time")
        self.inserttimebtn.setEnabled(False)
        self.inserttimebtn.clicked.connect(self._get_time)

        self.seekpositionbtn = QPushButton("Play from selected time")
        self.seekpositionbtn.setEnabled(False)
        self.seekpositionbtn.clicked.connect(self._find_position)

        shortcutmenu = self._shortcut_menu()

        self.shortcutbtn = QPushButton("More keyboard shortcuts")
        self.shortcutbtn.setEnabled(True)
        self.shortcutbtn.clicked.connect(self._display_shortcut_menu)

        self.cleartablebtn = QPushButton("Clear table")
        self.cleartablebtn.setEnabled(False)
        self.cleartablebtn.clicked.connect(self._clear_table)

        self.importannotbtn = QPushButton("Import annotations")
        self.importannotbtn.setEnabled(False)
        self.importannotbtn.clicked.connect(self._import_annot_file)

        self.adddropdownbtn = QPushButton("Add label drop-down list")
        self.adddropdownbtn.setEnabled(False)
        self.adddropdownbtn.clicked.connect(self._import_label_file)

        self.deldropdownbtn = QPushButton("Remove label drop-down list")
        self.deldropdownbtn.setEnabled(False)
        self.deldropdownbtn.clicked.connect(self._delete_label_file)

        self.savebtn = QPushButton("Save")
        self.savebtn.setEnabled(False)
        self.savebtn.clicked.connect(self._save)

        vbtnbox = QVBoxLayout()
        vbtnbox.addWidget(self.addrowbtn)
        vbtnbox.addWidget(self.inserttimebtn)
        vbtnbox.addWidget(self.seekpositionbtn)
        vbtnbox.addWidget(self.cleartablebtn)
        vbtnbox.addStretch(1)
        vbtnbox.addWidget(shortcutmenu)
        vbtnbox.addWidget(self.shortcutbtn)
        vbtnbox.addWidget(self.importannotbtn)
        vbtnbox.addWidget(self.adddropdownbtn)
        vbtnbox.addWidget(self.deldropdownbtn)
        vbtnbox.addWidget(self.savebtn)
        btnpanelwidget.setLayout(vbtnbox)

    def _add_shortcut(self):
        shortcut_add_row = QShortcut(QKeySequence("Ctrl++"), self)
        shortcut_add_row.activated.connect(self._shortcut_ctrlplus)
        shortcut_delete_row = QShortcut(QKeySequence("Ctrl+-"), self)
        shortcut_delete_row.activated.connect(self._shortcut_ctrlminus)
        shortcut_up_arrow = QShortcut(QKeySequence("Up"), self)
        shortcut_up_arrow.activated.connect(self._shortcut_up)
        shortcut_down_arrow = QShortcut(QKeySequence("Down"), self)
        shortcut_down_arrow.activated.connect(self._shortcut_down)
        shortcut_left_arrow = QShortcut(QKeySequence("Left"), self)
        shortcut_left_arrow.activated.connect(self._shortcut_left)
        shortcut_right_arrow = QShortcut(QKeySequence("Right"), self)
        shortcut_right_arrow.activated.connect(self._shortcut_right)
        shortcut_tab = QShortcut(QKeySequence("Tab"), self)
        shortcut_tab.activated.connect(self._shortcut_tab)
        shortcut_backtab = QShortcut(QKeySequence("Shift+Tab"), self)
        shortcut_backtab.activated.connect(self._shortcut_backtab)
        shortcut_home = QShortcut(QKeySequence("Home"), self)
        shortcut_home.activated.connect(self._shortcut_home)
        shortcut_end = QShortcut(QKeySequence("End"), self)
        shortcut_end.activated.connect(self._shortcut_end)
        shortcut_space = QShortcut(QKeySequence("Space"), self)
        shortcut_space.activated.connect(self._shortcut_space)
        shortcut_ins = QShortcut(QKeySequence("Ins"), self)
        shortcut_ins.activated.connect(self._shortcut_ins)
        shortcut_find_position = QShortcut(QKeySequence("Ctrl+F"), self)
        shortcut_find_position.activated.connect(self._find_position)
        shortcut_cut = QShortcut(QKeySequence("Ctrl+X"), self)
        shortcut_cut.activated.connect(self._shortcut_cut)
        shortcut_copy = QShortcut(QKeySequence("Ctrl+C"), self)
        shortcut_copy.activated.connect(self._shortcut_copy)
        shortcut_paste = QShortcut(QKeySequence("Ctrl+V"), self)
        shortcut_paste.activated.connect(self._shortcut_paste)
        shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        shortcut_undo.activated.connect(self._undo)
        shortcut_del = QShortcut(QKeySequence("Del"), self)
        shortcut_del.activated.connect(self._shortcut_del)
        shortcut_esc = QShortcut(QKeySequence("Esc"), self)
        shortcut_esc.activated.connect(self._shortcut_esc)
        shortcut_save = QShortcut(QKeySequence("Ctrl+S"), self)
        shortcut_save.activated.connect(self._save)

    def _shortcut_menu(self):
        shortcutmenuwidget = QWidget(self)
        vshortcutbox = QVBoxLayout()

        title = QLabel()
        title.setText("Keyboard Shortcuts")
        font = QFont()
        font.setBold(True)
        title.setFont(font)
        vshortcutbox.addWidget(title)

        shortcuts = {"Ctrl++" : "Add row",
                "Ctrl+-" : "Delete selected row",
                "Ins" : "Insert current time",
                "Ctrl+F" : "Play from selected time"}

        for key in shortcuts.keys():
            hshortcutbox = QHBoxLayout()

            shortcut = QLabel()
            shortcut.setText(key)
            hshortcutbox.addWidget(shortcut, 1)

            desc = QLabel()
            desc.setText(shortcuts[key])
            hshortcutbox.addWidget(desc, 2)

            vshortcutbox.addLayout(hshortcutbox)

        shortcutmenuwidget.setLayout(vshortcutbox)

        return shortcutmenuwidget

    def _display_shortcut_menu(self):
        dialog = KeyboardShortcuts(self)
        dialog.setFixedSize(320, 600)
        dialog.show()

    def _annot_table_ui(self):
        self.tablewidget = QTableWidget(self)
        self.tablewidget.setGeometry(QRect(720, 0, 760, 600))
        self.tablewidget.setObjectName("tablewidget")

        self.tablewidget.setColumnCount(5)
        self.tablewidget.setHorizontalHeaderLabels(annothdg + [""])
        self.tablewidget.setColumnWidth(0, 96)
        self.tablewidget.setColumnWidth(1, 96)
        self.tablewidget.setColumnWidth(2, 96)
        self.tablewidget.setColumnWidth(3, 396)
        self.tablewidget.setColumnWidth(4, 96)

        self.tablewidget.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.tablewidget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tablewidget.selectionModel().selectionChanged.connect(self._on_cell_selection)

        self.tablewidget.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tablewidget.setEditTriggers(QAbstractItemView.DoubleClicked)

        self.tablewidget.itemChanged.connect(self._update_annot)

    def _import_video(self):
        # Stops current video
        if self.videoplayer.is_playing():
            self._stop()

        # Save changes before closing
        if (not self.annot.empty) & self.savebtn.isEnabled():
            reply = self._confirm_action("Save changes to annotations?")
            saveoutcome = 0

            if reply == QMessageBox.Yes:
                saveoutcome = self._save()

            if saveoutcome != 0:
                return

        # Opens new video
        filename, _ = QFileDialog.getOpenFileName(self, "Open video", self.videodpath)

        if not filename:
            return

        video = Media(filename)
        self.videoplayer.set_hwnd(self.videoframe.winId())

        self.videoplayer.set_media(video)
        self._play()

        # Parses video metadata
        video.parse()
        self.videofname = video.get_meta(0)
        self.duration = self.videoplayer.get_length()
        #self.fps = self.videoplayer.get_fps()

        self.setWindowTitle(self.videofname)

        # Clears annotations
        self.annot = DataFrame(columns=annothdg)
        self._refresh_table()
        self.labelbackup = None
        self.undostate = -1

        # Creates new backup file
        if self.backupfpath is not None:
            if exists(self.backupfpath):
                remove(self.backupfpath)
        self._create_new_backup_file()

        # Updates button states
        self.playbtn.setEnabled(True)
        self.addrowbtn.setEnabled(True)
        self.importannotbtn.setEnabled(True)
        self.adddropdownbtn.setEnabled(True)
        self._update_btn_states(False)

    def _play(self):
        self.videoplayer.play()
        self.playbtn.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self.timer.start()
        self.ispaused = False

    def _pause(self):
        self.videoplayer.pause()
        self.playbtn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.timer.stop()
        self.ispaused = True

    def _play_pause(self):
        if self.videoplayer.is_playing():
            self._pause()
        else:
            self._play()

    def _stop(self):
        self.videoplayer.stop()
        self.playbtn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.timer.stop()

    def _set_position(self, position):
        if self.videofname is not None:
            if (not self.videoplayer.is_playing()) & (not self.ispaused):
                self._play()
            self.videoplayer.set_position(position/self.seekbarmax)
            self.currtime = self.videoplayer.get_time()
            self._print_time()

    def _update_position(self):
        self.seekbar.setValue(int(self.videoplayer.get_position()*self.seekbarmax))
        self.currtime = self.videoplayer.get_time()
        self._print_time()

        # Stops video player when video ends
        if (not self.videoplayer.is_playing()) & (not self.ispaused):
            self._stop()
            self.seekbar.setValue(self.seekbarmax)
            self.currtime = self.duration
            self._print_time()

    def _print_time(self):
        self.time.setText("/".join(map(lambda x : str(timedelta(milliseconds=x)).split(".")[0], (self.currtime, self.duration))))

    def _get_time(self):
        row, col = self.tablewidget.currentRow(), self.tablewidget.currentColumn()

        if (row != -1) & (col in [1, 2]):
            # Backup current annotations
            self.annot.to_csv(self.backupfpath, index=False)
            self.labelbackup = None
            self.undostate = 0

            # Updates annotations
            self.annot.loc[row, self.annot.columns[col]] = str(timedelta(milliseconds=self.currtime)).split(".")[0]
            self._refresh_table()
            self.tablewidget.setCurrentItem(self.tablewidget.item(row, col))

            # Updates button states
            self._update_btn_states()

    def _find_position(self):
        row, col = self.tablewidget.currentRow(), self.tablewidget.currentColumn()

        try:
            h, m, s = map(int, self.tablewidget.selectedItems()[0].text().split(":"))
        except:
            return

        ms = int(timedelta(hours=h, minutes=m, seconds=s).total_seconds()) * 1000

        if ms <= self.duration:
            # Plays video from selected time
            if (not self.videoplayer.is_playing()) & (not self.ispaused):
                self._play()
            self.videoplayer.set_time(ms)
            self.seekbar.setValue(int(self.videoplayer.get_position()*self.seekbarmax))
            self.currtime = self.videoplayer.get_time()
            self._print_time()

            # Updates annotations
            self.tablewidget.setCurrentItem(None)
        else:
            self._error("Selected time exceeds video duration." )

    def _set_volume(self, volume):
        if self.videofname is not None:
            self.videoplayer.audio_set_volume(volume)

    def _import_csv_file(self, dpath, req_hdg=None):
        if self.videoplayer.is_playing():
            self._pause()

        # Opens new file
        filename, _ = QFileDialog.getOpenFileName(self, "Open file", dpath)

        if not filename:
            return

        # Checks file uploaded is in csv format and contains required columns
        if splitext(filename)[-1] != ".csv":
            self._file_error("Please input a csv file.")
            return

        df = read_csv(filename)
        df.columns = list(map(lambda x : x.lower().strip(), df.columns.tolist()))

        missing_columns = [hdg for hdg in req_hdg if hdg not in df.columns]
        if len(missing_columns) > 0:
            self._file_error("The following columns are missing from the file uploaded:\n\n%s" %("\n".join(missing_columns)))
            return

        return df[req_hdg].copy()

    def _file_error(self, text):
        if self.videoplayer.is_playing():
            self._pause()

        self._error(text)

    def _import_annot_file(self):
        csv = self._import_csv_file(self.annotdpath, annothdg)

        if csv is not None:
            if not self.annot.empty:
                # Confirms action
                reply = self._confirm_action("Are you sure you want to overwrite existing annotations?")

                if reply == QMessageBox.No:
                    return

            # Backup current annotations
            self.annot.to_csv(self.backupfpath, index=False)
            self.labelbackup = None
            self.undostate = 0

            # Remove leading and trailing whitespaces from labels
            annotlabels = list(map(lambda x : str(x).strip(), csv["label"]))

            if self.label is not None:
                # Checks all labels in annotations exist in label drop-down list. Otherwise, updates label drop-down list
                labels = self.label["label"].tolist()
                labels = self._check_missing_labels(annotlabels, labels)
                self.label = DataFrame(labels, columns=["label"])

            # Updates annotations
            csv["label"] = annotlabels
            csv = csv.drop_duplicates().reset_index(drop=True)
            self.annot = csv
            self._refresh_table()

            # Updates button states
            self._update_btn_states()

    def _import_label_file(self):
        csv = self._import_csv_file(self.labeldpath, labelhdg)

        if csv is not None:
            if self.label is not None:
                # Confirms action
                reply = self._confirm_action("Are you sure you want to overwrite existing label drop-down list?")

                if reply == QMessageBox.No:
                    return

            # Backup current annotations
            self.annot.to_csv(self.backupfpath, index=False)
            self.labelbackup = self.label.copy() if self.label is not None else None
            self.undostate = 1

            # Remove duplicates and leading and trailing whitespaces from labels
            csv = csv[list(map(lambda x: not x, csv["label"].str.strip().str.lower().duplicated()))]
            labels = list(map(lambda x : str(x).strip(), csv["label"]))

            # Checks all labels in annotations exist in label drop-down list. Otherwise, updates label drop-down list
            annotlabels = self.annot["label"].tolist()
            labels = self._check_missing_labels(annotlabels, labels)

            # Adds label drop-down list
            self.label = DataFrame(labels, columns=["label"]).sort_values('label').reset_index(drop=True)
            self._refresh_table()

            if self.labelbackup is not None:
                self._success("New label drop-down list added.")

            if self.annot.empty & (self.labelbackup is None):
                self._success("Label drop-down list added.")

            # Updates button states
            self.deldropdownbtn.setEnabled(True)
            self._update_btn_states()

    def _check_missing_labels(self, annotlabels, labels):
        # Checks all labels in annotations exist in label drop-down list
        missing_labels = []

        for label in annotlabels:
            label = str(label)
            if (label != "") & (label != "nan") & (label.lower() not in list(map(lambda x : str(x).lower(), labels))):
                if label.lower() not in list(map(lambda x : str(x).lower(), missing_labels)):
                    missing_labels.append(label)

        if len(missing_labels) > 0:
            if self.videoplayer.is_playing():
                self._pause()

            # Adds missing labels to label drop-down list
            reply = self._confirm_action("The following label(s) are missing from label drop-down list:\n\n%s\n\nAdd to label drop-down list?" %("\n".join(missing_labels)))

            if reply == QMessageBox.Yes:
                labels += missing_labels

        return labels

    def _delete_label_file(self):
        if self.videoplayer.is_playing():
            self._pause()

        # Confirms action
        reply = self._confirm_action("Are you sure you want to remove label drop-down list?")

        if reply == QMessageBox.Yes:
            # Backup current annotations
            self.annot.to_csv(self.backupfpath, index=False)
            self.labelbackup = self.label.copy() if self.label is not None else None
            self.undostate = 1

            # Removes label drop-down list
            self.label = None
            self._refresh_table()

            if self.annot.empty:
                self._success("Label drop-down list removed.")

            # Updates button states
            self.deldropdownbtn.setEnabled(False)
            self._update_btn_states()

    def _on_cell_selection(self):
        self._update_btn_states()

    def _update_annot(self):
        if len(self.tablewidget.selectedItems()) == 0:
            return

        # Backup current annotations
        self.annot.to_csv(self.backupfpath, index=False)
        self.labelbackup = None
        self.undostate = 0

        # Updates annotations
        row, col = self.tablewidget.currentRow(), self.tablewidget.currentColumn()
        self.annot.loc[row, self.annot.columns[col]] = self.tablewidget.selectedItems()[0].text().strip()
        self._refresh_table()

        # Updates button states
        self._update_btn_states()

    def _refresh_table(self):
        size = self.annot.shape[0]

        self.tablewidget.clearContents()
        self.tablewidget.setRowCount(0)

        for i in range(size):
            rowcount = self.tablewidget.rowCount()
            self.tablewidget.insertRow(rowcount)

            rowitems = [item if (item != "nan") else "" for item in list(map(str, self.annot.loc[i]))]

            self.tablewidget.setItem(i, 0, QTableWidgetItem(rowitems[0]))
            self.tablewidget.setItem(i, 1, QTableWidgetItem(rowitems[1]))
            self.tablewidget.setItem(i, 2, QTableWidgetItem(rowitems[2]))
            if self.label is None:
                self.tablewidget.setItem(i, 3, QTableWidgetItem(rowitems[3]))
            else:
                self.tablewidget.setCellWidget(i, 3, self._add_combo_box(i, rowitems[3]))
            self.tablewidget.setCellWidget(i, 4, self._add_delete_btn(i))

    def _add_combo_box(self, row, label):
        # Creates label drop-down list
        combobox = QComboBox()
        comboitems = self.label["label"].tolist()
        comboitems.insert(0, "")

        for item in comboitems:
            combobox.addItem(item)

        # Checks label exists in label drop-down list. If not, remove label
        label = label.lower()
        comboitems = list(map(lambda x : x.lower(), comboitems))
        if label in comboitems:
            currentindex = comboitems.index(label)
            self.annot.loc[row, "label"] = comboitems[currentindex]
        else:
            currentindex = 0
            self.annot.loc[row, "label"] = ""

        combobox.setCurrentIndex(currentindex)

        combobox.currentIndexChanged.connect(lambda: self._selection_change(combobox, row))

        return combobox

    def _selection_change(self, combobox, row):
        # Backup current annotations
        self.annot.to_csv(self.backupfpath, index=False)
        self.labelbackup = None
        self.undostate = 0

        # Updates annotations
        self.annot.loc[row, "label"] = combobox.currentText()

        # Updates button state
        self._update_btn_states()

    def _add_delete_btn(self, row):
        deletebtnwidget = QWidget()
        deletebtn = QPushButton("Delete")
        deletebtn.setStyleSheet(""" text-align : center;
                              background-color : NavajoWhite;
                              height : 32px;
                              border-style: outset """)

        deletebtn.clicked.connect(lambda:self._delete_row(row))

        hlayout = QHBoxLayout()
        hlayout.addWidget(deletebtn)
        hlayout.setContentsMargins(6, 3, 6, 3)
        deletebtnwidget.setLayout(hlayout)

        return deletebtnwidget

    def _add_row(self):
        # Backup current annotation data
        self.annot.to_csv(self.backupfpath, index=False)
        self.labelbackup = None
        self.undostate = 0

        # Updates annotations
        row, col = self.tablewidget.currentRow(), self.tablewidget.currentColumn()
        col = 0 if col == -1 else col
        newrow = (row+1) if (row!=-1) else self.tablewidget.rowCount()

        annotupr = self.annot[:newrow].copy()
        annotlwr = self.annot[newrow:].copy()
        annotupr.loc[newrow] = (self.videofname, "", "", "")

        self.annot = annotupr.append(annotlwr).reset_index(drop=True).copy()
        del annotupr, annotlwr
        self._refresh_table()
        self.tablewidget.setCurrentItem(self.tablewidget.item(newrow, col))

        # Updates button states
        self._update_btn_states()

    def _delete_row(self, row):
        # Backup current annotation data
        self.annot.to_csv(self.backupfpath, index=False)
        self.labelbackup = None
        self.undostate = 0

        col = self.tablewidget.currentColumn()
        col = 0 if col == -1 else col

        # Updates annotations
        self.annot.drop(row, inplace=True)
        self.annot = self.annot.reset_index(drop=True)
        self._refresh_table()

        if row < self.annot.shape[0]:
            self.tablewidget.setCurrentItem(self.tablewidget.item(row, col))
        elif row > 0:
            self.tablewidget.setCurrentItem(self.tablewidget.item(row-1, col))

        # Updates button states
        self._update_btn_states()

    def _clear_table(self):
        if self.videoplayer.is_playing():
            self._pause()

        # Confirms action
        reply = self._confirm_action("Are you sure you want to clear table?")

        if reply == QMessageBox.Yes:
            # Backup current annotations
            self.annot.to_csv(self.backupfpath, index=False)
            self.labelbackup = None
            self.undostate = 0

            # Clears annotations
            self.annot = DataFrame(columns=annothdg)
            self._refresh_table()

            # Updates button states
            self._update_btn_states()

    def _undo(self):
        if self.undostate == -1:
            return

        row, col = self.tablewidget.currentRow(), self.tablewidget.currentColumn()

        if self.undostate == 0:
            # Reads data from backup file
            try:
                csv = read_csv(self.backupfpath)
                csv = csv[annothdg]
            except:
                return

            # Updates annotations
            self.annot = csv
            self._refresh_table()

        elif self.undostate == 1:
            # Updates labels
            printmsg = True if ((self.label is not None) & (self.labelbackup is not None)) else False
            self.label = self.labelbackup
            self._refresh_table()

            if printmsg | (self.annot.empty) & (self.label is not None):
                self._success("Reverted to previous label drop-down list.")

            if (self.annot.empty) & (self.label is None):
                self._success("Label drop-down list removed.")

        if (row != -1) & (col != -1):
            self.tablewidget.setCurrentItem(self.tablewidget.item(row, col))

        self.undostate = -1

        # Updates button states
        self._update_btn_states()
        if self.label is not None:
            self.deldropdownbtn.setEnabled(True)
        else:
            self.deldropdownbtn.setEnabled(False)

    def _save(self):
        if self.videofname is not None:
            videotitle = splitext(self.videofname)[0]

            # Saves annotations
            annotfpath = join(self.annotdpath, videotitle + "_annotations.csv")
            try:
                self.annot.to_csv(annotfpath, index=None)
            except:
                self._error("Could not save annotations to %s.\n\nPlease check that the file is not currently in used by another application." %annotfpath)
                return

            print("Annotations saved to: ", annotfpath)

            # Saves labels
            if self.label is not None:
                labelfpath = join(self.labeldpath, videotitle + "_labels.csv")
                try:
                    self.label.to_csv(labelfpath, index=None)
                except:
                    self._error("Could not save labels to %s.\n\nPlease check that the file is not currently in used by another application." %labelfpath)
                    return

                print("Labels saved to: ", labelfpath)

            # Updates button states
            self._update_btn_states(save=False)

            return 0

    def _confirm_action(self, text):
        dialogbox = QMessageBox()
        dialogbox.setIcon(QMessageBox.Question)
        dialogbox.setWindowTitle("Confirm")
        dialogbox.setText(text)
        dialogbox.addButton(QMessageBox.Yes)
        dialogbox.addButton(QMessageBox.No)
        dialogbox.setDefaultButton(QMessageBox.No)
        return dialogbox.exec()

    def _success(self, text):
        dialogbox = QMessageBox()
        dialogbox.setIcon(QMessageBox.Information)
        dialogbox.setWindowTitle("Success")
        dialogbox.setText(text)
        dialogbox.exec_()

    def _error(self, text):
        dialogbox = QMessageBox()
        dialogbox.setIcon(QMessageBox.Critical)
        dialogbox.setWindowTitle("Error")
        dialogbox.setText(text)
        dialogbox.exec_()

    # Shortcuts

    def _shortcut_ctrlplus(self):
        if self.videofname is not None:
            self._add_row()

    def _shortcut_ctrlminus(self):
        row = self.tablewidget.currentRow()

        if row != -1:
            self._delete_row(row)

    def _shortcut_up(self):
        if self.videofname is not None:
            row, col = self.tablewidget.currentRow(), self.tablewidget.currentColumn()

            if (row != -1) & (col != -1):
                # If table cell selected, move to cell above
                self.tablewidget.setCurrentItem(self.tablewidget.item(max(0, row-1), col))

    def _shortcut_down(self):
        if self.videofname is not None:
            row, col = self.tablewidget.currentRow(), self.tablewidget.currentColumn()

            if (row != -1) & (col != -1):
                # If table cell selected, move to cell below
                self.tablewidget.setCurrentItem(self.tablewidget.item(min(row+1, self.annot.shape[0]-1), col))

    def _shortcut_left(self):
        if self.videofname is not None:
            row, col = self.tablewidget.currentRow(), self.tablewidget.currentColumn()

            if (row == -1) & (col == -1):
                # If no table cell selected, rewind video by 5s
                position = max(0, self.videoplayer.get_position() - 5000/self.duration)
                self._skip(position)

            elif (row != -1) & (col != -1):
                # If table cell selected, move to cell to the left
                self.tablewidget.setCurrentItem(self.tablewidget.item(row, max(0, col-1)))

    def _shortcut_right(self):
        if self.videofname is not None:
            row, col = self.tablewidget.currentRow(), self.tablewidget.currentColumn()

            if (row == -1) & (col == -1):
                # If no table cell selected, fast forward video by 5s
                position = min(self.videoplayer.get_position() + 5000/self.duration, self.duration)
                self._skip(position)

            elif (row != -1) & (col != -1):
                # If table cell selected, move to cell to the right
                lastcol = 2 if self.label is not None else 3
                self.tablewidget.setCurrentItem(self.tablewidget.item(row, min(col+1, lastcol)))

    def _skip(self, position):
        if self.videoplayer.is_playing() | self.ispaused:
            self.videoplayer.set_position(position)
            self.seekbar.setValue(int(self.videoplayer.get_position()*self.seekbarmax))
            self.currtime = self.videoplayer.get_time()
            self._print_time()

    def _shortcut_tab(self):
        if self.videofname is not None:
            row, col = self.tablewidget.currentRow(), self.tablewidget.currentColumn()

            if (row != -1) & (col != -1):
                # If table cell selected, move to next cell
                lastrow = self.annot.shape[0] - 1
                lastcol = 2 if self.label is not None else 3
                nextrow = row if (col < lastcol) else (row+1)%(lastrow+1)
                nextcol = (col+1) % (lastcol+1)

                self.tablewidget.setCurrentItem(self.tablewidget.item(nextrow, nextcol))

    def _shortcut_backtab(self):
        if self.videofname is not None:
            row, col = self.tablewidget.currentRow(), self.tablewidget.currentColumn()

            if (row != -1) & (col != -1):
                # If table cell selected, move to previous cell
                lastrow = self.annot.shape[0] - 1
                lastcol = 2 if self.label is not None else 3
                prevrow = row if (col!=0) else ((row-1) if (row!=0) else lastrow)
                prevcol = (col-1) if (col!=0) else lastcol

                self.tablewidget.setCurrentItem(self.tablewidget.item(prevrow, prevcol))

    def _shortcut_home(self):
        if self.videofname is not None:
            row, col = self.tablewidget.currentRow(), self.tablewidget.currentColumn()

            if (row != -1) & (col != -1):
                # If table cell selected, move to first cell in row
                self.tablewidget.setCurrentItem(self.tablewidget.item(row, 0))

    def _shortcut_end(self):
        if self.videofname is not None:
            row, col = self.tablewidget.currentRow(), self.tablewidget.currentColumn()

            if (row != -1) & (col != -1):
                # If table cell selected, move to last cell in row
                lastcol = 2 if self.label is not None else 3
                self.tablewidget.setCurrentItem(self.tablewidget.item(row, lastcol))

    def _shortcut_space(self):
        if self.videofname is not None:
            row, col = self.tablewidget.currentRow(), self.tablewidget.currentColumn()

            if (row == -1) & (col == -1):
                # If no table cell selected, play/pause video
                self._play_pause()

            elif (row != -1) & (col != -1):
                # If table cell selected, edit cell
                self.tablewidget.editItem(self.tablewidget.item(row, col))

    def _shortcut_ins(self):
        self._get_time()

    def _shortcut_cut(self):
        self._shortcut_copy()
        self._shortcut_del()

    def _shortcut_copy(self):
        row, col = self.tablewidget.currentRow(), self.tablewidget.currentColumn()

        if (row != -1) & (col != -1):
            clipboard = QApplication.clipboard()
            clipboard.setText(self.tablewidget.selectedItems()[0].text())

    def _shortcut_paste(self):
        row, col = self.tablewidget.currentRow(), self.tablewidget.currentColumn()

        if (row != -1) & (col != -1):
            # Backup current annotation data
            self.annot.to_csv(self.backupfpath, index=False)
            self.labelbackup = None
            self.undostate = 0

            # Updates annotations
            clipboard = QApplication.clipboard()
            self.annot.loc[row, self.annot.columns[col]] = clipboard.text()
            self._refresh_table()
            self.tablewidget.setCurrentItem(self.tablewidget.item(row, col))

            # Updates button states
            self._update_btn_states()

    def _shortcut_del(self):
        row, col = self.tablewidget.currentRow(), self.tablewidget.currentColumn()

        if (row != -1) & (col != -1):
            # Backup current annotation data
            self.annot.to_csv(self.backupfpath, index=False)
            self.labelbackup = None
            self.undostate = 0

            # Updates annotations
            self.annot.loc[row, self.annot.columns[col]] = ""
            self._refresh_table()
            self.tablewidget.setCurrentItem(self.tablewidget.item(row, col))

            # Updates button states
            self._update_btn_states()

    def _shortcut_esc(self):
        self.tablewidget.setCurrentItem(None)

    def _update_btn_states(self, save=True):
        row, col = self.tablewidget.currentRow(), self.tablewidget.currentColumn()

        if (row != -1) & (col in [1, 2]):
            self.inserttimebtn.setEnabled(True)
            self.seekpositionbtn.setEnabled(True)
        else:
            self.inserttimebtn.setEnabled(False)
            self.seekpositionbtn.setEnabled(False)

        if not self.annot.empty:
            self.cleartablebtn.setEnabled(True)
        else:
            self.cleartablebtn.setEnabled(False)

        self.savebtn.setEnabled(save)

    def closeEvent(self, event):
        if (not self.annot.empty) & self.savebtn.isEnabled():
            reply = self._confirm_action("Save changes to annotations?")
            saveoutcome = 0

            if reply == QMessageBox.Yes:
                saveoutcome = self._save()

            if saveoutcome != 0:
                 event.ignore()
                 return

        if self.backupfpath is not None:
            if exists(self.backupfpath):
                remove(self.backupfpath)

        event.accept()

if __name__ == "__main__":
    app = QApplication(argv)

    videodpath = argv[1] if len(argv) >= 2 else "videos"
    annotdpath = argv[2] if len(argv) >= 3 else "annotations"
    labeldpath = argv[3] if len(argv) >= 4 else "labels"

    videoannotator = VideoAnnotator(videodpath, annotdpath, labeldpath)
    videoannotator.show()
    videoannotator.setFixedSize(1800, 600)
    exit(app.exec_())
