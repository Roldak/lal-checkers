"""
Defines the TypeInterpreter interface, as well as a few common
TypeInterpreters.
"""

from lalcheck.ai import domains
from lalcheck.ai import types
from lalcheck.ai.constants import lits, access_paths
from lalcheck.ai.domain_ops import (
    boolean_ops,
    interval_ops,
    finite_lattice_ops,
    product_ops,
    sparse_array_ops,
    access_paths_ops,
    ram_ops,
    util_ops
)
from lalcheck.ai.utils import Transformer

from lalcheck.ai.constants import ops


class TypeInterpretation(object):
    """
    A type interpretation is how the middle-end type is represented when
    doing abstract interpretation. It provides the abstract domain used to
    represent elements of the type, the implementation of the different
    operations available for that type, etc.
    """
    def __init__(self, domain, def_provider_builder, builder):
        """
        :param domains.AbstractDomain domain: The abstract domain used to
            represent the type.

        :param Signature->(function, function) def_provider_builder:
            A function which can be called with the signature of the desired
            definition to retrieve it and its inverse.

        :param function builder: A function used to build elements of the
            domain from literal values.
        """
        self.domain = domain
        self.def_provider_builder = def_provider_builder
        self.builder = builder


TypeInterpreter = Transformer
"""
TypeInterpreter[T] is equivalent to Transformer[T, TypeInterpretation]
"""

type_interpreter = Transformer.as_transformer
delegating_type_interpreter = Transformer.from_transformer_builder
memoizing_type_interpreter = Transformer.make_memoizing


class Signature(object):
    """
    The signature of a definition.

    Examples:
    - Signature(
        "+",
        (Intervals(-10, 10), Intervals(-10, 10)),
        Intervals(-10, 10),
        None
      )

    - Signature(
        "fopen",
        (Files,),
        None,
        (0,)
      )
    """

    def __init__(self, name, input_domains, output_domain, out_param_indices,
                 userdata=None):
        """
        :param string name: The name of the function.

        :param tuple[domains.AbstractDomain] input_domains: The abstract
            domains representing each input.

        :param domains.AbstractDomain | None output_domain: The abstract domain
            representing the output, if any.

        :param tuple[int] out_param_indices: The tuple indicating which
            of the parameters are out.

        :param object userdata: Any user data.
        """
        self.name = name
        self.input_domains = input_domains
        self.output_domain = output_domain
        self.out_param_indices = out_param_indices
        self.userdata = userdata

    def contains(self, domain):
        """
        Returns True if this signature contains the given domain, either as
        one of its input domain, or as the output domain.

        :param domains.AbstractDomain domain: The domain to consider.
        """
        return domain in self.input_domains or domain == self.output_domain

    def substituted(self, domain, by):
        """
        Returns a new signature in which every occurrence of a given domain is
        replaced by another domain.

        :param domains.AbstractDomain domain: The domain to replace in this
            signature
        :param domains.AbstractDomain by: The domain to replace it with.
        """
        return Signature(
            self.name,
            tuple(
                (by if dom == domain else dom)
                for dom in self.input_domains
            ),
            by if domain == self.output_domain else self.output_domain,
            self.out_param_indices
        )

    def __hash__(self):
        return hash((
            self.name,
            self.input_domains,
            self.output_domain,
            self.out_param_indices,
            self.userdata
        ))

    def __eq__(self, other):
        """
        :param Signature other:
        :return:
        """
        return (self.name == other.name and
                self.input_domains == other.input_domains and
                self.output_domain == other.output_domain and
                self.out_param_indices == other.out_param_indices and
                self.userdata == other.userdata)

    def __str__(self):
        return "{}({}){}".format(
            self.name,
            ", ".join(
                "{}{}".format(
                    "out " if i in self.out_param_indices else "",
                    str(dom)
                )
                for i, dom in enumerate(self.input_domains)
            ),
            "->{}".format(self.output_domain) if self.output_domain
            else ""
        )


DefProvider = Transformer
"""
DefProvider[T] is equivalent to Transformer[Signature, (function, function)]
"""
def_provider = Transformer.as_transformer


def def_provider_builder(f):
    def make(_):
        return def_provider(f)
    return make


def dict_to_provider(def_dict):
    """
    Converts a dictionary of definitions indexed by their names and domain
    signatures to a def provider.
    """
    @def_provider_builder
    def provider(sig):
        if sig in def_dict:
            return def_dict[sig]
    return provider


def _signer(input_domains, output_domain, out_param_indices=()):
    """
    Returns a function which, given a function name, output its complete
    signature.

    :param tuple[domains.AbstractDomain] input_domains: The abstract
        domains representing each input.

    :param domains.AbstractDomain | None output_domain: The abstract domain
        representing the output, if any.

    :param tuple[int] out_param_indices: The tuple indicating which
        of the parameters are out.

    :rtype: str -> Signature
    """
    def f(name):
        return Signature(name, input_domains, output_domain, out_param_indices)
    return f


def _not_implemented(*_):
    raise NotImplementedError


def new_universe_interpretation():
    """
    Returns a new instance of a type interpretation that uses the Universe
    domain.

    :rtype: TypeInterpretation
    """
    dom = domains.Universe()

    def not_implemented(*_):
        return dom.top

    @def_provider_builder
    def provider(_):
        pass

    return TypeInterpretation(dom, provider, not_implemented)


@type_interpreter
def default_boolean_interpreter(tpe):
    if tpe.is_a(types.Boolean):
        bool_dom = boolean_ops.Boolean

        un_fun_sig = _signer((bool_dom,), bool_dom)
        bin_fun_sig = _signer((bool_dom, bool_dom), bool_dom)

        defs = {
            un_fun_sig(ops.NOT): (boolean_ops.not_, boolean_ops.inv_not),
            bin_fun_sig(ops.AND): (boolean_ops.and_, boolean_ops.inv_and),
            bin_fun_sig(ops.OR): (boolean_ops.or_, boolean_ops.inv_or),

            bin_fun_sig(ops.EQ): (finite_lattice_ops.eq(bool_dom),
                                  finite_lattice_ops.inv_eq(bool_dom)),

            bin_fun_sig(ops.NEQ): (finite_lattice_ops.neq(bool_dom),
                                   finite_lattice_ops.inv_neq(bool_dom))
        }

        builder = boolean_ops.lit

        return TypeInterpretation(
            bool_dom,
            dict_to_provider(defs),
            builder
        )


def default_char_interpreter(int_range_interpreter):
    @Transformer.as_transformer
    def is_char_tpe(tpe):
        if tpe.is_a(types.ASCIICharacter):
            return tpe

    @Transformer.as_transformer
    def char_interpreter(int_interp):
        def builder(val):
            return int_interp.builder(ord(val))

        return TypeInterpretation(
            int_interp.domain,
            int_interp.def_provider_builder,
            builder
        )

    return is_char_tpe >> int_range_interpreter >> char_interpreter


@type_interpreter
def default_int_range_interpreter(tpe):
    if tpe.is_a(types.IntRange):
        int_dom = domains.Intervals(tpe.frm, tpe.to)
        bool_dom = boolean_ops.Boolean

        un_fun_sig = _signer((int_dom,), int_dom)
        bin_fun_sig = _signer((int_dom, int_dom), int_dom)
        bin_rel_sig = _signer((int_dom, int_dom), bool_dom)

        defs = {
            bin_fun_sig(ops.PLUS): (
                interval_ops.add_no_wraparound(int_dom),
                interval_ops.inv_add_no_wraparound(int_dom)
            ),
            bin_fun_sig(ops.MINUS): (
                interval_ops.sub_no_wraparound(int_dom),
                interval_ops.inv_sub_no_wraparound(int_dom)
            ),

            un_fun_sig(ops.NEG): (
                interval_ops.negate(int_dom), interval_ops.negate(int_dom)
            ),

            bin_rel_sig(ops.LT): (
                interval_ops.lt(int_dom), interval_ops.inv_lt(int_dom)
            ),
            bin_rel_sig(ops.LE): (
                interval_ops.le(int_dom), interval_ops.inv_le(int_dom)
            ),
            bin_rel_sig(ops.EQ): (
                interval_ops.eq(int_dom), interval_ops.inv_eq(int_dom)
            ),
            bin_rel_sig(ops.NEQ): (
                interval_ops.neq(int_dom), interval_ops.inv_neq(int_dom)
            ),
            bin_rel_sig(ops.GE): (
                interval_ops.ge(int_dom), interval_ops.inv_ge(int_dom)
            ),
            bin_rel_sig(ops.GT): (
                interval_ops.gt(int_dom), interval_ops.inv_gt(int_dom)
            )
        }

        builder = interval_ops.lit(int_dom)

        return TypeInterpretation(
            int_dom,
            dict_to_provider(defs),
            builder
        )


@type_interpreter
def default_real_range_interpreter(tpe):
    if tpe.is_a(types.RealRange):
        return new_universe_interpretation()


@type_interpreter
def default_enum_interpreter(tpe):
    if tpe.is_a(types.Enum):
        elems = set(tpe.lits)
        if len(tpe.lits) < 5:
            enum_dom = domains.FiniteLattice.of_subsets(elems)
        else:
            enum_dom = domains.FiniteSubsetLattice(elems)

        bool_dom = boolean_ops.Boolean

        bin_rel_sig = _signer((enum_dom, enum_dom), bool_dom)

        defs = {
            bin_rel_sig(ops.EQ): (
                finite_lattice_ops.eq(enum_dom),
                finite_lattice_ops.inv_eq(enum_dom)
            ),
            bin_rel_sig(ops.NEQ): (
                finite_lattice_ops.neq(enum_dom),
                finite_lattice_ops.inv_neq(enum_dom)
            )
        }

        builder = finite_lattice_ops.lit(enum_dom)

        return TypeInterpretation(
            enum_dom,
            dict_to_provider(defs),
            builder
        )


def default_simple_pointer_interpreter(inner_interpreter):
    """
    Builds a simple type interpreter for pointers, representing them as either
    null or nonnull. Provides comparison ops and deref/address.

    :param TypeInterpreter inner_interpreter: interpreter for pointer elements.
    :rtype: TypeInterpreter
    """
    @Transformer.as_transformer
    def get_pointer_element(tpe):
        """
        :param types.Type tpe: The type.
        :return: The type of the element of the pointer, if relevant.
        :rtype: type.Type
        """
        if tpe.is_a(types.Pointer):
            return tpe.elem_type

    @Transformer.as_transformer
    def pointer_interpreter(elem_interpretation):
        """
        :param TypeInterpretation elem_interpretation: The interpretation of
            the pointer element.

        :return: A type interpreter for pointers of such elements.
        :rtype: TypeInterpreter
        """
        ptr_dom = domains.FiniteLattice.of_subsets({lits.NULL, lits.NOT_NULL})
        elem_dom = elem_interpretation.domain
        bool_dom = boolean_ops.Boolean

        bin_rel_sig = _signer((ptr_dom, ptr_dom), bool_dom)
        deref_sig = _signer((ptr_dom,), elem_dom)
        address_sig = _signer((elem_dom,), ptr_dom)

        builder = finite_lattice_ops.lit(ptr_dom)
        null = builder(lits.NULL)
        notnull = builder(lits.NOT_NULL)

        def deref(ptr):
            return elem_dom.bottom if ptr == null else elem_dom.top

        def inv_deref(elem, e_constr):
            if ptr_dom.is_empty(e_constr) or elem_dom.is_empty(elem):
                return None

            if ptr_dom.le(notnull, e_constr):
                return notnull

            return None

        def address(elem):
            return notnull

        def inv_address(ptr, e_constr):
            if ptr_dom.is_empty(ptr) or elem_dom.is_empty(e_constr):
                return None

            return e_constr

        defs = {
            bin_rel_sig(ops.EQ): (
                finite_lattice_ops.eq(ptr_dom),
                finite_lattice_ops.inv_eq(ptr_dom)
            ),
            bin_rel_sig(ops.NEQ): (
                finite_lattice_ops.neq(ptr_dom),
                finite_lattice_ops.inv_neq(ptr_dom)
            ),
            deref_sig(ops.DEREF): (
                deref,
                inv_deref
            ),
            address_sig(ops.ADDRESS): (
                address,
                inv_address
            )
        }

        return TypeInterpretation(
            ptr_dom,
            dict_to_provider(defs),
            builder
        )

    return get_pointer_element >> inner_interpreter >> pointer_interpreter


def default_product_interpreter(elem_interpreter):
    """
    Builds a type interpreter for product types, using the product domain of
    the domains of each of its components.

    :param TypeInterpreter elem_interpreter: interpreter for elements of
        the product.

    :rtype: TypeInterpreter
    """
    @Transformer.as_transformer
    def get_elements(tpe):
        """
        :param types.Type tpe: The type.
        :return: The type of the elements of the record, if relevant.
        :rtype: list[type.Type]
        """
        if tpe.is_a(types.Product):
            return tpe.elem_types

    @Transformer.as_transformer
    def product_interpreter(elem_interpretations):
        """
        :param list[TypeInterpretation] elem_interpretations:
        :return:
        """
        elem_doms = [interp.domain for interp in elem_interpretations]
        prod_dom = domains.Product(*elem_doms)
        bool_dom = boolean_ops.Boolean

        bin_rel_sig = _signer((prod_dom, prod_dom), bool_dom)

        elem_bin_rel_sigs = [
            _signer((interp.domain, interp.domain), bool_dom)
            for interp in elem_interpretations
        ]

        getter_sig = [
            _signer((prod_dom,), e_dom)
            for e_dom in elem_doms
        ]

        updated_sig = [
            _signer((prod_dom, e_dom), prod_dom)
            for e_dom in elem_doms
        ]

        def provider_builder(inner_prov):
            """
            Given a definition provider for the components of this product
            (the types of its fields), creates a provider for the whole product
            type. It defines the equal, not equal operators as well as
            accessors for its fields.

            :param DefProvider inner_prov: The provider for this product's
                components.

            :return: A provider for this product type.
            """

            # This provider is composed of several transformers such that:
            # 1. If the definition of the "equal" operator is asked:
            #    a. A first transformer (case_bin_op(ops.EQ)) creates the
            #       signature of the "equal" operators of each field of the
            #       product.
            #    b. A second transformer (prov_lifted) uses the given provider
            #       "inner_prov" to retrieve the definitions of the "equal"
            #       operators of the fields using their signature.
            #    c. A third transformer (bin_eq_provider) uses these
            #       definitions to generate a definition of for the "equal"
            #       operator of this particular product domain.
            #
            # 2. If the definition of the "not equal" operator is asked, the
            #    process is similar.
            #
            # 3. If a definition of a field accessors/updaters is asked, the
            #    case_get_update transformer provides it.

            prov_lifted = inner_prov.lifted()

            def case_bin_op(op):
                @Transformer.as_transformer
                def components_eq_sigs(sig):
                    if sig.name == op and sig == bin_rel_sig(op):
                        return [s(ops.EQ) for s in elem_bin_rel_sigs]

                return components_eq_sigs

            def bin_op_provider_builder(op_impl, inv_op_impl):
                @Transformer.as_transformer
                def bin_op_provider(comp_eqs):
                    eq_defs = [eq_def[0] for eq_def in comp_eqs]
                    eq_inv_defs = [eq_def[1] for eq_def in comp_eqs]

                    return (
                        op_impl(eq_defs),
                        inv_op_impl(prod_dom, eq_inv_defs, eq_defs)
                    )
                return bin_op_provider

            @def_provider
            def case_get_update(sig):
                if (isinstance(sig.name, ops.GetName)
                        and sig.name.index < len(getter_sig)
                        and sig == getter_sig[sig.name.index](sig.name)):
                    return (product_ops.getter(sig.name.index),
                            product_ops.inv_getter(prod_dom, sig.name.index))
                elif (isinstance(sig.name, ops.UpdatedName)
                        and sig.name.index < len(updated_sig)
                        and sig == updated_sig[sig.name.index](sig.name)):
                    return (product_ops.updater(sig.name.index),
                            product_ops.inv_updater(prod_dom, sig.name.index))

            bin_eq_provider = bin_op_provider_builder(
                product_ops.eq, product_ops.inv_eq
            )
            bin_neq_provider = bin_op_provider_builder(
                product_ops.neq, product_ops.inv_neq
            )

            return (
                (case_bin_op(ops.EQ) >> prov_lifted >> bin_eq_provider) |
                (case_bin_op(ops.NEQ) >> prov_lifted >> bin_neq_provider) |
                case_get_update
            )

        return TypeInterpretation(
            prod_dom,
            provider_builder,
            product_ops.lit
        )

    return get_elements >> elem_interpreter.lifted() >> product_interpreter


def default_array_interpreter(attribute_interpreter):
    """
    Builds a type interpreter for array types.

    :param TypeInterpreter attribute_interpreter: interpreter for the
        attributes of the array.

    :rtype: TypeInterpreter
    """
    @Transformer.as_transformer
    def get_array_attributes(tpe):
        """
        :param types.Type tpe: The type.
        :rtype: (iterable[types.Type], types.Type)
        """
        if tpe.is_a(types.Array):
            return tpe.index_types, tpe.component_type

    @Transformer.as_transformer
    def array_interpreter(attribute_interps):
        """
        :param (iterable[TypeInterpretation], TypeInterpretation)
            attribute_interps: The interpretations of the types of the indices,
            and the interpretation of the type of the components.

        :return: The interpretation for the array type

        :rtype: TypeInterpretation
        """
        index_interps, component_interp = attribute_interps

        indices_dom = domains.Product(*(
            interp.domain for interp in index_interps
        ))
        comp_dom = component_interp.domain

        array_dom = domains.SparseArray(indices_dom, comp_dom, max_elems=15)

        call_sig = _signer(
            (array_dom,) + tuple(indices_dom.domains),
            comp_dom
        )(ops.CALL)

        updated_sig = _signer(
            (array_dom, comp_dom) + tuple(indices_dom.domains),
            array_dom
        )(ops.UPDATED)

        # Get the raw implementations of array operations:

        array_get = sparse_array_ops.get(array_dom)
        array_updated = sparse_array_ops.updated(array_dom)
        array_index_range = sparse_array_ops.index_range(array_dom)
        array_in_values_of = sparse_array_ops.in_values_of(array_dom)
        array_inv_get = sparse_array_ops.inv_get(array_dom)
        array_inv_updated = sparse_array_ops.inv_updated(array_dom)
        array_inv_index_range = sparse_array_ops.inv_index_range(array_dom)
        array_inv_in_values_of = sparse_array_ops.inv_in_values_of(array_dom)
        array_string = sparse_array_ops.array_string(array_dom)

        # Wrap them in actual implementations. Indeed, the format of the
        # arguments differ between the function call generated during the IR
        # and the one defined in array_ops. The reason is that the index domain
        # of our sparse array domain is a Product of all index domains, meaning
        # that the expected parameter type is a tuple (an element of that
        # product domain). However, the calls generated during the IR are
        # flatten the indices. For example, we have:
        #
        # Get(my_two_dimensional_array, 3, 4).
        #
        # Instead of
        #
        # Get(my_two_dimensional_array, (3, 4)).
        #
        # This choice was made due to the fact that the expression (3, 4)
        # does not existing in the original source and therefore would require
        # more work to type.
        # So, the purpose of these wrapper is to transform a flattened list of
        # indices into a list of tuple.

        def actual_get(array, *indices):
            return array_get(array, indices)

        def actual_updated(array, val, *indices):
            return array_updated(array, val, indices)

        def actual_string(*args):
            # Every index i must become (i,) to be a valid element of the index
            # domain. Since args is a flattened list of pairs (index, elem),
            # an index occurs every even argument.
            return array_string(
                *((arg,) if i % 2 == 0 else arg for i, arg in enumerate(args))
            )

        def actual_in_index_range(dim):
            idx_included = util_ops.included(indices_dom.domains[dim - 1])

            def do(index, array):
                return idx_included(index, array_index_range(array)[dim - 1])

            return do

        def actual_inv_get(res, array_constr, *indices_constr):
            arr, indices = array_inv_get(res, array_constr, indices_constr)
            return (arr,) + indices

        def actual_inv_udpated(res, array_constr, val_constr, *indices_constr):
            return array_inv_updated(
                res, array_constr, val_constr, indices_constr
            )

        def actual_inv_string(res, *arg_constrs):
            # Every index i must become (i,) to be a valid element of the index
            # domain. Since args is a flattened list of pairs (index, elem),
            # an index occurs every even argument.
            return arg_constrs

        def actual_inv_in_index_range(dim):
            index_dom = indices_dom.domains[dim - 1]
            inv_included = util_ops.inv_included(index_dom)
            prod_get = product_ops.getter(dim - 1)
            prod_inv_get = product_ops.inv_getter(indices_dom, dim - 1)

            def do(res, index_constr, array_constr):
                rng_constr = array_index_range(array_constr)

                index_constr, rng_dim_constr = inv_included(
                    res, index_constr, prod_get(rng_constr)
                ) or (index_dom.bottom, index_dom.bottom)

                array_constr = array_inv_index_range(
                    prod_inv_get(rng_dim_constr, rng_constr)
                    or indices_dom.bottom,
                    array_constr
                )

                if (index_dom.is_empty(index_constr) or
                        array_dom.is_empty(array_constr)):
                    return None

                return index_constr, array_constr

            return do

        @def_provider_builder
        def provider(sig):
            if sig == call_sig:
                return actual_get, actual_inv_get
            elif sig == updated_sig:
                return actual_updated, actual_inv_udpated
            elif (sig.name == ops.STRING
                    and sig.output_domain == array_dom):
                return actual_string, actual_inv_string
            elif (sig.name == ops.IN_VALUES_OF
                    and len(sig.input_domains) == 2
                    and sig.input_domains[1] == array_dom):
                return array_in_values_of, array_inv_in_values_of
            elif (isinstance(sig.name, ops.InRangeName)
                    and len(sig.input_domains) == 2
                    and sig.input_domains[1] == array_dom):
                dim = sig.name.index
                return (
                    actual_in_index_range(dim), actual_inv_in_index_range(dim)
                )

        return TypeInterpretation(
            array_dom,
            provider,
            sparse_array_ops.lit
        )

    return (
        get_array_attributes >>
        (attribute_interpreter.lifted() & attribute_interpreter) >>
        array_interpreter
    )


@type_interpreter
def custom_pointer_interpreter(tpe):
    """
    :rtype: TypeInterpretation
    """
    if tpe.is_a(types.Pointer):
        def merge_predicate(a, b):
            return path_dom.le(a, b) or path_dom.touches(a, b)

        path_dom = domains.AccessPathsLattice()
        ptr_dom = domains.Powerset(path_dom, merge_predicate, [path_dom.top])
        bool_dom = boolean_ops.Boolean

        bin_rel_sig = _signer((ptr_dom, ptr_dom), bool_dom)

        @def_provider
        def provide_simple(sig):
            if isinstance(sig.name, access_paths.Var):
                if sig.output_domain == ptr_dom:
                    idx = sig.name.var_obj
                    elem_dom = sig.userdata[0]
                    return (
                        access_paths_ops.var_address(ptr_dom, elem_dom, idx),
                        access_paths_ops.inv_var_address(ptr_dom, idx)
                    )

            elif isinstance(sig.name, access_paths.Field):
                if sig.output_domain == ptr_dom:
                    idx = sig.name.field_obj
                    elem_dom = sig.userdata[0]
                    return (
                        access_paths_ops.field_address(ptr_dom, elem_dom, idx),
                        access_paths_ops.inv_field_address(idx)
                    )

            elif sig.name == ops.DEREF and sig.input_domains[0] == ptr_dom:
                return (
                    access_paths_ops.deref(sig.output_domain),
                    access_paths_ops.inv_deref(sig.input_domains[1])
                )

            elif (sig.name == ops.UPDATED and len(sig.input_domains) == 3
                  and isinstance(sig.input_domains[0],
                                 domains.RandomAccessMemory)
                  and sig.input_domains[1] == ptr_dom):
                return (
                    access_paths_ops.updated,
                    access_paths_ops.inv_updated,
                )

            elif (sig.name == ops.CALL and len(sig.input_domains) >= 1
                  and sig.input_domains[0] == ptr_dom):
                return (
                    access_paths_ops.call(sig),
                    access_paths_ops.inv_call()
                )

            elif sig == bin_rel_sig(ops.EQ):
                return (access_paths_ops.eq(ptr_dom),
                        access_paths_ops.inv_eq(ptr_dom))

            elif sig == bin_rel_sig(ops.NEQ):
                return (access_paths_ops.neq(ptr_dom),
                        access_paths_ops.inv_neq(ptr_dom))

        def provide_subprogram_access(inner_provider):
            # This provider is composed of several providers in the following
            # manner:
            # 1. A first transformer (get_subprogram_access_signature)
            #    constructs dynamically the Signature object of the subprogram
            #    being accessed and returns the pair (access_sig, subp_sig)
            #    where access_sig is the signature of the function which
            #    creates the subprogram access, and subp_sig is the signature
            #    of the subprogram being accessed.
            #
            # 2. A second transformer (inner_provider) transforms the second
            #    element of this pair in order to retrieve the forward and
            #    backward implementations of the subprogram being accessed.
            #
            # 3. A third transformer (subprogram_access_provider) creates the
            #    definition of the subprogram access is finally constructed
            #    using the pair (access_sig, subp_defs).

            @Transformer.as_transformer
            def get_subprogram_access_signature(sig):
                if isinstance(sig.name, access_paths.Subprogram):
                    if sig.output_domain == ptr_dom:
                        if sig.name.interface.does_return:
                            input_domains = sig.userdata[:-1]
                            output_domain = sig.userdata[-1]
                        else:
                            input_domains = sig.userdata
                            output_domain = None

                        subp_signature = Signature(
                            sig.name.subp_obj,
                            tuple(input_domains),
                            output_domain,
                            tuple(sig.name.interface.out_indices)
                        )

                        return sig, subp_signature

            @def_provider
            def subprogram_access_provider(args):
                access_sig, subp_defs = args
                subp = access_sig.name.subp_obj
                interface = access_sig.name.interface
                return (
                    access_paths_ops.subp_address(
                        ptr_dom, subp, interface, subp_defs
                    ),
                    access_paths_ops.inv_subp_address()
                )

            return (
                get_subprogram_access_signature >>
                (Transformer.identity() & inner_provider) >>
                subprogram_access_provider
            )

        def provider(inner_provider):
            # The definition provider for pointers can be split in two main
            # parts: the provider for simple definitions that do not themselves
            # require access to a def provider, and the provider for subprogram
            # accesses, which is a bit more complex.
            return (
                provide_simple |
                provide_subprogram_access(inner_provider)
            )

        return TypeInterpretation(
            ptr_dom,
            provider,
            access_paths_ops.lit(ptr_dom)
        )


@type_interpreter
def default_ram_interpreter(tpe):
    if tpe.is_a(types.DataStorage):
        mem_dom = domains.RandomAccessMemory()
        bin_rel_signer = _signer((mem_dom, mem_dom), boolean_ops.Boolean)
        cpy_offset_sig = _signer((mem_dom, mem_dom), mem_dom)(ops.COPY_OFFSET)

        @def_provider_builder
        def provider(sig):
            if isinstance(sig.name, ops.GetName):
                if sig.input_domains[0] == mem_dom:
                    return (
                        ram_ops.getter(sig.name.index, sig.output_domain),
                        ram_ops.inv_getter(sig.name.index, sig.output_domain)
                    )

            elif isinstance(sig.name, ops.UpdatedName):
                if sig.input_domains[0] == mem_dom:
                    idx = sig.name.index
                    return (
                        ram_ops.updater(idx, sig.input_domains[1]),
                        ram_ops.inv_updater(idx, sig.input_domains[1])
                    )

            elif isinstance(sig.name, ops.OffsetName):
                if sig.input_domains[0] == mem_dom:
                    return (ram_ops.offseter(sig.name.index),
                            ram_ops.inv_offseter(sig.name.index))

            elif sig == cpy_offset_sig:
                return ram_ops.copy_offset, ram_ops.inv_copy_offset

            elif (sig == bin_rel_signer(ops.EQ) or
                  sig == bin_rel_signer(ops.NEQ)):
                return _not_implemented, _not_implemented

        return TypeInterpretation(
            mem_dom,
            provider,
            ram_ops.builder
        )


def default_modeled_interpreter(inner):
    @Transformer.as_transformer
    def get_inner_types(tpe):
        if tpe.is_a(types.ModeledType):
            return tpe.actual_type, tpe.model_type

    @Transformer.as_transformer
    def modeled_interpreter(interps):
        actual_interp, model_interp = interps

        dom = domains.Product(actual_interp.domain, model_interp.domain)

        @Transformer.as_transformer
        def original_signature(sig):
            if sig.contains(dom):
                return sig, sig.substituted(dom, actual_interp.domain)

        @Transformer.as_transformer
        def transform_implementation(sig_impl):
            sig, (def_impl, inv_impl) = sig_impl
            implicitly_converted_inputs = set(
                i for i, d in enumerate(sig.input_domains) if d == dom
            )
            implicitly_converted_output = sig.output_domain == dom
            model_top = model_interp.domain.top

            def new_def_impl(*args):
                res = def_impl(*(
                    arg[0] if i in implicitly_converted_inputs else arg
                    for i, arg in enumerate(args)
                ))

                return (res, model_top) if implicitly_converted_output else res

            def new_inv_impl(expected, *constrs):
                new_expected = (
                    expected[0] if implicitly_converted_output else expected
                )
                new_constrs = tuple(
                    constrs[i][0]
                    if i in implicitly_converted_inputs
                    else constrs[i]
                    for i in range(len(constrs))
                )
                res = inv_impl(new_expected, *new_constrs)

                return tuple(
                    (res[i], model_top)
                    if i in implicitly_converted_inputs
                    else res[i]
                    for i in range(len(res))
                )

            return new_def_impl, new_inv_impl

        @Transformer.as_transformer
        def model_provider(sig):
            if sig.name == ops.GET_MODEL and sig.input_domains[0] == dom:
                return product_ops.getter(1), product_ops.inv_getter(dom, 1)

        @Transformer.make_memoizing
        @Transformer.from_transformer_builder
        def provider():
            return (
                original_signature >>
                (Transformer.identity() &
                 actual_interp.def_provider_builder) >>
                transform_implementation
            ) | model_provider

        def builder(lit):
            return actual_interp.builder(lit), model_interp.domain.top

        return TypeInterpretation(
            dom,
            lambda _: provider,
            builder
        )

    return get_inner_types >> inner.lifted() >> modeled_interpreter


@type_interpreter
def default_unknown_interpreter(tpe):
    if tpe.is_a(types.Unknown):
        return new_universe_interpretation()


@memoizing_type_interpreter
@delegating_type_interpreter
def default_type_interpreter():
    return (
        default_boolean_interpreter |
        default_char_interpreter(default_int_range_interpreter) |
        default_int_range_interpreter |
        default_real_range_interpreter |
        default_enum_interpreter |
        custom_pointer_interpreter |
        default_product_interpreter(default_type_interpreter) |
        default_array_interpreter(default_type_interpreter) |
        default_ram_interpreter |
        default_modeled_interpreter(default_type_interpreter) |
        default_unknown_interpreter
    )
