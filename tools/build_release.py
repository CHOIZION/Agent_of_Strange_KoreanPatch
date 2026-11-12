import zipfile
import os
from pathlib import Path
import time
import sys

def build_release_zip(game_dir=None, output_zip=None):
    if not game_dir:
        game_dir = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Agent of Strange Arrival")
    else:
        game_dir = Path(game_dir)
        
    data_dir = game_dir / "Agent of Strange Arrival_Data"
    if not data_dir.is_dir():
        print(f"Error: Could not find game data directory at {data_dir}", file=sys.stderr)
        return False
        
    if not output_zip:
        repo_root = Path(__file__).resolve().parent.parent
        release_dir = repo_root / "release"
        release_dir.mkdir(parents=True, exist_ok=True)
        output_zip = release_dir / "Agent_of_Strange_Arrival_Korean_Patch_v1.0.zip"
    else:
        output_zip = Path(output_zip)
        output_zip.parent.mkdir(parents=True, exist_ok=True)

    files_to_pack = [
        data_dir / "level0",
        data_dir / "resources.assets",
        data_dir / "RuntimeInitializeOnLoads.json",
        data_dir / "ScriptingAssemblies.json",
        data_dir / "KoreanReview.screen",
        data_dir / "Managed" / "KoreanReview.dll"
    ]

    for f in files_to_pack:
        if not f.exists():
            print(f"Error: Missing patch file {f}", file=sys.stderr)
            return False

    print(f"Building release zip: {output_zip}")
    t0 = time.time()
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for f in files_to_pack:
            arcname = f.relative_to(game_dir)
            size_mb = f.stat().st_size / (1024 * 1024)
            print(f"  + Packing: {arcname} ({size_mb:.2f} MB)")
            zf.write(f, arcname)

    elapsed = time.time() - t0
    final_size_mb = output_zip.stat().st_size / (1024 * 1024)
    print(f"\n[Success] Created {output_zip.name} ({final_size_mb:.2f} MB) in {elapsed:.1f}s")
    return True

if __name__ == "__main__":
    build_release_zip()
