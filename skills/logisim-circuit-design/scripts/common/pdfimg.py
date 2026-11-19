# -*- coding: utf-8 -*-
"""从 PDF 中导出内嵌位图（DCTDecode 直接存 jpg；Flate 的 RGB 8 位包成 png）。"""
import re, sys, zlib, struct, os

def png_bytes(w, h, raw, colorspace=3, bpc=8):
    # 仅支持 8 位 RGB/Gray 连续数据
    if colorspace == 3:
        ctype = 2
    elif colorspace == 1:
        ctype = 0
    else:
        raise ValueError("colorspace")
    stride = w * (3 if ctype == 2 else 1)
    rows = b''.join(b'\x00' + raw[y*stride:(y+1)*stride] for y in range(h))
    def chunk(tag, data):
        c = tag + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    ihdr = struct.pack('>IIBBBBB', w, h, bpc, ctype, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr)
            + chunk(b'IDAT', zlib.compress(rows, 6)) + chunk(b'IEND', b''))

def main(pdf_path, outdir):
    data = open(pdf_path, 'rb').read()
    os.makedirs(outdir, exist_ok=True)
    count = 0
    for m in re.finditer(rb'(\d+)\s+0\s+obj\b', data):
        num = int(m.group(1))
        end = data.find(b'endobj', m.end())
        if end < 0:
            continue
        body = data[m.end():end]
        if b'/Subtype/Image' not in body and b'/Subtype /Image' not in body:
            continue
        w = re.search(rb'/Width\s+(\d+)', body)
        h = re.search(rb'/Height\s+(\d+)', body)
        sm = re.search(rb'stream\r?\n', body)
        if not w or not h or not sm:
            continue
        width, height = int(w.group(1)), int(h.group(1))
        raw = body[sm.end():]
        e = raw.rfind(b'endstream')
        if e >= 0:
            raw = raw[:e]
        if b'/DCTDecode' in body:
            fn = os.path.join(outdir, f"img{num:03d}_{width}x{height}.jpg")
            open(fn, 'wb').write(raw)
            count += 1
            print(fn)
        elif b'/FlateDecode' in body:
            try:
                dec = zlib.decompress(raw)
            except Exception:
                continue
            cs = 3 if b'/DeviceRGB' in body else (1 if b'/DeviceGray' in body else 0)
            if cs == 0 or b'/BitsPerComponent 8' not in body:
                continue
            if len(dec) < width * height * (3 if cs == 3 else 1):
                continue
            fn = os.path.join(outdir, f"img{num:03d}_{width}x{height}.png")
            open(fn, 'wb').write(png_bytes(width, height, dec, cs))
            count += 1
            print(fn)
    print("total", count)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])