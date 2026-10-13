"""Uniform cards, asynchronous project artwork and native-resolution file rows."""
import hashlib
import math
import time
import os
import re
import tempfile
from pathlib import Path
from PySide6.QtCore import Qt, QObject, Signal, QRunnable, QThreadPool, QRectF, QSize, QItemSelectionModel, QPoint, QPointF, QLineF
from PySide6.QtGui import QPainter, QColor, QPen, QImageReader, QPixmap, QFontMetrics, QIcon, QLinearGradient, QRadialGradient, QPainterPath, QFont
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QStyledItemDelegate, QAbstractItemView, QStyle
from . import art3d, physics
from .ambient import ambient_time
from .cards import CardSurface
from .design import icon
from .motion import clock, enabled, refresh_motion, snap, spring
from .physics import POP, SNAPPY
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

    def refresh_wave(self, delay=0, origin=None, speed=1650.0):
        """Bounce visible artwork; with an origin, each card jumps as the wave front reaches it."""
        lags={}
        rects=self.card_rects()
        for n,i in enumerate(sorted(rects)):
            rect=rects[i]
            if rect.bottom()<0 or rect.top()>self.height():
                continue
            reach=QLineF(QPointF(origin),rect.center()).length()/speed*1000 if origin is not None else min(n*65,650)
            lags[self.entries[i].get('path')]=delay+reach
        self.refresh_lags=lags
        def step(value):
            self.refresh_elapsed = float(value)
            self.update()
        clock(self,'_refresh_cards',physics.BOUNCE_MS+max(lags.values(),default=0),step,self.reset_wave)

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
        for i in sorted(rects,key=lambda i:(self.hover_level(i),i)):
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
        bob,stretch,wobble=refresh_motion(self.refresh_elapsed,self.refresh_lags.get(entry.get('path')),18) if moving else (0.0,1.0,0.0)
        glow_motion=max(0,-bob/18)
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
        grow=.9+.1*rise
        width,height=rect.width()*grow-2*press,(rect.height()+2*swell)*grow
        centre=rect.center()
        rect=QRectF(snap(centre.x()-width/2,dpr),snap(centre.y()-height/2-4*hover+40*(1-rise),dpr),width,height)
        # Living colour: each card drifts in hue and gradient angle, and a slow
        # diagonal wave of light and colour crosses the whole grid.
        diagonal=(rect.center().x()+rect.center().y()+self.offset)/max(1.0,self.width()+self.height())
        front=(t*.085)%1.9-.45
        wave=math.exp(-((diagonal-front)/.12)**2) if moving else 0.0
        drift=round(t*5+index*.23)/5  # body colours drift at 5 fps, staggered per card
        state=(round(rect.width()*dpr),round(rect.height()*dpr),top.rgb(),bottom.rgb(),drift,
               round(level*30),round(glow_motion*30),round(wave*30),round(tilt[0]*10),round(tilt[1]*10))
        path=entry.get('path')
        cached=self.faces.get(path)
        if cached is None or cached[0]!=state:
            pad=self.PAD
            body=QPixmap(max(1,round((rect.width()+2*pad)*dpr)),max(1,round((rect.height()+2*pad)*dpr)))
            body.setDevicePixelRatio(dpr);body.fill(Qt.transparent)
            q=QPainter(body);q.setRenderHints(QPainter.Antialiasing|QPainter.SmoothPixmapTransform)
            self.paint_body(q,QRectF(pad,pad,rect.width(),rect.height()),index,top,bottom,drift,phase,level,tilt,glow_motion,wave,front,diagonal)
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

    def paint_body(self,p,rect,index,top,bottom,t,phase,level,tilt,glow_motion,wave,front,diagonal):
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
        art3d.paint(p,artwork,centre,size,yaw=yaw,pitch=pitch,roll=roll,scale=scale,stretch=stretch,
                    opacity=opacity*reveal*max(0.0,min(1.0,art_in*2.2)),depth=size*.05*level if level>.05 else 0.0,
                    gloss=level,shadow=1.0,lift=max(lift,-(24+size*.06)))

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
        bob,stretch,wobble=refresh_motion(owner.refresh_elapsed,owner.refresh_lags.get(key),amplitude)
        return hover,chosen,rise,reveal,art_in,bob,stretch,wobble
    hover=1.0 if option.state & QStyle.State_MouseOver else 0.0
    return hover,1.0 if selected else 0.0,1.0,1.0,1.0,0.0,1.0,0.0


def paint_row(p,owner,option,hover,chosen,rise,reveal):
    """Scene-tinted glass row; returns its rect. Labels stay pixel-aligned."""
    level,chosen=max(0.0,min(1.0,hover)),max(0.0,min(1.0,chosen))
    dpr=owner.devicePixelRatioF()
    rect=QRectF(option.rect).adjusted(4,4,-4,-4)
    rect.moveTop(snap(rect.top()+22*(1-rise),dpr))
    p.setOpacity(reveal)
    surface=getattr(owner.window(),'surface',None)
    tint=surface.scene_colors()[1].lighter(420) if surface and hasattr(surface,'scene_colors') else QColor('#c9c3ff')
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255,255,255,int(15+13*level+18*chosen)))
    p.drawRoundedRect(rect,15,15)
    if chosen>.01:
        tint.setAlpha(int(58*chosen))
        p.setBrush(tint)
        p.drawRoundedRect(rect,15,15)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(255,255,255,int(24+26*level+80*chosen)),1))
    p.drawRoundedRect(rect,15,15)
    return rect


def paint_row_art(p,owner,art,centre,size,hover,reveal,art_in,bob,stretch,wobble,t=0.0,phase=0.0):
    """Row artwork in perspective: it turns toward the viewer and lifts on hover."""
    moving=enabled(owner)
    art3d.paint(p,art,QPointF(centre.x(),centre.y()),size,
                yaw=(-22*hover+60*(1-art_in)+wobble*2+5*math.sin(t*.5+phase)*(1-hover)) if moving else 0.0,
                pitch=(8*hover) if moving else 0.0,roll=wobble*.6 if moving else 0.0,
                scale=(.6+.4*art_in)*(1+.08*hover),stretch=stretch,
                opacity=reveal*max(0.0,min(1.0,art_in*2)),lift=bob-3*hover,
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
        rect=paint_row(p,owner,option,hover,chosen,rise,reveal)
        art=icon(file['application'],128).pixmap(128,128)
        paint_row_art(p,owner,art,QPointF(rect.left()+42,rect.top()+40),60,hover,reveal,art_in,bob,stretch,wobble)
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
        subtitle=(f"{file['stage_title']}  ·  " if file.get('stage_title') else '')+f"{file['application']}  ·  {file['shot']}  ·  {file['version']}  ·  "+time.strftime('%d %b %Y',time.localtime(file['modified']))
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
        rect=paint_row(p,owner,option,hover,chosen,rise,reveal)
        paint_row_art(p,owner,owner.pixmap(entry.get('artwork')),QPointF(rect.left()+38,rect.center().y()),50,
                      hover,reveal,art_in,bob,stretch,wobble,ambient_time(owner),index.row()*.9)
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
        lags={}
        for n,item in enumerate(self.visible_items()):
            centre=QPointF(self.viewport().mapTo(self,self.visualItemRect(item).center()))
            reach=QLineF(QPointF(origin),centre).length()/speed*1000 if origin is not None else min(n*65,650)
            lags[item.data(Qt.UserRole)['path']]=delay+reach
        self.refresh_lags=lags
        def step(value):
            self.refresh_elapsed=float(value)
            self.viewport().update()
        clock(self,'_refresh_files',physics.BOUNCE_MS+max(lags.values(),default=0),step,self.reset_wave)

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

    def mouseMoveEvent(self,event):
        item=self.itemAt(event.position().toPoint())
        path=item.data(Qt.UserRole)['path'] if item else None
        if path!=self.hover_path:
            if self.hover_path is not None:
                self.glide(self.hover_levels,self.hover_path,0.0,(.4,.95))
            if path is not None:
                self.glide(self.hover_levels,path,1.0,SNAPPY)
            self.hover_path=path
        super().mouseMoveEvent(event)

    def leaveEvent(self,event):
        if self.hover_path is not None:
            self.glide(self.hover_levels,self.hover_path,0.0,(.4,.95))
            self.hover_path=None
        super().leaveEvent(event)

    def set_entries(self,entries):
        changed=[f['path'] for f in entries]!=[self.item(i).data(Qt.UserRole)['path'] for i in range(self.count())]
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
        if changed:
            self.play_entrance()

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
