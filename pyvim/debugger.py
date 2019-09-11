import requests
import os
import sqlite3
from flask import Flask, request
from multiprocessing import Process
import logging
import sys

from PyQt5.QtWidgets import QMainWindow, QApplication, QWidget, QAction, \
    QTableWidget, QTableWidgetItem, QVBoxLayout
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSignal, QObject, QThread
import time


class ValueWatcher(QWidget):
    update_signal = pyqtSignal(int, int, str)

    def __init__(self, editor):
        super().__init__()

        self.setWindowTitle("Variable Watcher")
        self.setGeometry(0, 0, 300, 200)
        self.table = QTableWidget()
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.table)
        self.setLayout(self.layout)

        self.editor = editor

        self.update_signal.connect(self.handle_update)
        self.show()

    def handle_update(self, y, x, v):
        self.table.setItem(y, x, QTableWidgetItem(v))


class Debugger:

    def __init__(self, editor, hostname="localhost", port_num=8888,
                 database="debug.db"):
        self.host_name = hostname
        self.port_num = port_num
        self.editor = editor
        self.debugger_port = 8889

        # open the database file
        database = os.path.abspath(database)
        # since it is read-only, this is fine
        self.conn = sqlite3.connect(database, check_same_thread=False)
        self.cursor = self.conn.cursor()

        # disable flask logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)

        # flask app
        self.app = Flask(__name__)

        self.top = "TOP"

        self.watcher = ValueWatcher(self)
        self.watcher.table.setRowCount(3)
        self.watcher.table.setColumnCount(2)

        # define route
        @self.app.route("/status/breakpoint", methods=["POST"])
        def hit_breakpoint():
            id_ = request.get_data()
            id_ = int(id_)
            self.update(id_)
            return "Okay", 200

        class Worker(QThread):
            app = self.app
            debugger_port = self.debugger_port

            def __init__(self):
                QThread.__init__(self)

            def run(self):
                self.app.run(host="0.0.0.0", port=self.debugger_port)

        self.server_process = Worker()
        self.server_process.start()

        self.connect()

    def stop(self):
        self.server_process.terminate()

    def connect(self):
        try:
            r = requests.post("http://{0}:{1}/connect".format(self.host_name,
                                                              self.port_num),
                              data="{0}:{1}".format("0.0.0.0",
                                                    self.debugger_port))
            error = r.status_code != 200
        except requests.exceptions.ConnectionError:
            error = True
        if error:
            self.editor.show_message("Failed to connect to simulator")

    def update(self, stmt_id):
        self.cursor.execute("SELECT * from variable WHERE id=?", (stmt_id,))
        result = self.cursor.fetchall()
        table = []
        for gen_handle, var, front_var, _ in result:
            if self.top not in gen_handle:
                handle = self.top + "." + gen_handle
            else:
                handle = gen_handle
            handle = handle + "." + var
            try:
                r = requests.get(
                    "http://{0}:{1}/value/{2}".format(self.host_name,
                                                      self.port_num,
                                                      handle))
                error = r.status_code != 200
            except requests.exceptions.ConnectionError:
                error = True
                r = None
            if error:
                value = "ERROR"
            else:
                value = r.content
            table.append((front_var, value))

        for idx, (var, value) in enumerate(table):
            # self.watcher.table.setItem(idx, 0, QTableWidgetItem(str(var)))
            self.watcher.update_signal.emit(idx, 0, str(var))
            self.watcher.update_signal.emit(idx, 1, str(value))
        #self.watcher.move(0, 0)

    def continue_(self):
        try:
            r = requests.post("http://{0}:{1}/continue".format(self.host_name,
                                                               self.port_num))
            error = r.status_code != 200
        except requests.exceptions.ConnectionError:
            error = True
        if error:
            self.editor.show_message("Unable to connect to the debugger")

    def set_break_point(self, filename, line_number):
        if not filename:
            self.editor.show_message("Unable to set a break point")
            return
        filename = os.path.abspath(filename)

        # running query
        self.cursor.execute(
            "SELECT id FROM breakpoint WHERE filename=? AND line_num=?",
            (filename, line_number))
        r = self.cursor.fetchall()
        if len(r) != 1:
            self.editor.show_message("Not a valid breakpoint")
            return
        stmt_id = r[0][0]
        try:
            r = requests.post(
                "http://{0}:{1}/breakpoint/add/{2}".format(self.host_name,
                                                           self.port_num,
                                                           stmt_id))
            error = r.status_code != 200
        except requests.exceptions.ConnectionError:
            error = True
        if error:
            self.editor.show_message("Unable to set a break point")

    def get_all_files(self):
        # running query
        self.cursor.execute("SELECT DISTINCT filename FROM breakpoint")
        result = self.cursor.fetchall()
        return [x[0] for x in result]

    def get_available_breakpoints(self):
        eb = self.editor.current_editor_buffer
        if eb is None:
            return []
        filename = eb.location
        if filename is None:
            return []
        filename = os.path.abspath(filename)
        self.cursor.execute("SELECT line_num FROM breakpoint WHERE filename=?",
                            (filename,))
        result = self.cursor.fetchall()
        return [x[0] for x in result]
