import sys
import os
import zlib
import hashlib

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
        content = read_object(sha)
        print(content.decode(), end="")
    elif command == "hash-object":
        fname = sys.argv[3]
        sha = write_object(fname)
        print(sha.hexdigest())

    elif command == "ls-tree":
        sha = sys.argv[3]
        content = read_object(sha)
        
        buff = content
        while b"\x00" in buff:
            nb_index = buff.find(b"\x00")
            oname = buff[:nb_index].split(b"\x20")[1]
            print(oname.decode())
            
            buff = buff[nb_index + 20:]
    elif command == "write-tree":
        sha = write_directory(os.getcwd())
        print(sha.hexdigest())
    else:
        raise RuntimeError(f"Unknown command #{command}")


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
            sha  = write_object(f"{dir_name}/{entry.name}")
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


def write_object(fname):
    with open(fname, 'rb') as f:
        content = f.read()
    sha = serialize("blob", content)
    return sha


def read_object(sha):
    path = f".git/objects/{sha[:2]}/{sha[2:]}"
    with open(path, 'rb') as f:
        raw = zlib.decompress(f.read())
    fc_index = raw.find(b"\x00")
    
    return raw[fc_index+1:]


if __name__ == "__main__":
    main()
