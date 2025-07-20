
import os

def makeDirs(dir):
    """make directory path if it doesn't exist"""
    if not os.path.exists(dir):
        os.makedirs(dir)


