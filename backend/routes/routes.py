import logging
import os

from flask import Blueprint, abort, request, jsonify
from dotenv import load_dotenv

from services.initialization_service import initialize
from services.report_service import process_report

# Initialize Blueprint for Routes
routes = Blueprint('routes', __name__)

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# ======================================================================================================================
# Routes
# ======================================================================================================================
@routes.route('/')
def index():
    return "Hello, World!"

@routes.route("/initialization", methods=["POST"])
def initialization():
    """
    Initialization Endpoint:
    - Clones the repository.
    - Computes embeddings.
    - Stores embeddings along with repository information and SHA.
    - Always performs a fresh setup, overwriting any existing embeddings.

    Post Initialization Example:
    POST localhost:5000/initialization
    RAW JSON:
    {
    "repoData": {
        "repo_url": "https://github.com/LadyBugML/ladybug-data-android",
        "owner": "LadyBugML",
        "repo_name": "ladybug-data-android",
        "default_branch": "main",
        "latest_commit_sha": "3b54e17143c9906585fc0df1b4d2a3f969a2de5a"
        }
    } 
    """

    data = request.get_json()
    if not data:
        abort(400, description="Invalid JSON data")

    logger.info("Received data from /initialization request.")
    print(data)
   
    result = initialize(data)

    return result


@routes.route('/report', methods=["POST"])
def report():
    """
    Report Endpoint:
    - Receives repository information with the latest_commit_sha.
    - Writes the 'issue' to ./reports/repo_name/report.txt.
    - Preprocesses the bug report.
    - Checks if the provided SHA matches the stored SHA.
    - If SHAs do not match:
        - Reclones the repository.
        - Recomputes embeddings.
        - Updates the stored embeddings and SHA.
    - If SHAs match:
        - Confirms that embeddings are up to date.
    """

    data = request.get_json()
    if not data:
        abort(400, description="Invalid JSON data")

    result = process_report(data)

    return result