import os
import logging
import json
import torch
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv
load_dotenv()

class Database:
    """
    Creates (or references) the MongoDB database connection.

    :param database: The MongoDB database to access. Defaults to `'test'`.
    :param repo_collection: The repository collection name. Defaults to `'repos'`.
    :param embeddings_collection: The embeddings collection name. Defaults to `'embeddings'`.
    """
    _instance = None  # Class-level instance variable for the singleton pattern

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls, *args, **kwargs)
            cls._instance.__client = None
        return cls._instance

    def __init__(self, database='test', repo_collection='repos', embeddings_collection='embeddings', files_collection='files'):
        # Set up basic logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        # Load environment variables
        password = os.environ.get("MONGOPASSWORD")
        if not password:
            raise ValueError("MongoDB password not found in environment variables.")

        self.__initialize_database_client(password)
        self.__database = self.__client[database]
        self.__repos = self.__database[repo_collection]
        self.__embeddings = self.__database[embeddings_collection]
        self.__files = self.__database[files_collection]

    def __initialize_database_client(self, password):
        if self.__client is not None:
            return

        connection_string = (
            f"mongodb+srv://samarkaranch:{password}@cluster0.269ml.mongodb.net/"
            "?retryWrites=true&w=majority&appName=Cluster0"
        )

        try:
            self.__client = MongoClient(connection_string)
            self.logger.info("Connected to MongoDB successfully.")
        except ConnectionFailure as e:
            self.logger.error(f"Could not connect to MongoDB: {e}")

    def get_repo_collection(self):
        """
        Gets the reference to the repository collection on MongoDB.

        :return: The repository collection.
        """
        return self.__repos

    def get_embeddings_collection(self):
        """
        Gets the reference to the embeddings collection on MongoDB.

        :return: The embeddings collection.
        """
        return self.__embeddings

    def get_files_collection(self):
        """
        Gets the reference to the files collection on MongoDB.

        :return: The embeddings collection.
        """
        return self.__files

    def get_repo_files_embeddings(self, repo_id):
        """
        Gets the embeddings for all the files in a repo.

        :return: A list of tuples with (route, embedding).
        """
        embeddings = []
        results = self.__embeddings.find({"repo_id": repo_id})

        for document in results:
            embeddings.append((document.get("route"), document.get("embedding")))

        return embeddings

    def get_corpus_files_embeddings(self, repo_id, corpus: list[str]):
        """
        Retrieves the embeddings for the specified files in a repository.
        
        :param repo_id: The ID of the repository.
        :param corpus: A list of file paths whose embeddings need to be fetched.
        :return: A list of tuples in the format (route, embedding).
        """
        embeddings = []
        
        # Perform a single query to fetch all matching documents
        results = self.__embeddings.find({"repo_id": repo_id, "route": {"$in": corpus}})

        for document in results:
            embeddings.append((document.get("route"), document.get("embedding")))

        # Preserve order and return as tuples
        return embeddings

    def get_repo_file_contents(self, repo_id):
        """
        Gets all source code file contents from a specific repository in the 'files' collection

        Args: 
            repo_id of desired repository

        Returns:
            A list of tuples with the (file_path, file_name, file_contents)
        """

        files = []
        results = self.__files.find({"repo_id": repo_id})

        for document in results:
            file_path = document.get("route")
            file_name = os.path.basename(file_path)
            files.append((file_path, file_name, document.get("code content")))

        return files

    def insert_embeddings_document(self, embeddings_document, **kwargs):
        self.logger.debug("Storing embeddings in database.")
        self.__embeddings.update_one(
            {'repo_name': embeddings_document['repo_name'], 'owner': embeddings_document['owner']},
            {'$set': embeddings_document},
            kwargs
        )

    def retrive_repo_commit_sha(self, owner, repo_name, **kwargs):
        self.logger.debug(f"Retrieving stored SHA for {owner}/{repo_name}.")
        existing_embedding = self.__embeddings.find_one(
            {'repo_name': repo_name, 'owner': owner},
            kwargs,
            sort=[('stored_at', -1)]
        )
        return existing_embedding.get('commit_sha') if existing_embedding else None

    def insert_embeddings(self, owner: str, repo_name: str, commit_sha: str,
                          preprocessed_repository_files: list[tuple[str, str, list[torch.Tensor]]]):
        """
        PLEASE DO NOT USE
        Inserts the embeddings of a repository into the database.

        :param owner: The owner of the repository.

        :param repo_name: The name of the repository.

        :param commit_sha: The commit SHA associated with the preprocessed repository files.

        :param preprocessed_repository_files: A lists of tuples of the form `(filepath, filename, preprocessed_file_contents)`.
        """
        self.logger.debug("Storing repository embeddings in database.")

        filenames = []
        file_embeddings = []
        for filepath, _, embeddings in preprocessed_repository_files:
            filenames.append(filepath)
            file_embeddings.append((filepath, [e.tolist() for e in embeddings]))

        repository_document = {
            'project_name': repo_name,
            'owner': owner,
            'sha': commit_sha,
            'code_files': filenames
        }

        self.__repos.update_one(
            {'repo_name': repo_name, 'owner': owner},
            {'$set': repository_document},
            upsert=True
        )

        for filepath, embeddings in file_embeddings:
            embedding_document = {
                'route': filepath,
                'embeddings': embeddings
            }

            self.__embeddings.update_one(
                {'route': filepath},
                {'$set': embedding_document},
                upsert=True
            )
