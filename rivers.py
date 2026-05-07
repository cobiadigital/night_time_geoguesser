"""Build per-region river datasets from Natural Earth.

Mirrors the structure of cities.py: downloads a single source file, splits
features by continent, and writes one JSON per region for the front-end.
"""
import json
import urllib.request

URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "master/geojson/ne_10m_rivers_lake_centerlines.geojson"
)

REGIONS = ['na', 'eu', 'sa', 'af', 'as', 'oc']

# Drop any river whose Natural Earth scalerank is greater than this. Lower
# numbers are more prominent (Amazon = 0, Nile = 1). 7 keeps a few hundred
# named rivers worldwide.
MAX_SCALERANK = 7


def assign_region(lat, lng):
    """Pick a continental region for the centroid of a river.

    Order matters; the first matching box wins. The 60 E cap on Europe matches
    cities.py so that we don't pull Asian Russia into the European list.
    """
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
    """Distance-thin a polyline (degrees) to keep JSON small."""
    if len(coords) < 4:
        return coords
    out = [coords[0]]
    for c in coords[1:-1]:
        last = out[-1]
        if abs(c[0] - last[0]) + abs(c[1] - last[1]) > tol:
            out.append(c)
    out.append(coords[-1])
    return out


def fetch_geojson():
    print(f"Downloading {URL}")
    with urllib.request.urlopen(URL) as resp:
        return json.load(resp)


def main():
    data = fetch_geojson()

    by_name = {}
    for feat in data['features']:
        props = feat['properties']
        if props.get('featurecla') == 'Lake Centerline':
            continue
        name = props.get('name') or props.get('name_en')
        if not name:
            continue
        scalerank = props.get('scalerank')
        if scalerank is None or scalerank > MAX_SCALERANK:
            continue

        geom = feat['geometry']
        if geom['type'] == 'LineString':
            lines = [geom['coordinates']]
        elif geom['type'] == 'MultiLineString':
            lines = geom['coordinates']
        else:
            continue

        entry = by_name.setdefault(name, {'segments': [], 'scalerank': scalerank})
        entry['scalerank'] = min(entry['scalerank'], int(scalerank))
        for line in lines:
            # GeoJSON stores [lng, lat]; Leaflet wants [lat, lng].
            ll = [[round(p[1], 4), round(p[0], 4)] for p in line]
            entry['segments'].append(simplify(ll))

    regional = {r: [] for r in REGIONS}
    skipped = 0
    for name, info in by_name.items():
        points = [p for seg in info['segments'] for p in seg]
        if not points:
            continue
        lat = sum(p[0] for p in points) / len(points)
        lng = sum(p[1] for p in points) / len(points)
        region = assign_region(lat, lng)
        if region is None:
            skipped += 1
            continue
        regional[region].append({
            'name': name,
            'scalerank': info['scalerank'],
            'segments': info['segments'],
        })

    for region, rivers in regional.items():
        rivers.sort(key=lambda r: (r['scalerank'], r['name']))
        outfile = f'{region}_rivers.json'
        with open(outfile, 'w', encoding='utf-8') as f:
            json.dump(rivers, f, separators=(',', ':'))
        print(f"Saved {len(rivers):3d} rivers to {outfile}")
    if skipped:
        print(f"Skipped {skipped} rivers outside any region box.")


if __name__ == '__main__':
    main()
