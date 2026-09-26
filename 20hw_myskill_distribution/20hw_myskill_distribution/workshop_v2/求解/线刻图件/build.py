"""Rebuild the manuscript illustration suite from its existing bound tables."""
from pathlib import Path
import argparse,os,subprocess,sys,json
HERE=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--theme',choices=['qinglu','qianjiang','yanlan','mono'],default='qinglu')
    p.add_argument('--only',choices=['all','results','mechanisms','trace'],default='all')
    a=p.parse_args()
    env={**os.environ,'PAPER_INK_THEME':a.theme,'PYTHONUTF8':'1'}
    scripts={'results':'draw_results.py','mechanisms':'draw_mechanisms.py','trace':'draw_trace.py'}
    for key,script in scripts.items():
        if a.only in ('all',key):
            subprocess.run([sys.executable,str(HERE/script)],env=env,check=True)
    print('Written to the original manuscript figure directories; theme:',a.theme)

if __name__=='__main__':main()
