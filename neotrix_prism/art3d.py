"""Pseudo-3D artwork: real perspective rotation of rendered 3D icons, with
extruded thickness, a specular sweep that tracks the turn, and a floating
contact shadow. Also derives a card palette from an artwork's dominant colour.
"""
import math
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPixmap, QRadialGradient, QTransform

_silhouettes = {}
_dominants = {}
_scaled = {}


def _cached(store, key, build, limit=96):
    if key not in store:
        if len(store) >= limit:
            store.pop(next(iter(store)))
        store[key] = build()
    return store[key]


def fitted(pixmap, pixels):
    """The artwork pre-scaled near its on-screen size: sharper and far cheaper
    to transform every frame than sampling the full-size source."""
    pixels = max(16, min(max(pixmap.width(), pixmap.height()), int(math.ceil(pixels/24.0)*24)))
    def build():
        return pixmap.scaled(pixels, pixels, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return _cached(_scaled, (pixmap.cacheKey(), pixels), build, 160)


def silhouette(pixmap, colour):
    """The artwork's shape filled with one colour (for thickness and gloss)."""
    def build():
        image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32_Premultiplied)
        p = QPainter(image)
        p.setCompositionMode(QPainter.CompositionMode_SourceIn)
        p.fillRect(image.rect(), colour)
        p.end()
        return QPixmap.fromImage(image)
    return _cached(_silhouettes, (pixmap.cacheKey(), colour.rgba()), build)


def dominant(pixmap):
    """Saturation-weighted dominant colour of opaque artwork pixels."""
    def build():
        image = pixmap.toImage().scaled(28, 28, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        x = y = weight = sat = val = 0.0
        for py in range(image.height()):
            for px in range(image.width()):
                c = image.pixelColor(px, py)
                if c.alpha() < 160:
                    continue
                s, v = c.hsvSaturationF(), c.valueF()
                hue = c.hsvHueF()
                if hue < 0:
                    continue
                w = s*s*v*(c.alpha()/255)
                angle = hue*2*math.pi
                x += math.cos(angle)*w
                y += math.sin(angle)*w
                weight += w
                sat += s*w
                val += v*w
        if weight <= 0:
            return QColor.fromHsvF(.74, .5, .7)
        hue = (math.atan2(y, x)/(2*math.pi)) % 1.0
        return QColor.fromHsvF(hue, min(1.0, sat/weight), min(1.0, val/weight))
    return _cached(_dominants, pixmap.cacheKey(), build)


def luminance(colour):
    def channel(v):
        v /= 255
        return v/12.92 if v <= .03928 else ((v+.055)/1.055)**2.4
    return .2126*channel(colour.red())+.7152*channel(colour.green())+.0722*channel(colour.blue())


def readable(hue, saturation, value, ceiling):
    """Darken until white text keeps contrast (relative luminance under ceiling)."""
    colour = QColor.fromHsvF(hue % 1.0, saturation, value)
    while luminance(colour) > ceiling and value > .2:
        value -= .025
        colour = QColor.fromHsvF(hue % 1.0, saturation, value)
    return colour


def card_palette(pixmap, hue_shift=0.0):
    """(top, bottom) gradient for a card, matched to its artwork and safe for white text."""
    base = dominant(pixmap)
    hue = (base.hsvHueF() if base.hsvHueF() >= 0 else .74)+hue_shift
    saturation = max(.38, min(.78, base.hsvSaturationF()*.9))
    return (readable(hue-.02, saturation, .74, .2),
            readable(hue+.05, min(.9, saturation+.08), .5, .08))


def paint(p, pixmap, centre, size, yaw=0.0, pitch=0.0, roll=0.0, scale=1.0, stretch=1.0,
          opacity=1.0, depth=0.0, gloss=0.0, shadow=0.0, lift=0.0):
    """Draw artwork as a solid object turned in perspective.

    yaw/pitch/roll are degrees; depth is extrusion in pixels; gloss and shadow
    are 0..1 strengths; lift raises the object above its contact shadow.
    """
    if pixmap is None or pixmap.isNull() or opacity <= 0:
        return
    p.save()
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    if shadow > 0:
        # The contact shadow stays on the "floor": it tightens and fades as the
        # object rises, which is what sells the float.
        rise = max(0.0, -lift)/max(1.0, size)
        width = size*(.62-.3*rise)*scale
        floor = QPointF(centre.x(), centre.y()+size*.47*scale)
        shade = QRadialGradient(floor, width/2)
        tone = QColor(6, 3, 20, int(110*shadow*opacity*max(.25, 1-1.6*rise)))
        shade.setColorAt(0, tone)
        tone.setAlpha(0)
        shade.setColorAt(1, tone)
        p.setPen(Qt.NoPen)
        p.setBrush(shade)
        p.drawEllipse(QRectF(floor.x()-width/2, floor.y()-width*.16, width, width*.32))
    distance = max(240.0, size*3.2)
    dpr = p.device().devicePixelRatioF() if p.device() else 1.0
    pixmap = fitted(pixmap, size*scale*dpr*1.15)
    t = QTransform()
    t.translate(centre.x(), centre.y()+lift)
    t.rotate(roll)
    if abs(yaw) < 14 and abs(pitch) < 9 and depth <= .5 and gloss <= .01:
        # Small idle turns: an affine foreshortening reads the same as a true
        # perspective turn at a fraction of the cost.
        t.scale(math.cos(math.radians(yaw)), math.cos(math.radians(pitch)))
        t.shear(0, -math.sin(math.radians(yaw))*.08)
    else:
        t.rotate(yaw, Qt.YAxis, distance)
        t.rotate(pitch, Qt.XAxis, distance)
    t.scale(scale*(2-stretch), scale*stretch)
    target = QRectF(-size/2, -size/2, size, size)
    source = QRectF(pixmap.rect())
    p.setOpacity(opacity)
    if depth > .5:
        # Back faces of the extrusion appear displaced against the turn.
        dx = -math.sin(math.radians(yaw))*depth
        dy = math.sin(math.radians(pitch))*depth
        layers = 5
        for k in range(layers, 0, -1):
            f = k/layers
            shade = QColor.fromHsvF(dominant(pixmap).hsvHueF() % 1.0, .55, .16+.22*(1-f))
            p.setTransform(t*QTransform.fromTranslate(dx*f, dy*f))
            p.drawPixmap(target, silhouette(pixmap, shade), source)
    p.setTransform(t)
    p.drawPixmap(target, pixmap, source)
    if gloss > .01:
        # A light band slides across the surface opposite to the turn.
        band = max(.0, min(1.0, .5-yaw/48+pitch/80))
        side = 220
        sheen = QImage(side, side, QImage.Format_ARGB32_Premultiplied)
        sheen.fill(Qt.transparent)
        q = QPainter(sheen)
        q.setRenderHint(QPainter.SmoothPixmapTransform)
        q.drawPixmap(QRectF(0, 0, side, side), silhouette(pixmap, QColor(255, 255, 255)), source)
        q.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        stripe = QLinearGradient(0, 0, side, side*.55)
        for stop, alpha in ((band-.32, 0), (band-.06, 150), (band, 230), (band+.07, 120), (band+.3, 0)):
            stripe.setColorAt(max(0.0, min(1.0, stop)), QColor(0, 0, 0, alpha))
        q.fillRect(sheen.rect(), stripe)
        q.end()
        p.setCompositionMode(QPainter.CompositionMode_Screen)
        p.setOpacity(opacity*gloss*.55)
        p.drawImage(target, sheen)
    p.restore()
