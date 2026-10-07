"""Tiny expression graph that evaluates with numpy (preview) and emits DXIL LLVM IR (shader)."""
import struct
import numpy as np

F32 = np.float32


def hexf(x):
    return "0x%016X" % struct.unpack("<Q", struct.pack("<d", float(F32(x))))[0]


class N:
    def __init__(self, op, *args, value=None):
        self.op, self.args, self.value = op, args, value

    def __add__(s, o): return N("fadd", s, lift(o))
    def __radd__(s, o): return N("fadd", lift(o), s)
    def __sub__(s, o): return N("fsub", s, lift(o))
    def __rsub__(s, o): return N("fsub", lift(o), s)
    def __mul__(s, o): return N("fmul", s, lift(o))
    def __rmul__(s, o): return N("fmul", lift(o), s)
    def __truediv__(s, o): return N("fdiv", s, lift(o))


def lift(x):
    return x if isinstance(x, N) else N("const", value=float(F32(x)))


def inp(name): return N("input", value=name)
def frc(a): return N("u22", a)
def sat(a): return N("u7", a)
def fabs(a): return N("u6", a)
def sqrt(a): return N("u24", a)
def exp2(a): return N("u21", a)
def log2(a): return N("u23", a)
def ddy(a): return N("u84", a)
def fmax(a, b): return N("b35", lift(a), lift(b))
def fmin(a, b): return N("b36", lift(a), lift(b))
def select_le(a, b, x, y): return N("selle", lift(a), lift(b), lift(x), lift(y))
def mix(a, b, t): return a + (b - a) * t


def evaluate(node, env, cache=None):
    cache = {} if cache is None else cache
    k = id(node)
    if k in cache:
        return cache[k]
    op = node.op
    if op == "const":
        r = F32(node.value)
    elif op == "input":
        r = env[node.value]
    else:
        a = [evaluate(x, env, cache) for x in node.args]
        with np.errstate(all="ignore"):
            if op == "fadd": r = a[0] + a[1]
            elif op == "fsub": r = a[0] - a[1]
            elif op == "fmul": r = a[0] * a[1]
            elif op == "fdiv": r = a[0] / a[1]
            elif op == "u22": r = a[0] - np.floor(a[0])
            elif op == "u7": r = np.clip(a[0], 0, 1)
            elif op == "u6": r = np.abs(a[0])
            elif op == "u24": r = np.sqrt(a[0])
            elif op == "u21": r = np.exp2(a[0])
            elif op == "u23": r = np.log2(a[0])
            elif op == "u84": r = env["__ddy__"](a[0])
            elif op == "b35": r = np.maximum(a[0], a[1])
            elif op == "b36": r = np.minimum(a[0], a[1])
            elif op == "selle": r = np.where(a[0] <= a[1], a[2], a[3])
            else: raise ValueError(op)
        r = np.asarray(r, dtype=F32)
    cache[k] = r
    return r


def emit(outputs, inputs, prefix="bt"):
    """Return (ir_lines, {name: ssa}) for outputs dict name->node; inputs maps input name->ssa."""
    lines, names, counter = [], {}, [0]

    def ref(node):
        k = id(node)
        if k in names:
            return names[k]
        if node.op == "const":
            return hexf(node.value)
        if node.op == "input":
            return inputs[node.value]
        a = [ref(x) for x in node.args]
        counter[0] += 1
        name = f"%{prefix}.{counter[0]}"
        op = node.op
        if op in ("fadd", "fsub", "fmul", "fdiv"):
            lines.append(f"  {name} = {op} float {a[0]}, {a[1]}")
        elif op[0] == "u":
            lines.append(f"  {name} = call float @dx.op.unary.f32(i32 {op[1:]}, float {a[0]})")
        elif op[0] == "b":
            lines.append(f"  {name} = call float @dx.op.binary.f32(i32 {op[1:]}, float {a[0]}, float {a[1]})")
        elif op == "selle":
            lines.append(f"  {name}.c = fcmp ole float {a[0]}, {a[1]}")
            lines.append(f"  {name} = select i1 {name}.c, float {a[2]}, float {a[3]}")
        else:
            raise ValueError(op)
        names[k] = name
        return name

    out = {key: ref(node) for key, node in outputs.items()}
    return lines, out
