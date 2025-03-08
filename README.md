# Ladybug Documentation

Ladybug is a project that integrates a Probot GitHub bot with a Flask backend to automate bug localization in your repositories. This guide provides step-by-step instructions to set up and run both components locally.

---

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
  - [Flask Backend Setup](#flask-backend-setup)
    - [Initialize Virtual Environment](#initialize-virtual-environment)
    - [Install Dependencies](#install-dependencies)
    - [Run the Backend](#run-the-backend)
  - [Probot Bot Setup](#probot-bot-setup)
    - [Install Dependencies](#install-dependencies-1)
    - [Create a GitHub App](#create-a-github-app)
    - [Run the Bot](#run-the-bot)
- [Usage](#usage)
- [Red Wing](#red-wing)
- [Additional Commands](#additional-commands)
  - [Running Tests](#running-tests)
  - [Installing New Python Packages](#installing-new-python-packages)
  - [Deactivating the Virtual Environment](#deactivating-the-virtual-environment)
- [Troubleshooting](#troubleshooting)

---

## Overview

Ladybug automates **bug localization** by triggering an analysis whenever a new issue is created in your GitHub repository. The Probot bot listens for new issues, and the Flask backend processes the issue data to provide bug localization results.

---

## Prerequisites

- **Python 3.x** installed  
- **Node.js** and **npm** installed  
- **Git** installed  
- Access to the GitHub repository where you want to install the bot

---

## Setup

### Flask Backend Setup

#### Initialize Virtual Environment

Create a virtual environment to manage Python dependencies:

```bash
python -m venv myenv
```

Activate the virtual environment:

- **Windows:**

    ```bash
    myenv\Scripts\activate
    ```

- **Linux/Mac:**

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

- **Create a New Issue** in the GitHub repository where the bot is installed.
- The bot will automatically process the issue and **comment with bug localization results**.
- **Verify Communication:**
  - Check the terminal running the Flask backend for processing logs.
  - Check the terminal running the Probot bot for event handling logs.

---

## Red Wing

**Red Wing** is a local testing and metrics tool designed specifically for Ladybug. It extrapolates the bug localization pipeline so that users can run any of our 80 test datasets to evaluate the accuracy and metrics of Red Wing in a controlled, local environment.

### What It Does

- **Local Evaluation:**  
  Run a comprehensive analysis on your test datasets. With over 80 datasets available, you can measure how accurately the bug localization pipeline identifies buggy files.

- **Detailed Metrics:**  
  After processing the test datasets, Red Wing outputs detailed metrics (e.g., hits at various thresholds) and writes a summary CSV file with the results.

- **Script Modes:**  
  Choose the desired mode to run your tests:
  - **All Datasets:** Evaluate all test datasets.
  - **Specified Bug IDs:** Provide a list of bug IDs to evaluate specific cases.
  - **Random Selection:** Randomly select a specified number of bugs to test.

- **Progress Tracking:**  
  The tool utilizes Rich's progress bars and tables to provide clear, real-time feedback during processing.

### How to Run Red Wing

1. **Ensure all dependencies are installed.**  
   Follow the Flask backend setup instructions if needed.

2. **Run Red Wing from the command line:**

    ```bash
    python redwing.py -p <REPO_HOME> [ -v ] { -a | -i <bug_ID bug_ID ...> | -r <# of bugs> }
    ```

    **Parameters:**

    - **`-p <REPO_HOME>`**  
      Specifies the path to the repository home containing your test datasets.

    - **Mode Selection (choose one):**
      - **`-a`**  
        Iterate over **all** available test datasets.
      - **`-i <bug_ID bug_ID ...>`**  
        Iterate over the list of specified bug IDs.
      - **`-r <# of bugs>`**  
        Run in random mode, selecting the specified number of bugs to test.

    - **`-v`**  
      *(Optional)* Enables verbose output for detailed debugging information.

3. **Example:**

    ```bash
    python redwing.py -p /path/to/test_datasets -a -v
    ```

    This command processes all test datasets found in `/path/to/test_datasets` and outputs detailed logs along with the final accuracy metrics.

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

- **Bot Doesn't Respond to Issues:**
  - Ensure the bot is running (`npm start`).
  - Verify the GitHub App is installed on your repository.
  - Check webhook configurations in the GitHub App settings.

- **Backend Errors:**
  - Confirm all Python dependencies are installed (`pip install -r requirements.txt`).
  - Make sure the virtual environment is activated before running the backend.

- **Environment Variable Issues:**
  - Double-check that environment variables were set during the GitHub App creation.
  - Restart the bot after any changes to environment variables.

- **Why is the Bot Not on the Marketplace?**
  - Currently, the bot cannot be deployed on the marketplace due to the lack of a production server. It is designed to run locally in a development environment.
 README provides clear instructions for setting up and running both Ladybug and Red Wing while highlighting Red Wing's role as a local evaluation and metrics tool for testing the accuracy of the bug localization pipeline using our extensive test datasets.