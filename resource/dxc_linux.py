"""Linux port of docs/analysis-flame-huecycle-20260918-n1/dxc_api.py (same COM slots, cdecl ABI).

Toolchain: conda-forge linux-64 directx-shader-compiler-1.9.2602.24-hf2136f4_0.conda
(SHA-256 6dec45ac2bfa8566b642945e7c73296822ef85122672299770d1dfc928bcbf3b) plus
spirv-tools-2026.3-hb700be7_0.conda (SHA-256 863058fea246a08b348e010462dd5637cac9a15964012ae6c174f0f89978705f).
Its -dumpbin of 1d465925213c.dxbc is identical to the pinned Windows v1.9.2607 dump, and the
no-op rebuild of 903327e46fdd reproduces the Windows noop SHA-256 1fad4201... byte for byte.
"""
import ctypes as C, hashlib, uuid, subprocess
from pathlib import Path
import os
TOOL = Path(os.environ.get("BT_DXC_LINUX", "/tmp/claude-0/dxc/x"))
P=C.c_void_p; H=C.c_int32; U=C.c_uint32
PINNED = {"conda_pkg_sha256":"6dec45ac2bfa8566b642945e7c73296822ef85122672299770d1dfc928bcbf3b"}
def check(hr):
    if hr<0: raise RuntimeError(f"DXC HRESULT 0x{hr&0xffffffff:08x}")
def method(obj,slot,result,*types):
    table=C.cast(obj,C.POINTER(C.POINTER(P))).contents
    return C.CFUNCTYPE(result,P,*types)(table[slot])
def release(obj):
    if obj: method(obj,2,U)(obj)
def blob_bytes(blob):
    if not blob: return b""
    n=method(blob,4,C.c_size_t)(blob)
    if n>2_000_000: raise ValueError("bound")
    return C.string_at(method(blob,3,P)(blob),n)
class Dxc:
    def __init__(self):
        C.CDLL(str(TOOL/"lib/libSPIRV-Tools.so"),mode=C.RTLD_GLOBAL)
        C.CDLL(str(TOOL/"lib/libSPIRV-Tools-opt.so"),mode=C.RTLD_GLOBAL)
        self.lib=C.CDLL(str(TOOL/"lib/libdxcompiler.so"))
        self.sha=hashlib.sha256((TOOL/"lib/libdxcompiler.so").read_bytes()).hexdigest()
    def create(self,clsid,iid):
        fn=self.lib.DxcCreateInstance; fn.argtypes=[P,P,C.POINTER(P)]; fn.restype=H
        c=C.create_string_buffer(uuid.UUID(clsid).bytes_le); i=C.create_string_buffer(uuid.UUID(iid).bytes_le)
        obj=P(); check(fn(c,i,C.byref(obj)))
        if not obj: raise RuntimeError("null")
        return obj
    def blob(self,data):
        if not 0<len(data)<=900_000: raise ValueError("bound")
        utils=self.create("6245d6af-66e0-48fd-80b4-4d271796748c","4605c4cb-2019-492a-ada4-65f20bb7d67f")
        b=P()
        try:
            self._mem=C.create_string_buffer(data)
            check(method(utils,6,H,P,U,U,C.POINTER(P))(utils,self._mem,len(data),0,C.byref(b)))
            return b
        finally: release(utils)
    def operation(self,data,assemble):
        blob=self.blob(data); obj,res,out,err=P(),P(),P(),P()
        try:
            if assemble:
                obj=self.create("d728db68-f903-4f80-94cd-dccf76ec7151","091f7a26-1c1f-4948-904b-e6e3a8a771d5")
                check(method(obj,3,H,P,C.POINTER(P))(obj,blob,C.byref(res)))
            else:
                obj=self.create("8ca3e215-f728-4cf3-8cdd-88af917587a1","a6e82bd2-1fd7-4826-9811-2857e797f49a")
                check(method(obj,3,H,P,U,C.POINTER(P))(obj,blob,0,C.byref(res)))
            st=H(); check(method(res,3,H,C.POINTER(H))(res,C.byref(st)))
            check(method(res,5,H,C.POINTER(P))(res,C.byref(err)))
            msg=blob_bytes(err).decode("utf-8","replace").rstrip("\0")
            if st.value<0: raise RuntimeError(f"DXC op 0x{st.value&0xffffffff:08x}: {msg}")
            check(method(res,4,H,C.POINTER(P))(res,C.byref(out)))
            return blob_bytes(out),msg
        finally:
            for x in (err,out,res,obj,blob): release(x)
def dump(path):
    r=subprocess.run([str(TOOL/"bin/dxc-3.7"),"-dumpbin",str(path)],capture_output=True,timeout=30,
                     env={"LD_LIBRARY_PATH":str(TOOL/"lib")})
    if r.returncode or r.stderr or not 0<len(r.stdout)<=900_000: raise ValueError("dump failed "+r.stderr.decode())
    return r.stdout.decode()
