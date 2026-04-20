import os
import redis
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Get REDIS_URL
redis_url = os.getenv("REDIS_URL")

print("Loaded URL:", redis_url)  # 🔍 check if loaded

# Connect to Redis
r = redis.Redis.from_url(
    redis_url,
    decode_responses=True,
    ssl_cert_reqs=None
)

# Test connection
try:
    print("Ping:", r.ping())  # should return True

    r.set("test_key", "Hello Redis 🚀")
    value = r.get("test_key")

    print("Value:", value)

except Exception as e:
    print("Error:", e)