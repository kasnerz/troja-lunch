#!/usr/bin/env python3

import os
import sys
import argparse
import socket

sys.path.append(os.path.dirname(__name__))

from app import app, main

def parse_args():
    parser = argparse.ArgumentParser()
    # parser.add_argument("-t", "--cache_update_time", type=int, default=60,
    #     help="Time in minutes after cache with menus should be updated.")

    return parser.parse_args()

def main():
    args = parse_args()
    main(args)
    return app


if __name__ == '__main__':
    args = parse_args()
    main(args)
    
    app.run(debug=True)
