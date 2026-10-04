import unittest, importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('updater',Path(__file__).resolve().parents[1]/'fpl_dashboard_updater.py')
u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)
class UpdaterTests(unittest.TestCase):
    def test_tied_boundary(self):
        rows,pays=u.tied_slot_payments([{'points':200},{'points':220},{'points':220}],2,300,'points')
        self.assertEqual(len(rows),3);self.assertAlmostEqual(sum(pays),300);self.assertEqual(pays[1],pays[2])
    def test_three_tied(self):
        rows,pays=u.tied_slot_payments([{'points':10}]*3,2,300,'points')
        self.assertEqual(pays,[100,100,100])
    def test_history_incomplete_rejected(self):
        with self.assertRaises(ValueError):u.validate_history([{'manager_id':1}],[],5)
    def test_regressed_gw_preserves_snapshot(self):
        with self.assertRaises(ValueError):u.preserve_history_guard([],4)
    def test_double_transfer_hit_avoided(self):
        from unittest.mock import patch
        manager={'manager_id':1,'manager':'A','team':'T','manager_name':'A','team_name':'T'}
        payload={'current':[{'event':1,'points':72,'event_transfers_cost':4,'total_points':68}]}
        with patch.object(u,'api_get',return_value=payload): rows=u.get_histories([manager],1)
        self.assertEqual(rows[0]['net_gw_points'],68)
        self.assertEqual(rows[0]['transfer_cost'],4)
if __name__=='__main__':unittest.main()
