"""Uniform cards, asynchronous project artwork and native-resolution file rows."""
import hashlib
import math
import time
import os
import re
import tempfile
from pathlib import Path
from PySide6.QtCore import Qt, QObject, Signal, QRunnable, QThreadPool, QRectF, QSize, QItemSelectionModel, QPoint, QPointF, QLineF, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QImageReader, QPixmap, QFontMetrics, QIcon, QLinearGradient, QRadialGradient, QPainterPath, QFont, QCursor
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QStyledItemDelegate, QAbstractItemView, QStyle
from . import art3d, physics
from .ambient import ambient_time
from .cards import CardSurface, rubber
from .design import icon
from .motion import clock, enabled, refresh_motion, snap, snapshot, spring
from .physics import GLIDE, POP, SNAPPY
from .storage import user_dir

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ICON = Path(r'N:\Projects\Template\COMMERCIAL_ADS_TEMPLATE_V3\_TOOLS\icon')
LEGACY_ICON = 'e163fb890ed4d6afa4e593b85ef5a4569916259c05e7654ba8b1570010fc4448'
PROJECT_ART = ROOT/'assets/project-art'
# Whole words in a project's folder name choose its artwork, in priority order.
THEMES = (('title', ('title', 'titles', 'typography', 'type', 'lettering', 'font')),
          ('film', ('film', 'films', 'movie', 'cinema', 'feature', 'short')),
          ('series', ('series', 'episode', 'episodes', 'show', 'tv', 'season')),
          ('brand', ('brand', 'branding', 'identity', 'logo')),
          ('character', ('character', 'characters', 'creature', 'mascot', 'avatar')),
          ('motion', ('motion', 'animation', 'animated', 'anim', 'mograph')),
          ('product', ('product', 'products', 'packshot', 'packaging', 'retail', 'commerce')),
          ('music', ('music', 'audio', 'sound', 'song', 'podcast', 'album')),
          ('photo', ('photo', 'photography', 'shoot', 'still', 'stills', 'camera')),
          ('design', ('design', 'graphic', 'graphics', 'illustration', 'art', 'visual')),
          ('rocket', ('launch', 'startup', 'campaign')),
          ('idea', ('idea', 'ideas', 'concept', 'pitch', 'research')))
GENERIC_ART = ('rocket', 'idea', 'planet', 'compass', 'plane')


def themed_artwork(project):
    """Artwork chosen from the project's name; unmatched names get a stable pick."""
    name = Path(project).name
    words = re.findall(r'[a-z0-9]+', name.lower())
    for theme, keys in THEMES:
        candidate = PROJECT_ART/(theme+'.png')
        if any(word in keys for word in words) and candidate.is_file():
            return str(candidate)
    digest = int(hashlib.sha256(name.encode()).hexdigest(), 16)
    for step in range(len(GENERIC_ART)):
        candidate = PROJECT_ART/(GENERIC_ART[(digest+step) % len(GENERIC_ART)]+'.png')
        if candidate.is_file():
            return str(candidate)
    return str(ROOT/'assets/project-placeholder.png')


def custom_icon(candidate):
    """True only for artwork made for this project, not the template's copy."""
    size = candidate.stat().st_size
    if size == 19656 and hashlib.sha256(candidate.read_bytes()).hexdigest() == LEGACY_ICON:
        return False
    template = TEMPLATE_ICON/candidate.name
    try:
        if template.is_file() and template.stat().st_size == size and template.read_bytes() == candidate.read_bytes():
            return False
    except OSError:
        pass
    return True


def read_icon(project, cache):
    """Only called in a worker. Corrupt or absent candidates continue to fallback."""
    if cache.exists() and not Path(project).is_dir():
        return str(cache)
    for directory in (Path(project)/'_TOOLS/icon',):
        for name in ('project.png', 'project.svg', 'project.webp'):
            candidate=directory/name
            if not candidate.is_file() or not custom_icon(candidate):
                continue
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
    cache.unlink(missing_ok=True)
    return themed_artwork(project)


class ArtworkTask(QRunnable):
    def __init__(self, service, project, cache):
        super().__init__()
        self.service, self.project, self.cache = service, project, cache

    def run(self):
        try:
            path = read_icon(self.project, self.cache)
        except OSError:
            path = str(self.cache) if self.cache.exists() else themed_artwork(self.project)
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
        return user_dir()/'project-icons-v3'/(hashlib.sha256(project.encode()).hexdigest()+'.png')

    def request(self, project, refresh=False):
        cache = self.cache_path(project)
        if project not in self.paths:
            self.paths[project] = str(cache) if cache.exists() else themed_artwork(project)
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
    """Bento grid of artwork cards.

    A hovered card widens while its row-mates yield, lifts, glows in its own
    hue and turns its artwork in perspective toward the pointer. At rest the
    artwork floats, card colours drift and a slow colour wave crosses the grid.
    Card colours come from each card's artwork. Labels stay native-size and
    pixel-aligned throughout; only shapes, light and artwork change size.
    """
    GROW = .34
    context_requested = Signal(int, QPoint)

    def __init__(self, parent=None):
        super().__init__(False,parent)
        self.base_height = 264
        self.fit_rows = False
        self.art_size = 196
        self.appearance = 1.0
        self.entrance_elapsed = -1.0
        self.entrance_delay = 0
        self.entrance_only = None
        self.flip = {}
        self.palettes = {}
        self.faces = {}
        self.empty_art = None
        self.refresh_elapsed = -1.0
        self.refresh_lags = {}
        self.setAccessibleName('Project cards')

    @property
    def card_height(self):
        """Row height. A fitted grid (stage choices) shrinks its rows, down to a
        floor, so every choice is visible without scrolling."""
        if not self.fit_rows or not self.entries:
            return self.base_height
        rows=max(row for row,col,span in self.layout_slots())+1
        return max(188.0,min(float(self.base_height),(self.height()-52-(rows-1)*20)/rows))

    @card_height.setter
    def card_height(self,value):
        self.base_height=value

    def unit(self):
        cols=self.columns()
        return (self.width()-48-(cols-1)*20)/cols

    def card_rect(self,row,col,span):
        """Resting geometry of a slot."""
        unit,dpr=self.unit(),self.devicePixelRatioF()
        y=24+row*(self.card_height+20)-self.offset
        return QRectF(snap(24+col*(unit+20),dpr),snap(y,dpr),span*unit+(span-1)*20,self.card_height)

    def card_rects(self):
        """Live geometry: a hovered card widens and its row-mates yield, so the
        row always fills the same width with the same gutters."""
        unit,dpr=self.unit(),self.devicePixelRatioF()
        rows={}
        for i,(row,col,span) in enumerate(self.layout_slots()):
            rows.setdefault(row,[]).append((col,span,i))
        grow=self.GROW if enabled(self) else 0.0
        rects={}
        for row,items in rows.items():
            items.sort()
            y=snap(24+row*(self.card_height+20)-self.offset,dpr)
            rest=[span*unit+(span-1)*20 for col,span,i in items]
            weights=[w*(1+(grow if len(items)>1 else 0)*max(0.0,self.hover_level(i))) for w,(col,span,i) in zip(rest,items)]
            free,total=sum(rest),sum(weights)
            x=24+items[0][0]*(unit+20)
            for (col,span,i),weight in zip(items,weights):
                width=free*weight/total
                rects[i]=QRectF(snap(x,dpr),y,width,self.card_height)
                x+=width+20
        return rects

    RIPPLE_PUSH = 22.0   # px a card travels away from the orb at the ripple's peak
    RIPPLE_LIFT = 8.0    # px it rises as it is pushed
    RIPPLE_SWELL = .055  # shape growth at the peak (labels only translate)
    RIPPLE_STRETCH = .07  # shape stretch along the push at full speed

    def refresh_wave(self, delay=0, origin=None, speed=1650.0):
        """Ride the refresh wave: as the front reaches each card, the card is
        pushed away from the orb, lifts and catches a sheen of light, then its
        artwork jumps off it; with no origin the cards ripple in order."""
        self.refresh_origin=QPointF(origin) if origin is not None else None
        self.refresh_speed=speed
        lags={}
        rects=self.card_rects()
        for n,i in enumerate(sorted(rects)):
            rect=rects[i]
            if rect.bottom()<0 or rect.top()>self.height():
                continue
            reach=QLineF(QPointF(origin),rect.center()).length()/speed*1000 if origin is not None else min(n*65,650)
            lags[self.entries[i].get('path')]=delay+reach
        self.refresh_lags=lags
        self.refresh_span=(min(lags.values(),default=0),max(lags.values(),default=0))
        def step(value):
            self.refresh_elapsed = float(value)
            self.update()
        clock(self,'_refresh_cards',max(physics.BOUNCE_MS,physics.RIPPLE_MS)+max(lags.values(),default=0),step,self.reset_wave)

    def ripple_level(self,index):
        """How lifted a card is by the refresh ripple right now (for paint order)."""
        lag=self.refresh_lags.get(self.entries[index].get('path')) if 0<=index<len(self.entries) else None
        if lag is None or self.refresh_elapsed<0 or not enabled(self):
            return 0.0
        return max(0.0,physics.ripple(self.refresh_elapsed-lag)[0])

    def ripple_for(self,rect,lag):
        """(offset, lift 0..1, sheen, stretch) for a card the refresh wave is crossing.

        The push points away from the orb and weakens with distance; the card
        stretches along its travel while it moves fast. Cards near the widget's
        edge travel less along that axis, so nothing is ever cropped. The sheen
        is (direction, band position 0..1 from the near edge, strength) while
        the front is inside the card, else None."""
        if lag is None or self.refresh_elapsed<0:
            return QPointF(),0.0,None,(1.0,1.0)
        local=self.refresh_elapsed-lag
        amount,speed=physics.ripple(local)
        origin=getattr(self,'refresh_origin',None)
        if origin is None:
            direction=QPointF(0.0,-1.0)
        else:
            delta=rect.center()-origin
            length=math.hypot(delta.x(),delta.y()) or 1.0
            direction=QPointF(delta.x()/length,delta.y()/length)
        first,last=getattr(self,'refresh_span',(lag,lag))
        strength=1-.3*((lag-first)/(last-first) if last>first else 0.0)
        lift=max(0.0,amount)*strength
        # Outward peak of the push, then how much of it fits before the edge.
        px,py=self.RIPPLE_PUSH*direction.x()*strength,self.RIPPLE_PUSH*direction.y()*strength
        rise=self.RIPPLE_LIFT*strength
        peak_x,peak_y=px,py-rise
        grow_x,grow_y=rect.width()*self.RIPPLE_SWELL/2+2,rect.height()*self.RIPPLE_SWELL/2+2
        def fit(peak,low,high,low_visible,high_visible):
            if peak<-.5 and low_visible:
                return min(1.0,max(0.0,low)/-peak)
            if peak>.5 and high_visible:
                return min(1.0,max(0.0,high)/peak)
            return 1.0
        kx=fit(peak_x,rect.left()-grow_x-3,self.width()-3-rect.right()-grow_x,rect.left()>=0,rect.right()<=self.width())
        ky=fit(peak_y,rect.top()-grow_y-3,self.height()-3-rect.bottom()-grow_y,rect.top()>=0,rect.bottom()<=self.height())
        offset=QPointF(px*amount*kx,(py*amount-rise*max(0.0,amount))*ky)
        fast=min(1.0,abs(speed)/physics.RIPPLE_SPEED)*self.RIPPLE_STRETCH*strength
        stretch=(1+fast*abs(direction.x())-.5*fast*abs(direction.y()),1+fast*abs(direction.y())-.5*fast*abs(direction.x()))
        # The front (refresh_speed px/s) crosses the card: a band of light rides with it.
        extent=abs(direction.x())*rect.width()/2+abs(direction.y())*rect.height()/2
        crossing=max(1.0,2*extent/getattr(self,'refresh_speed',1650.0)*1000)
        position=(local+crossing/2)/crossing
        sheen=(direction,position,strength) if -.35<position<1.35 else None
        return offset,lift,sheen,stretch

    def reset_wave(self):
        if getattr(self, '_refresh_cards', None):self._refresh_cards.stop()
        self.refresh_elapsed = -1.0
        self.refresh_lags.clear()
        self.update()

    def set_entries(self,entries):
        before={}
        for i,rect in self.card_rects().items():
            path=self.entries[i].get('path')
            dx,dy,dw=self.flip.get(path,(0.0,0.0,0.0))
            before[path]=QRectF(rect.x()+dx,rect.y()+dy,rect.width()+dw,rect.height())
        changed=[e.get('path') for e in entries]!=[e.get('path') for e in self.entries]
        super().set_entries(entries)
        self.palettes.clear()
        self.faces.clear()
        if not changed:
            return
        survivors=set(before)&{e.get('path') for e in entries}
        if not survivors or not enabled(self) or not self.isVisible():
            self.play_entrance()
            return
        # FLIP reflow: cards that stay glide from their old slot (and width) to
        # the new one; only newcomers play the entrance.
        for i,new in self.card_rects().items():
            path=self.entries[i].get('path')
            if path not in survivors:
                continue
            old=before[path]
            delta=(old.x()-new.x(),old.y()-new.y(),old.width()-new.width())
            if max(abs(v) for v in delta)<.5:
                physics.cancel(self,('flip',path))
                self.flip.pop(path,None)
                continue
            def apply(value,path=path):
                self.flip[path]=value
                self.update()
            spring(self,('flip',path),(0.0,0.0,0.0),apply,value=delta,feel=(.5,.82),precision=.2)
        self.play_entrance(only={e.get('path') for e in entries}-survivors)

    def play_entrance(self, delay=0, only=None):
        """Cards rise and swell in a diagonal wave; within each card the artwork
        spins in from edge-on and the title settles a beat later."""
        self.entrance_only=only
        if not enabled(self) or not self.entries or only==set():
            self.entrance_elapsed=-1.0
            self.update()
            return
        self.entrance_delay=delay
        self.entrance_elapsed=0.0
        def step(value):
            self.entrance_elapsed=float(value)
            self.update()
        def finished():
            self.entrance_elapsed=-1.0
            self.update()
        clock(self,'_entrance',delay+600+physics.settle_time(*POP)+160,step,finished)

    def entrance(self,row,col,path=None):
        """(rise, opacity, artwork, title, title opacity) for one card, 1 at rest."""
        if self.entrance_elapsed<0 or (self.entrance_only is not None and path not in self.entrance_only):
            return 1.0,1.0,1.0,1.0,1.0
        first_row=int(self.offset//(self.card_height+20))
        local=self.entrance_elapsed-self.entrance_delay-min(600,max(0,row-first_row)*95+col*65)
        return (physics.progress(local,.52,.72),max(0.0,min(1.0,local/170)),
                physics.progress(local-60,.62,.5),physics.progress(local-140,.44,.9),
                max(0.0,min(1.0,(local-140)/170)))

    def palette_for(self,index):
        """Card colours derived from the card's own artwork; repeated artwork
        steps around the colour wheel so neighbours never look identical."""
        artwork=self.artwork_for(index)
        source=self.entries[index].get('artwork') or self.entries[index].get('application','')
        twin=sum(1 for e in self.entries[:index] if (e.get('artwork') or e.get('application',''))==source)
        key=(artwork.cacheKey(),twin)
        if key not in self.palettes:
            self.palettes[key]=art3d.card_palette(artwork,twin*.09)
        return self.palettes[key]

    def artwork_for(self,index):
        entry=self.entries[index]
        path=entry.get('artwork')
        if path:
            if path not in self.artwork_pixmaps:
                reader=QImageReader(path);size=reader.size()
                if size.isValid():reader.setScaledSize(size.scaled(640,640,Qt.KeepAspectRatio))
                self.artwork_pixmaps[path]=QPixmap.fromImage(reader.read())
                if len(self.artwork_pixmaps)>64:self.artwork_pixmaps.pop(next(iter(self.artwork_pixmaps)))
            artwork=self.artwork_pixmaps[path]
        else:artwork=icon('Versions' if entry.get('application')=='VERSION' else 'Default',384).pixmap(384,384)
        if artwork.isNull():artwork=icon('Default',384).pixmap(384,384)
        return artwork

    def zoom_source(self,index):
        """Where a card and its artwork sit now, for the shared-element zoom."""
        rect=next((r for i,r in self.hit_boxes if i==index),None)
        if rect is None:
            return None
        size=min(self.art_size,rect.width()-54,rect.height()-92)
        return {'rect':QRectF(rect),'art':QRectF(rect.center().x()-size/2,rect.top()+24,size,size),
                'colors':self.palette_for(index),
                'pixmap':self.artwork_for(index),'title':self.entries[index]['name']}

    def columns(self):
        return max(1,min(4,int((self.width()-48+20)//280)))

    def limit(self):
        slots=self.layout_slots()
        rows=max((row+1 for row,col,span in slots),default=0)
        return max(0,rows*(self.card_height+20)+28-self.height())

    def layout_slots(self):
        cols=self.columns()
        if getattr(self,'equal_pair',False) and len(self.entries)==2 and cols>=2:
            return [(0,0,cols/2),(0,cols/2,cols/2)]
        if cols<4:return [(i//cols,i%cols,1) for i in range(len(self.entries))]
        pattern=[(0,0,1),(0,1,2),(0,3,1),(1,0,2),(1,2,1),(1,3,1)]
        return [(pattern[i%6][0]+2*(i//6),pattern[i%6][1],pattern[i%6][2]) for i in range(len(self.entries))]

    def selectRow(self,index):
        self.selected_index = index if 0<=index<len(self.entries) else -1
        if self.selected_index>=0:
            y = 24+self.layout_slots()[index][0]*(self.card_height+20)
            if y<self.target+24:
                self.scroll_to(y-24)
            elif y+self.card_height>self.target+self.height()-24:
                self.scroll_to(y+self.card_height-self.height()+24)
        self.selection_changed.emit();self.update()
        if self.selected_index>=0:self.setAccessibleName(self.entries[self.selected_index]['name'])

    def paint_empty(self,p):
        t=ambient_time(self) if enabled(self) else 0.0
        message=getattr(self,'empty_message','No matching projects. Check your search and storage roots.')
        box=QRectF(self.rect()).adjusted(40,0,-40,0)
        if self.empty_art is not None and message:
            size=min(150.0,self.height()*.36)
            centre=QPointF(self.width()/2,self.height()/2-size*.45)
            art3d.paint(p,self.empty_art,centre,size,yaw=10*math.sin(t*.5),pitch=5*math.sin(t*.4),
                        roll=2*math.sin(t*.3),lift=size*.04*math.sin(t*.8),shadow=1.0,opacity=.92)
            box=QRectF(40,centre.y()+size*.62,self.width()-80,80)
        font=QFont(self.font());font.setPixelSize(15);p.setFont(font)
        p.setPen(QColor(236,230,246,215))
        p.drawText(box,Qt.AlignHCenter|(Qt.AlignTop if self.empty_art is not None else Qt.AlignVCenter)|Qt.TextWordWrap,message)

    def paintEvent(self,event):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing|QPainter.TextAntialiasing|QPainter.SmoothPixmapTransform)
        self.hit_boxes=[]
        if not self.entries:
            self.paint_empty(p)
            return
        t=ambient_time(self) if enabled(self) else 0.0
        slots=self.layout_slots()
        rects=self.card_rects()
        # The most lifted card paints last so its artwork can rise over the gutter.
        for i in sorted(rects,key=lambda i:(max(self.hover_level(i),self.ripple_level(i)),i)):
            rect=rects[i]
            row,col,span=slots[i]
            path=self.entries[i].get('path')
            dx,dy,dw=self.flip.get(path,(0.0,0.0,0.0))
            shown=QRectF(rect.x()+dx,rect.y()+dy,rect.width()+dw,rect.height())
            if shown.bottom()<-40 or shown.top()>self.height()+40:continue
            self.draw_card(p,i,shown,1.0,entrance=self.entrance(row,col,path),t=t)
            self.hit_boxes.append((i,rect))
        self.fade_edges(p)

    def fade_edges(self,p):
        """Cards dissolve into the living backdrop at the scroll edges."""
        surface=getattr(self.window(),'surface',None)
        if surface is None or getattr(surface,'frame',None) is None:
            return
        dpr=self.devicePixelRatioF()
        for at_top,active in ((True,self.offset>1),(False,self.offset<self.limit()-1)):
            if not active:
                continue
            height=46 if at_top else 64
            rect=QRectF(0,0 if at_top else self.height()-height,self.width(),height)
            # Rebuilt only when the backdrop or the widget changes, not per frame.
            state=(surface.frame_key,self.width(),self.height(),dpr,self.mapTo(surface,QPoint(0,0)).toTuple())
            cached=self.faces.get(('fade',at_top))
            if cached is not None and cached[0]==state:
                p.drawPixmap(rect.topLeft(),cached[1])
                continue
            strip=QPixmap(max(1,round(rect.width()*dpr)),max(1,round(height*dpr)))
            strip.setDevicePixelRatio(dpr)
            strip.fill(Qt.transparent)
            q=QPainter(strip)
            surface.paint_backdrop(q,self,rect,QRectF(0,0,rect.width(),height))
            q.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            ramp=QLinearGradient(0,0,0,height)
            ramp.setColorAt(0,QColor(0,0,0,255 if at_top else 0))
            ramp.setColorAt(1,QColor(0,0,0,0 if at_top else 255))
            q.fillRect(QRectF(0,0,rect.width(),height),ramp)
            q.end()
            self.faces[('fade',at_top)]=(state,strip)
            p.drawPixmap(rect.topLeft(),strip)

    PAD = 32  # room around a cached card for its shadow and coloured glow

    def draw_card(self,p,index,rect,opacity,distance=0,entrance=(1.0,1.0,1.0,1.0,1.0),t=0.0):
        """A card is three layers: a cached body (shadow, glow, living face), the
        artwork drawn live every frame, and a cached label strip on top. Idle
        frames therefore cost two blits and one artwork draw per card."""
        entry=self.entries[index]
        moving=enabled(self)
        rise,reveal,art_in,title_in,title_alpha=entrance
        lag=self.refresh_lags.get(entry.get('path'))
        bob,stretch,wobble=refresh_motion(self.refresh_elapsed,lag,24) if moving else (0.0,1.0,0.0)
        push,lift,sheen,(sx,sy)=self.ripple_for(rect,lag) if moving else (QPointF(),0.0,None,(1.0,1.0))
        glow_motion=max(0,-bob/24)
        focused=self.hasFocus() and index==self.selected_index
        if moving:
            hover=max(self.hover_level(index),1.0 if focused else 0.0)
            press=self.press_level(index)
            tilt=self.tilt if index==self.hover_index else (0.0,0.0)
        else:
            hover=1.0 if index==self.hover_index or focused else 0.0
            press,tilt=0.0,(0.0,0.0)
            t=0.0
        level=max(0.0,min(1.0,hover))
        top,bottom=self.palette_for(index)
        dpr=self.devicePixelRatioF()
        phase=index*1.618
        # Size: the card swells as it lifts and sinks when pressed; on entrance it
        # grows in from 90%. Only the shape scales; labels are re-anchored.
        swell=6*hover-3*press
        grow=(.9+.1*rise)*(1+self.RIPPLE_SWELL*lift)
        width,height=(rect.width()*grow-2*press)*sx,(rect.height()+2*swell)*grow*sy
        centre=rect.center()+push
        rect=QRectF(snap(centre.x()-width/2,dpr),snap(centre.y()-height/2-4*hover+40*(1-rise),dpr),width,height)
        # A lifted card casts the deeper shadow and hue glow of a hovered one.
        lit=max(level,.7*lift)
        # Living colour: each card drifts in hue and gradient angle, and a slow
        # diagonal wave of light and colour crosses the whole grid.
        diagonal=(rect.center().x()+rect.center().y()+self.offset)/max(1.0,self.width()+self.height())
        front=(t*.085)%1.9-.45
        wave=math.exp(-((diagonal-front)/.12)**2) if moving else 0.0
        drift=round(t*5+index*.23)/5  # body colours drift at 5 fps, staggered per card
        band=(round(sheen[0].x()*8),round(sheen[0].y()*8),round(sheen[1]*28),round(sheen[2]*8)) if sheen else None
        state=(round(rect.width()*dpr),round(rect.height()*dpr),top.rgb(),bottom.rgb(),drift,
               round(lit*30),round(glow_motion*30),round(wave*30),round(tilt[0]*10),round(tilt[1]*10),band)
        path=entry.get('path')
        cached=self.faces.get(path)
        if cached is None or cached[0]!=state:
            pad=self.PAD
            body=QPixmap(max(1,round((rect.width()+2*pad)*dpr)),max(1,round((rect.height()+2*pad)*dpr)))
            body.setDevicePixelRatio(dpr);body.fill(Qt.transparent)
            q=QPainter(body);q.setRenderHints(QPainter.Antialiasing|QPainter.SmoothPixmapTransform)
            self.paint_body(q,QRectF(pad,pad,rect.width(),rect.height()),index,top,bottom,drift,phase,lit,tilt,glow_motion,wave,front,diagonal,sheen)
            q.end()
            cached=(state,body)
            self.faces[path]=cached
        p.save();p.setOpacity(opacity*reveal)
        p.drawPixmap(QPointF(rect.left()-self.PAD,rect.top()-self.PAD),cached[1])
        self.paint_art(p,index,rect,opacity,reveal,art_in,hover,level,press,tilt,bob,stretch,wobble,t,phase,moving)
        strip=self.label_strip(index,entry,rect,title_in,title_alpha,hover,level,press,dpr)
        p.drawPixmap(QPointF(rect.left(),rect.bottom()-strip.deviceIndependentSize().height()),strip)
        p.restore()
        if focused:
            p.setPen(QPen(QColor('#f3e6ff'),1,Qt.DotLine));p.setBrush(Qt.NoBrush);p.drawRoundedRect(rect.adjusted(4,4,-4,-4),18,18)

    def paint_body(self,p,rect,index,top,bottom,t,phase,level,tilt,glow_motion,wave,front,diagonal,sheen=None):
        shift=.03*math.sin(t*.33+phase)+.07*wave+.09*glow_motion
        light=.1*wave+.14*glow_motion+.07*level
        def tone(colour,extra_shift=0.0,extra_light=0.0):
            hue=(colour.hsvHueF()+shift+extra_shift)%1.0
            return QColor.fromHsvF(hue,colour.hsvSaturationF(),min(1.0,colour.valueF()*(1+light+extra_light)))
        # Depth: a soft shadow plus a glow in the card's own hue as it rises.
        p.setPen(Qt.NoPen)
        for spread,alpha in ((0,32+24*level),(12,9+14*level)):
            p.setBrush(QColor(4,3,24,int(alpha)))
            p.drawRoundedRect(rect.translated(-3*tilt[0],6+9*level).adjusted(-spread*.4,0,spread*.4,spread),22+spread*.4,22+spread*.4)
        if level>.01:
            aura=QRadialGradient(rect.center().x(),rect.bottom(),rect.width()*.62)
            halo=tone(top,0.0,.35);halo.setAlpha(int(95*level))
            aura.setColorAt(0,halo);halo.setAlpha(0);aura.setColorAt(1,halo)
            p.setBrush(aura)
            p.drawEllipse(QRectF(rect.left()-24,rect.bottom()-rect.height()*.35,rect.width()+48,rect.height()*.7))
        shape=QPainterPath();shape.addRoundedRect(rect,22,22)
        angle=math.radians(38+16*math.sin(t*.21+phase))
        reach=math.hypot(rect.width(),rect.height())/2
        vector=QPointF(math.cos(angle)*reach,math.sin(angle)*reach)
        gradient=QLinearGradient(rect.center()-vector,rect.center()+vector)
        gradient.setColorAt(0,tone(top,-.015,.06))
        gradient.setColorAt(.55,tone(top,.02))
        gradient.setColorAt(1,tone(bottom,.04))
        p.fillPath(shape,gradient)
        p.save();p.setClipPath(shape)
        # A wandering complementary bloom keeps the colour field alive.
        bloom_at=QPointF(rect.left()+rect.width()*(.5+.36*math.sin(t*.4+phase)),rect.top()+rect.height()*(.26+.2*math.cos(t*.31+phase)))
        bloom=QRadialGradient(bloom_at,rect.width()*.72)
        glow=tone(top,.11,.45);glow.setAlpha(int(min(255,70+45*level+60*glow_motion+40*wave)))
        bloom.setColorAt(0,glow);glow.setAlpha(0);bloom.setColorAt(1,glow)
        p.setCompositionMode(QPainter.CompositionMode_Screen)
        p.fillPath(shape,bloom)
        if wave>.02:
            band=QLinearGradient(rect.topLeft(),rect.bottomRight())
            local=max(0.0,min(1.0,.5+(front-diagonal)*3.2))
            for stop,alpha in ((local-.25,0),(local,int(46*wave)),(local+.25,0)):
                band.setColorAt(max(0.0,min(1.0,stop)),QColor(255,248,255,alpha))
            p.fillPath(shape,band)
        if sheen is not None:
            # Light passing through the glass with the wave front, in the
            # direction the wave travels; strongest close to the orb.
            direction,position,strength=sheen
            extent=abs(direction.x())*rect.width()/2+abs(direction.y())*rect.height()/2
            start,end=rect.center()-direction*extent,rect.center()+direction*extent
            light_band=QLinearGradient(start,end)
            for stop,alpha in ((position-.24,0),(position-.07,46),(position,96),(position+.05,52),(position+.2,0)):
                light_band.setColorAt(max(0.0,min(1.0,stop)),QColor(255,247,255,int(alpha*strength)))
            p.fillPath(shape,light_band)
        if level>.01:
            spot=QRadialGradient(rect.center().x()+tilt[0]*rect.width()*.45,rect.center().y()+tilt[1]*rect.height()*.45,rect.width()*.55)
            spot.setColorAt(0,QColor(255,245,255,int(50*level)));spot.setColorAt(1,QColor(255,245,255,0))
            p.fillPath(shape,spot)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        # A gentle scrim keeps the title readable over any artwork colour.
        scrim=QLinearGradient(0,rect.top()+rect.height()*.5,0,rect.bottom())
        scrim.setColorAt(0,QColor(6,3,18,0));scrim.setColorAt(1,QColor(6,3,18,92))
        p.fillPath(shape,scrim)
        p.restore()
        p.setPen(QPen(QColor(255,246,255,int(min(255,34+60*level+50*wave))),1));p.setBrush(Qt.NoBrush);p.drawPath(shape)

    def paint_art(self,p,index,rect,opacity,reveal,art_in,hover,level,press,tilt,bob,stretch,wobble,t,phase,moving):
        artwork=self.artwork_for(index)
        size=min(self.art_size,rect.width()-54,rect.height()-92)
        if moving:
            # At rest the artwork floats and slowly turns; under the pointer it
            # rises, grows and turns in perspective toward it, showing its depth.
            idle=1-.75*level
            inertia=max(-12.0,min(12.0,-self.scroll_speed()*.012))
            yaw=9*math.sin(t*.55+phase)*idle+tilt[0]*28*level+75*(1-art_in)+wobble*2
            pitch=5*math.sin(t*.43+phase*1.3)*idle-tilt[1]*20*level
            roll=2.2*math.sin(t*.31+phase)*idle+wobble*.6
            lift=-size*.08*level+bob+size*.035*math.sin(t*.8+phase*.7)*idle+inertia
            scale=(.6+.4*art_in)*(1+.14*hover)*(1-.06*press)
        else:
            yaw=pitch=roll=lift=0.0
            scale=1.0
        centre=QPointF(rect.center().x()+tilt[0]*10*level,rect.top()+24+size/2)
        # Keep the artwork inside its card's reach and, for a top-row card, below
        # the grid's top edge however high the refresh throws it.
        floor=-(24+size*.06)
        if rect.top()>-size:
            floor=max(floor,-(rect.top()+24-size*(scale*1.15-1)/2-3))
        art3d.paint(p,artwork,centre,size,yaw=yaw,pitch=pitch,roll=roll,scale=scale,stretch=stretch,
                    opacity=opacity*reveal*max(0.0,min(1.0,art_in*2.2)),depth=size*.05*level if level>.05 else 0.0,
                    gloss=level,shadow=1.0,lift=max(lift,floor))

    def label_strip(self,index,entry,rect,title_in,title_alpha,hover,level,press,dpr):
        """Title and hover details, rendered once per change at device resolution."""
        height=90
        details=entry.get('details') or entry.get('subtitle','').split('·')[0].strip()
        if details.startswith('Explore'):details='Open project'
        state=(round(rect.width()*dpr),entry['name'],details,round(title_in*40),round(title_alpha*40),
               round(min(1.2,max(0.0,hover))*40),round(press*12),dpr)
        cached=self.faces.get(('labels',entry.get('path')))
        if cached is not None and cached[0]==state:
            return cached[1]
        strip=QPixmap(max(1,round(rect.width()*dpr)),round(height*dpr))
        strip.setDevicePixelRatio(dpr);strip.fill(Qt.transparent)
        q=QPainter(strip);q.setRenderHints(QPainter.Antialiasing|QPainter.TextAntialiasing)
        font=QFont(self.font());font.setPixelSize(17);font.setWeight(QFont.DemiBold)
        font.setHintingPreference(QFont.PreferVerticalHinting);q.setFont(font)
        title=QRectF(22,snap(height-67+14*(1-title_in),dpr),rect.width()-44,26)
        text=QFontMetrics(font).elidedText(entry['name'],Qt.ElideMiddle,int(title.width()))
        q.setOpacity(title_alpha*.55)
        q.setPen(QColor(6,2,20,150))
        q.drawText(title.translated(0,1),Qt.AlignLeft|Qt.AlignVCenter,text)
        q.setOpacity(title_alpha)
        q.setPen(QColor('#fffaff'))
        q.drawText(title,Qt.AlignLeft|Qt.AlignVCenter,text)
        if level>.01:
            # Details slide in from the left as the card lifts; the arrow leads.
            q.setOpacity(level)
            slide=snap(-12*(1-hover),dpr)
            font.setPixelSize(13);font.setWeight(QFont.Normal);q.setFont(font);q.setPen(QColor(244,238,252))
            caption=QRectF(22+slide,height-36,rect.width()-66,21)
            q.drawText(caption,Qt.AlignLeft|Qt.AlignVCenter,QFontMetrics(font).elidedText(details,Qt.ElideRight,int(caption.width())))
            q.setPen(QPen(QColor('#ffffff'),1.6,Qt.SolidLine,Qt.RoundCap))
            x,y=rect.width()-28-14*(1-hover)+3*press,height-26
            q.drawLine(QLineF(x-8,y,x+3,y));q.drawLine(QLineF(x-2,y-5,x+3,y));q.drawLine(QLineF(x-2,y+5,x+3,y))
        q.end()
        self.faces[('labels',entry.get('path'))]=(state,strip)
        return strip

    def contextMenuEvent(self,event):
        index=self.index_at(QPointF(event.pos()))
        if index>=0:
            self.context_requested.emit(index,event.globalPos())
            event.accept()

    def mouseReleaseEvent(self,event):
        if event.button()!=Qt.LeftButton or self.drag_start is None:return
        self.drag_start=None
        self.set_press_index(-1)
        if self.dragged:
            self.end_drag()
            return
        index=self.index_at(event.position())
        if index>=0:
            self.selectRow(index);self.activated.emit(index)

    def keyPressEvent(self,event):
        if event.key() not in (Qt.Key_Up,Qt.Key_Down):
            return super().keyPressEvent(event)
        current=max(0,self.selected_index)
        slots=self.layout_slots()
        if not slots:return
        row,col,span=slots[current]
        direction=1 if event.key()==Qt.Key_Down else -1
        candidates=[(abs(c+s/2-(col+span/2)),i) for i,(r,c,s) in enumerate(slots) if r==row+direction]
        if candidates:self.selectRow(min(candidates)[1])
        event.accept()

    def mouseDoubleClickEvent(self,event):
        event.accept()  # A single click opens a project or choice card.


def row_motion(owner,option,key,amplitude=8):
    """(hover, chosen, rise, reveal, artwork, bob, stretch, wobble) for one list row."""
    selected=bool(option.state & QStyle.State_Selected)
    if enabled(owner):
        hover=owner.hover_levels.get(key,0.0)
        chosen=owner.select_levels.get(key,1.0 if selected else 0.0)
        rise,reveal,art_in=owner.entrance(key)
        reveal*=1-.9*getattr(owner,'warp',0.0)  # arriving rows fade up after a long trip
        bob,stretch,wobble=refresh_motion(owner.refresh_elapsed,owner.refresh_lags.get(key),amplitude)
        return hover,chosen,rise,reveal,art_in,bob,stretch,wobble
    hover=1.0 if option.state & QStyle.State_MouseOver else 0.0
    return hover,1.0 if selected else 0.0,1.0,1.0,1.0,0.0,1.0,0.0


def row_ripple(owner,option,key,push=10.0):
    """(offset, lift 0..1) of a row the refresh wave is crossing: pushed away
    from the orb, lifted, then one rebound (the row only translates)."""
    lag=owner.refresh_lags.get(key)
    if lag is None or owner.refresh_elapsed<0 or not enabled(owner):
        return QPointF(),0.0
    amount,_=physics.ripple(owner.refresh_elapsed-lag)
    origin=getattr(owner,'refresh_origin',None)
    if origin is None:
        direction=QPointF(0.0,-1.0)
    else:
        delta=QPointF(owner.viewport().mapTo(owner,option.rect.center()))-origin
        length=math.hypot(delta.x(),delta.y()) or 1.0
        direction=QPointF(delta.x()/length,delta.y()/length)
    lift=max(0.0,amount)
    # Rows near the viewport's edge travel less along that axis, so they are never cropped.
    rect,view=QRectF(option.rect).adjusted(4,4,-4,-4),owner.viewport().rect()
    peak_x,peak_y=push*direction.x(),push*direction.y()-4
    kx=min(1.0,max(0.0,(rect.left()-1) if peak_x<0 else (view.width()-1-rect.right()))/abs(peak_x)) if abs(peak_x)>.5 else 1.0
    ky=min(1.0,max(0.0,(rect.top()-1) if peak_y<0 else (view.height()-1-rect.bottom()))/abs(peak_y)) if abs(peak_y)>.5 and rect.top()>=0 and rect.bottom()<=view.height() else 1.0
    return QPointF(push*amount*direction.x()*kx,(push*amount*direction.y()-4*lift)*ky),lift


def paint_row(p,owner,option,hover,chosen,rise,reveal,ripple=(QPointF(),0.0)):
    """Scene-tinted glass row; returns its rect. Labels stay pixel-aligned."""
    level,chosen=max(0.0,min(1.0,hover)),max(0.0,min(1.0,chosen))
    dpr=owner.devicePixelRatioF()
    offset,lift=ripple
    flow=owner.scroll_offset(option.rect) if hasattr(owner,'scroll_offset') else 0.0
    rect=QRectF(option.rect).adjusted(4,4,-4,-4)
    rect.moveTopLeft(QPointF(snap(rect.left()+offset.x(),dpr),snap(rect.top()+22*(1-rise)+offset.y()+flow,dpr)))
    p.setOpacity(reveal)
    surface=getattr(owner.window(),'surface',None)
    tint=surface.scene_colors()[1].lighter(420) if surface and hasattr(surface,'scene_colors') else QColor('#c9c3ff')
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255,255,255,int(15+13*level+18*chosen+20*lift)))
    p.drawRoundedRect(rect,15,15)
    if chosen>.01:
        tint.setAlpha(int(58*chosen))
        p.setBrush(tint)
        p.drawRoundedRect(rect,15,15)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(255,255,255,int(min(255,24+26*level+80*chosen+90*lift))),1))
    p.drawRoundedRect(rect,15,15)
    return rect


def paint_row_art(p,owner,art,centre,size,hover,reveal,art_in,bob,stretch,wobble,t=0.0,phase=0.0,swim=0.0):
    """Row artwork in perspective: it turns toward the viewer and lifts on hover;
    while the list glides it tips into the motion and trails a little behind."""
    moving=enabled(owner)
    tip=max(-10.0,min(10.0,-swim*.004)) if moving else 0.0
    trail=max(-5.0,min(5.0,swim*.0016)) if moving else 0.0
    art3d.paint(p,art,QPointF(centre.x(),centre.y()),size,
                yaw=(-22*hover+60*(1-art_in)+wobble*2+5*math.sin(t*.5+phase)*(1-hover)) if moving else 0.0,
                pitch=(8*hover+tip) if moving else 0.0,roll=wobble*.6 if moving else 0.0,
                scale=(.6+.4*art_in)*(1+.08*hover),stretch=stretch,
                opacity=reveal*max(0.0,min(1.0,art_in*2)),lift=bob-3*hover+trail,
                depth=size*.05*hover if hover>.05 else 0.0,gloss=hover*.7)


class FileDelegate(QStyledItemDelegate):
    def sizeHint(self,option,index):
        return QSize(240,90)

    def paint(self,p,option,index):
        file=index.data(Qt.UserRole)
        if not file:return
        owner=self.parent()
        hover,chosen,rise,reveal,art_in,bob,stretch,wobble=row_motion(owner,option,file['path'])
        p.save();p.setRenderHints(QPainter.Antialiasing|QPainter.TextAntialiasing|QPainter.SmoothPixmapTransform)
        rect=paint_row(p,owner,option,hover,chosen,rise,reveal,row_ripple(owner,option,file['path']))
        art=owner.app_art.get(file['application'])
        if art is None:
            art=owner.app_art[file['application']]=icon(file['application'],128).pixmap(128,128)
        paint_row_art(p,owner,art,QPointF(rect.left()+42,rect.top()+40),60,hover,reveal,art_in,bob,stretch,wobble,swim=owner.scroll_speed())
        p.setOpacity(reveal)
        text=rect.adjusted(88,14,-16,-10)
        font=option.font;font.setPixelSize(14);font.setBold(True);p.setFont(font)
        folder=file.get('folder')
        if folder:
            # All-stages view: the stage folder one level up leads the name.
            lead=folder.upper()+'  ›  '
            p.setPen(QColor(255,255,255,165))
            p.drawText(text,Qt.AlignTop,lead)
            text=text.adjusted(QFontMetrics(font).horizontalAdvance(lead),0,0,0)
        p.setPen(QColor('#fffaff'))
        p.drawText(text,Qt.AlignTop,QFontMetrics(font).elidedText(file['name'],Qt.ElideMiddle,int(text.width())))
        if folder:
            text=rect.adjusted(88,14,-16,-10)
        font.setPixelSize(12);font.setBold(False);p.setFont(font);p.setPen(QColor('#e8e1f2'))
        ai = file.get('department')=='AI Generation'
        if ai:
            from .indexer import ai_collection, AI_COLLECTIONS
            detail = AI_COLLECTIONS.get(ai_collection(file),'Other AI files')
        else:
            detail = file['shot']
        subtitle=(f"{file['stage_title']}  ·  " if file.get('stage_title') else '')+f"{file['application']}  ·  {detail}  ·  {file['version']}  ·  "+time.strftime('%d %b %Y',time.localtime(file['modified']))
        p.drawText(text.adjusted(0,28,0,0),Qt.AlignTop,QFontMetrics(font).elidedText(subtitle,Qt.ElideRight,int(text.width())))
        if option.state & QStyle.State_HasFocus:
            p.setBrush(Qt.NoBrush);p.setPen(QPen(QColor('#fffaff'),1,Qt.DotLine));p.drawRoundedRect(rect.adjusted(3,3,-3,-3),12,12)
        p.restore()


class ActivityDelegate(QStyledItemDelegate):
    """Timeline row: event artwork, event name, what it touched, and when."""
    def sizeHint(self,option,index):
        return QSize(240,78)

    def paint(self,p,option,index):
        entry=index.data(Qt.UserRole)
        if not entry:return
        owner=self.parent()
        hover,chosen,rise,reveal,art_in,bob,stretch,wobble=row_motion(owner,option,entry['path'],7)
        p.save();p.setRenderHints(QPainter.Antialiasing|QPainter.TextAntialiasing|QPainter.SmoothPixmapTransform)
        rect=paint_row(p,owner,option,hover,chosen,rise,reveal,row_ripple(owner,option,entry['path'],9.0))
        paint_row_art(p,owner,owner.pixmap(entry.get('artwork')),QPointF(rect.left()+38,rect.center().y()),50,
                      hover,reveal,art_in,bob,stretch,wobble,ambient_time(owner),index.row()*.9,owner.scroll_speed())
        p.setOpacity(reveal)
        font=option.font;font.setPixelSize(12);font.setBold(False);p.setFont(font)
        metrics=QFontMetrics(font)
        when=entry.get('when','')
        width=metrics.horizontalAdvance(when)+4
        p.setPen(QColor(232,226,244,190))
        p.drawText(QRectF(rect.right()-18-width,rect.top()+15,width,20),Qt.AlignRight|Qt.AlignVCenter,when)
        text=rect.adjusted(78,13,-34-width,-10)
        font.setPixelSize(14);font.setBold(True);p.setFont(font);p.setPen(QColor('#fffaff'))
        p.drawText(text,Qt.AlignTop,QFontMetrics(font).elidedText(entry['name'],Qt.ElideRight,int(text.width())))
        font.setPixelSize(12);font.setBold(False);p.setFont(font);p.setPen(QColor('#e8e1f2'))
        p.drawText(rect.adjusted(78,39,-18,-8),Qt.AlignTop,metrics.elidedText(entry.get('detail',''),Qt.ElideMiddle,int(rect.width()-96)))
        if option.state & QStyle.State_HasFocus:
            p.setBrush(Qt.NoBrush);p.setPen(QPen(QColor('#fffaff'),1,Qt.DotLine));p.drawRoundedRect(rect.adjusted(3,3,-3,-3),12,12)
        p.restore()


class FileList(QListWidget):
    selection_changed=Signal()
    activated=Signal(int)
    hovered=Signal(int)  # pointer arrived on a row; drives hover sound

    def __init__(self):
        super().__init__()
        self.setItemDelegate(FileDelegate(self))
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setMouseTracking(True)
        self.setStyleSheet('QListWidget { background: transparent; border: none; }')
        self.itemSelectionChanged.connect(self.selection_changed)
        self.itemSelectionChanged.connect(self.animate_selection)
        self.itemDoubleClicked.connect(lambda item:self.activated.emit(self.row(item)))
        self.empty_message='No matching files.'
        self.refresh_elapsed = -1.0
        self.refresh_lags = {}
        self.entrance_elapsed = -1.0
        self.entrance_delay = 0
        self.entrance_order = {}
        self.hover_levels, self.select_levels = {}, {}
        self.hover_path = None
        self.chosen = set()
        self.empty_art = None
        self.pixmaps = {}
        self.app_art = {}
        self.faces = {}
        # Every row has the same height, so thousands of rows lay out at once.
        self.setUniformItemSizes(True)
        # Spring scrolling state: a float position that may run past either end
        # (shown as an elastic edge), the overlay thumb's presence, wheel rhythm.
        self.scroll_pos = self.scroll_target = 0.0
        self.overscroll = 0.0
        self.scroll_anchor = None
        self.applying = False
        self.wheel_at, self.wheel_sign, self.wheel_streak = 0.0, 0, 0
        self.thumb = 0.0
        self.warp, self.warp_ghost, self.warp_sign = 0.0, None, 1
        self.edge_timer = QTimer(self)
        self.edge_timer.setSingleShot(True)
        self.edge_timer.timeout.connect(self.settle_edges)
        self.thumb_timer = QTimer(self)
        self.thumb_timer.setSingleShot(True)
        self.thumb_timer.timeout.connect(lambda: self.show_thumb(False))
        bar = self.verticalScrollBar()
        bar.valueChanged.connect(self.sync_scroll)
        bar.rangeChanged.connect(self.range_changed)

    # ------------------------------------------------------------ smooth scrolling
    STEP = 120.0  # px per wheel notch before quick notches gather speed

    def scroll_limit(self):
        return float(self.verticalScrollBar().maximum())

    def wheelEvent(self, event):
        """Spring scrolling: every notch glides instead of jumping, quick notches
        gather speed, and past either end the list gives a little before it
        eases home. A glide in flight is retargeted, never restarted."""
        delta = event.angleDelta().y()
        if not enabled(self) or not delta or event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier):
            return super().wheelEvent(event)
        now = time.monotonic()
        sign = 1 if delta < 0 else -1  # +1 travels down the list
        notch = abs(delta) >= 120
        if notch:
            quick = now-self.wheel_at < .16 and sign == self.wheel_sign
            self.wheel_streak = self.wheel_streak+1 if quick else 0
            step = self.STEP*min(2.6, 1+.32*self.wheel_streak)*abs(delta)/120
        else:
            step = self.STEP*abs(delta)/120  # high-resolution wheels and touchpads
        self.wheel_at, self.wheel_sign = now, sign
        self.scroll_anchor = event.position().y()
        low, high = 0.0, self.scroll_limit()
        target = self.scroll_target+sign*step
        if target < low:
            target = low-min(120.0, low-target)
        elif target > high:
            target = high+min(120.0, target-high)
        self.glide_to(target, GLIDE if notch else (.24, 1.0))
        if target < low or target > high:
            self.edge_timer.start(90)
        event.accept()

    def glide_to(self, target, feel=GLIDE, velocity=None):
        target = float(target)
        span = 2.5*max(200.0, self.viewport().height())
        distance = target-self.scroll_pos
        if abs(distance) > span*1.4 and self.isVisible():
            # A long trip (End, Home, a far reveal): rather than streak past
            # thousands of rows, the current rows dissolve away in the direction
            # of travel while the list lands a short glide from the target and
            # flies the last stretch in.
            self.warp_ghost = snapshot(self.viewport())
            self.warp_sign = 1 if distance > 0 else -1
            physics.cancel(self, 'scroll')
            self.apply_scroll(target-math.copysign(span, distance))
            velocity = math.copysign(span*5, distance)
            def fade(value):
                self.warp = max(0.0, float(value))
                self.viewport().update()
            def faded():
                self.warp_ghost = None
            self.warp = 1.0
            spring(self, 'warp', 0.0, fade, value=1.0, feel=(.3, 1.0), done=faded)
        self.scroll_target = target
        if self.scroll_limit() > 0:
            self.show_thumb(True)
        spring(self, 'scroll', self.scroll_target, self.apply_scroll, value=self.scroll_pos,
               velocity=velocity, feel=feel, precision=.25, done=self.scroll_settled)

    def apply_scroll(self, value):
        self.scroll_pos = float(value)
        low, high = 0.0, self.scroll_limit()
        clamped = max(low, min(high, self.scroll_pos))
        excess = self.scroll_pos-clamped
        # Past an end the rows stretch with growing resistance (a rubber band).
        self.overscroll = -math.copysign(rubber(abs(excess), max(1.0, self.viewport().height())), excess) if excess else 0.0
        self.applying = True
        self.verticalScrollBar().setValue(round(clamped))
        self.applying = False
        self.track_hover()
        self.viewport().update()

    def sync_scroll(self, value):
        if self.applying:
            return
        # Something else moved the list (a drag selection, a cleared list):
        # adopt its position and let go of any glide in flight.
        physics.cancel(self, 'scroll')
        self.scroll_pos = self.scroll_target = float(value)
        self.overscroll = 0.0

    def range_changed(self, low, high):
        if physics.get(self, 'scroll') is None:
            self.scroll_pos = self.scroll_target = float(max(low, min(high, self.verticalScrollBar().value())))
            self.overscroll = 0.0
        elif self.scroll_target > high and not self.edge_timer.isActive():
            self.glide_to(float(high), GLIDE)

    def settle_edges(self):
        """The wheel has stopped past an end: spring home with a soft landing."""
        low, high = 0.0, self.scroll_limit()
        if self.scroll_target < low or self.scroll_target > high:
            self.glide_to(max(low, min(high, self.scroll_target)), (.42, .86), physics.speed(self, 'scroll'))

    def scroll_settled(self):
        self.overscroll = 0.0
        self.scroll_anchor = None
        self.thumb_timer.start(700)
        self.viewport().update()

    def scroll_speed(self):
        """Current glide speed in px/s (positive travels down the list)."""
        return physics.speed(self, 'scroll') if enabled(self) else 0.0

    def scroll_offset(self, rect):
        """Paint offset of a row: the elastic edge, plus a gentle trail while the
        list glides; rows further from the pointer follow a little behind."""
        speed = self.scroll_speed()
        height = max(1.0, self.viewport().height())
        anchor = self.scroll_anchor if self.scroll_anchor is not None else height/2
        trail = max(-14.0, min(14.0, speed*.0045*abs(rect.center().y()-anchor)/height)) if speed else 0.0
        return self.overscroll+trail

    def scrollTo(self, index, hint=QAbstractItemView.EnsureVisible):
        """Keyboard moves and programmatic reveals glide too."""
        if not enabled(self) or not self.isVisible() or not index.isValid():
            return super().scrollTo(index, hint)
        rect, view = self.visualRect(index), self.viewport().height()
        value = self.verticalScrollBar().value()
        if hint == QAbstractItemView.PositionAtTop:
            target = value+rect.top()
        elif hint == QAbstractItemView.PositionAtBottom:
            target = value+rect.bottom()-view
        elif hint == QAbstractItemView.PositionAtCenter:
            target = value+rect.center().y()-view/2
        elif rect.top() < 0:
            target = value+rect.top()-6
        elif rect.bottom() > view:
            target = value+rect.bottom()-view+6
        else:
            return
        self.scroll_anchor = None
        self.glide_to(max(0.0, min(self.scroll_limit(), float(target))), GLIDE)

    def show_thumb(self, visible):
        if visible:
            self.thumb_timer.stop()
        def apply(value):
            self.thumb = max(0.0, float(value))
            self.viewport().update()
        spring(self, 'thumb', 1.0 if visible else 0.0, apply, value=self.thumb, feel=SNAPPY if visible else (.5, 1.0))

    def track_hover(self):
        """Rows passing under a resting pointer light up as they arrive (quietly while fast)."""
        view = self.viewport()
        point = view.mapFromGlobal(QCursor.pos())
        if view.rect().contains(point):
            self.update_hover(point, sound=abs(self.scroll_speed()) < 350)

    def pixmap(self, path):
        """Cached artwork for a row (application or event artwork)."""
        if path not in self.pixmaps:
            reader=QImageReader(str(path or ''));size=reader.size()
            if size.isValid():reader.setScaledSize(size.scaled(160,160,Qt.KeepAspectRatio))
            image=reader.read()
            self.pixmaps[path]=QPixmap.fromImage(image) if not image.isNull() else icon('Default',160).pixmap(160,160)
        return self.pixmaps[path]

    def visible_items(self):
        found=[]
        first=max(0,self.indexAt(QPoint(12,12)).row())
        for i in range(first,self.count()):
            item=self.item(i)
            rect=self.visualItemRect(item)
            if rect.top()>self.viewport().height():break
            if rect.intersects(self.viewport().rect()):found.append(item)
        return found

    def refresh_wave(self, delay=0, origin=None, speed=1650.0):
        self.refresh_origin=QPointF(origin) if origin is not None else None
        lags={}
        for n,item in enumerate(self.visible_items()):
            centre=QPointF(self.viewport().mapTo(self,self.visualItemRect(item).center()))
            reach=QLineF(QPointF(origin),centre).length()/speed*1000 if origin is not None else min(n*65,650)
            lags[item.data(Qt.UserRole)['path']]=delay+reach
        self.refresh_lags=lags
        def step(value):
            self.refresh_elapsed=float(value)
            self.viewport().update()
        clock(self,'_refresh_files',max(physics.BOUNCE_MS,physics.RIPPLE_MS)+max(lags.values(),default=0),step,self.reset_wave)

    def reset_wave(self):
        if getattr(self,'_refresh_files',None):self._refresh_files.stop()
        self.refresh_elapsed=-1.0
        self.refresh_lags.clear()
        self.viewport().update()

    def play_entrance(self, delay=0):
        """Rows rise one after another; each icon pops a beat after its row."""
        if not enabled(self) or not self.count():
            self.entrance_elapsed=-1.0
            self.viewport().update()
            return
        # Row order rather than geometry: freshly filled lists may not be laid out yet.
        first=max(0,self.indexAt(QPoint(12,12)).row())
        self.entrance_order={self.item(row).data(Qt.UserRole)['path']:row-first
                             for row in range(first,min(self.count(),first+16))}
        self.entrance_delay=delay
        self.entrance_elapsed=0.0
        def step(value):
            self.entrance_elapsed=float(value)
            self.viewport().update()
        def finished():
            self.entrance_elapsed=-1.0
            self.viewport().update()
        steps=min(len(self.entrance_order),14)
        clock(self,'_entrance',delay+steps*38+physics.settle_time(*POP)+120,step,finished)

    def entrance(self,path):
        """(rise, opacity, icon) for a row, 1 at rest."""
        order=self.entrance_order.get(path)
        if self.entrance_elapsed<0 or order is None:
            return 1.0,1.0,1.0
        local=self.entrance_elapsed-self.entrance_delay-min(order,14)*38
        return physics.progress(local,.5,.82),max(0.0,min(1.0,local/160)),physics.progress(local-60,*POP)

    def glide(self,levels,path,target,feel):
        def apply(value):
            levels[path]=value
            self.viewport().update()
        spring(self,(id(levels),path),target,apply,value=levels.get(path,0.0),feel=feel)

    def animate_selection(self):
        chosen={item.data(Qt.UserRole)['path'] for item in self.selectedItems()}
        for path in chosen^self.chosen:
            self.glide(self.select_levels,path,1.0 if path in chosen else 0.0,SNAPPY if path in chosen else (.32,1.0))
        self.chosen=chosen

    def update_hover(self,point,sound=True):
        item=self.itemAt(point)
        path=item.data(Qt.UserRole)['path'] if item else None
        if path!=self.hover_path:
            if self.hover_path is not None:
                self.glide(self.hover_levels,self.hover_path,0.0,(.4,.95))
            if path is not None:
                self.glide(self.hover_levels,path,1.0,SNAPPY)
                if sound:
                    self.hovered.emit(self.row(item))
            self.hover_path=path

    def mouseMoveEvent(self,event):
        self.update_hover(event.position().toPoint())
        super().mouseMoveEvent(event)

    def leaveEvent(self,event):
        if self.hover_path is not None:
            self.glide(self.hover_levels,self.hover_path,0.0,(.4,.95))
            self.hover_path=None
        super().leaveEvent(event)

    def set_entries(self,entries):
        old=[self.item(i).data(Qt.UserRole)['path'] for i in range(self.count())]
        new=[f['path'] for f in entries]
        changed=new!=old
        # A refreshed or re-scanned view keeps its place: the row at the top
        # stays put instead of the list snapping back to the start. A different
        # view (another filter or sort order) starts at the top as usual.
        anchor=None
        if changed and old and self.verticalScrollBar().value()>0:
            kept_old,kept_new=set(old),set(new)
            common=kept_old&kept_new
            if len(common)>=.6*len(old) and [p for p in old if p in kept_new]==[p for p in new if p in kept_old]:
                top=self.indexAt(QPoint(12,12))
                if top.isValid():
                    anchor=(old[top.row()],self.visualRect(top).top())
        selected={item.data(Qt.UserRole)['path'] for item in self.selectedItems()}
        self.blockSignals(True);self.clear()
        for file in entries:
            item=QListWidgetItem();item.setData(Qt.UserRole,file);item.setToolTip(file.get('tooltip',file['path']));self.addItem(item)
            if file['path'] in selected:
                self.setCurrentItem(item,QItemSelectionModel.Select);item.setSelected(True)
        self.blockSignals(False)
        self.chosen={item.data(Qt.UserRole)['path'] for item in self.selectedItems()}
        self.select_levels={path:1.0 for path in self.chosen}
        self.hover_path=None
        self.selection_changed.emit();self.viewport().update()
        if not changed:
            return
        physics.cancel(self,'scroll')
        self.overscroll=0.0
        rows={path:row for row,path in enumerate(new)}
        if anchor and anchor[0] in rows:
            self.doItemsLayout()
            index=self.model().index(rows[anchor[0]],0)
            bar=self.verticalScrollBar()
            bar.setValue(max(0,round(bar.value()+self.visualRect(index).top()-anchor[1])))
        else:
            # A new view starts at its first row (Qt keeps the old offset
            # across clear() until the next layout).
            self.verticalScrollBar().setValue(0)
            self.play_entrance()

    def paint_edges(self,p):
        """Rows dissolve into the living backdrop where the list continues."""
        surface=getattr(self.window(),'surface',None)
        if surface is None or getattr(surface,'frame',None) is None or not hasattr(surface,'paint_backdrop'):
            return
        view,bar=self.viewport(),self.verticalScrollBar()
        dpr=view.devicePixelRatioF()
        for at_top,active in ((True,bar.value()>1),(False,bar.value()<bar.maximum()-1)):
            if not active:
                continue
            height=28 if at_top else 40
            rect=QRectF(0,0 if at_top else view.height()-height,view.width(),height)
            state=(surface.frame_key,view.width(),view.height(),dpr,view.mapTo(surface,QPoint(0,0)).toTuple())
            cached=self.faces.get(at_top)
            if cached is None or cached[0]!=state:
                strip=QPixmap(max(1,round(rect.width()*dpr)),max(1,round(height*dpr)))
                strip.setDevicePixelRatio(dpr)
                strip.fill(Qt.transparent)
                q=QPainter(strip)
                surface.paint_backdrop(q,view,rect,QRectF(0,0,rect.width(),height))
                q.setCompositionMode(QPainter.CompositionMode_DestinationIn)
                ramp=QLinearGradient(0,0,0,height)
                ramp.setColorAt(0,QColor(0,0,0,255 if at_top else 0))
                ramp.setColorAt(1,QColor(0,0,0,0 if at_top else 255))
                q.fillRect(QRectF(0,0,rect.width(),height),ramp)
                q.end()
                cached=(state,strip)
                self.faces[at_top]=cached
            p.drawPixmap(rect.topLeft(),cached[1])

    def paint_thumb(self,p):
        """An overlay thumb that appears while the list moves, squashing at the ends."""
        bar=self.verticalScrollBar()
        if self.thumb<=.01 or bar.maximum()<=0:
            return
        view=self.viewport()
        height=view.height()
        length=max(32.0,height*height/(bar.maximum()+height))
        travel=height-length-8
        y=4+travel*bar.value()/bar.maximum()
        squash=min(length-12,abs(self.overscroll)*.8)
        length-=squash
        if self.overscroll<0:
            y+=squash
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255,255,255,int(110*self.thumb)))
        p.drawRoundedRect(QRectF(view.width()-7,y,3,length),1.5,1.5)

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
        if self.count():
            p=QPainter(self.viewport())
            p.setRenderHints(QPainter.Antialiasing|QPainter.SmoothPixmapTransform)
            if self.warp_ghost is not None and self.warp>.01:
                # The rows we left slide away and dissolve through the backdrop
                # while the arriving rows fade up (see row_motion), never both at once.
                p.setOpacity(self.warp**2.5)
                p.drawPixmap(QPointF(0,snap(-self.warp_sign*(1-self.warp)*self.viewport().height()*.5,self.devicePixelRatioF())),self.warp_ghost)
                p.setOpacity(1.0)
            self.paint_edges(p)
            self.paint_thumb(p)
            return
        if not self.count():
            p=QPainter(self.viewport())
            p.setRenderHints(QPainter.Antialiasing|QPainter.TextAntialiasing|QPainter.SmoothPixmapTransform)
            box=QRectF(self.viewport().rect()).adjusted(30,20,-30,-20)
            if self.empty_art is not None:
                t=ambient_time(self) if enabled(self) else 0.0
                size=min(150.0,self.viewport().height()*.36)
                centre=QPointF(box.center().x(),box.center().y()-size*.45)
                art3d.paint(p,self.empty_art,centre,size,yaw=10*math.sin(t*.5),pitch=5*math.sin(t*.4),
                            roll=2*math.sin(t*.3),lift=size*.04*math.sin(t*.8),shadow=1.0,opacity=.92)
                box=QRectF(box.left(),centre.y()+size*.62,box.width(),80)
            font=QFont(self.font());font.setPixelSize(15);p.setFont(font)
            p.setPen(QColor(236,230,246,215))
            p.drawText(box,Qt.AlignHCenter|(Qt.AlignTop if self.empty_art is not None else Qt.AlignVCenter)|Qt.TextWordWrap,self.empty_message)


class ActivityList(FileList):
    """Recent activity as a living timeline of glass rows."""
    def __init__(self):
        super().__init__()
        self.setItemDelegate(ActivityDelegate(self))
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setAccessibleName('Recent activity')
        self.empty_message='No activity yet. Opening files, saving versions and assigning stages will appear here.'
