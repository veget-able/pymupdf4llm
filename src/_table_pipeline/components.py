"""Explicit source-branch assembly of installed table consumers."""

def configure(runtime):
    from .directional_table_split import install
    install(runtime)
    runtime.installed_components.append('T19')
