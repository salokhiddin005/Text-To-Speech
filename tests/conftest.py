import os

# server.py reads API_KEYS at import time, and leaves /api/speak disabled when
# it is unset — so this has to be in place before the module is first imported.
TEST_API_KEY = "test-key-for-pytest"
os.environ.setdefault("API_KEYS", TEST_API_KEY)

# Both deployment targets sit behind a proxy and so run with this on; matching
# that here is what lets tests tell one visitor from another via X-Forwarded-For.
os.environ.setdefault("TRUST_PROXY", "1")
