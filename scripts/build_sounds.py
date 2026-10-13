"""Synthesize Neotrix Prism's interface sound set.

Every sound is generated from scratch (no samples): additive glass, kalimba,
wood and felt tones, spectrally shaped air, and one shared synthetic room, so
the whole set sounds like it lives in the same space. Notes come from E-flat
major pentatonic, so any overlap (a wave of plucks under a chime) stays
consonant. Timings follow the motion they accompany (docs/SOUND.md).

Output: 48 kHz stereo 16-bit WAV, loudness-matched per role, plus SOURCE.json.

    python scripts/build_sounds.py [--out assets/sounds] [--sheet sheet.png]

Development only (needs numpy and scipy); the app just plays the WAV files.
"""
import argparse
import json
import wave
import zlib
from pathlib import Path

import numpy as np
from scipy import signal

SR = 48000
ROOT = Path(__file__).resolve().parents[1]
NAMES = {'C': 0, 'Db': 1, 'D': 2, 'Eb': 3, 'E': 4, 'F': 5, 'Gb': 6, 'G': 7, 'Ab': 8, 'A': 9, 'Bb': 10, 'B': 11}

# Partial sets: (frequency ratio, amplitude, decay multiplier).
GLASS = ((1, 1, 1), (2.0, .26, .5), (3.0, .08, .32), (4.16, .04, .2), (5.4, .018, .14))
SOFT_GLASS = ((1, 1, 1), (2.0, .16, .5), (3.0, .04, .3))
KALIMBA = ((1, 1, 1), (2.0, .08, .45), (5.92, .2, .11), (8.86, .05, .06))
WOOD = ((1, 1, 1), (3.93, .32, .2), (9.15, .1, .07))
FELT = ((1, 1, 1), (2, .38, .6), (3, .16, .42), (4, .07, .3), (5, .03, .22))
WARM = ((1, 1, 1), (2, .32, .6), (3, .08, .4))


def hz(name):
    pitch, octave = name[:-1], int(name[-1])
    return 440.0*2**((12*(octave+1)+NAMES[pitch]-69)/12)


def axis(duration):
    return np.arange(int(round(duration*SR)))/SR


def onset(x, attack, release=.04):
    """Soft start (attack) and a click-free end (release) for any buffer."""
    n = min(len(x), max(1, int(attack*SR)))
    x[:n] *= np.sin(np.linspace(0, np.pi/2, n))**2
    m = min(len(x), int(release*SR))
    if m:
        x[-m:] *= np.cos(np.linspace(0, np.pi/2, m))**2
    return x


def tone(freq, duration, partials, decay, attack=.004, rng=None, bend=0.0, bend_time=.04, tremolo=0.0, rate=5.5):
    """Additive tone. `bend` starts the pitch at (1+bend)x and glides home."""
    t = axis(duration)
    glide = 1+bend*np.exp(-t/bend_time) if bend else np.ones_like(t)
    out = np.zeros_like(t)
    for ratio, amp, life in partials:
        f = freq*ratio
        if f >= SR*.42:
            continue
        phase = rng.uniform(0, 2*np.pi) if rng is not None else 0.0
        out += amp*np.sin(2*np.pi*np.cumsum(f*glide)/SR+phase)*np.exp(-t/(decay*life))
    if tremolo:
        out *= 1+tremolo*np.sin(2*np.pi*rate*t)
    return onset(out, attack)


def glass(name, duration, decay, attack=.005, rng=None, partials=GLASS, **kw):
    return tone(hz(name), duration, partials, decay, attack, rng, **kw)


def stereo(mono, position=0.0):
    """Constant-power pan; centre keeps unity gain."""
    angle = (np.clip(position, -1, 1)+1)*np.pi/4
    return np.stack([mono*np.cos(angle), mono*np.sin(angle)], axis=1)*np.sqrt(2)


def balance(x, start, end, curve=1.0):
    """Pan automation across a stereo sound (start/end in -1..1)."""
    p = np.linspace(0, 1, len(x))**curve
    angle = (np.clip(start+(end-start)*p, -1, 1)+1)*np.pi/4
    return x*np.stack([np.cos(angle), np.sin(angle)], axis=1)*np.sqrt(2)


def spectral(x, mask, nperseg=1024):
    """Time-varying filter: multiply the STFT by mask(freqs[:,None], times[None,:])."""
    padded = np.concatenate([x, np.zeros(max(0, 2*nperseg-len(x)))])
    f, tt, z = signal.stft(padded, SR, nperseg=nperseg, noverlap=nperseg*3//4)
    z = z*mask(f[:, None], tt[None, :])
    _, y = signal.istft(z, SR, nperseg=nperseg, noverlap=nperseg*3//4)
    out = np.zeros(len(x))
    out[:min(len(x), len(y))] = y[:len(x)]
    return out


def band(centre, width):
    """Gaussian band on a log-frequency axis; centre(times) in Hz, width in octaves."""
    sigma = width/2.355
    return lambda f, tt: np.exp(-.5*((np.log2(np.maximum(f, 20))-np.log2(centre(tt)))/sigma)**2)


def air(duration, rng, centre, width=1.2, side=1.0):
    """Stereo shaped noise. `side` (scalar or per-sample) sets stereo width."""
    n = int(round(duration*SR))
    mid = spectral(rng.standard_normal(n), band(centre, width))
    sid = spectral(rng.standard_normal(n), band(centre, width))
    side = np.broadcast_to(np.asarray(side, dtype=float), (n,))
    x = np.stack([mid+side*sid, mid-side*sid], axis=1)
    x = x/max(1e-9, np.sqrt(np.mean(x**2))*3)
    return np.stack([onset(x[:, 0].copy(), .001, .02), onset(x[:, 1].copy(), .001, .02)], axis=1)


def swell(t, peak, power=2.0, release=.1):
    """Rises as (t/peak)^power, then releases exponentially."""
    return np.where(t < peak, (np.clip(t, 0, None)/peak)**power, np.exp(-(t-peak)/release))


def whoosh(rng, duration, f0, f1, peak, release, pan0, pan1, width=1.3, power=2.2, side=.55):
    """Air that sweeps f0 -> f1, accelerating into its peak, moving pan0 -> pan1."""
    t = axis(duration)
    x = air(duration, rng, lambda tt: f0*(f1/f0)**(np.clip(tt/peak, 0, 1)**1.3), width, side)
    x *= swell(t, peak, power, release)[:, None]
    return balance(x, pan0, pan1, .6)


def pad(notes, duration, rng, envelope, cutoff=None, detune=(-5, 0, 6)):
    """Wide sustained chord: every note is a few detuned sines, decorrelated per side."""
    t = axis(duration)
    sides = []
    for _ in range(2):
        x = np.zeros_like(t)
        for name, amp in notes:
            for cents in detune:
                f = hz(name)*2**((cents+rng.uniform(-1.5, 1.5))/1200)
                x += amp/len(detune)*(np.sin(2*np.pi*f*t+rng.uniform(0, 6.3))+.12*np.sin(4*np.pi*f*t+rng.uniform(0, 6.3)))
        x *= envelope
        if cutoff is not None:
            x = spectral(x, lambda f, tt: 1/(1+(f/cutoff(tt))**4))
        sides.append(onset(x, .001, .08))
    return np.stack(sides, axis=1)


def twinkle(duration, rng, count=7, centre=7200):
    """A dusting of tiny high glints (shaped noise gated by short bumps)."""
    t = axis(duration)
    gate = np.zeros_like(t)
    for at in rng.uniform(.02, duration*.6, count):
        gate += np.exp(-.5*((t-at)/.006)**2)*rng.uniform(.4, 1)
    x = air(duration, rng, lambda tt: centre+0*tt, .9, .8)
    return x*gate[:, None]


class Mix:
    def __init__(self, duration):
        self.buf = np.zeros((int(round(duration*SR)), 2))

    def add(self, sound, at=0.0, gain=1.0):
        if sound.ndim == 1:
            sound = stereo(sound)
        i = int(round(at*SR))
        j = min(len(self.buf), i+len(sound))
        if j > i:
            piece = gain*sound[:j-i]
            if j-i < len(sound):
                piece = np.stack([onset(piece[:, 0].copy(), 0, .05), onset(piece[:, 1].copy(), 0, .05)], axis=1)
            self.buf[i:j] += piece
        return self


# ---------------------------------------------------------------- the room

def room_ir(rng, rt60=1.15, length=1.7, predelay=.011):
    """Shared synthetic space: early reflections plus a diffuse tail whose
    highs decay faster than its lows, like a soft, well-furnished hall."""
    n = int(length*SR)
    t = np.arange(n)/SR
    ir = np.zeros((n, 2))
    for ch in range(2):
        def decay(f, tt):
            rt = rt60*np.clip(1.15-.17*np.log2(np.maximum(f, 150)/150), .22, 1.15)
            return np.exp(-6.91*tt/rt)
        x = spectral(rng.standard_normal(n), decay, 512)
        x *= np.clip(t/.03, 0, 1)**1.5
        ir[:, ch] = x/np.sqrt(np.sum(x**2))
    for k, (delay, gain) in enumerate(((.0063, .2), (.0091, .18), (.0137, .15), (.0181, .12), (.0239, .1), (.0297, .08), (.0373, .06))):
        ir[int(delay*SR), k % 2] += gain
        ir[int((delay+.0011)*SR), (k+1) % 2] += gain*.5
    ir = signal.sosfilt(signal.butter(2, 7500, 'low', fs=SR, output='sos'), ir, axis=0)
    return np.concatenate([np.zeros((int(predelay*SR), 2)), ir])


ROOM = None


def reverb(x, wet, dry=1.0, send_highpass=None):
    """Shared room. `send_highpass` (Hz) keeps bass out of the reverb so a
    heavy low end stays tight instead of turning into rumble."""
    send = x if send_highpass is None else signal.sosfilt(signal.butter(2, send_highpass, 'high', fs=SR, output='sos'), x, axis=0)
    left, right = send[:, 0], send[:, 1]
    wl = signal.fftconvolve(.75*left+.25*right, ROOM[:, 0])
    wr = signal.fftconvolve(.25*left+.75*right, ROOM[:, 1])
    out = np.zeros((max(len(wl), len(x)), 2))
    out[:len(x)] += dry*x
    out[:len(wl), 0] += wet*wl
    out[:len(wr), 1] += wet*wr
    return out


# ---------------------------------------------------------------- mastering

K1 = ([1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, .73248077421585])
K2 = ([1.0, -2.0, 1.0], [1.0, -1.99004745483398, .99007225036621])


def loudness(x, window=.15):
    """Peak perceived loudness, LUFS: ITU-R BS.1770 K-weighting over a short
    window. 150 ms (not the 400 ms momentary window) is close to the ear's
    integration time, so brief clicks are not under-measured against swells."""
    y = signal.lfilter(*K2, signal.lfilter(*K1, x, axis=0), axis=0)
    w = int(window*SR)
    power = np.concatenate([np.sum(y**2, axis=1), np.zeros(w)])
    c = np.concatenate([[0.0], np.cumsum(power)])
    windows = (c[w:]-c[:-w])/w
    return -.691+10*np.log10(max(windows[::int(.01*SR)].max(), 1e-12))


def master(x, target, ceiling=-3.0, floor=-50.0):
    x = signal.sosfiltfilt(signal.butter(2, 32, 'high', fs=SR, output='sos'), x, axis=0)
    x = signal.sosfilt(signal.butter(2, 13000, 'low', fs=SR, output='sos'), x, axis=0)
    x = x*10**((target-loudness(x))/20)
    peak = 20*np.log10(np.max(np.abs(x))+1e-12)
    if peak > ceiling:
        x *= 10**((ceiling-peak)/20)
    level = np.max(np.abs(x), axis=1)
    # Tails end 50 dB under the sound's own peak (and never below -66 dBFS).
    alive = np.nonzero(level > max(np.max(level)*10**(floor/20), 10**(-66/20)))[0]
    end = min(len(x), alive[-1]+int(.02*SR)) if len(alive) else len(x)
    x = x[:end].copy()
    fade = min(len(x), int(.04*SR))
    x[-fade:] *= (np.linspace(1, 0, fade)**2)[:, None]
    guard = min(len(x), 32)
    x[:guard] *= np.linspace(0, 1, guard)[:, None]
    return x


def write(path, x, rng):
    dither = (rng.random(x.shape)-rng.random(x.shape))/32768
    data = np.clip(np.round((x+dither)*32767), -32768, 32767).astype('<i2')
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(SR)
        out.writeframes(data.tobytes())


# ---------------------------------------------------------------- the set
# Each builder returns a stereo float array. Comments give the motion it follows.

def intro(rng):
    """App opens: first light rises (dawn spring 1.1 s), nav items pop in at
    150+70i ms, the orb lands last at ~0.7 s."""
    t = axis(3.2)
    env = (1-np.exp(-t/.4))*np.where(t < 1.3, 1, np.exp(-(t-1.3)/.6))
    mix = Mix(3.2).add(pad((('Eb3', .5), ('Bb3', .42), ('Eb4', .36), ('G4', .24), ('Bb4', .16)), 3.2, rng, env,
                           cutoff=lambda tt: 450+3200*np.clip(tt/1.0, 0, 1)**1.4)*.5)
    for i, name in enumerate(('Eb5', 'G5', 'Bb5', 'Eb6')):
        mix.add(stereo(glass(name, 1.3, .42, .006, rng)*.3, -.5+.07*i), .22+.07*i)
    for name, amp, pos in (('Bb4', .34, -.1), ('Eb5', .3, .08), ('G5', .22, .15)):
        mix.add(stereo(glass(name, 1.8, .8, .014, rng)*amp, pos), .7)
    mix.add(stereo(tone(hz('Eb3'), 1.5, FELT, .6, .012, rng)*.3), .7)
    mix.add(stereo(tone(hz('Eb2'), 1.2, WARM, .35, .02, rng)*.32), .7)
    return reverb(mix.buf, .5)


def nav_whoosh(rng, rising):
    """Page change: the old page accelerates away within 320 ms while colour
    floods out from the sidebar (left) across the workspace."""
    f0, f1 = (650, 2300) if rising else (2300, 650)
    mix = Mix(.8).add(whoosh(rng, .8, f0, f1, .22, .1, -.45, .12))
    mix.add(whoosh(rng, .8, 220, 420, .2, .12, -.3, 0, width=1.0, side=.3)*.35)
    return reverb(mix.buf, .22)


def nav_chime(rng, first, second):
    """Each page has its own interval, rolled as the new page cascades in."""
    mix = Mix(1.5)
    mix.add(stereo(glass(first, 1.4, .5, .005, rng)*.5, -.18))
    mix.add(stereo(glass(second, 1.5, .58, .005, rng)*.42, .12), .06)
    return reverb(mix.buf, .38)


def open_card(rng, position):
    """Shared-element zoom (860 ms): air rises from the card to centre stage,
    peaks as the artwork flies through (~0.42 s), the colour field lands with a
    soft whomp and the next level blooms as a strummed chord."""
    mix = Mix(2.0)
    mix.add(whoosh(rng, .75, 380, 2900, .42, .065, position, 0, width=1.25, power=2.4)*.9)
    burst = air(.14, rng, lambda tt: 4300+0*tt, 1.0, .8)*swell(axis(.14), .02, 1.0, .03)[:, None]
    mix.add(burst*.3, .4)
    mix.add(stereo(tone(77.8, .9, WARM, .2, .012, bend=.8, bend_time=.05)*.55), .3)
    for k, (name, amp) in enumerate((('Eb4', .3), ('Bb4', .34), ('Eb5', .38), ('G5', .28), ('Bb5', .18))):
        mix.add(stereo(glass(name, 1.4, .6, .035, rng, tremolo=.08)*amp, -.3+.15*k), .36+.014*k)
    for name, at, pos in (('Eb6', .48, -.4), ('G6', .53, .35), ('Bb6', .6, .1)):
        mix.add(stereo(glass(name, .6, .18, .004, rng, SOFT_GLASS)*.09, pos), at)
    return reverb(mix.buf, .42)


def back(rng):
    """Up a level: a quick falling exit, then content settles down from above."""
    mix = Mix(1.3)
    mix.add(whoosh(rng, .6, 2500, 620, .08, .12, .15, -.35, power=1.3)*.8)
    mix.add(stereo(glass('Bb4', 1.0, .36, .008, rng)*.36, -.2), .09)
    mix.add(stereo(tone(hz('Eb4'), 1.0, FELT, .38, .01, rng)*.34, -.25), .16)
    return reverb(mix.buf, .32)


def refresh(rng):
    """Shockwave from the orb: a deep boom with the core flash (0.42 s), a ring
    of air that widens in stereo and darkens as it travels (1650 px/s), and the
    backdrop's light swelling (peak ~0.25 s, ebbing over ~1.5 s), with a low
    fifth under the swell for a full, cinematic body."""
    t = axis(2.8)
    mix = Mix(2.8)
    # The boom falls into E-flat 2 with a sub octave beneath; its upper harmonics
    # carry the weight on small speakers that cannot reproduce the fundamental.
    boom = ((1, 1, 1), (2, .4, .55), (3, .16, .36), (4, .06, .25))
    mix.add(stereo(tone(77.8, 1.5, boom, .42, .008, bend=.6, bend_time=.04)*.8))
    mix.add(stereo(tone(38.9, 1.6, ((1, 1, 1), (2, .3, .5)), .55, .02, bend=.35, bend_time=.06)*.26))
    thud = air(.35, rng, lambda tt: 120+0*tt, 1.6, .2)*swell(axis(.35), .006, 1.0, .07)[:, None]
    mix.add(thud*.45)
    mix.add(stereo(tone(hz('Eb3'), 1.3, FELT, .55, .01, rng)*.34), .005)
    mix.add(stereo(tone(hz('Eb2'), 1.6, FELT, .6, .015, rng)*.24), .005)
    mix.add(stereo(glass('Eb5', .5, .1, .003, rng, SOFT_GLASS)*.16), .03)
    ring = air(1.4, rng, lambda tt: 2600*(1100/2600)**np.clip(tt/.8, 0, 1), 2.6, np.clip(axis(1.4)/.55, 0, 1))
    mix.add(ring*swell(axis(1.4), .13, 1.6, .32)[:, None]*.55)
    for name, pos in (('Eb6', -.3), ('Bb6', .3)):
        mix.add(stereo(glass(name, 1.2, .5, .15, rng, SOFT_GLASS, tremolo=.2)*.08, pos), .05)
    swell_pad = (('Eb2', .3), ('Bb2', .3), ('Eb3', .36), ('Eb4', .5), ('Bb4', .4))
    mix.add(pad(swell_pad, 2.8, rng, swell(t, .3, 2.0, .75))*.24)
    return reverb(mix.buf, .53, send_highpass=140)


def wave_note(rng, name, position):
    """One artwork jumping as the wave reaches it: a kalimba pluck, panned
    where the artwork sits (left is low, right is high)."""
    mix = Mix(1.1)
    mix.add(stereo(tone(hz(name), 1.0, KALIMBA, .34, .003, rng)*.55, position))
    mix.add(stereo(tone(hz(name)*2**(2.5/1200), 1.0, KALIMBA, .3, .004, rng)*.1, -position*.6), .004)
    return reverb(mix.buf, .36)


def done(rng):
    """Refresh finished: the orb rolls back to Refresh with a soft settle, a
    breath out over a warm felt fifth. Low, brief and bell-free, so it can close
    every refresh without sounding like a notification."""
    mix = Mix(1.3)
    mix.add(whoosh(rng, .55, 900, 380, .06, .16, 0, 0, width=1.2, power=1.2, side=.4)*.35)
    mix.add(stereo(tone(hz('Eb4'), 1.2, FELT, .32, .022, rng)*.34, -.08), .02)
    mix.add(stereo(tone(hz('Bb4'), 1.2, FELT, .28, .022, rng)*.26, .08), .045)
    mix.add(stereo(tone(hz('Eb3'), 1.0, WARM, .25, .03, rng)*.18), .02)
    x = reverb(mix.buf, .3)
    return signal.sosfilt(signal.butter(2, 2200, 'low', fs=SR, output='sos'), x, axis=0)


def cancel(rng):
    mix = Mix(1.0)
    mix.add(stereo(tone(hz('Eb5'), .9, WOOD, .22, .004, rng)*.4, .05))
    mix.add(stereo(tone(hz('Bb4'), .9, WOOD, .28, .004, rng)*.4, -.05), .075)
    x = reverb(mix.buf, .3)
    return signal.sosfilt(signal.butter(2, 3000, 'low', fs=SR, output='sos'), x, axis=0)


def success(rng):
    mix = Mix(1.6)
    for k, name in enumerate(('G5', 'Bb5', 'Eb6')):
        mix.add(stereo(glass(name, 1.4, .5+.08*k, .005, rng)*(.4-.04*k), -.2+.2*k), .045*k)
    mix.add(twinkle(.5, rng, 6)*.05, .1)
    return reverb(mix.buf, .42)


def alert(rng):
    """Errors stay calm: two soft wooden notes stepping down, no buzz."""
    mix = Mix(1.1)
    mix.add(stereo(tone(hz('C5'), 1.0, WOOD, .3, .006, rng)*.4+tone(hz('C5'), 1.0, FELT, .35, .01, rng)*.15, .05))
    mix.add(stereo(tone(hz('G4'), 1.0, WOOD, .36, .006, rng)*.4+tone(hz('G4'), 1.0, FELT, .4, .01, rng)*.15, -.05), .09)
    x = reverb(mix.buf, .32)
    return signal.sosfilt(signal.butter(2, 2600, 'low', fs=SR, output='sos'), x, axis=0)


def favorite_add(rng):
    mix = Mix(1.3)
    for k, (name, amp) in enumerate((('Bb5', .42), ('Eb6', .36), ('G6', .3), ('Bb6', .22))):
        mix.add(stereo(glass(name, 1.0, .35, .004, rng)*amp, -.3+.2*k), .035*k)
    mix.add(twinkle(.5, rng, 8)*.06, .05)
    return reverb(mix.buf, .45)


def favorite_remove(rng):
    mix = Mix(1.0)
    mix.add(stereo(glass('G5', .9, .25, .006, rng)*.4, .1))
    mix.add(stereo(glass('Eb5', 1.0, .3, .006, rng)*.4, -.1), .06)
    x = reverb(mix.buf, .3)
    return signal.sosfilt(signal.butter(2, 3500, 'low', fs=SR, output='sos'), x, axis=0)


def copy(rng):
    mix = Mix(.6)
    mix.add(stereo(glass('F6', .4, .07, .003, rng, SOFT_GLASS)*.4))
    zip_ = air(.08, rng, lambda tt: 2000*(6000/2000)**np.clip(tt/.06, 0, 1), 1.0, .5)*swell(axis(.08), .05, 1.5, .01)[:, None]
    mix.add(zip_*.15)
    return reverb(mix.buf, .2)


def toggle(rng, on):
    name, bend = ('C6', -.03) if on else ('G5', .03)
    mix = Mix(.45).add(stereo(tone(hz(name), .4, WOOD, .05, .002, rng, bend=bend, bend_time=.02)*.45))
    mix.add(stereo(glass(name, .4, .06, .004, rng, SOFT_GLASS)*.12), .004)
    return reverb(mix.buf, .2)


def menu(rng):
    mix = Mix(.5)
    pop = tone(640, .3, ((1, 1, 1), (2, .1, .5)), .045, .002, bend=-.34, bend_time=.015)
    mix.add(stereo(pop*.4))
    mix.add(stereo(glass('G6', .3, .05, .003, rng, SOFT_GLASS)*.1), .01)
    return reverb(mix.buf, .22)


def dialog(rng):
    t = axis(1.0)
    mix = Mix(1.0).add(pad((('Eb5', .5), ('Bb5', .35)), 1.0, rng, swell(t, .09, 1.5, .25))*.35)
    mix.add(air(1.0, rng, lambda tt: 1400+0*tt, 1.5, .6)*swell(t, .1, 1.5, .2)[:, None]*.12)
    return reverb(mix.buf, .32)


def launch(rng):
    """Opening a file in its application: a shorter rise and a bright arpeggio."""
    mix = Mix(1.6)
    mix.add(whoosh(rng, .6, 500, 3000, .32, .07, -.1, .1, power=2.0)*.8)
    for k, name in enumerate(('Eb5', 'Bb5', 'Eb6')):
        mix.add(stereo(glass(name, 1.2, .5, .005, rng)*(.36-.04*k), -.2+.2*k), .18+.05*k)
    mix.add(stereo(tone(77.8, .7, WARM, .16, .012, bend=.6, bend_time=.04)*.3), .3)
    return reverb(mix.buf, .4)


def hover(rng, name, position):
    """Pointer over a card: a whisper of glass, pitched and panned by where the card sits."""
    x = stereo(glass(name, .45, .14, .006, rng, SOFT_GLASS)*.5, position)
    x = reverb(x, .3)
    return signal.sosfilt(signal.butter(2, 6000, 'low', fs=SR, output='sos'), x, axis=0)


def hover_soft(rng):
    mix = Mix(.35)
    tick = air(.05, rng, lambda tt: 3000+0*tt, 1.2, .3)*swell(axis(.05), .002, 1.0, .008)[:, None]
    mix.add(tick*.5)
    mix.add(stereo(glass('G6', .2, .03, .002, rng, SOFT_GLASS)*.25))
    return reverb(mix.buf, .15)


def press(rng, cents):
    """Tactile press: a short warm wooden tock with a felt mallet."""
    f = hz('G4')*2**(cents/1200)
    mix = Mix(.45).add(stereo(tone(f, .4, WOOD, .06, .0015, rng)*.5+tone(f, .4, FELT, .05, .002, rng)*.12))
    mallet = air(.012, rng, lambda tt: 2600+0*tt, 1.6, .2)*swell(axis(.012), .001, 1.0, .002)[:, None]
    mix.add(mallet*.25)
    return reverb(mix.buf, .18)


def press_card(rng):
    mix = Mix(.5).add(stereo(tone(hz('Eb4'), .45, WOOD, .09, .002, rng)*.5+tone(hz('Eb4'), .45, FELT, .08, .003, rng)*.2))
    mix.add(stereo(tone(hz('Eb3'), .4, WARM, .07, .004, rng)*.2))
    return reverb(mix.buf, .2)


def select(rng):
    return reverb(stereo(glass('Eb6', .35, .06, .004, rng, SOFT_GLASS)*.4), .2)


def shuffle(rng):
    """Filtered results reflow: a handful of tiny glass ticks."""
    mix = Mix(.6)
    names = ('Eb6', 'F6', 'G6', 'Bb6', 'C7')
    for at in sorted(rng.uniform(0, .16, 6)):
        name = names[rng.integers(len(names))]
        mix.add(stereo(glass(name, .25, .03, .002, rng, SOFT_GLASS)*rng.uniform(.3, .6), rng.uniform(-.5, .5)), at)
    return reverb(mix.buf, .25)


def sidebar(rng, opening):
    """The sidebar slides on its width spring (settling ~0.45 s, landing ~0.22 s).
    A warm two-voice glide, a fifth apart, slides up as it opens (down as it
    closes) like a felt-lined drawer; a whisper of air rides along; a soft
    detent lands with the panel. Panned with the sidebar's edge as it moves."""
    mix = Mix(1.0)
    notes = (('Eb4', 'Bb4') if opening else ('Bb3', 'F4'))
    start = .75 if opening else 1.33
    body = np.zeros(int(.9*SR))
    for name, amp in zip(notes, (.32, .24)):
        body += tone(hz(name), .9, WARM, .22, .03, rng, bend=start-1, bend_time=.07)*amp
    pan0, pan1 = (-.62, -.22) if opening else (-.22, -.62)
    mix.add(balance(stereo(body), pan0, pan1, .5))
    f0, f1 = (600, 1400) if opening else (1400, 600)
    mix.add(whoosh(rng, .45, f0, f1, .1, .1, pan0, pan1, width=1.0, power=1.4, side=.4)*.18)
    landing = .22 if opening else .2
    tick = 'Bb4' if opening else 'Eb4'
    mix.add(stereo(tone(hz(tick), .4, FELT, .06, .003, rng)*.13, pan1), landing)
    mix.add(stereo(glass('Eb6' if opening else 'Bb5', .4, .05, .003, rng, SOFT_GLASS)*.05, pan1), landing)
    x = reverb(mix.buf, .3)
    return signal.sosfilt(signal.butter(2, 2600, 'low', fs=SR, output='sos'), x, axis=0)


WAVE_NOTES = ('Bb4', 'C5', 'Eb5', 'F5', 'G5', 'Bb5', 'C6')
HOVER_NOTES = ('Eb5', 'F5', 'G5', 'Bb5', 'C6')

# name: (builder, target loudness LUFS, role)
SET = {
    'intro': (intro, -24, 'App opening, choreographed with the first-light intro'),
    'nav-whoosh-down': (lambda r: nav_whoosh(r, True), -29, 'Page change toward a later page'),
    'nav-whoosh-up': (lambda r: nav_whoosh(r, False), -29, 'Page change toward an earlier page'),
    'nav-projects': (lambda r: nav_chime(r, 'Eb5', 'Bb5'), -26, 'Projects page arrives'),
    'nav-favorites': (lambda r: nav_chime(r, 'G5', 'Eb6'), -26, 'Favorites page arrives'),
    'nav-activity': (lambda r: nav_chime(r, 'C5', 'G5'), -26, 'Activity page arrives'),
    'nav-settings': (lambda r: nav_chime(r, 'Bb4', 'F5'), -26, 'Settings page arrives'),
    'open-left': (lambda r: open_card(r, -.6), -22, 'Card zoom from the left'),
    'open-center': (lambda r: open_card(r, 0), -22, 'Card zoom from the centre'),
    'open-right': (lambda r: open_card(r, .6), -22, 'Card zoom from the right'),
    'back': (back, -26, 'Back up a level'),
    'refresh': (refresh, -21, 'Refresh shockwave from the orb'),
    **{f'wave-{i}': (lambda r, n=n, i=i: wave_note(r, n, -.7+1.4*i/6), -28, f'Artwork jump on the wave, {n}')
       for i, n in enumerate(WAVE_NOTES)},
    'done': (done, -31, 'Refresh finished: a soft low settle'),
    'cancel': (cancel, -27, 'Task cancelled'),
    'success': (success, -24, 'Saved or applied'),
    'alert': (alert, -25, 'Something needs attention'),
    'favorite-add': (favorite_add, -25, 'Added to favorites'),
    'favorite-remove': (favorite_remove, -28, 'Removed from favorites'),
    'copy': (copy, -28, 'Copied to clipboard'),
    'toggle-on': (lambda r: toggle(r, True), -29, 'Switch on'),
    'toggle-off': (lambda r: toggle(r, False), -30, 'Switch off'),
    'menu': (menu, -30, 'Menu or list opens'),
    'dialog': (dialog, -29, 'Dialog appears'),
    'launch': (launch, -24, 'File opens in its application'),
    **{f'hover-{i}': (lambda r, n=n, i=i: hover(r, n, -.6+1.2*i/4), -35, f'Card hover, {n}')
       for i, n in enumerate(HOVER_NOTES)},
    'hover-soft': (hover_soft, -39, 'Row and button hover'),
    **{f'press-{i}': (lambda r, c=c: press(r, c), -29, 'Button press') for i, c in enumerate((0, 22, -18))},
    'press-card': (press_card, -28, 'Card press'),
    'select': (select, -31, 'Row selected'),
    'shuffle': (shuffle, -30, 'Search results reflow'),
    'sidebar-open': (lambda r: sidebar(r, True), -29, 'Sidebar expands'),
    'sidebar-close': (lambda r: sidebar(r, False), -30, 'Sidebar collapses'),
}


def contact_sheet(rendered, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows = len(rendered)
    fig, axes = plt.subplots(rows, 2, figsize=(14, rows*1.05), gridspec_kw={'width_ratios': [1, 2.2]})
    for (name, x), (wave_ax, spec_ax) in zip(rendered.items(), axes):
        t = np.arange(len(x))/SR
        wave_ax.plot(t, x[:, 0], lw=.4, color='#7fb3ff')
        wave_ax.plot(t, x[:, 1], lw=.4, color='#ff9ad5', alpha=.7)
        wave_ax.set_ylim(-.75, .75)
        wave_ax.set_xlim(0, 3.2)
        wave_ax.set_ylabel(name, rotation=0, ha='right', va='center', fontsize=8)
        wave_ax.tick_params(labelsize=6)
        f, tt, s = signal.spectrogram(x.mean(axis=1), SR, nperseg=1024, noverlap=768)
        spec_ax.pcolormesh(tt, f, 10*np.log10(s+1e-12), vmin=-130, vmax=-50, shading='auto', cmap='magma')
        spec_ax.set_yscale('symlog', linthresh=200)
        spec_ax.set_ylim(40, 16000)
        spec_ax.set_xlim(0, 3.2)
        spec_ax.tick_params(labelsize=6)
    fig.tight_layout()
    fig.savefig(path, dpi=70)


def main():
    global ROOM
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT/'assets'/'sounds')
    parser.add_argument('--sheet', type=Path)
    parser.add_argument('--only', nargs='*')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    ROOM = room_ir(np.random.default_rng(2026))
    rendered, records = {}, []
    for name, (build, target, role) in SET.items():
        if args.only and name not in args.only:
            continue
        rng = np.random.default_rng(zlib.crc32(name.encode()))
        x = master(build(rng), target)
        write(args.out/f'{name}.wav', x, rng)
        rendered[name] = x
        peak = 20*np.log10(np.max(np.abs(x))+1e-12)
        records.append({'name': name, 'file': f'{name}.wav', 'role': role, 'seconds': round(len(x)/SR, 3),
                        'loudness_lufs': round(loudness(x), 1), 'peak_dbfs': round(peak, 1)})
        print(f'{name:18} {len(x)/SR:5.2f}s  {loudness(x):6.1f} LUFS  peak {peak:6.1f} dBFS')
    if not args.only:
        source = {'generator': 'scripts/build_sounds.py (additive synthesis, shaped noise, synthetic room; no samples)',
                  'format': '48 kHz stereo 16-bit PCM WAV', 'key': 'E-flat major pentatonic',
                  'loudness': 'maximum loudness over 150 ms windows, ITU-R BS.1770 K-weighting', 'sounds': records}
        (args.out/'SOURCE.json').write_text(json.dumps(source, indent=2), encoding='utf-8')
    if args.sheet:
        contact_sheet(rendered, args.sheet)
    total = sum(len(x) for x in rendered.values())*4
    print(f'{len(rendered)} sounds, {total/1048576:.1f} MB')


if __name__ == '__main__':
    main()
