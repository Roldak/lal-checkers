#! /usr/bin/env python

"""
This script will detect syntactically identical expressions which are chained
together in a chain of logical operators in the input Ada sources.
"""

from __future__ import (absolute_import, division, print_function)

import libadalang as lal
from tools.scheduler import Task, Requirement
from checkers.support.components import AnalysisUnit
from lalcheck.utils import dataclass
from checkers.support.checker import SyntacticChecker


class Results(SyntacticChecker.Results):
    def __init__(self, diags):
        super(Results, self).__init__(diags)

    @classmethod
    def diag_message(cls, diag):
        fst_line = diag[0].sloc_range.start.line
        return 'duplicate test with line {}'.format(fst_line)

    @classmethod
    def diag_position(cls, diag):
        return diag[1]


def find_same_tests(unit):
    def list_tests(ifnode):
        """
        List all the tests of `ifnode`.

        :type ifnode: lal.IfStmt|lal.IfExpr
        """
        return [ifnode.f_cond_expr] + [
            f.f_cond_expr for f in ifnode.f_alternatives
        ]

    def tokens_text(node):
        return tuple((t.kind, t.text) for t in node.tokens)

    def has_same_tests(expr):
        """
        For an if-statement or an if-expression, checks whether any
        combination of its tests are syntactically equivalent. If duplicate
        operands are found, return them.

        :rtype: lal.Expr|None
        """
        tests = {}
        all_tests = list_tests(expr)
        if len(all_tests) > 1:
            for test in all_tests:
                tokens = tokens_text(test)
                if tokens in tests:
                    return (tests[tokens], test)
                tests[tokens] = test

    diags = []
    for ifnode in unit.root.findall((lal.IfStmt, lal.IfExpr)):
        res = has_same_tests(ifnode)
        if res is not None:
            diags.append(res)

    return Results(diags)


@Requirement.as_requirement
def SameTests(project_config, files):
    return [SameTestFinder(
        project_config, files
    )]


@dataclass
class SameTestFinder(Task):
    def __init__(self, project_config, files):
        self.project_config = project_config
        self.files = files

    def requires(self):
        return {
            'unit_{}'.format(i): AnalysisUnit(self.project_config, f)
            for i, f in enumerate(self.files)
        }

    def provides(self):
        return {
            'res': SameTests(
                self.project_config,
                self.files
            )
        }

    def run(self, **kwargs):
        units = kwargs.values()
        return {
            'res': [find_same_tests(unit) for unit in units]
        }


class SameTestChecker(SyntacticChecker):
    @classmethod
    def name(cls):
        return "same_test_checker"

    @classmethod
    def description(cls):
        return ("Finds alternatives in if statements/expressions that contain "
                "multiple times syntactically identical conditions.")

    @classmethod
    def create_requirement(cls, *args, **kwargs):
        return cls.requirement_creator(SameTests)(*args, **kwargs)


checker = SameTestChecker


if __name__ == "__main__":
    print("Please run this checker through the run-checkers.py script")
