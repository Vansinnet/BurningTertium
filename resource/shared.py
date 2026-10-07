"""Verbatim copies: typed_module from resource/author_grid_shader.py; u32/dxbc from docs/analysis-flame-shader43-20260918-j1/decode.py."""
import re, struct

def u32(b, p):
    if not 0 <= p <= len(b)-4:
        raise ValueError('u32 bounds')
    return struct.unpack_from('<I', b, p)[0]

def dxbc(data):
    if len(data) < 32 or data[:4] != b'DXBC' or u32(data,20) != 1 or u32(data,24) != len(data):
        raise ValueError('DXBC header')
    n = u32(data,28)
    if not 1 <= n <= 16:
        raise ValueError('DXBC chunk count')
    p = 32+4*n
    chunks = []
    for i in range(n):
        off = u32(data,32+4*i)
        if off != p or off % 4:
            raise ValueError('DXBC chunk gap/overlap/alignment')
        size = u32(data,off+4)
        end = off+8+size
        if end > len(data):
            raise ValueError('DXBC chunk bounds')
        chunks.append(dict(tag=data[off:off+4].decode('ascii'),offset=off,size=size))
        if data[off:off+4] == b'DXIL':
            ver,words,magic,dxver,bc_off,bc_size=struct.unpack_from('<6I',data,off+8)
            bc=off+16+bc_off
            if words*4 != size or magic != 0x4c495844 or ver not in (0x60,0x10060) or dxver != 0x100:
                raise ValueError('DXIL program header/version')
            if bc_off != 16 or bc+bc_size > end or end-(bc+bc_size)>3 or data[bc:bc+4] != b'BC\xc0\xde':
                raise ValueError('DXIL bitcode bounds/magic')
            if any(data[bc+bc_size:end]):
                raise ValueError('DXIL bitcode padding')
            chunks[-1].update(program_version=ver,dxil_version=dxver,bitcode_offset=bc,bitcode_size=bc_size)
        p = end
    if p != len(data):
        raise ValueError('DXBC trailing data')
    return chunks


def typed_module(original, stat, entrypoint="ps_main"):
    if entrypoint not in ("ps_main", "vs_main"):
        raise ValueError("Unsupported shader entrypoint")
    body = re.search(r"^define void @" + entrypoint + r"\(\) \{\n.*?^\}", original, re.M | re.S)
    if not body:
        raise ValueError("Missing stock pixel function")
    module = stat[stat.index("target datalayout"):]
    if module.count("declare void @" + entrypoint + "()") != 1 or module.count("!2 = !{i32 0, i32 0}") != 1:
        raise ValueError("Unsupported STAT module framing")
    module = module.replace("!2 = !{i32 0, i32 0}", "!2 = !{i32 1, i32 7}")
    counter = re.search(r"^!dx.counters = !\{(!\d+)\}$", module, re.M)
    if not counter:
        raise ValueError("Missing STAT counter metadata")
    module = re.sub(r"^!dx.counters = .*\n", "", module, flags=re.M)
    module = re.sub(r"^" + re.escape(counter[1]) + r" = .*\n", "", module, flags=re.M)
    executable = body[0]
    refs = set(re.findall(r"!(\d+)", executable))
    if refs:
        next_id = 1 + max(map(int, re.findall(r"^!(\d+) =", module, re.M)))
        mapping = {key: str(next_id + i) for i, key in enumerate(sorted(refs, key=int))}
        extra_id = next_id + len(mapping)
        for key, newid in mapping.items():
            hint = re.search(r"^!" + key + r" = distinct !\{!" + key +
                             r', !"dx.controlflow.hints", i32 ([12])\}$', original, re.M)
            if not hint:
                original_definition = re.search(r"^!" + key + r" = .*", original, re.M)
                loop = re.fullmatch(r"!" + key + r" = distinct !\{!" + key + r", !(\d+)\}",
                                    original_definition[0]) if original_definition else None
                if not loop or not re.search(r'^!' + loop[1] + r' = !\{!"llvm.loop.unroll.disable"\}$',
                                              original, re.M):
                    raise ValueError("Unsupported control-flow metadata " + key + ": " +
                                     (original_definition[0] if original_definition else "missing"))
                module += f'\n!{newid} = distinct !{{!{newid}, !{extra_id}}}\n'
                module += f'!{extra_id} = !{{!"llvm.loop.unroll.disable"}}\n'
                extra_id += 1
            else:
                module += f'\n!{newid} = distinct !{{!{newid}, !"dx.controlflow.hints", i32 {hint[1]}}}\n'
        executable = re.sub(r"!(\d+)", lambda m: "!" + mapping[m[1]], executable)
    return module.replace("declare void @" + entrypoint + "()", executable)


