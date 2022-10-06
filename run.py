#!/usr/bin/env python3

import os
import sys

sys.path.append(os.path.dirname(__name__))

from app import app, create_app

if __name__ == '__main__':
    create_app()
    
    app.run(debug=True)
