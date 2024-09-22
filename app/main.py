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
        path = f".git/objects/{sha[:2]}/{sha[2:]}"
        
        """
        An object starts with a header that specifies its type: blob, commit, tag or tree. This header is followed by an ASCII space (0x20), then the size of the object in bytes as an ASCII number, then null (0x00) (the null byte), then the contents of the objec
        """
        
        with open(path, 'rb') as f:
            raw = zlib.decompress(f.read())
        fc_index = raw.find(b"\x00")
        print(raw[fc_index+1:].decode(), end="")
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
        

    else:
        raise RuntimeError(f"Unknown command #{command}")


if __name__ == "__main__":
    main()
