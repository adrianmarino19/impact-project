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
from ipyleaflet import Map, Marker

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
    st.write(f"Hello {name}!")
    st.write(f"Select any of the following 3 tabs to start to work:")


    # Display menu to navigate the dashboard
    menu = option_menu(
        menu_title = None,
        options = ["Clean Data", "New Address", "Navigation"],
        default_index = 0,
        orientation = "horizontal"
    )


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

            # Opening and performing alterations
            with open(input_file.name, encoding='utf-8') as file:
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

            # Save it as CSV
            ad_orig.to_csv('Add_nosc_csv.csv', index=False, header=True, encoding='utf-8')
            df = pd.read_csv('Add_nosc_csv.csv')


            # ESTA SI
            def type_street(add):
                prefixes = ['CALLE', 'AVENIDA']#, 'CARRETERA']
                # print(type(add))
                for p in prefixes:
                    if str(add).startswith(p):
                        # print(add.startswith(p))
                        # print("TRUE")
                        return p
                return ""

            def remove_prefix(add):
                prefixes = ['CALLE', 'AVENIDA']#, 'CARRETERA']
                # print(type(add))
                for p in prefixes:
                    if str(add).startswith(p):
                        address_parts = str(add).split(maxsplit=1)
                        if len(address_parts) > 1:
                            return address_parts[1]
                return add



            # Create a new column 'Type' based on the prefixes
            df['TYPE_OF_STREET'] = df['ADDRESSES'].apply(type_street)

            # Remove the prefixes from the original 'Street' column
            df['ADDRESSES'] = df['ADDRESSES'].apply(remove_prefix)

            # Move the 'Type' column to the first position
            type_column = df.pop('TYPE_OF_STREET')
            df.insert(0, 'TYPE_OF_STREET', type_column)

            #drop first line that is useless
            df = df.drop(df.index[0])

            # Function to rearrange the neighborhood names
            def rearrange_name(name):
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

            # check if there are any numbers mixed up and fill neighborhood with empty strings

            # Fill NaN values in 'NEIGHBORHOOD' with an empty string
            df['NEIGHBORHOOD'] = df['NEIGHBORHOOD'].fillna('')

            # Filter rows where 'NEIGHBORHOOD' starts with a number
            df_number_start = df[df['NEIGHBORHOOD'].str.startswith(tuple('0123456789'))]

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

            # Replace 'NO ENCONTRADA' with np.nan
            df.replace('no encontrada', np.nan, inplace=True)

            # Define a regular expression pattern to extract numbers preceded by a letter
            pattern = r'(\D)(\d+)'

            # Function to add a space between the last letter and the number
            def add_space_between_letter_and_number(address):
                if isinstance(address, str):  # Check if the value is a string
                    address = re.sub(pattern, r'\1 \2', address)
                return address

            # Apply the function to the 'addresses' column and update the values
            df['addresses'] = df['addresses'].apply(add_space_between_letter_and_number)

            # Define a regular expression pattern to detect a number followed by a letter without a space
            pattern = r'(\d+)(\D)'

            # Function to add a space between the number and the following non-digit character
            def add_space_between_number_and_letter(address):
                if isinstance(address, str):  # Check if the value is a string
                    address = re.sub(pattern, r'\1 \2', address)
                return address

            # Assume 'df' is your DataFrame and 'address' is your address column
            df['addresses'] = df['addresses'].apply(add_space_between_number_and_letter)

            # Define a regular expression pattern to extract the street number, street, and floor
            pattern = r'\b(\d+)\s+(\S+)\s*(.*)'

            # Function to extract the street, street number, and floor from the address
            def extract_address_components(address):
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
            # df[['street', 'street_number', 'floor']] = df['addresses'].apply(extract_address_components).apply(pd.Series)

            # Define a regular expression pattern to extract the street number
            pattern = r'\b(\d+)(?:\s|$)'

            # Function to extract the street number from the address
            def extract_street_number(address):
                if isinstance(address, str):  # Check if the value is a string
                    match = re.search(pattern, address)
                    if match:
                        return match.group(1)
                return ''

            # Apply the function to the 'address' column and create a new column 'street_number'
            df['street_number'] = df['addresses'].apply(extract_street_number)

            # Define a regular expression pattern to extract the street number
            pattern = r'\b(\d+)\b'

            # Function to extract the street number from the address
            def extract_street_number2(address):
                if isinstance(address, str):  # Check if the value is a string
                    matches = re.findall(pattern, address)
                    if matches:
                        return ' '.join(matches)
                return ''

            # Apply the function to the 'address' column and create a new column 'street_number'
            # df['street_number'] = df['addresses'].apply(extract_street_number)
            df['street_number'] = df.apply(lambda row: extract_street_number2(row['addresses']) if row['street_number'] == '' else row['street_number'], axis=1)

            # Convert all addresses to string type
            df['addresses'] = df['addresses'].astype(str)

            # Assuming df is your DataFrame and 'addresses' is the column with the full address
            df['street_name'] = df['addresses'].apply(lambda x: ' '.join(re.findall(r'[^\d]+', x.split(',')[0])).strip())
            # df['house_number'] = df['addresses'].apply(lambda x: ' '.join(re.findall(r'\d+', x.split(',')[0])).strip())

            # Assuming that floor number is represented as 'nd'
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
                address_without_numbers = re.sub(r'N°|\b\d+\b', '', address)
                return address_without_numbers.strip()
            df['street_name2'] = df['street_name2'].apply(lambda x: remove_numbers(x))

            def remove_nnd(address):
                address_without_nnd = re.sub(r' nnd$| nnd ', '', address, flags=re.IGNORECASE)
                return address_without_nnd.strip()

            df['street_name2'] = df['street_name2'].apply(lambda x: remove_nnd(x))

            def remove_nd(address):
                address_without_nnd = re.sub(r' nd$| nd ', '', address, flags=re.IGNORECASE)
                return address_without_nnd.strip()

            df['street_name2'] = df['street_name2'].apply(lambda x: remove_nd(x))

            def remove_parentheses(address):
                address_without_parentheses = re.sub(r'\((.*)\)', '', address)
                return address_without_parentheses.strip()

            df['street_name2'] = df['street_name2'].apply(lambda x: remove_parentheses(x))

            return df
        

        # Function to download the file
        def get_csv_download_link(df):
            csv = df.to_csv(index=False)
            b64 = base64.b64encode(csv.encode()).decode()  # Encoding the CSV data
            href = f'<a href="data:file/csv;base64,{b64}" download="transformed_data.csv">Click here to download the CSV file</a>'
            return href


        # STREAMLIT - File upload section
        st.header("Upload CSV File")
        uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

        if uploaded_file is not None:
            # Perform CSV transformation
            df = transform_csv(uploaded_file)

            # Show transformed data
            st.header("Transformed Data")
            st.write(df)

            # Download link for the transformed CSV file
            st.header("Download Transformed CSV")
            csv_download_link = get_csv_download_link(df)
            st.markdown(csv_download_link, unsafe_allow_html=True)
    
        # Button to save clean addresses
        if st.button("Save clean addresses"):
            # Connect to the database and store the clean addresses
            api_url = "https://api.example.com/save_clean_addresses"
            response = requests.post(api_url, json=df.to_dict(orient="records"))

            if response.status_code == 200:
                st.success("Clean addresses saved successfully!")
            else:
                st.error("Failed to save clean addresses. Please try again.")


    if menu == "New Address":
        # OpenStreetMap API endpoint
        API_ENDPOINT = "https://nominatim.openstreetmap.org/search"

        # Function to make API request and retrieve address details
        def get_address_details(street_type, street_name, street_number, inner_number, neighborhood, district_name, zip_code, city, province, country):
            query_params = {
                "street": f"{street_type} {street_name} #{street_number}",
                "neighbourhood": f"{neighborhood},",
                "district": f"{district_name},",
                "city": f"{city},",
                "county": f"{province},",
                "postalcode": f"{zip_code},",
                "country": f"{country},",
                "format": "json"
            }

            response = requests.get(API_ENDPOINT, params=query_params)
            if response.status_code == 200 and len(response.json()) > 0:
                result = response.json()[0]
                return result["display_name"]
            else:
                return "Address not found."

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
        neighborhood = st.text_input("Neighborhood")
        district_name = st.text_input("District / Municipality")
        zip_code = st.number_input("Zip Code", value=0, step=1)
        city = st.text_input("City")
        province = st.text_input("Province")
        country = st.text_input("Country")

        if st.button("Validate Address"):
            address = get_address_details(street_type, street_name, street_number, inner_number, neighborhood, district_name, zip_code, city, province, country)
            st.write("OK:", address)

        if st.button("Save Address"):
            save_address(get_address_details(street_type, street_name, street_number, inner_number, neighborhood, district_name, zip_code, city, province, country))
            st.write("Address confirmed and saved:", address)
            
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
        # Set the initial map location to Madrid, Spain
        initial_center = [40.4168, -3.7038]
        initial_zoom = 5

        # Create a map centered at the initial coordinates
        m = folium.Map(location=initial_center, zoom_start=initial_zoom)

        # Get user input for new coordinates
        user_coordinates = st.text_input("Enter coordinates (latitude, longitude):")

        # Parse user input into latitude and longitude
        try:
            latitude, longitude = [float(coord.strip()) for coord in user_coordinates.split(",")]
            # Add a marker at the user-specified location
            folium.Marker(location=[latitude, longitude], tooltip='User Location').add_to(m)
        except:
            st.warning("Invalid input. Please enter coordinates in the format 'latitude, longitude'.")

        # Convert the folium map to HTML
        html_map = m._repr_html_()

        # Display the map in Streamlit
        html(html_map, width=700, height=500, scrolling=False)



elif authentication_status == False:
    st.error('Username/password is incorrect')