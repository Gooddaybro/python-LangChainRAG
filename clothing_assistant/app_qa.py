"""Legacy wrapper for the Streamlit QA workbench.

Prefer running ``clothing_assistant/ui/app_qa.py`` directly. This wrapper is
kept during the package migration so existing imports and scripts keep working.
"""

from clothing_assistant.ui.app_qa import *  # noqa: F403
from clothing_assistant.ui.app_qa import main


if __name__ == "__main__":
    main()
