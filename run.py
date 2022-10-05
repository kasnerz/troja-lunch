#!/usr/bin/env python3

import os
import sys
import argparse
import pandas as pd
import socket

sys.path.append(os.path.dirname(__name__))

from app import app, main

def parse_args():
    parser = argparse.ArgumentParser()
    # parser.add_argument("-i", "--in_file", type=str, default='./crowdsourcing.csv', help="Input CSV file.")
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()
    main(args)

    app.run(debug=True)
