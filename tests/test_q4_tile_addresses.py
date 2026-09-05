"""Check the prototype's address contract, not GPU numerical correctness."""
import unittest


class TileAddressTest(unittest.TestCase):
    def test_adjacent_half_pairs_stay_in_one_quant_block(self):
        for offset in (0, 32, 64, 128):
            for column in range((256-offset)//2):
                element=offset+2*column
                self.assertEqual(element//32,(element+1)//32)
                self.assertLess((element%32)%16,15)
                self.assertEqual((element%32)>=16,((element+1)%32)>=16)

    def test_head_and_row_offsets_do_not_use_fp16_strides(self):
        row_bytes=256//32*18
        self.assertEqual(row_bytes,144)
        for row in (0,1,1023,200703,262143):
            for element in range(0,256,2):
                block_address=row*row_bytes+(element//32)*18
                self.assertGreaterEqual(block_address,row*row_bytes)
                self.assertLess(block_address+17,(row+1)*row_bytes)
