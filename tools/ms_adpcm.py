"""Encode mono PCM16 as standard seven-coefficient Microsoft ADPCM (512 samples/block).

XAudio2 requires a power-of-two samples-per-block count. FFmpeg's power-of-two
byte block sizes produce 500 samples at 256 bytes and do not meet that rule.
"""
import struct

COEFFICIENTS = ((256, 0), (512, -256), (0, 0), (192, 64), (240, 0), (460, -208), (392, -232))
ADAPT = (230, 230, 230, 230, 307, 409, 512, 614, 768, 614, 512, 409, 307, 230, 230, 230)
SAMPLES = 512
ALIGN = 262


def _block(samples, predictor):
    c1, c2 = COEFFICIENTS[predictor]
    older, newer = samples[0], samples[1]
    initial_delta = max(16, min(32767, abs(newer - older)))
    delta = initial_delta
    output = bytearray(struct.pack('<BHhh', predictor, delta, newer, older))
    high = None
    error = 0
    for sample in samples[2:]:
        product = newer * c1 + older * c2
        prediction = product // 256 if product >= 0 else -((-product) // 256)
        residual = sample - prediction
        magnitude = (abs(residual) + delta // 2) // delta
        signed = max(-8, min(7, magnitude if residual >= 0 else -magnitude))
        reconstructed = max(-32768, min(32767, prediction + signed * delta))
        error += (sample - reconstructed) ** 2
        older, newer = newer, reconstructed
        nibble = signed & 15
        delta = max(16, (delta * ADAPT[nibble]) // 256)
        if high is None:
            high = nibble << 4
        else:
            output.append(high | nibble)
            high = None
    return error, output


def encode_mono(pcm, rate):
    if len(pcm) % 2 or not pcm:
        raise ValueError('Expected nonempty mono PCM16 data')
    from array import array
    import sys
    samples = array('h')
    samples.frombytes(pcm)
    if sys.byteorder != 'little':
        samples.byteswap()
    original_samples = len(samples)
    output = bytearray()
    for start in range(0, original_samples, SAMPLES):
        block = list(samples[start:start + SAMPLES])
        block += [block[-1]] * (SAMPLES - len(block))
        _, encoded = min((_block(block, predictor) for predictor in range(7)), key=lambda item: item[0])
        if len(encoded) != ALIGN:
            raise AssertionError('Invalid encoded block length')
        output.extend(encoded)
    extra = struct.pack('<HH', SAMPLES, len(COEFFICIENTS))
    extra += b''.join(struct.pack('<hh', *pair) for pair in COEFFICIENTS)
    fmt = struct.pack('<HHIIHHH', 2, 1, rate, rate * ALIGN // SAMPLES, ALIGN, 4, len(extra)) + extra
    return fmt, bytes(output), original_samples
