"""Verify reference metadata against captured primary sources and cited prose.

File/field checks cannot prove that a review was performed or that a source is
authoritative. Actual source inspection and substantive review remain mandatory;
collectors never fill approval fields. No reference is admitted on a URL alone.
"""
from __future__ import annotations

import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit

from paper_contract import balanced, commands, expand_fragment

from ai_disclosure import AI_KEY, AI_DISCLOSURE, AI_TEXT, AI_REFERENCE_TYPE
ORDINARY_REFERENCE_TYPE = 'ordinary'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inside(root, raw):
    path = (root / raw).resolve()
    path.relative_to(root.resolve())
    return path


def plain(value):
    from pylatexenc.latex2text import LatexNodes2Text
    return LatexNodes2Text().latex_to_text(html.unescape(str(value)))


def norm(value):
    value = unicodedata.normalize('NFKD', plain(value)).casefold()
    return ''.join(c for c in value if c.isalnum())


def person(value):
    # Preserve author-list order; accept given/family inversion for one person.
    text = ''.join(c for c in unicodedata.normalize('NFKD', plain(value)).casefold()
                   if not unicodedata.combining(c))
    return tuple(sorted(re.findall(r'\w+', text)))


def doi(value):
    return re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', str(value).strip(), flags=re.I).casefold()


def field_value(field, value):
    if field == 'doi': return doi(value)
    if field == 'pages':
        return re.sub(r'\s+', '', plain(value)).replace('--','-').translate(str.maketrans({c:'-' for c in '–−‐‑'})).casefold()
    if field == 'title':
        text = unicodedata.normalize('NFKD', plain(value)).casefold().translate(str.maketrans({c:'-' for c in '–−‐‑'}))
        return ''.join(c for c in text if c.isalnum() or c in '+-=/<>')
    return norm(value)


def url_identity(value):
    parts = urlsplit(str(value).strip())
    return (parts.netloc.casefold(), parts.path.rstrip('/'), parts.query)


def author_in_manual(author, prefix):
    value = plain(author).strip()
    if norm(value) in norm(prefix): return True
    if ',' in value:
        family, given = value.split(',', 1)
    else:
        words = value.split()
        if len(words) < 2: return False
        i = len(words)-1
        while i > 1 and words[i-1][:1].islower(): i -= 1
        given, family = ' '.join(words[:i]), ' '.join(words[i:])
    initials = ''.join(w[0] for w in re.findall(r'\w+',given))
    return any(norm(form) in norm(prefix) for form in (family+initials, initials+family))


def pointer(data, raw):
    if raw and not raw.startswith('/'):
        raise ValueError('JSON定位必须为RFC6901 Pointer')
    for token in raw.split('/')[1:]:
        token = token.replace('~1', '/').replace('~0', '~')
        data = data[int(token)] if isinstance(data, list) else data[token]
    return data


class SourceHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta, self.text, self.hidden = {}, [], 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag == 'meta':
            self.meta.setdefault(attrs.get('name', '').lower(), []).append(attrs.get('content', ''))

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.hidden:
            self.hidden -= 1

    def handle_data(self, text):
        if not self.hidden:
            self.text.append(text)


def source_metadata(path, record):
    """Derive values from raw source bytes, never from an editable PASS field."""
    fmt = record['format']
    raw = path.read_text(encoding='utf-8-sig') if path.suffix.lower() != '.pdf' else ''
    if fmt == 'html_meta':
        parser = SourceHTML(); parser.feed(raw)
        get = lambda key: parser.meta.get('citation_'+key, [''])[0]
        date = get('publication_date') or get('date')
        year = re.search(r'\b\d{4}\b', date)
        meta = {'title': get('title'), 'authors': parser.meta.get('citation_author', []),
                'year': year[0] if year else '', 'container': get('journal_title') or get('conference_title'),
                'volume': get('volume'), 'issue': get('issue'), 'publisher': get('publisher'),
                'edition': get('edition'), 'doi': doi(get('doi'))}
        if get('firstpage'):
            meta['pages'] = get('firstpage') + ('--'+get('lastpage') if get('lastpage') != get('firstpage') and get('lastpage') else '')
        return {k:v for k,v in meta.items() if v}, ' '.join(parser.text)
    if fmt == 'csl_json':
        data = pointer(json.loads(raw), record.get('json_pointer', ''))
        names = data.get('author') or data.get('editor') or []
        authors = [p.get('literal') or ' '.join(filter(None, (p.get('given'),p.get('family')))) for p in names]
        date = data.get('issued', {}).get('date-parts', [[]])[0]
        meta = {'title':data.get('title'), 'authors':authors, 'year':str(date[0]) if date else ''}
        for target, key in (('container','container-title'),('pages','page'),('volume','volume'),('issue','issue'),
                            ('publisher','publisher'),('edition','edition'),('doi','DOI')):
            if data.get(key):
                value = data[key]
                meta[target] = value[0] if isinstance(value,list) else str(value)
        # A CSL abstract (if present) is evidence for prose; metadata alone is
        # not silently substituted for a scientific claim about the method.
        return {k:v for k,v in meta.items() if v}, plain(data.get('abstract',''))
    if fmt == 'field_quotes':
        if path.suffix.lower() == '.pdf':
            import pymupdf as fitz
            with fitz.open(path) as doc:
                pages = record.get('pdf_pages', [])
                if not pages:
                    raise ValueError('PDF来源须指明实际查看的页码')
                raw = '\n'.join(doc[p-1].get_text() for p in pages)
        elif path.suffix.lower() in ('.html', '.htm'):
            parser = SourceHTML(); parser.feed(raw); raw = ' '.join(parser.text)
        meta = {}
        for field, items in record.get('field_quotes', {}).items():
            values = []
            for item in items:
                if not item['quote'].strip() or norm(item['quote']) not in norm(raw) or norm(item['value']) not in norm(item['quote']):
                    raise ValueError('来源字段摘录不匹配：'+field)
                values.append(item['value'])
            if field != 'authors' and len(values) != 1:
                raise ValueError('非作者字段须为单值：'+field)
            meta[field] = values if field == 'authors' else values[0]
        return meta, raw
    raise ValueError('不支持的来源格式：'+fmt)


def bibliography(root, manifest):
    refs = [c for c in manifest['chapters'] if c['role']=='references']
    if len(refs) != 1:
        raise ValueError('参考文献入口必须唯一')
    text = expand_fragment(root, root/refs[0]['tex_path'])
    entries, files, manual = {}, {}, {}
    calls = commands(text, ('bibliography',))
    if calls:
        from bibtexparser.bparser import BibTexParser
        raw = []
        for call in calls:
            for name in call.argument.split(','):
                path = (root/name.strip()).resolve()
                if path.suffix.lower() != '.bib':
                    path = path.with_suffix('.bib')
                files[str(path)] = sha(path)
                raw.append(path.read_text(encoding='utf-8-sig'))
        try:
            db = BibTexParser(ignore_nonstandard_types=False, add_missing_from_crossref=True).parse('\n'.join(raw), partial=False)
        except Exception as exc:
            raise ValueError('BibTeX解析失败：'+str(exc)) from exc
        for item in db.entries:
            key = item['ID']
            if key == 'ai_tool_disclosure':
                raise ValueError('固定AI披露键由生成器管理，不得写入普通BibTeX书目')
            if key in entries:
                raise ValueError('重复BibTeX键：'+key)
            names = re.split(r'\s+and\s+', item.get('author') or item.get('editor') or '')
            meta = {'kind':item['ENTRYTYPE'], 'title':item.get('title',''), 'authors':[plain(x) for x in names if x],
                    'year':item.get('year',''), 'container':item.get('journal') or item.get('booktitle','')}
            for target, field in (('volume','volume'),('issue','number'),('pages','pages'),('publisher','publisher'),
                                  ('edition','edition'),('doi','doi'),('url','url'),('accessed','urldate')):
                if item.get(field): meta[target] = item[field]
            entries[key] = {k:v for k,v in meta.items() if v}
    else:
        items = commands(text, ('bibitem',))
        files[str((root/refs[0]['tex_path']).resolve())] = sha(root/refs[0]['tex_path'])
        for i, item in enumerate(items):
            if item.argument == 'ai_tool_disclosure':
                raise ValueError('固定AI披露键由生成器管理，不得手写重复条目')
            if item.argument in manual:
                raise ValueError('重复bibitem键：'+item.argument)
            end = items[i+1].start if i+1 < len(items) else text.find(r'\end{thebibliography}', item.end)
            if end < item.end: raise ValueError('未闭合的thebibliography')
            manual[item.argument] = text[item.end:end]
    return entries, manual, files


def metadata_errors(actual, expected):
    errors = []
    for field in ('title','authors','year'):
        if not actual.get(field) or not expected.get(field):
            errors.append('缺少元数据：'+field)
    # Every populated bibliographic field must have source support. Optional
    # issue/DOI fields need not be invented when the publisher does not supply them.
    for field, value in actual.items():
        if field in ('kind','url','accessed'): continue
        wanted = expected.get(field)
        equal = (bool(wanted) and [person(x) for x in value] == [person(x) for x in wanted]) if field=='authors' else (
            bool(wanted) and field_value(field,value)==field_value(field,wanted))
        if not equal: errors.append('元数据不符：'+field)
    kind = actual.get('kind','')
    if kind in ('article','inproceedings','conference') and not actual.get('container'):
        errors.append('论文类文献缺少期刊/会议名')
    if kind == 'article':
        for field in ('volume','pages'):
            if expected.get(field) and not actual.get(field): errors.append('遗漏来源已有字段：'+field)
    if kind in ('book','inbook','incollection'):
        for field in ('publisher','pages'):
            if not actual.get(field): errors.append('书籍引用缺少：'+field)
    if kind in ('misc','online','software','web') and (not actual.get('url') or not actual.get('accessed')):
        errors.append('网络/软件资料缺少URL或访问日期')
    if actual.get('doi') and not re.fullmatch(r'10\.\d{4,9}/\S+', doi(actual['doi'])):
        errors.append('无效DOI')
    return errors


def reference_inventory_errors(records, citation_keys):
    """Validate the count/type/order contract independently of source capture."""
    failures = []
    ordinary = [r for r in records if r.get('reference_type') == ORDINARY_REFERENCE_TYPE]
    ai = [r for r in records if r.get('reference_type') == AI_REFERENCE_TYPE]
    unknown = [r.get('key', '<unknown>') for r in records
               if r.get('reference_type') not in {ORDINARY_REFERENCE_TYPE, AI_REFERENCE_TYPE}]
    if unknown:
        failures.append('文献类型必须明确为 ordinary 或 ai_tool：' + ','.join(unknown))
    cited_ordinary_count = len({r.get("key") for r in ordinary} & set(citation_keys))
    if cited_ordinary_count < 10:
        failures.append(f'正文须有至少10条普通文献；正文实际引用{cited_ordinary_count}条，AI工具披露不计入。')
    if len(ai) != 1:
        failures.append('必须且只能有1条末尾AI工具披露记录')
    elif records[-1].get('reference_type', ORDINARY_REFERENCE_TYPE) != AI_REFERENCE_TYPE:
        failures.append('AI工具披露记录必须位于全部普通文献之后')
    for row in ai:
        if row.get('key') != AI_KEY or row.get('ai_disclosure') != AI_DISCLOSURE:
            failures.append(row.get('key', '<unknown>') + ': AI工具披露字段必须固定为 DeepSeek / DeepSeek-V4.1-Flash / 深度求索（DeepSeek） / 2026-09-23')
        if row.get('sources'):
            failures.append(row.get('key', '<unknown>') + ': AI工具披露不得伪造普通文献来源证据')
    keys = [r.get('key') for r in records]
    ai_keys = {r.get('key') for r in ai}
    if len(keys) != len(set(keys)) or set(keys) != (set(citation_keys) | ai_keys):
        failures.append('文献证据必须与正文普通实引键及固定AI披露键一一对应')
    return failures


def audit_references(manifest_path, citation_report):
    root = manifest_path.parent.resolve()
    failures, checked = [], []
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
        evidence = json.loads(inside(root, manifest['references_evidence_path']).read_text(encoding='utf-8-sig'))
        from jsonschema import Draft202012Validator
        schema = json.loads((Path(__file__).resolve().parents[1]/'参考文献证据.schema.json').read_text(encoding='utf-8'))
        errors = [str(e.message) for e in Draft202012Validator(schema).iter_errors(evidence)]
        if errors: raise ValueError('文献证据须更新至1.1并补齐类型/真实用途字段；schema：'+'; '.join(errors))
        records = evidence['references']
        keys = [r['key'] for r in records]
        failures += reference_inventory_errors(records, citation_report.get('keys', []))
        entries, manual, files = bibliography(root, manifest)
        expected_files = {str((root/r['path']).resolve()):r['sha256'] for r in evidence['bibliography_files']}
        if files != expected_files: failures.append('文献库/手写书目源哈希或范围已变化')
        ordinary_keys = [k for k in citation_report['keys'] if k != AI_KEY]
        if manual and list(manual) != ordinary_keys:
            failures.append('手写普通书目须与正文首次引用顺序及集合一致')
        bodies = {c['chapter_id']:expand_fragment(root,root/c['tex_path']) for c in manifest['chapters'] if c['role']!='references'}
        identities, seen_dois = {}, {}
        for record in records:
            key = record['key']; errors = []; supported = {}; source_texts = []; source_urls = set()
            reference_type = record['reference_type']
            if reference_type == AI_REFERENCE_TYPE:
                from audit_citations import citation_calls
                required = {c['chapter_id'] for c in citation_report['calls'] if key in c['keys']}
                found = set()
                if record['usage_status'] == 'template_only' and (required or record['usages']):
                    errors.append('固定模板字段不是实际使用事实；存在AI标注须登记adopted与真实使用记录')
                if record['usage_status'] == 'adopted' and not required:
                    errors.append('实际采用AI内容须在正文或正文披露说明中关联末尾条目')
                for use in record.get('usages', []):
                    chapter = use['chapter_id']; body = bodies.get(chapter,''); excerpt = use['body_excerpt']
                    if excerpt not in body or key not in {k for call in citation_calls(excerpt) for k in call}:
                        errors.append('AI披露用途摘录未绑定实际引文：'+chapter)
                    log = inside(root, use['record_path'])
                    if sha(log) != use['record_sha256']:
                        errors.append('AI实际使用记录哈希变化：'+chapter)
                    log_text = log.read_text(encoding='utf-8-sig')
                    if use['record_excerpt'] not in log_text or use['ai_output_excerpt'] not in use['record_excerpt']:
                        errors.append('AI实际生成内容摘录未绑定原始使用记录：'+chapter)
                    if use.get('purpose') != 'tool_disclosure':
                        errors.append('AI仅可标注工具使用披露，不得作为学术论据')
                    if len(use.get('ai_output_excerpt', '').strip()) < 8:
                        errors.append('AI披露缺少实际生成内容摘录：'+chapter)
                    if not use['reviewed'] or not use['tool_ref'].strip() or len(use['relevance'].strip()) < 20:
                        errors.append('AI披露缺少实际使用范围与人工核验记录：'+chapter)
                    found.add(chapter)
                if found != required:
                    errors.append('AI披露的正文使用记录必须覆盖所有实际AI标注章节')
                checked.append({'key':key, 'reference_type':reference_type, 'metadata':dict(AI_DISCLOSURE), 'failures':errors})
                failures += [key+': '+error for error in errors]
                continue
            for source in record['sources']:
                capture = inside(root, source['capture_path'])
                if sha(capture) != source['capture_sha256']: errors.append('来源快照哈希变化')
                receipt_path = inside(root,source['receipt_path'])
                if sha(receipt_path) != source['receipt_sha256']: errors.append('获取记录哈希变化')
                receipt = json.loads(receipt_path.read_text(encoding='utf-8-sig'))
                source_urls.update((url_identity(source['url']), url_identity(receipt.get('final_url',''))))
                if (receipt.get('requested_url') != source['url'] or receipt.get('sha256') != sha(capture) or
                        receipt.get('status') != 200 or not receipt.get('retrieved_utc') or
                        urlsplit(receipt.get('final_url','')).scheme not in ('http','https')):
                    errors.append('来源获取记录不匹配')
                meta, text = source_metadata(capture,source)
                source_texts.append(text)
                for field,value in meta.items():
                    old = supported.get(field)
                    same = [person(x) for x in old] == [person(x) for x in value] if field=='authors' and old else field_value(field,old)==field_value(field,value)
                    if old and not same: errors.append('多个来源元数据冲突：'+field)
                    supported[field] = value
                review = source['review']
                if not review['reviewed'] or not review['tool_ref'].strip() or len(review['observation'].strip()) < 20:
                    errors.append('来源尚未实际阅读复核')
            if key in entries:
                actual = entries[key]
                if 'manual_metadata' in record: errors.append('BibTeX条目不能以手填metadata覆盖')
            elif key in manual:
                actual = record.get('manual_metadata',{})
                # Metadata comes from sources; also bind it to the actual printed
                # bibliographic prose, not a separate unused sidecar entry.
                text = norm(manual[key])
                for field in ('title','year','container','volume','issue','pages','publisher','edition','doi'):
                    contained = (field_value('pages',actual.get(field,'')) in field_value('pages',manual[key])) if field=='pages' else norm(actual.get(field,'')) in text
                    if actual.get(field) and not contained:
                        errors.append('手写书目正文不包含已核对字段：'+field)
                displayed = plain(manual[key])
                title = plain(actual.get('title',''))
                prefix = displayed.split(title,1)[0] if title in displayed else ''
                for author in actual.get('authors',[]):
                    if not author_in_manual(author,prefix):
                        errors.append('手写书目作者不匹配：'+author)
            else:
                errors.append('实引键在书目入口中不存在'); actual = {}
            errors += metadata_errors(actual,supported)
            if supported.get('url'): source_urls.add(url_identity(supported['url']))
            if actual.get('url') and url_identity(actual['url']) not in source_urls:
                errors.append('书目URL不是已核对来源或其规范URL')
            identity = (norm(actual.get('title','')), tuple(person(a) for a in actual.get('authors',[])))
            if identity in identities: errors.append('同一著作不同键重复计数：'+identities[identity])
            identities[identity] = key
            if actual.get('doi'):
                value = doi(actual['doi'])
                if value in seen_dois: errors.append('重复DOI：'+seen_dois[value])
                seen_dois[value] = key
            from audit_citations import citation_calls
            required = {c['chapter_id'] for c in citation_report['calls'] if key in c['keys']}
            found = set()
            for use in record['usages']:
                chapter = use['chapter_id']; body = bodies.get(chapter,''); excerpt = use['body_excerpt']
                if excerpt not in body or key not in {k for call in citation_calls(excerpt) for k in call}:
                    errors.append('正文用途摘录未绑定实际引文：'+chapter)
                if len(use.get('source_excerpt', '').strip()) < 8 or not any(norm(use['source_excerpt']) in norm(t) for t in source_texts):
                    errors.append('论据摘录不在已保存来源中：'+chapter)
                if not use['reviewed'] or not use['tool_ref'].strip() or len(use['relevance'].strip()) < 20:
                    errors.append('缺少来源与正文用途的实际相关性审阅：'+chapter)
                found.add(chapter)
            if found != required: errors.append('每个实引章节都须有来源用途绑定')
            checked.append({'key':key,'reference_type':reference_type,'metadata':actual,'failures':errors})
            failures += [key+': '+error for error in errors]
    except (ValueError,KeyError,TypeError,OSError,IndexError,ImportError) as exc:
        failures.append('reference_evidence_invalid: '+str(exc))
    return {'status':'FAIL' if failures else 'PASS','failures':failures,'references':checked,
            'assurance':'Checks current bibliography fields, capture/receipt hashes, duplicate works and cited excerpts. '
                        'Does not prove remote authenticity or human cognition from editable records; actual source reading and review are mandatory.'}


def audit_printed_references(doc, names, numbers, appendix, evidence):
    """Bind reviewed core fields to actual bibliography glyphs, including across pages."""
    from audit_pdf_layout import destination, glyphs
    failures, records, starts = [], [], []
    chars = {p:glyphs(doc[p]) for p in range(len(doc))}
    for key, number in numbers.items():
        target = destination(doc,names,'cite.'+key)
        if not target:
            failures.append(key+': 缺少文献目的地'); continue
        page, x, y = target; raw = ''.join(c['c'] for c in chars[page])
        candidates = []
        for match in re.finditer(re.escape('['+str(number)+']'),raw):
            c = chars[page][match.start()]
            if -1 <= c['origin'][1]-y <= 22 and abs(c['origin'][0]-x) < 18:
                candidates.append(c['origin'][1])
        if len(candidates) != 1:
            failures.append(key+': 文献条目起始编号无法唯一定位'); continue
        starts.append((page,candidates[0]-1,key))
    starts.sort()
    metadata = {r['key']:r['metadata'] for r in evidence.get('references',[])}
    ai_keys = {r['key'] for r in evidence.get('references',[]) if r.get('reference_type') == AI_REFERENCE_TYPE}
    for i,(page,y,key) in enumerate(starts):
        end_page,end_y = starts[i+1][:2] if i+1<len(starts) else (appendix[0], appendix[2])
        selected = [c for p in range(page,end_page+1) for c in chars[p]
                    if (p>page or c['origin'][1]>=y) and (p<end_page or c['origin'][1]<end_y)
                    and c['origin'][1] < doc[p].rect.height-25/25.4*72]
        visible = ''.join(c['c'] for c in selected)
        meta = metadata.get(key,{})
        errors = []
        if key in ai_keys:
            expected = '['+str(numbers[key])+']'+AI_TEXT
            if re.sub(r'\s+', '', visible) != expected:
                errors.append('AI工具披露条目正文格式或固定字段不符')
            if i != len(starts)-1:
                errors.append('AI工具披露在实际PDF中不位于末尾')
            records.append({'key':key,'physical_page':page+1,'text':visible,'failures':errors})
            failures += [key+': '+e for e in errors]
            continue
        if not meta: errors.append('缺少已核对元数据')
        canonical = norm(visible)
        for field in ('title','container','publisher'):
            if meta.get(field) and norm(meta[field]) not in canonical:
                errors.append('实际PDF字段不符：'+field)
        if meta.get('pages') and field_value('pages',meta['pages']) not in field_value('pages',visible):
            errors.append('实际PDF字段不符：pages')
        # The prescribed article/book style prints the publication year at
        # the end, before any optional electronic URL/DOI. Don't mistake page
        # numbers or a year inside the title for the publication year.
        date_text = re.split(r'https?://|doi:',visible,flags=re.I)[0]
        dates = re.findall(r'(?<!\d)(\d{4})(?!\d)',date_text)
        if meta.get('year') and (not dates or dates[-1] != str(meta['year'])):
            errors.append('实际PDF字段不符：year')
        title = norm(meta.get('title',''))
        prefix = canonical.split(title,1)[0] if title and title in canonical else ''
        authors = meta.get('authors',[])
        if 'etal' in prefix:
            authors = authors[:3]
        for author in authors:
            if not author_in_manual(author,prefix): errors.append('实际PDF作者不符：'+author)
        records.append({'key':key,'physical_page':page+1,'text':visible,'failures':errors})
        failures += [key+': '+e for e in errors]
    return {'status':'FAIL' if failures else 'PASS','failures':failures,'references':records,
            'scope':'Visible core bibliography fields under the prescribed numeric bibliography style; actual source and page review remain required.'}
