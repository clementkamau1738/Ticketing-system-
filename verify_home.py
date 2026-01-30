import requests
import sys

try:
    response = requests.get('http://127.0.0.1:8000/')
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        content = response.text
        checks = {
            "Brand": "EventHub",
            "Hero Text": "Discover and book tickets",
            "Search Form": 'action="/events/"', # Checking if form points to events list
            "Date Filter": 'name="date"',
            "Category Dropdown": "Category",
            "Login Link": "Login" # Assuming unauthenticated
        }
        
        all_passed = True
        for name, string in checks.items():
            if string in content:
                print(f"✅ {name} found")
            else:
                print(f"❌ {name} NOT found")
                # Special check for Search Form action which might be rendered via url tag
                if name == "Search Form":
                    print(f"   (Expected '{string}' in HTML)")
                all_passed = False
                
        if not all_passed:
             print("\n📄 HTML Content Snippet (Navbar):")
             start = content.find('<nav')
             end = content.find('</nav>') + 6
             print(content[start:end])

        if all_passed:
            print("\n🎉 Homepage verification successful!")
        else:
            print("\n⚠️ Some checks failed.")
            sys.exit(1)
    else:
        print("❌ Failed to retrieve homepage")
        sys.exit(1)

except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
