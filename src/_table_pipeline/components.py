"""Explicit source-branch assembly of installed table consumers."""

def configure(runtime):
    from .union_split_coherence import install
    install(runtime)
    runtime.installed_components.append('T06')
