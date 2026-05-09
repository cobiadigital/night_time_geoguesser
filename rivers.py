"""Build per-region river datasets from Natural Earth.

Combines the global rivers file with regional supplementary files (which add
tributaries and finer detail). Segments from any source merge under the same
river name so the resulting polylines connect end-to-end where Natural Earth
draws them connected.
"""
import json
import urllib.request

NE_BASE = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "master/geojson/"
)

# Global file. Region is decided per-feature by centroid. scalerank goes 0..10
# (lower = more prominent); 9 keeps even modest tributaries.
GLOBAL_URL = NE_BASE + "ne_10m_rivers_lake_centerlines.geojson"
GLOBAL_MAX_SCALERANK = 9

# Regional supplementary files. Their scaleranks live on a different axis
# (10..13) and are all small/local rivers; we trust the file's region rather
# than recomputing from centroid.
REGIONAL_SOURCES = [
    {'region': 'na', 'file': 'ne_10m_rivers_north_america.geojson', 'max_sr': 11},
    {'region': 'eu', 'file': 'ne_10m_rivers_europe.geojson',        'max_sr': 11},
    {'region': 'oc', 'file': 'ne_10m_rivers_australia.geojson',     'max_sr': 12},
]

REGIONS = ['na', 'eu', 'sa', 'af', 'as', 'oc']


def assign_region(lat, lng):
    """Pick a continental region for a centroid; first match wins."""
    if -40 <= lat <= 38 and -20 <= lng <= 55:
        return 'af'
    if -60 <= lat <= 15 and -85 <= lng <= -30:
        return 'sa'
    if 7 <= lat <= 85 and -170 <= lng <= -50:
        return 'na'
    if 35 <= lat <= 72 and -25 <= lng <= 60:
        return 'eu'
    # Australia + New Zealand only; Indonesia/PNG go to Asia, matching cities.py.
    if -50 <= lat <= -10 and 110 <= lng <= 180:
        return 'oc'
    if -15 <= lat <= 82 and 25 <= lng <= 180:
        return 'as'
    return None


def simplify(coords, tol=0.05):
    if len(coords) < 4:
        return coords
    out = [coords[0]]
    for c in coords[1:-1]:
        last = out[-1]
        if abs(c[0] - last[0]) + abs(c[1] - last[1]) > tol:
            out.append(c)
    out.append(coords[-1])
    return out


def fetch(url):
    print(f"Downloading {url}")
    with urllib.request.urlopen(url) as resp:
        return json.load(resp)


def feature_lines(feat):
    g = feat['geometry']
    if g['type'] == 'LineString':
        return [g['coordinates']]
    if g['type'] == 'MultiLineString':
        return g['coordinates']
    return []


def to_latlng(line):
    return [[round(p[1], 4), round(p[0], 4)] for p in line]


def add(by_region, region, name, sr, lines):
    bucket = by_region.setdefault(region, {})
    entry = bucket.setdefault(name, {'scalerank': sr, 'segments': []})
    entry['scalerank'] = min(entry['scalerank'], int(sr))
    for line in lines:
        entry['segments'].append(simplify(to_latlng(line)))


def feature_name(props):
    return props.get('name') or props.get('name_en')


def main():
    by_region = {r: {} for r in REGIONS}

    # 1. Global file - centroid decides the region.
    skipped_global = 0
    for feat in fetch(GLOBAL_URL)['features']:
        p = feat['properties']
        if p.get('featurecla') == 'Lake Centerline':
            continue
        name = feature_name(p)
        if not name:
            continue
        sr = p.get('scalerank')
        if sr is None or sr > GLOBAL_MAX_SCALERANK:
            continue
        lines = feature_lines(feat)
        if not lines:
            continue
        pts = [pt for line in lines for pt in line]
        lat = sum(pt[1] for pt in pts) / len(pts)
        lng = sum(pt[0] for pt in pts) / len(pts)
        region = assign_region(lat, lng)
        if region is None:
            skipped_global += 1
            continue
        add(by_region, region, name, sr, lines)

    # 2. Regional supplementary files - source determines the region.
    for src in REGIONAL_SOURCES:
        data = fetch(NE_BASE + src['file'])
        before = len(by_region[src['region']])
        added_features = 0
        for feat in data['features']:
            p = feat['properties']
            if p.get('featurecla') == 'Lake Centerline':
                continue
            name = feature_name(p)
            if not name:
                continue
            sr = p.get('scalerank')
            if sr is None or sr > src['max_sr']:
                continue
            lines = feature_lines(feat)
            if not lines:
                continue
            add(by_region, src['region'], name, sr, lines)
            added_features += 1
        gained = len(by_region[src['region']]) - before
        print(f"  +{added_features} features ({gained} new river names) -> {src['region']}")

    # 3. Write per-region JSONs.
    for region in REGIONS:
        rivers = [
            {'name': n, 'scalerank': info['scalerank'], 'segments': info['segments']}
            for n, info in by_region[region].items()
        ]
        rivers.sort(key=lambda r: (r['scalerank'], r['name']))
        outfile = f'{region}_rivers.json'
        with open(outfile, 'w', encoding='utf-8') as f:
            json.dump(rivers, f, separators=(',', ':'))
        seg_count = sum(len(r['segments']) for r in rivers)
        print(f"Saved {len(rivers):4d} rivers / {seg_count:5d} segments to {outfile}")
    if skipped_global:
        print(f"(Skipped {skipped_global} global features outside any region box.)")


if __name__ == '__main__':
    main()
