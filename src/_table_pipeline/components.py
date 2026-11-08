"""Explicit source-branch assembly of installed table consumers."""

def configure(runtime):
    from .header_row_policy import install
    install(runtime)
    runtime.installed_components.append('T15')
