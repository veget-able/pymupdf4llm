"""Explicit source-branch assembly of installed table consumers."""

def configure(runtime):
    from .native_union_policy import install
    install(runtime)
    runtime.installed_components.append('T04')
