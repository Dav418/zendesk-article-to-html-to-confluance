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
  if ! python3 -m venv .venv; then
    echo "Could not create the Python environment."
    read -r -p "Press Enter to close..."
    exit 1
  fi
fi

if ! .venv/bin/python -m pip install --upgrade pip || ! .venv/bin/python -m pip install -r requirements.txt; then
  echo "Could not install the Python packages. Check your internet connection and run this again."
  read -r -p "Press Enter to close..."
  exit 1
fi

.venv/bin/python migrate.py
status=$?
echo
read -r -p "Press Enter to close..."
exit "$status"
