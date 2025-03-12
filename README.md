# Ladybug Documentation

Ladybug is a project that integrates a Probot GitHub bot with a Flask backend to automate bug localization in your repositories. This guide provides step-by-step instructions to set up and run both components locally.

---

## Table of Contents

-   [Overview](#overview)
-   [Prerequisites](#prerequisites)
-   [Setup](#setup)
    -   [Flask Backend Setup](#flask-backend-setup)
        -   [Initialize Virtual Environment](#initialize-virtual-environment)
        -   [Install Dependencies](#install-dependencies)
        -   [Run the Backend](#run-the-backend)
    -   [Probot Bot Setup](#probot-bot-setup)
        -   [Install Dependencies](#install-dependencies-1)
        -   [Create a GitHub App](#create-a-github-app)
        -   [Run the Bot](#run-the-bot)
-   [Usage](#usage)
-   [Additional Commands](#additional-commands)
    -   [Installing New Python Packages](#installing-new-python-packages)
    -   [Deactivating the Virtual Environment](#deactivating-the-virtual-environment)
-   [Troubleshooting](#troubleshooting)

---

## Overview

Ladybug automates **bug localization** by triggering an analysis whenever a new issue is created in your GitHub repository. The Probot bot listens for new issues, and the Flask backend processes the issue data to provide bug localization results.

---

## Prerequisites

-   **Python 3.x** installed
-   **Node.js** and **npm** installed
-   **Git** installed
-   Access to the GitHub repository where you want to install the bot

---

## Setup

### Flask Backend Setup

#### Initialize Virtual Environment

Create a virtual environment to manage Python dependencies:

```bash
python -m venv myenv
```

Activate the virtual environment:

-   **Windows:**

    ```bash
    myenv\Scripts\activate
    ```

-   **Linux/Mac:**

    ```bash
    source myenv/bin/activate
    ```

#### Install Dependencies

```bash
pip install -r requirements.txt
```

#### Run the Backend

Navigate to the backend directory and start the Flask application:

```bash
cd backend
python index.py
```

### Probot Bot Setup

#### Install Dependencies

Navigate to the Probot directory and install the necessary npm packages:

```bash
cd ../probot
npm install
```

#### Create a GitHub App

1. **Start the Bot Setup**

    ```bash
    npm start
    ```

2. **Register a New GitHub App**

    - Follow the prompts in the terminal.
    - You'll be directed to GitHub to register a new GitHub App.
    - **Important:** When setting up the app, grant access only to the specific repository you intend to use. Do not select all repositories.

3. **Configure Webhooks and Permissions**

    - Set the required webhook URLs and permissions if instructed.
    - The setup process will automatically configure your environment variables.

#### Run the Bot

After setting up the GitHub App, restart the bot to apply the changes:

```bash
npm start
```

---

## Usage

With both the backend and bot running:

-   **Create a New Issue** in the GitHub repository where the bot is installed.
-   The bot will automatically process the issue and **comment with bug localization results**.
-   **Verify Communication:**
    -   Check the terminal running the Flask backend for processing logs.
    -   Check the terminal running the Probot bot for event handling logs.

---

## Additional Commands

### Running Tests

To run tests for the Flask backend:

```bash
cd ladybug
pytest
```

### Installing New Python Packages

To add new packages to the Flask backend:

```bash
pip install <package-name>
pip freeze > requirements.txt
```

### Deactivating the Virtual Environment

After you're done working:

```bash
deactivate
```

---

## Troubleshooting

-   **Bot Doesn't Respond to Issues:**

    -   Ensure the bot is running (`npm start`).
    -   Verify the GitHub App is installed on your repository.
    -   Check webhook configurations in the GitHub App settings.

-   **Backend Errors:**

    -   Confirm all Python dependencies are installed (`pip install -r requirements.txt`).
    -   Make sure the virtual environment is activated before running the backend.

-   **Environment Variable Issues:**
    -   Double-check that environment variables were set during the GitHub App creation.
    -   Restart the bot after any changes to environment variables.
-   **Why is the bot not on marketplace?**
    -   The bot is currently can't be deployed on the marketplace due to the lack of a server to host the bot. Until then, the bot can only be run locally in a development environment.

---
