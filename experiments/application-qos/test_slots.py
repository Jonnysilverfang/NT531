"""Inference guards; all inputs are synthetic and must never enter measured results."""
import importlib.util
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('analysis',HERE/'analyze_slots.py');analysis=importlib.util.module_from_spec(spec);spec.loader.exec_module(analysis)


class StatisticsTests(unittest.TestCase):
    def test_complete_study_required_and_margin_ties_not_successes(self):
        p=dict(blocks=16,improvement_margin_fraction=.1,primary_critical_successes=12,seed=123)
        rows=[dict(mode=m,slots=s,rate_rps=r,deadline_success_count=100,scheduled=100) for m in ['tgw','peering'] for s in [8,16] for r in [600,800]]
        blocks=[dict(improvement='.10',rows=rows)]*16
        with self.assertRaises(ValueError):analysis.inference(blocks[:15],p)
        result=analysis.inference(blocks,p)
        self.assertEqual(result['above_margin_blocks'],0)
        self.assertFalse(result['majority_improvement_supported'])
        self.assertEqual(result['one_sided_exact_p'],1)
        self.assertEqual(result['descriptive_whole_block_bootstrap_95_ci']['slot_improvement_at_800']['lower'],10)

    def test_exact_critical_boundary(self):
        self.assertGreater(analysis.rtt.tail(16,11),.05)
        self.assertLess(analysis.rtt.tail(16,12),.05)
        self.assertGreater(analysis.rtt.lower_probability(16,12),.5)
        self.assertLess(analysis.rtt.lower_probability(16,11),.5)


if __name__=='__main__':unittest.main()
