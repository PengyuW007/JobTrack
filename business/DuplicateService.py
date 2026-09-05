"""Public job-page extraction and conservative all-history matching."""
import html
import ipaddress
import json
import re
import socket
from dataclasses import dataclass
from difflib import SequenceMatcher
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests


def normalize(text):
    return ' '.join(re.findall(r'\w+', html.unescape(text or '').casefold()))


def canonical_url(url):
    parts = urlsplit(html.unescape(url.strip()).rstrip('.,);'))
    if parts.scheme.lower() not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        raise ValueError('请输入完整的 http:// 或 https:// 职位网址。')
    # Preserve job identifiers in query parameters; remove only known tracking keys.
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in
             ('fbclid', 'gclid', 'trk', 'trackingid')]
    return urlunsplit(('https', parts.netloc.lower(), parts.path.rstrip('/') or '/',
                       urlencode(sorted(query)), ''))


def urls_in(text):
    result = set()
    for value in re.findall(r'https?://[^\s<>"\'\x00-\x1f]+', html.unescape(text or '')):
        try:
            result.add(canonical_url(value))
        except ValueError:
            pass
    return result


@dataclass
class Posting:
    url: str
    company: str = ''
    position: str = ''
    description: str = ''
    warning: str = ''


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.capture = False
        self.buffer = []
        self.in_title = False
        self.title = ''

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script':
            self.capture = attrs.get('type', '').lower() == 'application/ld+json'
            self.buffer = []
        if tag == 'title':
            self.in_title = True

    def handle_data(self, data):
        if self.capture:
            self.buffer.append(data)
        if self.in_title:
            self.title += data

    def handle_endtag(self, tag):
        if tag == 'script' and self.capture:
            self.scripts.append(''.join(self.buffer))
            self.capture = False
        if tag == 'title':
            self.in_title = False


def job_nodes(value):
    if isinstance(value, list):
        for item in value:
            yield from job_nodes(item)
    elif isinstance(value, dict):
        types = value.get('@type', [])
        if types == 'JobPosting' or isinstance(types, list) and 'JobPosting' in types:
            yield value
        for child in value.values():
            if isinstance(child, (dict, list)):
                yield from job_nodes(child)


def parse_posting(url, source):
    parser = PageParser()
    parser.feed(source)
    nodes = []
    for script in parser.scripts:
        try:
            nodes.extend(job_nodes(json.loads(script)))
        except (ValueError, TypeError):
            continue
    if len(nodes) == 1:
        node = nodes[0]
        company = node.get('hiringOrganization') or {}
        company = company.get('name', '') if isinstance(company, dict) else str(company)
        description = html.unescape(re.sub('<[^>]+>', ' ', str(node.get('description', ''))))
        return Posting(url, company, str(node.get('title', '')), description)
    return Posting(url, warning='页面没有唯一的结构化职位信息。请补充公司、岗位名称和职位描述后查重。')


def fetch_posting(url):
    canonical_url(url)  # Validate without changing the actual requested URL.
    current = url.strip()
    for _ in range(6):
        parts = urlsplit(current)
        canonical_url(current)
        addresses = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == 'https' else 80))
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError('仅支持公开招聘页面网址。')
        with requests.get(current, timeout=(5, 15), allow_redirects=False, stream=True,
                          headers={'User-Agent': 'JobTrack/1.0'}) as response:
            if response.is_redirect:
                current = urljoin(current, response.headers['Location'])
                continue
            response.raise_for_status()
            chunks = bytearray()
            for chunk in response.iter_content(65536):
                chunks.extend(chunk)
                if len(chunks) > 3_000_000:
                    raise ValueError('页面过大，请手动填写职位信息。')
            return parse_posting(url, chunks.decode(response.encoding or 'utf-8', errors='replace'))
    raise ValueError('页面重定向过多，请使用最终职位网址。')


class DuplicateService:
    def __init__(self, conn):
        self.conn = conn

    def search(self, posting):
        target = canonical_url(posting.url)
        rows = self.conn.execute('''
            SELECT application_key, company, position, created_date, status, subject, body_preview
            FROM jobs ORDER BY created_date DESC
        ''').fetchall()
        evidence = {}
        for key, date, status, subject, body in self.conn.execute(
                'SELECT application_key, date, status, subject, body FROM application_evidence'):
            evidence.setdefault(key, []).append((date, status, subject, body))
        snapshots = {}
        for key, url, company, position, description in self.conn.execute('SELECT * FROM posting_snapshots'):
            snapshots.setdefault(key, []).append((url, company, position, description))
        matches = []
        for key, company, position, created, status, subject, preview in rows:
            events = evidence.get(key, [])
            texts = [subject or '', preview or ''] + [e[2] + ' ' + e[3] for e in events]
            exact = any(target in urls_in(text) for text in texts)
            reason = '历史邮件包含相同网址' if exact else ''
            score = 100 if exact else 0
            candidates = [(company, position, '')]
            # Legacy company fields often contain a sender name/address. Use
            # whole phrases in email evidence as a fallback, never title alone.
            company_phrase = normalize(posting.company)
            title_phrase = normalize(posting.position)
            if len(company_phrase) >= 3 and len(title_phrase) >= 5:
                searchable = ' ' + normalize(' '.join([company or '', position or ''] + texts)) + ' '
                if (' ' + company_phrase + ' ') in searchable and (' ' + title_phrase + ' ') in searchable:
                    candidates.append((posting.company, posting.position, ''))
            for url, org, title, description in snapshots.get(key, []):
                if canonical_url(url) == target:
                    score, reason = 100, '已关联的历史职位网址相同'
                candidates.append((org, title, description))
            for org, title, description in candidates:
                same_company = normalize(posting.company) and normalize(posting.company) == normalize(org)
                title_a, title_b = normalize(posting.position), normalize(title)
                if not same_company or not title_a or not title_b or title_b in ('unknown', 'unknown position'):
                    continue
                similarity = SequenceMatcher(None, title_a, title_b).ratio()
                if similarity >= .86 and score < 80:
                    score, reason = 80, '同公司、相同或近似岗位名称；需核对描述／地点／级别'
                if similarity >= .86 and len(normalize(description)) >= 100 and len(normalize(posting.description)) >= 100:
                    desc_similarity = SequenceMatcher(None, normalize(description), normalize(posting.description), autojunk=False).ratio()
                    if desc_similarity >= .92 and score < 95:
                        score, reason = 95, '公司、岗位及已保存描述高度一致，疑似更换网址重新发布'
            if score:
                dates = sorted({e[0] for e in events if e[1] == 'Applied'})
                date_label = '投递确认邮件：' + '、'.join(dates) if dates else '最早相关记录：' + created + '（未必为实际投递日）'
                matches.append(dict(key=key, company=company, position=position, dates=date_label,
                                    status=status, reason=reason, score=score))
        return sorted(matches, key=lambda item: -item['score'])

    def save_snapshot(self, key, posting):
        self.conn.execute('INSERT OR REPLACE INTO posting_snapshots VALUES (?, ?, ?, ?, ?)',
                          (key, canonical_url(posting.url), posting.company, posting.position, posting.description))
        self.conn.commit()
