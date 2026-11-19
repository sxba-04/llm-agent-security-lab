"""Exercise a fixed Linux namespace boundary with disposable files and a loopback listener.

Run without arguments on a Linux host with /usr/bin/{python3,ldd,bwrap,unshare}.
The report describes this reference process on this host. Exit status is 0 for
all checks passed, 1 for a failed check and 2 for an inconclusive/setup error.
No provider, network service, project workspace, credentials or study inputs
are needed. The only attempted connection is to the probe's own IPv4 listener.
"""
from __future__ import annotations

import datetime
import hashlib
import inspect
import json
import os
from pathlib import Path
import platform
import secrets
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading


RUNTIME = "/usr/bin/python3"
BWRAP = "/usr/bin/bwrap"
UNSHARE = "/usr/bin/unshare"
MARKER = "LAB_SYNTHETIC_PARENT_MARKER"


def namespace_ids():
    return {name: os.readlink("/proc/self/ns/" + name) for name in ("mnt", "pid", "net", "user")}


def child_observations(spec):
    """This function and namespace_ids are the complete, fixed child program."""
    import errno

    def access(path, mode):
        try:
            with open(path, mode) as stream:
                if mode == "ab":
                    stream.write(b"unexpected write")
                else:
                    stream.read(1)
            return "allowed"
        except OSError as error:
            return errno.errorcode.get(error.errno, "UNKNOWN")

    # Opening in r+b requests write access to an existing marker without creating or changing it.
    private = spec["private"]
    private_read = access(private, "rb")
    private_write = access(private, "r+b")
    content = None
    try:
        with open("/fixture/input", "rb") as stream:
            content = stream.read(128)
        input_read = "allowed"
    except OSError as error:
        input_read = errno.errorcode.get(error.errno, "UNKNOWN")
    input_write = access("/fixture/input", "ab")
    try:
        with open("/fixture/output", "wb") as stream:
            stream.write(b"child:" + (content or b""))
        output_write = "allowed"
    except OSError as error:
        output_write = errno.errorcode.get(error.errno, "UNKNOWN")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as endpoint:
        endpoint.settimeout(1)
        try:
            endpoint.connect(("127.0.0.1", spec["port"]))
            network = "connected"
        except OSError as error:
            network = errno.errorcode.get(error.errno, "UNKNOWN")
    with open("/proc/net/dev", encoding="ascii") as stream:
        interfaces = [line.split(":", 1)[0].strip() for line in stream if ":" in line]
    with open("/proc/self/status", encoding="ascii") as stream:
        status = dict(line.split(":", 1) for line in stream if ":" in line)
    return {"namespaces": namespace_ids(), "interfaces": interfaces, "parent_connect": network,
            "private_read": private_read, "private_write": private_write, "input_write": input_write,
            "input_read": input_read, "input_observed_hex": content.hex() if content is not None else None,
            "output_write": output_write, "environment_keys": sorted(os.environ),
            "environment_is_fixed": os.environ.get("LC_ALL") == "C" and os.environ.get("PWD", "/") == "/",
            "no_new_privs": int(status["NoNewPrivs"]), "capabilities": {
                name: status[name].strip() for name in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb")}}


class Echo(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(1)
        self.wfile.write(self.rfile.readline(80))


def round_trip(address):
    challenge = secrets.token_hex(24).encode() + b"\n"
    with socket.create_connection(address, timeout=1) as connection:
        connection.sendall(challenge)
        with connection.makefile("rb") as reply:
            return reply.readline(80) == challenge


def host_tcp_control(address, phase):
    try:
        if round_trip(address):
            return True
    except OSError as error:
        raise ValueError(f"Host loopback control {phase} failed: {type(error).__name__}") from error
    raise ValueError(f"Host loopback control {phase} returned the wrong nonce")


def system_output(args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=5,
                          env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"}).stdout


def runtime_mounts():
    # Identify the dependencies of a fixed system executable and its trusted stdlib modules.
    discover = ("import errno,json,os,socket,sys,sysconfig; "
                "files=[getattr(m,'__file__','') or '' for m in list(sys.modules.values())]; "
                "print(json.dumps([sysconfig.get_path('stdlib'),[f for f in files if f.endswith('.so')]]))")
    stdlib, extensions = json.loads(system_output([RUNTIME, "-I", "-S", "-c", discover]))
    executable = str(Path(RUNTIME).resolve(strict=True))
    libraries = set()
    for binary in (executable, *extensions):
        for line in system_output(["/usr/bin/ldd", binary]).splitlines():
            fields = line.split("=>")[-1].strip().split()
            if fields and fields[0].startswith("/"):
                libraries.add(fields[0])
    mounts = ["--ro-bind", executable, executable, "--ro-bind", stdlib, stdlib]
    for path in sorted(libraries):
        mounts.extend(["--ro-bind", path, path])
    return executable, mounts


def classify(parent, child, private_preserved, input_preserved, output_matches, expected_input_hex):
    """Assess child observations only after positive host controls succeeded."""
    return {"distinct_namespaces": all(parent[key] != child["namespaces"][key] for key in ("mnt", "pid", "net", "user")),
            "only_loopback_interface": child["interfaces"] == ["lo"],
            "parent_tcp_unreachable": child["parent_connect"] in {"ENETUNREACH", "EHOSTUNREACH", "ECONNREFUSED"},
            "private_absent_for_read_and_write": child["private_read"] == child["private_write"] == "ENOENT",
            "parent_marker_preserved": private_preserved,
            "input_read_only": (child["input_read"] == "allowed" and child["input_observed_hex"] == expected_input_hex
                                and child["input_write"] == "EROFS" and input_preserved),
            "writable_output_returned": child["output_write"] == "allowed" and output_matches,
            "only_fixed_environment": (child["environment_is_fixed"] and
                                       set(child["environment_keys"]) in ({"LC_ALL"}, {"LC_ALL", "PWD"})),
            "no_new_privileges": child["no_new_privs"] == 1,
            "no_permitted_effective_inheritable_or_ambient_caps": all(
                int(child["capabilities"][key], 16) == 0 for key in ("CapPrm", "CapEff", "CapInh", "CapAmb"))}


def run_probe():
    if platform.system() != "Linux":
        raise ValueError("A Linux namespace environment is required")
    versions = {"bubblewrap": system_output([BWRAP, "--version"]).strip(),
                "unshare": system_output([UNSHARE, "--version"]).strip()}
    executable, mounts = runtime_mounts()
    parent = namespace_ids()
    fixed_child = ("import json,os,socket,sys\n" + inspect.getsource(namespace_ids) + "\n" +
                   inspect.getsource(child_observations) + "\nprint(json.dumps(child_observations(json.load(sys.stdin))))")
    with tempfile.TemporaryDirectory(prefix="lab-isolation-", dir="/tmp") as root:
        private, given, output = (Path(root) / name for name in ("parent-only", "input", "output"))
        sentinel, nonce = secrets.token_bytes(24), secrets.token_bytes(24)
        private.write_bytes(sentinel)
        given.write_bytes(nonce)
        output.touch()
        controls = {"parent_can_read_written_private_marker": private.read_bytes() == sentinel,
                    "parent_can_read_written_input": given.read_bytes() == nonce}
        with socketserver.TCPServer(("127.0.0.1", 0), Echo) as listener:
            thread = threading.Thread(target=listener.serve_forever, args=(0.05,), daemon=True)
            thread.start()
            try:
                controls["host_tcp_nonce_before"] = host_tcp_control(listener.server_address, "before child")
                if not all(controls.values()):
                    raise ValueError("The host could not read back a newly written synthetic fixture")
                config = {"port": listener.server_address[1], "private": str(private)}
                # unshare creates the disconnected network namespace before bwrap sets up mounts and PID isolation.
                cmd = [UNSHARE, "--user", "--map-root-user", "--net", "--", BWRAP,
                       "--unshare-pid", "--die-with-parent", "--new-session", "--cap-drop", "ALL",
                       "--clearenv", "--setenv", "LC_ALL", "C", *mounts, "--proc", "/proc",
                       "--remount-ro", "/proc", "--ro-bind", str(given), "/fixture/input",
                       "--bind", str(output), "/fixture/output", "--remount-ro", "/", "--chdir", "/",
                       "--", executable, "-I", "-B", "-S", "-c", fixed_child]
                result = subprocess.run(cmd, input=json.dumps(config), text=True, capture_output=True, timeout=12,
                                        env={"LC_ALL": "C", MARKER: secrets.token_hex(12)}, close_fds=True)
            finally:
                try:
                    controls["host_tcp_nonce_after"] = host_tcp_control(listener.server_address, "after child")
                finally:
                    listener.shutdown()
                    thread.join(timeout=2)
        if result.returncode != 0:
            # No completed child observations: the launch cannot establish the boundary.
            raise ValueError("Fixed child unavailable: " + result.stderr.strip()[-350:])
        evidence = json.loads(result.stdout)
        checks = {**controls, **classify(parent, evidence, private.read_bytes() == sentinel,
                                       given.read_bytes() == nonce, output.read_bytes() == b"child:" + nonce, nonce.hex())}
        return {"status": "passed" if all(checks.values()) else "failed", "checks": checks,
                "parent_namespaces": parent, "child": evidence, "fixture_input_sha256": hashlib.sha256(nonce).hexdigest(),
                "tools": versions}


def main():
    try:
        if len(sys.argv) != 1:
            raise ValueError("This fixed probe accepts no arguments")
        result = run_probe()
    except subprocess.TimeoutExpired:
        result = {"status": "inconclusive", "reason": "A fixed probe operation timed out"}
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        result = {"status": "inconclusive", "reason": str(error)[:600]}
    result.update(probe="linux-worker-reference-v1", probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  kernel=platform.release(),
                  checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    print(json.dumps(result, indent=2, sort_keys=True))
    return {"passed": 0, "failed": 1, "inconclusive": 2}[result["status"]]


if __name__ == "__main__":
    sys.exit(main())
