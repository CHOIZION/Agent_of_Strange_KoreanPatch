from pathlib import Path
from contextlib import contextmanager
import collections, hashlib, json, mmap, msvcrt, os, shutil, sqlite3, struct, subprocess, sys, tempfile, base64

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / 'data' / '번역.sqlite'
DLL_SRC = ROOT / 'data' / 'KoreanReview.dll'

DEFAULT_GAME = Path(r'C:\Program Files (x86)\Steam\steamapps\common\Agent of Strange Arrival')

def digest(path):
    if not path.exists():
        return None
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def write_json(path, data):
    tmp = path.with_suffix('.new')
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf8')
    os.replace(tmp, path)

def pack(text):
    raw = text.encode('utf8')
    return struct.pack('<I', len(raw)) + raw + bytes((-len(raw)) % 4)

@contextmanager
def exclusive(backup_dir):
    backup_dir.mkdir(exist_ok=True)
    with (backup_dir / 'review.lock').open('a+b') as lock:
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise RuntimeError('다른 프로그램이 게임 파일을 변경하고 있습니다.')
        try:
            yield
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)

def render_assets(original, target, db):
    groups = collections.defaultdict(list)
    for pid, pos, src, ko in db.execute('select pid,pos,original,ko from refs join entries using(id) join objects using(pid) where filename=? order by pid,pos', (original.name,)):
        groups[pid].append((pos, src, ko))
    shutil.copyfile(original, target)
    with original.open('rb') as fp, mmap.mmap(fp.fileno(), 0, access=mmap.ACCESS_READ) as data, target.open('r+b') as out:
        base = struct.unpack_from('>Q', data, 32)[0]
        tail = len(data)
        for pid, start, size, meta in db.execute('select pid,offset,size,metadata from objects where filename=? order by pid', (original.name,)):
            actual_id, offset, old_size = struct.unpack_from('<qqI', data, meta)
            if (actual_id, base + offset, old_size) != (pid, start, size):
                raise RuntimeError('게임의 리소스 구조가 변경되었습니다.')
            old = data[start:start + size]
            new = bytearray()
            cursor = 0
            for pos, src, ko in groups[pid]:
                field = pack(src)
                if pos < cursor or old[pos:pos + len(field)] != field:
                    raise RuntimeError('게임의 원문이 번역 데이터와 다릅니다.')
                new.extend(old[cursor:pos])
                new.extend(pack(ko))
                cursor = pos + len(field)
            new.extend(old[cursor:])
            tail = (tail + 7) & ~7
            out.seek(tail)
            out.write(new)
            out.seek(meta + 8)
            out.write(struct.pack('<qI', tail - base, len(new)))
            tail += len(new)
        out.seek(24)
        out.write(struct.pack('>Q', tail))
        out.flush()
        os.fsync(out.fileno())

def operation(game_path=None, restore=False, progress=print):
    game = Path(game_path) if game_path else DEFAULT_GAME
    data_dir = game / 'Agent of Strange Arrival_Data'
    backup_dir = game / 'KoreanReviewBackup'
    dll_rel = 'Managed/KoreanReview.dll'

    if not data_dir.is_dir():
        raise RuntimeError(f'게임 설치 폴더를 찾을 수 없습니다: {game}')

    with exclusive(backup_dir), sqlite3.connect(DB) as db:
        db.execute('begin')
        originals = dict(db.execute('select * from originals'))
        originals[dll_rel] = None
        originals["KoreanReview.screen"] = None
        statepath = backup_dir / 'state.json'
        state = json.loads(statepath.read_text('utf8')) if statepath.exists() else {}

        progress('현재 게임 파일 확인 중…')
        live = {name: digest(data_dir / name) for name in originals}
        for name, orig in originals.items():
            if live[name] not in [orig, *state.get(name, [])]:
                raise RuntimeError('다른 빌드 또는 수정된 파일을 발견했습니다.\n' + name)

        if restore and live == originals:
            progress('이미 원본 상태입니다.')
            return

        with tempfile.TemporaryDirectory(dir=backup_dir, prefix='stage-') as tempdir:
            stage = Path(tempdir)
            for name, orig in originals.items():
                if orig is None:
                    continue
                backup = backup_dir / name
                if not backup.exists() and live[name] == orig:
                    tmp = stage / ('backup-' + Path(name).name)
                    shutil.copyfile(data_dir / name, tmp)
                    os.replace(tmp, backup)
                if digest(backup) != orig:
                    raise RuntimeError('원본 백업을 확인할 수 없습니다.\n' + name)

            if restore:
                targets = originals.copy()
                for name, orig in originals.items():
                    if orig and live[name] != orig:
                        shutil.copyfile(backup_dir / name, stage / Path(name).name)
            else:
                progress('한국어 번역과 한글 글꼴 적용 파일 생성 중…')
                for name, in db.execute('select distinct filename from objects'):
                    render_assets(backup_dir / name, stage / name, db)
                for name in ['ScriptingAssemblies.json', 'RuntimeInitializeOnLoads.json']:
                    data = json.loads((backup_dir / name).read_text('utf-8-sig'))
                    if name.startswith('Scripting'):
                        data['names'].append('KoreanReview.dll')
                        data['types'].append(16)
                    else:
                        data['root'].append(dict(assemblyName='KoreanReview', nameSpace='KoreanReview', className='DisplaySupport', methodName='StartReview', loadTypes=1, isUnityClass=False))
                    (stage / name).write_text(json.dumps(data, separators=(',', ':')), encoding='utf8')

                shutil.copyfile(DLL_SRC, stage / 'KoreanReview.dll')
                with (stage / 'KoreanReview.screen').open('w', encoding='ascii') as screen:
                    for en, ko in db.execute("select coalesce(nullif(en,''),ru),ko from entries where substr(key,1,8)='@screen:'"):
                        enc = lambda value: base64.b64encode(value.encode('utf8')).decode('ascii')
                        screen.write(enc(en) + '\t' + enc(ko) + '\n')

                targets = {name: digest(stage / Path(name).name) for name in originals}

            write_json(statepath, {n: [live[n], targets[n]] for n in originals})
            progress('게임 파일 반영 중…')
            for name, target in targets.items():
                if live[name] == target:
                    continue
                if target is None:
                    (data_dir / name).unlink()
                else:
                    os.replace(stage / Path(name).name, data_dir / name)
            write_json(statepath, {n: [v] for n, v in targets.items()})
            progress('완료되었습니다!')

if __name__ == '__main__':
    operation()
