"""
Lambeth Cyclists Email Processor - Main Application Entry Point
Monitors Gmail for "Lambeth Cyclists" labeled emails and processes them with Claude AI.
Creates structured entries in Notion and generates meeting agendas.
"""

import asyncio
import signal
import sys
from typing import Optional

from config.settings import get_settings, validate_settings
from config.logging_config import setup_logging, get_logger
from processors.email_processor import EmailProcessor
from agenda.meeting_detector import MeetingDetector
from agenda.meeting_reminder import MeetingReminder


logger = get_logger(__name__)


class Application:
    """Main application class managing the polling loops."""

    def __init__(self):
        """Initialize the application."""
        self.settings = get_settings()
        self.running = False
        self.email_task: Optional[asyncio.Task] = None
        self.meeting_task: Optional[asyncio.Task] = None

        # Initialize email processor
        self.email_processor = EmailProcessor()

        # Initialize meeting detector and reminder system
        self.meeting_detector = MeetingDetector()
        self.meeting_reminder = MeetingReminder()

    async def email_polling_loop(self):
        """
        Poll Gmail for new emails every EMAIL_POLL_INTERVAL seconds.
        Process emails: download attachments, analyze with Claude, create Notion items.
        """
        logger.info(f"Starting email polling loop (interval: {self.settings.email_poll_interval}s)")

        while self.running:
            try:
                logger.debug("Polling Gmail for new emails...")

                # Process new emails
                logger.debug("About to call process_new_emails()")
                await self.email_processor.process_new_emails()
                logger.debug("Returned from process_new_emails()")

                logger.info("Email polling cycle complete")

            except Exception as e:
                logger.error(f"Error in email polling loop: {e}", exc_info=True)

            # Wait for next poll interval
            await asyncio.sleep(self.settings.email_poll_interval)

    async def meeting_agenda_loop(self):
        """
        Check for upcoming meetings every MEETING_CHECK_INTERVAL seconds.
        Generate agendas for meetings 1-2 days in the future.
        """
        logger.info(f"Starting meeting agenda loop (interval: {self.settings.meeting_check_interval}s)")

        while self.running:
            try:
                logger.debug("Checking for meetings needing agendas and sending reminders...")

                # Check for meetings and generate agendas
                await self.meeting_detector.check_and_generate()

                # Check for meetings needing reminders
                await self.meeting_reminder.check_and_send_reminders()

                logger.info("Meeting agenda cycle complete")

            except Exception as e:
                logger.error(f"Error in meeting agenda loop: {e}", exc_info=True)

            # Wait for next check interval
            await asyncio.sleep(self.settings.meeting_check_interval)

    async def startup(self):
        """Perform startup tasks and validation."""
        logger.info("=" * 60)
        logger.info("Lambeth Cyclists Email Processor Starting")
        logger.info("=" * 60)

        # Validate configuration
        try:
            validate_settings()
        except Exception as e:
            logger.critical(f"Configuration validation failed: {e}")
            sys.exit(1)

        # TODO: Validate API connections in later phases
        # - Test Gmail API authentication
        # - Test Notion API connection
        # - Test Claude API connection
        # - Test Google Drive API connection

        logger.info("Startup complete")
        self.running = True

    async def shutdown(self):
        """Perform graceful shutdown."""
        logger.info("Shutting down...")
        self.running = False

        # Cancel running tasks
        if self.email_task and not self.email_task.done():
            self.email_task.cancel()
            try:
                await self.email_task
            except asyncio.CancelledError:
                pass

        if self.meeting_task and not self.meeting_task.done():
            self.meeting_task.cancel()
            try:
                await self.meeting_task
            except asyncio.CancelledError:
                pass

        logger.info("Shutdown complete")

    async def run(self):
        """Main application run loop."""
        await self.startup()

        try:
            # Start both polling loops concurrently
            self.email_task = asyncio.create_task(self.email_polling_loop())
            self.meeting_task = asyncio.create_task(self.meeting_agenda_loop())

            # Wait for both tasks (they run indefinitely until shutdown)
            await asyncio.gather(self.email_task, self.meeting_task)

        except asyncio.CancelledError:
            logger.info("Application cancelled")
        except Exception as e:
            logger.critical(f"Fatal error: {e}", exc_info=True)
        finally:
            await self.shutdown()


def handle_signal(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, initiating shutdown...")
    sys.exit(0)


async def main():
    """Main entry point."""
    # Set up logging
    settings = get_settings()

    # Use JSON logging in production (Railway), colored in development
    use_json = settings.log_level == "INFO" and not sys.stdout.isatty()
    setup_logging(level=settings.log_level, use_json=use_json)

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Run the application
    app = Application()
    await app.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.critical(f"Application crashed: {e}", exc_info=True)
        sys.exit(1)
