"""Smoke test: confirm Python can start MATLAB through the MATLAB Engine API."""

import matlab.engine

print("Starting MATLAB engine...")
engine = matlab.engine.start_matlab()
print(f"Connected. sqrt(16) = {engine.sqrt(16.0)}")
engine.quit()
