"""Build the MDL manager ZIP without bundling a loader or overriding game boot."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import uuid
import zipfile

from build_release import LUA_TYPE, murmur64

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.3.0'
RESOURCE = 'mods/2375120981/rainie_love/main'
PATCH = '9ba626afa44a3aa3.patch_0'


def archive(source):
    payload, offset = struct.pack('<II', len(source), 2) + source, 192
    length = (offset + len(payload) + 15) // 16 * 16
    head = struct.pack('<III20sQQ24s', 0xF0000011, 1, 1, b'', length, 0, b'')
    typ = struct.pack('<IIQIIII', 0, 0, LUA_TYPE, 1, 0, 16, 16)
    row = struct.pack('<7Q6I', murmur64(RESOURCE.encode()), LUA_TYPE, offset,
                      0, 0, 0, 0, len(payload), 0, 0, 16, 16, 0)
    body = head + typ + row + b'\0' * (offset - len(head + typ + row)) + payload
    return body + b'\0' * (length - len(body))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', type=Path, required=True)
    parser.add_argument('--ffmpeg', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'release')
    args = parser.parse_args()
    staging = ROOT / 'build/mdl-release'
    subprocess.run([sys.executable, '-B', str(ROOT/'tools/build_mdl_hot.py'),
        '--audio', str(args.audio), '--ffmpeg', str(args.ffmpeg), '--output-dir', str(staging)], check=True)
    source = ('-- HD2-Addon: ' + RESOURCE + '\n' + (staging/'mod.lua').read_text(encoding='utf-8')).encode('utf-8')
    entry = staging / 'manager_main.lua'
    entry.write_bytes(source)
    subprocess.run([sys.executable, '-B', str(ROOT/'tools/check_mdl.py'), '--hot-entry', str(entry)], check=True)
    for forbidden in (b'__MDL_', b'__AUDIO_', b'CAPTURE_', b'PREVIEW_TIMEOUT', b'preview_started'):
        assert forbidden not in source, forbidden
    assert '热加载测试'.encode() not in source
    patch = archive(source)
    magic, types, count = struct.unpack_from('<III', patch)
    row = struct.unpack_from('<7Q6I', patch, 104)
    assert (magic, types, count) == (0xF0000011, 1, 1)
    assert row[:2] == (murmur64(RESOURCE.encode()), LUA_TYPE)
    assert row[0] != 0xf476df93691895fa, 'must not replace the game startup script'
    assert struct.unpack_from('<II', patch, row[2]) == (len(source), 2)
    assert patch[row[2]+8:row[2]+row[7]] == source
    description = '增援耗尽且仅剩一人存活时播放雨爱；每次从头播放，支持试听循环、音量、淡出与自动开关。需要 MDL3 和 HD2 Data Hub。'
    manifest = {'Version': 1, 'Guid': str(uuid.uuid5(uuid.NAMESPACE_URL,
        'https://github.com/2375120981/Rainie-Love-on-Reinforcement-Depletion#mdl')),
        'Name': f'增援耗尽自动播放雨爱 MDL v{VERSION}', 'Description': description,
        'Options': [{'Name': '增援耗尽自动播放雨爱', 'Description': description, 'Include': ['Addon']}]}
    files = {'manifest.json': (json.dumps(manifest, ensure_ascii=False, indent=2)+'\n').encode('utf-8'),
        'README.md': (ROOT/'MDL_RELEASE_README.md').read_bytes(),
        'Addon/'+PATCH: patch, 'Addon/'+PATCH+'.stream': b'', 'Addon/'+PATCH+'.gpu_resources': b''}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f'Rainie-Love-on-Reinforcement-Depletion-MDL-v{VERSION}.zip'
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as package:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 11, 6, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            package.writestr(info, data)
    with zipfile.ZipFile(output) as package:
        assert package.testzip() is None
        assert set(package.namelist()) == set(files)
        for name, data in files.items():
            assert package.read(name) == data
        assert json.loads(package.read('manifest.json'))['Options'][0]['Include'] == ['Addon']
    report = {'path': str(output.resolve()), 'version': VERSION, 'bytes': output.stat().st_size,
        'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'resource': RESOURCE,
        'resource_id': f'{row[0]:016x}', 'script_sha256': hashlib.sha256(source).hexdigest(),
        'audio': json.loads((staging/'BUILD.json').read_text(encoding='utf-8'))['encoding'],
        'checks': ['Lua 5.1 lifecycle and automatic conditions', 'unlimited looping preview and manual stop',
            'exactly four settings', 'no capture/test entry', 'archive resource and source identity',
            'manifest include mapping', 'ZIP CRC and every file identity', 'no game boot replacement'],
        'game_validation': 'mdl.11 behavior confirmed by user; release menu and unlimited preview verified offline'}
    (args.output_dir/'Rainie-Love-on-Reinforcement-Depletion-MDL-v0.3.0.build.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
