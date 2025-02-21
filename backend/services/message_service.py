import logging
import os
import queue
import requests
import threading

logger = logging.getLogger(__name__)
message_queue = queue.Queue()
NODE_URL = os.environ.get("NODE_URL") or "http://localhost:3000"

def message_worker():
    """
    Background worker that sends messages to Probot from the message_queue.
    Ensures that each message is sent with at least a 5-second interval.
    """
    while True:
        try:
            # Get the next message from the queue
            owner, repo, comment_id, message = message_queue.get()
            if owner and repo and comment_id and message:
                success = actual_send_update_to_probot(owner, repo, comment_id, message)
                if success:
                    logger.info(f"Message sent to Probot: {message}")
                else:
                    logger.error(f"Failed to send message to Probot: {message}")

        except Exception as e:
            logger.error(f"Error in message_worker: {e}")

def actual_send_update_to_probot(owner, repo, comment_id, message):
    """
    Sends an update message to the Probot /post-message endpoint to comment on a GitHub issue or pull request.

    Args:
        owner (str): The GitHub username or organization name that owns the repository.
        repo (str): The name of the repository.
        comment_id (int): The number of the issue or pull request to comment on.
        message (str): The message to post as a comment.

    Returns:
        bool: True if the comment was posted successfully, False otherwise.
    """
    payload = {
        'owner': owner,
        'repo': repo,
        'comment_id': comment_id,
        'message': message
    }
    try:
        response = requests.post(f'{NODE_URL}/post-message', json=payload)
        response.raise_for_status()  # Raises stored HTTPError, if one occurred.

        logger.info(f"Successfully posted message to {owner}/{repo} Issue #{comment_id}: {message}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to post message to Probot: {e}")
        return False

def send_update_to_probot(owner, repo, comment_id, message):
    """
    Enqueues a message to be sent to Probot.

    Args:
        owner (str): The GitHub username or organization name that owns the repository.
        repo (str): The name of the repository.
        comment_id (int): The number of the issue or pull request to comment on.
        message (str): The message to post as a comment.
    """
    if comment_id == -1:
        return

    message_queue.put((owner, repo, comment_id, message))
    logger.debug(f"Enqueued message for Probot: {message}")

# Start the background worker thread
worker_thread = threading.Thread(target=message_worker, daemon=True)
worker_thread.start()