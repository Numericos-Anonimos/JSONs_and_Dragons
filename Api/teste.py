import os

from dotenv import load_dotenv
from gdrive import (
    find_file_by_name,
    get_file_content,
    setup_drive_structure,
    upload_or_update,
)
from jose import jwt

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# Para pegar basta acessar o auth/login e pegar o token da URL. Colocar no .env
jwt_token = os.getenv("JWT_TOKEN")

data = jwt.decode(jwt_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
access_token = data["google_access_token"]

resultado = setup_drive_structure(access_token)
print(resultado)
