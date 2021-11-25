
import os

def makeDirs(dir):
    """make directory path if doesn't exist"""
    if not os.path.exists(dir):
        os.makedirs(dir)


