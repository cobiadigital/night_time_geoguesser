import urllib.request
import zipfile
import csv
import json
import io

REGIONS = {
    'na': {
        'countries': {
            'US', 'CA', 'MX', 'GT', 'CU', 'HT', 'DO', 'HN',
            'SV', 'NI', 'CR', 'PA', 'JM', 'BS', 'BZ', 'PR'
        },
        'min_pop': 50000,
        'state_in_label': {'US', 'CA'},
        'outfile': 'na_cities.json',
    },
    'eu': {
        'countries': {
            'AL', 'AD', 'AT', 'BA', 'BE', 'BG', 'BY', 'CH', 'CY', 'CZ',
            'DE', 'DK', 'EE', 'ES', 'FI', 'FO', 'FR', 'GB', 'GG', 'GI',
            'GR', 'HR', 'HU', 'IE', 'IM', 'IS', 'IT', 'JE', 'LI', 'LT',
            'LU', 'LV', 'MC', 'MD', 'ME', 'MK', 'MT', 'NL', 'NO', 'PL',
            'PT', 'RO', 'RS', 'RU', 'SE', 'SI', 'SK', 'SM', 'TR', 'UA',
            'VA', 'XK'
        },
        # Trim Asian Russia and most of eastern Turkey by longitude.
        'max_lng': 60.0,
        'min_pop': 50000,
        'state_in_label': set(),
        'outfile': 'eu_cities.json',
    },
}


def download_geonames():
    url = "http://download.geonames.org/export/dump/cities15000.zip"
    print("Downloading GeoNames data (this might take a few seconds)...")
    response = urllib.request.urlopen(url)
    zipped = zipfile.ZipFile(io.BytesIO(response.read()))
    with zipped.open('cities15000.txt') as f:
        return f.read().decode('utf-8').splitlines()


def build_region(lines, key, cfg):
    cities = []
    reader = csv.reader(lines, delimiter='\t')

    for row in reader:
        if len(row) < 15:
            continue

        name = row[1]
        try:
            lat = float(row[4])
            lng = float(row[5])
        except ValueError:
            continue
        country = row[8]
        state_code = row[10]

        try:
            population = int(row[14])
        except ValueError:
            population = 0

        if country not in cfg['countries']:
            continue
        if population < cfg['min_pop']:
            continue
        if 'max_lng' in cfg and lng > cfg['max_lng']:
            continue

        if country in cfg['state_in_label'] and state_code:
            display_name = f"{name}, {state_code}"
        else:
            display_name = f"{name}, {country}"

        cities.append({
            "name": display_name,
            "lat": lat,
            "lng": lng,
            "pop": population,
        })

    with open(cfg['outfile'], 'w', encoding='utf-8') as f:
        json.dump(cities, f, indent=4)

    print(f"Saved {len(cities)} cities to {cfg['outfile']}")


def main():
    lines = download_geonames()
    for key, cfg in REGIONS.items():
        build_region(lines, key, cfg)


if __name__ == '__main__':
    main()
