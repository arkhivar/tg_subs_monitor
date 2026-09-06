import os
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template
import config
import telegram
from telegram.ext import Application
from telegram_bot import bot, application
from grist_simple_client import GristSimpleClient

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
# Avoid logging authorization-bearing request URLs from Telegram's HTTP stack.
for noisy_logger in ('httpx', 'httpcore', 'telegram'):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")

# Initialize Grist client
db_client = GristSimpleClient()
db_client.init_table()

# The application is already initialized in telegram_bot.py

@app.route('/debug-webhook', methods=['POST'])
def debug_webhook():
    """Debug endpoint to see raw webhook data from Telegram."""
    update_data = request.get_json()
    if update_data:
        logger.warning(f"RAW WEBHOOK DEBUG: {update_data}")
        
        # Check for reaction-specific data
        if 'message_reaction' in update_data:
            logger.warning(f"REACTION FOUND: {update_data['message_reaction']}")
        elif 'message_reaction_count' in update_data:
            logger.warning(f"REACTION COUNT FOUND: {update_data['message_reaction_count']}")
        
        return jsonify({"status": "debug received"})
    return jsonify({"status": "no data"})

@app.route('/')
def index():
    """Render the bot status page."""
    try:
        # Get all subscribers from Grist
        all_subscribers = db_client.get_all_subscribers()
        
        # Process the data - make sure we have proper dict objects
        processed_subscribers = []
        for sub in all_subscribers:
            if isinstance(sub, dict):
                processed_subscribers.append(sub)
            elif hasattr(sub, '__dict__'):
                processed_subscribers.append(dict(sub))
        
        # Now filter active and inactive subscribers from the processed list
        active_subscribers = [s for s in processed_subscribers if s.get('current_status') == 'active']
        inactive_subscribers = [s for s in processed_subscribers if s.get('current_status') == 'inactive']
        
        # Calculate statistics
        total_count = len(active_subscribers) + len(inactive_subscribers)
        
        # Handle reaction counter - safely get integer values
        def safe_get_reaction(sub):
            try:
                return int(sub.get('reaction_counter', 0))
            except (ValueError, TypeError):
                return 0
                
        total_reactions = sum(safe_get_reaction(s) for s in processed_subscribers)
        
        # Count recent joins (those that joined in the last 7 days)
        from datetime import datetime, timedelta
        one_week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        
        def is_recent_join(sub):
            try:
                join_date = sub.get('join_date', '')
                if join_date and isinstance(join_date, str):
                    return join_date > one_week_ago
                return False
            except Exception:
                return False
                
        recent_joins = sum(1 for s in active_subscribers if is_recent_join(s))
        
        # Prepare the stats for the template
        display_stats = {
            'active_count': len(active_subscribers),
            'inactive_count': len(inactive_subscribers),
            'total_count': total_count,
            'total_reactions': total_reactions,
            'recent_joins': recent_joins
        }
        
        logger.info(f"Stats prepared: {display_stats}")
        
    except Exception as e:
        logger.error(f"Error preparing stats: {e}")
        display_stats = {
            'active_count': 0,
            'inactive_count': 0,
            'total_count': 0,
            'total_reactions': 0,
            'recent_joins': 0,
            'error': str(e)
        }
    
    return render_template('index.html', stats=display_stats)

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle webhook requests from Telegram."""
    try:
        # Import the webhook handler from our dedicated module
        from telegram_grist_webhook import handle_telegram_update
        
        if request.method == 'POST':
            # Get the update from Telegram
            update_json = request.get_json()
            
            # Enhanced logging for webhook debugging
            if update_json:
                logger.info(f"Received webhook with update type: {list(update_json.keys())}")
                
                # Log specific event types for easier debugging
                if 'message' in update_json:
                    msg = update_json['message']
                    logger.info(f"Message from {msg.get('from', {}).get('id')} in chat {msg.get('chat', {}).get('id')}")
                elif 'my_chat_member' in update_json:
                    chat_member = update_json['my_chat_member']
                    logger.info(f"Chat member update in {chat_member.get('chat', {}).get('title', 'unknown')} from user {chat_member.get('from', {}).get('id')}")
                    logger.info(f"Status change: {chat_member.get('old_chat_member', {}).get('status')} -> {chat_member.get('new_chat_member', {}).get('status')}")
            
            # Process the update using the dedicated handler
            result = handle_telegram_update(update_json)
            logger.info(f"Processed webhook update: {result}")
            
            # Queue for async processing if needed
            try:
                from threading import Thread
                thread = Thread(target=lambda: application.update_queue.put_nowait(update_json))
                thread.daemon = True
                thread.start()
            except Exception as e:
                logger.error(f"Error queuing update: {e}")
            
            return jsonify(result)
        else:
            return jsonify({'status': 'error', 'message': 'Method not allowed'}), 405
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get-updates', methods=['GET'])
def get_updates():
    """
    Manually fetch and process pending updates from Telegram.
    This is useful when webhook isn't set up properly.
    """
    try:
        # Run the async operation synchronously
        import asyncio
        async def fetch_updates_async():
            try:
                # Get pending updates
                from telegram_grist_webhook import handle_telegram_update
                
                # Get updates with a 30 second timeout (long polling)
                updates = await application.bot.get_updates(timeout=1, allowed_updates=[
                    "message", "edited_message", "channel_post", "edited_channel_post", 
                    "message_reaction", "message_reaction_count", "chat_member", "my_chat_member"
                ])
                
                # Process each update
                processed_count = 0
                success_count = 0
                for update in updates:
                    update_dict = update.to_dict()
                    logger.info(f"Processing update: {update.update_id}, type: {list(update_dict.keys())}")
                    
                    # Process the update
                    result = handle_telegram_update(update_dict)
                    if result.get('status') == 'success':
                        success_count += 1
                    
                    processed_count += 1
                    
                    # Acknowledge the update to avoid processing it again
                    await application.bot.get_updates(offset=update.update_id + 1)
                
                return {
                    'status': 'success',
                    'updates_count': len(updates),
                    'processed_count': processed_count,
                    'success_count': success_count
                }
            except Exception as e:
                logger.error(f"Error fetching updates: {e}")
                return {
                    'status': 'error',
                    'message': str(e)
                }
                
        # Run the async function in a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = {'status': 'processing'}
        try:
            result = loop.run_until_complete(fetch_updates_async())
        finally:
            loop.close()
            
        # Return the result
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting updates: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/grist-status', methods=['GET'])
def grist_status():
    """Get Grist connection status."""
    try:
        # Check if the table exists
        init_result = db_client.init_table()
        
        # Try to get subscriber count
        try:
            subscribers = db_client.get_all_subscribers()
            count = len(subscribers)
        except Exception as e:
            count = 0
            logger.error(f"Error getting subscribers: {e}")
        
        return jsonify({
            'status': 'success' if init_result else 'warning',
            'message': 'Grist table is ready' if init_result else 'Grist table needs to be created manually',
            'subscriber_count': count
        })
    except Exception as e:
        logger.error(f"Error checking Grist status: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def process_telegram_update(update_data):
    """
    Process a Telegram update and store subscriber activity in Grist.
    
    Args:
        update_data: Dict containing the Telegram update
    
    Returns:
        bool: Success status
    """
    try:
        logger.info(f"Processing Telegram update: {update_data}")
        
        # Check for new chat members (join event)
        if 'message' in update_data and 'new_chat_members' in update_data['message']:
            chat = update_data['message'].get('chat', {})
            chat_id = chat.get('id')
            chat_type = chat.get('type')
            # Only process updates from channels or supergroups
            logger.info(f"Received new chat members event for chat {chat_id} of type {chat_type}")
            
            if chat_type in ['channel', 'supergroup', 'group']:
                for member in update_data['message']['new_chat_members']:
                    user_id = str(member.get('id'))
                    username = member.get('username', '')
                    logger.info(f"Adding new subscriber: user_id={user_id}, username={username}")
                    
                    user_data = {
                        'user_id': user_id,
                        'username': username,
                        'first_name': member.get('first_name', ''),
                        'last_name': member.get('last_name', ''),
                        'join_date': datetime.now().isoformat(),
                        'current_status': 'active'
                    }
                    success = db_client.add_subscriber(user_data)
                    logger.info(f"Add subscriber result: {success}")
            
            return True
        
        # Check for left chat member (leave event)
        elif 'message' in update_data and 'left_chat_member' in update_data['message']:
            chat = update_data['message'].get('chat', {})
            chat_id = chat.get('id')
            chat_type = chat.get('type')
            # Only process updates from channels or supergroups
            logger.info(f"Received left chat member event for chat {chat_id} of type {chat_type}")
            
            if chat_type in ['channel', 'supergroup', 'group']:
                member = update_data['message']['left_chat_member']
                user_id = str(member.get('id'))
                username = member.get('username', '')
                logger.info(f"Updating subscriber leave: user_id={user_id}, username={username}")
                
                success = db_client.update_subscriber_leave(user_id)
                logger.info(f"Update leave result: {success}")
            
            return True
        
        # Check for my_chat_member updates (join/leave events from bot perspective)
        elif 'my_chat_member' in update_data:
            chat = update_data['my_chat_member'].get('chat', {})
            chat_id = chat.get('id')
            chat_type = chat.get('type')
            new_status = update_data['my_chat_member'].get('new_chat_member', {}).get('status')
            old_status = update_data['my_chat_member'].get('old_chat_member', {}).get('status')
            
            logger.info(f"Received my_chat_member update for chat {chat_id}, status change from {old_status} to {new_status}")
            
            # This usually means a member was added/removed by admin rather than themselves
            if new_status in ['member', 'administrator'] and old_status in ['left', 'kicked']:
                # Someone added the user to the chat
                user = update_data['my_chat_member'].get('from', {})
                user_id = str(user.get('id'))
                username = user.get('username', '')
                
                logger.info(f"User was added to chat: user_id={user_id}, username={username}")
                
                user_data = {
                    'user_id': user_id,
                    'username': username,
                    'first_name': user.get('first_name', ''),
                    'last_name': user.get('last_name', ''),
                    'join_date': datetime.now().isoformat(),
                    'current_status': 'active'
                }
                success = db_client.add_subscriber(user_data)
                logger.info(f"Add subscriber result: {success}")
                
            elif new_status in ['left', 'kicked'] and old_status in ['member', 'administrator']:
                # Someone removed the user from the chat
                user = update_data['my_chat_member'].get('from', {})
                user_id = str(user.get('id'))
                username = user.get('username', '')
                
                logger.info(f"User was removed from chat: user_id={user_id}, username={username}")
                
                success = db_client.update_subscriber_leave(user_id)
                logger.info(f"Update leave result: {success}")
            
            return True
        
        # Check for chat_member updates (status changes for regular members)
        elif 'chat_member' in update_data:
            chat = update_data['chat_member'].get('chat', {})
            chat_id = chat.get('id')
            chat_type = chat.get('type')
            new_status = update_data['chat_member'].get('new_chat_member', {}).get('status')
            old_status = update_data['chat_member'].get('old_chat_member', {}).get('status')
            
            logger.info(f"Received chat_member update for chat {chat_id}, status change from {old_status} to {new_status}")
            
            if new_status in ['member', 'administrator'] and old_status in ['left', 'kicked']:
                # Member joined
                member = update_data['chat_member'].get('new_chat_member', {})
                user = member.get('user', {})
                user_id = str(user.get('id'))
                username = user.get('username', '')
                
                logger.info(f"Member joined: user_id={user_id}, username={username}")
                
                user_data = {
                    'user_id': user_id,
                    'username': username,
                    'first_name': user.get('first_name', ''),
                    'last_name': user.get('last_name', ''),
                    'join_date': datetime.now().isoformat(),
                    'current_status': 'active'
                }
                success = db_client.add_subscriber(user_data)
                logger.info(f"Add subscriber result: {success}")
                
            elif new_status in ['left', 'kicked'] and old_status in ['member', 'administrator']:
                # Member left
                member = update_data['chat_member'].get('old_chat_member', {})
                user = member.get('user', {})
                user_id = str(user.get('id'))
                username = user.get('username', '')
                
                logger.info(f"Member left: user_id={user_id}, username={username}")
                
                success = db_client.update_subscriber_leave(user_id)
                logger.info(f"Update leave result: {success}")
            
            return True
        
        # Check for message reactions
        elif 'message_reaction' in update_data:
            chat = update_data['message_reaction'].get('chat', {})
            chat_id = chat.get('id')
            chat_type = chat.get('type')
            
            logger.info(f"Received message_reaction for chat {chat_id} of type {chat_type}")
            
            if chat_type in ['channel', 'supergroup', 'group']:
                user = update_data['message_reaction'].get('user', {})
                if user:
                    user_id = str(user.get('id'))
                    username = user.get('username', '')
                    
                    logger.info(f"Updating reaction count: user_id={user_id}, username={username}")
                    
                    success = db_client.update_reaction_count(user_id)
                    logger.info(f"Update reaction result: {success}")
            
            return True
        
        # Check for message_reaction_count
        elif 'message_reaction_count' in update_data:
            chat = update_data['message_reaction_count'].get('chat', {})
            chat_id = chat.get('id')
            chat_type = chat.get('type')
            
            logger.info(f"Received message_reaction_count for chat {chat_id} of type {chat_type}")
            logger.info("Cannot process message_reaction_count as it doesn't include user information")
            
            return True
        
        # Unknown update type
        else:
            logger.info(f"No relevant events found in update: {update_data}")
            return True
        
    except Exception as e:
        logger.error(f"Error processing Telegram update: {e}")
        return False

@app.route('/set-webhook', methods=['GET'])
def set_webhook():
    """Setup webhook for the Telegram bot."""
    try:
        # Try to get the webhook URL from the request parameters first, then fall back to env
        webhook_url = request.args.get('url') or os.environ.get('WEBHOOK_URL')
        if not webhook_url:
            return jsonify({
                'status': 'error', 
                'message': 'WEBHOOK_URL not provided. Please provide a webhook URL by adding ?url=YOUR_URL to this request or set WEBHOOK_URL environment variable.'
            }), 400
            
        # Add /webhook to the URL if it doesn't already have it
        if not webhook_url.endswith('/webhook'):
            webhook_url = webhook_url.rstrip('/') + '/webhook'
        
        # Run the async operation synchronously
        import asyncio
        import telegram
        
        # Create a fresh bot instance to avoid event loop issues
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        bot = telegram.Bot(token=token)
        
        async def set_webhook_async():
            try:
                # In v20+, we need to specify which update types we want to receive
                await bot.set_webhook(
                    url=webhook_url,
                    allowed_updates=["message", "edited_message", "channel_post", "edited_channel_post", 
                                    "message_reaction", "message_reaction_count", "chat_member", "my_chat_member"]
                )
                logger.info(f"Webhook set successfully to {webhook_url}")
                
                # Get webhook info to verify
                webhook_info = await bot.get_webhook_info()
                webhook_data = {
                    'url': webhook_info.url,
                    'has_custom_certificate': webhook_info.has_custom_certificate,
                    'pending_update_count': webhook_info.pending_update_count,
                    'allowed_updates': webhook_info.allowed_updates or []
                }
                
                return {
                    'status': 'success',
                    'message': f'Webhook set successfully to {webhook_url}',
                    'webhook_url': webhook_url,
                    'webhook_info': webhook_data
                }
            except Exception as e:
                logger.error(f"Error setting webhook: {e}")
                return {
                    'status': 'error',
                    'message': str(e),
                    'webhook_url': webhook_url
                }
        
        # Create and use a fresh event loop
        result = asyncio.run(set_webhook_async())
        
        # Return the result
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/remove-webhook', methods=['GET'])
def remove_webhook():
    """Remove the webhook for the Telegram bot."""
    try:
        # Run the async operation synchronously
        import asyncio
        import telegram
        
        # Create a fresh bot instance to avoid event loop issues
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        bot = telegram.Bot(token=token)
        
        async def remove_webhook_async():
            try:
                # Remove the webhook
                await bot.delete_webhook()
                logger.info("Webhook removed successfully")
                
                # Get webhook info to verify
                webhook_info = await bot.get_webhook_info()
                webhook_data = {
                    'url': webhook_info.url,
                    'has_custom_certificate': webhook_info.has_custom_certificate,
                    'pending_update_count': webhook_info.pending_update_count
                }
                
                return {
                    'status': 'success',
                    'message': 'Webhook removed successfully',
                    'webhook_info': webhook_data
                }
            except Exception as e:
                logger.error(f"Error removing webhook: {e}")
                return {
                    'status': 'error',
                    'message': str(e)
                }
        
        # Create and use a fresh event loop
        result = asyncio.run(remove_webhook_async())
        
        # Return the result
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error removing webhook: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/bot-info', methods=['GET'])
def bot_info():
    """Get information about the bot."""
    try:
        # Run the async operation synchronously
        import asyncio
        import telegram
        
        # Create a fresh bot instance to avoid event loop issues
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        bot = telegram.Bot(token=token)
        
        async def get_bot_info_async():
            try:
                # Get bot info using a fresh bot instance 
                bot_user = await bot.get_me()
                
                # Get webhook info as well
                webhook_info = await bot.get_webhook_info()
                logger.info(f"Webhook URL: {webhook_info.url}")
                logger.info(f"Pending update count: {webhook_info.pending_update_count}")
                
                # Format the data for the response
                bot_data = {
                    'id': bot_user.id,
                    'username': bot_user.username,
                    'first_name': bot_user.first_name,
                    'is_bot': bot_user.is_bot,
                    'webhook_url': webhook_info.url,
                    'pending_updates': webhook_info.pending_update_count,
                    'allowed_updates': webhook_info.allowed_updates
                }
                
                return {
                    'status': 'success',
                    'bot_info': bot_data
                }
            except Exception as e:
                logger.error(f"Error in get_bot_info_async: {e}")
                return {
                    'status': 'error',
                    'message': str(e)
                }
        
        # Create and use a fresh event loop
        result = asyncio.run(get_bot_info_async())
            
        # Return the result
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting bot info: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/webhook-info', methods=['GET'])
def webhook_info():
    """Get information about the webhook setup."""
    try:
        # Run the async operation synchronously
        import asyncio
        import telegram
        
        # Create a fresh bot instance to avoid event loop issues
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        bot = telegram.Bot(token=token)
        
        async def get_webhook_info_async():
            try:
                # Get webhook info using a fresh bot instance
                webhook_info = await bot.get_webhook_info()
                
                # Extract info from the webhook
                webhook_data = {
                    'url': webhook_info.url,
                    'has_custom_certificate': webhook_info.has_custom_certificate,
                    'pending_update_count': webhook_info.pending_update_count,
                    'max_connections': webhook_info.max_connections,
                    'allowed_updates': webhook_info.allowed_updates or [],
                    'ip_address': webhook_info.ip_address,
                    'last_error_date': webhook_info.last_error_date,
                    'last_error_message': webhook_info.last_error_message,
                    'last_sync_error_date': webhook_info.last_synchronization_error_date
                }
                
                logger.info(f"Retrieved webhook info: {webhook_data}")
                return {
                    'status': 'success',
                    'webhook_info': webhook_data
                }
            except Exception as e:
                logger.error(f"Error getting webhook info: {e}")
                return {
                    'status': 'error',
                    'message': str(e)
                }
                
        # Create and use a fresh event loop
        result = asyncio.run(get_webhook_info_async())
            
        # Return the result
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting webhook info: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/test-leave', methods=['GET'])
def test_leave():
    """Test function to simulate a leave event."""
    try:
        # Create a simulated leave event
        test_user_id = "12345678"  # Use your own Telegram ID for testing
        logger.info(f"Testing leave event for user_id: {test_user_id}")
        
        # Simulate updating the database
        result = db_client.update_subscriber_leave(test_user_id)
        
        return jsonify({
            'status': 'success' if result else 'error',
            'message': f'Leave event simulated for user {test_user_id}. Result: {result}'
        })
    except Exception as e:
        logger.error(f"Error simulating leave event: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
        
@app.route('/debug-records', methods=['GET'])
def debug_records():
    """Debug endpoint to see what records are in the Grist table."""
    try:
        # Get all records from the Grist table
        all_records = db_client.get_all_subscribers()
        
        # Process the records for display
        processed_records = []
        for record in all_records:
            if isinstance(record, dict):
                processed_records.append(record)
            elif hasattr(record, '__dict__'):
                processed_records.append(dict(record))
        
        # Return the full data for debugging
        return jsonify({
            'status': 'success',
            'count': len(processed_records),
            'records': processed_records
        })
    except Exception as e:
        logger.error(f"Error debugging records: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/test-join', methods=['GET'])
def test_join():
    """Test function to simulate a join event."""
    try:
        # Create a simulated join event
        test_user_id = "12345678"  # Use your own Telegram ID for testing
        test_username = "test_user"
        logger.info(f"Testing join event for user_id: {test_user_id}")
        
        # Create a user data object
        user_data = {
            'user_id': test_user_id,
            'username': test_username,
            'first_name': 'Test',
            'last_name': 'User',
            'join_date': datetime.now().isoformat(),
            'current_status': 'active'
        }
        
        # Simulate updating the database
        result = db_client.add_subscriber(user_data)
        
        return jsonify({
            'status': 'success' if result else 'error',
            'message': f'Join event simulated for user {test_user_id}. Result: {result}'
        })
    except Exception as e:
        logger.error(f"Error simulating join event: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/sync-subscribers', methods=['GET'])
def sync_subscribers():
    """Manually trigger a sync of all subscribers."""
    try:
        chat_id = os.environ.get("TELEGRAM_CHANNEL_ID") or "@nochacha"
        
        # Start synchronization in a background thread
        def async_sync_subscribers():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Coroutine to sync subscribers
                async def _sync_subscribers():
                    try:
                        # Get admins with timeout handling
                        admins = await bot.get_chat_administrators(chat_id)
                        admins_count = len(admins)
                        
                        added_count = 0
                        updated_count = 0
                        
                        # Process admins
                        for admin in admins:
                            user = admin.user
                            user_id = user.id
                            
                            if user.is_bot:
                                continue
                                
                            # Check if user already exists
                            existing_user = db_client.get_subscriber(user_id)
                            
                            if existing_user:
                                # Update as active if previously inactive
                                if existing_user.get('current_status') != 'active':
                                    db_client.update_subscriber_rejoin(user_id, existing_user.get('id'))
                                    updated_count += 1
                            else:
                                # Add new subscriber
                                user_data = {
                                    'id': user_id,
                                    'username': user.username,
                                    'first_name': user.first_name,
                                    'last_name': user.last_name,
                                    'is_admin': True
                                }
                                db_client.add_subscriber(user_data)
                                added_count += 1
                        
                        logger.info(f"Sync completed: {admins_count} admins, {added_count} added, {updated_count} updated")
                        
                    except telegram.error.TimedOut:
                        logger.warning("Sync timed out. Try using the /sync command directly in Telegram.")
                
                # Run the coroutine
                loop.run_until_complete(_sync_subscribers())
                
            except Exception as e:
                logger.error(f"Error in async_sync_subscribers: {e}")
            finally:
                loop.close()
        
        # Start the sync in a background thread
        from threading import Thread
        thread = Thread(target=async_sync_subscribers)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'status': 'success',
            'message': 'Admin sync initiated. For full channel sync, use the /sync command in Telegram.'
        })
    except Exception as e:
        logger.error(f"Error initiating sync: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/start-aiogram', methods=['GET'])
def start_aiogram():
    """Start the Aiogram bot in polling mode."""
    try:
        # Import the Aiogram extension
        import importlib.util
        spec = importlib.util.spec_from_file_location("aiogram_extension", "aiogram_extension.py")
        aiogram_ext = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(aiogram_ext)
        
        # Start the bot in a background thread
        aiogram_ext.start_bot()
        
        return jsonify({
            'status': 'success',
            'message': 'Aiogram bot started in polling mode'
        })
    except Exception as e:
        logger.error(f"Error starting Aiogram bot: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/start-poller')
def start_bot_poller():
    """Start the bot in polling mode to capture channel events more reliably."""
    try:
        import threading
        import subprocess
        import sys
        
        def run_bot_process():
            try:
                # Execute the run_bot.py script
                process = subprocess.Popen(
                    [sys.executable, "run_bot.py"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )
                
                # Log output from the bot process
                for line in process.stdout:
                    logger.info(f"Bot: {line.strip()}")
                
                logger.warning(f"Bot process exited with code {process.returncode}")
            except Exception as e:
                logger.error(f"Error in bot process: {e}")
        
        # Start the bot in a separate thread
        bot_thread = threading.Thread(target=run_bot_process)
        bot_thread.daemon = True
        bot_thread.start()
        
        return jsonify({
            'status': 'success',
            'message': 'Bot started in polling mode via separate process'
        })
    except Exception as e:
        logger.error(f"Error starting bot poller: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    # Initialize the Grist table
    logger.info("Initializing Grist table...")
    init_result = db_client.init_table()
    logger.info(f"Grist initialization complete: {init_result}")
    
    # Test the Grist connection more thoroughly
    try:
        all_subscribers = db_client.get_all_subscribers()
        logger.info(f"Retrieved {len(all_subscribers)} subscribers from Grist")
        
        # Display first few subscribers for debugging
        if all_subscribers:
            sample_limit = min(3, len(all_subscribers))
            for i in range(sample_limit):
                subscriber = all_subscribers[i]
                logger.info(f"Sample subscriber {i+1}: ID={subscriber.get('id')}, "
                           f"User ID={subscriber.get('user_id')}")
    except Exception as e:
        logger.error(f"Error testing Grist connection: {e}", exc_info=True)
    
    # We're not running the telegram bot here - it's started in a separate thread from main.py
    
    # Run the Flask app
    logger.info("Starting Flask web application...")
    app.run(host="0.0.0.0", port=5000, debug=True)
