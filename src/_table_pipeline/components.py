"""Explicit assembly of the integrated, feature-owned consumers."""

def configure(runtime):
    from .native_union_policy import install as install_native_union_policy
    install_native_union_policy(runtime)
    runtime.installed_components.append('T04')
    from .independent_union import install as install_independent_union
    install_independent_union(runtime)
    runtime.installed_components.append('T05')
