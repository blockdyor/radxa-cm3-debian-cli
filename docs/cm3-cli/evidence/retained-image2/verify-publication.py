"""Read-only checks for the retained-image2 documentation and preserved packets.

Run: python3 docs/cm3-cli/evidence/retained-image2/verify-publication.py
This validates evidence preservation, not the image or a VM boot.
"""
from pathlib import Path
import csv
import hashlib
import json
import re
import zipfile

HERE = Path(__file__).resolve().parent
DOCS = HERE.parents[1]

def digest(data):
    return hashlib.sha256(data).hexdigest()

def matrix_rows(path):
    with path.open(newline='') as handle:
        reader = csv.DictReader(handle, delimiter='\t')
        return reader.fieldnames, list(reader)

def verify_rows(original, annotated, fields):
    assert len(original) == len(annotated) == 28
    for number, (before, after) in enumerate(zip(original, annotated), 1):
        assert before['id'] == after['id'] == f'H{number:02}'
        assert before['current_status'] == after['current_status'] == 'UNTESTED'
        assert all(before[key] == after[key] for key in fields)
        assert 'REQUIRES PHYSICAL CM3' in after['additional_evidence']
        assert after['evidence_scope'] and after['evidence_reports']
        for ref in after['evidence_reports'].split('; '):
            assert (DOCS / ref).is_file(), ref

locked = json.loads((DOCS / 'evidence-hashes.json').read_text())
for name, sha in locked.items():
    assert digest((DOCS / name).read_bytes()) == sha, name
original = DOCS / 'hardware-matrix.tsv'
assert original.read_bytes() == (HERE / 'hardware-matrix.original.tsv').read_bytes()
fields, rows = matrix_rows(original)
extra, annotated = matrix_rows(DOCS / 'hardware-matrix-evidence.tsv')
assert extra[:len(fields)] == fields
verify_rows(rows, annotated, fields)
# Prove the preservation check rejects a hardware promotion.
bad = [dict(row) for row in annotated]
bad[0]['current_status'] = 'PASS'
try:
    verify_rows(rows, bad, fields)
except AssertionError:
    pass
else:
    raise AssertionError('matrix mutation not detected')

index = json.loads((HERE / 'packet-index.json').read_text())
packets = []
for record in index:
    path = HERE / record['path']
    assert path.stat().st_size == record['bytes'], str(path)
    assert digest(path.read_bytes()) == record['sha256'], str(path)
    if path.suffix != '.zip':
        continue
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert len(names) == len(set(names)), 'duplicate ZIP member'
        for name in names:
            assert not Path(name).is_absolute() and '..' not in Path(name).parts
        manifest_name = ('packet-manifest.json' if 'packet-manifest.json' in names
                         else 'SHA256-index.json')
        manifest = json.loads(archive.read(manifest_name))
        report_files = list(path.parent.glob('*-report.txt'))
        assert len(report_files) == 1
        assert archive.read(report_files[0].name) == report_files[0].read_bytes()
        for name, item in manifest.items():
            expected = item['sha256'] if isinstance(item, dict) else item
            data = archive.read(name)
            assert digest(data) == expected, (str(path), name)
            if isinstance(item, dict) and 'bytes' in item:
                assert len(data) == item['bytes'], name
        packets.append({'path': record['path'], 'indexed_members': len(manifest),
                        'crc_and_member_hashes': 'PASS'})
assert len(packets) == 5

links = 0
for name in ['virtual-validation-report.md', 'validation.md', 'retained-image-candidate.md']:
    text = (DOCS / name).read_text()
    for target in re.findall(r'\]\(([^)]+)\)', text):
        if '://' in target or target.startswith('#'):
            continue
        assert (DOCS / target.split('#', 1)[0]).is_file(), (name, target)
        links += 1
report = (DOCS / 'virtual-validation-report.md').read_text()
for sha in [
    'b0d1f56240fafc49cc32ceab0f041d4bb6f529604635684135ccc6ad26ebbff8',
    '6b72f1005c517309e9647e7c65d2344ee31e013da0e2f4ae5a07c4f2afcd8037',
    'cac0f8575b91529e4809d86a99fb460b2279acc19fd8eea56469dca51d959fad',
]:
    assert sha in report
for term in ['STATIC PASS', 'NOT APPLICABLE', 'UNTESTED', 'FAIL',
             'does not simulate or replace', '52 cases', '36-test lifecycle replay',
             'six FAIL', 'eight complete PEM', 'Zero product defects']:
    assert term in report, term
print(json.dumps({'physical_rows': len(rows), 'physical_status': 'UNTESTED',
                  'original_fields_preserved': len(fields), 'locked_hashes': len(locked),
                  'hardware_promotion_negative_selfcheck': 'PASS',
                  'relative_links_checked': links, 'packets': packets,
                  'scope': 'documentation/packet preservation only'}, indent=2))
