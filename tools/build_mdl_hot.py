"""Assemble the MDL Lua script and audio assets; used internally by build_mdl_release.py."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
from ms_adpcm import encode_mono
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_AUDIO_SHA256 = 'b0659832d46bd6f3633adac8723c624ccdae8ece72c53e9928a68f476ead314e'


def read_wave(path):
    data = path.read_bytes()
    if data[:4] != b'RIFF' or data[8:12] != b'WAVE':
        raise ValueError('Expected RIFF WAVE audio')
    chunks = {}
    offset = 12
    while offset + 8 <= len(data):
        kind, size = struct.unpack_from('<4sI', data, offset)
        offset += 8
        if offset + size > len(data):
            raise ValueError('Truncated WAVE chunk')
        chunks[kind] = data[offset:offset + size]
        offset += size + size % 2
    return chunks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', type=Path, required=True)
    parser.add_argument('--ffmpeg', type=Path, required=True)
    parser.add_argument('--codec', choices=('pcm', 'adpcm'), default='adpcm')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'build/mdl-hot/rainie_love_mdl')
    args = parser.parse_args()
    audio_hash = hashlib.sha256(args.audio.read_bytes()).hexdigest()
    if audio_hash != ORIGINAL_AUDIO_SHA256:
        raise ValueError('Audio differs from the original v0.2.9 track')
    with tempfile.TemporaryDirectory(prefix='rainie-mdl-') as temporary:
        wave = Path(temporary) / 'rainie.wav'
        subprocess.run([
            str(args.ffmpeg), '-v', 'error', '-nostdin', '-y', '-i', str(args.audio),
            '-ac', '1', '-ar', '20000',
            '-c:a', 'pcm_s16le', str(wave)
        ], check=True)
        chunks = read_wave(wave)
    format_data, content = chunks[b'fmt '], chunks[b'data']
    if len(format_data) == 16:
        format_data += b'\0\0'
    tag, channels, rate, average, alignment, bits, extra = struct.unpack_from('<HHIIHHH', format_data)
    if not (len(format_data) == 18 and tag == 1 and channels == 1 and rate == 20000
            and bits == 16 and extra == 0 and alignment == 2 and average == rate * alignment
            and len(content) % alignment == 0
            and len(content) <= 8 * 1024 * 1024):
        raise ValueError('Encoded audio does not meet the MDL audio asset constraints')
    original_samples = len(content) // 2
    if args.codec == 'adpcm':
        format_data, content, original_samples = encode_mono(content, rate)
    source = (ROOT / 'src/rainie_love_mdl.lua.in').read_text(encoding='utf-8')
    for marker, path in [('__MDL_POLICY__', 'mdl_policy.lua'), ('__MDL_DATA__', 'mdl_data.lua'), ('__MDL_AUDIO__', 'mdl_audio.lua')]:
        if source.count(marker) != 1:
            raise ValueError(f'Missing or duplicate marker {marker}')
        source = source.replace(marker, (ROOT / 'src' / path).read_text(encoding='utf-8'))
    source = source.replace('__AUDIO_FORMAT__', base64.b64encode(format_data).decode('ascii'))
    source = source.replace('__AUDIO_CONTENT__', base64.b64encode(content).decode('ascii'))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    entry = args.output_dir / 'mod.lua'
    entry.write_text(source, encoding='utf-8', newline='\n')
    report = {
        'version': '0.3.2', 'kind': 'MDL source staging',
        'original_audio_sha256': audio_hash, 'audio_bytes': len(content),
        'encoding': ('MS-ADPCM, mono, 20000 Hz, 512 samples/block' if args.codec == 'adpcm' else 'PCM16, mono, 20000 Hz'),
        'original_samples': original_samples,
        'entry_sha256': hashlib.sha256(entry.read_bytes()).hexdigest(),
        'game_verified': False, 'automatic_trigger_verified': False,
        'limitations': ['Hub status inference instead of numeric reinforcement count; auto trigger not yet game verified',
                        'No extraction boarding detector', 'API 2 audio requires dev.40+',
                        'Mono conversion for native audio limits']
    }
    (args.output_dir / 'BUILD.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (args.output_dir / 'README.md').write_text((ROOT / 'MDL_RELEASE_README.md').read_text(encoding='utf-8'), encoding='utf-8')
    print(json.dumps({'entry': str(entry.resolve()), 'audio_bytes': len(content), 'source_bytes': entry.stat().st_size}, ensure_ascii=False))


if __name__ == '__main__':
    main()
