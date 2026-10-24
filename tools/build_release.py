from pathlib import Path
import argparse, base64, hashlib, json, re, struct, uuid, zipfile

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
RESOURCE = "mods/c09nat/rainie_love_on_reinforcement_depletion"
PATCH = "9ba626afa44a3aa3.patch_0"
LUA_TYPE = 0xA14E8DFA2CD117E2
VERSION = "0.2.9"

def murmur64(data: bytes) -> int:
    mask, m = (1 << 64) - 1, 0xC6A4A7935BD1E995
    h, end = len(data) * m & mask, len(data) // 8 * 8
    for offset in range(0, end, 8):
        k = int.from_bytes(data[offset:offset+8], "little") * m & mask
        k ^= k >> 47; k = k * m & mask; h = (h ^ k) * m & mask
    if end < len(data): h = (h ^ int.from_bytes(data[end:], "little")) * m & mask
    h ^= h >> 47; h = h * m & mask
    return h ^ (h >> 47)

def archive(source: bytes) -> bytes:
    assert source.startswith(("-- HD2-Addon: " + RESOURCE + "\n").encode())
    payload, offset = struct.pack("<II", len(source), 2) + source, 192
    length = (offset + len(payload) + 15) // 16 * 16
    head = struct.pack("<III20sQQ24s", 0xF0000011, 1, 1, b"", length, 0, b"")
    typ = struct.pack("<IIQIIII", 0, 0, LUA_TYPE, 1, 0, 16, 16)
    row = struct.pack("<7Q6I", murmur64(RESOURCE.encode()), LUA_TYPE, offset,
                      0, 0, 0, 0, len(payload), 0, 0, 16, 16, 0)
    data = head + typ + row + b"\0" * (offset - len(head + typ + row)) + payload
    return data + b"\0" * (length - len(data))

def load_music(audio=None, package=None):
    if audio and package:
        raise ValueError("Use either --audio or --from-package, not both")
    candidates = [Path(audio)] if audio else [ROOT / "assets/audio/雨爱DJ.mp3", WORKSPACE / "雨爱DJ.mp3"]
    music_path = next((path for path in candidates if path.is_file()), None)
    if audio and music_path is None:
        raise FileNotFoundError(f"Audio file not found: {audio}")
    if music_path is not None and package is None:
        music = music_path.read_bytes()
    else:
        # Original audio is not distributed with the source repository.
        if package is None:
            package = next(WORKSPACE.glob("Rainie_Love_On_Reinforcement_Depletion_V0.2.7_*.zip"), None)
        if package is None:
            raise FileNotFoundError("Supply the original MP3 with --audio PATH or a previously downloaded mod ZIP with --from-package PATH")
        with zipfile.ZipFile(package) as z:
            if z.testzip() is not None:
                raise ValueError("Input package failed ZIP integrity check")
            original = z.read("Addon/" + PATCH)
        size = struct.unpack_from("<I", original, 192)[0]
        lua = original[200:200+size].decode("utf-8")
        match = re.search(r'local audio64 = \{(.*?)\n  \}', lua, re.S)
        if not match:
            raise ValueError("Original package has no embedded audio table")
        music = base64.b64decode("".join(re.findall(r'"([A-Za-z0-9+/=]+)"', match.group(1))), validate=True)
    if len(music) != 6319567 or hashlib.sha256(music).hexdigest() != "b0659832d46bd6f3633adac8723c624ccdae8ece72c53e9928a68f476ead314e":
        raise ValueError("Audio does not match the original Rainie Love track required by v0.2.9")
    return music

def main():
    parser = argparse.ArgumentParser(description="Build the v0.2.9 Arsenal/HD2MM ZIP using locally supplied audio.")
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--audio", type=Path, help="Original 雨爱DJ.mp3 (not included in Git)")
    inputs.add_argument("--from-package", type=Path, help="Extract the original track from a locally supplied mod ZIP")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "release")
    args = parser.parse_args()
    music = load_music(args.audio, args.from_package)
    encoded = base64.b64encode(music).decode("ascii")
    chunks = "\n".join(f'    "{encoded[i:i+32768]}",' for i in range(0, len(encoded), 32768))
    template = (ROOT / "src/rainie_love.lua.in").read_text("utf-8")
    template = template.replace("__MISSION_BOUNDARY__", (ROOT / "src/mission_boundary.lua").read_text("utf-8"))
    source = template.replace("__AUDIO_BASE64__", chunks).encode("utf-8")
    data = archive(source)
    guid = str(uuid.uuid5(uuid.NAMESPACE_URL, "https://local.c09nat/helldivers2/rainie-love"))
    desc = "Plays Rainie Love when an activated reinforcement budget is depleted and only one Helldiver remains alive. Adjustable volume and fade-out, music preview, decoder prewarming, extraction-shuttle detection, and native mission-end lockout even when extraction is missed. Requires Bingus Shared Loader v15+. No HD2Runtime dependency."
    manifest = {"Version":1,"Guid":guid,"Name":f"Rainie Love on Reinforcement Depletion v{VERSION}","Description":desc,
      "Options":[{"Name":"增援耗尽自动播放雨爱","Description":desc,"Include":["Addon"]}]}
    readme = ("增援耗尽自动播放雨爱 / Rainie Love on Reinforcement Depletion\n"
              "需要 Bingus Shared Loader v15+。支持音量、1-30 秒淡出时间和试听开关；淡入固定 1 秒。\n"
              "开局从未获得增援的特殊任务不会误触发；首次获得增援后才启用耗尽检测。\n"
              "登上撤离运输船后停止播放，并在结算及返回驱逐舰期间保持停止。\n"
              "v0.2.8：修复普通载具被误判为撤离运输船的问题；坦克、机甲和侦察车内可继续播放。\n"
              "v0.2.9：新增原生任务结束检测，修复错过撤离运输船后音乐持续播放的问题；结束后保持停播，下一局开始时重置。无需安装 HD2Runtime。\n"
              "日志：%LOCALAPPDATA%\\CowboyBingus\\Helldivers2\\Logs\\RainieLove.log\n")
    files={"manifest.json":(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n").encode(),"README.txt":readme.encode("utf-8"),
      "Addon/"+PATCH:data,"Addon/"+PATCH+".stream":b"","Addon/"+PATCH+".gpu_resources":b""}
    outdir=args.output_dir; outdir.mkdir(parents=True,exist_ok=True)
    out=outdir/f"Rainie-Love-on-Reinforcement-Depletion-v{VERSION}.zip"
    with zipfile.ZipFile(out,"w") as z:
      for name,body in sorted(files.items()):
        info=zipfile.ZipInfo(name,(2026,10,9,0,0,0)); info.compress_type=zipfile.ZIP_DEFLATED; info.external_attr=0o100644<<16; z.writestr(info,body)
    with zipfile.ZipFile(out) as z: assert z.testzip() is None
    print(json.dumps({"path":str(out),"bytes":out.stat().st_size,"sha256":hashlib.sha256(out.read_bytes()).hexdigest(),"music_sha256":hashlib.sha256(music).hexdigest()},ensure_ascii=False))

if __name__ == "__main__": main()
