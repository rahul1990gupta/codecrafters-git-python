import os
import hashlib
import sys
import zlib
import hashlib
import struct
from pathlib import Path
from typing import Tuple, List, cast
import urllib.request 

def init_repo(parent: Path):
    (parent / ".git").mkdir(parents=True, exist_ok=True)
    (parent / ".git" / "objects").mkdir(parents=True, exist_ok=True)
    (parent / ".git" / "refs").mkdir(parents=True, exist_ok=True)
    (parent / ".git" / "refs" / "heads").mkdir(parents=True, exist_ok=True)
    (parent / ".git" / "HEAD").write_text("ref: refs/heads/main\n")

def read_object(parent: Path, sha: str) -> Tuple[str, bytes]:
    pre = sha[:2]
    post = sha[2:]
    p = parent / ".git" / "objects" / pre / post
    bs = p.read_bytes()
    head, content = zlib.decompress(bs).split(b"\0", maxsplit=1)
    ty, _ = head.split(b" ")
    return ty.decode(), content

def write_object(parent: Path, ty: str, content: bytes) -> str:

    content = ty.encode() + b" " + f"{len(content)}".encode() + b"\0" + content
    hash = hashlib.sha1(content, usedforsecurity=False).hexdigest()
    compressed_content = zlib.compress(content, level=zlib.Z_BEST_SPEED)
    pre = hash[:2]
    post = hash[2:]
    p = parent / ".git" / "objects" / pre / post
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(compressed_content)
    return hash

def render_tree(parent: Path, dir: Path, sha: str):
    dir.mkdir(parents=True, exist_ok=True)
    _, tree = read_object(parent, sha)
    while tree:
        mode, tree = tree.split(b" ", 1)
        name, tree = tree.split(b"\0", 1)
        sha = tree[:20].hex()
        tree = tree[20:]
        match mode:
            case b"40000":
                render_tree(parent, dir / name.decode(), sha)
            case b"100644":
                _, content = read_object(parent, sha)
                Path(dir / name.decode()).write_bytes(content)
            case _:
                raise RuntimeError("Not implemented")

def next_size_type(bs: bytes) -> Tuple[str, int, bytes]:
    ty = (bs[0] & 0b_0111_0000) >> 4
    match ty:
        case 1:
            ty = "commit"
        case 2:
            ty = "tree"
        case 3:
            ty = "blob"
        case 4:
            ty = "tag"
        case 6:
            ty = "ofs_delta"
        case 7:
            ty = "ref_delta"
        case _:
            ty = "unknown"
    size = bs[0] & 0b_0000_1111
    i = 1
    off = 4
    while bs[i - 1] & 0b_1000_0000:
        size += (bs[i] & 0b_0111_1111) << off
        off += 7
        i += 1
    return ty, size, bs[i:]

def next_size(bs: bytes) -> Tuple[int, bytes]:
    size = bs[0] & 0b_0111_1111
    i = 1
    off = 7
    while bs[i - 1] & 0b_1000_0000:
        size += (bs[i] & 0b_0111_1111) << off
        off += 7
        i += 1
    return size, bs[i:]

headers = {
    "Content-Type": "application/x-git-upload-pack-request",
    "Git-Protocol": "version=2"
}


def get_refs(url):
    # https://github.com/git/git/blob/master/Documentation/gitprotocol-v2.txt#L135-L146
    query = "/git-upload-pack"
    command_request = "0014command=ls-refs\n"  # PKT-LINE for `command=ls-refs`
    capability_list = "0000"  #  (delim-pkt)
    command_args = "0000"  #  (flush-pkt)
                    
    # Combining to form the full request body
    request_body = command_request + capability_list + command_args

    req = urllib.request.Request(
        url+query,
        data=request_body.encode(),
        headers=headers,
    )
    with urllib.request.urlopen(req) as f:
        content = cast(bytes, f.read())

    ref_lines = content.decode().split("\n")

    refs = {
        line.split(" ")[1]: line.split(" ")[0][4:] 
        for line in ref_lines[:-1]
    }
    return refs
 
def get_pack(url, shas):
    query = "/git-upload-pack"
    command_request = "0011command=fetch"
    delim = "0001" 
    args1 = "000fno-progress"
    args2 = "".join("0031want " + sha for sha in shas)
    done = "0008done" 
    flush_packet = "0000"
                    
    # Combining to form the full request body
    request_body = (command_request +
                    delim +
                    args1 + args2 + done +
                    flush_packet)

    req = urllib.request.Request(
        url+query,
        data=request_body.encode(),
        headers=headers,
    )
    with urllib.request.urlopen(req) as f:
        pack_bytes = cast(bytes, f.read())

    pack_lines = []
    while pack_bytes:
        line_len = int(pack_bytes[:4], 16)
        if line_len == 0:
            break
        pack_lines.append(pack_bytes[4:line_len])
        pack_bytes = pack_bytes[line_len:]
    pack_file = b"".join(l[1:] for l in pack_lines[1:])

    return pack_file

def apply_edits(content, base_content):
    target_content = b""
    while content:
        is_copy = content[0] & 0b_1000_0000
        if is_copy:
            data_ptr = 1
            offset = 0
            size = 0
            for i in range(0, 4):
                if content[0] & (1 << i):
                    offset |= content[data_ptr] << (i * 8)
                    data_ptr += 1
            for i in range(0, 3):
                if content[0] & (1 << (4 + i)):
                    size |= content[data_ptr] << (i * 8)
                    data_ptr += 1
            # do something with offset and size
            content = content[data_ptr:]
            target_content += base_content[offset : offset + size]
        else:
            size = content[0]
            append = content[1 : size + 1]
            content = content[size + 1 :]
            # do something with append
            target_content += append
    return target_content


def clone(url, dirname):
    parent = Path(dirname)
    init_repo(parent)
    # fetch refs
    refs = get_refs(url)
    # render refs
    for name, sha in refs.items():
        Path(parent / ".git" / name).write_text(sha + "\n")
    # fetch pack
    pack_file = get_pack(url, refs.values())

    # get objs
    pack_file = pack_file[8:]  # strip header and version
    n_objs, *_ = struct.unpack("!I", pack_file[:4])
    pack_file = pack_file[4:]
    for _ in range(n_objs):
        ty, _, pack_file = next_size_type(pack_file)

        match ty:
            case "commit" | "tree" | "blob" | "tag":
                dec = zlib.decompressobj()
                content = dec.decompress(pack_file)
                pack_file = dec.unused_data
                write_object(parent, ty, content)
            case "ref_delta":
                obj = pack_file[:20].hex()
                pack_file = pack_file[20:]
                dec = zlib.decompressobj()
                content = dec.decompress(pack_file)
                pack_file = dec.unused_data

                base_ty, base_content = read_object(parent, obj)
                # base and output sizes
                _, content = next_size(content)
                _, content = next_size(content)

                target_content = apply_edits(content, base_content)
                write_object(parent, base_ty, target_content)
            case _:
                raise RuntimeError("Not implemented")
    # render tree
    _, commit = read_object(parent, refs["HEAD"])
    tree_sha = commit[5 : 40 + 5].decode()
    render_tree(parent, parent, tree_sha)

def main():
    # You can use print statements as follows for debugging, they'll be visible when running tests.

    # Uncomment this block to pass the first stage
    #
    command = sys.argv[1]
    if command == "init":
        os.mkdir(".git")
        os.mkdir(".git/objects")
        os.mkdir(".git/refs")
        with open(".git/HEAD", "w") as f:
            f.write("ref: refs/heads/main\n")
        print("Initialized git directory")
    elif command == "cat-file":
        sha = sys.argv[3]
        content = read_object_v0(sha)
        print(content.decode(), end="")
    elif command == "hash-object":
        fname = sys.argv[3]
        sha = write_object_v0(fname)
        print(sha.hexdigest())

    elif command == "ls-tree":
        sha = sys.argv[3]
        content = read_object_v0(sha)
        
        buff = content
        while b"\x00" in buff:
            nb_index = buff.find(b"\x00")
            oname = buff[:nb_index].split(b"\x20")[1]
            print(oname.decode())
            
            buff = buff[nb_index + 20:]
    elif command == "write-tree":
        sha = write_directory(os.getcwd())
        print(sha.hexdigest())
    elif command == "commit-tree":
        tree_sha = sys.argv[2]
        parent = None
        if sys.argv[3] == "-p":
            parent = sys.argv[4]
            cmsg = sys.argv[6]
        elif sys.argv[3] == "-m":
            cmsg = sys.argv[4]
        sha = commit_tree(tree_sha, cmsg, parent)
        print(sha.hexdigest())
    elif command == "clone":
        remote_git = sys.argv[2]
        dirname = sys.argv[3]
        os.makedirs(dirname, exist_ok=True)
        clone(remote_git, dirname)
    else:
        raise RuntimeError(f"Unknown command #{command}")


"""
tree {tree_sha}
{parents}
author {author_name} <{author_email}> {author_date_seconds} {author_date_timezone}
committer {committer_name} <{committer_email}> {committer_date_seconds} {committer_date_timezone}

{commit message}
"""
    
def commit_tree(tree_sha, cmsg, parent):
    astr = b"author Scott Chacon <schacon@gmail.com> 1243040974 -0700"
    cstr = b"committer Scott Chacon <schacon@gmail.com> 1243040974 -0700"

    content = b"tree " + tree_sha.encode() + b"\n"
    if parent: 
        content+=b"parent " + parent.encode() + b"\n"

    content += astr + b"\n" + cstr + b"\n\n" + cmsg.encode() + b"\n"
    # content will be bytes

    sha = serialize('commit', content)
    return sha

def write_directory(dir_name):
    
    buff = b""
    entries = list(os.scandir(dir_name))
    entries.sort(key= lambda x: x.name)
    for entry in entries:
        if entry.name == ".git":
            continue

        if entry.is_file():
            mode = "100644"
        elif entry.is_dir():
            mode = "40000"
        else: 
            ValueError("mode not supported")
        
        name = entry.name
        if entry.is_file():
            sha  = write_object_v0(f"{dir_name}/{entry.name}")
        elif entry.is_dir():
            sha = write_directory(f"{dir_name}/{entry.name}")
        
        sha_20 = int.to_bytes(int(sha.hexdigest(), base=16), length=20, byteorder="big")
        
        buff += f"{mode} {name}".encode() + b"\x00" + sha_20
        len(buff)

    sha = serialize("tree", buff)
    return sha


def serialize(ctype, content):
    size = len(content)
    header = f"{ctype} {size}"
    obj_content = header.encode() + b"\x00" + content 
    
    sha_raw = hashlib.sha1(obj_content)
    sha = sha_raw.hexdigest()
    
    os.makedirs(f".git/objects/{sha[:2]}", exist_ok=True)
    
    with open(f".git/objects/{sha[:2]}/{sha[2:]}", "wb") as f:
        f.write(zlib.compress(obj_content))
    
    return sha_raw


def write_object_v0(fname):
    with open(fname, 'rb') as f:
        content = f.read()
    sha = serialize("blob", content)
    return sha


def read_object_v0(sha):
    path = f".git/objects/{sha[:2]}/{sha[2:]}"
    with open(path, 'rb') as f:
        raw = zlib.decompress(f.read())
    fc_index = raw.find(b"\x00")
    
    return raw[fc_index+1:]


if __name__ == "__main__":
    main()
