"""Virtualized, keyboard-operable card surfaces without visible scroll tracks."""
import math
import time
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QEvent, QObject
from PySide6.QtGui import (QPainter, QColor, QPen, QLinearGradient, QRadialGradient,
                          QPainterPath, QFont, QFontMetrics, QRegion, QImage, QTransform, QPixmap)
from PySide6.QtWidgets import QWidget, QToolTip
from . import physics
from .design import icon
from .motion import spring, enabled
from .physics import SNAPPY, GLIDE


def rubber(distance, extent):
    """iOS-style resistance: overscroll gets heavier the further it travels."""
    extent = max(1.0, extent)
    return (1-1/(distance*.55/extent+1))*extent


class RoundedClip(QObject):
    def __init__(self,widget):
        super().__init__(widget)
        self.widget=widget
        widget.installEventFilter(self)
        self.update_shape()

    def update_shape(self):
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.widget.rect()), 18, 18)
        self.widget.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def eventFilter(self,watched,event):
        if event.type() in (QEvent.Resize,QEvent.Show):
            self.update_shape()
        return False


def round_surface(widget):
    if not getattr(widget,'_rounded_clip',None):
        widget._rounded_clip=RoundedClip(widget)


class CardSurface(QWidget):
    selection_changed = Signal()
    activated = Signal(int)
    hovered = Signal(int)  # pointer arrived on a card (index); drives hover sound
    pressed = Signal(int)  # pointer pressed a card (index)

    def __init__(self, shelf=False, parent=None):
        super().__init__(parent)
        self.shelf = shelf
        self.entries = []
        self.offset = self.target = 0.0
        self.selected_index = self.hover_index = -1
        self.pointer = QPointF()
        self.hover = 0.0
        # Each card owns its hover and press springs, so leaving one card lets
        # it settle naturally while the next one lifts.
        self.hover_levels, self.press_levels = {}, {}
        self.tilt = (0.0, 0.0)
        self.press_index = -1
        self.drag_samples = []
        self.hit_boxes = []
        self.previews = {}
        self.artwork_pixmaps = {}
        self.drag_start = None
        self.dragged = False
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumHeight(160)
        self.setAccessibleName('Project card shelf' if shelf else 'Working file card gallery')
        self.setAccessibleDescription('Use arrows to browse, Enter to open. Scroll or drag to browse more cards.')

    def set_entries(self, entries):
        old = self.entries[self.selected_index].get('path') if 0 <= self.selected_index < len(self.entries) else None
        initial = not self.entries
        self.entries = entries
        # Only bounded thumbnails of existing preview files; no DCC launch or
        # full-size image cache is used to decorate a card.
        self.previews.clear()
        self.artwork_pixmaps.clear()
        self.selected_index = next((i for i,e in enumerate(entries) if e.get('path') == old), -1)
        self.target = min(self.target,self.limit())
        self.offset = min(self.offset,self.limit())
        if self.shelf and (initial or self.selected_index<0):
            self.offset = self.target = float(max(0,min(len(entries)-1,len(entries)//2)))
        self.hit_boxes.clear()
        self.update()

    def rowCount(self):
        return len(self.entries)

    def currentRow(self):
        return self.selected_index

    def columns(self):
        return max(1,min(4,(self.width()-24)//210))

    def limit(self):
        if self.shelf:
            return max(0,len(self.entries)-1)
        return max(0,math.ceil(len(self.entries)/self.columns())*226 + 24 - self.height())

    def advance(self,value):
        self.offset = float(value)
        if self.shelf and self.entries:
            index=max(0,min(len(self.entries)-1,int(self.offset+.5)))
            if self.selected_index!=index:
                self.selected_index=index
                self.setAccessibleName('Project: '+self.entries[index]['name'])
                self.selection_changed.emit()
        self.update()

    def scroll_to(self,value,velocity=None):
        # Retargeting keeps momentum: rapid wheel ticks merge into one glide.
        self.target = max(0,min(self.limit(),float(value)))
        spring(self,'scroll',self.target,self.advance,value=self.offset,velocity=velocity,
               feel=GLIDE,precision=.05 if self.shelf else .2)

    def scroll_speed(self):
        return physics.speed(self,'scroll')

    def hover_key(self,index):
        return self.entries[index].get('path',index) if 0<=index<len(self.entries) else None

    def hover_level(self,index):
        return self.hover_levels.get(self.hover_key(index),0.0)

    def press_level(self,index):
        return self.press_levels.get(self.hover_key(index),0.0)

    def set_hover_index(self,index):
        if index==self.hover_index:
            return
        for previous,target in ((self.hover_index,0.0),(index,1.0)):
            key=self.hover_key(previous)
            if key is None:
                continue
            def apply(value,key=key):
                self.hover_levels[key]=value
                self.update()
            spring(self,('hover',key),target,apply,value=self.hover_levels.get(key,0.0),
                   feel=SNAPPY if target else (.44,.92))
        self.hover_index=index
        self.hover=1.0 if index>=0 else 0.0
        if index<0:
            self.track_tilt(None)
        else:
            self.hovered.emit(index)

    def set_press_index(self,index):
        for previous,target in ((self.press_index,0.0),(index,1.0)):
            key=self.hover_key(previous)
            if key is None:
                continue
            def apply(value,key=key):
                self.press_levels[key]=value
                self.update()
            # Firm press, then a jelly release that briefly swells past rest.
            spring(self,('press',key),target,apply,value=self.press_levels.get(key,0.0),
                   feel=(.15,.9) if target else (.36,.42))
        self.press_index=index

    def track_tilt(self,point):
        rect=next((r for i,r in self.hit_boxes if i==self.hover_index),None) if point is not None else None
        if rect is None:
            target=(0.0,0.0)
        else:
            target=(max(-1.0,min(1.0,(point.x()-rect.center().x())/(rect.width()/2))),
                    max(-1.0,min(1.0,(point.y()-rect.center().y())/(rect.height()/2))))
        def apply(value):
            self.tilt=value
            self.update()
        spring(self,'tilt',target,apply,value=self.tilt,feel=(.3,.86))

    def selectRow(self,index):
        if not 0 <= index < len(self.entries):
            self.selected_index = -1
            self.selection_changed.emit()
            self.update()
            return
        self.selected_index = index
        if self.shelf:
            self.scroll_to(index)
        else:
            y = (index//self.columns())*226+12
            if index//self.columns()==math.ceil(len(self.entries)/self.columns())-1:
                self.scroll_to(self.limit())
            elif y < self.target:
                self.scroll_to(y-12)
            elif y+214 > self.target+self.height():
                self.scroll_to(y+226-self.height())
        entry = self.entries[index]
        self.setAccessibleName(('Project: ' if self.shelf else 'Working file: ')+entry['name'])
        self.selection_changed.emit()
        self.update()

    def keyPressEvent(self,event):
        index = self.selected_index if self.selected_index>=0 else max(0,min(len(self.entries)-1,round(self.offset))) if self.shelf else 0
        step = 1 if self.shelf else self.columns()
        moves = {Qt.Key_Left:-1,Qt.Key_Right:1,Qt.Key_Up:-step,Qt.Key_Down:step}
        if event.key() in moves:
            self.selectRow(max(0,min(len(self.entries)-1,index+moves[event.key()])))
        elif event.key() in (Qt.Key_Return,Qt.Key_Enter) and self.entries:
            self.activated.emit(index)
        elif event.key() == Qt.Key_Home:
            self.selectRow(0)
        elif event.key() == Qt.Key_End:
            self.selectRow(len(self.entries)-1)
        elif event.key() in (Qt.Key_PageDown,Qt.Key_PageUp):
            self.scroll_to(self.target+(1 if event.key()==Qt.Key_PageDown else -1)*(1 if self.shelf else self.height()*.8))
        else:
            super().keyPressEvent(event)

    def wheelEvent(self,event):
        delta = event.pixelDelta()
        if delta.isNull():
            amount = (event.angleDelta().y() or event.angleDelta().x())/120
            self.scroll_to(self.target-amount*(1 if self.shelf else 150))
        else:
            amount = delta.x() or delta.y()
            self.scroll_to(self.target-amount/(180 if self.shelf else 1))
        event.accept()

    def index_at(self,point):
        return next((i for i,rect in reversed(self.hit_boxes) if rect.contains(point)), -1)

    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton:
            self.setFocus()
            self.drag_start = event.position()
            self.drag_offset = self.offset
            self.dragged = False
            self.drag_samples = [(time.monotonic(),self.offset)]
            # Catch a gliding grid mid-flight, like a hand stopping a page.
            physics.cancel(self,'scroll')
            self.target = self.offset
            self.set_press_index(self.index_at(event.position()))
            if self.press_index>=0:
                self.pressed.emit(self.press_index)
            event.accept()

    def mouseMoveEvent(self,event):
        self.pointer = event.position()
        if self.drag_start is not None and event.buttons() & Qt.LeftButton:
            distance = event.position()-self.drag_start
            if distance.manhattanLength()>8 and not self.dragged:
                self.dragged = True
                self.set_press_index(-1)
            if self.dragged:
                displacement = distance.x()/220 if self.shelf else distance.y()
                raw = self.drag_offset-displacement
                if not self.shelf and raw<0:
                    raw = -rubber(-raw,self.height())
                elif not self.shelf and raw>self.limit():
                    raw = self.limit()+rubber(raw-self.limit(),self.height())
                elif self.shelf:
                    raw = max(0,min(self.limit(),raw))
                self.offset = self.target = raw
                self.drag_samples = (self.drag_samples+[(time.monotonic(),raw)])[-6:]
                self.update()
                return
        index = self.index_at(event.position())
        if index != self.hover_index:
            self.set_hover_index(index)
            self.setCursor(Qt.PointingHandCursor if index>=0 else Qt.ArrowCursor)
        if index>=0 and enabled(self):
            self.track_tilt(event.position())
        self.update()

    def end_drag(self):
        """Release a drag with its real velocity; overscroll springs back."""
        first,last = self.drag_samples[0],self.drag_samples[-1]
        span = last[0]-first[0]
        velocity = (last[1]-first[1])/span if span>.008 else 0.0
        if self.shelf:
            self.scroll_to(round(self.offset))
            return
        projected = self.offset+velocity*.3
        self.scroll_to(projected,velocity)

    def set_hover(self,value):
        self.hover = float(value)
        self.update()

    def leaveEvent(self,event):
        self.set_hover_index(-1)
        self.setCursor(Qt.ArrowCursor)
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self,event):
        if event.button()!=Qt.LeftButton or self.drag_start is None:
            return
        self.drag_start = None
        self.set_press_index(-1)
        if self.dragged:
            self.end_drag()
            return
        index = self.index_at(event.position())
        if index >= 0:
            centered = self.shelf and abs(self.offset-index)<.15
            self.selectRow(index)
            if centered:
                self.activated.emit(index)

    def mouseDoubleClickEvent(self,event):
        index = self.index_at(event.position())
        if index >= 0 and not self.shelf:
            self.selectRow(index)
            self.activated.emit(index)

    def event(self,event):
        if event.type()==QEvent.ToolTip:
            index = self.index_at(QPointF(event.pos()))
            if index >= 0:
                QToolTip.showText(event.globalPos(),self.entries[index].get('path',''),self)
                return True
        return super().event(event)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.offset = self.target = min(self.target,self.limit())

    def paintEvent(self,event):
        dpr = self.devicePixelRatioF()
        layer = QImage(max(1,int(self.width()*dpr)),max(1,int(self.height()*dpr)),QImage.Format_ARGB32_Premultiplied)
        layer.setDevicePixelRatio(dpr)
        layer.fill(Qt.transparent)
        p = QPainter(layer)
        p.setRenderHints(QPainter.Antialiasing|QPainter.SmoothPixmapTransform)
        boundary = QPainterPath()
        boundary.addRoundedRect(QRectF(self.rect()),22,22)
        p.setClipPath(boundary)
        self.hit_boxes = []
        if not self.entries:
            p.setPen(QColor('#e6d2f4'))
            p.drawText(QRectF(self.rect()).adjusted(30,20,-30,-20),Qt.AlignCenter|Qt.TextWordWrap,
                       'No matching projects. Check your search and storage roots.' if self.shelf else getattr(self,'empty_message','Choose a project above to discover its creative files.'))
        elif self.shelf:
            indices = [i for i in range(max(0,int(self.offset)-4),min(len(self.entries),int(self.offset)+5))]
            indices.sort(key=lambda i:-abs(i-self.offset))
            for i in indices:
                distance = i-self.offset
                scale = 1-.14*min(2,abs(distance))
                w,h = 260*scale, min(340,self.height()-64)*scale
                x = self.width()/2+distance*242-w/2
                y = (self.height()-h)/2+abs(distance)*5
                rect = QRectF(x,y,w,h)
                edge = min(1,max(0,min(rect.center().x(),self.width()-rect.center().x())/130))
                opacity = (1-.24*min(2,abs(distance)))*edge
                if opacity>0 and rect.intersects(QRectF(self.rect())):
                    self.draw_card(p,i,rect,opacity,distance)
                    self.hit_boxes.append((i,rect))
        else:
            cols = self.columns()
            w = (self.width()-24-(cols-1)*16)/cols
            start_row = max(0,int(self.offset)//226)
            end_row = min(math.ceil(len(self.entries)/cols),int((self.offset+self.height())//226)+2)
            for row in range(start_row,end_row):
                for col in range(cols):
                    i = row*cols+col
                    if i>=len(self.entries):
                        break
                    rect = QRectF(12+col*(w+16),12+row*226-self.offset,w,210)
                    # Cards dissolve at the viewport ends instead of striking
                    # a hard rectangular clipping line while scrolling.
                    opacity = min(1,max(0,min(rect.bottom(),self.height()-rect.top())/95))
                    self.draw_card(p,i,rect,opacity)
                    self.hit_boxes.append((i,rect))
        # The layer fades into the actual atmosphere behind it. An opaque
        # imitation of the background would leave visible rectangular seams.
        if self.entries:
            mask = QLinearGradient(0,0,self.width() if self.shelf else 0,0 if self.shelf else self.height())
            start_alpha = 0 if self.shelf or self.offset>1 else 255
            end_alpha = 0 if self.shelf or self.offset<self.limit()-1 else 255
            for stop,alpha in ((0,start_alpha),(.08,255),(.92,255),(1,end_alpha)):
                mask.setColorAt(stop,QColor(255,255,255,alpha))
            p.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            p.fillRect(self.rect(),mask)
        p.end()
        display = QPainter(self)
        display.drawImage(QPointF(0,0),layer)
        if not self.shelf and self.offset<self.limit()-1:
            display.setRenderHint(QPainter.Antialiasing)
            pill = QRectF(self.width()/2-85,self.height()-34,170,26)
            display.setPen(QPen(QColor(222,190,246,90),1))
            display.setBrush(QColor(43,23,74,230))
            display.drawRoundedRect(pill,13,13)
            display.setPen(QColor('#e8d7f8'))
            display.drawText(pill,Qt.AlignCenter,'Scroll to explore  ↓')

    def draw_card(self,p,index,rect,opacity,distance=0):
        entry = self.entries[index]
        hover = self.hover if index==self.hover_index and enabled(self) else 0
        p.save()
        p.setOpacity(opacity)
        lift = 7*hover
        # A contact shadow anchors the floating face, while its highlight
        # responds to the pointer. Artwork has its own generous safe bounds.
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(12,5,35,65))
        p.drawRoundedRect(rect.translated(0,6+lift),22,22)
        tones = {'Blender':('#715025','#33215b'),'Photoshop':('#244f98','#28205b'),
                 'Illustrator':('#89562b','#39214f'),'After Effects':('#6048b2','#291c59'),
                 'Fusion':('#814552','#352254')}
        a,b = tones.get(entry.get('application'),('#68439e','#34235f'))
        gradient = QLinearGradient(rect.topLeft(),rect.bottomRight())
        gradient.setColorAt(0,QColor(a));gradient.setColorAt(1,QColor(b))
        p.setBrush(gradient)
        p.setPen(QPen(QColor('#e7b4ff') if index==self.selected_index else QColor(216,182,241,int(75+80*hover)),2 if index==self.selected_index else 1))
        p.drawRoundedRect(rect,22,22)
        shape=QPainterPath();shape.addRoundedRect(rect,22,22);p.setClipPath(shape,Qt.IntersectClip)
        light=QRadialGradient(rect.right()-20+hover*10,rect.top()+30,rect.width()*.9)
        light.setColorAt(0,QColor(194,154,247,int(70+30*hover)));light.setColorAt(1,QColor(194,154,247,0))
        p.fillPath(shape,light)
        preview_path = entry.get('preview')
        if preview_path:
            if preview_path not in self.previews:
                from PySide6.QtGui import QImageReader
                reader = QImageReader(preview_path)
                reader.setAutoTransform(True)
                size=reader.size()
                if size.isValid():
                    reader.setScaledSize(size.scaled(420,230,Qt.KeepAspectRatio))
                self.previews[preview_path] = QPixmap.fromImage(reader.read()) if size.isValid() else QPixmap()
                if len(self.previews)>64:
                    self.previews.pop(next(iter(self.previews)))
            pixmap = self.previews.get(preview_path)
            if pixmap and not pixmap.isNull():
                preview_rect=QRectF(rect.left()+14,rect.top()+34,rect.width()-28,rect.height()*.35)
                preview_clip=QPainterPath();preview_clip.addRoundedRect(preview_rect,12,12)
                p.save();p.setClipPath(preview_clip,Qt.IntersectClip)
                p.setOpacity(opacity*.55)
                source=QRectF(pixmap.rect())
                ratio=preview_rect.width()/preview_rect.height()
                if source.width()/source.height()>ratio:
                    width=source.height()*ratio;source.setLeft((source.width()-width)/2);source.setWidth(width)
                else:
                    height=source.width()/ratio;source.setTop((source.height()-height)/2);source.setHeight(height)
                p.drawPixmap(preview_rect,pixmap,source);p.restore()
        art_size = min(getattr(self,'art_size',140 if self.shelf else 78),rect.height()*.48)
        p.save()
        p.translate(rect.right()-art_size*.65-18,rect.top()+art_size*.6+10)
        p.rotate(-distance*7-8*hover)
        p.scale(1+.08*hover,1+.08*hover)
        if entry.get('artwork'):
            path=entry['artwork']
            if path not in self.artwork_pixmaps:
                from PySide6.QtGui import QImageReader
                reader=QImageReader(path)
                size=reader.size()
                if size.isValid():reader.setScaledSize(size.scaled(320,320,Qt.KeepAspectRatio))
                self.artwork_pixmaps[path]=QPixmap.fromImage(reader.read())
                if len(self.artwork_pixmaps)>64:self.artwork_pixmaps.pop(next(iter(self.artwork_pixmaps)))
            artwork=self.artwork_pixmaps[path]
        else:
            artwork=icon(entry.get('application','Projects'),256).pixmap(256,256)
        if artwork.isNull():
            artwork=icon('Projects',256).pixmap(256,256)
        p.drawPixmap(QRectF(-art_size/2,-art_size/2,art_size,art_size),artwork,QRectF(artwork.rect()))
        p.restore()
        font=QFont(self.font());font.setPixelSize(10);font.setBold(True);p.setFont(font)
        p.setPen(QColor('#decaf1'))
        p.drawText(rect.adjusted(18,18,-18,-18),Qt.AlignTop|Qt.AlignLeft,entry.get('application','PROJECT'))
        font.setPixelSize(15);font.setBold(True);p.setFont(font)
        metrics=QFontMetrics(font)
        raw=entry['name'];width=int(rect.width()-36)
        count=len(raw)
        while count>0 and metrics.horizontalAdvance(raw[:count])>width:
            count-=1
        if count<len(raw):
            space=raw.rfind(' ',0,count)
            if space>count*.5:
                count=space
            elif raw.rfind('_',0,count)>count*.45:
                count=raw.rfind('_',0,count)+1
            name=raw[:count].rstrip()+'\n'+metrics.elidedText(raw[count:].lstrip(),Qt.ElideMiddle,width)
        else:
            name=raw
        p.setPen(QColor('#fffaff'))
        p.drawText(QRectF(rect.left()+18,rect.top()+rect.height()*.50,rect.width()-36,48),Qt.AlignLeft|Qt.AlignTop,name)
        font.setPixelSize(11);font.setBold(False);p.setFont(font);p.setPen(QColor('#e2cfee'))
        p.drawText(rect.adjusted(18,rect.height()*.72,-18,-16),Qt.AlignTop|Qt.AlignLeft,
                   entry.get('subtitle','Explore project  →'))
        if self.hasFocus() and index==self.selected_index:
            p.setPen(QPen(QColor('#fffaff'),1,Qt.DotLine));p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(rect.adjusted(4,4,-4,-4),18,18)
        p.restore()
