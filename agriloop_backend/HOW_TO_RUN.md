# How to Run AgriLoop AI Backend (MongoDB Edition)

This guide will walk you through setting up and running the AgriLoop AI backend service with MongoDB.

## 1. Prerequisites

*   Python 3.10 or higher
*   `pip` (Python package installer)
*   A MongoDB Atlas account or a local MongoDB server.
*   An ngrok account to expose your local server to the internet for Twilio.

## 2. Installation

```bash
# It is recommended to use a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows
venv\\Scripts\\activate
# On macOS/Linux
source venv/bin/activate

# Install the required dependencies
pip install -r requirements.txt
```

## 3. Configuration

1.  **Create an environment file:**
    In the `agriloop_backend` directory, create a copy of `.env.example` and name it `.env`.

2.  **Fill in your credentials** in the newly created `.env` file:

    *   `GEMINI_API_KEY`: Your API key from Google AI Studio.
    *   `OPENWEATHER_API_KEY`: Your API key from [OpenWeatherMap](https://openweathermap.org/api).
    *   `TWILIO_ACCOUNT_SID`: Your Twilio Account SID from your Twilio Console dashboard.
    *   `TWILIO_AUTH_TOKEN`: Your Twilio Auth Token from your Twilio Console dashboard.
    *   `TWILIO_PHONE_NUMBER`: Your Twilio Phone Number (e.g., `whatsapp:+1234567890`) that is enabled for WhatsApp. This is often your Twilio Sandbox number.
    *   `MONGODB_URL`: Your MongoDB connection string (without the database name).
        *   **For MongoDB Atlas:** `mongodb+srv://<username>:<password>@<cluster-url>`
        *   **For local MongoDB:** `mongodb://localhost:27017`
    *   `MONGODB_DB_NAME`: The name of your database (e.g., `agriloop`).

## 4. Running the Application

Once the dependencies are installed and the `.env` file is configured, you can start the FastAPI server using `uvicorn`.

```bash
# From the agriloop_backend directory
uvicorn app.main:app --reload
```

The server will start, and you can access the API documentation at `http://127.0.0.1:8000/docs`.

## 5. Connecting to Twilio WhatsApp Sandbox

This process remains the same for exposing your local server, but the interaction with the bot is now different due to automated onboarding and multilingual support.

1.  **Expose your local server:**
    ```bash
    ngrok http 8000
    ```

2.  **Configure the Twilio Webhook:**
    *   In your Twilio Console, go to **Messaging > Try it out > Send a WhatsApp message > Sandbox settings**.
    *   Set the "WHEN A MESSAGE COMES IN" field to your ngrok forwarding URL, appending the webhook path `/api/webhook/whatsapp`.
    *   Example: `https://xxxx-xx-xxx-xx-xx.ngrok-free.app/api/webhook/whatsapp`
    *   Ensure the request method is `HTTP POST`.
    *   Save the configuration.

### 6. Test the Automated Onboarding and Multilingual Bot

Now you can interact with the bot. The first time you message it from a new number, it will guide you through registration.

1.  **First Message (Initiate Onboarding):** Send any message to your Twilio Sandbox number (e.g., "Hi"). The bot will respond by asking for your preferred language.
2.  **Choose Language:** Reply with the name of your preferred language (e.g., "Hindi", "English"). The bot will then ask for your name in your chosen language.
3.  **Provide Name:** Reply with your name. The bot will welcome you, and your profile will be created.
4.  **Ask a Question (Multilingual):** Once registered, you can send farming-related questions in your chosen language. For example, in Hindi: `टमाटर के पौधों को कीड़ों से कैसे बचाएं?` (How to protect tomato plants from pests?). The bot will translate your query, process it, and respond in your preferred language.
5.  **Send an Image (Multilingual):** Send a picture of a plant leaf that might have a pest or disease. The AI will analyze it and respond in your chosen language.

You will see the activity logged in your running server terminal each time you send a message.
