# -*- coding: utf-8 -*-
from lmfdb.tests import LmfdbTest


class GalGpTest(LmfdbTest):

    # All tests should pass
    #
    def test_search_deg(self):
        L = self.tc.get('/GaloisGroup/?start=0&parity=0&cyc=0&solv=0&prim=0&n=7&t=&count=50')
        assert '7 matches' in L.get_data(as_text=True)

    def test_search_t_solv_prim(self):
        L = self.tc.get('/GaloisGroup/?start=0&parity=-1&cyc=0&solv=1&prim=-1&n=&t=18&count=50')
        assert '14T18' in L.get_data(as_text=True)
        assert '294' in L.get_data(as_text=True) # order of 21T18

    def test_display_bigpage(self):
        L = self.tc.get('/GaloisGroup/22T29')
        assert '22528' in L.get_data(as_text=True) # order of 22T29

    def test_search_range(self):
        L = self.tc.get('GaloisGroup/?start=0&parity=0&cyc=0&solv=0&prim=0&n=8-11&t=3-5&count=50')
        assert '8T3' in L.get_data(as_text=True)
        assert '660' in L.get_data(as_text=True) # order of 11T5

    def test_search_order(self):
        L = self.tc.get('GaloisGroup/?order=18')
        assert '9T5' in L.get_data(as_text=True)
        assert '9 matches' in L.get_data(as_text=True)

    def test_search_gapid(self):
        L = self.tc.get('GaloisGroup/?gapid=[60,5]')
        assert '20T15' in L.get_data(as_text=True)
        assert '15T5' in L.get_data(as_text=True)

    def test_bad_jump(self):
        L = self.tc.get('/GaloisGroup/notagroup', follow_redirects=True)
        assert 'not a valid label for a Galois group' in L.get_data(as_text=True)

    def test_bad_out_of_range(self):
        L = self.tc.get('/GaloisGroup/12345T678', follow_redirects=True)
        assert 'was not found in the database' in L.get_data(as_text=True)

    def test_underlying_data(self):
        data = self.tc.get('/GaloisGroup/8T44').get_data(as_text=True)
        assert "Underlying data" in data and "data/8T44" in data

