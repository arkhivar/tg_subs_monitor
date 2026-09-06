import os
import subprocess
import sys
import datetime
from flask import Flask, render_template_string

# Create Flask app
app = Flask(__name__)

# HTML template for the status page
STATUS_PAGE = """
<!DOCTYPE html>
<html data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Reaction Tracker Bot</title>
    <link href="https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css" rel="stylesheet">
    <style>
        .container { padding-top: 2rem; }
        .bot-status { margin-top: 2rem; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Telegram Reaction Tracker Bot</h1>
        
        <div class="card bot-status">
            <div class="card-header">
                <h5>Bot Status</h5>
            </div>
            <div class="card-body">
                <div class="alert alert-success">
                    <strong>Bot is ready</strong>
                    <p>The bot is configured and ready to use!</p>
                    <p>To run the bot from the command line: <code>bash run_telegram_bot.sh</code></p>
                    <p>Current time: {{ current_time }}</p>
                </div>
                
                <div class="alert alert-info mt-3">
                    <strong>Note:</strong> This web interface is only for monitoring and information.
                    The actual bot needs to be run as a separate process.
                </div>
                
                <div class="alert alert-warning mt-3">
                    <strong>Running the Bot:</strong>
                    <p>To run the bot properly in Replit, follow these steps:</p>
                    <ol>
                        <li>Open a new Shell tab in Replit</li>
                        <li>Run the command: <code>./run_telegram_bot.sh</code></li>
                        <li>The bot will start and connect to Telegram</li>
                        <li>Keep this Shell tab open while using the bot</li>
                    </ol>
                </div>
            </div>
        </div>
        
        <div class="card mt-4">
            <div class="card-header">
                <h5>Bot Features</h5>
            </div>
            <div class="card-body">
                <ul class="list-group">
                    <li class="list-group-item">Tracks message reactions</li>
                    <li class="list-group-item">Logs member join/leave events</li>
                    <li class="list-group-item">Provides statistics via commands</li>
                </ul>
            </div>
        </div>
        
        <div class="card mt-4">
            <div class="card-header">
                <h5>Available Commands</h5>
            </div>
            <div class="card-body">
                <table class="table">
                    <thead>
                        <tr>
                            <th>Command</th>
                            <th>Description</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><code>/start</code></td>
                            <td>Start the bot</td>
                        </tr>
                        <tr>
                            <td><code>/help</code></td>
                            <td>Show help information</td>
                        </tr>
                        <tr>
                            <td><code>/stats</code></td>
                            <td>Show reaction statistics</td>
                        </tr>
                        <tr>
                            <td><code>/members</code></td>
                            <td>Show member statistics</td>
                        </tr>
                        <tr>
                            <td><code>/reset</code></td>
                            <td>Reset all data (admin only)</td>
                        </tr>
                        <tr>
                            <td><code>/export</code></td>
                            <td>Export statistics (admin only)</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="card mt-4">
            <div class="card-header">
                <h5>Setup Instructions</h5>
            </div>
            <div class="card-body">
                <ol class="list-group list-group-numbered">
                    <li class="list-group-item">Make sure your BOT_TOKEN is set in the .env file</li>
                    <li class="list-group-item">Add the bot to your Telegram group or channel</li>
                    <li class="list-group-item">Give the bot admin privileges to track member changes</li>
                    <li class="list-group-item">Use the commands listed above to interact with the bot</li>
                </ol>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    """Render bot status page."""
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template_string(STATUS_PAGE, current_time=current_time)

@app.route('/start-bot')
def start_bot():
    """Start the bot as a separate process."""
    # This endpoint could be used in the future to manually start the bot
    return "Bot start endpoint (for future use)"

# The app variable is used by the gunicorn server
