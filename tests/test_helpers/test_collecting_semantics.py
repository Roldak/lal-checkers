"""
Output the JSON-formatted results of the "collecting semantics" analysis.
"""

from lalcheck.irs.basic.purpose import SyntheticVariable
from checkers.collecting_semantics import collect_semantics
import test_helper
import collecting_semantics_helpers

import json
import os


def format_analysis_results(results):
    return json.dumps({
        pred_name: {
            node.name: [
                {
                    'trace:': sorted([n.name for n in trace]),
                    'values': {
                        var.name: repr(value)
                        for var, value in values.iteritems()
                        if not SyntheticVariable.is_purpose_of(var)
                    }
                }
                for trace, values in sorted(
                    state.iteritems(), key=lambda x: x[0]
                )
            ]
            for node, state in sorted(
                analysis.semantics.iteritems(), key=lambda x: x[0].name
            )
        }
        for pred_name, analysis in results.iteritems()
    }, sort_keys=True, indent=2)


@test_helper.run
def run(args):
    results = collecting_semantics_helpers.do_analysis(
        collect_semantics,
        collecting_semantics_helpers.default_merge_predicates
    )

    if args.output_dir is not None:
        test_helper.ensure_dir(args.output_dir)

        cfg_file = os.path.join(args.output_dir, 'cfg.dot')
        sem_pattern = os.path.join(args.output_dir, 'sem_{}.dot')

    for pred_name, analysis in results.iteritems():
        if args.output_dir is not None:
            analysis.save_cfg_to_file(cfg_file)
            analysis.save_results_to_file(sem_pattern.format(pred_name))

    print(str(format_analysis_results(results)))