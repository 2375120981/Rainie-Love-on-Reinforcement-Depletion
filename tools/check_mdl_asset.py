"""Validate the generated asset using FFmpeg's independent decoder; never plays audio."""
import argparse
from array import array
import base64
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entry', type=Path, required=True)
    parser.add_argument('--ffmpeg', type=Path, required=True)
    parser.add_argument('--original', type=Path, required=True)
    args = parser.parse_args()
    source = args.entry.read_text(encoding='utf-8')
    fmt = base64.b64decode(re.search(r"local format = '([^']+)'", source)[1], validate=True)
    audio = base64.b64decode(re.search(r"local content = '([^']+)'", source)[1], validate=True)
    tag, channels, rate, average, alignment, bits, extra = struct.unpack_from('<HHIIHHH', fmt)
    assert tag == 2 and channels == 1 and bits == 4 and rate == 20000
    assert alignment == 262 and extra == 32 and len(fmt) == 50
    assert struct.unpack_from('<HH', fmt, 18) == (512, 7)
    assert len(audio) % alignment == 0
    assert len(base64.b64encode(audio)) <= 12000000
    for offset in range(0, len(audio), alignment):
        predictor, delta = struct.unpack_from('<BH', audio, offset)
        assert predictor < 7 and delta >= 16
    def chunk(kind, payload):
        return kind + struct.pack('<I', len(payload)) + payload + (b'\0' if len(payload) % 2 else b'')
    body = b'WAVE' + chunk(b'fmt ', fmt) + chunk(b'data', audio)
    with tempfile.TemporaryDirectory(prefix='rainie-asset-') as temporary:
        wave = Path(temporary) / 'audio.wav'
        wave.write_bytes(b'RIFF' + struct.pack('<I', len(body)) + body)
        decoded = subprocess.run([str(args.ffmpeg), '-v', 'error', '-nostdin', '-i', str(wave),
            '-f', 's16le', '-c:a', 'pcm_s16le', '-'], check=True, capture_output=True).stdout
        original = subprocess.run([str(args.ffmpeg), '-v', 'error', '-nostdin', '-i', str(args.original),
            '-ac', '1', '-ar', str(rate), '-f', 's16le', '-c:a', 'pcm_s16le', '-'], check=True, capture_output=True).stdout
    original_samples, decoded_samples = array('h'), array('h')
    original_samples.frombytes(original)
    decoded_samples.frombytes(decoded)
    assert 0 <= len(decoded_samples) - len(original_samples) < 512
    signal = sum(x*x for x in original_samples)
    noise = sum((x-y)**2 for x,y in zip(original_samples, decoded_samples))
    snr = 10 * math.log10(signal / max(1, noise))
    assert snr > 15, f'Unexpectedly low signal-to-noise ratio: {snr}'
    print(json.dumps({'codec': 'MS-ADPCM', 'audio_bytes': len(audio),
        'samples_per_block': 512, 'duration_seconds': len(original_samples)/rate,
        'decoded_padding_samples': len(decoded_samples)-len(original_samples),
        'snr_db': round(snr,2), 'pcm_size_reduction_percent': round((1-len(audio)/len(original))*100,2)}))
    print('PASS: independent FFmpeg decoding, complete duration, block headers, audio error and upload size')


if __name__ == '__main__':
    main()
