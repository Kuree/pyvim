#!/usr/bin/env python
"""
pyvim: Pure Python Vim clone.
Usage:
    pyvim [-p] [-o] [-O] [-u <pyvimrc>] [<location>...]

Options:
    -p           : Open files in tab pages.
    -o           : Split horizontally.
    -O           : Split vertically.
    -u <pyvimrc> : Use this .pyvimrc file instead.
"""
from __future__ import unicode_literals
import docopt
import os
import sys

from pyvim.editor import Editor
from pyvim.rc_file import run_rc_file
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QThread

__all__ = (
    'run',
)


def run():
    a = docopt.docopt(__doc__)
    locations = a['<location>']
    in_tab_pages = True
    hsplit = a['-o']
    vsplit = a['-O']
    pyvimrc = a['-u']

    # compute the db
    if len(locations) != 1:
        print("Please indicate a debug database file", file=sys.stderr)
        exit(1)

    database = locations[0]
    if not os.path.isfile(database):
        print(database, "does not exsit", file=sys.stderr)
        exit(1)

    # watcher
    app = QApplication(sys.argv)
    # Create new editor instance.
    editor = Editor(database)

    # Apply rc file.
    if pyvimrc:
        run_rc_file(editor, pyvimrc)
    else:
        default_pyvimrc = os.path.expanduser('~/.pyvimrc')

        if os.path.exists(default_pyvimrc):
            run_rc_file(editor, default_pyvimrc)

    # get all the locations
    locations = editor.debugger.get_all_files()

    # Load files and run.
    editor.load_initial_files(locations, in_tab_pages=in_tab_pages,
                              hsplit=hsplit, vsplit=vsplit)

    class LoopThread(QThread):
        def __init__(self):
            QThread.__init__(self)

        def __del__(self):
            self.wait()

        def run(self):
            editor.run()
    t = LoopThread()
    t.start()
    app.exec_()


if __name__ == '__main__':
    run()
