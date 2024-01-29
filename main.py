from time import sleep
from pymongo import MongoClient
from config import Configuration
from ssh_pymongo import MongoSession
import requests
import os
import logging
from retrying import retry
from requests.adapters import HTTPAdapter

# Set up logging
logging.basicConfig(level=logging.INFO)

# Set up connection pooling
session = requests.Session()
session.mount('http://', HTTPAdapter(pool_connections=5, pool_maxsize=10))
session.mount('https://', HTTPAdapter(pool_connections=5, pool_maxsize=10))

@retry(wait_fixed=2000, stop_max_attempt_number=3)
def make_request(url):
    return session.get(url, timeout=(5, 30))

def update_movie(moviedb):
    try:
        all_titles = moviedb.find({"category": "movie", "can_embed": 1}, allow_disk_use=True,
                                  no_cursor_timeout=True, batch_size=2).sort([("releaseDate", -1)])
    except Exception as error:
        logging.error(f'Error fetching data from db: {error}')
        return

    for i, doc in enumerate(all_titles):
        id = doc['_id']
        imdb_id = doc['imdb_id']
        url = f'https://vidsrc.to/embed/movie/{imdb_id}'
        logging.info(f'Processing URL: {url}')

        try:
            res = make_request(url)
            logging.info(f'Response status: {res.status_code}')
            if res.status_code == 200:
                logging.info("Success")
            else:
                moviedb.update_one({"_id": id}, {"$set": {"can_embed": 0}})
                logging.info(f"Updated {id} can_embed to 0")
        except Exception as error:
            logging.error(f'Error making request: {error}')

        if i == 100:
            break

def update_episode(moviedb):
    try:
        all_titles = moviedb.find({"category": "series", "can_embed": 1}, allow_disk_use=True,
                                  no_cursor_timeout=True, batch_size=2).sort([("releaseDate", -1)])
    except Exception as error:
        logging.error(f'Error fetching data from db: {error}')
        return

    for i, doc in enumerate(all_titles):
        id = doc['_id']
        imdb_id = doc['imdb_id']
        
        url = f'https://vidsrc.to/embed/tv/{imdb_id}/1/1'
        logging.info(f'Processing URL: {url}')

        try:
            res = make_request(url)
            logging.info(f'Response status: {res.status_code}')
            if res.status_code == 200:
                logging.info("Success")
            else:
                moviedb.update_one({"_id": id}, {"$set": {"can_embed": 0}})
                logging.info(f"Updated {id} can_embed to 0")
        except Exception as error:
            logging.error(f'Error making request: {error}')

        if i == 100:
            break

if __name__ == "__main__":
    ssh_key_file = os.path.join(os.path.dirname(__file__), Configuration.ssh_file_path)
    db_client = MongoSession(host=Configuration.light_sail_ip, user=Configuration.light_sail_user, key=ssh_key_file)
    db_client.start()
    database = db_client.connection[Configuration.db]
    title_collection = database[Configuration.title_collection]

    try:
        update_episode(title_collection)
        update_movie(title_collection)
    finally:
        # Ensure MongoDB connection is closed
        db_client.stop()
    
