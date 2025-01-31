import os
import logging

from flask import Flask, jsonify
from dotenv import find_dotenv, load_dotenv

from app.api.routes import routes
from database.database import Database

# Load environment variables
load_dotenv(find_dotenv())

def create_app(test_config=None):

    app = Flask(__name__)
    app.register_blueprint(routes)

    # Initializes the client
    db = Database()

    # Configuration Flag: Add USE_DATABASE="False" to your .env to use local file database
    db.USE_DATABASE = os.environ.get("USE_DATABASE", "True").lower() == "true"

    # Initialize logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    @app.route("/", methods=["GET", "POST"])
    def index():
        return jsonify({"message": "Hello, world!"}), 200
    
    # Apply test-specific configurations if any
    if test_config:
        app.config.update(test_config)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host='0.0.0.0', port=5000)