import pandas as pd
from sqlalchemy import create_engine
import requests

# URL of the public Google Sheet (replace with your actual sheet's ID)
google_sheet_id = '1yQe_zzrDu31zO5yhMr_0P0DUrSQCywoIKI56NudmIv8'
csv_url = f'https://docs.google.com/spreadsheets/d/{google_sheet_id}/gviz/tq?tqx=out:csv'

# Download the Google Sheet as a CSV
response = requests.get(csv_url)
response.raise_for_status()  # Ensure the request was successful

# Load the CSV into a DataFrame
import io
df = pd.read_csv(io.StringIO(response.text))

# Rename columns for easier handling (optional but recommended)
df.columns = [col.lower().replace(' ', '_') for col in df.columns]

# Convert 'birthdate' to datetime, handling invalid dates (like leap years)
df['birthdate'] = pd.to_datetime(df['birthdate'], errors='coerce')
df['deathdate'] = pd.to_datetime(df['deathdate'], errors='coerce')

# Prepare PostgreSQL connection (replace placeholders with your actual credentials)
engine = create_engine('postgresql://postgres:postgres@localhost:5432/characters')

# # Drop any existing table if it exists
# with engine.connect() as connection:
#     connection.exec_driver_sql("DROP TABLE IF EXISTS characters;")

# with engine.connect() as connection:
#     with open('create table.sql', 'r') as file:
#         create_table_sql = file.read()
#         connection.exec_driver_sql(create_table_sql)

# Save to SQL
df.to_sql('characters', engine, if_exists='replace', index=False)