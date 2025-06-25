from pymongo import MongoClient
from config import MONGODB_URI

client = MongoClient(MONGODB_URI)
db = client["moviebot"]
collection = db["files"]

def get_files_by_title(title):
    return list(collection.find({"title": {"$regex": f"^{title}", "$options": "i"}}))

def get_files_by_title_and_lang(title, lang):
    return list(collection.find({
        "title": {"$regex": f"^{title}", "$options": "i"},
        "language": lang
    }))
