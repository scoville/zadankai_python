#!/usr/local/bin/python3

from ortools.constraint_solver import pywrapcp


class ZadankaiCSP:
    __DEFAULT_NEXT_VAR = pywrapcp.Solver.CHOOSE_RANDOM
    __DEFAULT_NEXT_VALUE = pywrapcp.Solver.ASSIGN_MAX_VALUE

    def __init__(self, companies, students, terms):
        self.csp = pywrapcp.Solver("zadankai")

        self.__process_data(companies, students, terms)

        self.__make_variables()
        self.__make_expressions()
        self.__make_constraints()

    def __process_data(self, companies, students, terms):
        self.__process_cardinality(companies['count'], students['count'], terms['count'])
        self.__process_groups(companies['groups'])
        self.__process_ratings(companies['ratings'], students['ratings'])

    def __process_cardinality(self, num_companies, num_students, num_terms):
        self.num_companies = num_companies
        self.num_students = num_students
        self.num_terms = num_terms

        self.rg_companies = range(num_companies)
        self.rg_students = range(num_students)
        self.rg_terms = range(num_terms)

    def __process_groups(self, groups):
        self.num_groups_per_company = groups
        num_groups = sum(groups)
        avg_group_size = self.num_students / num_groups
        self.target_assignments = [
            round(num_groups * avg_group_size)
            for num_groups in groups
        ]

    def __process_ratings(self, company_ratings, student_ratings):
        self.combined_ratings = {}
        for company in self.rg_companies:
            for student in self.rg_students:
                c_rating = int((company_ratings['values'][company][student] / 5) * 100)
                s_rating = int((student_ratings['values'][student][company] / 5) * 100)
                combined = company_ratings['weight'] * c_rating + student_ratings['weight'] * s_rating
                combined /= company_ratings['weight'] + student_ratings['weight']
                self.combined_ratings[(company, student)] = int(combined)

    def __make_variables(self):
        self.assignments = {}
        self.assignments_flat = []
        for company in self.rg_companies:
            for term in self.rg_terms:
                for student in self.rg_students:
                    assignment = self.csp.BoolVar(f"assignment(c{company}, t{term}, s{student})")
                    self.assignments[(company, term, student)] = assignment
                    self.assignments_flat.append(assignment)

    def __make_expressions(self):
        self.headcounts = {}
        self.headcounts_flat = []
        for company in self.rg_companies:
            for term in self.rg_terms:
                headcount = self.csp.Sum([
                    self.assignments[(company, term, s)]
                    for s in self.rg_students
                ])
                self.headcounts[(company, term)] = headcount
                self.headcounts_flat.append(headcount)

        self.deltas = {}
        self.deltas_flat = []
        for company in self.rg_companies:
            for term in self.rg_terms:
                delta = self.headcounts[(company, term)] - int(self.target_assignments[company])
                self.deltas[(company, term)] = delta
                self.deltas_flat.append(delta)

        self.abs_deltas = {}
        self.abs_deltas_flat = []
        for company in self.rg_companies:
            for term in self.rg_terms:
                abs_delta = abs(self.deltas[(company, term)])
                self.abs_deltas[(company, term)] = abs_delta
                self.abs_deltas_flat.append(abs_delta)

        self.ttl_delta = self.csp.Sum([
            self.abs_deltas[c, t]
            for c in self.rg_companies
            for t in self.rg_terms
        ])
        self.avg_delta = self.ttl_delta // (self.num_companies * self.num_terms)
        self.var_delta = self.csp.Sum([
            self.deltas[(c, t)].Square()
            for c in self.rg_companies
            for t in self.rg_terms
        ]) // (self.num_companies * self.num_terms)

        self.assigned_dissatisfaction = {}
        for c in self.rg_companies:
            for t in self.rg_terms:
                for s in self.rg_students:
                    dissatisfaction = self.assignments[(c, t, s)] * (100 - self.combined_ratings[(c, s)])
                    self.assigned_dissatisfaction[(c, t, s)] = dissatisfaction

        self.ttl_dissatisfaction = self.csp.Sum([
            self.assigned_dissatisfaction[(c, t, s)]
            for c in self.rg_companies
            for t in self.rg_terms
            for s in self.rg_students
        ])
        self.avg_dissatisfaction = self.ttl_dissatisfaction // (self.num_companies * self.num_terms * self.num_students)
        self.var_dissatisfaction = self.csp.Sum([
            (self.assigned_dissatisfaction[(c, t, s)] - self.avg_dissatisfaction).Square()
            for c in self.rg_companies
            for t in self.rg_terms
            for s in self.rg_students
        ]) // (self.num_companies * self.num_terms * self.num_students)

    def __make_constraints(self):
        self.__make_business_constraints()
        self.__make_symmetry_breaking_constraints()

    def __make_business_constraints(self):
        # Each Term, a Student can only be assigned to one Company
        for term in self.rg_terms:
            for student in self.rg_students:
                self.csp.Add(self.csp.Sum([
                    self.assignments[(c, term, student)]
                    for c in self.rg_companies
                ]) == 1)

        # Each Company sees each Student at most once
        for company in self.rg_companies:
            for student in self.rg_students:
                self.csp.Add(self.csp.Sum([
                    self.assignments[(company, t, student)]
                    for t in self.rg_terms
                ]) <= 1)

        # Each Company has at least one Student per Term
        for company in self.rg_companies:
            for term in self.rg_terms:
                self.csp.Add(self.headcounts[(company, term)] >= min(
                    min(self.target_assignments),
                    self.num_groups_per_company[company]
                ))

    def __make_symmetry_breaking_constraints(self):
        # TODO
        pass

    def __make_objective_function(self, weights):
        delta_objective =\
            weights['delta']['ttl'] * self.ttl_delta\
            + weights['delta']['var'] * self.var_delta
        dissatisfaction_objective =\
            weights['satisfaction']['ttl'] * self.ttl_dissatisfaction\
            + weights['satisfaction']['var'] * self.var_dissatisfaction

        objective_var =\
            (weights['delta']['obj'] * delta_objective)\
            + (weights['satisfaction']['obj'] * dissatisfaction_objective)

        return self.csp.Minimize(objective_var, 1)

    def __make_solution_collector(self):
        collector = self.csp.LastSolutionCollector()

        collector.Add(self.assignments_flat)

        collector.Add(self.headcounts_flat)
        collector.Add(self.deltas_flat)
        collector.Add(self.abs_deltas_flat)

        collector.Add(self.ttl_delta)
        collector.Add(self.avg_delta)
        collector.Add(self.var_delta)

        collector.Add(self.ttl_dissatisfaction)
        collector.Add(self.avg_dissatisfaction)
        collector.Add(self.var_dissatisfaction)

        return collector

    def solve(self, weights, next_var=__DEFAULT_NEXT_VAR, next_value=__DEFAULT_NEXT_VALUE, max_timeout=60):
        solution_collector = self.__make_solution_collector()
        solved = self.csp.Solve(
            self.csp.Phase(self.assignments_flat, next_var, next_value),
            [
                solution_collector,
                self.__make_objective_function(weights),
                self.csp.TimeLimit(max_timeout * 1000),
            ]
        )
        if solved:
            s_assignments = self.__format_assignments(solution_collector)
            self.csp.EndSearch()
            return s_assignments
        else:
            return None

    def __format_assignments(self, sc):
        s_assignments = self.__collect_assignments(sc)
        formatted_assignments = {}
        for c in self.rg_companies:
            formatted_assignments[c] = {}
            for t in self.rg_terms:
                assigned_students = []
                for s in self.rg_students:
                    if s_assignments[(c, t, s)] == 1:
                        assigned_students.append(s)
                formatted_assignments[c][t] = assigned_students
        return formatted_assignments

    def __collect_assignments(self, sc):
        s_assignments = {}
        for c in self.rg_companies:
            for t in self.rg_terms:
                for s in self.rg_students:
                    s_assignments[(c, t, s)] = sc.Value(0, self.assignments[(c, t, s)])
        return s_assignments
