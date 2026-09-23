"""Fetch public IEEE XML full text; credentials only from IEEE_API_KEY.

Usage: python ieee_fulltext.py 8579198 11098909 --output-dir fulltext
Does not call a purchase, account-token or subscription endpoint.
"""
import argparse
import hashlib
import json
import os
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

BASE = 'https://ieeexploreapi.ieee.org/api/v1/search'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('article_numbers', nargs='+')
    parser.add_argument('--output-dir', type=Path, default=Path('ieee_fulltext'))
    args = parser.parse_args()
    key = os.environ.get('IEEE_API_KEY')
    if not key:
        raise SystemExit('Set IEEE_API_KEY in the environment; no key is embedded in this script.')
    results = []
    session = requests.Session()
    for number in args.article_numbers:
        if not number.isdigit():
            raise SystemExit('Article numbers must contain digits only.')
        item = {'article_number': number}
        try:
            response = session.get(BASE+'/articles', params={'apikey':key,'article_number':number,'format':'json'}, timeout=(15,60))
            item['metadata_http_status'] = response.status_code
            response.raise_for_status()
            articles = response.json().get('articles', [])
            if not articles:
                item['status'] = 'metadata_missing'
                results.append(item)
                continue
            article = articles[0]
            access = str(article.get('access_type', ''))
            item.update(title=article.get('title'), access_type=access)
            normalized = access.upper().replace('_',' ')
            if not any(x in normalized for x in ['OPEN ACCESS', 'EPHEMERA', 'CCBY', 'CC BY']):
                item['status'] = 'not_public_access'
                results.append(item)
                continue
            time.sleep(1.2)
            response = session.get(BASE+f'/document/{number}/fulltext', params={'apikey':key,'format':'xml'}, timeout=(15,60))
            item.update(http_status=response.status_code,content_type=response.headers.get('Content-Type',''))
            response.raise_for_status()
            data = response.content
            root = ET.fromstring(data)
            bodies = [x for x in root.iter() if x.tag.rsplit('}',1)[-1]=='body']
            chars = sum(len(''.join(x.itertext())) for x in bodies)
            if not bodies or chars < 1000:
                raise ValueError('No substantial article body in response')
            args.output_dir.mkdir(parents=True,exist_ok=True)
            dest = args.output_dir/f'{number}.xml'
            dest.write_bytes(data)
            item.update(status='downloaded_xml',file=str(dest),bytes=len(data),body_count=len(bodies),body_chars=chars,sha256=hashlib.sha256(data).hexdigest())
        except Exception as exc:
            # Exceptions from requests can include credential-bearing URLs; never print them.
            item.update(status='not_downloaded',error_type=type(exc).__name__)
        results.append(item)
        time.sleep(1.2)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/'api_log.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'articles':len(results),'downloaded':sum(x['status']=='downloaded_xml' for x in results)}))

if __name__=='__main__':
    main()
