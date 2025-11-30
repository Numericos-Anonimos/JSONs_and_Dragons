from jose import jwt
import os
from dotenv import load_dotenv
from gdrive import upload_or_update, find_file_by_name

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
jwt_token = os.getenv("JWT_TOKEN")

data = jwt.decode(jwt_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
access_token = data["google_access_token"]


resultado = upload_or_update(access_token, "teste.json", '{"teste":123}')
print(resultado)