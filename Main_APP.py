import logging, os, json
from fastapi import FastAPI, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from typing import List
import uvicorn

# Setup logging
logger = logging.getLogger("package_app")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("app.log"), logging.StreamHandler()]
)

# Constants
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "measurement_db"
COLLECTION_NAME = "measurements"
KEY_FILE = "encryption.key"
PRIVATE_KEY_FILE = "private_key.pem"
PUBLIC_KEY_FILE = "public_key.pem"
ENCRYPTED_FILE = "measurements.json"

# Globals
mongo_client = db = collection = encryption_key = None
app = FastAPI(title="Measurement API")

alpha = {chr(i): i - 96 for i in range(97, 123)}
alpha['_'] = 0

# Init and Utility Functions
def get_fernet():
    global encryption_key
    if os.path.exists(KEY_FILE):
        encryption_key = open(KEY_FILE, 'rb').read()
    else:
        encryption_key = Fernet.generate_key()
        open(KEY_FILE, 'wb').write(encryption_key)
    return Fernet(encryption_key)

def create_rsa_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    with open(PRIVATE_KEY_FILE, 'wb') as priv:
        priv.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()))

    with open(PUBLIC_KEY_FILE, 'wb') as pub:
        pub.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo))

def load_key(path, private=True):
    with open(path, 'rb') as file:
        return serialization.load_pem_private_key(file.read(), None) if private else serialization.load_pem_public_key(file.read())

def encrypt(data: str) -> str:
    key = load_key(PUBLIC_KEY_FILE, private=False)
    return key.encrypt(data.encode(), padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)).hex()

def decrypt(data: str) -> str:
    key = load_key(PRIVATE_KEY_FILE)
    return key.decrypt(bytes.fromhex(data), padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)).decode()

# App Events
@app.on_event("startup")
async def startup():
    global mongo_client, db, collection
    logger.info("App startup initiated.")
    mongo_client = AsyncIOMotorClient(MONGO_URI)
    db = mongo_client[DB_NAME]
    collection = db[COLLECTION_NAME]
    get_fernet()
    if not all(map(os.path.exists, [PRIVATE_KEY_FILE, PUBLIC_KEY_FILE])):
        create_rsa_keys()

@app.on_event("shutdown")
async def shutdown():
    if mongo_client:
        mongo_client.close()
        logger.info("MongoDB client closed.")

# Core Logic
def compute_packages(text: str) -> List[int]:
    result, i = [], 0
    while i < len(text):
        if text[i] == 'z' and i + 1 < len(text):
            package_size = alpha['z'] + alpha[text[i+1]]
            i += 2
        else:
            package_size = alpha.get(text[i], 1)
            i += 1
        total, count = 0, 0
        while count < package_size and i < len(text):
            value = 0
            while i < len(text) and text[i] == 'z':
                value += alpha['z']
                i += 1
            if i < len(text):
                value += alpha.get(text[i], 1)
                i += 1
            total += value
            count += 1
        while count < package_size:
            total += 1
            count += 1
        result.append(total)
    return result

# Routes
@app.get("/convert-measurements/")
async def convert(input: str):
    try:
        result = compute_packages(input)
        encrypted = {"input": encrypt(input), "output": encrypt(json.dumps(result))}
        data = []
        if os.path.exists(ENCRYPTED_FILE):
            with open(ENCRYPTED_FILE, 'r') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    logger.warning("Corrupt or empty encrypted file.")
        data.append(encrypted)
        with open(ENCRYPTED_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return result
    except Exception as e:
        logger.error(f"Failed conversion: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/decrypted-measurements/")
async def decrypted():
    try:
        if not os.path.exists(ENCRYPTED_FILE): return []
        with open(ENCRYPTED_FILE) as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                return []
        return [{"input": decrypt(i['input']), "output": json.loads(decrypt(i['output']))} for i in data]
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise HTTPException(status_code=500, detail="Unable to decrypt data")

@app.get("/measurement-history/")
async def history():
    try:
        return await collection.find().to_list(None)
    except Exception as e:
        logger.error(f"History fetch error: {e}")
        raise HTTPException(status_code=500, detail="History access error")

if __name__ == '__main__':
    uvicorn.run("Main_APP:app", host="0.0.0.0", port=8080)