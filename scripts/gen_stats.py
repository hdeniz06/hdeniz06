# -*- coding: utf-8 -*-
"""GitHub istatistik kartı üretir -> stats.svg"""
import os, json, base64, datetime as dt, urllib.request

FD = os.path.join(os.path.dirname(__file__), 'fonts')
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
_c = {}
def load(n):
    if n not in _c:
        f = TTFont(os.path.join(FD, n))
        _c[n] = (f, f.getGlyphSet(), f['cmap'].getBestCmap(), f['head'].unitsPerEm, f['hmtx'])
    return _c[n]
def measure(t, fo, sz, tr=0.0):
    f, gs, cm, u, hm = load(fo); s = sz/u; a = 0
    for ch in t: a += hm[cm.get(ord(ch)) or cm.get(32)][0]*s + tr
    return a - (tr if t else 0)
def tp(t, fo, sz, x, y, fill, tr=0.0, anchor='start'):
    f, gs, cm, u, hm = load(fo); s = sz/u
    w = measure(t, fo, sz, tr)
    if anchor == 'middle': x -= w/2
    elif anchor == 'end': x -= w
    d = []; a = 0
    for ch in t:
        gn = cm.get(ord(ch)) or cm.get(32)
        p = SVGPathPen(gs); gs[gn].draw(TransformPen(p, (s, 0, 0, -s, x+a, y)))
        cmds = p.getCommands()
        if cmds: d.append(cmds)
        a += hm[gn][0]*s + tr
    return '<path d="%s" fill="%s"/>' % (" ".join(d), fill)

DSB='InterDisplay-SemiBold.ttf'; MED='Inter-Medium.ttf'; REG='Inter-Regular.ttf'
BG='#09090B'; LINE='#1E1E24'; WHITE='#F7F7F9'; MUTE='#8B8B94'; DIM='#5C5C66'

Q = """
query($login:String!, $from:DateTime!, $to:DateTime!) {
  user(login:$login) {
    contributionsCollection(from:$from, to:$to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}"""

def gql(token, variables):
    req = urllib.request.Request(
        'https://api.github.com/graphql',
        data=json.dumps({'query': Q, 'variables': variables}).encode(),
        headers={'Authorization': 'bearer ' + token,
                 'Content-Type': 'application/json',
                 'User-Agent': 'profile-stats'})
    return json.loads(urllib.request.urlopen(req).read())

def fetch(user, token, years=4):
    days = {}
    today = dt.date.today()
    for i in range(years):
        to = today - dt.timedelta(days=365*i)
        fr = to - dt.timedelta(days=365)
        d = gql(token, {'login': user,
                        'from': fr.isoformat()+'T00:00:00Z',
                        'to': to.isoformat()+'T23:59:59Z'})
        cal = d['data']['user']['contributionsCollection']['contributionCalendar']
        for w in cal['weeks']:
            for day in w['contributionDays']:
                days[day['date']] = day['contributionCount']
    return days

def streaks(days):
    ds = sorted(days)
    cur = best = 0
    today = dt.date.today().isoformat()
    run = 0
    for d in ds:
        if days[d] > 0:
            run += 1; best = max(best, run)
        else:
            if d != today: run = 0
    # current streak: walk back from today
    cur = 0; d = dt.date.today()
    if days.get(d.isoformat(), 0) == 0: d -= dt.timedelta(days=1)
    while days.get(d.isoformat(), 0) > 0:
        cur += 1; d -= dt.timedelta(days=1)
    return cur, best

RAMP = ['#16161B', '#3A2A4E', '#7B3A9E', '#C9416F', '#FF7A3D']

def render(days, total, cur, best, out='stats.svg'):
    W, H = 1000, 352
    X, R = 66, 934
    o = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" role="img" aria-label="GitHub activity">' % (W, H, W, H)]
    o.append('<defs><clipPath id="c"><rect width="%d" height="%d" rx="28"/></clipPath></defs>' % (W, H))
    o.append('<g clip-path="url(#c)"><rect width="%d" height="%d" fill="%s"/>' % (W, H, BG))
    o.append(tp('GITHUB ACTIVITY', MED, 10.5, X, 48, DIM, tr=2.4))
    o.append(tp(dt.date.today().strftime('Updated %d %b %Y').upper(), MED, 10.5, R, 48, DIM, tr=2.4, anchor='end'))

    cells = [('{:,}'.format(total), 'TOTAL CONTRIBUTIONS'),
             (str(cur), 'CURRENT STREAK'),
             (str(best), 'LONGEST STREAK')]
    gw = (R-X)/3
    for i, (n, l) in enumerate(cells):
        cx = X + gw*i + gw/2
        o.append(tp(n, DSB, 34, cx, 108, WHITE, tr=-1.0, anchor='middle'))
        o.append(tp(l, MED, 10, cx, 130, DIM, tr=1.8, anchor='middle'))
        if i: o.append('<rect x="%.1f" y="72" width="1" height="68" fill="%s"/>' % (X+gw*i, LINE))
    o.append('<rect x="%d" y="168" width="%d" height="1" fill="%s"/>' % (X, R-X, LINE))

    # heatmap: last 53 weeks
    end = dt.date.today()
    end -= dt.timedelta(days=(end.weekday()+1) % 7)   # back to Sunday
    start = end - dt.timedelta(weeks=52)
    cell, gap = 12.0, 3.4
    gridw = 53*(cell+gap) - gap
    ox = X + ((R-X)-gridw)/2
    oy = 200
    mx = max([v for v in days.values()] + [1])
    for w in range(53):
        for dd in range(7):
            day = start + dt.timedelta(weeks=w, days=dd)
            if day > dt.date.today(): continue
            v = days.get(day.isoformat(), 0)
            if v == 0: col = RAMP[0]
            else:
                lvl = min(4, 1 + int(3*min(1.0, (v/ (mx*0.6)) )))
                col = RAMP[lvl]
            o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" fill="%s"/>'
                     % (ox+w*(cell+gap), oy+dd*(cell+gap), cell, cell, col))
    o.append(tp('Less', REG, 11, ox, oy+7*(cell+gap)+22, DIM))
    lx = ox + measure('Less', REG, 11) + 10
    for i, c in enumerate(RAMP):
        o.append('<rect x="%.1f" y="%.1f" width="11" height="11" rx="3" fill="%s"/>' % (lx+i*15, oy+7*(cell+gap)+11, c))
    o.append(tp('More', REG, 11, lx+5*15+4, oy+7*(cell+gap)+22, DIM))
    o.append('</g></svg>')
    open(out, 'w').write('\n'.join(o))

if __name__ == '__main__':
    user = os.environ.get('GH_USER', 'hdeniz06')
    token = os.environ.get('GH_TOKEN')
    days = fetch(user, token)
    total = sum(days.values())
    cur, best = streaks(days)
    render(days, total, cur, best)
    print('stats.svg ok', total, cur, best)
