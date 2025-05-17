# GCP Budget Agent

This project contains an AI agent designed to help categorize financial transactions, potentially using Gmail search via the Google Cloud ADK (Agent Development Kit).

## Prerequisites

*   **Git:** To clone the repository.
*   **Python:** Version 3.10 (as specified in `pyproject.toml`). See `.python-version`.
*   **uv:** The Python package manager used in this project. Install via pip: `pip install uv`.
*   **Google Cloud Account:** Access to a Google Cloud project.
*   **Google Workspace Account:** Required for Gmail API access via Domain-Wide Delegation.
*   **Google Workspace Admin Privileges:** Needed *once* during setup to authorize the service account for Domain-Wide Delegation.

## Setup Instructions

Follow these steps to set up the project on a new machine:

1.  **Clone the Repository:**
    ```bash
    git clone <repository-url> # Replace <repository-url> with the actual repo URL
    cd gcp_budget_agent
    ```

2.  **Install Correct Python Version:**
    Ensure you have Python 3.10 installed and available. If you use `pyenv`, you can run `pyenv install` in the project directory.

3.  **Set Up Virtual Environment:**
    Create and activate a virtual environment using `uv`:
    ```bash
    uv venv
    source .venv/bin/activate
    ```

4.  **Install Dependencies:**
    Install the project and its dependencies in editable mode (required for the `deploy-remote` script):
    ```bash
    uv pip install -e .
    ```

5.  **Configure Environment Variables:**
    Create a `.env` file in the project root directory by copying the example below. Fill in your specific Google Cloud details:
    ```dotenv
    # .env
    # Google Cloud Configuration
    GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
    GOOGLE_CLOUD_LOCATION="us-central1" # Or your desired region e.g., europe-west1
    GOOGLE_CLOUD_STAGING_BUCKET="gs://your-gcp-staging-bucket-name" # Bucket must exist
    ```
    *   Replace `your-gcp-project-id` with your Google Cloud project ID.
    *   Replace `us-central1` with the GCP region you want to use (must support Vertex AI Agent Engines).
    *   Replace `gs://your-gcp-staging-bucket-name` with the URI of a Cloud Storage bucket in the *same region* (or a multi-region like `eu` or `us`) that the script can use for staging. Make sure this bucket exists.

6.  **Google Cloud Authentication (Local):**
    Authenticate your local environment using Application Default Credentials (ADC). This allows the Python script to authenticate to GCP services when run locally.
    ```bash
    gcloud auth application-default login
    ```
    Optionally, set your active `gcloud` project configuration (though the script primarily uses the `.env` file):
    ```bash
    gcloud config set project your-gcp-project-id
    ```

7.  **Gmail Tool Setup (Service Account & Domain-Wide Delegation):**
    This is required for the agent to search Gmail using the `search_gmail_for_transactions` tool. It involves creating a service account and authorizing it to act on behalf of a user in your Google Workspace.

    **a. Create Service Account in GCP:**
        *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
        *   Navigate to **IAM & Admin -> Service Accounts**.
        *   Select your project (`your-gcp-project-id`).
        *   Click **+ CREATE SERVICE ACCOUNT**.
        *   Give it a name (e.g., `gmail-budget-agent-reader`) and optional description.
        *   Click **CREATE AND CONTINUE**.
        *   Skip granting roles for now (unless needed for other GCP tasks). Click **CONTINUE**.
        *   Skip granting user access. Click **DONE**.

    **b. Create and Download Service Account Key:**
        *   Click on the email address of the service account you just created.
        *   Go to the **KEYS** tab.
        *   Click **ADD KEY -> Create new key**.
        *   Choose **JSON** key type. Click **CREATE**.
        *   A JSON key file will be downloaded. **This file contains sensitive credentials!**

    **c. Enable Domain-Wide Delegation (Requires Workspace Admin):**
        *   On the service account details page (where you created the key), go back to the **DETAILS** tab.
        *   Expand **Advanced settings**.
        *   Copy the **Client ID** (a large numeric value).
        *   Go to your [Google Workspace Admin Console](https://admin.google.com/) (requires Workspace admin login).
        *   Navigate to **Security -> Access and data control -> API Controls**.
        *   Under **Domain-wide Delegation**, click **MANAGE DOMAIN-WIDE DELEGATION**.
        *   Click **Add new**.
        *   Paste the **Client ID** you copied.
        *   In **OAuth scopes (comma-delimited)**, enter: `https://www.googleapis.com/auth/gmail.readonly`
        *   Click **AUTHORIZE**.

    **d. Place Key File:**
        *   Create a directory named `credentials` in the root of your project.
        *   Move the downloaded JSON key file into this `credentials/` directory.
        *   Rename the key file if desired (e.g., `service-account-key.json`).

    **e. Verify `transaction_categorizer/sub_agents/gmail_agent/gmail_tool.py` Configuration:**
        *   Open the `transaction_categorizer/sub_agents/gmail_agent/gmail_tool.py` file.
        *   This file contains the `SERVICE_ACCOUNT_FILE` and `USER_EMAIL_TO_IMPERSONATE` constants.
        *   Ensure the `SERVICE_ACCOUNT_FILE` constant points to the correct path/filename of your key file within the `credentials/` directory.
        *   Ensure the `USER_EMAIL_TO_IMPERSONATE` constant is set to the **email address of the user whose Gmail inbox the agent should search** (e.g., `'your-email@yourdomain.com'`).
        *   The `.gitignore` file is already configured to ignore the `credentials/` directory, protecting your key file.

## Running the Agent

Make sure your virtual environment is active (`source .venv/bin/activate`).

*   **Run Locally (Using ADK CLI):**
    You can interact with the agent locally for testing using the ADK development UI.
    ```bash
    adk run transaction_categorizer # Or gmail_agent if you renamed the main package
    ```
    Navigate to the URL provided (usually `http://localhost:8000`) in your browser.

*   **Deploy Remotely (Using Helper Script):**
    The `deployment/remote.py` script helps deploy the agent to Vertex AI Agent Engines.
    ```bash
    # Create a new deployment
    deploy-remote --create

    # List existing deployments
    deploy-remote --list

    # Delete a deployment (requires full resource name from --list)
    deploy-remote --delete --resource_id <projects/.../agentEngines/...>

    # Create a session for interacting with a deployed agent
    deploy-remote --create_session --resource_id <projects/.../agentEngines/...>

    # Send a message to a session
    deploy-remote --send --resource_id <...> --session_id <...> --message "Your message here"
    ```
    *Note: The `deploy-remote` command requires the project to be installed via `uv pip install -e .`.*

## Troubleshooting

*   **Authentication Errors:** Double-check ADC (`gcloud auth application-default login`) and ensure the Service Account key file path and Domain-Wide Delegation setup are correct.
*   **API Not Enabled:** Ensure `Vertex AI API` and `Cloud Resource Manager API` are enabled in your GCP project.
*   **Agent Engine Errors (`501`, `404`, etc.):** Check the Agent Engine deployment status and logs in the GCP Console (Vertex AI -> Agent Engines). Ensure you are using the correct region and resource ID.
*   **Tool Not Used:** Ensure the agent's `instruction` prompt clearly guides it on *when* and *how* to use available tools like the Gmail search.
