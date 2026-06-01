from mangum import Mangum
from app import app   # assuming your Flask app instance is named 'app'

handler = Mangum(app)