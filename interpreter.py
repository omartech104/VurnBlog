import os

def interpreter(filename):
    """
    Returns True ONLY if the file extension is in our safe whitelist.
    """
    # 1. Define the ONLY allowed extensions
    # Since this is for profile photos, we only want image types.
    ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif'}
    
    # 2. Extract the extension
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    
    # 3. The Guard: Check if the extension is 'invited'
    if ext in ALLOWED_EXTENSIONS:
        return True
    
    # 4. Default Deny: If it's not in the list, it's rejected.
    return False