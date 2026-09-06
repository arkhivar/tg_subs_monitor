# tg_subs_monitor

This project provides a Telegram bot that tracks and maintains subscriber data using Grist as a dynamic, real-time database platform. The application captures comprehensive subscriber lifecycle events with advanced logging and tracking capabilities.

## Features

- Tracks when users join, leave, or rejoin a channel (maintaining historical data)
- Records user reactions with reaction counts and last reaction timestamp
- Provides a web interface to view bot status and subscriber statistics
- Integrates with Grist for reliable structured data storage

## Environment Setup

This application requires the following environment variables to be set:

- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
- `GRIST_API_KEY`: API key for Grist
- `GRIST_DOC_ID`: Document ID for your Grist document

## Grist Database Configuration

The application uses Grist for database storage. You need to create a table with the following structure in your Grist document:

### Table Structure

The table must have these columns:

- `user_id` (Text): Telegram user ID
- `username` (Text): Telegram username
- `first_name` (Text): User's first name
- `last_name` (Text): User's last name
- `join_date` (Date): When user first joined
- `leave_date` (Date): When user left (if applicable)
- `rejoin_date` (Date): When user rejoined (if applicable)
- `current_status` (Text): Current status ('active' or 'inactive')
- `reaction_counter` (Numeric): Count of reactions
- `last_reacted` (Date): Timestamp of last reaction
- `is_admin` (Toggle): Whether user is an admin

### Important Note on Table Names

In Grist, there's a difference between the display name shown in the UI and the API name used in code:

- The display name in the UI might be "subscribers"
- The API name could be "Table1" (or something else)

The application is configured to use the API name, not the display name. This is set in `config.py`:

```python
GRIST_TABLE_NAME = "Table1"  # Important: This is the API name, not the display name "subscribers"
```

If you need to change this, you can find the API name by looking at the Grist Data API documentation or by examining the "Raw Data Tables" section in your Grist document.

## Webhook Configuration

To receive real-time updates from Telegram, you need to set up a webhook. This requires:

1. A publicly accessible HTTPS URL for your application
2. Setting this URL as the webhook for your Telegram bot

You can set up the webhook using the `/set-webhook` endpoint of this application.

## Running the Application

To start the application:

```
gunicorn --bind 0.0.0.0:5000 main:app
```

## Troubleshooting

If you're not seeing updates when users join or leave:

1. Check that the webhook is properly set up (`/webhook-info` endpoint)
2. Verify that your bot has the necessary permissions in the channel
3. Make sure the table name in `config.py` matches the actual API name in Grist
4. Look at the application logs for error messages

## Available Routes

- `/`: Main status page
- `/webhook`: Webhook endpoint for Telegram updates
- `/set-webhook`: Set up the Telegram webhook
- `/remove-webhook`: Remove the Telegram webhook
- `/bot-info`: Get information about the bot
- `/debug-records`: View records in the Grist database (for debugging)