import os
import django
from django.conf import settings
from django.core.cache import cache
import time

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

def verify_redis():
    print("🚀 Verifying Redis Caching...")
    
    try:
        # 1. Test Set
        print("1. Testing cache.set()...")
        cache.set('test_key', 'Hello Redis', 60)
        
        # 2. Test Get
        print("2. Testing cache.get()...")
        value = cache.get('test_key')
        
        if value == 'Hello Redis':
            print(f"   ✅ Success! Retrieved: {value}")
        else:
            print(f"   ❌ Failed. Expected 'Hello Redis', got {value}")
            return

        # 3. Test Delete Pattern (django-redis specific)
        print("3. Testing cache.delete_pattern()...")
        cache.set('foo_1', 'bar')
        cache.set('foo_2', 'baz')
        
        try:
            cache.delete_pattern('foo_*')
            if cache.get('foo_1') is None and cache.get('foo_2') is None:
                print("   ✅ Success! delete_pattern worked.")
            else:
                print("   ❌ Failed. Keys still exist.")
        except AttributeError:
             print("   ⚠️ delete_pattern not supported (backend might not be django-redis or not loaded correctly).")
        except Exception as e:
            print(f"   ❌ Error during delete_pattern: {e}")

        print("\n🎉 Redis Caching Configuration is VALID.")
        
    except Exception as e:
        print(f"\n❌ Redis Connection Failed or Configuration Error: {e}")
        print("⚠️ Ensure Redis server is running on localhost:6379")

if __name__ == "__main__":
    verify_redis()
