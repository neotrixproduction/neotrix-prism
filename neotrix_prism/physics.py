"""Retargetable spring physics on Qt's unified animation clock.

Fixed-duration tweens restart from a standstill whenever they are interrupted,
which is what makes interface motion feel mechanical. Springs here keep their
velocity when given a new destination, so hover, scroll, selection and page
motion flow into each other. Every spring is solved in closed form, so a slow
frame never destabilises it, and the shared driver stops when nothing moves.
"""
import math
from PySide6.QtCore import QAbstractAnimation, QCoreApplication

try:
    from shiboken6 import isValid as _alive
except ImportError:  # pragma: no cover - shiboken ships with PySide6
    def _alive(obj):
        return True

# Motion vocabulary: (response in seconds, damping ratio). Lower damping is
# livelier; 1.0 arrives without overshoot.
SNAPPY = (.28, .78)     # pointer feedback, buttons
POP = (.42, .52)        # artwork landing with a visible bounce
FLUID = (.46, .82)      # entrances and shared elements
GLIDE = (.36, 1.0)      # scrolling and layout, never overshoots
SETTLE = (.9, .96)      # atmosphere and large colour fields
EXIT = (.2, 1.0)        # fast departures


def sample(displacement, velocity, elapsed, response, damping):
    """Exact (displacement, velocity) of a unit-mass damped oscillator."""
    omega = 2*math.pi/max(response, 1e-3)
    zeta = max(0.0, damping)
    x0, v0, t = displacement, velocity, max(0.0, elapsed)
    if zeta < .9999:
        wd = omega*math.sqrt(1-zeta*zeta)
        decay = math.exp(-zeta*omega*t)
        c, s = math.cos(wd*t), math.sin(wd*t)
        return (decay*(x0*c + (v0+zeta*omega*x0)/wd*s),
                decay*(v0*c - (x0*omega*omega+zeta*omega*v0)/wd*s))
    if zeta <= 1.0001:
        decay = math.exp(-omega*t)
        k = v0+omega*x0
        return decay*(x0+k*t), decay*(v0-omega*k*t)
    wo = omega*math.sqrt(zeta*zeta-1)
    r1, r2 = -zeta*omega+wo, -zeta*omega-wo
    c2 = (r1*x0-v0)/(r1-r2)
    c1 = x0-c2
    e1, e2 = math.exp(r1*t), math.exp(r2*t)
    return c1*e1+c2*e2, c1*r1*e1+c2*r2*e2


def progress(elapsed_ms, response, damping):
    """0 → 1 settle sampled at a time, for painters driven by one shared clock."""
    if elapsed_ms <= 0:
        return 0.0
    return 1.0+sample(-1.0, 0.0, elapsed_ms/1000, response, damping)[0]


def settle_time(response, damping, tolerance=.004):
    """Milliseconds until a 0 → 1 settle stays within tolerance."""
    t, last_outside = 0.0, 0.0
    while t < 6000:
        x, v = sample(-1.0, 0.0, t/1000, response, damping)
        if abs(x) > tolerance or abs(v) > tolerance*20:
            last_outside = t
        t += 8
    return int(last_outside+8)


class Spring:
    __slots__ = ('owner', 'key', 'update', 'done', 'vector', 'value', 'velocity', 'target',
                 'response', 'damping', 'precision', 'delay')

    def __init__(self, owner, key, value, update):
        self.owner, self.key, self.update, self.done = owner, key, update, None
        self.vector = isinstance(value, (tuple, list))
        self.value = [float(v) for v in value] if self.vector else [float(value)]
        self.velocity = [0.0]*len(self.value)
        self.target = list(self.value)
        self.response, self.damping = GLIDE
        self.precision = .001
        self.delay = 0.0

    def current(self):
        return tuple(self.value) if self.vector else self.value[0]

    def speed(self):
        return tuple(self.velocity) if self.vector else self.velocity[0]

    def step(self, dt):
        if self.delay > 0:
            self.delay -= dt
            if self.delay > 0:
                return False
            dt = -self.delay
            self.delay = 0.0
        resting = True
        for i, target in enumerate(self.target):
            x, v = sample(self.value[i]-target, self.velocity[i], dt, self.response, self.damping)
            if abs(x) > self.precision or abs(v) > self.precision*12:
                resting = False
            self.value[i], self.velocity[i] = target+x, v
        if resting:
            self.value = list(self.target)
            self.velocity = [0.0]*len(self.value)
        return resting


class _Driver(QAbstractAnimation):
    """One frame clock for every spring; it runs only while something moves."""
    def __init__(self):
        super().__init__(QCoreApplication.instance())
        self.springs = {}
        self.watched = set()
        self.last = None

    def duration(self):
        return -1

    def updateCurrentTime(self, current):
        now = current/1000
        dt = 0.0 if self.last is None else min(.064, max(0.0, now-self.last))
        self.last = now
        if not dt:
            return
        for ident, spring in list(self.springs.items()):
            if not _alive(spring.owner):
                self.springs.pop(ident, None)
                continue
            resting = spring.step(dt)
            if resting and self.springs.get(ident) is spring:
                self.springs.pop(ident, None)
            try:
                spring.update(spring.current())
                if resting and spring.done:
                    spring.done()
            except RuntimeError:
                self.springs.pop(ident, None)
        if not self.springs:
            self.stop()

    def ensure(self):
        if self.state() != QAbstractAnimation.Running:
            self.last = None
            self.start()

    def watch(self, owner):
        ident = id(owner)
        if ident in self.watched or not hasattr(owner, 'destroyed'):
            return
        self.watched.add(ident)
        def forget(*_):
            self.watched.discard(ident)
            for key in [k for k in self.springs if k[0] == ident]:
                self.springs.pop(key, None)
        owner.destroyed.connect(forget)


_driver_instance = None


def _driver():
    global _driver_instance
    if _driver_instance is None or not _alive(_driver_instance):
        _driver_instance = _Driver()
    return _driver_instance


def animate(owner, key, target, update, value=None, velocity=None, feel=FLUID,
            delay=0, precision=None, done=None):
    """Move owner's `key` toward target, preserving any motion already under way.

    `value`/`velocity` override the current state; `delay` is in milliseconds.
    Numbers and equal-length tuples are both supported.
    """
    driver = _driver()
    ident = (id(owner), key)
    spring = driver.springs.get(ident)
    if spring is None:
        spring = Spring(owner, key, target if value is None else value, update)
    else:
        spring.update = update
        if value is not None:
            spring.value = [float(v) for v in value] if spring.vector else [float(value)]
    spring.target = [float(v) for v in target] if spring.vector else [float(target)]
    if velocity is not None:
        spring.velocity = [float(v) for v in velocity] if spring.vector else [float(velocity)]
    spring.response, spring.damping = feel
    spring.delay = max(0.0, delay/1000)
    if precision is not None:
        spring.precision = precision
    spring.done = done
    driver.springs[ident] = spring
    driver.watch(owner)
    driver.ensure()
    if value is not None:
        # Show the starting state now; the first frame tick is up to 16 ms away.
        update(spring.current())
    return spring


def get(owner, key):
    return _driver().springs.get((id(owner), key))


def speed(owner, key, default=0.0):
    spring = get(owner, key)
    return spring.speed() if spring else default


def cancel(owner, key):
    _driver().springs.pop((id(owner), key), None)


def settle(owner=None):
    """Snap springs (all, or one owner's) to their destinations immediately."""
    driver = _driver()
    for ident, spring in list(driver.springs.items()):
        if owner is not None and ident[0] != id(owner):
            continue
        driver.springs.pop(ident, None)
        spring.value = list(spring.target)
        spring.velocity = [0.0]*len(spring.value)
        try:
            spring.update(spring.current())
            if spring.done:
                spring.done()
        except RuntimeError:
            pass


# Refresh bounce: a quick anticipation dip, then a spring released upward that
# overshoots its landing and settles. Normalised so the highest point is -1.
_ANTICIPATION_MS, _DIP = 95.0, .17
_RELEASE = (.6, .4)


def _peak(launch):
    lowest, t = 0.0, 0.0
    while t < 1.2:
        lowest = min(lowest, sample(_DIP, -launch, t, *_RELEASE)[0])
        t += .004
    return lowest


def _solve_launch():
    low, high = 0.0, 60.0
    for _ in range(40):
        middle = (low+high)/2
        if _peak(middle) > -1:
            low = middle
        else:
            high = middle
    return (low+high)/2


_LAUNCH = _solve_launch()


def _bounce_settle():
    t, last = 0.0, 0.0
    while t < 4.0:
        x, v = sample(_DIP, -_LAUNCH, t, *_RELEASE)
        if abs(x) > .006 or abs(v) > .06:
            last = t
        t += .008
    return int(_ANTICIPATION_MS+last*1000+8)


BOUNCE_MS = _bounce_settle()


def bounce(elapsed_ms):
    """(displacement, velocity per second) of the unit refresh bounce; -1 is the peak."""
    if elapsed_ms <= 0 or elapsed_ms >= BOUNCE_MS:
        return 0.0, 0.0
    if elapsed_ms < _ANTICIPATION_MS:
        phase = elapsed_ms/_ANTICIPATION_MS
        return _DIP*math.sin(phase*math.pi/2), _DIP*math.pi/2*math.cos(phase*math.pi/2)/(_ANTICIPATION_MS/1000)
    return sample(_DIP, -_LAUNCH, (elapsed_ms-_ANTICIPATION_MS)/1000, *_RELEASE)
