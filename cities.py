import urllib.request
import zipfile
import csv
import json
import io
import re

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
    'sa': {
        'countries': {
            'AR', 'BO', 'BR', 'CL', 'CO', 'EC', 'FK', 'GF', 'GY',
            'PE', 'PY', 'SR', 'UY', 'VE'
        },
        'min_pop': 50000,
        'state_in_label': set(),
        'outfile': 'sa_cities.json',
    },
    'af': {
        'countries': {
            'AO', 'BF', 'BI', 'BJ', 'BW', 'CD', 'CF', 'CG', 'CI', 'CM',
            'CV', 'DJ', 'DZ', 'EG', 'EH', 'ER', 'ET', 'GA', 'GH', 'GM',
            'GN', 'GQ', 'GW', 'KE', 'KM', 'LR', 'LS', 'LY', 'MA', 'MG',
            'ML', 'MR', 'MU', 'MW', 'MZ', 'NA', 'NE', 'NG', 'RE', 'RW',
            'SC', 'SD', 'SH', 'SL', 'SN', 'SO', 'SS', 'ST', 'SZ', 'TD',
            'TG', 'TN', 'TZ', 'UG', 'YT', 'ZA', 'ZM', 'ZW'
        },
        'min_pop': 50000,
        'state_in_label': set(),
        'outfile': 'af_cities.json',
    },
    'as': {
        'countries': {
            'AE', 'AF', 'AM', 'AZ', 'BD', 'BH', 'BN', 'BT', 'CN', 'GE',
            'HK', 'ID', 'IL', 'IN', 'IQ', 'IR', 'JO', 'JP', 'KG', 'KH',
            'KP', 'KR', 'KW', 'KZ', 'LA', 'LB', 'LK', 'MM', 'MN', 'MO',
            'MV', 'MY', 'NP', 'OM', 'PH', 'PK', 'PS', 'QA', 'SA', 'SG',
            'SY', 'TH', 'TJ', 'TL', 'TM', 'TW', 'UZ', 'VN', 'YE',
            # Asian Russia (eastern half), filtered by min_lng below.
            'RU'
        },
        # Only keep Russian cities east of the Urals so we don't duplicate the
        # European-Russia entries that already appear in the EU dataset.
        'ru_min_lng': 60.0,
        'min_pop': 50000,
        'state_in_label': set(),
        'outfile': 'as_cities.json',
    },
    'oc': {
        'countries': {
            'AS', 'AU', 'CK', 'FJ', 'FM', 'GU', 'KI', 'MH', 'MP', 'NC',
            'NF', 'NR', 'NU', 'NZ', 'PF', 'PG', 'PN', 'PW', 'SB', 'TK',
            'TO', 'TV', 'VU', 'WF', 'WS'
        },
        'min_pop': 50000,
        'state_in_label': set(),
        'outfile': 'oc_cities.json',
    },
}

# GeoNames stores Canadian admin1 as numeric FIPS codes; map to postal abbrs.
CA_ADMIN1 = {
    '01': 'AB', '02': 'BC', '03': 'MB', '04': 'NB', '05': 'NL',
    '07': 'NS', '08': 'ON', '09': 'PE', '10': 'QC', '11': 'SK',
    '12': 'YT', '13': 'NT', '14': 'NU',
}

# City subdivisions GeoNames lists alongside the parent city. Drop them so the
# parent (e.g. "Paris, FR") isn't crowded out by 13 arrondissements.
SUBDIVISION_PATTERNS = {
    'FR': re.compile(r'^(?:Paris|Marseille|Lyon) \d+\b'),
    'RO': re.compile(r'^Sector \d+$'),
}
# NYC boroughs are coded as PPLA2 (county seats), so they slip past the PPLX
# filter. Drop them by name within New York state.
NYC_BOROUGHS = {'Manhattan', 'Brooklyn', 'Queens', 'Staten Island',
                'The Bronx', 'Bronx'}


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

        # Skip sections of populated places (boroughs, arrondissements, etc.)
        if row[7] == 'PPLX':
            continue

        name = row[1]
        country = row[8]
        state_code = row[10]

        sub_re = SUBDIVISION_PATTERNS.get(country)
        if sub_re and sub_re.match(name):
            continue
        if country == 'US' and state_code == 'NY' and name in NYC_BOROUGHS:
            continue
        try:
            lat = float(row[4])
            lng = float(row[5])
        except ValueError:
            continue

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
        if country == 'RU' and 'ru_min_lng' in cfg and lng < cfg['ru_min_lng']:
            continue

        if country in cfg['state_in_label'] and state_code:
            if country == 'CA':
                state_code = CA_ADMIN1.get(state_code, state_code)
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
