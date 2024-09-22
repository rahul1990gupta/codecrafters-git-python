import sys
import os
import zlib

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
        with open(fname, 'rb') as f:
            content = f.read()
        size = len(content)
        header = f"blob {size}"
        obj_content = header.encode() + b"\x00" + content 
        
        import hashlib
        sha = hashlib.sha1(obj_content).hexdigest()
        print(sha)
        os.mkdir(f".git/objects/{sha[:2]}")
        
        with open(f".git/objects/{sha[:2]}/{sha[2:]}", "wb") as f:
            f.write(zlib.compress(obj_content))
    elif command == "ls-tree":
        sha = sys.argv[3]
        content = read_object(sha)
        

        buff = content
        
        while b"\x00" in buff:
            nb_index = buff.find(b"\x00")
            oname = buff[:nb_index].split(b"\x20")[1]
            print(oname.decode())
            
            offset = nb_index + 20 
            buff = buff[nb_index + 20:]
            
    else:
        raise RuntimeError(f"Unknown command #{command}")


def read_object(sha):
    path = f".git/objects/{sha[:2]}/{sha[2:]}"
    with open(path, 'rb') as f:
        raw = zlib.decompress(f.read())
    fc_index = raw.find(b"\x00")
    
    return raw[fc_index+1:]


if __name__ == "__main__":
    main()
