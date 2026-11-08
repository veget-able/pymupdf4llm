"""Explicit source-branch assembly of installed table consumers."""

def configure(runtime):
    from .header_provider import install
    install(runtime)
    runtime.installed_components.append('T11~T14')
