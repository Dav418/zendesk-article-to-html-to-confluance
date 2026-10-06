#!/bin/bash
cd "$(dirname "$0")" || exit 1

case "$PWD" in
  *.zip/*|*"/private/var/folders/"*)
    echo "This was started from inside the ZIP, before it was unzipped."
    echo "Double-click the ZIP in Downloads. A folder will appear next to it."
    echo "Open that folder and double-click start.command there."
    read -r -p "Press Enter to close..."
    exit 1
    ;;
esac

if [ ! -f "migrate.py" ] || [ ! -w "." ]; then
  echo "Unzip the download first, then run start.command from inside the unzipped folder."
  echo "The folder should contain migrate.py and start.command."
  read -r -p "Press Enter to close..."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.11 or newer is not installed."
  echo "Install it from https://www.python.org/downloads/macos/ and run this again."
  read -r -p "Press Enter to close..."
  exit 1
fi

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "Python is installed, but it is older than 3.11."
  echo "Install Python 3.11 or newer from https://www.python.org/downloads/macos/ and run this again."
  read -r -p "Press Enter to close..."
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv || exit 1
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

if [ ! -f ".env" ] || [ ! -s ".env" ]; then
  if [ -f ".env.example" ]; then
    cp .env.example .env
  fi
  echo
  echo "A file named .env must be filled in before the migration can run."
  echo "It was just created in this folder if it was missing or empty:"
  echo "  $PWD/.env"
  echo
  echo "Finder hides this file because the name starts with a dot."
  echo "  1. Open this folder in Finder, the one that contains start.command."
  echo "  2. Press Command + Shift + . (the period key). Hidden files appear in grey."
  echo "  3. Double-click .env. If Mac asks for an app, choose TextEdit."
  echo "  4. Replace every example value, including PASTE_ZENDESK_TOKEN_HERE."
  echo "  5. Save, then run start.command again."
  echo "Do not edit the .venv folder. That is a different hidden item."
  echo "Press Command + Shift + . again to hide those files when you are finished."
  open -e ".env" >/dev/null 2>&1 || true
  read -r -p "Press Enter to close..."
  exit 1
fi

.venv/bin/python migrate.py
status=$?
echo
read -r -p "Press Enter to close..."
exit "$status"
