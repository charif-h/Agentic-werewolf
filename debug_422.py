#!/usr/bin/env python3
"""
Simple test to debug the 422 error
"""
import sys

def test_simple_request():
    """Test simple request with detailed error info"""
    try:
        import requests
        print("✅ requests module imported successfully")
        
        # Test connection
        print("Testing connection to server...")
        
        # First test a simple GET request
        try:
            response = requests.get('http://localhost:8000/')
            print(f"✅ Server is responding: {response.status_code}")
        except Exception as e:
            print(f"❌ Server connection failed: {e}")
            return False
        
        # Test the problematic POST request with detailed error handling
        print("Testing POST request to create game...")
        try:
            response = requests.post(
                'http://localhost:8000/api/game/create',
                json={"num_players": 5},
                headers={"Content-Type": "application/json"}
            )
            
            print(f"Response status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")
            
            if response.status_code == 422:
                print("❌ Validation error (422):")
                try:
                    error_detail = response.json()
                    print(f"Error details: {error_detail}")
                except:
                    print(f"Error text: {response.text}")
            elif response.status_code == 200:
                print("✅ Request successful!")
                result = response.json()
                print(f"Result: {result}")
            else:
                print(f"❌ Unexpected status code: {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")
            return False
            
        return True
        
    except ImportError:
        print("❌ requests module not available")
        print("Available modules:", [m for m in sys.modules.keys() if not m.startswith('_')])
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    test_simple_request()