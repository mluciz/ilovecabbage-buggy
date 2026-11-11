"""Rebuild the complete landscape MP4 (including its audio) from eight tracked segments.
Run: python tools/reassemble_video.py
"""
from pathlib import Path
import hashlib
root = Path(__file__).resolve().parents[1]
parts = [root / "assets" / f"ilovecabbage-feature.p{i:02}" for i in range(1, 9)]
output = root / "assets" / "ilovecabbage-feature.mp4"
with output.open("wb") as result:
    for part in parts:
        result.write(part.read_bytes())
print(f"Created {output} ({output.stat().st_size:,} bytes)")
print("SHA256:", hashlib.sha256(output.read_bytes()).hexdigest())
