import asyncio
import sys
import os
import signal

async def run_bot():
    from bot import main
    await main()

async def shutdown(loop, signal_obj=None):
    """Cleanup tasks tied to the service's shutdown."""
    if signal_obj:
        print(f"Received exit signal {signal_obj}")
    else:
        print("Shutting down")
    
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    
    for task in tasks:
        task.cancel()
    
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()

if __name__ == "__main__":
    try:
        # Handle signals properly
        loop = asyncio.get_event_loop()
        # Add signal handlers
        for s in [signal.SIGTERM, signal.SIGINT]:
            loop.add_signal_handler(s, lambda s=s: asyncio.create_task(shutdown(loop, s)))
        
        # Run the bot
        loop.run_until_complete(run_bot())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped!")