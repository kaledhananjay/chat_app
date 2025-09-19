import os
import sys
from daphne.cli import CommandLineInterface

# Explicitly set the environment variable
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chat_app.settings")

# Launch Daphne
sys.argv = ["daphne", "chat_app.asgi:application"]
CommandLineInterface.entrypoint()