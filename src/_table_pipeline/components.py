"""Explicit source-branch assembly of installed table consumers."""

def configure(runtime):
    from .independent_union import install
    install(runtime)
    runtime.installed_components.append('T05')
