# Import modules
import streamlit as st
import streamlit_authenticator as stauth
from streamlit_option_menu import option_menu
from streamlit.components.v1 import html
from yaml.loader import SafeLoader
import yaml
import authenticator
import requests
import sqlite3
import pandas as pd
import base64
import numpy as np
import re
import folium
import tempfile
from geopy.geocoders import GoogleV3
from functions import  extract_clean_address, validate_address
from unidecode import unidecode
import time
import os
import datetime



# Import API key from environment
API_KEY = os.environ.get("api_key")
# In case you use it locally, you can use the following line
# API_KEY = ""

# from ipyleaflet import Map, Marker

# Defining credentials
with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

# Creating authenticator variable
authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
    config['preauthorized']
)

# Establishing login
name, authentication_status, username = authenticator.login('Login', 'main')

# Establishing routes to login
if authentication_status:

    authenticator.logout('Logout', "sidebar")
    st.sidebar.image("olin_group.png")
    st.write("""
    # Welcome to the Olin Group Dashboard 
    """)
    st.write(f"Hello {name}!")
    st.write(f"Select any of the following 3 tabs to start to work:")


    # Display menu to navigate the dashboard
    menu = option_menu(
        menu_title = None,
        options = ["Clean Data", "New Address", "Navigation"],
        default_index = 0,
        orientation = "horizontal"
    )

    ndf = pd.DataFrame()
    address = ""

    # Display the Clean Data menu
    if menu == "Clean Data":

        #Function to make the transformtions in the CSV (here goes our cleaning and code)
        def transform_csv(input_file):
            # Reading data
            ad_orig = []

            # Dictionary to normalize the data
            replacements = {
                #";", ","
                '"': "",
                "º": "ND",
                "Á": "A",
                "É": "E",
                "Í": "I",
                "Ó": "O",
                "Ú": "U",
                "Ñ": "N",
                "Ü": "U",
                "C/": "CALLE",
                "C /": "CALLE",
                "AVDA": "AVENIDA",
                "CTRA": "CARRETERA",
                "URB. ": "URBANIZACION ",
                "URB " : "URBANIZACION ",
                "URB." : "URBANIZACION ",
                "AVENIDAAVENIDA" : "AVENIDA",
                "\n": "",
                "PLAZAPLAZA": "PLAZA"
            }

            # Create a temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False)

            # Write the contents of the uploaded file to the temporary file
            temp_file.write(input_file.read())

            # Close the temporary file
            temp_file.close()

            # Opening and performing alterations
            with open(temp_file.name, encoding='utf-8') as file:
                for line in file:
                    line = line.upper()
                    for key, value in replacements.items():
                        line = line.replace(key, value)
                    
                    # Split the line by the semicolon, normally its the neighborhood and province
                    line = line.split(';')

                    ad_orig.append(line)

            # From the list, create a dataframe
            ad_orig = pd.DataFrame(ad_orig)
            # Create the column names
            ad_orig.columns = ["ADDRESSES", "NEIGHBORHOOD", "PROVINCE"]

            df = ad_orig

            def type_street(add):
                """
                This function is used to create a new column with the type of street
                in case CALLE or AVENIDA is present in the address
                """
                prefixes = ['CALLE', 'AVENIDA']#, 'CARRETERA']
                # print(type(add))
                for p in prefixes:
                    if str(add).startswith(p):
                        # print(add.startswith(p))
                        # print("TRUE")
                        return p
                return ""

            def remove_prefix(add):
                """ 
                This function is to remove the prefixes from the address
                in case they are present
                """
                prefixes = ['CALLE', 'AVENIDA']#, 'CARRETERA']
                # print(type(add))
                for p in prefixes:
                    if str(add).startswith(p):
                        address_parts = str(add).split(maxsplit=1)
                        if len(address_parts) > 1:
                            return address_parts[1]
                return add



            # Create a new column 'Type of street' based on the prefixes
            df['TYPE_OF_STREET'] = df['ADDRESSES'].apply(type_street)

            # Remove the prefixes from the original 'Street' column
            df['ADDRESSES'] = df['ADDRESSES'].apply(remove_prefix)

            # Move the 'Type' column to the first position
            type_column = df.pop('TYPE_OF_STREET')
            df.insert(0, 'TYPE_OF_STREET', type_column)

            #drop first line that is empty (is the header of the csv)
            df = df.drop(df.index[0])

            # Function to rearrange the neighborhood names
            def rearrange_name(name):
                """
                This function is to rearrange the neighborhood names.
                Ex: 'MANGA DEL MAR, LA' -> 'LA MANGA DEL MAR'
                """
                if isinstance(name, str) and ',' in name:
                    # Split the name into two parts around the comma
                    parts = name.split(',')
                    # Remove leading/trailing white space and reverse the parts
                    parts = [part.strip() for part in reversed(parts)]
                    # Join the parts back together with a space
                    name = ' '.join(parts)
                return name

            # Apply the function to the 'NEIGBORHOOD' column
            df['NEIGHBORHOOD'] = df['NEIGHBORHOOD'].apply(rearrange_name)

            # Fill NaN values in 'NEIGHBORHOOD' with an empty string in case there are any
            df['NEIGHBORHOOD'] = df['NEIGHBORHOOD'].fillna('')

            # Change column names
            df.columns = ['type_of_street','addresses', 'neighborhood', 'province']

            # Space out 'addresses' entries in case they are not spaced out
            df['addresses'] = df['addresses'].str.replace('(\d+)', r' \1 ').str.replace('([A-Z]{2,})', r' \1 ')

            # Convert all entries to lower case for uniformity
            df = df.applymap(lambda s:s.lower() if type(s) == str else s)

            # Replace 'NO ENCONTRADA' with np.nan
            df.replace('no encontrada', np.nan, inplace=True)

            # Drop rows where 'addresses' column is NaN
            df.dropna(subset=['addresses'], inplace=True)

            def add_space_between_letter_and_number(address):
                """
                This function adds a space between the last letter and the number
                """
                # Define a regular expression pattern to extract numbers preceded by a letter
                pattern = r'(\D)(\d+)'

                if isinstance(address, str):  # Check if the value is a string
                    address = re.sub(pattern, r'\1 \2', address)
                return address

            # Apply the function to the 'addresses' column and update the values
            df['addresses'] = df['addresses'].apply(add_space_between_letter_and_number)

            def add_space_between_number_and_letter(address):
                """ 
                This function adds a space between the number and the following non-digit character
                """
                # Define a regular expression pattern to detect a number followed by a letter without a space
                pattern = r'(\d+)(\D)'
                
                if isinstance(address, str):  # Check if the value is a string
                    address = re.sub(pattern, r'\1 \2', address)
                return address

            # Apply the function to add a space between the number and the following non-digit character
            df['addresses'] = df['addresses'].apply(add_space_between_number_and_letter)

            # Detect "Urbanizacion" wrong spelled and replace it
            def check_urb(address):
                if 'urbanizaci' in address and 'urbanizacion' not in address:
                    address = address.replace('urbanizaci', 'urbanizacion ')
                elif 'urbaniz' in address and 'urbanizacion' not in address:
                    address = address.replace('urbaniz', 'urbanizacion ')
                elif 'urb' in address and 'urbanizacion' not in address:
                    address = address.replace('urb', 'urbanizacion ')
                if 'apartamentoapartamento' in address:
                    address = address.replace('apartamentoapartamento', 'apartamento ')
                if 'plaza' in address and 'plaza ' not in address:
                    address = address.replace('plaza', 'plaza ')
                if 'duplex' in address and 'duplex ' not in address:
                    address = address.replace('duplex', 'duplex ')
                if 'parcelafosforo' in address:
                    address = address.replace('parcelafosforo, esquina con ', '')

                return address

            # Apply the check_urb function to the 'addresses' column
            df['addresses'] = df['addresses'].apply(lambda x: check_urb(x))

            def extract_address_components(address):
                """
                This function extracts the street, street number, and floor from the address
                """
                # Define a regular expression pattern to extract the street number, street, and floor
                pattern = r'\b(\d+)\s+(\S+)\s*(.*)'

                if isinstance(address, str):  # Check if the value is a string
                    match = re.search(pattern, address)
                    if match:
                        street_number = match.group(1)
                        # street = match.group(2)
                        floor = match.group(2) + ' ' + match.group(3)
                        # return street, street_number, floor
                        return street_number, floor
                # return '', '', ''
                return '', ''

            # Apply the function to the 'address' column and create new columns 'street', 'street_number', and 'floor'
            df[['street_number', 'floor']] = df['addresses'].apply(extract_address_components).apply(pd.Series)

            def extract_street_number(address):
                """  
                This function extracts the street number from the address
                """
                # Define a regular expression pattern to extract the street number
                pattern = r'\b(\d+)(?:\s|$)'
                if isinstance(address, str):  # Check if the value is a string
                    match = re.search(pattern, address)
                    if match:
                        return match.group(1)
                return ''

            # Apply the function to the 'address' column and create a new column 'street_number'
            df['street_number'] = df['addresses'].apply(extract_street_number)

            # Function to extract the street number from the address
            def extract_street_number2(address):
                """ 
                This function extracts the street number from the address with a different pattern.
                """
                
                # Define a regular expression pattern to extract the street number
                pattern = r'\b(\d+)\b'
                if isinstance(address, str):  # Check if the value is a string
                    matches = re.findall(pattern, address)
                    if matches:
                        return ' '.join(matches)
                return ''

            # Apply the function to the 'address' column and create a new column 'street_number'
            df['street_number'] = df.apply(lambda row: extract_street_number2(row['addresses']) if row['street_number'] == '' else row['street_number'], axis=1)

            def check_st_num(st_num):
                """ 
                This function is to check if the street number is a valid number and correct it if it is not.
                Ex: 4242 -> 42
                """
                if len(st_num) >= 4:
                    n = len(st_num) // 2
                    return st_num[:n]
                return st_num

            # Apply the check_st_num function to the 'street_number' column    
            df['street_number'] = df['street_number'].apply(lambda x: check_st_num(x))

            # Convert all addresses to string type
            df['addresses'] = df['addresses'].astype(str)

            # Extract the street name from the address
            # df['street_name'] = df['addresses'].apply(lambda x: ' '.join(re.findall(r'[^\d]+', x.split(',')[0])).strip())

            # Check floor_numbers
            df['floor_number'] = df['addresses'].apply(lambda x: re.findall(r'(\d+\s*nd)', x))
            df['floor_number'] = df['floor_number'].apply(lambda x: x[0] if x else '')

            # Function to extract the street name from the address
            def extract_street_name(address):
                if isinstance(address, str):  # Check if the value is a string
                    if ',' in address:
                        # If address contains a comma, extract all characters before the comma
                        street_name = address.split(',')[0]
                    elif re.search(r'\d', address):
                        # If address contains a number, extract all characters before the first number
                        street_name = re.split(r'\d', address)[0]
                    else:
                        # Otherwise, return the whole address as the street name
                        street_name = address
                    
                    return street_name.strip()  # Remove leading/trailing whitespace from the street name
                return ''

            # Apply the function to the 'addresses' column and create a new column 'street_name'
            df['street_name2'] = df['addresses'].apply(extract_street_name)

            def remove_numbers(address):
                """ 
                This function removes all numbers from the address.
                """
                address_without_numbers = re.sub(r'N°|\b\d+\b', '', address)
                return address_without_numbers.strip()

            # Remove numbers from the 'street_name' column
            df['street_name2'] = df['street_name2'].apply(lambda x: remove_numbers(x))

            def remove_nnd(address):
                """ 
                This function removes nnd from the address.
                """
                address_without_nnd = re.sub(r' nnd$| nnd ', '', address, flags=re.IGNORECASE)
                return address_without_nnd.strip()

            # Remove nnd from the 'street_name' and 'floor' column
            df['street_name2'] = df['street_name2'].apply(lambda x: remove_nnd(x))
            df['floor'] = df['floor'].apply(lambda x: remove_nnd(x))

            def remove_nd(address):
                """ 
                This function removes nd from the address.
                """
                address_without_nnd = re.sub(r' nd$| nd ', '', address, flags=re.IGNORECASE)
                return address_without_nnd.strip()

            # Remove nd from the 'street_name' and 'floor' column
            df['street_name2'] = df['street_name2'].apply(lambda x: remove_nd(x))
            df['floor'] = df['floor'].apply(lambda x: remove_nd(x))


            def remove_parentheses(address):
                """ 
                This function removes parentheses from the address.
                And remove the content inside the parentheses.
                """
                address_without_parentheses = re.sub(r'\((.*)\)', '', address)
                return address_without_parentheses.strip()

            # Remove parentheses from the 'street_name' column
            df['street_name2'] = df['street_name2'].apply(lambda x: remove_parentheses(x))


            return df
        
        def call_api(df):

            # Start working on the dataframe to be able to send it to the API
            # Prepare the data 
            df['prov'] = df.apply(lambda x: "Region de Murcia" if x['province'] == "murcia" else x['province'], axis=1)
            df['type_of_street'] = df['type_of_street'].apply(lambda x: x if pd.notnull(x) else '')
            df['street_number'] = df['street_number'].apply(lambda x: int(x) if pd.notnull(x) else '')
            df['prov'] = df['prov'].astype(str)

            # Format the full address to send to the API
            df['full'] = df['type_of_street'] + ' ' + df['street_name2'] + ', ' + df['street_number'].astype(str) + ', ' + df['prov'] + ', España'

            # Start with the API part
            # Let's start with Google Places API
            # Function was imported previously





            # Apply the function to the dataframe
            df['FORMATED_ADDRESS'] = df.apply(lambda x: validate_address(x['full']), axis=1)

            # Now we already have a Formated Address column, but we need to get the coordinates
            # Let's start with Google Geocoding API - Function was imported previously

            # Apply the extract_clean_address function to 'clean address' column and assign it back to the column
            df[['TYPE_STREET','STREET_NAME', 'STREET_NUMBER', \
                'LOCALITY', 'PROVINCE', 'REGION', 'COUNTRY', 'POSTAL_CODE',\
                'NEIGHBOURHOOD', 'LAT', 'LONG']] = df.apply(extract_clean_address, axis=1)
            
            


            # As we have a lot of urbanizaciones and are having problems with it, we will make it easier to read
            def clean_urba(row):
                """
                This adds the urbanization name to the neighbourhood column
                in case it exists.
                """
                if 'urbaniz' in str(row['FORMATED_ADDRESS']).lower() or 'aldeas' in str(row['FORMATED_ADDRESS']).lower():
                    neigh = row['FORMATED_ADDRESS'].split(',')[0]
                    return neigh
                return ''

            # Apply the clean_urba function
            df['NEIGHBOURHOOD'] = df.apply(clean_urba, axis=1)

            # Add the OBSERVATIONS column with extra data not included in the API.
            df['OBSERVATIONS'] = df['floor'].apply(lambda x: x if pd.notna(x) else '')

            # Function to add floor and street number if urbanization
            def add_observ_urba(row):
                """
                This function adds the floor and street number to the 
                observations column if the address is an urbanization.
                """
                if 'urbaniz' in str(row['NEIGHBOURHOOD']).lower() or 'aldeas' in str(row['NEIGHBOURHOOD']).lower():
                    number = str(row['street_number']).split('.')[0]
                    # number = int(number)
                    return  number + ' ' + str(row['floor'])
                
                return row['OBSERVATIONS']

            # Add observations    
            df['OBSERVATIONS'] = df.apply(add_observ_urba, axis=1)

            # Take the nan out in observations
            df['OBSERVATIONS'] = df['OBSERVATIONS'].apply(lambda x: x.replace('nan', '') if 'nan' in x else x)

            # Add street number if it's not automatically added
            def add_street_number(row):
                """"
                This function adds the street number in case it was not added before
                """
                
                if str(row['STREET_NUMBER']) == 'nan' or str(row['STREET_NUMBER']) == '':
                    number = row['street_number']
                    return number
                else:
                    return row['STREET_NUMBER']

            df['STREET_NUMBER'] = df.apply(add_street_number, axis=1)

            # Create a clean dataframe with only the columns we want
            clean_df = df[['FORMATED_ADDRESS', 'TYPE_STREET', 'STREET_NAME', 'STREET_NUMBER', \
                        'LOCALITY', 'PROVINCE', 'REGION', 'COUNTRY', 'POSTAL_CODE', 'NEIGHBOURHOOD',\
                            'OBSERVATIONS', 'LAT', 'LONG']].copy()
            
            # def replace_quotes(input_string):
            #     try:
            #         return input_string.replace("'", "''")
            #     except:
            #         pass

            # columns = ['FORMATED_ADDRESS', 'TYPE_STREET', 'STREET_NAME', 'STREET_NUMBER', \
            #                         'LOCALITY', 'PROVINCE', 'REGION', 'COUNTRY', 'POSTAL_CODE', 'NEIGHBOURHOOD',\
            #                             'OBSERVATIONS']

            # for column in columns:
            #     df[column] = df[column].apply(replace_quotes)
            #     clean_df[column] = clean_df[column].apply(replace_quotes)
            
            
            return df, clean_df
        

        # Function to download the file
        def get_csv_download_link(df):
            def clean_text(input_string):
                try:
                    return unidecode(input_string)
                except:
                    pass
            columns = ['FORMATED_ADDRESS', 'TYPE_STREET', 'STREET_NAME', 'STREET_NUMBER', \
                                    'LOCALITY', 'PROVINCE', 'REGION', 'COUNTRY', 'POSTAL_CODE', 'NEIGHBOURHOOD',\
                                        'OBSERVATIONS', 'LAT', 'LONG']
            
            for column in columns:
                df[column] = df[column].apply(clean_text)

            current_date = datetime.datetime.now().strftime("%Y-%m-%d")
            csv = df.to_csv(encoding='utf-8', index=False)
            b64 = base64.b64encode(csv.encode()).decode()  # Encoding the CSV data
            href = f'<a href="data:file/csv;base64,{b64}" download="Clean_Data_{current_date}.csv">Click here to download the CSV file</a>'
            return href


        # STREAMLIT - File upload section
        st.header("Upload CSV File")
        uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
        

        if uploaded_file is not None:
            # Perform CSV transformation
            df = transform_csv(uploaded_file)

            df, clean_df = call_api(df)

            # Show transformed data
            # st.header("Transformed Data")
            # st.write(df)

            # Download link for the transformed CSV file
            st.write("Please compare the data: Clean Data - Raw data")
            st.write(df)
            st.write("Clean Data")
            st.write(clean_df)
            st.header("Download Transformed CSV")
            csv_download_link = get_csv_download_link(clean_df)
            st.markdown(csv_download_link, unsafe_allow_html=True)

        # def insert_db(row):
        #     """
        #     This function inserts the data into the database.
        #     """
        #     api_url = "http://127.0.0.1:5000/api/og/v1/addr/insertaddr"
        #     data = {
        #             "FORMATED_ADDRESS" : row['FORMATED_ADDRESS'],
        #             "TYPE_STREET" : row['TYPE_STREET'],
        #             "STREET_NAME" : row['STREET_NAME'],
        #             "STREET_NUMBER" : row['STREET_NUMBER'],
        #             "LOCALITY" : row['LOCALITY'],
        #             "PROVINCE" : row['PROVINCE'],
        #             "REGION" : row['REGION'],
        #             "COUNTRY" : row['COUNTRY'],
        #             "POSTAL_CODE" : row['POSTAL_CODE'],
        #             "NEIGHBOURHOOD" : row['NEIGHBOURHOOD'],
        #             "LAT" : row['LAT'],
        #             "LNG" : row['LONG'],
        #             "OBSERVATIONS" : row['OBSERVATIONS']
        #     }
        #     response = requests.post(api_url, json=data)
        #     if response.status_code == 200:
        #         st.success("Clean addresses saved successfully!")
            

        # Button to save clean addresses
        if st.button("Save clean addresses"):
            # Connect to the database and store the clean addresses
            # api_url = "http://127.0.0.1:5000/api/og/v1/addr/insertaddr"
            
            # requests.post(api_url, json=data, headers=headers)
            # response = requests.post(api_url, json=clean_df.to_dict(orient="records"))
            # clean_df.apply(insert_db, axis=1)

            # if response.status_code == 200:
            st.success("Clean addresses saved successfully!")
            # else:
            #     st.error("Failed to save clean addresses. Please try again.")


    if menu == "New Address":

        # Function to save the confirmed address in SQLite
        def save_address(address):
            conn = sqlite3.connect("confirmed_addresses.db")
            c = conn.cursor()
            c.execute("INSERT INTO addresses (address) VALUES (?)", (address,))
            conn.commit()
            conn.close()


        # Streamlit app
        st.title("OLIN Address Registery")

        # Form fields
        client_name = st.text_input("Client Name")
        street_type = st.selectbox("Street Type", ["Avenida", "Calle", "Callejón", "Travesía"])
        street_name = st.text_input("Street Name")
        street_number = st.text_input("Street Number")
        inner_number = st.text_input("Inner Number")
        district_name = st.text_input("District / Municipality")
        zip_code = st.number_input("Zip Code", value=0, step=1)
        city = st.text_input("City")
        province = st.text_input("Province")
        country = st.text_input("Country")

        form_address = f"{street_type} {street_name}, {street_number}, {city}, {zip_code} ,{province}, {country}"

        if st.button("Validate Address"):
            address = validate_address(form_address)
            nadf = pd.DataFrame()
            data = {'FORMATED_ADDRESS': address}
            nadf['FORMATED_ADDRESS'] = [address]
            nadf[['TYPE_STREET','STREET_NAME', 'STREET_NUMBER', \
                'LOCALITY', 'PROVINCE', 'REGION', 'COUNTRY', 'POSTAL_CODE',\
                'NEIGHBOURHOOD', 'LAT', 'LONG']] = extract_clean_address(data)
            nadf['OBSERVATIONS'] = inner_number
            

            # address = get_address_details(street_type, street_name, street_number, inner_number, neighborhood, district_name, zip_code, city, province, country)
            st.write("Addres:", address)

            # Make a map
            initial_center = [nadf['LAT'], nadf['LONG']]
            initial_zoom = 30

            # Create a map centered at the initial coordinates
            m = folium.Map(location=initial_center, zoom_start=initial_zoom)

            # Parse user input into latitude and longitude
            try:
                latitude, longitude = initial_center
                # Add a marker at the user-specified location
                folium.Marker(location=[latitude, longitude], tooltip='User Location').add_to(m)
            except:
                st.warning("Invalid input. Please enter coordinates in the format 'latitude, longitude'.")

            # Convert the folium map to HTML
            html_map = m._repr_html_()

            # Display the map in Streamlit
            html(html_map, width=700, height=500, scrolling=False)

        if st.button("Save Address"):
            st.success("Address saved successfully!")
            
        reset_button = st.button("Reset")

        if reset_button:
            street_name = ""
            street_number = ""
            inner_number = ""
            neighborhood = ""
            district_name = ""
            zip_code = 0
            city = ""
            province = ""
            country = ""

    if menu == "Navigation":
        
        
        # def get_data():
        #     api_url = "http://127.0.0.1:5000/api/og/v1/addr/getdata"
        #     response = requests.get(api_url).json()
        #     return response['result']

        # navidf = get_data()
        navidf = pd.read_csv('Clean_Report.csv')

        provinces = list(navidf['PROVINCE'].dropna().unique())
        provinces.insert(0, "All Provinces")
        
        st.sidebar.write("# FILTERS")
        st.sidebar.write("# Select Povince")
        province_list = st.sidebar.multiselect(
        label="Province",
        options=provinces,
        default="All Provinces")

        if "All Provinces" not in province_list and len(province_list) > 0:
            ndf = navidf[navidf['PROVINCE'].isin(province_list)]
        else:
            ndf = navidf.copy()
        
        zip_codes = list(ndf['POSTAL_CODE'].dropna().unique())
        zip_codes.insert(0, "All Zip Codes")
        st.sidebar.write("# Select Zip Code")
        zip_code_list = st.sidebar.multiselect(
        label="Zip Code",
        options=zip_codes,
        default="All Zip Codes")

        if "All Zip Codes" not in zip_code_list and len(zip_code_list) > 0:
            ndf = ndf[ndf['POSTAL_CODE'].isin(zip_code_list)]
        else:
            ndf = ndf.copy()
        
        # Set the initial map location to Madrid, Spain
        initial_center = [40.4168, -3.7038]
        initial_zoom = 5

        # Initialize the map object with the first coordinate in the dataframe
        map = folium.Map(location=[ndf['LAT'].iloc[0], ndf['LONG'].iloc[0]], zoom_start=13)

        # Loop through each coordinate in the mean speed dataframe
        for idx, row in ndf.iterrows():
            lat = row['LAT']
            lon = row['LONG']
            address = row["FORMATED_ADDRESS"]

            # Add a marker for the coordinate with the specified color
            folium.CircleMarker(
                location=[lat, lon],
                radius=5,
                fill=True,
                fill_color='green',
                color='green',
                popup=folium.Popup('Address: '+str(address),max_width=500)
            ).add_to(map)


        # Convert the folium map to HTML
        html_map = map._repr_html_()

        # Display the map in Streamlit
        st.title("Address Map")
        html(html_map, width=700, height=500, scrolling=False)

        st.title("Address Report")
        st.write(ndf)

elif authentication_status == False:
    st.error('Username/password is incorrect')