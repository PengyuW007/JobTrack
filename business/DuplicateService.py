"""Public job-page extraction and conservative all-history matching."""
import html
import ipaddress
import json
import re
import socket
import sys
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
        raise ValueError('Enter a complete http:// or https:// job URL.')
    # Preserve job identifiers in query parameters; remove only known tracking keys.
    host = parts.netloc.lower().removeprefix('www.')
    params = dict(parse_qsl(parts.query, keep_blank_values=True))
    path = parts.path.rstrip('/') or '/'
    if host.endswith('indeed.com') and params.get('jk'):
        path, params = '/viewjob', {'jk': params['jk']}
    elif host.endswith('linkedin.com'):
        match = re.search(r'/jobs/view/(?:[^/?]+-)?(\d+)', path)
        if match:
            path, params = f'/jobs/view/{match.group(1)}', {}
    query = [(k, v) for k, v in params.items()
             if not k.lower().startswith(('utm_', 'refid')) and k.lower() not in
             ('fbclid', 'gclid', 'trk', 'trackingid', 'tracking', 'from', 'source')]
    return urlunsplit(('https', host, path,
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
    return Posting(url, warning='This page could not be parsed automatically.')


def _fetch_direct(url):
    canonical_url(url)  # Validate without changing the actual requested URL.
    current = url.strip()
    for _ in range(6):
        parts = urlsplit(current)
        canonical_url(current)
        addresses = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == 'https' else 80))
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError('Only public job-page URLs are supported.')
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
                    raise ValueError('The job page is too large to parse.')
            return parse_posting(url, chunks.decode(response.encoding or 'utf-8', errors='replace'))
    raise ValueError('The job URL redirects too many times.')


def _browser_candidates():
    if sys.platform == 'darwin':
        return ('safari', 'chrome', 'firefox', 'edge')
    if sys.platform == 'win32':
        return ('edge', 'chrome', 'firefox')
    return ('firefox', 'chrome', 'edge')


def _create_driver(name):
    from selenium import webdriver
    if name == 'safari':
        return webdriver.Safari()
    if name == 'firefox':
        options = webdriver.FirefoxOptions()
        options.add_argument('--width=1280')
        options.add_argument('--height=1000')
        return webdriver.Firefox(options=options)
    if name == 'edge':
        options = webdriver.EdgeOptions()
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1280,1000')
        options.add_argument('--lang=en-CA')
        options.add_argument('--log-level=3')
        return webdriver.Edge(options=options)
    options = webdriver.ChromeOptions()
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1280,1000')
    options.add_argument('--lang=en-CA')
    options.add_argument('--log-level=3')
    return webdriver.Chrome(options=options)


def _fetch_with_browser(url):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    driver = None
    last_error = None
    for name in _browser_candidates():
        try:
            driver = _create_driver(name)
            break
        except Exception as error:
            last_error = error
    if driver is None:
        raise RuntimeError('No supported browser is available for automatic job-page parsing.') from last_error
    try:
        driver.minimize_window()
        driver.set_page_load_timeout(25)
        driver.get(url)
        WebDriverWait(driver, 10).until(
            lambda active: active.execute_script('return document.readyState') == 'complete'
        )
        posting = parse_posting(url, driver.page_source)
        if posting.position:
            return posting

        def text_from(selectors):
            for selector in selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements and elements[0].text.strip():
                    return elements[0].text.strip()
            return ''

        position = text_from((
            'h1.top-card-layout__title',
            '.job-details-jobs-unified-top-card__job-title h1',
            'h1',
        ))
        company = text_from((
            '.topcard__org-name-link',
            '.job-details-jobs-unified-top-card__company-name',
            '.top-card-layout__card .topcard__flavor a',
        ))
        description = text_from((
            '.show-more-less-html__markup',
            '.jobs-description__content',
            '.jobs-box__html-content',
            '[class*="job-description"]',
        ))
        if position and description:
            return Posting(url, company, position, description)
        return posting
    finally:
        driver.quit()


def fetch_posting(url):
    canonical_url(url)
    host = (urlsplit(url).hostname or '').lower()
    try:
        posting = _fetch_direct(url)
        if posting.position or not host.endswith(('indeed.com', 'linkedin.com')):
            return posting
    except requests.RequestException:
        posting = None
    try:
        browser_posting = _fetch_with_browser(url)
        if browser_posting.position:
            return browser_posting
    except Exception:
        pass
    return posting or Posting(url, warning='This job board blocked automatic access.')


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
            reason = 'Same URL found in application email' if exact else ''
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
                    score, reason = 100, 'Same saved job URL'
                candidates.append((org, title, description))
            for org, title, description in candidates:
                same_company = normalize(posting.company) and normalize(posting.company) == normalize(org)
                title_a, title_b = normalize(posting.position), normalize(title)
                if same_company and title_a and (not title_b or title_b in ('unknown', 'unknown position')):
                    if score < 55:
                        score, reason = 55, 'Possible match: same company; original role unavailable'
                    continue
                if not same_company or not title_a or not title_b:
                    continue
                similarity = SequenceMatcher(None, title_a, title_b).ratio()
                if similarity >= .86 and score < 80:
                    score, reason = 80, 'Same company and similar title'
                if similarity >= .86 and len(normalize(description)) >= 100 and len(normalize(posting.description)) >= 100:
                    desc_similarity = SequenceMatcher(None, normalize(description), normalize(posting.description), autojunk=False).ratio()
                    if desc_similarity >= .92 and score < 95:
                        score, reason = 95, 'Likely repost: company, title, and description match'
            if score:
                applied_events = [e for e in events if e[1] == 'Applied']
                applications = []
                for date, _event_status, event_subject, event_body in applied_events:
                    applications.append({
                        'date': date[:10],
                        'channel': self._application_channel(event_subject, event_body),
                    })
                if not applications:
                    applications.append({'date': created[:10], 'channel': 'Unknown'})
                date_label = ', '.join(application['date'] for application in applications)

                generic_companies = {'linkedin', 'indeed', 'workday', 'autonotification workday'}
                display_company = posting.company if normalize(company) in generic_companies else company
                display_position = position or posting.position
                matches.append(dict(key=key, company=display_company, position=display_position,
                                    dates=date_label, applications=applications,
                                    status=status, reason=reason, score=score))
        return sorted(matches, key=lambda item: -item['score'])

    @staticmethod
    def _application_channel(subject, body):
        text = normalize(f'{subject or ""} {body or ""}')
        if 'easy apply' in text:
            return 'LinkedIn Easy Apply'
        if 'myworkdayjobs' in text or 'workday' in text:
            return 'Workday'
        if 'indeed' in text:
            return 'Indeed'
        if 'linkedin' in text:
            return 'LinkedIn'
        if 'greenhouse' in text:
            return 'Greenhouse'
        if 'lever.co' in text or 'lever jobs' in text:
            return 'Lever'
        return 'Company website'

    def save_snapshot(self, key, posting):
        self.conn.execute('INSERT OR REPLACE INTO posting_snapshots VALUES (?, ?, ?, ?, ?)',
                          (key, canonical_url(posting.url), posting.company, posting.position, posting.description))
        self.conn.commit()
