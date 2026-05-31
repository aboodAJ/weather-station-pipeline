import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Load variables from a .env file (optional but convenient)
load_dotenv()

DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ["DB_NAME"]

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL)

# Download the table
df = pd.read_sql_table("sensors_data", engine)

# Save to CSV
df.to_csv("sensors_data.csv", index=False)

print(f"Exported {len(df)} rows to sensors_data.csv")