"""Explicit source-branch assembly of installed table consumers."""

def configure(runtime):
    from .header_span_policy import install
    install(runtime)
    runtime.installed_components.append('T18')
