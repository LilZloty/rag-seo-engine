import sys
import os

# Add the current directory to sys.path to import app
sys.path.append(os.getcwd())

from app.models.product import Product

def test_product_description_length():
    print("Testing Product.description_length property...")
    
    # Test with content
    p1 = Product(current_description_html="Hello World")
    print(f"Content: '{p1.current_description_html}', Length: {p1.description_length}")
    assert p1.description_length == 11
    
    # Test with None
    p2 = Product(current_description_html=None)
    print(f"Content: {p2.current_description_html}, Length: {p2.description_length}")
    assert p2.description_length == 0
    
    # Test with empty string
    p3 = Product(current_description_html="")
    print(f"Content: '{p3.current_description_html}', Length: {p3.description_length}")
    assert p3.description_length == 0
    
    print("\n✅ Verification successful! The description_length property works as expected.")

if __name__ == "__main__":
    try:
        test_product_description_length()
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        sys.exit(1)
