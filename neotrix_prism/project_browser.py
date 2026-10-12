"""Uniform cards, asynchronous project artwork and native-resolution file rows."""
import hashlib
import math
import time
import os
import tempfile
from pathlib import Path
from PySide6.QtCore import Qt, QObject, Signal, QRunnable, QThreadPool, QRectF, QSize, QItemSelectionModel
from PySide6.QtGui import QPainter, QColor, QPen, QImageReader, QPixmap, QFontMetrics, QIcon
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QStyledItemDelegate, QAbstractItemView, QStyle
from .cards import CardSurface
from .design import icon
from .storage import user_dir

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ICON = Path(r'N:\Projects\Template\COMMERCIAL_ADS_TEMPLATE_V3\_TOOLS\icon')


def read_icon(project, cache):
    """Only called in a worker. Corrupt or absent candidates continue to fallback."""
    if cache.exists() and not Path(project).is_dir():
        return str(cache)
    for directory in (Path(project)/'_TOOLS/icon', TEMPLATE_ICON):
        for name in ('project.png', 'project.svg', 'project.webp'):
            reader = QImageReader(str(directory/name))
            reader.setAutoTransform(True)
            size = reader.size()
            if size.isValid():
                reader.setScaledSize(size.scaled(512,512,Qt.KeepAspectRatio))
                image = reader.read()
                if not image.isNull():
                    cache.parent.mkdir(parents=True, exist_ok=True)
                    fd, filename = tempfile.mkstemp(prefix='icon-',suffix='.tmp',dir=cache.parent)
                    os.close(fd)
                    temporary=Path(filename)
                    try:
                        if image.save(str(temporary), 'PNG'):
                            temporary.replace(cache)
                            return str(cache)
                    finally:
                        temporary.unlink(missing_ok=True)
    return str(cache) if cache.exists() else str(ROOT/'assets/project-placeholder.png')


class ArtworkTask(QRunnable):
    def __init__(self, service, project, cache):
        super().__init__()
        self.service, self.project, self.cache = service, project, cache

    def run(self):
        try:
            path = read_icon(self.project, self.cache)
        except OSError:
            path = str(self.cache) if self.cache.exists() else str(ROOT/'assets/project-placeholder.png')
        try:
            self.service.ready.emit(self.project, path)
        except RuntimeError:
            pass  # The window may have closed while network artwork was loading.


class ProjectArtwork(QObject):
    ready = Signal(str,str)
    changed = Signal(str)

    def __init__(self, parent):
        super().__init__(parent)
        self.pool = QThreadPool.globalInstance()
        self.pending = set()
        self.loaded_projects = set()
        self.paths = {}
        self.ready.connect(self.loaded)

    def cache_path(self, project):
        return user_dir()/'project-icons'/(hashlib.sha256(project.encode()).hexdigest()+'.png')

    def request(self, project, refresh=False):
        cache = self.cache_path(project)
        if project not in self.paths:
            self.paths[project] = str(cache) if cache.exists() else str(ROOT/'assets/project-placeholder.png')
        if (refresh or project not in self.loaded_projects) and project not in self.pending:
            self.pending.add(project)
            self.pool.start(ArtworkTask(self, project, cache))
        return self.paths[project]

    def loaded(self, project, path):
        # Keep a loaded marker so search changes don't restart network reads.
        self.paths[project] = path
        self.pending.discard(project)
        self.loaded_projects.add(project)
        self.changed.emit(project)


class GridCards(CardSurface):
    def __init__(self, parent=None):
        super().__init__(False,parent)
        self.card_height = 246
        self.art_size = 96
        self.setAccessibleName('Project cards')

    def columns(self):
        return max(1,min(4,int((self.width()-48+20)//240)))

    def limit(self):
        return max(0,math.ceil(len(self.entries)/self.columns())*(self.card_height+20)+28-self.height())

    def selectRow(self,index):
        self.selected_index = index if 0<=index<len(self.entries) else -1
        if self.selected_index>=0:
            y = 24+(index//self.columns())*(self.card_height+20)
            if y<self.target+24:
                self.scroll_to(y-24)
            elif y+self.card_height>self.target+self.height()-24:
                self.scroll_to(y+self.card_height-self.height()+24)
        self.selection_changed.emit();self.update()

    def paintEvent(self,event):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing|QPainter.TextAntialiasing|QPainter.SmoothPixmapTransform)
        self.hit_boxes=[]
        if not self.entries:
            p.setPen(QColor('#e6d2f4'))
            p.drawText(self.rect(),Qt.AlignCenter|Qt.TextWordWrap,getattr(self,'empty_message','No matching projects. Check your search and storage roots.'))
            return
        cols = self.columns()
        width = (self.width()-48-(cols-1)*20)/cols
        first = max(0,int(self.offset)//(self.card_height+20))
        last = min(math.ceil(len(self.entries)/cols),int((self.offset+self.height())//(self.card_height+20))+1)
        for row in range(first,last):
            for col in range(cols):
                i=row*cols+col
                if i>=len(self.entries):break
                rect=QRectF(24+col*(width+20),24+row*(self.card_height+20)-self.offset,width,self.card_height)
                self.draw_card(p,i,rect,1)
                self.hit_boxes.append((i,rect))

    def mouseReleaseEvent(self,event):
        if event.button()!=Qt.LeftButton or self.drag_start is None:return
        self.drag_start=None
        if self.dragged:return
        index=self.index_at(event.position())
        if index>=0:
            self.selectRow(index);self.activated.emit(index)

    def mouseDoubleClickEvent(self,event):
        event.accept()  # A single click opens a project or choice card.


class FileDelegate(QStyledItemDelegate):
    def sizeHint(self,option,index):
        return QSize(240,82)

    def paint(self,p,option,index):
        file=index.data(Qt.UserRole)
        if not file:return
        p.save();p.setRenderHints(QPainter.Antialiasing|QPainter.TextAntialiasing)
        rect=QRectF(option.rect).adjusted(4,4,-4,-4)
        selected=bool(option.state & QStyle.State_Selected)
        hovered=bool(option.state & QStyle.State_MouseOver)
        p.setBrush(QColor('#65408c' if selected else '#503271' if hovered else '#392558'))
        p.setPen(QPen(QColor('#d4a9ef' if selected else '#795997'),1))
        p.drawRoundedRect(rect,15,15)
        art=icon(file['application'],56).pixmap(56,56)
        p.drawPixmap(QRectF(rect.left()+12,rect.top()+10,52,52),art,QRectF(art.rect()))
        text=rect.adjusted(78,12,-16,-10)
        font=option.font;font.setPixelSize(14);font.setBold(True);p.setFont(font)
        p.setPen(QColor('#fffaff'))
        p.drawText(text,Qt.AlignTop,QFontMetrics(font).elidedText(file['name'],Qt.ElideMiddle,int(text.width())))
        font.setPixelSize(11);font.setBold(False);p.setFont(font);p.setPen(QColor('#ddc9ee'))
        subtitle=f"{file['application']}  ·  {file['shot']}  ·  {file['version']}  ·  "+time.strftime('%d %b %Y',time.localtime(file['modified']))
        p.drawText(text.adjusted(0,28,0,0),Qt.AlignTop,QFontMetrics(font).elidedText(subtitle,Qt.ElideRight,int(text.width())))
        if option.state & QStyle.State_HasFocus:
            p.setBrush(Qt.NoBrush);p.setPen(QPen(QColor('#fffaff'),1,Qt.DotLine));p.drawRoundedRect(rect.adjusted(3,3,-3,-3),12,12)
        p.restore()


class FileList(QListWidget):
    selection_changed=Signal()
    activated=Signal(int)

    def __init__(self):
        super().__init__()
        self.setItemDelegate(FileDelegate(self))
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setMouseTracking(True)
        self.setStyleSheet('QListWidget { background: transparent; border: none; }')
        self.itemSelectionChanged.connect(self.selection_changed)
        self.itemDoubleClicked.connect(lambda item:self.activated.emit(self.row(item)))
        self.empty_message='No matching files.'

    def set_entries(self,entries):
        selected={item.data(Qt.UserRole)['path'] for item in self.selectedItems()}
        self.blockSignals(True);self.clear()
        for file in entries:
            item=QListWidgetItem();item.setData(Qt.UserRole,file);item.setToolTip(file['path']);self.addItem(item)
            if file['path'] in selected:
                self.setCurrentItem(item,QItemSelectionModel.Select);item.setSelected(True)
        self.blockSignals(False);self.selection_changed.emit();self.viewport().update()

    def rowCount(self):return self.count()
    def selectRow(self,index):
        self.setCurrentRow(index);self.scrollToItem(self.item(index)) if self.item(index) else None
    def selected_files(self):return [item.data(Qt.UserRole) for item in self.selectedItems()]
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key_Return,Qt.Key_Enter) and self.currentRow()>=0:
            self.activated.emit(self.currentRow());event.accept()
        else:super().keyPressEvent(event)
    def paintEvent(self,event):
        super().paintEvent(event)
        if not self.count():
            p=QPainter(self.viewport());p.setPen(QColor('#ddc9ee'))
            p.drawText(self.viewport().rect().adjusted(20,20,-20,-20),Qt.AlignCenter|Qt.TextWordWrap,self.empty_message)
