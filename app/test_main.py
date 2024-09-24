import unittest 
from app.main import (
    get_refs,
    get_pack,
    next_size_type,
    next_size,
    apply_edits
)

class TestGgzor(unittest.TestCase):
    def setUp(self):
        self.url = "https://github.com/codecrafters-io/git-sample-3"

        self.head_sha = "23f0bc3b5c7c3108e41c448f01a3db31e7064bbb"
        self.pf_length = 20983 
    def tearDown(self):
        pass

    def test_get_refs(self):
        refs = get_refs(self.url)
        self.assertEqual(len(refs), 2)
        self.assertEqual(refs["HEAD"], self.head_sha)


    def test_get_pack(self):
        pack_file = get_pack(self.url, [self.head_sha])
        self.assertEqual(len(pack_file), self.pf_length)

    
    def test_next_size_type(self):
        pack_file = get_pack(self.url, [self.head_sha])
        ty, _, pack_file = next_size_type(pack_file[12:])
        self.assertEqual(ty, "commit")
        self.assertEqual(len(pack_file), 20969)

        buff = 0b_0001_1111.to_bytes(1, byteorder="big")
        ty, size, buff = next_size_type(buff)
        self.assertEqual(ty, "commit")
        self.assertEqual(size, 15)
        self.assertEqual(buff, b"")

        buff = (0b_1001_1111.to_bytes(1, byteorder="big") +
               0b_0000_0001.to_bytes(1, byteorder="big"))
        ty, size, buff = next_size_type(buff)
        self.assertEqual(ty, "commit")
        self.assertEqual(size, 31)
        self.assertEqual(buff, b"")

    def test_next_size(self):
        
        buff = 0b_0001_1111.to_bytes(1, byteorder="big")
        size, buff = next_size(buff)
        self.assertEqual(size, 31)
        self.assertEqual(buff, b"")
 
 
        buff = (0b_1001_1111.to_bytes(1, byteorder="big") +
               0b_0000_0001.to_bytes(1, byteorder="big"))
        size, buff = next_size(buff)
        self.assertEqual(size, 0b_1001_1111)
        self.assertEqual(buff, b"")
    
    def test_apply_edits(self):
        with open("app/content.bin", "rb") as f:
            content = f.read()
        with open("app/base.bin", "rb") as f:
            base_content = f.read()
        
        target = apply_edits(content, base_content)
        with open("app/target.bin", "rb") as f:
            target_correct = f.read()
        self.assertEqual(target, target_correct)
