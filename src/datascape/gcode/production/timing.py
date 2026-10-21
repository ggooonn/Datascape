"""Offline Cartesian junction-deviation model; never a controller time guarantee.

Uses projected axis limits, junction geometry, reverse braking and forward
acceleration constraints. Assumes adequate full lookahead and uninterrupted
streaming; excludes finite planner/serial/step quantization and brush dynamics.
"""
from collections import Counter
from math import sqrt, dist
from ..estimation import rest_to_rest_seconds

CATEGORIES = ('drawing', 'paper_engagement', 'non_drawing_travel',
              'station_transfer', 'station_handling')
PAPER_FEEDS = {'approach':'paper_approach_mm_min', 'initial_contact':'paper_contact_mm_min',
               'pressure_variation':'paper_contact_mm_min', 'release':'paper_release_mm_min',
               'paper_release_clearance':'paper_release_mm_min', 'draw':'draw_mm_min'}


def prepare_timing(commands, profile):
    """Cache unchanged 3D geometry for focused feed-only scenario comparisons."""
    pos = tuple(profile.data['machine']['start_work_xyz']); blocks = []
    for c in commands:
        if c.kind == 'move':
            length = dist(pos, c.xyz)
            if length > 1e-12:
                unit = tuple((q-p)/length for p,q in zip(pos,c.xyz))
                blocks.append((length, unit, c.feed_mm_min, c.time_category or 'non_drawing_travel',
                               c.action, c.travel_state, c.travel_phase))
            pos = c.xyz
        elif c.kind in ('dwell','pause'):
            blocks.append((0., (), c.seconds or 0., c.time_category or 'station_handling', c.kind, '', ''))
    return blocks


def requested_feed(block, motion):
    _, _, original, _, action, state, phase = block
    if action in PAPER_FEEDS: return motion[PAPER_FEEDS[action]]
    if action == 'travel':
        feed = motion[state+'_mm_min']
        if state == 'wet_loaded' and phase in ('departure','arrival'):
            feed = min(feed, motion['wet_'+phase+'_mm_min'])
        return feed
    if action in ('lift','retract','paper_hover','park'): return motion['z_travel_mm_min']
    # Station feeds remain independently calibrated, never paper-contact speeds.
    return original


def estimate_prepared(blocks, machine, motion=None):
    nominal = Counter({k:0. for k in CATEGORIES}); modeled = nominal.copy(); stopped = 0.
    lengths=[]; units=[]; speeds=[]; accels=[]; categories=[]
    rates = machine['axis_max_rate_mm_min']; axes = machine['axis_acceleration_mm_s2']
    jd = machine['junction_deviation_mm']
    def flush():
        nonlocal stopped
        n = len(lengths)
        if not n: return
        # Squared boundary speeds in mm/s, bounded by both neighboring feeds.
        v2 = [0.]*(n+1)
        for i in range(1,n):
            cosine = max(-1.,min(1.,sum(a*b for a,b in zip(units[i-1],units[i]))))
            cap = min(speeds[i-1],speeds[i])**2
            if cosine < -0.999999: cap = 0.
            elif cosine <= 0.999999:
                delta = tuple(b-a for a,b in zip(units[i-1],units[i]))
                norm = sqrt(sum(x*x for x in delta))
                ja = min(a*norm/abs(x) for a,x in zip(axes,delta) if x)
                half = sqrt(.5*(1+cosine))
                cap = min(cap, ja*jd*half/(1-half))
            v2[i] = cap
        for i in range(n-1,-1,-1):
            v2[i] = min(v2[i], v2[i+1]+2*accels[i]*lengths[i])
        for i in range(n):
            v2[i+1] = min(v2[i+1], v2[i]+2*accels[i]*lengths[i])
        for i,(length,speed,accel,category) in enumerate(zip(lengths,speeds,accels,categories)):
            entry,exit = sqrt(v2[i]),sqrt(v2[i+1])
            peak = min(speed,sqrt(max(0.,accel*length+(v2[i]+v2[i+1])/2)))
            ramp_distance = max(0.,(2*peak*peak-v2[i]-v2[i+1])/(2*accel))
            seconds = (2*peak-entry-exit)/accel + max(0.,length-ramp_distance)/peak
            modeled[category] += seconds
            stopped += rest_to_rest_seconds(length,speed*60,accel)
        lengths.clear(); units.clear(); speeds.clear(); accels.clear(); categories.clear()
    for block in blocks:
        length,unit,feed,category,action,_,_ = block
        if not length:
            flush(); nominal[category] += feed; modeled[category] += feed; stopped += feed
            continue
        if motion is not None: feed = requested_feed(block,motion)
        feed = min(feed,*(r/abs(u) for r,u in zip(rates,unit) if u))
        if motion is not None and unit[2]:
            cap = motion['pressure_z_mm_min'] if action in ('draw','pressure_variation') else motion['z_travel_mm_min']
            feed = min(feed,cap/abs(unit[2]))
        acceleration = min(a/abs(u) for a,u in zip(axes,unit) if u)
        nominal[category] += length/feed*60
        lengths.append(length); units.append(unit); speeds.append(feed/60)
        accels.append(acceleration); categories.append(category)
    flush()
    return {'commanded_feed_seconds_by_category':dict(nominal),
            'acceleration_sensitive_seconds_by_category':dict(modeled),
            'commanded_feed_seconds':sum(nominal.values()),
            'acceleration_sensitive_seconds':sum(modeled.values()),
            'stop_each_segment_seconds':stopped,
            'model':'Cartesian projected-axis / junction deviation / full lookahead',
            'verified_physical_time':False,
            'limitations':['adequate full lookahead and continuous streaming assumed',
                           'finite buffer, step quantization and controller/serial overhead omitted',
                           'brush recovery and physical dynamic approval not inferred']}


def estimate_commands(commands, profile):
    return estimate_prepared(prepare_timing(commands,profile),profile.data['machine'])
