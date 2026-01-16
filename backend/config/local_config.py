import os
from dotenv import load_dotenv  # make sure python-dotenv is installed

# Load .env from this backend folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, "..", ".env")
load_dotenv(ENV_PATH)

# Groq API
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
print("DEBUG GROQ_API_KEY length:", len(GROQ_API_KEY))

# Local Storage
PDF_STORAGE_PATH = "./data/resumes_pdf"
VECTOR_DB_PATH = "./data/vector_db"
SQLITE_DB_PATH = "./data/resumes.db"

# Embedding Model
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

os.makedirs(PDF_STORAGE_PATH, exist_ok=True)
os.makedirs(VECTOR_DB_PATH, exist_ok=True)
os.makedirs("./data", exist_ok=True)
