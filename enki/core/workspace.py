"""
workspace --- Open documents and manage it
==========================================

Terminology:

Workspace - main working area, where documents are placed.

Document - opened file, widget on workspace. :class:`enki.core.document.Document` instance

:class:`enki.core.workspace.Workspace`
"""

import os.path
import sys

from PyQt4.QtGui import QAction, \
                        QApplication, \
                        QDialog, QDialogButtonBox, \
                        QFileDialog, \
                        QKeySequence, \
                        QListWidgetItem, \
                        QMessageBox, \
                        QStackedWidget, \
                        QShortcut
from PyQt4.QtCore import pyqtSignal, QEvent, Qt  # pylint: disable=E0611
from PyQt4 import uic

from enki.core.core import core, DATA_FILES_PATH
import enki.core.openedfilemodel
from enki.core.document import Document


class _UISaveFiles(QDialog):
    """Save files dialog.
    Shows checkable list of not saved files.
    """
    def __init__(self, workspace, documents):
        super(_UISaveFiles, self).__init__(workspace)
        self.cancelled = False
        uic.loadUi(os.path.join(DATA_FILES_PATH, 'ui/SaveFiles.ui'), self)
        self.buttonBox.clicked.connect(self._onButtonClicked)

        self._itemToDocument = {}
        for document in documents:
            name = document.fileName()
            if name is None:
                name = 'untitled'
            item = QListWidgetItem( name, self.listWidget )
            if document.filePath() is not None:
                item.setToolTip( document.filePath() )
            item.setCheckState( Qt.Checked )
            self._itemToDocument[item] = document
        self.buttonBox.button(self.buttonBox.Discard).setText(self.tr('Close &without Saving'))
        self.buttonBox.button(self.buttonBox.Cancel).setText(self.tr('&Cancel Close'))
        self.buttonBox.button(self.buttonBox.Save).setText(self.tr('&Save checked'))

        self.buttonBox.button(QDialogButtonBox.Cancel).setFocus()

    def _onButtonClicked(self, button):
        """Button click handler.
        Saves files, if necessary, accepts or rejects dialog
        """
        stButtton = self.buttonBox.standardButton(button)
        if stButtton == QDialogButtonBox.Save:
            for i in range(self.listWidget.count()):
                if  self.listWidget.item( i ).checkState() != Qt.Unchecked:
                    self._itemToDocument[self.listWidget.item(i)].saveFile()
            self.accept()
        elif stButtton == QDialogButtonBox.Cancel:
            self.reject()
        elif stButtton == QDialogButtonBox.Discard:
            self.accept()
        else:
            assert 0


class Workspace(QStackedWidget):
    """
    Class manages set of opened documents, allows to open new file

    instance is accessible as: ::

        from enki.core.core import core
        core.workspace()

    """

    documentOpened = pyqtSignal(Document)
    """
    documentOpened(:class:`enki.core.document.Document`)

    **Signal** emitted, when document has been created, i.e. textual file opened,
    or some other document added to workspace
    """  # pylint: disable=W0105

    documentClosed = pyqtSignal(Document)
    """
    documentClosed(:class:`enki.core.document.Document`)

    **Signal** emitted, when document was closed
    """  # pylint: disable=W0105

    currentDocumentChanged = pyqtSignal(Document,
                                        Document)
    """
    currentDocumentChanged(:class:`enki.core.document.Document` old,
    :class:`enki.core.document.Document` current)

    **Signal** emitted, when current document changed, i.e. user selected another document,
    new document opened, current closed
    """  # pylint: disable=W0105

    modificationChanged = pyqtSignal(Document, bool)
    """
    modificationChanged(document, modified)

    **Signal** emitted, when modified state of a document had been changed (file edited, or saved)
    Bool parameter contains new value
    Convenience signal, which retransmits original signal, sent by the document
    """  # pylint: disable=W0105

    cursorPositionChanged = pyqtSignal(Document)
    """
    cursorPositionChanged(document)

    **Signal** emitted, when cursor position has been changed
    Convenience signal, which retransmits original signal, sent by the document
    """  # pylint: disable=W0105

    textChanged = pyqtSignal(Document)
    """
    textChanged(document)

    **Signal** emitted, when text has been chagned
    Convenience signal, which retransmits original signal, sent by the document
    """  # pylint: disable=W0105

    languageChanged = pyqtSignal(Document, unicode)
    """
    languageChanged(document, language)

    **Signal** emitted, when highlighting (programming) language of a file has been changed
    Convenience signal, which retransmits original signal, sent by Qutepart
    """  # pylint: disable=W0105

    indentWidthChanged = pyqtSignal(Document, int)
    """
    indentWidthChanged(document, width)

    **Signal** emitted, when indentation with has been changed
    Convenience signal, which retransmits original signal, sent by the document
    """  # pylint: disable=W0105

    indentUseTabsChanged = pyqtSignal(Document, bool)
    """
    indentUseTabsChanged(document, use)

    **Signal** emitted, when indentation mode has been changed
    Convenience signal, which retransmits original signal, sent by the document
    """  # pylint: disable=W0105

    eolChanged = pyqtSignal(Document, unicode)
    """
    eolChanged(document, eol)

    **Signal** emitted, when EOL mode has been changed
    Convenience signal, which retransmits original signal, sent by the document
    """  # pylint: disable=W0105

    escPressed = pyqtSignal()
    """
    escPressed()

    **Signal** emitted, when Esc pressed in the editor.
    Search widget closes themselves on this signal
    """  # pylint: disable=W0105

    _QUTEPART_ACTIONS = (

        ('mEdit/mCopyPasteLines/aCopy', 'copyLineAction'),
        ('mEdit/mCopyPasteLines/aPaste', 'pasteLineAction'),
        ('mEdit/mCopyPasteLines/aCut', 'cutLineAction'),
        ('mEdit/mCopyPasteLines/aDuplicate', 'duplicateLineAction'),

        ('mEdit/aMoveLineUp', 'moveLineUpAction'),
        ('mEdit/aMoveLineDown', 'moveLineDownAction'),
        ('mEdit/aDeleteLine', 'deleteLineAction'),

        ('mEdit/aSeparatorBeforeIndent', None),
        ('mEdit/aDecreaseIndent', 'decreaseIndentAction'),
        ('mEdit/aAutoIndent', 'autoIndentLineAction'),
        ('mEdit/aIndentWithSpace', 'indentWithSpaceAction'),
        ('mEdit/aUnIndentWithSpace', 'unIndentWithSpaceAction'),
        ('mEdit/aInvokeCompletion', 'invokeCompletionAction'),

        ('mNavigation/mScroll/aUp', 'scrollUpAction'),
        ('mNavigation/mScroll/aDown', 'scrollDownAction'),
        ('mNavigation/mScroll/aSelectAndScrollUp', 'selectAndScrollUpAction'),
        ('mNavigation/mScroll/aSelectAndScrollDown', 'selectAndScrollDownAction'),

        ('mFile/aPrint', 'printAction'),

        ('mNavigation/mBookmarks/aToggle', 'toggleBookmarkAction'),
        ('mNavigation/mBookmarks/aPrevious', 'prevBookmarkAction'),
        ('mNavigation/mBookmarks/aNext', 'nextBookmarkAction'),
    )

    def __init__(self, mainWindow):
        """ list of opened documents as it is displayed in the Opened Files Explorer.
        List accessed and modified by enki.core.openedfilemodel.OpenedFileModel class
        """
        QStackedWidget.__init__(self, mainWindow)
        mainWindow.setFocusProxy(self)

        self.setStyleSheet("QStackedWidget { padding-bottom: 5; }");
        self.sortedDocuments = []  # not protected, because available for OpenedFileModel
        self._oldCurrentDocument = None

        # create opened files explorer
        # openedFileExplorer is not protected, because it is available for OpenedFileModel
        self.openedFileExplorer = enki.core.openedfilemodel.OpenedFileExplorer(self)
        mainWindow.addDockWidget(Qt.LeftDockWidgetArea, self.openedFileExplorer)

        self.currentChanged.connect(self._onStackedLayoutIndexChanged)

        self.currentDocumentChanged.connect(self._updateMainWindowTitle)
        self.currentDocumentChanged.connect(self._onCurrentDocumentChanged)

    def del_(self):
        """Terminate workspace. Called by the core to clear actions
        """
        self.openedFileExplorer.del_()

    def _mainWindow(self):
        """Get mainWindow instance
        """
        return self.parentWidget().parentWidget()

    def _updateMainWindowTitle(self):
        """Update window title after document or it's modified state has been changed
        """
        document = self.currentDocument()
        if document:
            name = document.fileName()
            if name is None:
                name = 'untitled'
            if document.qutepart.document().isModified():
                name += '*'
            if document.filePath() is not None:
                path = os.path.dirname(document.filePath())
            else:
                try:
                    path = os.path.abspath(os.curdir)
                except OSError:  # deleted
                    path = '?'

            name += ' - '
            name += path
        else:
            name = self._mainWindow().defaultTitle()
        self._mainWindow().setWindowTitle(name)

    def eventFilter( self, obj, event ):
        pass  # suppress docstring for non-public method
        """
        Handler for QObject events of children
        """
        if  obj.isWidgetType() :
            document = obj
            if  event.type() == QEvent.Close:
                event.ignore()
                self.closeDocument( document )
                return True

        return super(Workspace, self).eventFilter(obj, event)

    def keyPressEvent(self, event):
        pass  # suppress docstring for non-public method
        """Esc press handler. Closes search widget.
        If QShortcut is used instead of keyPressEvent(), completion list is not closed by Esc
        """
        if event.key() == Qt.Key_Escape:
            self.escPressed.emit()

    def _onStackedLayoutIndexChanged(self, index):
        """Handler of change of current document in the stacked layout.
        Only emits a signal, if document realy has changed
        """
        document = self.widget(index)

        if document is None and self.count():  # just lost focus, no real change
            return
        if document == self._oldCurrentDocument:  # just recieved focus, no real change
            return

        if document is not None:
            self.setFocusProxy(document)

        self.currentDocumentChanged.emit(self._oldCurrentDocument, document)
        self._oldCurrentDocument = document

    def _onCurrentDocumentChanged(self, old, new):
        """Change current directory, if current file changed
        """
        if  new and new.filePath() is not None and \
            os.path.exists(os.path.dirname(new.filePath())):
            try:
                os.chdir( os.path.dirname(new.filePath()) )
            except OSError, ex:  # directory might be deleted
                print >> sys.stderr, 'Failed to change directory:', str(ex)

        if old is not None:
            for path, name in self._QUTEPART_ACTIONS:
                core.actionManager().removeAction(path)

        if new is not None:
            for path, name in self._QUTEPART_ACTIONS:
                if name is not None:
                    core.actionManager().addAction(path, getattr(new.qutepart, name))
                else:
                    act = QAction(self)
                    act.setSeparator(True)
                    core.actionManager().addAction(path, act)

    def currentDocument(self):
        """Returns currently active (focused) document. None, if no documents are opened
        """
        return self.currentWidget()

    def setCurrentDocument( self, document ):
        """Select active (focused and visible) document form list of opened documents
        """
        self.setCurrentWidget( document )

    def _activeDocumentByIndex(self, index):
        """Activate document by it's index in the list of documents
        """
        document = self.documents()[index]
        self.setCurrentDocument(document)

    def activateNextDocument(self):
        """Activate next document in the list
        """
        documents = self.documents()

        curIndex = documents.index(self.currentDocument())
        nextIndex = (curIndex + 1) % len(documents)
        self._activeDocumentByIndex(nextIndex)


    def activatePreviousDocument(self):
        """Activate previous document in the list
        """
        documents = self.documents()

        curIndex = documents.index(self.currentDocument())
        prevIndex = (curIndex - 1 + len(documents)) % len(documents)

        self._activeDocumentByIndex(prevIndex)

    def focusCurrentDocument(self):
        """Set focus (cursor) to current document.

        Used if user has finished work with some dialog, and, probably, want's to edit text
        """
        document = self.currentDocument()
        if  document :
            document.setFocus()

    def goTo(self, filePath, absPos=None, line=None, column=None, selectionLength=None):
        """Open file, activate it, and go to specified position. Select text after position, if necessary.

        selectionLength specifies, how much characters should be selected
        """
        document = self.openFile(filePath)  # search for already opened or open new
        if document is None:
            return

        if line is not None:
            assert absPos is None
            if line >= len(document.qutepart.lines):
                line = len(document.qutepart.lines) - 1
                column = None

            if column is None:
                lineToGo = document.qutepart.lines[line]
                column = len(lineToGo) - len(lineToGo.lstrip())  # count of whitespaces before text

            document.qutepart.cursorPosition = line, column
        elif absPos is not None:
            assert line is None and column is None
            document.qutepart.absCursorPosition = absPos

        if selectionLength is not None:
            document.absSelectedPosition = (document.qutepart.absCursorPosition,
                                            document.qutepart.absCursorPosition + selectionLength)

    def _handleDocument( self, document ):
        """Add document to the workspace. Connect signals
        """
        # update file menu
        document.qutepart.document().modificationChanged.connect(self._updateMainWindowTitle)

        # Create lambda functions, which retransmit conveniense signals, and connect it to document signals
        document.qutepart.document().modificationChanged.connect(lambda modified: self.modificationChanged.emit(document, modified))
        document.qutepart.cursorPositionChanged.connect(lambda: self.cursorPositionChanged.emit(document))
        document.qutepart.textChanged.connect(lambda: self.textChanged.emit(document))
        document.qutepart.languageChanged.connect(lambda name: self.languageChanged.emit(document, name))
        document.qutepart.indentWidthChanged.connect(lambda width: self.indentWidthChanged.emit(document, width))
        document.qutepart.indentUseTabsChanged.connect(lambda useTabs: self.indentUseTabsChanged.emit(document, useTabs))
        document.qutepart.eolChanged.connect(lambda eol: self.eolChanged.emit(document, eol))

        # add to workspace
        document.installEventFilter( self )

        self.documentOpened.emit( document )

        self.addWidget( document )

    def _unhandleDocument( self, document ):
        """Remove document from the workspace. Disconnect signals
        """
        # remove from workspace
        document.removeEventFilter( self )
        self.removeWidget(document)

    @staticmethod
    def _isSameFile(pathA, pathB):
        """Check if we are trying to open same file, as already opened
        None is never equal
        """
        if pathA is None or pathB is None:
            return False

        if hasattr(os.path, "samefile"):
            return os.path.isfile(pathA) and \
                   os.path.isfile(pathB) and \
                   os.path.samefile(pathA, pathB)
        else:  # os.path.samefile not available
            return os.path.normpath(pathA) == os.path.normpath(pathB)

    def _openSingleFile(self, filePath):
        """Open 1 file.
        Helper method, used by openFile() and openFiles()
        """
        # Close 'untitled'
        if len(self.documents()) == 1 and \
           self.documents()[0].fileName() is None and \
           not self.documents()[0].filePath() and \
           not self.documents()[0].qutepart.text and \
           not self.documents()[0].qutepart.document().isModified():
            self.closeDocument(self.documents()[0])

        # check if file is already opened
        alreadyOpenedDocument = self.findDocumentForPath(filePath)
        if alreadyOpenedDocument is not None:
            self.setCurrentDocument( alreadyOpenedDocument )
            return alreadyOpenedDocument

        # open file
        try:
            document = Document(self, filePath)
        except IOError as ex:
            QMessageBox.critical(None,
                                 self.tr("Failed to open file"),
                                 unicode(str(ex), 'utf8'))
            return None

        self._handleDocument( document )

        if not os.access(filePath, os.W_OK):
            core.mainWindow().appendMessage( \
                        self.tr( "File '%s' is not writable" % filePath), 4000) # todo fix

        return document

    def openFile(self, filePath):
        """Open file.

        Return document, if opened, None otherwise

        Open modal message box, if failed to open the file
        """
        try:
            QApplication.setOverrideCursor( Qt.WaitCursor )

            document = self._openSingleFile(filePath)
        finally:
            QApplication.restoreOverrideCursor()

        if document is not None:
            self.setCurrentWidget(document)

        return document

    def openFiles(self, filePaths):
        """Open files.

        Open modal message box and stop opening files, if failed to open any file
        """
        documents = []
        try:
            QApplication.setOverrideCursor( Qt.WaitCursor )
            for filePath in filePaths:
                document = self._openSingleFile(filePath)
                if document is None:
                    break

                documents.append(document)
        finally:
            QApplication.restoreOverrideCursor()

    def findDocumentForPath(self, filePath):
        """Try to find document for path.
        Fimilar to open(), but doesn't open file, if it is not opened
        On Unix may return file, for which path is not equal, if soft or hards links are used
        Return None, if not found
        """
        for document in self.sortedDocuments:
            if self._isSameFile(filePath, document.filePath()):
                return document

    def createEmptyNotSavedDocument(self, filePath=None):
        """Create empty not saved document.
        Used on startup, if no file was specified, and after File->New file has been triggered
        """
        if filePath is not None and \
           not os.path.isabs(filePath):
            try:
                current = os.path.abspath(os.path.curdir)
            except OSError:  # current directory might have been deleted
                pass  # leave as is
            else:
                filePath = os.path.join(current, filePath)

        document = Document(self, filePath, createNew=True)
        self._handleDocument(document)
        self.setCurrentWidget(document)

        document.setFocus()

        return document

    def documents(self):
        """Get list of opened documents (:class:`enki.core.document.Document` instances)
        """
        return self.sortedDocuments

    def _doCloseDocument(self, document):
        """Closes document, even if it is modified
        """
        if len(self.sortedDocuments) > 1:  # not the last document
            if document == self.sortedDocuments[-1]:  # the last document
                self.activatePreviousDocument()
            else:  # not the last
                self.activateNextDocument()

        self.documentClosed.emit( document )
        # close document
        self._unhandleDocument( document )
        document.del_()

    def closeDocument( self, document):
        """Close opened file, remove document from workspace and delete the widget.

        Ask for confirmation with dialog, if modified.
        """
        if document.qutepart.document().isModified():
            if _UISaveFiles(self, [document]).exec_() == QDialog.Rejected:
                return

        self._doCloseDocument(document)

    def askToCloseAll(self):
        """If have unsaved documents, ask user to save it and close all.
        Will save documents, checked by user.

        Returns True, if user hasn't pressed Cancel Close
        """
        modifiedDocuments = [d for d in self.documents() if d.qutepart.document().isModified()]
        if modifiedDocuments:
            if (_UISaveFiles( self, modifiedDocuments).exec_() == QDialog.Rejected):
                return False # do not close

        return True

    def closeAllDocuments(self):
        """Close all documents

        If there are not saved documents, dialog will be shown.

        Handler of File->Close->All

        Returns True, if all files had been closed, and False, if save dialog rejected

        If hideMainWindow is True, main window will be hidden, if user hadn't pressed "Cancel Close"
        """
        if not self.askToCloseAll():
            return

        self.forceCloseAllDocuments()

    def forceCloseAllDocuments(self):
        """Close all documents without asking user to save
        """
        for document in self.documents()[::-1]:
            self._doCloseDocument(document)
