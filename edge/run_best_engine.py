#!/usr/bin/env python3
"""Production entry point: always uses the requested icar_models/best.engine."""
import sys

if '--model' not in sys.argv:
    sys.argv += ['--model', '/home/jetson/icar_models/best.engine']

from icar_yolo_infer import main

if __name__ == '__main__':
    main()
