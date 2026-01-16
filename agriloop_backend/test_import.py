
import sys
import os

print(f"Python executable: {sys.executable}")
try:
    import google.genai
    print("Successfully imported google.genai")
    try:
        print(f"Version: {google.genai.__version__}")
    except AttributeError:
        print("Version attribute not found")
except ImportError as e:
    print(f"Failed to import google.genai: {e}")
    try:
        import google
        print(f"google package path: {google.__path__}")
    except:
        pass

try:
    import google.generativeai
    print("Successfully imported google.generativeai")
except ImportError:
    print("google.generativeai not found")
