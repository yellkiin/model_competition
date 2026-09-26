"""Compatibility entry: rebuild only manuscript figures, never rerun experiments."""
from pathlib import Path
import subprocess,sys
if __name__=='__main__':
    subprocess.run([sys.executable,str(Path(__file__).resolve().parent/'线刻图件/build.py'),'--only','results',*sys.argv[1:]],check=True)
