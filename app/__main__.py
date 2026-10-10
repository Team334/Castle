import os

from dotenv import load_dotenv
from waitress import serve

from app.app import create_app

load_dotenv()

app = create_app()

if __name__ == "__main__":
    debug_mode = os.getenv("DEBUG", "False").lower() == "true"
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 5000))

    if debug_mode:
        app.run(debug=True, host=host, port=port)
    else:
        threads = int(os.getenv("WAITRESS_THREADS", "4"))
        if not 1 <= threads <= 64:
            raise ValueError("WAITRESS_THREADS must be between 1 and 64")
        serve(app, host=host, port=port, threads=threads)
