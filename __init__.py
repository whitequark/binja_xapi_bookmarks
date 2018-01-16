import binaryninja as bn
import binaryninjax as bnx
from PyQt5.QtCore import Qt, QVariant, QAbstractListModel, QModelIndex
from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import QListView, QMenu


try:
    for _on_reload_fn in _on_reload:
        _on_reload_fn()
except NameError:
    pass
_on_reload = []


class BookmarkItemModel(QAbstractListModel):
    def __init__(self, parent, binaryView):
        QAbstractListModel.__init__(self, parent)
        self._binaryView = binaryView
        try:
            bookmarks = self._binaryView.query_metadata('bookmarks')
            self._bookmarks = [(int(addr), bookmarks[addr]) for addr in bookmarks]
            self._bookmarks.sort()
        except KeyError:
            self._bookmarks = []

    def save(self):
        bookmarks = { addr: name for (addr, name) in self._bookmarks }
        self._binaryView.store_metadata('bookmarks', bookmarks)

    def rowCount(self, parent):
        return len(self._bookmarks)

    def data(self, index, role):
        if role == Qt.DisplayRole:
            fg_color = self.parent().palette().color(QPalette.Active, QPalette.Foreground).rgba()
            addr_color = bnx.getThemeColor('address').rgba()
            sym_color = bnx.getThemeColor('symbol').rgba()

            address, name = self._bookmarks[index.row()]

            lines = []
            lines.append([
                [addr_color, "{:08x}".format(int(address))], [0, " "], [fg_color, name]
            ])

            symbol = self._binaryView.get_symbol_at(address)
            if symbol is not None:
                lines.append([
                    [0, "  "], [fg_color, "at"], [0, " "], [sym_color, symbol.short_name]
                ])

            funcs = self._binaryView.get_functions_containing(address)
            for func in funcs or []:
                offset = address - func.symbol.address
                if offset == 0:
                    continue
                lines.append([
                    [0, "  "], [fg_color, "at"], [0, " "],
                    [sym_color, func.symbol.short_name],
                    [fg_color, " + "], [addr_color, "{:x}".format(offset)]
                ])

            return QVariant(lines)

    def addBookmark(self, addr, name):
        insert_at = 0
        for i, (iter_addr, _) in enumerate(self._bookmarks):
            if addr >= iter_addr:
                insert_at = i + 1
            else:
                break

        self.beginInsertRows(QModelIndex(), insert_at, 1)
        self._bookmarks.insert(insert_at, (addr, name))
        self.endInsertRows()

        self.save()

    def renameBookmark(self, row, new_name):
        addr, name = self._bookmarks[row]
        self._bookmarks[row] = (addr, new_name)
        self.dataChanged.emit(self.index(row, 0), self.index(row, 0))

        self.save()

    def removeBookmark(self, row):
        self.beginRemoveRows(QModelIndex(), row, 1)
        self._bookmarks = self._bookmarks[:row] + self._bookmarks[row + 1:]
        self.endRemoveRows()

        self.save()


class BookmarkList(QListView):
    def __init__(self, viewFrame):
        QListView.__init__(self)
        self._viewFrame = viewFrame
        self._binaryView = viewFrame.getView().getBinaryView()

        self.setViewMode(QListView.ListMode)
        self.setFlow(QListView.TopToBottom)
        self.setMovement(QListView.Static)
        self.setWordWrap(False)
        self.setSelectionMode(QListView.SingleSelection)

        self._model = BookmarkItemModel(self, self._binaryView)
        self.setModel(self._model)

        self._delegate = bnx.CrossReferenceItemDelegate()
        self.setItemDelegate(self._delegate.q._q_object)

        self.doubleClicked.connect(self.goToBookmark)

    def contextMenuEvent(self, event):
        menu = QMenu()
        menu.addAction("Add...", self.addBookmark)
        if self.currentIndex().isValid():
            menu.addAction("Rename...", self.renameBookmark)
            menu.addAction("Remove", self.removeBookmark)
        menu.exec_(event.globalPos())

    def goToBookmark(self, index):
        address, name = self._model._bookmarks[index.row()]
        self._binaryView.navigate(self._binaryView.view, address)

    def addBookmark(self):
        name = bn.get_text_line_input(
            "Create bookmark", "Enter bookmark name:"
        )
        if name:
            self._model.addBookmark(self._binaryView.file.offset, name)

    def renameBookmark(self):
        index = self.currentIndex()
        if index.isValid():
            new_name = bn.get_text_line_input(
                "Rename bookmark", "Enter new bookmark name:"
            )
            if new_name:
                self._model.renameBookmark(index.row(), new_name)

    def removeBookmark(self):
        index = self.currentIndex()
        if index.isValid():
            self._model.removeBookmark(index.row())


_bookmark_lists = []

def _tabInitCallback(viewFrame):
    bookmarkList = BookmarkList(viewFrame)
    tabWidget = viewFrame.getInfoPanel().getTabWidget()
    tabWidget.addTab(bookmarkList, "Bookmarks")
    _bookmark_lists.append(bookmarkList)

bnx.ViewFrame.addInitCallback(_tabInitCallback)
_on_reload.append(lambda: bnx.ViewFrame.removeInitCallback(_tabInitCallback))
