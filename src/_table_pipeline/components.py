"""Explicit assembly of the integrated, feature-owned consumers."""

def configure(runtime):
    from .native_union_policy import install as install_native_union_policy
    install_native_union_policy(runtime)
    runtime.installed_components.append('T04')
