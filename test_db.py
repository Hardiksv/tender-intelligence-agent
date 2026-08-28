import os, sys
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()
url = os.environ.get('DATABASE_URL').strip('\"').strip('\'')
print(f'Attempting connection to {url}')
try:
    engine = create_engine(url, connect_args={'connect_timeout': 3})
    with engine.connect() as conn:
        print('Connection successful!')
except Exception as e:
    print(f'Connection failed: {e}')
