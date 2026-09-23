import unittest
from types import SimpleNamespace

from pymupdf._table_spans import SpanCell
from pymupdf4llm._table_pipeline.fragment_consolidation import snapshot, join_evidence, revert_eligible, concat_placements


def fragment(start, end, y, depth=0, xshift=0):
    rows = [[SpanCell((xshift, y+i*10, 20+xshift, y+i*10+10), f'({n})', 1, 1),
             SpanCell((20+xshift, y+i*10, 100+xshift, y+i*10+10), f'value {n}', 1, 1)]
            for i, n in enumerate(range(start, end+1))]
    return SimpleNamespace(placements=rows, bbox=[xshift,y,100+xshift,y+10*len(rows)], header_rows=depth)


class FragmentTest(unittest.TestCase):
    def test_positive_and_no_input_mutation(self):
        a,b = fragment(0,15,0,1), fragment(16,18,180)
        a.placements[0][1].text='Description'
        self.assertEqual(join_evidence(snapshot(a),snapshot(b)), 'row-continuity')
        copied = concat_placements([a,b])
        self.assertEqual(len(copied),19)
        copied[0][0].tag = 'th'
        self.assertEqual(a.placements[0][0].tag,'td')

    def test_header_or_noncontinuity_is_not_join(self):
        a,b = fragment(0,15,0,1), fragment(16,18,180,1)
        self.assertIsNone(join_evidence(snapshot(a),snapshot(b)))
        b.header_rows=0
        b.placements[0][0].text='ISI\n1 BEST\n2 GOOD'
        self.assertIsNone(join_evidence(snapshot(a),snapshot(b)))
        b.placements[0][0].text='(17)'
        self.assertIsNone(join_evidence(snapshot(a),snapshot(b)))

    def test_geometry_parent_overlap_and_shift(self):
        a=fragment(0,15,0,1)
        self.assertIsNone(join_evidence(snapshot(a),snapshot(fragment(16,18,100))))
        self.assertIsNone(join_evidence(snapshot(a),snapshot(fragment(16,18,180,xshift=3))))

    def test_spans_remain_intact(self):
        a=fragment(0,1,0)
        a.placements=[[SpanCell((0,0,100,20),'shared',2,2,'th')],[]]
        joined=concat_placements([a,fragment(2,2,25)])
        self.assertEqual((joined[0][0].colspan,joined[0][0].rowspan),(2,2))
        self.assertEqual(joined[0][0].bbox,(0,0,100,20))

    def test_revert_veto_and_original_pair_links(self):
        ts=[snapshot(fragment(n,n,y)) for n,y in [(1,0),(2,20),(3,40)]]
        # Repeated word 'value' is a veto even when row numbers differ.
        self.assertFalse(revert_eligible(ts))
        for i,t in enumerate(ts):t['first']={f'unique{i}'}
        self.assertTrue(revert_eligible(ts))
        self.assertFalse(revert_eligible(ts[:2]))


if __name__ == '__main__':
    unittest.main()
