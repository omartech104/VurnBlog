from flask import Flask, flash
import subprocess
import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'

def interpreter(filename):    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    # Get the file extension
    ext = filename[filename.rfind('.'):].lower()
    
    if ext in ('.php', '.py', '.sh'):
        try:
            os.chmod(filepath, 0o755)
            
            cmd = {
                '.php': ['php', filepath],
                '.py': ['python3', filepath],
                '.sh': ['bash', filepath]
            }[ext]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return f"<pre>OUTPUT:\n{result.stdout}\nERRORS:\n{result.stderr}</pre>"
        except Exception as e:
            return f"Execution failed: {str(e)}", 500
    else:
        # For non-script files like images, return None (to proceed with default behavior)
        return None
