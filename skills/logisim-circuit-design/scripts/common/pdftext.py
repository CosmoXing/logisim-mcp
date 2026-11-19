# -*- coding: utf-8 -*-
"""Minimal PDF text extractor with ToUnicode CMap support (for CJK CID fonts)."""
import re, sys, zlib

class PDF:
    def __init__(self, path):
        self.data = open(path, 'rb').read()
        self.objs = {}
        self._scan_objects()
        self._scan_objstm()

    def _scan_objects(self):
        for m in re.finditer(rb'(\d+)\s+(\d+)\s+obj\b', self.data):
            num = int(m.group(1))
            start = m.end()
            end = self.data.find(b'endobj', start)
            if end < 0:
                continue
            self.objs[num] = self.data[start:end]

    def _scan_objstm(self):
        for num, body in list(self.objs.items()):
            if b'/ObjStm' not in body:
                continue
            m = re.search(rb'/First\s+(\d+)', body)
            n = re.search(rb'/N\s+(\d+)', body)
            if not m or not n:
                continue
            first = int(m.group(1)); count = int(n.group(1))
            stream = self.stream(body)
            if stream is None:
                continue
            header = stream[:first].split()
            pairs = [(int(header[i]), int(header[i+1])) for i in range(0, min(len(header), 2*count), 2)]
            for i, (onum, off) in enumerate(pairs):
                end = pairs[i+1][1] + first if i+1 < len(pairs) else len(stream)
                self.objs.setdefault(onum, stream[first+off:end])

    def stream(self, body):
        m = re.search(rb'stream\r?\n', body)
        if not m:
            return None
        raw = body[m.end():]
        e = raw.rfind(b'endstream')
        if e >= 0:
            raw = raw[:e]
        if b'/FlateDecode' in body[:m.start()]:
            try:
                return zlib.decompress(raw)
            except Exception:
                return None
        return raw

    def ref(self, body, key):
        m = re.search(key.encode() + rb'\s+(\d+)\s+0\s+R', body)
        return int(m.group(1)) if m else None

def parse_cmap(data):
    cmap = {}
    if not data:
        return cmap
    txt = data.decode('latin-1', 'ignore')
    for block in re.findall(r'beginbfchar(.*?)endbfchar', txt, re.S):
        for a, b in re.findall(r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', block):
            try:
                cmap[int(a, 16)] = bytes.fromhex(b).decode('utf-16-be', 'ignore')
            except Exception:
                pass
    for block in re.findall(r'beginbfrange(.*?)endbfrange', txt, re.S):
        for a, b, c in re.findall(r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', block):
            lo, hi = int(a, 16), int(b, 16); base = int(c, 16)
            for k in range(lo, min(hi, lo + 65535) + 1):
                try:
                    cmap[k] = chr(base + (k - lo))
                except Exception:
                    pass
    return cmap

def decode_str(raw, cmap, two_byte):
    out = []
    if two_byte:
        for i in range(0, len(raw) - 1, 2):
            code = (raw[i] << 8) | raw[i+1]
            out.append(cmap.get(code, ''))
    else:
        for b in raw:
            v = cmap.get(b)
            out.append(v if v is not None else (chr(b) if 32 <= b < 127 else ''))
    return ''.join(out)

def unescape(b):
    out = bytearray(); i = 0
    while i < len(b):
        c = b[i]
        if c == 0x5c and i + 1 < len(b):
            n = b[i+1]
            mp = {ord('n'): 10, ord('r'): 13, ord('t'): 9, ord('b'): 8, ord('f'): 12}
            if n in mp:
                out.append(mp[n]); i += 2; continue
            if 0x30 <= n <= 0x37:
                od = b[i+1:i+4]; j = 0
                while j < 3 and j < len(od) and 0x30 <= od[j] <= 0x37:
                    j += 1
                out.append(int(od[:j], 8)); i += 1 + j; continue
            out.append(n); i += 2; continue
        out.append(c); i += 1
    return bytes(out)

def tokens(content):
    """Yield (kind, value) with kind in name/num/str/hex/op."""
    i, n = 0, len(content)
    while i < n:
        c = content[i]
        if c in b' \r\n\t\f\x00':
            i += 1; continue
        if c == 0x25:  # comment
            j = content.find(b'\n', i)
            i = n if j < 0 else j + 1; continue
        if c == 0x28:  # (
            j = i + 1; depth = 1
            while j < n:
                if content[j] == 0x5c:
                    j += 2; continue
                if content[j] == 0x28:
                    depth += 1
                elif content[j] == 0x29:
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            yield ('str', content[i+1:j]); i = j + 1; continue
        if c == 0x3c and i + 1 < n and content[i+1] != 0x3c:
            j = content.find(b'>', i)
            if j < 0:
                break
            yield ('hex', content[i+1:j]); i = j + 1; continue
        if c == 0x3c:  # <<
            i += 2; continue
        if c == 0x3e:
            i += 2 if i + 1 < n and content[i+1] == 0x3e else 1; continue
        if c == 0x2f:  # /Name
            j = i + 1
            while j < n and content[j] not in b' \r\n\t\f\x00[]<>/(){}%':
                j += 1
            yield ('name', content[i+1:j].decode('latin-1')); i = j; continue
        if c in b'[]{}+-0123456789.':
            j = i + 1
            while j < n and content[j] not in b' \r\n\t\f\x00[]<>/(){}%':
                j += 1
            yield ('num', content[i:j].decode('latin-1')); i = j; continue
        j = i + 1
        while j < n and content[j] not in b' \r\n\t\f\x00[]<>/(){}%':
            j += 1
        yield ('op', content[i:j].decode('latin-1')); i = j

def content_text(cont, fonts):
    out = []
    cmap, two = {}, False
    operands = []
    for kind, val in tokens(cont):
        if kind in ('str', 'hex', 'num'):
            operands.append((kind, val)); continue
        if kind == 'name':
            operands.append((kind, val)); continue
        op = val
        if op == 'Tf':
            names = [v for k, v in operands if k == 'name']
            if names:
                cmap, two = fonts.get(names[-1], ({}, False))
        elif op in ('Tj', 'TJ', "'", '"'):
            for k, v in operands:
                if k == 'hex':
                    try:
                        rb = bytes.fromhex(v.decode('ascii'))
                    except Exception:
                        continue
                    if two and len(rb) % 2:
                        rb = b'\x00' + rb
                    out.append(decode_str(rb, cmap, two))
                elif k == 'str':
                    out.append(decode_str(unescape(v), cmap, two))
            if op in ("'", '"'):
                out.append('\n')
        elif op in ('Td', 'TD', 'T*'):
            if out:
                out.append('\n')
        operands = []
    return ''.join(out)

def main(path):
    pdf = PDF(path)
    page_refs = sorted(num for num, body in pdf.objs.items()
                       if re.search(rb'/Type\s*/Page\b', body))
    pages = []
    for pnum in page_refs:
        body = pdf.objs.get(pnum, b'')
        if b'/Contents' not in body:
            continue
        fonts = {}
        fres = re.search(rb'/Font\s*<<(.*?)>>', body, re.S)
        if fres:
            for fm in re.finditer(rb'/([A-Za-z0-9]+)\s+(\d+)\s+0\s+R', fres.group(1)):
                fname = fm.group(1).decode(); fnum = int(fm.group(2))
                fbody = pdf.objs.get(fnum, b'')
                tu = pdf.ref(fbody, '/ToUnicode')
                cmap = parse_cmap(pdf.stream(pdf.objs.get(tu, b'')) if tu else None)
                two = b'/Type0' in fbody or b'Identity-H' in fbody
                fonts[fname] = (cmap, two)
        cm = re.search(rb'/Contents\s+(\d+)\s+0\s+R', body)
        if not cm:
            continue
        cont = pdf.stream(pdf.objs.get(int(cm.group(1)), b''))
        if cont is None:
            continue
        pages.append(content_text(cont, fonts))
    return '\n\n===== PAGE =====\n\n'.join(pages)

if __name__ == '__main__':
    sys.stdout.write(main(sys.argv[1]))