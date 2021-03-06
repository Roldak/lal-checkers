"""
Provides a collection of common useful operations on sparse array domains.
"""
from lalcheck.ai.utils import partition
from lalcheck.ai.domain_capabilities import Capability
import boolean_ops
import util_ops


def get(domain):
    """
    :param lalcheck.domains.SparseArray domain: The sparse array domain.

    :return: A function which returns all values that can be get from the
        given indices.

    :rtype: (list, object) -> object
    """
    index_dom = domain.index_dom
    elem_dom = domain.elem_dom

    def do(array, index):
        """
        :param list array: A set of arrays to get from, represented by an
            element of the sparse array domain.

        :param object index: A set of indices to get from, represented by an
            element of the sparse array domain's index domain.

        :return: A set of values that can be get from the given indices, as
            an element of the sparse array domain's element domain.

        :rtype: object
        """
        relevant = [
            elem[1]
            for elem in array
            if not index_dom.is_empty(
                index_dom.meet(index, elem[0])
            )
        ]

        return reduce(elem_dom.join, relevant, elem_dom.bottom)

    return do


def updated(domain):
    """
    :param lalcheck.domains.SparseArray domain: The sparse array domain.

    :return: A function which returns all the arrays that can result after
        updating it to the given index with the given value.

    :rtype: (list, object, object) -> list
    """
    index_dom = domain.index_dom
    has_split = Capability.HasSplit(index_dom)

    def do_precise(array, val, indices):
        """
        :param list array: A set of arrays to update, represented by an
            element of the sparse array domain.

        :param object val: A set of concrete values to update the arrays with,
            represented by an element of the sparse array domain's element
            domain.

        :param object indices: A set of indices to update the array at,
            represented by an element of the sparse array domain's index
            domain.

        :return: A new set of arrays resulting from updating the given arrays
            at the given indices with the given values, represented by an
            element of the sparse array domain.
            If the indices represent a single concrete value, the update is
            done precisely by splitting the existing entry that overlaps with
            this concrete value (it it exists) and adding a new entry for it.

        :rtype: list
        """

        if index_dom.size(indices) == 1:
            not_relevant, relevant = partition(
                array,
                lambda elem: index_dom.is_empty(
                    index_dom.meet(indices, elem[0])
                )
            )

            updated_relevant = [
                (split, elem[1])
                for elem in relevant
                for split in index_dom.split(elem[0], indices)
                if not index_dom.is_empty(split)
            ]

            return domain.normalized(
                not_relevant +
                updated_relevant +
                [(indices, val)]
            )
        else:
            return domain.join(
                array,
                [(indices, val)]
            )

    def do_imprecise(array, val, indices):
        """
        :param list array: A set of arrays to update, represented by an
            element of the sparse array domain.

        :param object val: A set of concrete values to update the arrays with,
            represented by an element of the sparse array domain's element
            domain.

        :param object indices: A set of indices to update the array at,
            represented by an element of the sparse array domain's index
            domain.

        :return: A new set of arrays resulting from updating the given arrays
            at the given indices with the given values, represented by an
            element of the sparse array domain.

        :rtype: list
        """
        return domain.join(array, [(indices, val)])

    return do_precise if has_split else do_imprecise


def index_range(domain):
    """
    Returns a function which takes an abstract array and returns an abstract
    element representing the range of the indices which are defined in the
    array.

    :param lalcheck.ai.domains.SparseArray domain: The sparse array domain.
    :rtype: list -> object
    """
    index_dom = domain.index_dom

    def do(array):
        """
        Returns an abstract element of the index domain which represents the
        range of indices that are defined in the array.

        :param list array: The abstract array.
        :rtype: object
        """
        return reduce(index_dom.join, [i for i, e in array], index_dom.bottom)

    return do


def in_values_of(domain):
    """
    Returns a function which checks that the given element belongs to the set
    of values that a given array holds.

    For example, let:
      - my_domain = SparseArrayDomain(Intervals(-10, 10), Intervals(-10, 10)).
      - my_array = [((-10, 3), (2, 3)), ((4, 10), (6, 10))]
      - do = in_values_of(my_domain)

    Then:
      - do((2, 2),  my_array) returns {True}.
      - do((4, 5),  my_array) returns {False}.
      - do((2, 10), my_array) returns {True, False}.
      - do(bottom, my_array) returns {}.

    :param lalcheck.ai.domains.SparseArray domain: The sparse array domain.
    :rtype: (object, list) -> frozenset
    """
    elem_dom = domain.elem_dom
    is_included = util_ops.included(elem_dom)

    def do(x, array):
        """
        Checks whether the given set of elements (as an element of the
        component domain of the array domain) is included in the set of
        values that the given array holds.

        :type x: object
        :type array: list
        :rtype: frozenset
        """
        res = boolean_ops.none
        for _, e in array:
            res = boolean_ops.Boolean.join(res, is_included(x, e))
            if res == boolean_ops.both:
                # Early exit, as the rest of the iterations would be joins on
                # the top element.
                break
        return res

    return do


def array_string(domain):
    """
    :param lalcheck.domains.SparseArray domain: The sparse array domain.

    :return: A function which takes a set of arrays as an element of the sparse
        array domain and returns all the arrays that can result from
        updating them with an arbitrary long sequence of (index, element)
        pairs.

    :rtype: (list, *object) -> list
    """
    def do(*args):
        """
        :param list array: A set of arrays to update, represented by an
            element of the sparse array domain.

        :param *object args: A sequence of objects i_1, e_1, ..., i_n, e_n
            (a flattened list of pairs) such that each (i_k, e_k) is a set of
            concrete index-value pairs to update the arrays with, represented
            by an element of the sparse array domain's product domain
            (Index * Element).

        :return: A new set of arrays resulting from updating the given arrays
            at the given indices with the given values, represented by an
            element of the sparse array domain.

        :rtype: list
        """

        if len(args) == 0:
            return domain.empty

        # Transform the flattened list of pairs into an actual list of pairs.
        arrs = [[(args[i], args[i+1])] for i in range(0, len(args), 2)]

        return domain.normalized(reduce(domain.join, arrs))

    return do


def inv_get(domain):
    """
    :param lalcheck.domains.SparseArray domain: The sparse array domain.

    :return: A function which performs the inverse of the get operation.

    :rtype: (object, list, object) -> (list, object)
    """
    index_dom = domain.index_dom
    elem_dom = domain.elem_dom
    do_get = get(domain)
    do_updated = updated(domain)
    has_split = Capability.HasSplit(index_dom)

    def do_precise(res, array_constr, index_constr):
        """
        :param object res: The set of values corresponding to an output of the
            get operation, represented by an element of the sparse array
            domain's element domain.

        :param list array_constr: A constraint on the set of arrays.

        :param object index_constr: A constraint on the set of indices.

        :return: A set of arrays which contain the expected values at the
            given indices, and these indices.
        """
        biggest_array = [
            (split, elem_dom.top)
            for split in index_dom.split(
                index_dom.top,
                index_constr
            )
        ] + [(index_constr, res)]

        array_meet = domain.meet(biggest_array, array_constr)

        if domain.is_empty(array_meet):
            return None

        indices = reduce(index_dom.join, [
            i
            for i, v in array_meet
            if index_dom.le(i, index_constr) and elem_dom.le(v, res)
        ], index_dom.bottom)

        indices_size = index_dom.size(indices)

        if indices_size == 0:
            return None
        elif indices_size == 1:
            return do_updated(
                array_constr,
                elem_dom.meet(res, do_get(array_constr, indices)),
                indices
            ), indices
        else:
            return array_constr, indices

    def do_imprecise(res, array_constr, index_constr):
        """
        :param object res: The set of values corresponding to an output of the
            get operation, represented by an element of the sparse array
            domain's element domain.

        :param list array_constr: A constraint on the set of arrays.

        :param object index_constr: A constraint on the set of indices.

        :return: A set of arrays which contain the expected values at the
            given indices, and these indices.
        """
        if domain.is_empty(array_constr) or index_dom.is_empty(index_constr):
            return None
        else:
            return array_constr, index_constr

    return do_precise if has_split else do_imprecise


def inv_updated(domain):
    def do(res, array_constr, val_constr, indices_constr):
        raise NotImplementedError

    return do


def inv_index_range(domain):
    """
    Returns a function which performs the inverse of retrieving the index
    range of an abstract array.

    :param lalcheck.ai.domains.SparseArray domain: The array domain.
    :rtype: (object, list) -> list
    """
    index_dom = domain.index_dom

    def do(res, array_constr):
        """
        Given an expected range and an abstract array constraint, returns
        all possible arrays which have the given index range and satisfy the
        array constraint, as an element of the sparse array domain.

        :param object res: The expected index range as an element of the
            index domain of the array domain.
        :param list array_constr: The constraint on the array as an element
            of the array domain.
        :rtype: list
        """
        if index_dom.is_empty(res) or domain.is_empty(array_constr):
            return None

        return [
            (index_dom.meet(res, i), e)
            for i, e in array_constr
            if not index_dom.is_empty(index_dom.meet(res, i))
        ]

    return do


def inv_in_values_of(domain):
    """
    Returns a function which performs the inverse of checking that a given
    element is in the range of values that the array holds.

    For example, let:
      - my_domain = SparseArrayDomain(Intervals(-10, 10), Intervals(-10, 10)).
      - my_array_constr = [((-10, 3), (2, 3)), ((4, 10), (6, 10))]
      - do_inv = inv_in_values_of(my_domain)

    Then:
      - do_inv({False}, X_CONSTR, ARRAY_CONSTR) returns X_CONSTR, ARRAY_CONSTR:
            do_inv is only precise for res = {True}.

      - do_inv({True}, (2, 3),  my_array_constr) returns
            (2, 3), [((-10, 3), (2, 3))].

      - do_inv({True}, (2, 10), my_array_constr) returns
            (2, 10), [((-10, 3), (2, 3)), ((4, 10), (6, 10))]

      - do_inv({True}, (-3, 10), my_array_constr) returns
            (2, 10), [((-10, 3), (2, 3)), ((4, 10), (6, 10))]

      - do_inv({True}, (-3, 8), my_array_constr) returns
            (2, 8), [((-10, 3), (2, 3)), ((4, 10), (6, 8))]

    :param lalcheck.ai.domains.SparseArray domain: The sparse array domain.
    :rtype: (frozenset, object, list) -> (object, list)
    """
    elem_dom = domain.elem_dom

    def do(res, x_constr, array_constr):
        """
        Performs the inverse of checking whether a given set of elements (as
        an element of the component domain of the array domain) is included
        in the values that the array can hold.

        :param frozenset res: The expected boolean result.
        :param object x_constr: A constraint on the element.
        :param list array_constr: A constraint on the array.
        :rtype: (object, list)
        """
        if (elem_dom.is_empty(x_constr) or
                domain.is_empty(array_constr) or
                res == boolean_ops.none):
            return None

        if res == boolean_ops.true:
            # Compute the meet with all elements in the array.
            meets = [elem_dom.meet(x_constr, e) for i, e in array_constr]

            # Refine the constraint on the array knowing that its values cannot
            # hold what is outside the previously computed meet.
            expected_arr = [
                (i, meet)
                for meet, (i, _) in zip(meets, array_constr)
                if not elem_dom.is_empty(meet)
            ]

            # If the resulting array is empty, there are no solutions.
            if domain.is_empty(expected_arr):
                return None

            return reduce(elem_dom.join, meets, elem_dom.bottom), expected_arr

        return x_constr, array_constr

    return do


def inv_array_string(domain):
    def do(_, *args):
        return args

    return do


def lit(_):
    raise NotImplementedError
