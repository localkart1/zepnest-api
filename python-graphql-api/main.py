#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from api import create_app

load_dotenv()

app = create_app()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5002))
    debug = os.getenv('FLASK_DEBUG', 'True') == 'True'

    print(f"Starting API server on http://localhost:{port}")
    print(f"GraphQL IDE: http://localhost:{port}/graphql")

    app.run(host='0.0.0.0', port=port, debug=debug)
