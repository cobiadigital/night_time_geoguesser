import urllib.request
import zipfile
import csv
import json
import io

# 1. Download the GeoNames dataset for global cities > 15,000
url = "http://download.geonames.org/export/dump/cities15000.zip"
print("Downloading GeoNames data (this might take a few seconds)...")

try:
    response = urllib.request.urlopen(url)
    zipped_data = zipfile.ZipFile(io.BytesIO(response.read()))
except Exception as e:
    print(f"Failed to download data: {e}")
    exit()

# 2. Extract the text file into memory
with zipped_data.open('cities15000.txt') as f:
    lines = f.read().decode('utf-8').splitlines()

# 3. Define North American country codes
na_countries = {
    'US', 'CA', 'MX', 'GT', 'CU', 'HT', 'DO', 'HN',
    'SV', 'NI', 'CR', 'PA', 'JM', 'BS', 'BZ', 'PR'
}

cities_json = []

# GeoNames is tab-separated
reader = csv.reader(lines, delimiter='\t')

for row in reader:
    # Safely skip malformed rows
    if len(row) < 15:
        continue

    name = row[1]
    lat = float(row[4])
    lng = float(row[5])
    country = row[8]
    state_code = row[10]  # Admin1 code (State/Province for US/CA)

    # Catch any missing population data
    try:
        population = int(row[14])
    except ValueError:
        population = 0

    # FILTER: North America AND Population >= 50,000
    if country in na_countries and population >= 50000:
        # Format the display name (e.g., "Mobile, AL" or "Monterrey, MX")
        if country in ['US', 'CA'] and state_code:
            display_name = f"{name}, {state_code}"
        else:
            display_name = f"{name}, {country}"

        cities_json.append({
            "name": display_name,
            "lat": lat,
            "lng": lng
        })

# 4. Save to a perfectly formatted JSON file
with open('na_cities.json', 'w', encoding='utf-8') as outfile:
    json.dump(cities_json, outfile, indent=4)

print(f"Success! Saved {len(cities_json)} North American cities to na_cities.json")