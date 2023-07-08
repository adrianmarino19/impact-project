import requests
import pandas as pd
import numpy as np
from geopy.geocoders import GoogleV3

API_KEY = "AIzaSyCikxBls3oMC-l3pOoQDfWzI5a20KBrA1s"

def validate_address(address):
    """
    Validate an address using Google Places API. 
    """
    try:
        # Prepare the API request
        url = 'https://maps.googleapis.com/maps/api/place/autocomplete/json'
        params = {
            'input': address,
            'key': API_KEY
        }

        # Send the request
        response = requests.get(url, params=params)

        # Parse the response
        data = response.json()
        if data['status'] == 'OK':
            # Return the first autocomplete prediction if available
            if len(data['predictions']) > 0:
                # print(data['predictions'][0]['description'])
                return data['predictions'][0]['description']
            else:
                return None
        else:
            return None

    except Exception as e:
        print("Didn't Work: ", e)
        return None
                

# Create the Geolocator
geolocator2 = GoogleV3(api_key=API_KEY)

def extract_clean_address(row):
    """
    This function calls the API, gets all the data, separates it into columns and returns it.
    """

    address = row['FORMATED_ADDRESS']
    
    try:
        location = geolocator2.geocode(address)
        data = location.raw
        type_street = ''
        neighborhood = ''
        street = ''
        locality = ''
        province = ''
        region = ''
        country = ''
        postal_code = ''
        streetnumber = ''
        lat = 'fallo'
        long = 'fallo'

        for row in data['address_components']:
            if row['types'] == ['route']:
                street_parts = row['long_name'].split(' ', 1) # This splits the string at the first space
                if len(street_parts) > 1 and street_parts[0] in ['Calle', 'Avenida']:
                    type_street = street_parts[0] # This is 'Calle', 'Avenida', etc.
                    street = street_parts[1] # This is the rest of the string
                else:
                    street = row['long_name'] # If there was 
                # street = row['long_name']
                # print(street)
            elif row['types'] == ['locality', 'political']:
                locality = row['long_name']
                # print(locality)
            elif row['types'] == ['administrative_area_level_2', 'political']:
                province = row['long_name']
                # print(province)
            elif row['types'] == ['administrative_area_level_1', 'political']:
                region = row['long_name']
                # print(region)
            elif row['types'] == ['country', 'political']:
                country = row['long_name']
                # print(country)
            elif row['types'] == ['postal_code']:
                postal_code = row['long_name']
                # print(postal_code)
            elif row['types'] == ['street_number']:
                streetnumber = row['long_name']
                # print(streetnumber)
            elif row['types'] == ['neighborhood', 'political']:
                neighborhood = row['long_name']
                # print(neighborhood)
        try:
            # lat = data['geometry']['location']['lat']
            # long = data['geometry']['location']['lng']
            lat = location.latitude
            long = location.longitude
        except:
            print("EL LAT O LONG FALLO")
            pass
        
        return pd.Series((type_street, street, streetnumber, locality, province, region, country, postal_code, neighborhood, lat, long))
    except:
        print("Didn't Work")
        return pd.Series((None, None, None, None, None, None, None, None, None, None, None))