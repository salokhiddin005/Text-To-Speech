import os

# server.py reads API_KEYS at import time, and leaves /api/speak disabled when
# it is unset — so this has to be in place before the module is first imported.
TEST_API_KEY = "test-key-for-pytest"
os.environ.setdefault("API_KEYS", TEST_API_KEY)
