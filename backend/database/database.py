import os
import logging
import json
import torch
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

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

        # Initialize client (or use local files if a connection to MongoDB can't be made)
        self.USE_DATABASE = False
        self.__initialize_database_client(password)
        self.__database = self.__client[database]
        self.__repos = self.__database[repo_collection]
        self.__embeddings = self.__database[embeddings_collection]
        self.__files = self.__database[files_collection]

    def __initialize_database_client(self, password):
        if self.__client is not None:
            return
        
        client = None
        connection_string = (
                f"mongodb+srv://samarkaranch:{password}@cluster0.269ml.mongodb.net/"
                "?retryWrites=true&w=majority&appName=Cluster0"
            )
        
        try:
            client = MongoClient(connection_string)
            self.logger.info("Connected to MongoDB successfully.")
            self.USE_DATABASE = True
        except ConnectionFailure as e:
            self.logger.error(f"Could not connect to MongoDB: {e}")
        
        self.__client = client
    
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

        if not self.USE_DATABASE:
            self.insert_embeddings_localdb(embeddings_document, kwargs)
            return

        self.__embeddings.update_one(
            {'repo_name': embeddings_document['repo_name'], 'owner': embeddings_document['owner']},
            {'$set': embeddings_document},
            kwargs
        )

    def retrive_repo_commit_sha(self, owner, repo_name, **kwargs):
        self.logger.debug(f"Retrieving stored SHA for {owner}/{repo_name}.")

        if not self.USE_DATABASE:
            return self.retrive_repo_commit_sha_localdb(owner, repo_name)
        
        existing_embedding = self.__embeddings.find_one(
            {'repo_name': repo_name, 'owner': owner},
            kwargs,
            sort=[('stored_at', -1)]
        )

        stored_commit_sha = None
        if existing_embedding:
            stored_commit_sha = existing_embedding.get('commit_sha')
        
        return stored_commit_sha
    
    def retrive_repo_commit_sha_localdb(self, owner, repo_name):
        self.logger.debug("Using local filesystem...")
        filename = 'embeddings_records.txt'

        if not os.path.exists(filename):
            self.logger.debug(f"Embeddings records file {filename} does not exist.")
            return None
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                lines = file.readlines()
                for line in reversed(lines):  # Start from the end for the latest entry
                    try:
                        record = json.loads(line)
                        if (record['owner'] == owner and
                                record['repo_name'] == repo_name):
                            self.logger.debug(f"Found matching record: {record}")
                            return record.get('commit_sha')
                    except json.JSONDecodeError:
                        self.logger.warning("Encountered invalid JSON record in embeddings_records.txt.")
                        continue
        except Exception as e:
            self.logger.error(f"Error reading embeddings records file: {e}")
        return None
    
    def insert_embeddings_localdb(self, embeddings_document):
        self.logger.debug("Using local filesystem...")

        filename = 'embeddings_records.txt'
        try:
            # Read existing records
            records = {}
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as file:
                    for line in file:
                        try:
                            record = json.loads(line)
                            key = (record['owner'], record['repo_name'])
                            records[key] = record
                        except json.JSONDecodeError:
                            self.logger.warning("Encountered invalid JSON record in embeddings_records.txt.")
                            continue

            # Update the record for the current repository
            key = (embeddings_document['owner'], embeddings_document['repo_name'])
            records[key] = embeddings_document

            # Write all records back to the file
            with open(filename, 'w', encoding='utf-8') as file:
                for record in records.values():
                    json_record = json.dumps(record)
                    file.write(json_record + '\n')

            self.logger.info('Embeddings stored in text file successfully.')
        except Exception as e:
            self.logger.error(f"Failed to write to embeddings records file: {e}")
            raise

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

        if not self.USE_DATABASE:
            return
        
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