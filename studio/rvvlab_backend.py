"""Shared SSH / snapshot / native test backend for RVV Lab RVV Studio v5.0.1.
No secrets or service-side package installs. SSH server key pinned before auth.
"""
from __future__ import annotations
import base64, hashlib, datetime as dt, fnmatch, json, os, re, shlex, subprocess, time, zipfile, codecs
from pathlib import Path, PurePosixPath

DEFAULT_HOST='' # Explicit host required in .env
DEFAULT_PORT=22
DEFAULT_USER='' # Explicit user required in .env
HOST_FINGERPRINT='' # Explicit pinned fingerprint required in .env
DEFAULT_REMOTE_NAME='rvvlab-v5'
CONFIG_DIR=Path.home()/'.rvvlab_lab_v3'
SETTINGS_PATH=CONFIG_DIR/({'Cloud-V':'settings_cloudv.json','EPCC':'settings_epcc.json'}.get(os.environ.get('RVVLAB_STUDIO_TARGET',''),'settings.json'))
DEFAULT_RESULTS=Path.home()/'RVV_Lab_results'
REMOTE_NAME_RE=re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,59}$')
SKIP_DIRS={'.git','.hg','.svn','.idea','.vs','.vscode','.venv','venv','.ssh','.aws','.kube','.tox','build','dist','__pycache__','.mypy_cache','.pytest_cache','.ruff_cache','node_modules','rvv-server-runs','rvv-native-runs','rvv-perf-lab','coverage','_build'}
SECRET_GLOBS=('.env','.env.*','*.pem','*.p12','*.pfx','*.key','id_rsa*','id_ed25519*','*credentials*','*password*','*.secret','*.token','*.ppk')

EXTRACT_PY = r'''
import hashlib, os, pathlib, stat, sys, zipfile
source, destination, expected = sys.argv[1:4]
sha = hashlib.sha256()
with open(source, 'rb') as f:
    while True:
        block = f.read(1024 * 1024)
        if not block: break
        sha.update(block)
actual = sha.hexdigest()
if actual != expected:
    raise SystemExit('Uploaded ZIP SHA256 mismatch')
target = pathlib.Path(destination)
if target.exists():
    raise SystemExit('Target already exists; refusing overwrite')
target.mkdir(parents=True)
with zipfile.ZipFile(source) as z:
    for info in z.infolist():
        p = pathlib.PurePosixPath(info.filename)
        if p.is_absolute() or not p.parts or '..' in p.parts or '\\' in info.filename:
            raise SystemExit('Unsafe path in ZIP: ' + info.filename)
        if (info.external_attr >> 16) & 0o170000 == stat.S_IFLNK:
            raise SystemExit('Symlinks not allowed in ZIP')
        dest = target.joinpath(*p.parts)
        if info.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as fin, open(dest, 'wb') as fout:
                while True:
                    block = fin.read(1024*1024)
                    if not block: break
                    fout.write(block)
print('Deployed:', target)
print('Archive SHA256:', actual)
'''


def utc_id() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def git_snapshot(root: Path) -> dict:
    result = {"commit": None, "branch": None, "dirty": None}
    args = {"commit": ["rev-parse", "HEAD"], "branch": ["branch", "--show-current"],
            "dirty": ["status", "--porcelain=v1"]}
    for field, opts in args.items():
        try:
            cp = subprocess.run(["git", "-C", str(root), *opts], capture_output=True,
                                text=True, timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if cp.returncode == 0:
                value = cp.stdout.strip()
                result[field] = bool(value) if field == "dirty" else value
        except (OSError, subprocess.SubprocessError):
            pass
    return result


def excluded(rel: Path) -> bool:
    if any(part in SKIP_DIRS or part.startswith("build-") for part in rel.parts[:-1]):
        return True
    if rel.name in SKIP_DIRS:
        return True
    if rel.name.lower().endswith((".zip", ".tar.gz", ".7z", ".log", ".pyc")):
        return True
    if any(fnmatch.fnmatch(rel.name.lower(), pat) for pat in SECRET_GLOBS):
        return True
    return False


def list_source_files(root: Path) -> list[Path]:
    """Use Git's tracked + non-ignored untracked files where possible."""
    try:
        cp = subprocess.run(["git", "-C", str(root), "ls-files", "--cached", "--others",
                             "--exclude-standard", "-z"], capture_output=True, timeout=30,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if cp.returncode == 0 and cp.stdout:
            paths = []
            for raw in cp.stdout.split(b"\0"):
                if not raw:
                    continue
                rel = Path(os.fsdecode(raw))
                file = root / rel
                if file.is_file() and not file.is_symlink() and not excluded(rel):
                    paths.append(rel)
            return sorted(set(paths), key=lambda x: x.as_posix())
    except (OSError, subprocess.SubprocessError):
        pass
    paths = []
    for current, dirs, names in os.walk(root, followlinks=False):
        rel_dir = Path(current).relative_to(root)
        dirs[:] = [d for d in dirs if not excluded(rel_dir / d)
                   and not (Path(current) / d).is_symlink()]
        for name in names:
            rel = rel_dir / name
            p = root / rel
            if not excluded(rel) and p.is_file() and not p.is_symlink():
                paths.append(rel)
    return sorted(paths, key=lambda x: x.as_posix())


def build_source_zip(root: Path, archive: Path, progress) -> dict:
    root = root.expanduser().resolve()
    if not (root / "CMakeLists.txt").is_file() or not (root / "scripts/rvv/server_control.py").is_file():
        raise ValueError("Select the simdjson-rvv-vla root (CMakeLists.txt et scripts/rvv/server_control.py requis).")
    import re
    version_file = root / 'include/simdjson/simdjson_version.h'
    version_text = version_file.read_text(encoding='utf-8', errors='replace') if version_file.is_file() else ''
    if not re.search(r'SIMDJSON_VERSION_MAJOR\s*=\s*5\b', version_text) or not re.search(r'SIMDJSON_VERSION_MINOR\s*=\s*0\b', version_text):
        raise ValueError('RVV Lab Studio v5 requires simdjson 5.0.x sources; select the fresh v5 checkout')
    if not (root / 'src/rvv/stream_support.h').is_file():
        raise ValueError('The RVV-VLA v5 streaming integration is missing in the selected repository')
    files = list_source_files(root)
    if len(files) < 20:
        raise ValueError("Too few files detected in repository.")
    git = git_snapshot(root)
    count = 0
    total_bytes = 0
    manifest = {"created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "source": "bundled-engine", "github": "project-source:bundled-engine",
                "git": git, "file_count": len(files)}
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=4) as z:
        z.writestr("rvvlab-source-manifest.json", json.dumps(manifest, indent=2) + "\n")
        for rel in files:
            file = root / rel
            try:
                if file.stat().st_size > 100 * 1024 * 1024:
                    raise ValueError(f"File too large (>100 MiB) : {rel}")
                z.write(file, rel.as_posix())
                total_bytes += file.stat().st_size
                count += 1
                if count % 100 == 0:
                    progress(f"Archive: {count}/{len(files)} files")
            except OSError as e:
                raise RuntimeError(f"Impossible de lire {rel}: {e}") from e
    digest = hash_file(archive)
    return {"zip_sha256": digest, "files": count, "bytes": total_bytes, "git": git,
            "source_root": str(root), "archive": str(archive)}


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as inp:
        for block in iter(lambda: inp.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate_remote_name(value: str) -> str:
    if not REMOTE_NAME_RE.fullmatch(value) or value in {".", ".."}:
        raise ValueError("Invalid remote folder (simple name, without slashes or spaces).")
    return value


def safe_uname(text: str) -> bool:
    return text.strip() == "riscv64"



RUN_ACTIONS={'preflight','smoke','phase1','auto','matrix','standard','publication'}


def discover_env_file(lab_root: Path) -> Path:
    """Use an external user-owned .env without copying it into this repo.

    Priority: explicit RVVLAB_ENV_FILE; parent workspace .env; the
    standalone Lab orchestration .env; Studio-local .env. No secrets
    are read until parse_env is invoked during a requested SSH action.
    """
    root = Path(lab_root).expanduser().resolve()
    explicit = os.environ.get('RVVLAB_ENV_FILE', '').strip()
    if explicit:
        return Path(explicit).expanduser()
    for candidate in (root.parent / '.env', root / 'orchestrator' / '.env',
                      root / 'studio' / '.env'):
        if candidate.is_file():
            return candidate
    return root / 'orchestrator' / '.env'


def parse_env(path: Path) -> dict:
    """Load only recognized SSH variables; accept legacy CLOUDV_ keys.

    The original file stays at its chosen location. No execution, env
    interpolation, connection, rewriting or logging of secret values.
    RVVLAB_* values take precedence over legacy CLOUDV_* if both exist.
    """
    path = Path(path).expanduser()
    if path.is_symlink():
        raise ValueError('Symlinked .env is not permitted')
    if not path.is_file():
        raise FileNotFoundError(f'SSH .env not found: {path}')
    names = ('HOST', 'PORT', 'USER', 'PASSWORD', 'HOST_SHA256', 'SSH_KEY',
             'JUMP_HOST', 'JUMP_PORT', 'JUMP_USER', 'JUMP_PASSWORD',
             'JUMP_HOST_SHA256', 'JUMP_KEY', 'JUMP_ALLOW_AGENT', 'JUMP_KEY_PASSPHRASE',
             'SSH_KEY_PASSPHRASE', 'INSECURE_EPCC_TEST_MODE')
    allowed = {prefix + name for prefix in ('RVVLAB_', 'CLOUDV_') for name in names}
    data = {}
    for i, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        if '=' not in line:
            continue
        key, val = line.split('=', 1)
        key, val = key.strip(), val.strip()
        if key not in allowed:
            continue
        if val.startswith(('"', "'")):
            if len(val) < 2 or val[-1] != val[0]:
                raise ValueError(f'.env: mismatched quote at line {i}')
            val = val[1:-1]
        if '\x00' in val:
            raise ValueError('.env: invalid value')
        data[key] = val

    def opt(name: str) -> str:
        return data.get('RVVLAB_' + name) or data.get('CLOUDV_' + name) or ''

    host = opt('HOST') or DEFAULT_HOST
    user = opt('USER') or DEFAULT_USER
    try:
        port = int(opt('PORT') or DEFAULT_PORT)
    except ValueError:
        raise ValueError('Invalid .env port') from None
    if (not re.fullmatch(r'[A-Za-z0-9.-]+', host) or
        not re.fullmatch(r'[A-Za-z0-9_-]+', user) or
        not 1 <= port <= 65535):
        raise ValueError('Invalid SSH host, user or port in .env')
    jump_host = opt('JUMP_HOST')
    unverified_test = opt('INSECURE_EPCC_TEST_MODE') == '1'
    if opt('INSECURE_EPCC_TEST_MODE') not in ('', '0', '1'):
        raise ValueError('INSECURE_EPCC_TEST_MODE must be 0 or 1')
    if unverified_test and not (
        jump_host == 'gateway.epcc.ed.ac.uk' and
        (host == 'riscv-login.epcc.ed.ac.uk' or host.endswith('.epcc.ed.ac.uk'))):
        raise ValueError('Unverified testing mode is allowed for EPCC gateway+host ONLY')
    jump_host = opt('JUMP_HOST')
    unverified_test = opt('INSECURE_EPCC_TEST_MODE') == '1'
    if opt('INSECURE_EPCC_TEST_MODE') not in ('', '0', '1'):
        raise ValueError('INSECURE_EPCC_TEST_MODE must be 0 or 1')
    if unverified_test and not (
        jump_host == 'gateway.epcc.ed.ac.uk' and
        (host == 'riscv-login.epcc.ed.ac.uk' or host.endswith('.epcc.ed.ac.uk'))):
        raise ValueError('Unverified testing mode is allowed for EPCC gateway+host ONLY')
    expected = opt('HOST_SHA256') or HOST_FINGERPRINT
    if not unverified_test and not re.fullmatch(r'SHA256:[A-Za-z0-9+/]{43}', expected):
        raise ValueError('Missing/invalid SSH host fingerprint: set RVVLAB_HOST_SHA256 or CLOUDV_HOST_SHA256 in .env')
    cfg = {'host': host, 'user': user, 'port': port,
           'host_fingerprint': expected if not unverified_test else '',
           'unverified_epcc_test_mode': unverified_test,
           'password': opt('PASSWORD'), 'key': opt('SSH_KEY'),
           'key_passphrase': opt('SSH_KEY_PASSPHRASE')}
    jump_host = opt('JUMP_HOST')
    if jump_host:
        jump_user = opt('JUMP_USER')
        jump_key_fp = opt('JUMP_HOST_SHA256')
        try:
            jump_port = int(opt('JUMP_PORT') or '22')
        except ValueError:
            raise ValueError('Invalid SSH jump port') from None
        if (not re.fullmatch(r'[A-Za-z0-9.-]+', jump_host) or
            not re.fullmatch(r'[A-Za-z0-9_-]+', jump_user) or
            not 1 <= jump_port <= 65535 or
            (not unverified_test and not re.fullmatch(r'SHA256:[A-Za-z0-9+/]{43}', jump_key_fp))):
            raise ValueError('Invalid SSH gateway host/user/port or missing verified RVVLAB_JUMP_HOST_SHA256')
        agent = opt('JUMP_ALLOW_AGENT').lower()
        if agent not in ('', '0', '1', 'true', 'false', 'yes', 'no'):
            raise ValueError('JUMP_ALLOW_AGENT must be 0 or 1')
        cfg['jump'] = {'host':jump_host,'port':jump_port,'user':jump_user,
                       'host_fingerprint':jump_key_fp if not unverified_test else '',
                       'password':opt('JUMP_PASSWORD'),'key':opt('JUMP_KEY'),
                       'key_passphrase':opt('JUMP_KEY_PASSPHRASE'),
                       'allow_agent':agent in ('1','true','yes')}
    elif any(opt(name) for name in ('JUMP_PORT', 'JUMP_USER', 'JUMP_PASSWORD',
                                     'JUMP_HOST_SHA256','JUMP_KEY','JUMP_ALLOW_AGENT',
                                     'JUMP_KEY_PASSPHRASE')):
        raise ValueError('JUMP_HOST must be set when SSH gateway fields are configured')
    return cfg


def preferred_repo(app_dir:Path) -> Path:
    """Always prefer this Lab's engine, while allowing an explicit override."""
    import os
    override=os.environ.get('RVVLAB_ENGINE_PATH','').strip()
    if override:
        return Path(override).expanduser().resolve()
    return (Path(app_dir).resolve().parent/'engine').resolve()


def config_for_run(cfg:dict)->dict:
    cfg=dict(cfg)
    name=validate_remote_name(cfg['remote_name'])
    cfg['remote_name']=name
    try:jobs=int(cfg['jobs'])
    except (TypeError,ValueError):raise ValueError('Jobs must be an integer') from None
    if not 1<=jobs<=8:raise ValueError('Jobs: choose between 1 and 8')
    cfg['jobs']=jobs
    bits=str(cfg.get('vls_bits') or '').strip()
    if bits and (not all(i in {'128','256','512'} for i in bits.split(',')) or len(set(bits.split(',')))!=len(bits.split(','))):
        raise ValueError('VLS must be 128, 256, 512 or a list without duplicates')
    cfg['vls_bits']=bits
    core=str(cfg.get('core') or '').strip()
    if core and not re.fullmatch(r'\d{1,3}',core):raise ValueError('Invalid CPU core')
    cfg['core']=core
    for name in ('gcc_cc','gcc_cxx','clang_cc','clang_cxx'):
        value=str(cfg.get(name) or '').strip()
        if value and not re.fullmatch(r'[A-Za-z0-9_.+/-]+',value):raise ValueError('Invalid compiler: '+name)
        cfg[name]=value
    if bool(cfg['gcc_cc']) != bool(cfg['gcc_cxx']) or bool(cfg['clang_cc']) != bool(cfg['clang_cxx']):
        raise ValueError('C / C++ compilers must be specified as a pair')
    return cfg


class PinnedHostKey:
    def __init__(self,expected):self.expected=expected
    def missing_host_key(self,client,hostname,key):
        actual='SHA256:'+base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        if actual!=self.expected:
            raise RuntimeError('SSH HOST FINGERPRINT MISMATCH. Expected '+self.expected+'; received '+actual)


class StudioSSH:
    """One app-wide SSHClient, multiple SSH/SFTP channels for Console, Tests, Reports."""
    def __init__(self):
        self.client=None
        self.gateway_client=None
        self.jump_channel=None
        self.home=None
    def connected(self):
        try:
            target=bool(self.client and self.client.get_transport() and
                        self.client.get_transport().is_active())
            if self.gateway_client:
                target=target and bool(self.gateway_client.get_transport() and
                                       self.gateway_client.get_transport().is_active())
            return target
        except Exception:
            return False
    @staticmethod
    def _ssh_options(entry):
        opts=dict(hostname=entry['host'],port=entry['port'],username=entry['user'],
                  timeout=20,auth_timeout=25,banner_timeout=25,
                  allow_agent=bool(entry.get('allow_agent',False)),look_for_keys=False)
        if entry.get('password'):
            opts['password']=entry['password']
        if entry.get('key'):
            key=Path(entry['key']).expanduser()
            if not key.is_file():
                raise ValueError('SSH key not found: '+str(key))
            opts['key_filename']=str(key)
        return opts
    @staticmethod
    def _epcc_gateway_connect(entry, env):
        """EPCC public-key THEN keyboard-interactive MFA (partial auth).

        Standard SSHClient.connect() does not guarantee the EPCC key+TOTP flow.
        Never cache, log, save or transmit a TOTP outside the SSH protocol.
        """
        import base64, hashlib, socket
        import paramiko
        sock=socket.create_connection((entry['host'],entry['port']),timeout=20)
        t=paramiko.Transport(sock)
        try:
            t.start_client(timeout=25)
            remote_key=t.get_remote_server_key()
            got='SHA256:'+base64.b64encode(hashlib.sha256(remote_key.asbytes()).digest()).decode().rstrip('=')
            pinned=entry.get('host_fingerprint','')
            if pinned and got!=pinned:
                raise RuntimeError('EPCC gateway SSH host key mismatch. Expected '+pinned+'; received '+got)
            if not pinned and not env.get('unverified_epcc_test_mode'):
                raise RuntimeError('Missing verified EPCC gateway host key fingerprint')
            user=entry['user']
            key_path=entry.get('key')
            if not key_path:
                raise RuntimeError('EPCC gateway needs a private SSH key; set RVVLAB_JUMP_KEY in .env.epcc')
            # EPCC login uses an ED25519 key stored by the user, not the .pub file.
            pkey=paramiko.Ed25519Key.from_private_key_file(str(Path(key_path).expanduser()),
                    password=entry.get('key_passphrase') or None)
            remaining=t.auth_publickey(user,pkey)
            if not t.is_authenticated():
                if 'keyboard-interactive' not in remaining:
                    raise RuntimeError('EPCC gateway did not offer keyboard-interactive MFA after SSH key')
                code=entry.get('totp_code','').strip()
                if not code or not code.isdigit() or len(code)!=6:
                    raise RuntimeError('Studio needs a current 6-digit EPCC MFA code')
                def handler(title,instructions,prompts):
                    # Never store the TOTP or echo prompts/response into Studio logs.
                    return [code if echo is False or ('otp' in prompt.lower() or 'code' in prompt.lower()) else ''
                            for prompt,echo in prompts]
                t.auth_interactive(user,handler)
            if not t.is_authenticated():
                raise RuntimeError('EPCC gateway MFA failed')
            t.set_keepalive(30)
            client=paramiko.SSHClient()
            client._transport=t
            return client,pkey
        except Exception:
            t.close()
            raise

    def connect(self,env:dict):
        if self.connected():return
        import paramiko
        target=paramiko.SSHClient()
        gateway=None
        jump_channel=None
        try:
            key=None
            if env.get('jump'):
                if env.get('profile_label')=='EPCC':
                    gateway,key=self._epcc_gateway_connect(env['jump'],env)
                else:
                    gateway=paramiko.SSHClient()
                    gateway.set_missing_host_key_policy(paramiko.AutoAddPolicy() if env.get('unverified_epcc_test_mode') else PinnedHostKey(env['jump']['host_fingerprint']))
                    gateway.connect(**self._ssh_options(env['jump']))
                    gateway.get_transport().set_keepalive(30)
                # The gateway is transport-only; NO shell/session is opened there.
                jump_channel=gateway.get_transport().open_channel(
                    'direct-tcpip',(env['host'],env['port']),('127.0.0.1',0),timeout=20)
                if not jump_channel:raise RuntimeError('Gateway rejected SSH forwarding to internal host')
            target.set_missing_host_key_policy(paramiko.AutoAddPolicy() if env.get('unverified_epcc_test_mode') else PinnedHostKey(env['host_fingerprint']))
            opts=self._ssh_options(env)
            if jump_channel is not None:opts['sock']=jump_channel
            if key is not None and env.get('key') and env['key'].replace('\\','/').lower()==env['jump'].get('key','').replace('\\','/').lower():
                # Reuse already unlocked key; do NOT prompt for its passphrase again.
                opts.pop('key_filename',None)
                opts['pkey']=key
            target.connect(**opts)
            target.get_transport().set_keepalive(30)
            sftp=target.open_sftp()
            try:home=sftp.normalize('.')
            finally:sftp.close()
            if not home.startswith('/'):
                raise ValueError('Invalid remote SSH directory')
            self.client=target
            self.gateway_client=gateway
            self.jump_channel=jump_channel
            self.home=home.rstrip('/')
        except Exception:
            target.close()
            if jump_channel is not None:jump_channel.close()
            if gateway is not None:gateway.close()
            raise
    def close(self):
        if self.client:
            self.client.close()
        if self.jump_channel:
            self.jump_channel.close()
        if self.gateway_client:
            self.gateway_client.close()
        self.client=None
        self.jump_channel=None
        self.gateway_client=None
        self.home=None
    def open_shell(self):
        if not self.connected():raise RuntimeError('Connect to RVV Lab')
        chan=self.client.get_transport().open_session(timeout=20)
        chan.get_pty(term='dumb',width=120,height=36)
        chan.invoke_shell()
        return chan
    def exec_stream(self,cmd:str,callback,stop=None):
        if not self.connected():raise RuntimeError('SSH disconnected')
        channel=self.client.get_transport().open_session(timeout=20)
        try:
            channel.exec_command('bash -lc '+shlex.quote(cmd+' 2>&1'))
            decoder=codecs.getincrementaldecoder('utf-8')('replace')
            pending=''
            while True:
                if stop is not None and stop.is_set():
                    channel.close()
                    raise RuntimeError('SSH command interrupted on client side. Check remote processes.')
                if channel.recv_ready():
                    data=channel.recv(65536)
                    pending+=decoder.decode(data)
                    lines=pending.split('\n');pending=lines.pop()
                    for line in lines:callback(line.rstrip('\r'))
                elif channel.exit_status_ready() and not channel.recv_ready():break
                else:time.sleep(.08)
            pending+=decoder.decode(b'',final=True)
            for line in pending.splitlines():callback(line.rstrip('\r'))
            return channel.recv_exit_status()
        finally:channel.close()
    def exec_text(self,cmd):
        chunks=[]
        rc=self.exec_stream(cmd,chunks.append)
        if rc:raise RuntimeError('SSH command failed ('+str(rc)+'): '+str(chunks[-4:]))
        return '\n'.join(chunks)
    def base(self,remote_name):return self.home+'/'+validate_remote_name(remote_name)
    def mkdir(self,path):
        sftp=self.client.open_sftp()
        try:
            walk=''
            for item in PurePosixPath(path).parts[1:]:
                walk+='/'+item
                try:sftp.stat(walk)
                except IOError:sftp.mkdir(walk)
        finally:sftp.close()
    def deploy(self,archive:Path,manifest:dict,run_id:str,remote_name:str,callback,stop=None):
        base=self.base(remote_name)
        self.mkdir(base+'/incoming');self.mkdir(base+'/sources');self.mkdir(base+'/results')
        target=base+'/sources/'+run_id
        remote_zip=base+'/incoming/'+run_id+'.zip'
        if stop is not None and stop.is_set():raise RuntimeError('Transfer cancelled')
        # SFTP channels on Cloud-V can close mid-transfer (observed EOF at 20%).
        # Re-open the SFTP channel and resume the SAME remote file, never
        # restart an unrelated experiment. SHA256 is checked by EXTRACT_PY.
        total=archive.stat().st_size
        last=[-1]
        for attempt in range(1,6):
            if stop is not None and stop.is_set():raise RuntimeError('Transfer cancelled')
            if not self.connected():
                raise RuntimeError('SSH connection dropped during source upload. Reconnect Studio and retry Test94; no remote benchmark was launched.')
            sftp=None
            try:
                sftp=self.client.open_sftp()
                sftp.get_channel().settimeout(90)
                try:offset=sftp.stat(remote_zip).st_size
                except OSError:offset=0
                if offset>total:
                    sftp.remove(remote_zip);offset=0
                # Writing to an existing partial file must use an explicit seek,
                # not SFTP append mode (which may ignore offsets on some servers).
                mode='r+b' if offset else 'wb'
                with archive.open('rb') as local, sftp.open(remote_zip,mode,bufsize=0) as remote:
                    remote.set_pipelined(False)
                    local.seek(offset)
                    remote.seek(offset)
                    sent=offset
                    while sent<total:
                        if stop is not None and stop.is_set():raise RuntimeError('Transfer cancelled')
                        block=local.read(min(65536,total-sent))
                        if not block:raise IOError('Unexpected local archive EOF')
                        remote.write(block);sent+=len(block)
                        pct=int(sent*100/max(total,1))
                        if pct//10!=last[0]//10:
                            last[0]=pct;callback(f'SFTP : {pct}%')
                if sftp.stat(remote_zip).st_size!=total:
                    raise IOError('Remote upload size mismatch')
                break
            except Exception as error:
                if stop is not None and stop.is_set():raise
                if attempt>=5:
                    raise RuntimeError('SFTP source transfer failed after 5 resumable attempts ('+
                                       type(error).__name__+': '+str(error)+'). '+
                                       'No benchmark was started. Check SSH/SFTP connection and remote disk.') from error
                callback(f'SFTP interruption ({type(error).__name__}); resume attempt {attempt+1}/5')
                import time as _time
                _time.sleep(min(attempt,3))
            finally:
                if sftp is not None:
                    try:sftp.close()
                    except Exception:pass
        command='python3 -c '+shlex.quote(EXTRACT_PY)+' '+shlex.quote(remote_zip)+' '+shlex.quote(target)+' '+shlex.quote(manifest['zip_sha256'])
        if self.exec_stream(command,callback,stop)!=0:raise RuntimeError('RVV Lab SHA256 verification/extraction failed')
        try:
            sftp=self.client.open_sftp()
            try:sftp.remove(remote_zip)
            finally:sftp.close()
        except OSError:pass
        return target
    def run(self,target:str,run_id:str,action:str,cfg:dict,callback,stop=None):
        if action not in RUN_ACTIONS:raise ValueError('Action not allowed')
        cfg=config_for_run(cfg)
        base=self.base(cfg['remote_name']);dest=base+'/results/'+run_id
        env_names={'gcc_cc':'RVV_NATIVE_CC','gcc_cxx':'RVV_NATIVE_CXX','clang_cc':'RVV_NATIVE_CLANG_CC','clang_cxx':'RVV_NATIVE_CLANG_CXX'}
        prefix=' '.join(f'{name}={shlex.quote(cfg[key])}' for key,name in env_names.items() if cfg[key])
        cmd=['python3','scripts/rvv/server_control.py',action,'--results-root',dest,'--jobs',str(cfg['jobs'])]
        if cfg['vls_bits'] and action != 'preflight':cmd+=['--vls-bits',cfg['vls_bits']]
        if cfg['core']:cmd+=['--core',cfg['core']]
        line='cd '+shlex.quote(target)+' && '+(prefix+' ' if prefix else '')+'PYTHONUNBUFFERED=1 '+' '.join(shlex.quote(i) for i in cmd)
        callback('=== Tests : '+action+' ===')
        return self.exec_stream(line,callback,stop)
    def available_kib(self):
        text=self.exec_text("df -Pk ~ | tail -n 1 | awk '{print $4}'")
        try:return int(text.strip().splitlines()[-1])
        except (ValueError,IndexError):return None
