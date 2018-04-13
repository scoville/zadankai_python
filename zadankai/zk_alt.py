#!/usr/local/bin/python3

from ortools.constraint_solver import pywrapcp


class ZadankaiCSP:
    __DEFAULT_NEXT_VAR = pywrapcp.Solver.CHOOSE_RANDOM
    __DEFAULT_NEXT_VALUE = pywrapcp.Solver.ASSIGN_MAX_VALUE

    def __init__(self, companies, students, terms):
        self.csp = pywrapcp.Solver("zadankai")
        self.solution_collector = None

        self.__process_data(companies, students, terms)

        self.__make_variables()
        self.__make_expressions()
        self.__make_constraints()

    def __process_data(self, companies, students, terms):
        self.__process_cardinality(companies['count'], students['count'], terms['count'], companies['groups'])
        self.__process_groups(companies['groups'])
        self.__process_ratings(companies['ratings'], students['ratings'])

    def __process_cardinality(self, num_companies, num_students, num_terms, groups):
        self.num_companies = num_companies
        self.num_students = num_students
        self.num_terms = num_terms
        self.num_groups = sum(groups)

        self.rg_companies = range(num_companies)
        self.rg_students = range(num_students)
        self.rg_terms = range(num_terms)
        self.rg_groups = range(self.num_groups)

    def __process_groups(self, groups):
        self.num_groups_per_company = groups
        self.target_headcount = int(self.num_students / self.num_groups)
        self.company_groups = {}
        current_index = 0
        for c in self.rg_companies:
            self.company_groups[c] = list(range(current_index, current_index + self.num_groups_per_company[c]))
            current_index += self.num_groups_per_company[c]
        self.group_company = {}
        for c in self.rg_companies:
            for g in self.company_groups[c]:
                self.group_company[g] = c

    def __process_ratings(self, company_ratings, student_ratings):
        self.combined_ratings = {}
        for group in self.rg_groups:
            group_company = self.group_company[group]
            for student in self.rg_students:
                c_rating = int((company_ratings['values'][group_company][student] / 4) * 100)
                s_rating = int((student_ratings['values'][student][group_company] / 4) * 100)
                combined = company_ratings['weight'] * c_rating + student_ratings['weight'] * s_rating
                combined /= company_ratings['weight'] + student_ratings['weight']
                self.combined_ratings[(group, student)] = int(combined)

    def __make_variables(self):
        self.assignments = {}
        self.assignments_flat = []
        for group in self.rg_groups:
            for term in self.rg_terms:
                for student in self.rg_students:
                    assignment = self.csp.BoolVar(f"assignment(g{group}, t{term}, s{student})")
                    self.assignments[(group, term, student)] = assignment
                    self.assignments_flat.append(assignment)

    def __make_expressions(self):
        self.headcounts = {}
        self.headcounts_flat = []
        for group in self.rg_groups:
            for term in self.rg_terms:
                headcount = self.csp.Sum([
                    self.assignments[(group, term, s)]
                    for s in self.rg_students
                ])
                self.headcounts[(group, term)] = headcount
                self.headcounts_flat.append(headcount)

        self.assigned_dissatisfaction = {}
        for g in self.rg_groups:
            for t in self.rg_terms:
                for s in self.rg_students:
                    dissatisfaction = self.assignments[(g, t, s)] * (100 - self.combined_ratings[(g, s)])
                    self.assigned_dissatisfaction[(g, t, s)] = dissatisfaction

        self.ttl_dissatisfaction = self.csp.Sum([
            self.assigned_dissatisfaction[(g, t, s)]
            for g in self.rg_groups
            for t in self.rg_terms
            for s in self.rg_students
        ])
        self.avg_dissatisfaction = self.ttl_dissatisfaction // (self.num_groups * self.num_terms * self.num_students)
        self.var_dissatisfaction = self.csp.Sum([
            (self.assigned_dissatisfaction[(g, t, s)] - self.avg_dissatisfaction).Square()
            for g in self.rg_groups
            for t in self.rg_terms
            for s in self.rg_students
        ]) // (self.num_groups * self.num_terms * self.num_students)

        self.combined_assignments = {}
        self.combined_assignments_flat = []
        for group in self.rg_groups:
            for student in self.rg_students:
                combined_assignment = self.csp.Sum([
                    self.assignments[(group, t, student)]
                    for t in self.rg_terms
                ])
                self.combined_assignments[(group, student)] = combined_assignment
                self.combined_assignments_flat.append(combined_assignment)

        self.duplicates = {}
        self.duplicates_flat = []
        for company in self.rg_companies:
            for student in self.rg_students:
                summed = self.csp.Sum([
                    self.combined_assignments[(g, student)]
                    for g in self.company_groups[company]
                ])
                duplicate = self.csp.IsDifferentVar(summed, self.csp.IntConst(0)) * self.csp.IsDifferentVar(summed, self.csp.IntConst(1)) * (summed - 1)
                self.duplicates[(company, student)] = duplicate
                self.duplicates_flat.append(duplicate)

        self.ttl_company_duplicates = [
            self.csp.Sum([self.duplicates[(c, s)] for s in self.rg_students])
            for c in self.rg_companies
        ]

        self.ttl_duplicates = self.csp.Sum(self.ttl_company_duplicates)

    def __make_constraints(self):
        self.__make_business_constraints()
        self.__make_symmetry_breaking_constraints()

    def __make_business_constraints(self):
        # Each Term, a Student can only be assigned to one Company
        for term in self.rg_terms:
            for student in self.rg_students:
                self.csp.Add(self.csp.Sum([
                    self.assignments[(g, term, student)]
                    for g in self.rg_groups
                ]) == 1)

        # Each Group sees each Student at most once
        for group in self.rg_groups:
            for student in self.rg_students:
                self.csp.Add(self.csp.Sum([
                    self.assignments[(group, t, student)]
                    for t in self.rg_terms
                ]) <= 1)

        # Each Group has either target_headcount or target_headcount + 1 students per term
        for group in self.rg_groups:
            for term in self.rg_terms:
                self.csp.Add(self.headcounts[(group, term)] >= self.target_headcount)
                self.csp.Add(self.headcounts[(group, term)] <= self.target_headcount + 1)

    def __make_symmetry_breaking_constraints(self):
        # TODO
        pass

    def __make_objective_function(self, weights):
        dissatisfaction_objective = (20 * 100 * self.avg_dissatisfaction + 80 * self.var_dissatisfaction) // 100
        duplicate_objective = self.ttl_duplicates
        objective_var = (duplicate_objective * 80 + dissatisfaction_objective * 20) // 100
        # objective_var = duplicate_objective

        return self.csp.Minimize(objective_var, 1)

    def __make_solution_collector(self):
        collector = self.csp.LastSolutionCollector()

        collector.Add(self.assignments_flat)

        collector.Add(self.headcounts_flat)
        collector.Add(self.combined_assignments_flat)
        collector.Add(self.duplicates_flat)
        collector.Add(self.ttl_company_duplicates)
        collector.Add(self.ttl_duplicates)

        return collector

    def solve(self, weights, next_var=__DEFAULT_NEXT_VAR, next_value=__DEFAULT_NEXT_VALUE, max_timeout=60):
        self.solution_collector = self.__make_solution_collector()
        solved = self.csp.Solve(
            self.csp.Phase(self.assignments_flat, next_var, next_value),
            [
                self.solution_collector,
                self.__make_objective_function(weights),
                self.csp.TimeLimit(max_timeout * 1000),
                # self.csp.SolutionsLimit(1),
            ]
        )
        if solved:
            s_assignments = self.__format_assignments()
            self.csp.EndSearch()
            return s_assignments
        else:
            return None

    def __format_assignments(self):
        s_assignments = self.__collect_assignments()
        formatted_assignments = {}
        for c in self.rg_companies:
            formatted_assignments[c] = {}
            for gi in range(self.num_groups_per_company[c]):
                g = self.company_groups[c][gi]
                formatted_assignments[c][gi] = {}
                for t in self.rg_terms:
                    assigned_students = []
                    for s in self.rg_students:
                        if s_assignments[(g, t, s)] == 1:
                            assigned_students.append(s)
                    formatted_assignments[c][gi][t] = assigned_students
        return formatted_assignments

    def __collect_assignments(self):
        s_assignments = {}
        for g in self.rg_groups:
            for t in self.rg_terms:
                for s in self.rg_students:
                    s_assignments[(g, t, s)] = self.solution_collector.Value(0, self.assignments[(g, t, s)])
        return s_assignments

    def __collect_combined_assignments(self):
        s_combined_assignments = {}
        for g in self.rg_groups:
            for s in self.rg_students:
                s_combined_assignments[(g, s)] = self.solution_collector.Value(0, self.combined_assignments[(g, s)])
        return s_combined_assignments

    def __collect_duplicates(self):
        s_duplicates = {}
        for c in self.rg_companies:
            for s in self.rg_students:
                s_duplicates[(c, s)] = self.solution_collector.Value(0, self.duplicates[(c, s)])
        return s_duplicates

    def __collect_ttl_company_duplicates(self):
        s_ttl_company_duplicates = {}
        for c in self.rg_companies:
            s_ttl_company_duplicates[c] = self.solution_collector.Value(0, self.ttl_company_duplicates[c])
        return s_ttl_company_duplicates

    def __collect_headcounts(self):
        s_headcounts = {}
        for g in self.rg_groups:
            for t in self.rg_terms:
                s_headcounts[(g, t)] = self.solution_collector.Value(0, self.headcounts[(g, t)])
        return s_headcounts

    def __print_raw_assignments(self):
        s_assignments = self.__collect_assignments()

        cell_content_length = 5
        cell_padding = 1
        cell_length = cell_content_length + cell_padding
        cell_format = f"{{:^{cell_content_length}}}"
        separator = "|"
        separator_padding = 1
        separator_length = len(separator) + separator_padding
        label_length = cell_length + separator_length
        term_length = cell_length * self.num_students + separator_length
        term_format = f"{{:^{term_length - separator_length}}}"
        row_length = label_length + self.num_terms * term_length - 1

        print("", end=" " * (label_length - separator_length))
        print(separator, end=" " * separator_padding)
        for t in self.rg_terms:
            print(term_format.format(f"t{t}"), end="")
            print(separator, end=" " * separator_padding)
        print()

        print("", end=" " * (label_length - separator_length))
        print(separator, end=" " * separator_padding)
        for _ in self.rg_terms:
            for s in self.rg_students:
                print(cell_format.format(f"s{s}"), end=" " * cell_padding)
            print(separator, end=" " * separator_padding)
        print()

        for g in self.rg_groups:
            if self.group_company[g] > 0 and self.group_company[g] == self.group_company[g - 1]:
                print(" " * cell_length, end="")
                print("-" * (row_length - cell_length))
            else:
                print("-" * row_length)
            print(cell_format.format(f"g{g}"), end=" " * cell_padding)
            print(separator, end=" " * separator_padding)
            for t in self.rg_terms:
                for s in self.rg_students:
                    assigned = s_assignments[(g, t, s)]
                    print(cell_format.format(assigned), end=" " * cell_padding)
                print(separator, end=" " * separator_padding)
            print()
        print("-" * row_length)
        print()

    def __print_combined_assignments(self):
        s_combined_assignments = self.__collect_combined_assignments()

        cell_content_length = 5
        cell_padding = 1
        cell_length = cell_content_length + cell_padding
        cell_format = f"{{:^{cell_content_length}}}"
        separator = "|"
        separator_padding = 1
        separator_length = len(separator) + separator_padding
        label_length = cell_length + separator_length
        term_length = cell_length * self.num_students + separator_length
        row_length = label_length + term_length - 1

        print("", end=" " * (label_length - separator_length))
        print(separator, end=" " * separator_padding)
        for s in self.rg_students:
            print(cell_format.format(f"s{s}"), end=" " * cell_padding)
        print(separator, end=" " * separator_padding)
        print()

        for g in self.rg_groups:
            if self.group_company[g] > 0 and self.group_company[g] == self.group_company[g - 1]:
                print(" " * cell_length, end="")
                print("-" * (row_length - cell_length))
            else:
                print("-" * row_length)
            print(cell_format.format(f"g{g}"), end=" " * cell_padding)
            print(separator, end=" " * separator_padding)
            for s in self.rg_students:
                assigned = s_combined_assignments[(g, s)]
                print(cell_format.format(assigned), end=" " * cell_padding)
            print(separator, end=" " * separator_padding)
            print()
        print("-" * row_length)
        print()

    def __print_duplicates(self):
        s_duplicates = self.__collect_duplicates()

        cell_content_length = 5
        cell_padding = 1
        cell_length = cell_content_length + cell_padding
        cell_format = f"{{:^{cell_content_length}}}"
        separator = "|"
        separator_padding = 1
        separator_length = len(separator) + separator_padding
        label_length = cell_length + separator_length
        term_length = cell_length * self.num_students + separator_length
        row_length = label_length + term_length - 1

        print("", end=" " * (label_length - separator_length))
        print(separator, end=" " * separator_padding)
        for s in self.rg_students:
            print(cell_format.format(f"s{s}"), end=" " * cell_padding)
        print(separator, end=" " * separator_padding)
        print()

        for c in self.rg_companies:
            print("-" * row_length)
            print(cell_format.format(f"c{c}"), end=" " * cell_padding)
            print(separator, end=" " * separator_padding)
            for s in self.rg_students:
                assigned = s_duplicates[(c, s)]
                print(cell_format.format(assigned), end=" " * cell_padding)
            print(separator, end=" " * separator_padding)
            print()
        print("-" * row_length)
        print()

    def __print_ttl_duplicates(self):
        s_ttl_company_duplicates = self.__collect_ttl_company_duplicates()
        s_ttl_duplicates = self.solution_collector.Value(0, self.ttl_duplicates)

        cell_content_length = 5
        cell_padding = 1
        cell_length = cell_content_length + cell_padding
        cell_format = f"{{:^{cell_content_length}}}"
        separator = "|"
        separator_padding = 1
        separator_length = len(separator) + separator_padding
        label_length = cell_length + separator_length
        term_length = cell_length + separator_length
        row_length = label_length + term_length - 1

        print("", end=" " * (label_length - separator_length))
        print(separator, end=" " * separator_padding)
        print(cell_format.format(f"dup"), end=" " * cell_padding)
        print(separator, end=" " * separator_padding)
        print()

        for c in self.rg_companies:
            print("-" * row_length)
            print(cell_format.format(f"c{c}"), end=" " * cell_padding)
            print(separator, end=" " * separator_padding)
            assigned = s_ttl_company_duplicates[c]
            print(cell_format.format(assigned), end=" " * cell_padding)
            print(separator, end=" " * separator_padding)
            print()
        print("-" * row_length)
        print()

        print(s_ttl_duplicates)
        print()

    def __print_assignments(self):
        s_assignments = self.__collect_assignments()
        s_headcounts = self.__collect_headcounts()

        largest_group_or_target_per_term = [
            max([max(s_headcounts[(g, t)], self.target_headcount) for g in self.rg_groups])
            for t in self.rg_terms
        ]

        cell_content_length = 4
        cell_padding = 1
        cell_length = cell_content_length + cell_padding
        cell_format = f"{{:^{cell_content_length}}}"
        separator = "|"
        separator_padding = 1
        separator_length = len(separator) + separator_padding
        label_length = cell_length + separator_length
        term_lengths = [cell_length * largest_group_or_target_per_term[t] + separator_length for t in self.rg_terms]
        term_formats = [f"{{:^{term_lengths[t] - separator_length}}}" for t in self.rg_terms]
        row_length = label_length + sum(term_lengths) - 1

        print("", end=" " * (label_length - separator_length))
        print(separator, end=" " * separator_padding)
        for t in self.rg_terms:
            print(term_formats[t].format(f"t{t}"), end="")
            print(separator, end=" " * separator_padding)
        print()

        print("", end=" " * (label_length - separator_length))
        print(separator, end=" " * separator_padding)
        for t in self.rg_terms:
            for sl in range(largest_group_or_target_per_term[t]):
                print(cell_format.format(f"sl{sl}"), end=" " * cell_padding)
            print(separator, end=" " * separator_padding)
        print()

        already_assigned = [[] for _ in self.rg_companies]

        for g in self.rg_groups:
            group_company = self.group_company[g]
            if self.group_company[g] > 0 and self.group_company[g] == self.group_company[g - 1]:
                print(" " * cell_length, end="")
                print("-" * (row_length - cell_length))
            else:
                print("-" * row_length)
            print(cell_format.format(f"g{g}"), end=" " * cell_padding)
            print(separator, end=" " * separator_padding)
            target_assignments = self.target_headcount
            for t in self.rg_terms:
                assigned_students = []
                for s in self.rg_students:
                    if s_assignments[(g, t, s)] == 1:
                        assigned_students.append(s)
                num_assigned_students = len(assigned_students)
                student_index = 0
                for sl in range(largest_group_or_target_per_term[t]):
                    printed = assigned_students[student_index] if student_index < num_assigned_students else " "
                    if printed != ' ':
                        student = assigned_students[student_index]
                        if student in already_assigned[group_company]:
                            printed = f"({printed})"
                        else:
                            already_assigned[group_company].append(student)
                    print(cell_format.format(printed), end=" " * cell_padding)
                    student_index += 1
                print(separator, end=" " * separator_padding)
            print()
        print("-" * row_length)
        print()

    def __print_compatibilities(self):
        cell_content_length = 5
        cell_padding = 1
        cell_length = cell_content_length + cell_padding
        cell_format = f"{{:^{cell_content_length}}}"
        separator = "|"
        separator_padding = 1
        separator_length = len(separator) + separator_padding
        label_length = cell_length + separator_length
        row_length = label_length + self.num_students * cell_length + separator_length - 1

        print("", end=" " * (label_length - separator_length))
        print(separator, end=" " * separator_padding)
        for s in self.rg_students:
            print(cell_format.format(f"s{s}"), end=" " * cell_padding)
        print(separator, end=" " * separator_padding)
        print()

        for g in self.rg_groups:
            print("-" * row_length)
            print(cell_format.format(f"g{g}"), end=" " * cell_padding)
            print(separator, end=" " * separator_padding)
            for s in self.rg_students:
                compatibility = self.combined_ratings[(g, s)]
                print(cell_format.format(compatibility), end=" " * cell_padding)
            print(separator, end=" " * separator_padding)
            print()
        print("-" * row_length)
        print()

    def print_solution(self):
        if self.solution_collector is not None:
            self.__print_raw_assignments()
            self.__print_combined_assignments()
            self.__print_duplicates()
            self.__print_ttl_duplicates()
            self.__print_assignments()
        else:
            print('No solutions yet')
